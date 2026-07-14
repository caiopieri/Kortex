"""Ponta a ponta com ClienteStub — valida a topologia, o retry do verifier,
o gate do fundador (interrupt/resume) e a missão dirigida por spec serializada."""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from motor import __main__ as cli
from motor.grafo import PROMPT_SUBAGENTE, _proximo_tier, construir_grafo
from motor.modelos import ClienteRoteador, ClienteStub
from motor.orcamento import (
    CotacaoTentativa,
    RequisitosTentativaCusteada,
    RepositorioOrcamento,
    ResultadoTentativa,
    RotaTentativaCusteada,
)
from motor.politica import PoliticaGates

SPEC = json.loads(
    (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text(encoding="utf-8")
)
for _sub in SPEC["subagentes"]:
    _sub.setdefault("capacidades_requeridas", ["pesquisa"])


def spec_dependencias():
    sub_base = {
        "tipo": "modelo",
        "papel": "executor",
        "objetivo": "produzir parte coerente",
        "entradas": {},
        "resultado_esperado": "texto",
        "rubrica": ["entrega texto"],
        "tier": "simples",
        "capacidades_requeridas": ["redacao"],
    }
    return {
        "versao": "0.1",
        "padrao": "grafo_dependencias",
        "missao": {
            "id": "dep",
            "objetivo": "validar recomputação em cadeia",
            "contexto": "",
            "criterios_cobertura": ["resultados consistentes"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 3, "max_tentativas": 1},
        "subagentes": [
            {**sub_base, "id": "A"},
            {**sub_base, "id": "B", "depende_de": ["A"]},
            {**sub_base, "id": "C", "depende_de": ["B"]},
        ],
        "gates": [],
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }


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
    class Tentativa:
        def cotar_tentativa(self):
            return CotacaoTentativa(Decimal("0.01"), "BRL", "teste-v1")

        def tentar_uma_vez(self):
            return ResultadoTentativa(roteador("planner", prompt), Decimal("0"), "BRL", "teste-uso")

    def fabrica(_papel, prompt_recebido, _tentativa, _requisitos):
        nonlocal prompt
        prompt = prompt_recebido
        return [RotaTentativaCusteada("stub", "stub-provider", Tentativa())]

    prompt = ""
    grafo = construir_grafo(
        ClienteStub(roteador), log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        repositorio_orcamento=RepositorioOrcamento(tmp_path / "orcamento"),
        fabrica_tentativas_orcadas=fabrica,
    )
    entrada = {"run_id": "run-teste", "thread_id": "t1", **entrada}
    config = {"configurable": {"thread_id": "t1"}}
    return grafo, config, log, grafo.invoke(entrada, config)


def _orcamento_cliente(tmp_path, cliente):
    class Tentativa:
        def __init__(self, papel, prompt, requisitos):
            self.papel, self.prompt, self.requisitos = papel, prompt, requisitos

        def cotar_tentativa(self):
            return CotacaoTentativa(Decimal("0.01"), "BRL", "teste-v1")

        def tentar_uma_vez(self):
            texto = cliente.chamar(
                self.papel, self.prompt,
                ferramentas=self.requisitos.ferramentas,
                tier=self.requisitos.tier,
                evitar=self.requisitos.evitar_provedor,
                capacidades=(
                    list(self.requisitos.capacidades)
                    if self.requisitos.capacidades is not None else None
                ),
            )
            return ResultadoTentativa(texto, Decimal("0"), "BRL", "teste-uso")

    def fabrica(papel, prompt, _tentativa, requisitos):
        assert isinstance(requisitos, RequisitosTentativaCusteada)
        return [RotaTentativaCusteada(
            f"teste:{papel}", f"teste-provider:{papel}",
            Tentativa(papel, prompt, requisitos),
        )]

    return {
        "repositorio_orcamento": RepositorioOrcamento(tmp_path / "orcamento"),
        "fabrica_tentativas_orcadas": fabrica,
    }


def eventos_de(tmp_path):
    linhas = (tmp_path / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(linha) for linha in linhas]


def spec_rag(fonte_rag=None):
    sub = {
        "id": "rust",
        "tipo": "modelo",
        "papel": "executor",
        "objetivo": "corrigir erro de ownership com move e borrow",
        "entradas": {"codigo": "let s = String::from(\"x\"); let t = s; println!(\"{}\", s);"},
        "resultado_esperado": "explicação e código Rust corrigido",
        "rubrica": ["aborda ownership", "inclui correção"],
        "tier": "simples",
        "capacidades_requeridas": ["codigo"],
    }
    if fonte_rag is not None:
        sub["fonte_rag"] = str(fonte_rag)
        sub["rag_k"] = 2
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "rag-rust",
            "objetivo": "Validar RAG em tarefa Rust",
            "contexto": "",
            "criterios_cobertura": ["subagente aprovado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 1, "max_tentativas": 1},
        "subagentes": [sub],
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def _cliente_prompts_rag():
    def roteador(papel, prompt):
        if papel == "executor":
            return "ownership explicado"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    return ClienteStub(roteador)


def test_rag_injeta_contexto_recuperado_e_emite_evento(tmp_path):
    dataset = tmp_path / "rust.jsonl"
    dataset.write_text(
        "\n".join([
            json.dumps({"id": "erro-move", "origem": "rust-book", "conteudo": "move de String impede uso posterior; use borrow por referência"}),
            json.dumps({"id": "result", "conteudo": "Result e operador ? propagam erros"}),
            json.dumps({"id": "irrelevante", "conteudo": "trait bounds e generics"}),
        ]),
        encoding="utf-8",
    )
    cliente = _cliente_prompts_rag()
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente,
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
    )

    resultado = grafo.invoke({"spec": spec_rag(dataset)}, {"configurable": {"thread_id": "rag"}})

    assert resultado["resposta_final"] == "FINAL"
    prompt = next(p for papel, p in cliente.chamadas if papel == "executor")
    assert "CONTEXTO RECUPERADO" in prompt
    assert "erro-move" in prompt
    assert "move de String impede uso posterior" in prompt
    assert "irrelevante" not in prompt
    evento = next(e for e in eventos_de(tmp_path) if e["evento"] == "rag.consultado")
    assert evento["subagente"] == "rust"
    assert evento["fonte"] == str(dataset)
    assert evento["k"] == 2
    assert evento["recuperados"] == 1
    assert evento["ids"] == ["erro-move"]


def test_sem_fonte_rag_prompt_permanece_sem_bloco_e_sem_evento(tmp_path):
    cliente = _cliente_prompts_rag()
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente,
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
    )
    spec = spec_rag()

    grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "sem-rag"}})

    prompt = next(p for papel, p in cliente.chamadas if papel == "executor")
    sub = spec["subagentes"][0]
    esperado = PROMPT_SUBAGENTE.format(
        id=sub["id"],
        papel=sub["papel"],
        missao_objetivo=spec["missao"]["objetivo"],
        missao_contexto=spec["missao"]["contexto"],
        objetivo=sub["objetivo"],
        entradas=json.dumps(sub["entradas"], ensure_ascii=False),
        resultado_esperado=sub["resultado_esperado"],
        deps_txt="",
        rubrica_txt="\n".join(f"- {c}" for c in sub["rubrica"]),
        feedback="",
    )
    assert prompt == esperado
    assert not any(e["evento"] == "rag.consultado" for e in eventos_de(tmp_path))


