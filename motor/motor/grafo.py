"""Grafo fixo que interpreta uma WorkflowSpec dinâmica — padrão fan_out_sintese.

Topologia (espelha a referência dynamic-workflow-harness, ver memória do projeto):

    START → planner → revisar_plano → [fan-out: subagente × N] → avaliar → decidir → sintetizar
                          (attempt → verifier → commit, retry ≤ max_tentativas)
                                  (preencher → reconciliar → avaliar; ou interrupt() ao fundador)

Regras de fronteira (anti-lock-in):
- planner, executor, verifier, evaluator e synthesizer usam tentativas custeadas;
- estado serializável; a spec é dado, não código;
- todo passo emite evento JSONL próprio (painel/auditoria), além do checkpointer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Callable, Mapping, Optional, Sequence, TypeAlias, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing_extensions import assert_never

from .eventos import LogEventos
from .modelos import ClienteModelo, ClienteStub, extrai_json
from .orcamento import (
    ErroOrcamento,
    IdentidadeTentativaCusteada,
    RequisitosTentativaCusteada,
    RepositorioOrcamento,
    RespostaTentativaCusteada,
    RotaTentativaCusteada,
    StatusTentativaTerminal,
    TentativaBloqueadaPreEfeito,
    TentativaReconciliada,
    TentativaTerminal,
    executar_tentativa_custeada,
)
from .politica import PoliticaGates
from .rag import carregar_dataset, recuperar
from .runner import (
    MAX_TIMEOUT_S,
    MIN_TIMEOUT_S,
    CommandRequest,
    CommandRunner,
    DenyCommandRunner,
)
from .spec import ConfigContem, WorkflowSpec

try:
    from jsonschema import ValidationError as JsonSchemaValidationError  # type: ignore[import-untyped]
    from jsonschema import validate as validar_jsonschema  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - fallback para ambiente sem jsonschema.
    JsonSchemaValidationError = None  # type: ignore[assignment]
    validar_jsonschema = None  # type: ignore[assignment]


def mesclar_resultados(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mescla commits de subagentes por id; commits mais novos substituem antigos."""
    por_id = {r["id"]: r for r in a}
    for resultado in b:
        por_id[resultado["id"]] = resultado
    return list(por_id.values())


class EstadoMotor(TypedDict, total=False):
    missao_texto: str
    spec: dict[str, Any]
    run_id: str
    thread_id: str
    resultados: Annotated[list[dict[str, Any]], mesclar_resultados]
    avaliacao: dict[str, Any]
    resposta_final: str
    rodada_reconciliacao: int
    preenchimento_vazio: bool
    decisao_cobertura: str
    escaladas_cobertura: int


@dataclass(frozen=True)
class ChamadaOrcadaSemResposta:
    pass


@dataclass(frozen=True)
class ChamadaOrcadaBloqueada:
    motivo: str


@dataclass(frozen=True)
class ChamadaOrcadaTerminal:
    motivo: str
    status_reserva: StatusTentativaTerminal


ResultadoChamadaOrcada: TypeAlias = (
    RespostaTentativaCusteada
    | ChamadaOrcadaSemResposta
    | ChamadaOrcadaBloqueada
    | ChamadaOrcadaTerminal
)


class _VereditoVerifier(BaseModel):
    model_config = ConfigDict(strict=True)

    aprovado: bool
    motivo: str = "sem motivo"


class _VereditoEvaluator(BaseModel):
    model_config = ConfigDict(strict=True)

    aprovado: bool
    lacunas: list[str] = Field(default_factory=list)
    nos_a_refazer: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coerente(self) -> "_VereditoEvaluator":
        if self.aprovado and (self.lacunas or self.nos_a_refazer):
            raise ValueError("evaluator aprovado nao pode declarar lacunas")
        return self


class _SaidaFerramentaJSON(BaseModel):
    model_config = ConfigDict(strict=True)

    aprovado: bool
    metricas: dict[str, Any] = Field(default_factory=dict)
    motivo: str = ""


def _decisao_texto(valor: Any) -> str | None:
    return valor.strip().lower() if isinstance(valor, str) else None


GABARITO_ROTA_DEFAULT = (
    "entre 2 e {max_sub} subagentes focados e INDEPENDENTES (depende_de sempre []);"
)
ROTA_DEFAULT = {
    "padrao": "fan_out_sintese",
    "gabarito": GABARITO_ROTA_DEFAULT,
}

PROMPT_SELETOR_ROTA = """Escolha a rota de decomposição para a missão abaixo.
Missão:
\"\"\"{missao}\"\"\"

Rotas disponíveis (nome e quando usar):
{catalogo}

Escolha a rota cujo campo "quando" melhor descreve a missão. Se nenhuma servir claramente,
responda "pesquisa-sintese". Responda APENAS um JSON: {{"rota": "<nome>"}}"""

PROMPT_PLANNER = """Você é o planner da meta-fábrica. Missão do usuário:
\"\"\"{missao}\"\"\"

Produza uma WorkflowSpec versão 0.1 em JSON (responda APENAS o JSON), conforme o schema:
{schema}

Regras: {gabarito}
cada subagente com rubrica objetiva e verificável; criterios_cobertura checáveis contra a missão;
padrao = "{padrao}".
Subagentes podem ser executados por modelos de capacidade limitada: escreva cada objetivo sem
ambiguidade nem decisão de design implícita, e rubricas que checam a PRESENÇA de conteúdo
verificável (um tópico abordado, um número, um exemplo, um caso) — nunca critérios que dependem de
bom gosto. Cada rubrica deve ter NO MÁXIMO 5 critérios, e cada critério julga a SUBSTÂNCIA pelo
SIGNIFICADO, não por caracteres exatos: descreva o que a saída deve CONTER ("aborda tratamento de
erros", "lista pelo menos 2 casos de teste"), e NUNCA exija título de seção exato, nível de heading,
formato de ID, prefixo de linha ou estilo de lista (marcador vs numerado) — formatação cosmética não
é critério. NÃO exija versão exata de biblioteca, nomes internos de parâmetros de API, valores-padrão
de funções de terceiros, nem conhecimento factual profundo que um executor de capacidade limitada não
garante: a rubrica é o CONTRATO MÍNIMO do objetivo, não uma prova de erudição nem de formatação.
Para cada subagente, classifique o campo "tier" pela complexidade da tarefa (roteamento por custo):
"simples" (extração/formatação/lookup direto), "media" (pesquisa ou redação com algum raciocínio),
"complexa" (design, trade-offs, modelagem ou síntese que exige um modelo forte).
Para cada subagente, preencha também "capacidades_requeridas": a LISTA de capacidades que a tarefa exige, escolhidas SOMENTE deste vocabulário fixo (use exatamente estas palavras): codigo (escrever/editar/revisar código ou script), redacao (texto natural: relatório, doc, spec, descrição), calculo (quantitativo determinístico: custos, tolerâncias, dimensionamento), pesquisa (levantar info externa: busca, sourcing, lookup), raciocinio-longo (planejamento, trade-offs, design ou síntese multi-passo). Liste só o que a tarefa REALMENTE exige (em geral 1–2 tags). Estas tags valem para qualquer domínio (software, hardware, manufatura): a produção física é de outros executores; aqui você classifica só o trabalho cognitivo.{erro}"""

PROMPT_SUBAGENTE = """Você é o subagente '{id}' (papel: {papel}) de um workflow.
Missão global: {missao_objetivo}
Contexto: {missao_contexto}
Seu objetivo: {objetivo}
Entradas: {entradas}
Resultado esperado: {resultado_esperado}{deps_txt}
Sua saída será avaliada contra esta rubrica — atenda TODOS os critérios:
{rubrica_txt}{feedback}

Entregue diretamente o resultado, específico e fundamentado."""

PROMPT_VERIFIER = """Você é o verificador adversarial do subagente '{id}'.
Objetivo dele: {objetivo}
Rubrica (TODOS os critérios precisam passar):
{rubrica}

Saída a avaliar:
\"\"\"{saida}\"\"\"

Julgue ESTRITAMENTE contra os critérios da rubrica acima: NÃO invente critérios novos nem exija nada
além do que a rubrica lista (sem trazer conhecimento de domínio que não está na rubrica). Se TODOS os
critérios da rubrica forem atendidos, APROVE — mesmo que você imagine melhorias possíveis. Seja cético
quanto ao que a rubrica pede, não quanto ao que você gostaria. Responda APENAS um JSON:
{{"aprovado": true/false, "motivo": "cite QUAL critério da rubrica falhou, específico e acionável"}}"""

PROMPT_EVALUATOR = """Você é o avaliador global de cobertura de um workflow.
Missão: {missao_objetivo}
Critérios de cobertura (TODOS precisam estar cobertos pelos resultados):
{criterios}

Resultados commitados:
{resultados}

Em "nos_a_refazer", liste os ids (EXATAMENTE como aparecem nos resultados) dos subagentes que são a
ORIGEM de cada lacuna/inconsistência — prefira o nó MAIS A MONTANTE responsável (ex.: se a
especificação contradiz a arquitetura, nomeie o nó da especificação), pois refazê-lo re-deriva os que
dependem dele. Se nada precisa refazer, use [].
Responda APENAS um JSON: {{"aprovado": true/false, "lacunas": ["o que falta", ...], "nos_a_refazer": ["id", ...]}}"""

PROMPT_SYNTHESIZER = """Você é o sintetizador final de um workflow.
Missão: {missao_objetivo}
Instrução de síntese: {instrucao} (formato: {formato})

Resultados verificados dos subagentes:
{resultados}
{reprovados}
Produza a resposta final da missão."""

# Bloco só presente quando algo reprovou. Antes ele não existia: o sintetizador
# recebia SOMENTE os resultados aprovados e mesmo assim a spec lhe pedia para
# declarar reprovação. Ele não mentiu — não tinha como saber. Sonegar a falha e
# depois cobrar honestidade sobre ela é um jeito garantido de produzir relatório
# otimista.
BLOCO_REPROVADOS = """
ATENÇÃO — estes subagentes REPROVARAM e a missão NÃO está pronta:
{itens}
A resposta precisa dizer isso explicitamente. Não apresente o trabalho como
entregue."""


# Força da prova que cobre um artefato, do mais forte para o mais fraco.
#
# A distinção não é acadêmica: é o que a landing promete ("nada vira 'pronto' sem
# prova que atravesse um portão") e o que separa o Kortex de encadear LLMs.
#
# - `execucao`: um processo rodou o artefato e o exit code decidiu. É prova de
#   COMPORTAMENTO -- a suíte passou, o script rodou.
# - `estrutural`: checagem determinística de forma (`schema_json`, `contem`).
#   Prova que o artefato tem o formato certo, NÃO que ele funciona. JSON que
#   valida contra schema pode estar inteiramente errado.
# - `opiniao`: só um modelo leu e achou bom. É o default quando não há validador,
#   porque o verifier sempre roda -- e é exatamente o que qualquer um consegue
#   encadeando LLMs.
FORCA_DA_PROVA = {"comando": "execucao", "schema_json": "estrutural",
                  "contem": "estrutural"}
