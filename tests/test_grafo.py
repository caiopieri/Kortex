"""Ponta a ponta com ClienteStub — valida a topologia, o retry do verifier,
o gate do fundador (interrupt/resume) e a missão dirigida por spec serializada."""
import json
from pathlib import Path

from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub

SPEC = json.loads(
    (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text(encoding="utf-8")
)


def faz_roteador(reprovar_beta_uma_vez=False, evaluator_aprova=True):
    """Stub determinístico por papel; identifica o subagente pelo conteúdo do prompt."""
    estado = {"beta_reprovado": False}

    def roteador(papel: str, prompt: str):
        if papel == "planner":
            return json.dumps(SPEC, ensure_ascii=False)
        if papel == "pesquisador":
            return "RESULTADO alfa" if "pesquisa-alfa" in prompt else "RESULTADO beta"
        if papel == "verifier":
            if reprovar_beta_uma_vez and "pesquisa-beta" in prompt and not estado["beta_reprovado"]:
                estado["beta_reprovado"] = True
                return json.dumps({"aprovado": False, "motivo": "faltou evidência"})
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            if evaluator_aprova:
                return json.dumps({"aprovado": True, "lacunas": []})
            return json.dumps({"aprovado": False, "lacunas": ["canal beta sem evidência"]})
        if papel == "synthesizer":
            return "SÍNTESE FINAL DA MISSÃO"
        raise AssertionError(f"papel inesperado: {papel}")

    return roteador


def roda(tmp_path, roteador, entrada):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    return grafo, config, log, grafo.invoke(entrada, config)


def eventos_de(tmp_path):
    linhas = (tmp_path / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(l) for l in linhas]


def test_missao_dirigida_por_spec_serializada(tmp_path):
    """Critério de falsificação nº1: a missão roda inteira dirigida por uma spec
    serializada, sem código novo por missão."""
    _, _, _, resultado = roda(tmp_path, faz_roteador(), {"spec": SPEC})
    assert resultado["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    assert {r["id"] for r in resultado["resultados"]} == {"pesquisa-alfa", "pesquisa-beta"}
    assert all(r["aprovado"] for r in resultado["resultados"])
    tipos = [e["evento"] for e in eventos_de(tmp_path)]
    assert "spec.recebida" in tipos and "paralelo.iniciado" in tipos and "tarefa.concluida" in tipos


def test_planner_cria_spec_a_partir_de_missao_texto(tmp_path):
    _, _, _, resultado = roda(tmp_path, faz_roteador(), {"missao_texto": "pesquise oportunidades de receita"})
    assert resultado["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    assert "spec.criada" in [e["evento"] for e in eventos_de(tmp_path)]


def test_retry_do_verifier(tmp_path):
    """Verifier reprova a 1ª tentativa do beta → retry corrige → aprovado na 2ª."""
    _, _, _, resultado = roda(tmp_path, faz_roteador(reprovar_beta_uma_vez=True), {"spec": SPEC})
    beta = next(r for r in resultado["resultados"] if r["id"] == "pesquisa-beta")
    assert beta["aprovado"] and beta["tentativas"] == 2
    eventos = eventos_de(tmp_path)
    reprovacoes = [e for e in eventos if e["evento"] == "portao.reprovado" and e["portao"] == "verifier:pesquisa-beta"]
    assert len(reprovacoes) == 1 and reprovacoes[0]["motivo"] == "faltou evidência"


def test_gate_fundador_prosseguir(tmp_path):
    """Evaluator reprova cobertura → interrupt pausa → resume 'prosseguir' → síntese parcial."""
    grafo, config, _, resultado = roda(tmp_path, faz_roteador(evaluator_aprova=False), {"spec": SPEC})
    assert "__interrupt__" in resultado  # pausado no gate, sem resposta final
    assert resultado["__interrupt__"][0].value["portao"] == "cobertura"
    retomado = grafo.invoke(Command(resume="prosseguir"), config)
    assert retomado["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    assert retomado["avaliacao"]["prosseguir_parcial"] is True
    tipos = [e["evento"] for e in eventos_de(tmp_path)]
    assert "escalado" in tipos and "decisao.fundador" in tipos


def test_gate_fundador_abortar(tmp_path):
    grafo, config, _, resultado = roda(tmp_path, faz_roteador(evaluator_aprova=False), {"spec": SPEC})
    assert "__interrupt__" in resultado
    retomado = grafo.invoke(Command(resume="abortar"), config)
    assert "resposta_final" not in retomado
    assert retomado["avaliacao"]["abortada"] is True
    assert "tarefa.abortada" in [e["evento"] for e in eventos_de(tmp_path)]


def test_gate_auto_mode_nao_interrompe(tmp_path):
    """Auto-mode (Corte C): cobertura reprova mas NÃO pausa — resolve 'prosseguir' e
    completa a missão sozinho. Sem 'escalado', com 'gate.auto'."""
    from motor.politica import PoliticaGates
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(ClienteStub(faz_roteador(evaluator_aprova=False)), log,
                            checkpointer=InMemorySaver(), politica=PoliticaGates(auto_mode=True))
    res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "auto"}})
    assert "__interrupt__" not in res
    assert res["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    assert res["avaliacao"]["prosseguir_parcial"] is True
    tipos = [e["evento"] for e in eventos_de(tmp_path)]
    assert "gate.auto" in tipos and "escalado" not in tipos


def test_gate_override_manual_interrompe_mesmo_com_auto(tmp_path):
    """Exceção por gate: auto-mode ligado, mas 'cobertura' cravado manual → ainda pausa."""
    from motor.politica import PoliticaGates
    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(auto_mode=True, overrides={"cobertura": "manual"})
    grafo = construir_grafo(ClienteStub(faz_roteador(evaluator_aprova=False)), log,
                            checkpointer=InMemorySaver(), politica=pol)
    res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "ovr"}})
    assert "__interrupt__" in res  # override forçou manual apesar do auto_mode
    assert "gate.auto" not in [e["evento"] for e in eventos_de(tmp_path)]


def test_gate_auto_abortar_por_override(tmp_path):
    """Override pode automatizar pra ABORTAR também (não só prosseguir)."""
    from motor.politica import PoliticaGates
    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"cobertura": "abortar"})
    grafo = construir_grafo(ClienteStub(faz_roteador(evaluator_aprova=False)), log,
                            checkpointer=InMemorySaver(), politica=pol)
    res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "abrt"}})
    assert "__interrupt__" not in res and res["avaliacao"]["abortada"] is True


def test_subagente_esgotado_vira_lacuna(tmp_path):
    """Verifier sempre reprova alfa → 3 tentativas → commit reprovado → evaluator
    recebe a lacuna mesmo que o modelo aprove (regra dura no código, não no prompt)."""

    def roteador(papel, prompt):
        base = faz_roteador()
        if papel == "verifier" and "pesquisa-alfa" in prompt:
            return json.dumps({"aprovado": False, "motivo": "insuficiente"})
        return base(papel, prompt)

    grafo, config, _, resultado = roda(tmp_path, roteador, {"spec": SPEC})
    assert "__interrupt__" in resultado  # reprovado força gate, apesar do evaluator stub aprovar
    lacunas = resultado["__interrupt__"][0].value["lacunas"]
    assert any("pesquisa-alfa" in l for l in lacunas)