def test_fonte_rag_inexistente_nao_quebra_e_nao_injeta_bloco(tmp_path):
    cliente = _cliente_prompts_rag()
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente,
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
    )

    resultado = grafo.invoke(
        {"spec": spec_rag(tmp_path / "ausente.jsonl")},
        {"configurable": {"thread_id": "rag-ausente"}},
    )

    assert resultado["resposta_final"] == "FINAL"
    prompt = next(p for papel, p in cliente.chamadas if papel == "executor")
    assert "CONTEXTO RECUPERADO" not in prompt
    evento = next(e for e in eventos_de(tmp_path) if e["evento"] == "rag.consultado")
    assert evento["recuperados"] == 0
    assert evento["ids"] == []


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


def test_run_perfil_emitido_como_certificado_por_default(tmp_path):
    _, _, _, _ = roda(tmp_path, faz_roteador(), {"spec": SPEC})

    eventos = eventos_de(tmp_path)
    perfil = next(e for e in eventos if e["evento"] == "run.perfil")
    assert perfil["perfil"] == "certificado"
    assert [e["evento"] for e in eventos].index("run.perfil") < [e["evento"] for e in eventos].index("spec.recebida")


def test_run_perfil_emitido_como_rascunho_quando_configurado(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(faz_roteador()),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        perfil_execucao="rascunho",
    )

    grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "perfil-rascunho"}})

    perfil = next(e for e in eventos_de(tmp_path) if e["evento"] == "run.perfil")
    assert perfil["perfil"] == "rascunho"


