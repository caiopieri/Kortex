"""Grafo fixo que interpreta uma WorkflowSpec dinâmica — padrão fan_out_sintese.

Topologia (espelha a referência dynamic-workflow-harness, ver memória do projeto):

    START → planner → revisar_plano → [fan-out: subagente × N] → avaliar → sintetizar → END
                          (attempt → verifier → commit, retry ≤ max_tentativas)
                                              (cobertura reprovada → interrupt() ao fundador)

Regras de fronteira (anti-lock-in):
- nós são funções puras que só falam com `cliente.chamar(papel, prompt)`;
- estado serializável; a spec é dado, não código;
- todo passo emite evento JSONL próprio (painel/auditoria), além do checkpointer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional, TypedDict, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .eventos import LogEventos
from .modelos import ClienteModelo, extrai_json
from .politica import PoliticaGates
from .rag import carregar_dataset, recuperar
from .runner import (
    MAX_TIMEOUT_S,
    MIN_TIMEOUT_S,
    CommandRequest,
    CommandRunner,
    DenyCommandRunner,
)
from .spec import WorkflowSpec

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
    resultados: Annotated[list[dict[str, Any]], mesclar_resultados]
    avaliacao: dict[str, Any]
    resposta_final: str


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

Produza a resposta final da missão."""


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


def _validar_schema_minimo(dados: Any, schema: dict[str, Any], caminho: str = "$") -> str | None:
    tipo = schema.get("type")
    if tipo:
        tipos = tipo if isinstance(tipo, list) else [tipo]

        def confere(tipo_json: str) -> bool:
            if tipo_json == "object":
                return isinstance(dados, dict)
            if tipo_json == "array":
                return isinstance(dados, list)
            if tipo_json == "string":
                return isinstance(dados, str)
            if tipo_json == "integer":
                return isinstance(dados, int) and not isinstance(dados, bool)
            if tipo_json == "number":
                return isinstance(dados, (int, float)) and not isinstance(dados, bool)
            if tipo_json == "boolean":
                return isinstance(dados, bool)
            if tipo_json == "null":
                return dados is None
            return False

        if not any(isinstance(t, str) and confere(t) for t in tipos):
            return f"{caminho}: esperado {tipo}"
    if isinstance(dados, dict):
        required = schema.get("required") or []
        for campo in required:
            if campo not in dados:
                return f"{caminho}: campo obrigatório ausente '{campo}'"
        propriedades = schema.get("properties") or {}
        if isinstance(propriedades, dict):
            for campo, sub_schema in propriedades.items():
                if campo in dados and isinstance(sub_schema, dict):
                    erro = _validar_schema_minimo(dados[campo], sub_schema, f"{caminho}.{campo}")
                    if erro:
                        return erro
        if schema.get("additionalProperties") is False:
            extras = set(dados) - set(propriedades)
            if extras:
                return f"{caminho}: campos extras {sorted(extras)}"
    if isinstance(dados, list) and isinstance(schema.get("items"), dict):
        for indice, item in enumerate(dados):
            erro = _validar_schema_minimo(item, schema["items"], f"{caminho}[{indice}]")
            if erro:
                return erro
    return None