ORDEM_DA_PROVA = ["execucao", "estrutural", "opiniao"]


def cobertura_de_evidencia(
    spec: Mapping[str, Any],
    resultados: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Que tipo de prova cobre cada artefato da missão.

    A razão execução/total é a métrica do produto: ela responde "quanto disto foi
    provado e quanto foi só opinado". Sem medir, "portão de evidência" é slogan.

    Sem `resultados`, mede o que a spec PROMETE — é o que o corpus de exemplos
    checa. Com `resultados`, mede o que de fato aconteceu: portão que reprovou ou
    que nem chegou a rodar deixa de contar como prova.

    Essa distinção foi achado da auditoria GPT-5 (2026-07-29, C-02): a versão
    anterior lia só a spec e escrevia "passaram por portão de execução" mesmo com
    o validador tendo saído com exit code 1. A frase é uma afirmação sobre
    RESULTADO, e a função só conhecia CONFIGURAÇÃO.
    """
    subagentes = spec.get("subagentes") or []
    if not isinstance(subagentes, list):
        return {"artefatos": [], "execucao": 0, "total": 0,
                "medido": resultados is not None}

    aprovado_por_id: dict[str, bool] | None = None
    if resultados is not None:
        # `is True`, não `bool(...)`: `bool("false")` é True, e a métrica de
        # cobertura é o último lugar do sistema onde se pode aceitar coerção
        # generosa. Achado da segunda rodada da trava GPT-5 (C-04). Hoje o motor
        # só emite bool aqui, mas o mesmo rigor de `_recomputar_sombra` vale.
        #
        # Id repetido: o ÚLTIMO vence, e isso é intencional. `resultados` é
        # cronológico, e nó que reprovou e passou na retentativa está coberto --
        # o veredito válido é o final. A 3ª rodada da trava leu isso como defeito
        # ("dá para escolher o resultado aprovado pela ordem"); só seria se a
        # ordem viesse de fora, e ela vem do próprio append do motor.
        # Id vazio fica de fora: sem isto, um resultado sem `id` e um validador
        # sem `id` viravam ambos "" e casavam entre si -- string vazia como
        # chave-curinga. A spec exige id nao vazio, entao isto e cinto e
        # suspensorio; achado da 4a rodada da trava GPT-5 (C-09).
        aprovado_por_id = {
            str(r.get("id", "")): r.get("aprovado") is True
            for r in resultados
            if isinstance(r, Mapping) and str(r.get("id", "")).strip()
        }

    # Prova mais forte encontrada por alvo. Vários validadores no mesmo nó valem
    # pelo melhor: quem roda a suíte E confere o schema está coberto por execução.
    prova_por_alvo: dict[str, str] = {}
    falhou_por_alvo: dict[str, bool] = {}
    for sub in subagentes:
        if not isinstance(sub, dict) or sub.get("tipo") != "validador":
            continue
        kind = str((sub.get("validador") or {}).get("kind") or "")
        forca = FORCA_DA_PROVA.get(kind)
        alvo = str(sub.get("valida") or "")
        if not forca or not alvo:
            continue
        sub_id = str(sub.get("id", "")).strip()
        if aprovado_por_id is not None and not (
            sub_id and aprovado_por_id.get(sub_id)
        ):
            # Portão que reprovou ou que não rodou não é prova de nada. Ausente do
            # log conta como não-prova pelo mesmo motivo que reprovado: em ambos
            # os casos ninguém viu o artefato passar.
            falhou_por_alvo[alvo] = True
            continue
        atual = prova_por_alvo.get(alvo)
        if atual is None or ORDEM_DA_PROVA.index(forca) < ORDEM_DA_PROVA.index(atual):
            prova_por_alvo[alvo] = forca

    artefatos: list[dict[str, Any]] = []
    for sub in subagentes:
        if not isinstance(sub, dict) or sub.get("tipo") == "validador":
            continue
        produzidos = [
            str(a.get("nome", "")) for a in (sub.get("produz_artefatos") or [])
            if isinstance(a, dict)
        ]
        if not produzidos:
            continue
        node_id = str(sub.get("id", ""))
        artefatos.append({
            "id": node_id,
            "artefatos": produzidos,
            "prova": prova_por_alvo.get(node_id, "opiniao"),
            "portao_falhou": bool(falhou_por_alvo.get(node_id)),
        })

    # Denominador em ARTEFATOS, não em nós -- outro achado da auditoria GPT-5
    # (C-01). Contando nós, um nó com 1 artefato coberto e outro com 100
    # descobertos davam "1 de 2 = 50%", quando a cobertura real era 1 de 101.
    # Métrica de cobertura que superestima é pior que métrica nenhuma.
    return {
        "artefatos": artefatos,
        "execucao": sum(len(a["artefatos"]) for a in artefatos
                        if a["prova"] == "execucao"),
        "total": sum(len(a["artefatos"]) for a in artefatos),
        # `medido=False` e a leitura spec-only: promessa, nao resultado. O campo
        # existe para que os dois modos nao tenham a MESMA cara na saida -- um
        # consumidor futuro publicando promessa como cobertura observada era o
        # risco apontado na 4a rodada da trava (C-08).
        "medido": resultados is not None,
    }


# Frases que SÓ o motor tem autoridade para escrever. Se aparecerem no texto do
# sintetizador, foram imitadas.
FRASES_CARIMBADAS = ("Cobertura de evidência:", "⚠️ RUN REPROVADO")
AVISO_IMITACAO = "[texto do modelo, não é o carimbo do motor] "


def desautorizar_imitacao(texto: str) -> str:
    """Neutraliza carimbo falsificado dentro do texto do sintetizador.

    Achado da 3ª rodada da trava GPT-5. O carimbo era só concatenado, então o
    modelo podia escrever "Cobertura de evidência: 100 de 100 artefatos passaram
    por portão de execução" no próprio corpo e o carimbo real vinha depois: duas
    coberturas em conflito, e quem lesse a primeira -- humano com pressa ou script
    com regex -- levava a forjada.

    O ataque não precisa de má-fé do modelo: basta ele resumir o rodapé de um run
    anterior. Carimbo cuja autoridade depende de o leitor escolher a ocorrência
    certa não é carimbo.
    """
    for frase in FRASES_CARIMBADAS:
        texto = texto.replace(frase, AVISO_IMITACAO + frase)
    return texto


def carimbar_evidencia(texto: str, state: Mapping[str, Any]) -> str:
    """Declara na resposta que tipo de prova cobriu os artefatos.

    O buraco que isto fecha: até aqui, uma missão com ZERO portão de processo
    terminava com uma resposta tão confiante quanto uma cujos testes passaram.
    Ausência de prova era indistinguível de prova -- o pior modo de falha
    possível para um produto cuja tese é justamente a prova.

    Neutro de propósito, e não alarmista. Missão de texto não tem o que executar,
    e carimbar aviso vermelho nela treinaria você a ignorar o carimbo -- que é
    como se perde o carimbo de reprovação junto.
    """
    texto = desautorizar_imitacao(texto)
    spec = state.get("spec") or {}
    # Com os resultados: "passaram" é afirmação sobre o que aconteceu, então tem
    # que ser lida do que aconteceu.
    cobertura = cobertura_de_evidencia(spec, state.get("resultados") or [])
    if not cobertura["total"]:
        return texto

    linhas = [
        f"Cobertura de evidência: {cobertura['execucao']} de {cobertura['total']} "
        f"artefatos passaram por portão de execução."
    ]
    for item in cobertura["artefatos"]:
        if item["prova"] != "execucao":
            if item["portao_falhou"]:
                rotulo = "portão de execução NÃO aprovou este artefato"
            elif item["prova"] == "opiniao":
                rotulo = "verificado só por opinião de modelo"
            else:
                rotulo = "checado só na forma, não no comportamento"
            linhas.append(f"- {item['id']} ({', '.join(item['artefatos'])}): {rotulo}")
    return texto + "\n\n---\n\n" + "\n".join(linhas)


def reprovados_de(state: Mapping[str, Any]) -> list[dict[str, str]]:
    """Nós reprovados, do estado — não da narrativa de ninguém."""
    return [
        {"id": str(r.get("id", "")), "motivo": str(r.get("motivo", ""))}
        for r in state.get("resultados", []) or []
        if isinstance(r, dict) and not r.get("aprovado")
    ]


def carimbar_reprovacao(texto: str, state: Mapping[str, Any]) -> str:
    """Prefixa a síntese com o veredito REAL, derivado do estado.

    Existe porque instrução de prompt não segura isto. Em 2026-07-28 o
    sintetizador apresentou como entrega pronta um run cujo validador havia
    falhado, com a spec mandando, em português claro, declarar a reprovação na
    primeira linha. Pedir a um modelo que seja honesto sobre o próprio fracasso
    é pedir; carimbo montado a partir do log é fato.

    O cabeçalho é montado aqui, não pelo modelo, então ele não tem como reescrevê-lo
    nem omiti-lo. É isto que torna verdadeira a promessa de que nada vira "pronto"
    sem prova que atravesse um portão.
    """
    avaliacao = state.get("avaliacao") or {}
    reprovados = reprovados_de(state)
    lacunas = [str(item) for item in (avaliacao.get("lacunas") or [])]
    # `prosseguir_parcial` é o gate de cobertura tendo sido liberado APESAR de
    # reprovado; sem ele o run pode ter nós reprovados e ainda assim ter passado.
    parcial = bool(avaliacao.get("prosseguir_parcial"))
    if not reprovados and not parcial:
        return texto

    linhas = ["⚠️ RUN REPROVADO — o conteúdo abaixo NÃO é entregável."]
    if parcial:
        linhas.append("portão de cobertura: liberado com lacunas, não aprovado")
    for lacuna in lacunas:
        linhas.append(f"lacuna: {lacuna}")
    for item in reprovados:
        motivo = item["motivo"].strip().splitlines()[0] if item["motivo"].strip() else "sem motivo"
        linhas.append(f"subagente reprovado: {item['id']} — {motivo}")
    return "\n".join(linhas) + "\n\n---\n\n" + texto


ORDEM_TIER = ["simples", "media", "complexa"]


def _proximo_tier(t: str | None) -> str:
    """Próximo degrau acima na escada de dificuldade. Teto = 'complexa'."""
    if t in ORDEM_TIER and ORDEM_TIER.index(t) < len(ORDEM_TIER) - 1:
        return ORDEM_TIER[ORDEM_TIER.index(t) + 1]
    return "complexa"


def montar_prompt_planner(*, missao: str, schema: str, max_sub: int, erro: str = "",
                           rota: dict[str, Any] | None = None) -> str:
    rota_ativa = rota or ROTA_DEFAULT
    gabarito = str(rota_ativa.get("gabarito") or "").replace("{max_sub}", str(max_sub))
    return PROMPT_PLANNER.format(
        missao=missao,
        schema=schema,
        gabarito=gabarito,
        padrao=rota_ativa["padrao"],
        erro=erro,
    )


def _formatar_contexto_rag(fonte: str, registros: list[dict[str, Any]]) -> str:
    partes = []
    for i, registro in enumerate(registros, start=1):
        metadados = []
        for chave in ("id", "origem", "licenca"):
            valor = registro.get(chave)
            if valor:
                metadados.append(f"{chave}: {valor}")
        cabecalho = f"[{i}]"
        if metadados:
            cabecalho += " " + " · ".join(metadados)
        partes.append(f"{cabecalho}\n{registro['conteudo']}")
    corpo = "\n\n".join(partes)
    return (
        f"\n\nCONTEXTO RECUPERADO (fonte: {fonte}, use se relevante; "
        f"NÃO invente além disto):\n{corpo}"
    )


def _validar_schema_json(saida: str, config: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    schema = config.get("schema")
    if not isinstance(schema, dict):
        return False, "config.schema ausente ou inválido", {"erro": "schema inválido"}
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as ex:
        return False, f"JSON inválido: {ex.msg}", {"erro": ex.msg}
    if validar_jsonschema is None:
        # A-06: aqui existia um fallback que ignorava enum/minimum/pattern/oneOf
        # e devolvia o MESMO "schema_json aprovado". O portao ficava mais fraco
        # conforme o ambiente, sem evento que distinguisse os dois modos -- e o
        # carimbo saia `estrutural` sobre algo que ninguem checou. Portao que
        # nao consegue checar reprova; nao aprova com menos rigor.
        motivo = "schema_json indisponivel: jsonschema ausente no ambiente"
        return False, motivo, {"erro": "jsonschema ausente"}
    try:
        validar_jsonschema(instance=dados, schema=schema)
    except Exception as ex:
        if JsonSchemaValidationError is not None and isinstance(ex, JsonSchemaValidationError):
            caminho = ".".join(str(p) for p in ex.path)
            local = f" em {caminho}" if caminho else ""
            return False, f"schema_json falhou{local}: {ex.message}", {"erro": ex.message}
        return False, f"schema_json falhou: {ex}", {"erro": str(ex)}
    return True, "schema_json aprovado", {"json": dados}


def _validar_contem(saida: str, config: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    try:
        config_validada = ConfigContem.model_validate(config)
    except ValidationError as ex:
        return False, "config contem inválida", {"erro": str(ex)}
    requer = config_validada.requer
    minimo = config_validada.minimo
    texto = saida.casefold()
    presentes = [item for item in requer if item.casefold() in texto]
    faltantes = [item for item in requer if item not in presentes]
    aprovado = len(presentes) >= minimo
    if aprovado:
        return True, "contem aprovado", {"presentes": presentes, "faltantes": faltantes, "min": minimo}
    return (
        False,
        f"contem falhou: presentes {len(presentes)}/{minimo}; faltantes: {', '.join(faltantes)}",
        {"presentes": presentes, "faltantes": faltantes, "min": minimo},
    )


def registrar_artefato(workspace: str | Path, nome: str, tipo: str, conteudo: str) -> dict[str, str]:
    """Escreve conteúdo textual no workspace e devolve só a referência serializável."""
    raiz = Path(workspace)
    raiz.mkdir(parents=True, exist_ok=True)
    caminho = raiz / nome
    caminho.write_text(conteudo, encoding="utf-8")
    digest = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()
    return {"nome": nome, "caminho": str(caminho), "tipo": tipo, "hash": digest}


def referenciar_artefato(caminho: str | Path, nome: str, tipo: str) -> dict[str, str]:
    caminho = Path(caminho)
    digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
    return {"nome": nome, "caminho": str(caminho), "tipo": tipo, "hash": digest}


def construir_grafo(cliente: ClienteModelo, log: LogEventos, checkpointer=None,
                    politica: PoliticaGates | None = None,
                    workspace_base: str | Path = "runs",
                    ferramentas: dict[str, dict[str, Any]] | None = None,
                    rota: dict[str, Any] | None = None,
                    rotas: dict[str, dict[str, Any]] | None = None,
                    escalar_em_retry: bool = False,
                    max_rodadas_reconciliacao: int = 1,
                    max_escaladas: int = 1,
                    perfil_execucao: str = "certificado",
                    ferramentas_permitidas: list[str] | None = None,
                    command_runner: CommandRunner | None = None,
                    repositorio_orcamento: RepositorioOrcamento | None = None,
                    medicao_monetaria_desligada: bool = False,
                    fabrica_tentativas_orcadas: Callable[
                        [str, str, int, RequisitosTentativaCusteada],
                        list[RotaTentativaCusteada],
                    ] | None = None,
                    teto_bootstrap: Decimal = Decimal("2.0")):
    """Compila o grafo. `cliente` e `log` são injetados — o grafo não conhece backends.
    `politica` decide quais gates pausam (manual) ou resolvem sozinhos (auto-mode);
    ausente = tudo manual (comportamento default).
    `max_escaladas` limita quantas vezes um portao reprovado sobe para um juiz
    independente. E a contencao principal do modo automatico: escalada e o
    primeiro lugar do sistema onde uma falha gera trabalho sozinha, e sem teto um
    portao teimoso consome a assinatura a noite inteira. Esgotado, o motor CHAMA
    O FUNDADOR -- degrada para humano, nunca para liberacao silenciosa.

    `max_rodadas_reconciliacao` limita quantas rodadas de preenchimento de cobertura
    podem rodar antes de seguir parcial."""
    politica = politica or PoliticaGates()
    if (not isinstance(teto_bootstrap, Decimal) or not teto_bootstrap.is_finite()
            or teto_bootstrap <= 0):
        raise ErroOrcamento("teto bootstrap invalido")
    # Absoluto desde a construcao: o sandbox monta o workspace como bind e recusa
    # caminho relativo, entao `--workspace runs` fazia TODO validador de comando
    # morrer em "workspace absoluto existente obrigatorio" -- com o portao
    # reprovando pelo motivo certo e a causa parecendo do sandbox, nao da CLI.
    # Caminho relativo tambem e ambiguo para qualquer runner que troque de cwd.
    workspace_base = Path(workspace_base).resolve()
    ferramentas = ferramentas or {}
    command_runner = command_runner if command_runner is not None else DenyCommandRunner()
    perfil_execucao = "rascunho" if perfil_execucao == "rascunho" else "certificado"
    # Quando o runner tem sistema de arquivos proprio (sandbox), quem responde
    # pelo executavel e a allowlist selada JUNTO COM A IMAGEM, e nao a config de
    # ferramentas do host: `/usr/local/bin/python3` existe dentro da imagem e nao
    # fora dela. Resolver contra o host aqui reprovaria todo comando, e o sandbox
    # ficaria ligado sem nunca executar nada.
    namespace_proprio = bool(getattr(command_runner, "namespace_proprio", False))
    executaveis_permitidos: set[Path] = set()
    if namespace_proprio:
        executaveis_permitidos = {
            Path(item) for item in getattr(command_runner, "executaveis", ())
        }
    else:
        for executavel_bruto in ferramentas_permitidas or []:
            executavel = Path(str(executavel_bruto).strip())
            if not executavel.is_absolute():
                continue
            try:
                identidade = executavel.resolve(strict=True)
            except OSError:
                continue
            if identidade.is_file() and os.access(identidade, os.X_OK):
                executaveis_permitidos.add(identidade)

    def run_id_de(state: EstadoMotor) -> str:
        return state.get("run_id") or f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"

    def chamar_planner_orcado(
        state: EstadoMotor, run_id: str, prompt: str, tentativa: int,
        fase: str = "spec",
    ) -> str | None:
        thread_id = state.get("thread_id") or (run_id if isinstance(cliente, ClienteStub) else None)
        resultado = chamar_orcado(
            run_id, thread_id, teto_bootstrap, "planner", fase, "planner", prompt, tentativa,
        )
        resposta = resposta_orcada_ou_none(resultado)
        return resposta.texto if resposta is not None else None

    def resposta_orcada_ou_none(
        resultado: ResultadoChamadaOrcada,
    ) -> RespostaTentativaCusteada | None:
        match resultado:
            case RespostaTentativaCusteada():
                return resultado
            case (
                ChamadaOrcadaSemResposta()
                | ChamadaOrcadaBloqueada()
                | ChamadaOrcadaTerminal()
            ):
                return None
            case _:
                assert_never(resultado)

    def chamar_orcado(
        run_id: object,
        thread_id: object,
        teto: object,
        papel: str,
        fase: str,
        no_id: str,
        prompt: str,
        tentativa: int,
        requisitos: RequisitosTentativaCusteada | None = None,
        ciclo: int = 0,
    ) -> ResultadoChamadaOrcada:
        if fabrica_tentativas_orcadas is None:
            raise ErroOrcamento("fabrica de adaptadores custeados ausente")
        if type(medicao_monetaria_desligada) is not bool:
            raise ErroOrcamento("medicao monetaria invalida")
        if repositorio_orcamento is None and not medicao_monetaria_desligada:
            raise ErroOrcamento("repositorio de orcamento ausente")
        if isinstance(run_id, str) and not isinstance(thread_id, str) and isinstance(cliente, ClienteStub):
            thread_id = run_id
        if not isinstance(run_id, str) or not isinstance(thread_id, str):
            raise ErroOrcamento("identidade da execucao ausente")
        try:
            teto_decimal = Decimal(str(teto))
        except Exception as erro:
            raise ErroOrcamento("teto de orcamento invalido") from erro
        cadeia = fabrica_tentativas_orcadas(
            papel, prompt, tentativa, requisitos or RequisitosTentativaCusteada()
        )
        if not isinstance(cadeia, list) or not cadeia:
            raise ErroOrcamento("adaptador custeado ausente")
        if medicao_monetaria_desligada:
            for indice, item in enumerate(cadeia, start=1):
                if not isinstance(item, RotaTentativaCusteada):
                    raise ErroOrcamento("adaptador custeado invalido")
                route_id, provider_id, adaptador = item.route_id, item.provider_id, item.adaptador
                if requisitos is not None and provider_id == requisitos.evitar_provedor:
                    continue
                tentar = getattr(adaptador, "tentar_uma_vez_sem_medicao", None)
                if not callable(tentar):
                    raise ErroOrcamento("adaptador sem caminho sem medicao")
                try:
                    texto = tentar()
                except Exception:
                    continue
                if isinstance(texto, str) and texto:
                    log.evento(
                        "modelo.atendeu", papel=papel, fase=fase,
                        modelo=route_id, provedor=provider_id, tentativa=indice,
                    )
                    return RespostaTentativaCusteada(texto, route_id, provider_id)
            return ChamadaOrcadaSemResposta()
        if repositorio_orcamento is None:
            raise ErroOrcamento("repositorio de orcamento ausente")
        sessao = repositorio_orcamento.sessao(run_id, thread_id, teto_decimal)
        bloqueios: list[tuple[str, str]] = []
        modelo_sem_resposta = False
        for indice, item in enumerate(cadeia, start=1):
            if not isinstance(item, RotaTentativaCusteada):
                raise ErroOrcamento("adaptador custeado invalido")
            route_id, provider_id, adaptador = item.route_id, item.provider_id, item.adaptador
            if requisitos is not None and provider_id == requisitos.evitar_provedor:
                continue
            prompt_id = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            call_base = f"{run_id}:{thread_id}:{fase}:{no_id}:{ciclo}:{tentativa}:{prompt_id}"
            call_id = (
                f"planner-{fase}-{tentativa}" if papel == "planner"
                else f"{fase}-{hashlib.sha256(call_base.encode()).hexdigest()[:32]}"
            )
            base = f"{run_id}:{thread_id}:{call_id}:{route_id}:{indice}"
            prefixo = "planner" if papel == "planner" else fase
            identidade = IdentidadeTentativaCusteada(
                reservation_id=f"{prefixo}-{hashlib.sha256(base.encode()).hexdigest()[:32]}",
                call_id=call_id,
                route_id=route_id,
                attempt=indice,
            )
            resultado = executar_tentativa_custeada(
                repositorio_orcamento, sessao, identidade, adaptador,
            )
            match resultado:
                case TentativaReconciliada(resultado=resultado_reconciliado):
                    if resultado_reconciliado.texto:
                        # Qual modelo REALMENTE atendeu. `executor.chamado` só consegue
                        # dizer "omniroute/roteado", porque a rota só é escolhida aqui,
                        # percorrendo a cadeia de failover.
                        #
                        # Não é cosmético: o curador perfila aptidão por modelo lendo o
                        # campo `modelo` do log. Sem este evento, Gemini, Opus e Codex
                        # caem todos no mesmo balde `omniroute/roteado` e o perfil por
                        # modelo -- a entrada do flywheel inteiro -- vira uma linha só.
                        log.evento("modelo.atendeu", papel=papel, fase=fase,
                                   modelo=route_id, provedor=provider_id,
                                   tentativa=indice)
                        return RespostaTentativaCusteada(
                            resultado_reconciliado.texto, route_id, provider_id,
                        )
                    modelo_sem_resposta = True
                case TentativaBloqueadaPreEfeito(motivo=motivo):
                    bloqueios.append((route_id, motivo))
                case TentativaTerminal(motivo=motivo, status_reserva=status_reserva):
                    return ChamadaOrcadaTerminal(motivo, status_reserva)
                case _:
                    assert_never(resultado)
        if modelo_sem_resposta:
            return ChamadaOrcadaSemResposta()
        if bloqueios:
            detalhes = "; ".join(
                f"{route_id}={motivo}" for route_id, motivo in bloqueios
            )
            return ChamadaOrcadaBloqueada(f"bloqueio pré-efeito: {detalhes}")
        return ChamadaOrcadaBloqueada("nenhuma rota elegível")

    def workspace_de(state: EstadoMotor) -> Path:
        return workspace_base / state["run_id"] / "artefatos"

    def _template_evento(spec: dict[str, Any]) -> dict[str, str]:
        missao = spec.get("missao") or {}
        dados = {}
        if missao.get("template"):
            dados["template"] = str(missao["template"])
        if missao.get("versao_template"):
            dados["versao_template"] = str(missao["versao_template"])
        return dados

    def _descricao_modelo(papel: str, tier: str | None = None,
                          ferramentas: str | None = None,
                          capacidades: list[str] | None = None) -> str | None:
        if hasattr(cliente, "descricao_de"):
            return cast(Optional[str], cliente.descricao_de(papel, tier, ferramentas, capacidades=capacidades))
        prov = getattr(cliente, "provedor", None)
        mapa = getattr(cliente, "mapa_papeis", None)
        modelo = mapa.get(papel) if isinstance(mapa, dict) and papel in mapa else getattr(cliente, "modelo", None)
        if prov and modelo:
            return f"{prov}/{modelo}"
        return str(prov) if prov else (str(modelo) if modelo else None)

    def teto_declarado(bruto: object) -> bool:
        """Alguém escreveu um teto, ou é o default 2.0 do schema?"""
        if not isinstance(bruto, dict):
            return False
        restricoes = bruto.get("restricoes")
        return isinstance(restricoes, dict) and "teto_custo" in restricoes

    def com_teto_do_operador(spec: WorkflowSpec) -> WorkflowSpec:
        """Faz a missão herdar o teto que o operador autorizou.

        `Restricoes.teto_custo` tem default 2.0 e virou o teto real de gasto de
        todo nó custeado. O planner recebe o schema no prompt e ecoa esse 2.0 —
        o número não é decisão dele, e sem isto o orçamento efetivo de qualquer
        missão gerada é um default de Pydantic. Spec escrita por humano é outra
        coisa: lá o teto declarado é decisão, e continua valendo.
        """
        dados = spec.model_dump()
        dados["restricoes"]["teto_custo"] = float(teto_bootstrap)
        log.evento("teto.herdado", teto=str(teto_bootstrap))
        return WorkflowSpec.model_validate(dados)

    def planner(state: EstadoMotor) -> dict:
        run_id = run_id_de(state)
        log.evento("run.perfil", perfil=perfil_execucao)
        if state.get("spec"):  # spec fornecida pelo usuário: valida e segue (missão dirigida por dado)
            spec = WorkflowSpec.model_validate(state["spec"])
            # O teto bootstrap é a única contenção monetária do sistema, e a spec
            # vinda da CLI/serviço é o entrypoint de produção. Confrontar só o ramo
            # gerado pelo planner deixaria o teto contornável por quem escreve o
            # arquivo de spec — que é o caminho normal, não a exceção.
            if Decimal(str(spec.restricoes.teto_custo)) > teto_bootstrap:
                raise ValueError(
                    f"spec fornecida nao pode elevar teto bootstrap "
                    f"({spec.restricoes.teto_custo} > {teto_bootstrap})"
                )
            if not teto_declarado(state["spec"]):
                spec = com_teto_do_operador(spec)
            log.evento("spec.recebida", missao=spec.missao.id, subagentes=len(spec.subagentes))
            return {"spec": spec.model_dump(), "run_id": run_id}
        rota_ativa = rota
        if rota_ativa is None and rotas:
            catalogo = [
                {"nome": nome, "quando": item.get("quando", "")}
                for nome, item in rotas.items()
            ]
            resposta_rota = chamar_planner_orcado(
                state, run_id, PROMPT_SELETOR_ROTA.format(
                    missao=state["missao_texto"],
                    catalogo=json.dumps(catalogo, ensure_ascii=False),
                ), 1, fase="rota",
            )
            bruto_rota = extrai_json(resposta_rota or "")
            nome_rota = (
                str(bruto_rota.get("rota") or "").strip()
                if isinstance(bruto_rota, dict) else ""
            )
            fallback = nome_rota not in rotas
            if fallback:
                nome_rota = "pesquisa-sintese" if "pesquisa-sintese" in rotas else ""
            escolhida = rotas.get(nome_rota) or ROTA_DEFAULT
            log.evento("rota.escolhida", rota=nome_rota or "pesquisa-sintese",
                       padrao=escolhida["padrao"], fallback=fallback)
            rota_ativa = rotas.get(nome_rota) if nome_rota is not None else ROTA_DEFAULT
            rota_ativa = rota_ativa or ROTA_DEFAULT
        erro = ""
        for tentativa in (1, 2, 3):
            log.evento("executor.chamado", executor="planner", tentativa=tentativa,
                       modelo=_descricao_modelo("planner"))
            prompt = montar_prompt_planner(
                missao=state["missao_texto"],
                schema=json.dumps(WorkflowSpec.model_json_schema(), ensure_ascii=False),
                max_sub=10, erro=erro, rota=rota_ativa)
            resp = chamar_planner_orcado(state, run_id, prompt, tentativa)
            bruto = extrai_json(resp or "")
            if bruto is not None:
                try:
                    spec = WorkflowSpec.model_validate(bruto)
                    if Decimal(str(spec.restricoes.teto_custo)) > teto_bootstrap:
                        raise ValueError("spec gerada nao pode elevar teto bootstrap")
                    spec = com_teto_do_operador(spec)
                    log.evento("spec.criada", missao=spec.missao.id, subagentes=len(spec.subagentes))
                    return {"spec": spec.model_dump(), "run_id": run_id}
                except Exception as ex:  # validação pydantic reprovada → reinjeta o erro
                    erro = f"\n\nSua tentativa anterior falhou na validação: {ex}\nCorrija e reenvie só o JSON."
            else:  # sem JSON parseável → reinjeta instrução (senão a retentativa repete às cegas)
                erro = ("\n\nSua resposta anterior NÃO continha um objeto JSON válido. Responda APENAS o "
                        "objeto JSON da WorkflowSpec, sem nenhum texto antes ou depois e sem cercas de código (```).")
            log.evento("executor.erro", executor="planner", motivo="spec inválida ou sem JSON", tentativa=tentativa)
        raise RuntimeError("planner não produziu WorkflowSpec válida em 3 tentativas")

    def plano_de(spec: dict[str, Any]) -> list[dict[str, Any]]:
        plano = []
        for sub in spec["subagentes"]:
            modelo = None
            if sub.get("tipo", "modelo") == "modelo":
                modelo = (cliente.provedor_de(sub["papel"], sub.get("tier"), sub.get("ferramentas"),
                                              capacidades=sub.get("capacidades_requeridas"))
                          if hasattr(cliente, "provedor_de") else None)
            plano.append({
                "id": sub["id"],
                "papel": sub.get("papel"),
                "tier": sub.get("tier"),
                "modelo": modelo,
                "objetivo": sub["objetivo"],
            })
        return plano

    def revisar_plano(state: EstadoMotor) -> dict:
        spec = state["spec"]
        plano = plano_de(spec)
        auto = _decisao_texto(politica.decisao_auto("plano", default="prosseguir"))
        if auto in {"prosseguir", "abortar"}:
            log.evento("gate.auto", portao="plano", decisao=auto)
            if auto == "abortar":
                return {"avaliacao": {"abortada": True, "motivo": "plano rejeitado"}}
            return {}

        log.evento("escalado", para="plano")
        decisao = interrupt({
            "portao": "plano",
            "plano": plano,
            "pergunta": "Revise o plano. prosseguir / editar / abortar",
            "opcoes": "prosseguir · editar · abortar",
        })

        if isinstance(decisao, dict):
            edicoes = dict(decisao)
            spec_editada = {**spec, "subagentes": [dict(s) for s in spec["subagentes"]]}
            ids = {sub["id"] for sub in spec_editada["subagentes"]}
            desconhecidos = set(edicoes) - ids
            if desconhecidos:
                raise ValueError(
                    f"edicao referencia subagente desconhecido: {sorted(map(str, desconhecidos))}"
                )
            for sub in spec_editada["subagentes"]:
                if sub["id"] in edicoes:
                    sub["tier"] = edicoes[sub["id"]]
            spec_validada = WorkflowSpec.model_validate(spec_editada).model_dump()
            log.evento("decisao.plano", edicoes=edicoes)
            return {"spec": spec_validada}

        decisao_txt = _decisao_texto(decisao)
        log.evento("decisao.plano", decisao=str(decisao))
        if decisao_txt == "prosseguir":
            return {}
        if decisao_txt == "abortar":
            return {"avaliacao": {"abortada": True, "motivo": "plano rejeitado"}}
        return {"avaliacao": {"abortada": True, "motivo": "decisao de plano invalida"}}

    def despachar(state: EstadoMotor):
        spec = state["spec"]
        log.evento("paralelo.iniciado", subagentes=[s["id"] for s in spec["subagentes"]])
        workspace = workspace_de(state)
        return [Send("subagente", {
            "sub": s, "spec": spec, "workspace": workspace,
            "run_id": state.get("run_id"), "thread_id": state.get("thread_id"),
        }) for s in spec["subagentes"]]

    def rota_pos_plano(state: EstadoMotor):
        if state.get("avaliacao", {}).get("abortada"):
            return END
        if state["spec"]["padrao"] == "grafo_dependencias":
            return "executar_grafo_dep"
        return despachar(state)

    def subagente(payload: dict) -> dict:
        sub, spec = payload["sub"], payload["spec"]
        missao = spec["missao"]
        max_t = spec["restricoes"]["max_tentativas"]
        deps = payload.get("deps", {})
        deps_txt = ""
        if deps:
            deps_txt = "\nResultados das dependências:\n" + "\n".join(
                f"- {sid}: {saida}" for sid, saida in deps.items()
            )
        if sub.get("tipo", "modelo") == "ferramenta":
            return executar_ferramenta(sub, payload["workspace"])
        if sub.get("tipo", "modelo") == "validador":
            return executar_validador(sub, deps, payload["workspace"])

        capacidades = sub.get("capacidades_requeridas")
        if capacidades and getattr(cliente, "roteamento_capacidades_runtime", False) is not True:
            motivo = "cliente sem roteamento runtime por capacidade"
            log.evento("registro.sem_executor", papel=sub["papel"], capacidades=capacidades)
            log.evento("executor.erro", executor=sub["id"], motivo=motivo, tentativa=1)
            return {"resultados": [{
                "id": sub["id"], "saida": "", "tentativas": 0,
                "aprovado": False, "motivo": motivo,
            }]}

        tier_atual = sub.get("tier")
        capacidades_tupla = (
            tuple(capacidades) if isinstance(capacidades, list) else None
        )
        rubrica_txt = "\n".join(f"- {c}" for c in sub["rubrica"])
        feedback, ultima = payload.get("feedback", ""), payload.get("rascunho_anterior")
        contexto_rag = ""
        fonte_rag = sub.get("fonte_rag")
        if fonte_rag:
            consulta = f"{sub['objetivo']} {json.dumps(sub.get('entradas', {}), ensure_ascii=False)}"
            k_rag = int(sub.get("rag_k", 5))
            recs = recuperar(carregar_dataset(fonte_rag), consulta, k_rag)
            log.evento(
                "rag.consultado",
                subagente=sub["id"],
                fonte=fonte_rag,
                k=k_rag,
                recuperados=len(recs),
                ids=[r.get("id") for r in recs if r.get("id")],
            )
            if recs:
                contexto_rag = _formatar_contexto_rag(fonte_rag, recs)
        for tentativa in range(1, max_t + 1):
            # Revisão > regeneração: se já há um rascunho, mandamos corrigir SÓ o que o
            # verificador apontou em vez de reescrever do zero (não joga trabalho bom fora
            # e converge mais rápido em falhas pequenas/cosméticas).
            if feedback and ultima:
                bloco_feedback = (
                    "\n\nSUA TENTATIVA ANTERIOR (o conteúdo já está bom — NÃO reescreva do zero):\n"
                    f"\"\"\"\n{ultima}\n\"\"\"\n"
                    f"O verificador reprovou por: \"{feedback}\". Corrija APENAS o que foi apontado "
                    "e devolva o texto inteiro corrigido, preservando todo o resto como está."
                )
            elif feedback:
                bloco_feedback = f"\nNa tentativa anterior o verificador reprovou: \"{feedback}\". Corrija."
            else:
                bloco_feedback = ""
            log.evento("executor.chamado", executor=sub["id"], papel=sub["papel"],
                       tier=tier_atual, tentativa=tentativa,
                       modelo=_descricao_modelo(
                           sub["papel"], tier_atual, sub.get("ferramentas"),
                           capacidades=sub.get("capacidades_requeridas"),
                       ),
                       **_template_evento(spec))
            prompt_subagente = contexto_rag + PROMPT_SUBAGENTE.format(
                id=sub["id"], papel=sub["papel"],
                missao_objetivo=missao["objetivo"], missao_contexto=missao["contexto"],
                objetivo=sub["objetivo"], entradas=json.dumps(sub["entradas"], ensure_ascii=False),
                resultado_esperado=sub["resultado_esperado"],
                deps_txt=deps_txt, rubrica_txt=rubrica_txt,
                feedback=bloco_feedback,
            )
            try:
                resultado_executor = chamar_orcado(
                    payload.get("run_id"), payload.get("thread_id"),
                    spec["restricoes"]["teto_custo"], sub["papel"], "executor",
                    sub["id"], prompt_subagente, tentativa,
                    RequisitosTentativaCusteada(
                        tier=tier_atual,
                        ferramentas=sub.get("ferramentas"),
                        capacidades=capacidades_tupla,
                    ),
                    int(payload.get("ciclo_reconciliacao", 0)),
                )
            except Exception as erro:
                # O modelo continua recebendo texto genérico -- devolver a
                # exceção crua para dentro do prompt é entregar detalhe interno
                # a quem só precisa saber que falhou.
                #
                # O LOG, não. Até 2026-07-29 o `except` descartava a exceção e
                # gravava a mesma frase fixa, então "snapshot FX vencido",
                # "credencial ausente" e "upstream fora do ar" eram
                # indistinguíveis para quem operava. Diagnóstico e prompt têm
                # públicos diferentes.
                feedback = "falha externa do executor"
                log.evento(
                    "executor.erro",
                    executor=sub["id"],
                    motivo=f"{feedback}: {type(erro).__name__}: {erro}"[:400],
                    tentativa=tentativa,
                )
                continue
            match resultado_executor:
                case RespostaTentativaCusteada():
                    resposta_executor = resultado_executor
                    ultima = resposta_executor.texto
                case ChamadaOrcadaSemResposta():
                    feedback = "modelo não respondeu"
                    log.evento(
                        "executor.erro", executor=sub["id"],
                        motivo=feedback, tentativa=tentativa,
                    )
                    continue
                case ChamadaOrcadaBloqueada(motivo=motivo):
                    feedback = "falha externa do executor"
                    log.evento(
                        "executor.erro", executor=sub["id"],
                        motivo=motivo[:400], tentativa=tentativa,
                    )
                    continue
                case ChamadaOrcadaTerminal(motivo=motivo, status_reserva=status_reserva):
                    feedback = "falha externa do executor"
                    log.evento(
                        "executor.erro", executor=sub["id"],
                        motivo=f"{motivo[:360]} ({status_reserva})",
                        tentativa=tentativa,
                    )
                    continue
                case _:
                    assert_never(resultado_executor)
            log.evento("executor.respondeu", executor=sub["id"], tentativa=tentativa)
            try:
                resultado_verifier_orcado = chamar_orcado(
                    payload.get("run_id"), payload.get("thread_id"),
                    spec["restricoes"]["teto_custo"], "verifier", "verifier",
                    sub["id"],
                    PROMPT_VERIFIER.format(
                        id=sub["id"],
                        objetivo=sub["objetivo"],
                        rubrica="\n".join(f"- {c}" for c in sub["rubrica"]),
                        saida=ultima,
                    ),
                    tentativa,
                    RequisitosTentativaCusteada(
                        evitar_provedor=(
                            resposta_executor.provider_id
                        ),
                    ),
                    int(payload.get("ciclo_reconciliacao", 0)),
                )
                resposta_verifier_orcada = resposta_orcada_ou_none(
                    resultado_verifier_orcado,
                )
                resposta_verifier = (
                    resposta_verifier_orcada.texto
                    if resposta_verifier_orcada else None
                )
            except Exception:
                feedback = "falha externa do verifier"
                log.evento(
                    "executor.erro",
                    executor=sub["id"],
                    motivo=feedback,
                    tentativa=tentativa,
                )
                continue
            bruto_veredito = extrai_json(resposta_verifier or "")
            try:
                veredito = _VereditoVerifier.model_validate(bruto_veredito)
            except ValidationError:
                veredito = _VereditoVerifier(aprovado=False, motivo="verifier sem veredito valido")
            if veredito.aprovado:
                log.evento("portao.aprovado", portao=f"verifier:{sub['id']}", ciclo=tentativa)
                resultado = {"id": sub["id"], "saida": ultima,
                             "tentativas": tentativa, "aprovado": True}
                if sub.get("produz_artefatos"):
                    # `produz_artefatos` e `list[dict[str, Any]]` e vem da spec, que o
                    # planner (LLM) gera: a validacao nao garante nem que `nome` exista
                    # nem que seja um componente de path. Sem guarda, um dict sem `nome`
                    # (KeyError) ou um nome com separador (OSError) derrubava o run
                    # inteiro, sem evento e sem resultado. Falha de artefato e falha
                    # DESTE subagente — reprovacao, nao queda do motor.
                    try:
                        artefato = sub["produz_artefatos"][0]
                        nome = f"{sub['id']}__{artefato['nome']}"
                        ref = registrar_artefato(payload["workspace"], nome, artefato["tipo"], ultima)
                        ref["nome"] = artefato["nome"]
                    except (KeyError, TypeError, OSError, ValueError) as ex:
                        motivo = f"artefato invalido: {type(ex).__name__}: {ex}"
                        log.evento("portao.reprovado", portao=f"artefato:{sub['id']}",
                                   ciclo=tentativa, motivo=motivo)
                        return {"resultados": [{"id": sub["id"], "saida": ultima,
                                                "tentativas": tentativa, "aprovado": False,
                                                "motivo": motivo}]}
                    log.evento(
                        "artefato.atualizou",
                        nome=ref["nome"],
                        tipo=ref["tipo"],
                        subagente=sub["id"],
                        caminho=ref["caminho"],
                    )
                    resultado["artefatos"] = [ref]
                return {"resultados": [resultado]}
            feedback = veredito.motivo
            log.evento("portao.reprovado", portao=f"verifier:{sub['id']}", ciclo=tentativa, motivo=feedback)
            if escalar_em_retry:
                novo = _proximo_tier(tier_atual)
                if novo != tier_atual:
                    log.evento("executor.escalado", executor=sub["id"],
                               de=tier_atual, para=novo, tentativa=tentativa)
                tier_atual = novo
        return {"resultados": [{"id": sub["id"], "saida": ultima or "",
                                "tentativas": max_t, "aprovado": False, "motivo": feedback}]}

    def executar_comando_seguro(
        comando_tpl: str,
        valores: dict[str, Any],
        timeout_s: Any,
        *,
        cwd: Path,
    ) -> dict[str, Any]:
        if (
            not isinstance(timeout_s, int)
            or isinstance(timeout_s, bool)
            or not MIN_TIMEOUT_S <= timeout_s <= MAX_TIMEOUT_S
        ):
            return {
                "ok": False,
                "erro": "timeout",
                "motivo": (
                    f"timeout inválido: esperado inteiro entre {MIN_TIMEOUT_S} e {MAX_TIMEOUT_S}"
                ),
                "saida": "",
            }
        try:
            partes_tpl = shlex.split(comando_tpl)
        except ValueError as ex:
            return {"ok": False, "erro": "comando_invalido", "motivo": f"comando inválido: {ex}", "saida": ""}
        valores_fmt = {chave: str(valor) for chave, valor in valores.items()}
        try:
            partes = [parte.format_map(valores_fmt) for parte in partes_tpl]
        except (KeyError, ValueError) as ex:
            detalhe = ex.args[0] if isinstance(ex, KeyError) else "formato invalido"
            return {"ok": False, "erro": "placeholder", "motivo": f"placeholder invalido: {detalhe}", "saida": ""}
        if not partes:
            return {"ok": False, "erro": "executavel_ausente", "motivo": "executável ausente: ", "saida": ""}
        if partes_tpl[0] != partes[0]:
            return {
                "ok": False,
                "erro": "executavel_nao_permitido",
                "motivo": "placeholder não pode selecionar executável",
                "saida": "",
            }
        fim_opcoes = False
        for parte_tpl, parte in zip(partes_tpl[1:], partes[1:]):
            if parte_tpl == "--":
                fim_opcoes = True
                continue
            if not fim_opcoes and parte.startswith("-") and not parte_tpl.startswith("-"):
                return {
                    "ok": False,
                    "erro": "argumento_nao_permitido",
                    "motivo": "placeholder não pode selecionar opção de comando",
                    "saida": "",
                }
        candidato = Path(partes[0])
        if not candidato.is_absolute() or not executaveis_permitidos:
            return {
                "ok": False,
                "erro": "executavel_nao_permitido",
                "motivo": f"executável não permitido: {partes[0]}",
                "saida": "",
            }
        if namespace_proprio:
            # Sem `resolve`/`access`: o caminho vive na imagem, nao aqui. A
            # comparacao e literal contra a allowlist selada, o que continua
            # sendo fail-closed -- so muda qual sistema de arquivos manda.
            identidade = candidato
        else:
            try:
                identidade = candidato.resolve(strict=True)
            except OSError:
                return {
                    "ok": False,
                    "erro": "executavel_ausente",
                    "motivo": f"executável ausente: {partes[0]}",
                    "saida": "",
                }
        if identidade not in executaveis_permitidos or (
            not namespace_proprio
            and (not identidade.is_file() or not os.access(identidade, os.X_OK))
        ):
            return {
                "ok": False,
                "erro": "executavel_nao_permitido",
                "motivo": f"executável não permitido: {partes[0]}",
                "saida": "",
            }
        partes[0] = str(identidade)
        # O `CommandRunner` e um adapter externo e o protocolo nao e validado em
        # runtime. Um backend que levanta — sandbox pifado, `ValueError: embedded
        # null byte` de um `\x00` que veio na spec — nao pode atravessar a fronteira
        # e derrubar o motor: a fronteira e justamente o lugar onde falha de
        # execucao vira reprovacao com motivo.
        try:
            proc = command_runner.run(CommandRequest(
                argv=tuple(partes),
                workspace=cwd,
                timeout_s=timeout_s,
            ))
        except Exception as ex:
            return {
                "ok": False,
                "erro": "runner_falhou",
                "motivo": f"runner de comando falhou: {type(ex).__name__}: {ex}",
                "saida": "",
            }
        saida = "\n".join(p for p in [proc.stdout.strip(), proc.stderr.strip()] if p)
        if proc.erro is not None:
            return {"ok": False, "erro": proc.erro, "motivo": proc.motivo, "saida": saida}
        return {"ok": True, "proc": proc, "saida": saida, "partes": partes}

    def executar_ferramenta(sub: dict[str, Any], workspace: Path) -> dict:
        nome_ferramenta = str(sub.get("ferramenta") or "")
        ferramenta = ferramentas.get(nome_ferramenta)
        if ferramenta is None:
            motivo = f"ferramenta '{nome_ferramenta}' não registrada"
            log.evento("ferramenta.indisponivel", ferramenta=nome_ferramenta, motivo=motivo)
            return {"resultados": [{"id": sub["id"], "saida": "", "tentativas": 1,
                                    "aprovado": False, "motivo": motivo}]}

        comando_tpl = str(ferramenta.get("comando") or "")
        produz = ferramenta.get("produz") or []
        if not isinstance(produz, list):
            produz = []
        workspace.mkdir(parents=True, exist_ok=True)
        valores = dict(sub.get("entradas", {}))
        saidas_por_placeholder: dict[str, dict[str, str]] = {}
        for item in produz:
            if not isinstance(item, dict):
                continue
            nome = str(item.get("nome") or "").strip()
            tipo = str(item.get("tipo") or "").strip()
            placeholder = str(item.get("de_placeholder") or "").strip()
            if nome and placeholder:
                caminho_saida = workspace / f"{sub['id']}__{nome}"
                valores[placeholder] = str(caminho_saida)
                saidas_por_placeholder[placeholder] = {"nome": nome, "tipo": tipo, "caminho": str(caminho_saida)}
        timeout_s = ferramenta.get("timeout", 300)
        execucao = executar_comando_seguro(comando_tpl, valores, timeout_s, cwd=workspace)
        if not execucao["ok"]:
            motivo = str(execucao["motivo"])
            if execucao.get("erro") == "timeout":
                motivo = "timeout ao executar ferramenta"
                log.evento("ferramenta.executada", ferramenta=nome_ferramenta,
                           subagente=sub["id"], aprovado=False)
            else:
                log.evento("ferramenta.indisponivel", ferramenta=nome_ferramenta, motivo=motivo)
            return {"resultados": [{"id": sub["id"], "saida": "", "tentativas": 1,
                                    "aprovado": False, "motivo": motivo}]}

        proc = execucao["proc"]
        saida = str(execucao["saida"])
        modo = ferramenta.get("interpreta_saida")
        metricas: dict[str, Any] = {}
        motivo_json = ""
        if modo == "exit_code":
            aprovado = proc.returncode == 0
        elif modo == "json":
            try:
                dados = json.loads(proc.stdout)
                saida_json = _SaidaFerramentaJSON.model_validate(dados)
                aprovado = saida_json.aprovado
                metricas = saida_json.metricas
                motivo_json = saida_json.motivo
            except json.JSONDecodeError:
                aprovado = False
                motivo_json = "saída inválida: JSON malformado"
                log.evento("ferramenta.saida_invalida", ferramenta=nome_ferramenta,
                           subagente=sub["id"], motivo=motivo_json)
            except ValidationError:
                aprovado = False
                detalhe = "json sem 'aprovado'" if isinstance(dados, dict) and "aprovado" not in dados else "contrato de ferramenta"
                motivo_json = f"saída inválida: {detalhe}"
                log.evento("ferramenta.saida_invalida", ferramenta=nome_ferramenta,
                           subagente=sub["id"], motivo=motivo_json)
        else:
            aprovado = False
        motivo = "" if aprovado else (motivo_json or saida or f"exit_code={proc.returncode}")
        artefatos = []
        if aprovado:
            for ref in saidas_por_placeholder.values():
                caminho = Path(ref["caminho"])
                if not caminho.exists():
                    aprovado = False
                    motivo = f"artefato não produzido: {ref['nome']}"
                    break
                artefato = referenciar_artefato(caminho, ref["nome"], ref["tipo"])
                artefatos.append(artefato)
                log.evento(
                    "artefato.atualizou",
                    nome=artefato["nome"],
                    tipo=artefato["tipo"],
                    subagente=sub["id"],
                    caminho=artefato["caminho"],
                )
        dados_evento = {"ferramenta": nome_ferramenta, "subagente": sub["id"], "aprovado": aprovado}
        if metricas:
            dados_evento["metricas"] = metricas
        log.evento("ferramenta.executada", **dados_evento)
        resultado = {"id": sub["id"], "saida": saida, "tentativas": 1,
                     "aprovado": aprovado}
        if motivo:
            resultado["motivo"] = motivo
        if metricas:
            resultado["metricas"] = metricas
        if artefatos:
            resultado["artefatos"] = artefatos
        return {"resultados": [resultado]}

    def executar_validador(sub: dict[str, Any], deps: dict[str, str], workspace: Path) -> dict:
        alvo = str(sub.get("valida") or "")
        spec_validador = sub.get("validador") or {}
        kind = str(spec_validador.get("kind") or "")
        config = spec_validador.get("config") or {}
        if not isinstance(config, dict):
            config = {}
        saida_alvo = deps.get(alvo)
        if saida_alvo is None:
            aprovado = False
            motivo = f"saída do alvo '{alvo}' indisponível"
            evidencia: dict[str, Any] = {"erro": "alvo indisponível"}
        elif kind == "schema_json":
            aprovado, motivo, evidencia = _validar_schema_json(saida_alvo, config)
        elif kind == "contem":
            aprovado, motivo, evidencia = _validar_contem(saida_alvo, config)
        elif kind == "comando":
            workspace.mkdir(parents=True, exist_ok=True)
            timeout_s = config.get("timeout", 30)
            comando_tpl = str(config.get("comando") or "")
            execucao = executar_comando_seguro(comando_tpl, sub.get("entradas", {}), timeout_s, cwd=workspace)
            if execucao["ok"]:
                proc = execucao["proc"]
                saida_cmd = str(execucao["saida"])
                aprovado = proc.returncode == 0
                motivo = "" if aprovado else (saida_cmd or f"exit_code={proc.returncode}")
                evidencia = {"exit_code": proc.returncode, "saida": saida_cmd}
            else:
                aprovado = False
                motivo = str(execucao["motivo"])
                evidencia = {"erro": execucao.get("erro"), "saida": execucao.get("saida", "")}
        else:
            aprovado = False
            motivo = f"validador kind inválido: {kind}"
            evidencia = {"erro": "kind inválido"}
        log.evento("validador.rodou", id=sub["id"], alvo=alvo, kind=kind,
                   aprovado=aprovado, motivo=motivo)
        saida = json.dumps(
            {"id": sub["id"], "alvo": alvo, "kind": kind, "aprovado": aprovado,
             "motivo": motivo, "evidencia": evidencia},
            ensure_ascii=False,
        )
        resultado = {"id": sub["id"], "saida": saida, "tentativas": 1,
                     "aprovado": aprovado, "motivo": motivo, "alvo": alvo}
        if not aprovado and alvo:
            resultado["refazer"] = alvo
        return {"resultados": [resultado]}

    def resultado_bloqueado(
        sid: str,
        dependencias: list[str],
        concluidos: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        reprovadas = [
            dep for dep in dependencias if concluidos[dep].get("aprovado") is not True
        ]
        if not reprovadas:
            return None
        motivo = f"dependencias reprovadas: {', '.join(reprovadas)}"
        log.evento("portao.reprovado", portao=f"dependencias:{sid}", motivo=motivo)
        return {
            "id": sid,
            "saida": "",
            "tentativas": 0,
            "aprovado": False,
            "motivo": motivo,
        }

    def executar_grafo_dep(state: EstadoMotor) -> dict:
        spec = state["spec"]
        subs = {s["id"]: s for s in spec["subagentes"]}
        workspace = workspace_de(state)
        concluidos: dict[str, dict[str, Any]] = {}
        resultados: list[dict[str, Any]] = []
        restantes = set(subs)
        log.evento("grafo_dep.iniciado", subagentes=list(subs))
        while restantes:
            onda = sorted(
                sid for sid in restantes
                if set(subs[sid].get("depende_de", [])) <= set(concluidos)
            )
            if not onda:
                log.evento("grafo_dep.travado", restantes=sorted(restantes))
                break
            log.evento("onda.iniciada", ids=onda)
            for sid in onda:
                dependencias = list(subs[sid].get("depende_de", []))
                for dep in dependencias:
                    log.evento("aresta.fluxo", de=dep, para=sid)
                resultado = resultado_bloqueado(sid, dependencias, concluidos)
                if resultado is None:
                    sub = {
                        **subs[sid],
                        "entradas": resolver_refs_artefato(
                            subs[sid].get("entradas", {}), concluidos
                        ),
                    }
                    deps = {d: texto_dependencia(concluidos[d]) for d in dependencias}
                    retorno = subagente(
                        {
                            "sub": sub, "spec": spec, "deps": deps, "workspace": workspace,
                            "run_id": state.get("run_id"), "thread_id": state.get("thread_id"),
                        }
                    )
                    resultado = retorno["resultados"][0]
                concluidos[sid] = resultado
                resultados.append(resultado)
                restantes.discard(sid)
            log.evento("onda.concluida", ids=onda)
        return {"resultados": resultados}

    def texto_dependencia(resultado: dict[str, Any]) -> str:
        texto = str(resultado.get("saida", ""))
        if resultado.get("metricas"):
            texto += "\nMétricas: " + json.dumps(resultado["metricas"], ensure_ascii=False)
        return texto

    def resolver_refs_artefato(valor: Any, concluidos: dict[str, dict[str, Any]]) -> Any:
        if isinstance(valor, dict):
            ref = valor.get("ref_artefato")
            if isinstance(ref, dict):
                origem = str(ref.get("de") or "")
                nome = str(ref.get("nome") or "")
                artefatos = concluidos.get(origem, {}).get("artefatos", [])
                for artefato in artefatos:
                    if artefato.get("nome") == nome:
                        return artefato["caminho"]
                raise RuntimeError(f"artefato '{nome}' de '{origem}' não encontrado em runtime")
            return {chave: resolver_refs_artefato(item, concluidos) for chave, item in valor.items()}
        if isinstance(valor, list):
            return [resolver_refs_artefato(item, concluidos) for item in valor]
        return valor

    def avaliar_cobertura(
        state: EstadoMotor, resultados: list[dict[str, Any]], ordinal: int,
        evitar_provedor: str | None = None,
    ) -> dict[str, Any]:
        spec = state["spec"]
        reprovados = [r["id"] for r in resultados if not r["aprovado"]]
        refazer_reprovados = [
            str(r.get("refazer") or r["id"])
            for r in resultados
            if not r["aprovado"]
        ]
        log.evento("executor.chamado", executor="global_evaluator",
                   modelo=_descricao_modelo("evaluator"),
                   **_template_evento(spec))
        resultado_chamada = chamar_orcado(
            state.get("run_id"), state.get("thread_id"), spec["restricoes"]["teto_custo"],
            "evaluator", "evaluator", "global_evaluator",
            PROMPT_EVALUATOR.format(
                missao_objetivo=spec["missao"]["objetivo"],
                criterios="\n".join(f"- {c}" for c in spec["missao"]["criterios_cobertura"]),
                resultados=json.dumps(resultados, ensure_ascii=False),
            ),
            ordinal,
            RequisitosTentativaCusteada(evitar_provedor=evitar_provedor),
        )
        resposta = resposta_orcada_ou_none(resultado_chamada)
        if resposta is None:
            raise ErroOrcamento("evaluator orcado indisponivel")
        bruto_veredito = extrai_json(resposta.texto)
        try:
            tipado = _VereditoEvaluator.model_validate(bruto_veredito)
        except ValidationError:
            tipado = _VereditoEvaluator(aprovado=False, lacunas=["evaluator sem veredito valido"])
        veredito = tipado.model_dump()
        if reprovados:
            # `{**veredito, ...}` e nao um dict novo: reconstruir do zero descartava
            # `nos_a_refazer`, e a leitura logo abaixo pegava o dict mutilado. Com A→B→C
            # e C reprovado, a atribuicao a montante do evaluator ("a causa e A") sumia e
            # a reconciliacao refazia so o sintoma C — queimando uma rodada do teto para
            # corrigir o no errado.
            veredito = {**veredito, "aprovado": False,
                        "lacunas": list(veredito.get("lacunas", [])) + [f"subagente reprovado: {i}" for i in reprovados]}
        nomes = veredito.get("nos_a_refazer", [])
        if not isinstance(nomes, list):
            nomes = []
        nos = list(dict.fromkeys([str(n) for n in nomes] + refazer_reprovados))
        # `julgado_por` fica no veredito para a escalada poder EXCLUIR quem já
        # julgou. Sem isso, escalar chamaria o mesmo provedor de novo — que é
        # pedir a mesma opinião mais alto, não uma segunda opinião.
        veredito = {**veredito, "nos_a_refazer": nos, "julgado_por": resposta.provider_id}
        return veredito

    def escalar_cobertura(
        state: EstadoMotor, veredito: dict[str, Any], escaladas: int,
    ) -> dict[str, Any] | None:
        """Sobe o portão reprovado para um juiz INDEPENDENTE fazer o papel do fundador.

        Independente de verdade: exclui o provedor que acabou de julgar. Chamar o
        mesmo provedor de novo é pedir a mesma opinião mais alto — e um segundo
        veredito correlacionado com o primeiro dá aparência de revisão sem ser
        revisão.

        Devolve o novo veredito, ou None quando não há juiz independente
        disponível ou o teto de escaladas se esgotou. None significa DEGRADAR
        PARA HUMANO, nunca liberar: o modo automático pode chamar o fundador,
        mas não pode enganá-lo.
        """
        if escaladas >= max_escaladas:
            log.evento("escalada.esgotada", portao="cobertura", escaladas=escaladas)
            return None
        anterior = str(veredito.get("julgado_por") or "") or None
        log.evento("gate.escalado", portao="cobertura",
                   evitando=anterior or "", tentativa=escaladas + 1)
        try:
            novo = avaliar_cobertura(
                state, state["resultados"],
                state.get("rodada_reconciliacao", 0) + 1,
                evitar_provedor=anterior,
            )
        except ErroOrcamento:
            # Sem juiz independente disponível (papel com uma alternativa só, cota
            # esgotada) o portão NÃO relaxa. Falta de segunda opinião não é
            # aprovação.
            log.evento("escalada.indisponivel", portao="cobertura")
            return None
        return novo

    def decidir_cobertura(veredito: dict[str, Any], permitir_preencher: bool) -> Any:
        auto = _decisao_texto(politica.decisao_auto("cobertura", default="escalar"))
        if auto not in {None, "escalar", "prosseguir", "preencher", "abortar"}:
            auto = None
        if auto == "preencher" and not permitir_preencher:
            auto = "prosseguir"
        if auto is not None:  # auto-mode (ou override): resolve sozinho, sem pausar
            log.evento("gate.auto", portao="cobertura", decisao=auto)
            return auto

        log.evento("escalado", para="fundador")
        opcoes = "prosseguir · preencher · abortar" if permitir_preencher else "prosseguir · abortar"
        pergunta = ("Cobertura insuficiente. Prosseguir com síntese parcial, preencher lacunas ou abortar?"
                    if permitir_preencher else
                    "Cobertura insuficiente. Prosseguir com síntese parcial ou abortar?")
        decisao = interrupt({  # pausa durável: o checkpointer segura até Command(resume=...)
            "portao": "cobertura",
            "pergunta": pergunta,
            "lacunas": veredito.get("lacunas", []),
            "opcoes": opcoes,
        })
        log.evento("decisao.fundador", portao="cobertura", decisao=str(decisao))
        return decisao

    def preencher_lacunas(state: EstadoMotor, spec: dict[str, Any], resultados: list[dict[str, Any]],
                          workspace: Path,
                          veredito: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        por_id = {s["id"]: s for s in spec["subagentes"]}
        alvo = [
            sid for sid in dict.fromkeys(str(s) for s in veredito.get("nos_a_refazer", []))
            if sid in por_id
        ]
        if not alvo:
            return resultados, []

        alvo_set = set(alvo)
        closure_set = set(alvo)
        mudou = True
        while mudou:
            mudou = False
            for sid, sub in por_id.items():
                if sid not in closure_set and any(dep in closure_set for dep in sub.get("depende_de", [])):
                    closure_set.add(sid)
                    mudou = True

        restantes = set(closure_set)
        concluidos = {r["id"]: r for r in resultados if r["id"] not in closure_set}
        por_id_resultado = {r["id"]: r for r in resultados}
        lacunas = [str(lac) for lac in veredito.get("lacunas", [])]
        novos: list[dict[str, Any]] = []
        ordem_recomputada: list[str] = []
        log.evento("reconciliacao.iniciada", nos=sorted(closure_set))
        while restantes:
            onda = sorted(
                sid for sid in restantes
                if set(por_id[sid].get("depende_de", [])) <= set(concluidos)
            )
            if not onda:
                log.evento("grafo_dep.travado", restantes=sorted(restantes))
                break
            for sid in onda:
                dependencias = list(por_id[sid].get("depende_de", []))
                resultado = resultado_bloqueado(sid, dependencias, concluidos)
                if resultado is None:
                    sub = {
                        **por_id[sid],
                        "entradas": resolver_refs_artefato(
                            por_id[sid].get("entradas", {}), concluidos
                        ),
                    }
                    deps = {d: texto_dependencia(concluidos[d]) for d in dependencias}
                    feedback_lacunas = [lac for lac in lacunas if sid in lac] or lacunas[:]
                    if sid not in alvo_set:
                        feedback_lacunas.append(
                            "uma dependência foi revista; realinhe-se a ela"
                        )
                    feedback = "; ".join(feedback_lacunas)
                    retorno = subagente({
                        "sub": sub,
                        "spec": spec,
                        "deps": deps,
                        "feedback": feedback,
                        "rascunho_anterior": por_id_resultado.get(sid, {}).get("saida"),
                        "workspace": workspace,
                        "run_id": state.get("run_id"),
                        "thread_id": state.get("thread_id"),
                        "ciclo_reconciliacao": state.get("rodada_reconciliacao", 0) + 1,
                    })
                    resultado = retorno["resultados"][0]
                    log.evento("lacuna.preenchida", subagente=sid)
                concluidos[sid] = resultado
                novos.append(resultado)
                ordem_recomputada.append(sid)
                restantes.discard(sid)
        log.evento("reconciliacao.concluida", nos=ordem_recomputada)
        return mesclar_resultados(resultados, novos), novos

    def finalizar_cobertura(veredito: dict[str, Any], decisao: Any) -> dict[str, Any]:
        if _decisao_texto(decisao) == "prosseguir":
            return {**veredito, "prosseguir_parcial": True}
        log.evento("tarefa.abortada", motivo="decisão do fundador inválida ou abortar")
        return {**veredito, "abortada": True}

    def avaliar(state: EstadoMotor) -> dict:
        resultados = state["resultados"]
        rodada = state.get("rodada_reconciliacao", 0)
        if rodada == 0:
            log.evento("paralelo.concluido", commitados=len(resultados))
        try:
            veredito = avaliar_cobertura(state, resultados, rodada + 1)
        except ErroOrcamento:
            log.evento(
                "executor.erro", executor="global_evaluator",
                motivo="orcamento indisponivel", tentativa=rodada + 1,
            )
            log.evento("tarefa.abortada", motivo="evaluator orcado indisponivel")
            return {"avaliacao": {
                "aprovado": False, "abortada": True,
                "lacunas": ["evaluator orcado indisponivel"], "nos_a_refazer": [],
            }}
        if veredito["aprovado"]:
            log.evento("portao.aprovado", portao="cobertura")
        return {"avaliacao": veredito, "preenchimento_vazio": False}

    def rota_pos_avaliacao(state: EstadoMotor):
        if state["avaliacao"].get("abortada"):
            return END
        return "sintetizar" if state["avaliacao"].get("aprovado") else "decidir_cobertura"

    def decidir_cobertura_node(state: EstadoMotor) -> dict[str, Any]:
        veredito = state["avaliacao"]
        rodada = state.get("rodada_reconciliacao", 0)
        log.evento("portao.reprovado", portao="cobertura", lacunas=veredito.get("lacunas", []))
        limite_esgotado = rodada >= max_rodadas_reconciliacao
        permitir = not limite_esgotado and not state.get("preenchimento_vazio", False)
        if limite_esgotado:
            log.evento("reconciliacao.esgotada", rodadas=rodada)
        decisao = decidir_cobertura(veredito, permitir_preencher=permitir)
        texto = _decisao_texto(decisao) or "abortar"

        escaladas = state.get("escaladas_cobertura", 0)
        if texto == "escalar":
            novo = escalar_cobertura(state, veredito, escaladas)
            if novo is not None:
                escaladas += 1
                if novo.get("aprovado"):
                    # Juiz independente aprovou: o portão passa de verdade, sem
                    # `prosseguir_parcial` -- e portanto sem carimbo. Foi provado,
                    # nao liberado.
                    log.evento("portao.aprovado", portao="cobertura")
                    return {"decisao_cobertura": "", "escaladas_cobertura": escaladas,
                            "avaliacao": novo}
                # Reprovou de novo. Se ainda da para reconciliar, reconcilia; foi
                # o que o fundador faria.
                if permitir and novo.get("nos_a_refazer"):
                    return {"decisao_cobertura": "preencher",
                            "escaladas_cobertura": escaladas, "avaliacao": novo}
                veredito = novo
            # Sem juiz independente, teto estourado, ou reprovado sem o que
            # refazer: DEGRADA PARA HUMANO. Automatico pode chamar o fundador;
            # nao pode liberar em silencio.
            log.evento("escalado", para="fundador")
            decisao = interrupt({
                "portao": "cobertura",
                "pergunta": ("Cobertura reprovada e a escalada automática não resolveu. "
                             "Prosseguir com síntese parcial ou abortar?"),
                "lacunas": veredito.get("lacunas", []),
                "opcoes": "prosseguir · abortar",
            })
            log.evento("decisao.fundador", portao="cobertura", decisao=str(decisao))
            texto = _decisao_texto(decisao) or "abortar"
            return {
                "decisao_cobertura": texto,
                "escaladas_cobertura": escaladas,
                "avaliacao": finalizar_cobertura(veredito, decisao),
            }

        if permitir and texto == "preencher":
            return {"decisao_cobertura": texto}
        return {
            "decisao_cobertura": texto,
            "avaliacao": finalizar_cobertura(veredito, decisao),
        }

    def rota_pos_decisao(state: EstadoMotor):
        if state.get("decisao_cobertura") == "preencher":
            return "preencher_lacunas"
        return END if state["avaliacao"].get("abortada") else "sintetizar"

    def preencher_lacunas_node(state: EstadoMotor) -> dict[str, Any]:
        _resultados, novos = preencher_lacunas(
            state, state["spec"], state["resultados"], workspace_de(state), state["avaliacao"],
        )
        if not novos:
            return {"preenchimento_vazio": True, "decisao_cobertura": ""}
        return {
            "resultados": novos,
            "rodada_reconciliacao": state.get("rodada_reconciliacao", 0) + 1,
            "preenchimento_vazio": False,
            "decisao_cobertura": "",
        }

    def rota_pos_preenchimento(state: EstadoMotor):
        return "decidir_cobertura" if state.get("preenchimento_vazio") else "avaliar"

    def sintetizar(state: EstadoMotor) -> dict:
        spec = state["spec"]
        log.evento("executor.chamado", executor="synthesizer",
                   modelo=_descricao_modelo("synthesizer"),
                   **_template_evento(spec))
        try:
            resultado_chamada = chamar_orcado(
                state.get("run_id"), state.get("thread_id"), spec["restricoes"]["teto_custo"],
                "synthesizer", "synthesizer", "synthesizer",
                PROMPT_SYNTHESIZER.format(
                    missao_objetivo=spec["missao"]["objetivo"],
                    instrucao=spec["sintese"]["instrucao"], formato=spec["sintese"]["formato"],
                    resultados=json.dumps(
                        [r for r in state["resultados"] if r["aprovado"]], ensure_ascii=False,
                    ),
                    reprovados=(
                        BLOCO_REPROVADOS.format(itens="\n".join(
                            f"- {item['id']}: {item['motivo'][:400]}"
                            for item in reprovados_de(state)
                        )) if reprovados_de(state) else ""
                    ),
                ),
                1,
            )
            resposta_orcada = resposta_orcada_ou_none(resultado_chamada)
        except ErroOrcamento:
            resposta_orcada = None
        if resposta_orcada is None:
            log.evento(
                "executor.erro", executor="synthesizer",
                motivo="orcamento indisponivel", tentativa=1,
            )
            log.evento("tarefa.abortada", motivo="synthesizer orcado indisponivel")
            return {"avaliacao": {
                **state.get("avaliacao", {}), "aprovado": False, "abortada": True,
                "motivo": "synthesizer orcado indisponivel",
            }}
        # Evidência primeiro, reprovação por cima: o veredito mais grave tem que
        # ficar na primeira linha, e o rodapé de cobertura embaixo do texto.
        resposta = carimbar_evidencia(resposta_orcada.texto, state)
        resposta = carimbar_reprovacao(resposta, state)
        cobertura = cobertura_de_evidencia(spec, state.get("resultados") or [])
        log.evento("evidencia.cobertura", missao=spec["missao"]["id"],
                   execucao=cobertura["execucao"], artefatos=cobertura["total"])
        reprovados = reprovados_de(state)
        if reprovados or (state.get("avaliacao") or {}).get("prosseguir_parcial"):
            # Evento próprio: "tarefa.concluida" sozinho fazia run reprovado ser
            # indistinguível de run aprovado para quem lê o log de fora.
            log.evento("tarefa.reprovada", missao=spec["missao"]["id"],
                       reprovados=[item["id"] for item in reprovados])
        log.evento("tarefa.concluida", missao=spec["missao"]["id"])
        return {"resposta_final": resposta}

    g = StateGraph(EstadoMotor)
    g.add_node("planner", planner)
    g.add_node("revisar_plano", revisar_plano)
    g.add_node("subagente", subagente)  # type: ignore[arg-type]
    g.add_node("executar_grafo_dep", executar_grafo_dep)
    g.add_node("avaliar", avaliar)
    g.add_node("decidir_cobertura", decidir_cobertura_node)
    g.add_node("preencher_lacunas", preencher_lacunas_node)
    g.add_node("sintetizar", sintetizar)
    g.add_edge(START, "planner")
    g.add_edge("planner", "revisar_plano")
    g.add_conditional_edges("revisar_plano", rota_pos_plano, ["subagente", "executar_grafo_dep", END])
    g.add_edge("subagente", "avaliar")
    g.add_edge("executar_grafo_dep", "avaliar")
    g.add_conditional_edges("avaliar", rota_pos_avaliacao, ["decidir_cobertura", "sintetizar", END])
    g.add_conditional_edges(
        "decidir_cobertura", rota_pos_decisao, ["preencher_lacunas", "sintetizar", END],
    )
    g.add_conditional_edges(
        "preencher_lacunas", rota_pos_preenchimento, ["decidir_cobertura", "avaliar"],
    )
    g.add_edge("sintetizar", END)
    return g.compile(checkpointer=checkpointer)