def test_cli_rascunho_propaga_perfil_para_grafo(tmp_path, monkeypatch):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(SPEC), encoding="utf-8")
    capturado = {}

    class LogFake:
        def __init__(self, caminho):
            self.caminho = caminho

        def fechar(self):
            pass

    class GrafoFake:
        def invoke(self, entrada, config):
            return {"resposta_final": "ok"}

    def construir_fake(*args, **kwargs):
        capturado["perfil_execucao"] = kwargs.get("perfil_execucao")
        return GrafoFake()

    monkeypatch.setattr(sys, "argv", ["motor", "--spec", str(spec_path), "--rascunho"])
    monkeypatch.setattr(cli, "LogEventos", LogFake)
    monkeypatch.setattr(cli, "construir_cliente", lambda *args, **kwargs: ClienteStub(faz_roteador()))
    monkeypatch.setattr(cli, "construir_grafo", construir_fake)

    assert cli.main() == 0
    assert capturado["perfil_execucao"] == "rascunho"


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
    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(auto_mode=True, overrides={"cobertura": "manual"})
    grafo = construir_grafo(ClienteStub(faz_roteador(evaluator_aprova=False)), log,
                            checkpointer=InMemorySaver(), politica=pol)
    res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "ovr"}})
    assert "__interrupt__" in res  # override forçou manual apesar do auto_mode
    assert not any(e["evento"] == "gate.auto" and e["portao"] == "cobertura"
                   for e in eventos_de(tmp_path))


def test_gate_auto_abortar_por_override(tmp_path):
    """Override pode automatizar pra ABORTAR também (não só prosseguir)."""
    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "abortar"})
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
    assert any("pesquisa-alfa" in lac for lac in lacunas)


def test_gate_cobertura_preencher_reexecuta_reprovado_uma_vez(tmp_path):
    """Decisão preencher reexecuta só o subagente citado na lacuna, no máximo uma rodada."""

    def roteador(papel, prompt):
        base = faz_roteador()
        if papel == "verifier" and "pesquisa-alfa" in prompt:
            return json.dumps({"aprovado": False, "motivo": "insuficiente"})
        return base(papel, prompt)

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver(), politica=pol)

    resultado = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "preencher"}})

    assert "__interrupt__" not in resultado
    assert resultado["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    eventos = eventos_de(tmp_path)
    assert sum(1 for e in eventos if e["evento"] == "lacuna.preenchida") == 1
    assert any(e["evento"] == "lacuna.preenchida" and e["subagente"] == "pesquisa-alfa"
               for e in eventos)
    chamados_alfa = [e for e in eventos if e["evento"] == "executor.chamado"
                     and e.get("executor") == "pesquisa-alfa"]
    chamados_beta = [e for e in eventos if e["evento"] == "executor.chamado"
                     and e.get("executor") == "pesquisa-beta"]
    assert len(chamados_alfa) == SPEC["restricoes"]["max_tentativas"] * 2
    assert len(chamados_beta) == 1
    assert len([e for e in eventos if e["evento"] == "executor.chamado"
                and e.get("executor") == "global_evaluator"]) == 2


def test_gate_cobertura_preencher_refaz_fonte_e_dependentes_em_ordem(tmp_path):
    spec = spec_dependencias()
    estado = {"evaluator": 0, "execucoes": {"A": 0, "B": 0, "C": 0}}
    prompts: dict[str, list[str]] = {"A": [], "B": [], "C": []}

    def roteador(papel, prompt):
        if papel == "executor":
            sid = next(s for s in ["A", "B", "C"] if f"subagente '{s}'" in prompt)
            estado["execucoes"][sid] += 1
            prompts[sid].append(prompt)
            return f"{sid} v{estado['execucoes'][sid]}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            estado["evaluator"] += 1
            if estado["evaluator"] == 1:
                return json.dumps({
                    "aprovado": False,
                    "lacunas": ["B diverge da arquitetura e C herdou a divergência"],
                    "nos_a_refazer": ["B"],
                })
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver(), politica=pol)

    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "dep-chain"}})

    assert resultado["avaliacao"]["aprovado"] is True
    assert {r["id"]: r["saida"] for r in resultado["resultados"]} == {"A": "A v1", "B": "B v2", "C": "C v2"}
    assert estado["execucoes"] == {"A": 1, "B": 2, "C": 2}
    assert "B v2" in prompts["C"][1]
    eventos = eventos_de(tmp_path)
    assert any(e["evento"] == "reconciliacao.iniciada" and set(e["nos"]) == {"B", "C"} for e in eventos)
    assert [e["subagente"] for e in eventos if e["evento"] == "lacuna.preenchida"] == ["B", "C"]