def _validar_schema_json(saida: str, config: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    schema = config.get("schema")
    if not isinstance(schema, dict):
        return False, "config.schema ausente ou inválido", {"erro": "schema inválido"}
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as ex:
        return False, f"JSON inválido: {ex.msg}", {"erro": ex.msg}
    if validar_jsonschema is not None:
        try:
            validar_jsonschema(instance=dados, schema=schema)
        except Exception as ex:
            if JsonSchemaValidationError is not None and isinstance(ex, JsonSchemaValidationError):
                caminho = ".".join(str(p) for p in ex.path)
                local = f" em {caminho}" if caminho else ""
                return False, f"schema_json falhou{local}: {ex.message}", {"erro": ex.message}
            return False, f"schema_json falhou: {ex}", {"erro": str(ex)}
    else:
        erro = _validar_schema_minimo(dados, schema)
        if erro:
            return False, f"schema_json falhou: {erro}", {"erro": erro}
    return True, "schema_json aprovado", {"json": dados}


def _validar_contem(saida: str, config: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    requer = config.get("requer")
    if not isinstance(requer, list) or not all(isinstance(item, str) for item in requer):
        return False, "config.requer ausente ou inválido", {"faltantes": []}
    minimo_bruto = config.get("min", len(requer))
    try:
        minimo = int(minimo_bruto)
    except (TypeError, ValueError):
        return False, "config.min inválido", {"faltantes": requer}
    minimo = max(0, min(minimo, len(requer)))
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


def _escolher_rota(cliente: ClienteModelo, missao: str,
                   rotas: dict[str, dict[str, Any]], log: LogEventos) -> str | None:
    catalogo = [
        {"nome": nome, "quando": rota.get("quando", "")}
        for nome, rota in rotas.items()
    ]
    try:
        resposta = cliente.chamar("planner", PROMPT_SELETOR_ROTA.format(
            missao=missao,
            catalogo=json.dumps(catalogo, ensure_ascii=False),
        ))
    except Exception:
        resposta = None
    bruto = extrai_json(resposta or "")
    nome = str(bruto.get("rota") or "").strip() if isinstance(bruto, dict) else ""
    fallback = nome not in rotas
    if fallback:
        nome = "pesquisa-sintese" if "pesquisa-sintese" in rotas else ""
    rota_ativa = rotas.get(nome) or ROTA_DEFAULT
    log.evento(
        "rota.escolhida",
        rota=nome or "pesquisa-sintese",
        padrao=rota_ativa["padrao"],
        fallback=fallback,
    )
    return nome or None


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
                    perfil_execucao: str = "certificado",
                    ferramentas_permitidas: list[str] | None = None,
                    command_runner: CommandRunner | None = None):
    """Compila o grafo. `cliente` e `log` são injetados — o grafo não conhece backends.
    `politica` decide quais gates pausam (manual) ou resolvem sozinhos (auto-mode);
    ausente = tudo manual (comportamento default).
    `max_rodadas_reconciliacao` limita quantas rodadas de preenchimento de cobertura
    podem rodar antes de seguir parcial."""
    politica = politica or PoliticaGates()
    workspace_base = Path(workspace_base)
    ferramentas = ferramentas or {}
    command_runner = command_runner if command_runner is not None else DenyCommandRunner()
    perfil_execucao = "rascunho" if perfil_execucao == "rascunho" else "certificado"
    executaveis_permitidos: set[Path] = set()
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

    def planner(state: EstadoMotor) -> dict:
        run_id = run_id_de(state)
        log.evento("run.perfil", perfil=perfil_execucao)
        if state.get("spec"):  # spec fornecida pelo usuário: valida e segue (missão dirigida por dado)
            spec = WorkflowSpec.model_validate(state["spec"])
            log.evento("spec.recebida", missao=spec.missao.id, subagentes=len(spec.subagentes))
            return {"spec": spec.model_dump(), "run_id": run_id}
        rota_ativa = rota
        if rota_ativa is None and rotas:
            nome_rota = _escolher_rota(cliente, state["missao_texto"], rotas, log)
            rota_ativa = rotas.get(nome_rota) if nome_rota is not None else ROTA_DEFAULT
            rota_ativa = rota_ativa or ROTA_DEFAULT
        erro = ""
        for tentativa in (1, 2, 3):
            log.evento("executor.chamado", executor="planner", tentativa=tentativa,
                       modelo=_descricao_modelo("planner"))
            resp = cliente.chamar("planner", montar_prompt_planner(
                missao=state["missao_texto"],
                schema=json.dumps(WorkflowSpec.model_json_schema(), ensure_ascii=False),
                max_sub=10, erro=erro, rota=rota_ativa))
            bruto = extrai_json(resp or "")
            if bruto is not None:
                try:
                    spec = WorkflowSpec.model_validate(bruto)
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
        return [Send("subagente", {"sub": s, "spec": spec, "workspace": workspace}) for s in spec["subagentes"]]

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

        # Guard de independência: o verifier deve evitar o provedor DO executor desta
        # tarefa (cross-model anti-auto-aprovação). Só quando o cliente sabe rotear.
        prov_exec = (cliente.provedor_de(sub["papel"], sub.get("tier"), sub.get("ferramentas"),
                                         capacidades=sub.get("capacidades_requeridas"))
                     if hasattr(cliente, "provedor_de") else None)
        kw_verifier = {"evitar": prov_exec} if prov_exec else {}
        tier_atual = sub.get("tier")
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
                ultima = cliente.chamar(
                    sub["papel"],
                    prompt_subagente,
                    ferramentas=sub.get("ferramentas"),
                    tier=tier_atual,
                    capacidades=sub.get("capacidades_requeridas"),
                )
            except Exception:
                feedback = "falha externa do executor"
                log.evento(
                    "executor.erro",
                    executor=sub["id"],
                    motivo=feedback,
                    tentativa=tentativa,
                )
                continue
            if not ultima:
                feedback = "modelo não respondeu"
                log.evento("executor.erro", executor=sub["id"], motivo=feedback, tentativa=tentativa)
                continue
            log.evento("executor.respondeu", executor=sub["id"], tentativa=tentativa)
            try:
                resposta_verifier = cliente.chamar(
                    "verifier",
                    PROMPT_VERIFIER.format(
                        id=sub["id"],
                        objetivo=sub["objetivo"],
                        rubrica="\n".join(f"- {c}" for c in sub["rubrica"]),
                        saida=ultima,
                    ),
                    **kw_verifier,
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
                    artefato = sub["produz_artefatos"][0]
                    nome = f"{sub['id']}__{artefato['nome']}"
                    ref = registrar_artefato(payload["workspace"], nome, artefato["tipo"], ultima)
                    ref["nome"] = artefato["nome"]
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
        try:
            identidade = candidato.resolve(strict=True)
        except OSError:
            return {
                "ok": False,
                "erro": "executavel_ausente",
                "motivo": f"executável ausente: {partes[0]}",
                "saida": "",
            }
        if (
            identidade not in executaveis_permitidos
            or not identidade.is_file()
            or not os.access(identidade, os.X_OK)
        ):
            return {
                "ok": False,
                "erro": "executavel_nao_permitido",
                "motivo": f"executável não permitido: {partes[0]}",
                "saida": "",
            }
        partes[0] = str(identidade)
        proc = command_runner.run(CommandRequest(
            argv=tuple(partes),
            workspace=cwd,
            timeout_s=timeout_s,
        ))
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
                        {"sub": sub, "spec": spec, "deps": deps, "workspace": workspace}
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

    def avaliar_cobertura(spec: dict[str, Any], resultados: list[dict[str, Any]]) -> dict[str, Any]:
        reprovados = [r["id"] for r in resultados if not r["aprovado"]]
        refazer_reprovados = [
            str(r.get("refazer") or r["id"])
            for r in resultados
            if not r["aprovado"]
        ]
        log.evento("executor.chamado", executor="global_evaluator",
                   modelo=_descricao_modelo("evaluator"),
                   **_template_evento(spec))
        bruto_veredito = extrai_json(cliente.chamar("evaluator", PROMPT_EVALUATOR.format(
            missao_objetivo=spec["missao"]["objetivo"],
            criterios="\n".join(f"- {c}" for c in spec["missao"]["criterios_cobertura"]),
            resultados=json.dumps(resultados, ensure_ascii=False),
        )) or "")
        try:
            tipado = _VereditoEvaluator.model_validate(bruto_veredito)
        except ValidationError:
            tipado = _VereditoEvaluator(aprovado=False, lacunas=["evaluator sem veredito valido"])
        veredito = tipado.model_dump()
        if reprovados:
            veredito = {"aprovado": False,
                        "lacunas": list(veredito.get("lacunas", [])) + [f"subagente reprovado: {i}" for i in reprovados]}
        nomes = veredito.get("nos_a_refazer", [])
        if not isinstance(nomes, list):
            nomes = []
        nos = list(dict.fromkeys([str(n) for n in nomes] + refazer_reprovados))
        veredito = {**veredito, "nos_a_refazer": nos}
        return veredito

    def decidir_cobertura(veredito: dict[str, Any], permitir_preencher: bool) -> Any:
        auto = _decisao_texto(politica.decisao_auto("cobertura", default="prosseguir"))
        if auto not in {None, "prosseguir", "preencher", "abortar"}:
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

    def preencher_lacunas(spec: dict[str, Any], resultados: list[dict[str, Any]],
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
        spec, resultados = state["spec"], state["resultados"]
        log.evento("paralelo.concluido", commitados=len(resultados))
        veredito = avaliar_cobertura(spec, resultados)
        acumulados: list[dict[str, Any]] = []
        rodada = 0

        while veredito["aprovado"] is False:
            log.evento("portao.reprovado", portao="cobertura", lacunas=veredito.get("lacunas", []))
            permitir = rodada < max_rodadas_reconciliacao
            if not permitir:
                log.evento("reconciliacao.esgotada", rodadas=rodada)
            decisao = decidir_cobertura(veredito, permitir_preencher=permitir)
            if not (permitir and _decisao_texto(decisao) == "preencher"):
                base = {"resultados": acumulados} if acumulados else {}
                return {**base, "avaliacao": finalizar_cobertura(veredito, decisao)}

            resultados, novos = preencher_lacunas(spec, resultados, workspace_de(state), veredito)
            if not novos:
                decisao = decidir_cobertura(veredito, permitir_preencher=False)
                base = {"resultados": acumulados} if acumulados else {}
                return {**base, "avaliacao": finalizar_cobertura(veredito, decisao)}

            acumulados = mesclar_resultados(acumulados, novos)
            rodada += 1
            veredito = avaliar_cobertura(spec, resultados)

        log.evento("portao.aprovado", portao="cobertura")
        if acumulados:
            return {"resultados": acumulados, "avaliacao": veredito}
        return {"avaliacao": veredito}

    def rota_pos_avaliacao(state: EstadoMotor):
        return END if state["avaliacao"].get("abortada") else "sintetizar"

    def sintetizar(state: EstadoMotor) -> dict:
        spec = state["spec"]
        log.evento("executor.chamado", executor="synthesizer",
                   modelo=_descricao_modelo("synthesizer"),
                   **_template_evento(spec))
        resposta = cliente.chamar("synthesizer", PROMPT_SYNTHESIZER.format(
            missao_objetivo=spec["missao"]["objetivo"],
            instrucao=spec["sintese"]["instrucao"], formato=spec["sintese"]["formato"],
            resultados=json.dumps([r for r in state["resultados"] if r["aprovado"]], ensure_ascii=False),
        )) or "(synthesizer não respondeu)"
        log.evento("tarefa.concluida", missao=spec["missao"]["id"])
        return {"resposta_final": resposta}

    g = StateGraph(EstadoMotor)
    g.add_node("planner", planner)
    g.add_node("revisar_plano", revisar_plano)
    g.add_node("subagente", subagente)  # type: ignore[arg-type]
    g.add_node("executar_grafo_dep", executar_grafo_dep)
    g.add_node("avaliar", avaliar)
    g.add_node("sintetizar", sintetizar)
    g.add_edge(START, "planner")
    g.add_edge("planner", "revisar_plano")
    g.add_conditional_edges("revisar_plano", rota_pos_plano, ["subagente", "executar_grafo_dep", END])
    g.add_edge("subagente", "avaliar")
    g.add_edge("executar_grafo_dep", "avaliar")
    g.add_conditional_edges("avaliar", rota_pos_avaliacao, ["sintetizar", END])
    g.add_edge("sintetizar", END)
    return g.compile(checkpointer=checkpointer)
