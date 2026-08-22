"""A síntese não pode citar arquivo que não existe no workspace da run.

Issue #18. A síntese é o ÚNICO texto que um humano lê no fim de uma missão, e
ela entregava instruções que não rodam: `pytest -q testes.py` e
`from ebay import buscar`, enquanto em disco havia `testador__testes.py` e
`codificador__ebay.py`. Quem seguisse ao pé da letra recebia
`ModuleNotFoundError` — no ponto exato onde ninguém tem contexto para corrigir.

O prefixo de subagente está CERTO e a spec depende dele. O defeito era o
sintetizador receber o `nome` declarado em `produz_artefatos` como se fosse o
nome do arquivo.

ESTE TESTE CONFERE CONTRA O DISCO, não contra strings esperadas.

A diferença importa: um teste que afirmasse `arquivo == "autor__saida.txt"`
passaria a mentir junto no dia em que o esquema de prefixo mudasse — ele estaria
verificando a regra que gera o nome, não o fato de o arquivo existir. Aqui a
síntese é varrida atrás de coisas que parecem nome de arquivo, e cada uma é
procurada no workspace real da run. Mude o prefixo para `-`, para nada, ou mude
o layout de diretório: o teste continua fazendo a pergunta certa.

O sintetizador do stub é deliberadamente OBEDIENTE — ele lê o prompt e cita o
artefato que o prompt lhe apresenta. É o modelo bem-comportado, e é o caso que
importa: se um modelo que segue instrução à risca produz uma instrução quebrada,
o defeito é do prompt, não do modelo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover - compatibilidade de versão
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from tests.helpers_grafo import construir_grafo_teste as construir_grafo

# Qualquer token que pareça um arquivo de artefato dentro do texto da síntese.
# Só extensões que a fábrica de fato produz — varrer `.md` ou `.txt` genérico
# pegaria prosa ("veja o README.md") e o teste viraria ruído.
CITACAO = re.compile(r"[\w./-]+\.(?:py|json|jsonl|csv|stl|html|css|js)\b")


def _spec(produz: list[dict]) -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "issue18",
            "objetivo": "Produzir artefato e explicar como usar",
            "contexto": "",
            "criterios_cobertura": ["subagente aprovado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": [{
            "id": "codificador",
            "papel": "executor",
            "objetivo": "Gerar modulo",
            "entradas": {},
            "resultado_esperado": "codigo",
            "rubrica": ["tem codigo"],
            "produz_artefatos": produz,
        }],
        "gates": [],
        "sintese": {"instrucao": "Explique como usar", "formato": "markdown"},
    }


def _rodar(tmp_path: Path, spec: dict) -> tuple[str, Path]:
    """Roda a missão e devolve (texto da síntese, workspace da run)."""
    capturado: dict[str, str] = {}

    def roteador(papel: str, prompt: str) -> str:
        if papel == "executor":
            return "print('ok')"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            capturado["prompt"] = prompt
            # O modelo OBEDIENTE: cita o artefato pelo campo que o prompt
            # apresenta como nome de arquivo. Com a correção da #18 existe
            # `arquivo`; sem ela sobra só `nome`, que é o nome declarado na spec
            # e não existe em disco.
            #
            # A extração é por campo e não por `json.loads` do prompt inteiro:
            # um `[.*]` guloso atravessa o prompt de ponta a ponta e captura
            # colchete de outra seção. Foi o que aconteceu na primeira versão
            # deste stub, e o sintoma foi o teste "falhando certo pelo motivo
            # errado" — acusando a #18 quando a #18 já estava corrigida.
            achado = re.search(r'"arquivo":\s*"([^"]+)"', prompt)
            if achado is None:
                achado = re.search(r'"nome":\s*"([^"]+)"', prompt)
            citado = achado.group(1)
            return f"Para usar:\n\n```bash\npytest -q {citado}\n```\n"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    workspace_base = tmp_path / "runs"
    grafo = construir_grafo(
        ClienteStub(roteador), log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        workspace_base=workspace_base,
    )
    estado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "issue18"}})
    workspaces = list(workspace_base.glob("*/artefatos"))
    assert workspaces, "a run não criou workspace de artefatos"
    return estado.get("resposta_final") or "", workspaces[0]


def _arquivos_citados(texto: str) -> set[str]:
    return {Path(m).name for m in CITACAO.findall(texto)}


def test_todo_arquivo_citado_na_sintese_existe_em_disco(tmp_path):
    """O negativo da #18, contra o disco.

    Reverter `artefatos_como_o_disco` derruba este teste: a síntese passaria a
    citar `saida.py` e o disco tem `codificador__saida.py`.
    """
    sintese, workspace = _rodar(tmp_path, _spec([{"nome": "saida.py", "tipo": "python"}]))

    em_disco = {p.name for p in workspace.iterdir() if p.is_file()}
    citados = _arquivos_citados(sintese)

    assert citados, (
        "a síntese não citou arquivo nenhum — o teste não verificou nada. "
        f"Texto: {sintese[:200]!r}"
    )
    fantasmas = sorted(citados - em_disco)
    assert not fantasmas, (
        "a síntese manda usar arquivo que NÃO existe no workspace da run: "
        + ", ".join(fantasmas)
        + f"\nem disco: {sorted(em_disco)}"
        + "\nQuem seguir a síntese ao pé da letra recebe ModuleNotFoundError."
    )


def test_o_prefixo_do_subagente_continua_no_disco(tmp_path):
    """A guarda do outro lado: o teste acima não pode ser satisfeito removendo o
    prefixo, que é comportamento correto de que a spec depende."""
    _sintese, workspace = _rodar(tmp_path, _spec([{"nome": "saida.py", "tipo": "python"}]))

    nomes = {p.name for p in workspace.iterdir() if p.is_file()}
    assert "codificador__saida.py" in nomes, (
        f"o prefixo de subagente sumiu do disco: {sorted(nomes)}. "
        "A síntese e o disco precisam concordar SUBINDO a síntese, não baixando o disco."
    )


def test_a_sintese_nao_recebe_caminho_absoluto(tmp_path):
    """Caminho absoluto aponta para o checkout onde a run rodou.

    Num texto que alguém lê noutra máquina, é ruído na melhor hipótese e
    instrução errada na pior — a mesma razão pela qual a identidade de artefato
    é relativa (issue #22).
    """
    capturado: dict[str, str] = {}

    def roteador(papel: str, prompt: str) -> str:
        if papel == "executor":
            return "print('ok')"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            capturado["prompt"] = prompt
            return "pronto"
        raise AssertionError(papel)

    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador), log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        workspace_base=tmp_path / "runs",
    )
    grafo.invoke(
        {"spec": _spec([{"nome": "saida.py", "tipo": "python"}])},
        {"configurable": {"thread_id": "issue18-abs"}},
    )

    prompt = capturado["prompt"]
    assert "artefatos/codificador__saida.py" in prompt, "o caminho relativo não chegou"
    assert str(tmp_path) not in prompt, (
        "o caminho ABSOLUTO do workspace vazou para o prompt da síntese"
    )


def test_o_nome_declarado_continua_disponivel_e_rotulado(tmp_path):
    """O nome da spec não é apagado — é RENOMEADO para o que ele é.

    Some-lo seria a outra forma de não declarar: o sintetizador perderia a
    ligação entre o que a missão pediu e o que a run produziu.
    """
    capturado: dict[str, str] = {}

    def roteador(papel: str, prompt: str) -> str:
        if papel == "executor":
            return "print('ok')"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            capturado["prompt"] = prompt
            return "pronto"
        raise AssertionError(papel)

    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador), log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        workspace_base=tmp_path / "runs",
    )
    grafo.invoke(
        {"spec": _spec([{"nome": "saida.py", "tipo": "python"}])},
        {"configurable": {"thread_id": "issue18-decl"}},
    )

    prompt = capturado["prompt"]
    assert '"nome_declarado_na_spec": "saida.py"' in prompt
    assert '"arquivo": "codificador__saida.py"' in prompt


def test_o_nome_e_derivado_da_escrita_e_nao_recriado_por_regra():
    """A guarda do critério: sobreviver a uma mudança no esquema de prefixo.

    Os testes acima passariam com uma implementação que RECONSTRUÍSSE o nome por
    regra (`f"{sub_id}__{nome}"`), porque hoje a regra e o disco concordam. Ela
    passaria hoje e mentiria no dia em que o prefixo mudasse — que é exatamente o
    modo de falha que a issue #18 é.

    Aqui o `caminho` deliberadamente NÃO segue a regra atual: o arquivo em disco
    se chama `xx-saida.py`, não `codificador__saida.py`. Uma implementação que
    lê `Path(caminho).name` acerta; uma que remonta `id + "__" + nome` erra.

    Descobri a lacuna porque uma mutação minha caiu pelo motivo errado — ela
    quebrou por sintaxe, não por reconstrução — e conferir *por que* uma mutação
    falha é o que separa provar de achar que provou.
    """
    from motor.grafo import artefatos_como_o_disco

    resultados = [{
        "id": "codificador",
        "aprovado": True,
        "artefatos": [{
            "nome": "saida.py",
            "caminho": "/w/run-1/artefatos/xx-saida.py",
            "tipo": "python",
            "hash": "abc",
        }],
    }]

    ref = artefatos_como_o_disco(resultados, "/w/run-1")[0]["artefatos"][0]

    assert ref["arquivo"] == "xx-saida.py", (
        "o nome do arquivo foi RECONSTRUÍDO por regra em vez de lido do caminho "
        f"que a escrita devolveu: {ref['arquivo']!r}"
    )
    assert ref["caminho"] == "artefatos/xx-saida.py"
    assert ref["nome_declarado_na_spec"] == "saida.py"