def test_gate_cobertura_preencher_loop_converge_com_teto_dois(tmp_path):
    spec = spec_dependencias()
    estado = {"evaluator": 0, "execucoes": {"A": 0, "B": 0, "C": 0}}

    def roteador(papel, prompt):
        if papel == "executor":
            sid = next(s for s in ["A", "B", "C"] if f"subagente '{s}'" in prompt)
            estado["execucoes"][sid] += 1
            return f"{sid} v{estado['execucoes'][sid]}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            estado["evaluator"] += 1
            if estado["evaluator"] <= 2:
                return json.dumps({
                    "aprovado": False,
                    "lacunas": [f"B ainda inconsistente rodada {estado['evaluator']}"],
                    "nos_a_refazer": ["B"],
                })
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=pol,
        max_rodadas_reconciliacao=2,
    )

    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "loop-converge"}})

    assert resultado["avaliacao"]["aprovado"] is True
    assert estado["evaluator"] == 3
    assert estado["execucoes"] == {"A": 1, "B": 3, "C": 3}
    eventos = eventos_de(tmp_path)
    assert sum(1 for e in eventos if e["evento"] == "reconciliacao.iniciada") == 2
    assert [e["subagente"] for e in eventos if e["evento"] == "lacuna.preenchida"] == ["B", "C", "B", "C"]
    assert not any(e["evento"] == "reconciliacao.esgotada" for e in eventos)


def test_gate_cobertura_preencher_teto_dois_prossegue_parcial(tmp_path):
    spec = spec_dependencias()
    estado = {"evaluator": 0, "execucoes": {"A": 0, "B": 0, "C": 0}}

    def roteador(papel, prompt):
        if papel == "executor":
            sid = next(s for s in ["A", "B", "C"] if f"subagente '{s}'" in prompt)
            estado["execucoes"][sid] += 1
            return f"{sid} v{estado['execucoes'][sid]}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            estado["evaluator"] += 1
            return json.dumps({
                "aprovado": False,
                "lacunas": [f"B ainda inconsistente rodada {estado['evaluator']}"],
                "nos_a_refazer": ["B"],
            })
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=pol,
        max_rodadas_reconciliacao=2,
    )

    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "loop-teto"}})

    assert resultado["avaliacao"]["aprovado"] is False
    assert resultado["avaliacao"]["prosseguir_parcial"] is True
    assert resultado["resposta_final"] == "FINAL"
    assert estado["evaluator"] == 3
    assert estado["execucoes"] == {"A": 1, "B": 3, "C": 3}
    eventos = eventos_de(tmp_path)
    assert sum(1 for e in eventos if e["evento"] == "reconciliacao.iniciada") == 2
    assert [e["rodadas"] for e in eventos if e["evento"] == "reconciliacao.esgotada"] == [2]


def test_gate_cobertura_preencher_revisao_usa_rascunho_anterior(tmp_path):
    spec = spec_dependencias()
    estado = {"evaluator": 0, "execucoes": {"A": 0, "B": 0, "C": 0}}
    prompts: dict[str, list[str]] = {"A": [], "B": [], "C": []}

    def roteador(papel, prompt):
        if papel == "executor":
            sid = next(s for s in ["A", "B", "C"] if f"subagente '{s}'" in prompt)
            estado["execucoes"][sid] += 1
            prompts[sid].append(prompt)
            return f"{sid} rascunho {estado['execucoes'][sid]}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            estado["evaluator"] += 1
            if estado["evaluator"] == 1:
                return json.dumps({
                    "aprovado": False,
                    "lacunas": ["B precisa ser alinhado"],
                    "nos_a_refazer": ["B"],
                })
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver(), politica=pol)

    grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "dep-revisao"}})

    assert "NÃO reescreva do zero" in prompts["B"][1]
    assert "B rascunho 1" in prompts["B"][1]


def test_gate_cobertura_preencher_sem_no_nomeado_eh_inerte(tmp_path):
    estado = {"executor": 0, "evaluator": 0}

    def roteador(papel, prompt):
        if papel == "pesquisador":
            estado["executor"] += 1
            return "RESULTADO"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            estado["evaluator"] += 1
            return json.dumps({"aprovado": False, "lacunas": ["lacuna global"], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver(), politica=pol)

    resultado = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "inerte"}})

    assert resultado["resposta_final"] == "FINAL"
    assert estado == {"executor": len(SPEC["subagentes"]), "evaluator": 1}
    eventos = eventos_de(tmp_path)
    assert not any(e["evento"].startswith("reconciliacao.") for e in eventos)
    assert not any(e["evento"] == "lacuna.preenchida" for e in eventos)


def _cliente_roteador(roteador):
    stub = ClienteStub(roteador)
    stub.provedor = "stub"
    return ClienteRoteador(
        padrao=stub,
        catalogo=[(stub, frozenset({"pesquisa", "redacao", "codigo"}), 1)],
    )


def test_revisao_plano_auto_mode_nao_interrompe(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(_cliente_roteador(faz_roteador()), log,
                            checkpointer=InMemorySaver(), politica=PoliticaGates(auto_mode=True))
    res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "plano-auto"}})

    assert "__interrupt__" not in res
    assert res["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    eventos = eventos_de(tmp_path)
    assert any(e["evento"] == "gate.auto" and e["portao"] == "plano" for e in eventos)


def test_revisao_plano_manual_interrompe_com_payload(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(_cliente_roteador(faz_roteador()), log,
                            checkpointer=InMemorySaver())
    res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "plano-manual"}})

    assert "__interrupt__" in res
    pedido = res["__interrupt__"][0].value
    assert pedido["portao"] == "plano"
    assert len(pedido["plano"]) == len(SPEC["subagentes"])
    assert all({"id", "papel", "tier", "modelo"} <= set(item) for item in pedido["plano"])


def test_revisao_plano_resume_abortar_nao_roda_fanout(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(_cliente_roteador(faz_roteador()), log,
                            checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "plano-abortar"}}
    res = grafo.invoke({"spec": SPEC}, config)
    assert res["__interrupt__"][0].value["portao"] == "plano"

    retomado = grafo.invoke(Command(resume="abortar"), config)

    assert "resposta_final" not in retomado
    assert retomado["avaliacao"]["abortada"] is True
    eventos = eventos_de(tmp_path)
    assert not any(e["evento"] == "executor.chamado" and e.get("papel") == "pesquisador"
                   for e in eventos)


def test_revisao_plano_resume_dict_edita_tier_antes_do_fanout(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    cliente = _cliente_roteador(faz_roteador())
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        **_orcamento_cliente(tmp_path, cliente),
    )
    config = {"configurable": {"thread_id": "plano-editar"}}
    res = grafo.invoke({"spec": SPEC, "run_id": "plano-editar", "thread_id": "plano-editar"}, config)
    assert res["__interrupt__"][0].value["portao"] == "plano"

    retomado = grafo.invoke(Command(resume={"pesquisa-alfa": "complexa"}), config)

    assert retomado["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    eventos = eventos_de(tmp_path)
    alfa = [e for e in eventos if e["evento"] == "executor.chamado" and e.get("executor") == "pesquisa-alfa"]
    assert alfa and alfa[0]["tier"] == "complexa"
    assert any(e["evento"] == "decisao.plano" and e.get("edicoes") == {"pesquisa-alfa": "complexa"}
               for e in eventos)


def test_revisao_plano_rejeita_edicao_de_id_desconhecido(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(_cliente_roteador(faz_roteador()), log,
                            checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "plano-id-desconhecido"}}
    grafo.invoke({"spec": SPEC}, config)

    with pytest.raises(ValueError, match="subagente desconhecido"):
        grafo.invoke(Command(resume={"nao-existe": "complexa"}), config)


def test_subagente_usa_catalogo_por_capacidade(tmp_path):
    spec = {
        **SPEC,
        "subagentes": [{
            **SPEC["subagentes"][0],
            "id": "capaz",
            "papel": "executor-capaz",
            "tier": None,
            "capacidades_requeridas": ["x"],
        }],
    }
    padrao = ClienteStub(faz_roteador())
    padrao.provedor = "claude"
    capaz = ClienteStub(lambda papel, prompt: "RESULTADO capacidade")
    capaz.provedor = "capaz"
    log = LogEventos(tmp_path / "log.jsonl")
    cliente = ClienteRoteador(padrao=padrao, catalogo=[(capaz, frozenset({"x"}), 1)], log=log)
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        **_orcamento_cliente(tmp_path, cliente),
    )

    resultado = grafo.invoke(
        {"spec": spec, "run_id": "capacidade", "thread_id": "capacidade"},
        {"configurable": {"thread_id": "capacidade"}},
    )

    assert resultado["resultados"][0]["saida"] == "RESULTADO capacidade"
    assert len(capaz.chamadas) == 1
    assert "modelo.roteado_capacidade" in [e["evento"] for e in eventos_de(tmp_path)]


@pytest.mark.parametrize(
    ("tier", "esperado"),
    [
        ("simples", "media"),
        ("media", "complexa"),
        ("complexa", "complexa"),
        (None, "complexa"),
        ("xpto", "complexa"),
    ],
)
def test_proximo_tier(tier, esperado):
    assert _proximo_tier(tier) == esperado


class ClienteTierFake:
    roteamento_capacidades_runtime = True

    def __init__(self, aprovar_na_tentativa: int = 3):
        self.aprovar_na_tentativa = aprovar_na_tentativa
        self.chamadas: list[tuple[str, str | None]] = []
        self.verificacoes = 0

    def chamar(self, papel: str, prompt: str, ferramentas=None, tier=None, timeout=300,
               evitar=None, capacidades=None):
        self.chamadas.append((papel, tier))
        if papel == "pesquisador":
            return f"SAÍDA tentativa {sum(1 for p, _ in self.chamadas if p == 'pesquisador')}"
        if papel == "verifier":
            self.verificacoes += 1
            aprovado = self.verificacoes >= self.aprovar_na_tentativa
            return json.dumps({"aprovado": aprovado, "motivo": "faltou evidência"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")


def _spec_um_subagente(tier="simples", max_tentativas=3):
    return {
        **SPEC,
        "restricoes": {**SPEC["restricoes"], "max_tentativas": max_tentativas},
        "subagentes": [{**SPEC["subagentes"][0], "tier": tier}],
    }


def test_executor_chamado_loga_modelo_resolvido_com_roteador(tmp_path):
    spec = _spec_um_subagente()

    def stub_modelo(resposta, provedor, modelo):
        stub = ClienteStub(lambda papel, prompt: resposta)
        stub.provedor = provedor
        stub.modelo = modelo
        return stub

    executor = stub_modelo("RESULTADO executor", "nv-llama", "meta/llama-3.3-70b-instruct")
    synthesizer = stub_modelo("FINAL PINADO", "nv-qwen", "qwen/qwen3-coder")

    def juiz(papel: str, prompt: str):
        if papel == "planner":
            return json.dumps(spec, ensure_ascii=False)
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        raise AssertionError(f"papel inesperado no juiz: {papel}")

    padrao = ClienteStub(juiz)
    padrao.provedor = "juiz"
    padrao.modelo = "sonnet"
    cliente = ClienteRoteador(
        padrao=padrao,
        tiers={"simples": executor},
        pins={"synthesizer": synthesizer},
        catalogo=[(executor, frozenset({"pesquisa"}), 1)],
    )
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        **_orcamento_cliente(tmp_path, cliente),
    )

    grafo.invoke({"missao_texto": "produza algo", "run_id": "modelo-log",
                  "thread_id": "modelo-log"}, {"configurable": {"thread_id": "modelo-log"}})

    chamados = [e for e in eventos_de(tmp_path) if e["evento"] == "executor.chamado"]
    assert next(e for e in chamados if e["executor"] == "planner")["modelo"] == "juiz/sonnet"
    assert next(e for e in chamados if e["executor"] == spec["subagentes"][0]["id"])["modelo"] == (
        "nv-llama/meta/llama-3.3-70b-instruct"
    )
    assert next(e for e in chamados if e["executor"] == "global_evaluator")["modelo"] == "juiz/sonnet"
    assert next(e for e in chamados if e["executor"] == "synthesizer")["modelo"] == "nv-qwen/qwen/qwen3-coder"


def test_executor_chamado_carrega_template_versao_quando_presentes(tmp_path):
    spec = json.loads(json.dumps(_spec_um_subagente(max_tentativas=1)))
    spec["missao"]["template"] = "pesquisa"
    spec["missao"]["versao_template"] = "v3"

    _, _, _, _ = roda(tmp_path, faz_roteador(), {"spec": spec})

    chamados = [e for e in eventos_de(tmp_path) if e["evento"] == "executor.chamado"]
    assert next(e for e in chamados if e["executor"] == spec["subagentes"][0]["id"])["template"] == "pesquisa"
    assert next(e for e in chamados if e["executor"] == spec["subagentes"][0]["id"])["versao_template"] == "v3"
    assert next(e for e in chamados if e["executor"] == "global_evaluator")["template"] == "pesquisa"
    assert next(e for e in chamados if e["executor"] == "synthesizer")["versao_template"] == "v3"


def test_executor_chamado_modelo_none_com_cliente_single_sem_identidade(tmp_path):
    _, _, _, _ = roda(tmp_path, faz_roteador(), {"spec": _spec_um_subagente(max_tentativas=1)})

    chamados = [e for e in eventos_de(tmp_path) if e["evento"] == "executor.chamado"]
    assert chamados
    assert all("modelo" in e and e["modelo"] is None for e in chamados)


def test_retry_sem_flag_mantem_tier_declarado_em_todas_as_tentativas(tmp_path):
    cliente = ClienteTierFake(aprovar_na_tentativa=3)
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        **_orcamento_cliente(tmp_path, cliente),
    )

    resultado = grafo.invoke(
        {"spec": _spec_um_subagente(), "run_id": "tier-inerte", "thread_id": "tier-inerte"},
        {"configurable": {"thread_id": "tier-inerte"}},
    )

    assert resultado["resultados"][0]["aprovado"] is True
    assert [tier for papel, tier in cliente.chamadas if papel == "pesquisador"] == ["simples", "simples", "simples"]
    assert not any(e["evento"] == "executor.escalado" for e in eventos_de(tmp_path))


def test_retry_com_flag_escala_tier_ate_complexa(tmp_path):
    cliente = ClienteTierFake(aprovar_na_tentativa=3)
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}), escalar_em_retry=True,
        **_orcamento_cliente(tmp_path, cliente),
    )

    resultado = grafo.invoke(
        {"spec": _spec_um_subagente(), "run_id": "tier-escalado", "thread_id": "tier-escalado"},
        {"configurable": {"thread_id": "tier-escalado"}},
    )

    assert resultado["resultados"][0]["aprovado"] is True
    assert [tier for papel, tier in cliente.chamadas if papel == "pesquisador"] == ["simples", "media", "complexa"]
    escalados = [e for e in eventos_de(tmp_path) if e["evento"] == "executor.escalado"]
    assert [(e["de"], e["para"]) for e in escalados] == [("simples", "media"), ("media", "complexa")]


def test_retry_com_flag_nao_escala_quando_aprova_na_primeira(tmp_path):
    cliente = ClienteTierFake(aprovar_na_tentativa=1)
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}), escalar_em_retry=True,
        **_orcamento_cliente(tmp_path, cliente),
    )

    resultado = grafo.invoke(
        {"spec": _spec_um_subagente(), "run_id": "tier-aprovado", "thread_id": "tier-aprovado"},
        {"configurable": {"thread_id": "tier-aprovado"}},
    )

    assert resultado["resultados"][0]["tentativas"] == 1
    assert [tier for papel, tier in cliente.chamadas if papel == "pesquisador"] == ["simples"]
    assert not any(e["evento"] == "executor.escalado" for e in eventos_de(tmp_path))


def test_cli_escalar_liga_flag_e_default_mantem_inerte(monkeypatch, capsys):
    flags: list[bool] = []

    class GrafoFake:
        def invoke(self, entrada, config):
            return {"resposta_final": "ok"}

    monkeypatch.setattr(cli, "construir_cliente", lambda cfg_modelos, dir_registro, log=None: ClienteStub(faz_roteador()))

    def construir_fake(*args, **kwargs):
        flags.append(kwargs["escalar_em_retry"])
        return GrafoFake()

    monkeypatch.setattr(cli, "construir_grafo", construir_fake)

    monkeypatch.setattr(cli.sys, "argv", ["python -m motor", "missão"])
    assert cli.main() == 0
    monkeypatch.setattr(cli.sys, "argv", ["python -m motor", "missão", "--escalar"])
    assert cli.main() == 0

    assert flags == [False, True]
    assert capsys.readouterr().out.count("=== RESPOSTA FINAL ===") == 2
