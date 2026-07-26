"""Probes da auditoria Anthropic (grupos K e S).

Cada teste aqui DEMONSTRA uma falha de invariante documentada em
`docs/auditoria/ACHADOS-anthropic-kernel-spec.md`. Eles falham de propósito
contra o código atual; não corrigem nada.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.spec import WorkflowSpec
from tests.helpers_grafo import construir_grafo_teste as construir_grafo


def _spec_dep():
    base = {
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
            "id": "dep", "objetivo": "auditoria", "contexto": "",
            "criterios_cobertura": ["resultados consistentes"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 3, "max_tentativas": 1},
        "subagentes": [
            {**base, "id": "A"},
            {**base, "id": "B", "depende_de": ["A"]},
            {**base, "id": "C", "depende_de": ["B"]},
        ],
        "sintese": {"instrucao": "junte", "formato": "markdown"},
    }


def _eventos(tmp_path):
    return [json.loads(l) for l in (tmp_path / "log.jsonl").read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------- A1 (G2/S2)
def test_A1_nos_a_refazer_do_evaluator_sao_descartados_quando_ha_reprovado(tmp_path):
    """grafo.py:1147-1149 reconstrói o veredito e PERDE `nos_a_refazer` do evaluator.

    Cenário: C reprova no verifier E o evaluator aponta 'A' como a origem a
    montante. O esperado (G2/S2) é reconciliar A → B → C. O real reconcilia só C.
    """
    spec = _spec_dep()
    estado = {"evaluator": 0, "exec": {"A": 0, "B": 0, "C": 0}}

    def roteador(papel, prompt):
        if papel == "executor":
            sid = next(s for s in "ABC" if f"subagente '{s}'" in prompt)
            estado["exec"][sid] += 1
            return f"{sid} v{estado['exec'][sid]}"
        if papel == "verifier":
            reprova = "subagente 'C'" in prompt and estado["evaluator"] == 0
            return json.dumps({"aprovado": not reprova, "motivo": "auditoria"})
        if papel == "evaluator":
            estado["evaluator"] += 1
            if estado["evaluator"] == 1:
                return json.dumps({
                    "aprovado": False,
                    "lacunas": ["a premissa de A esta errada e contaminou B e C"],
                    "nos_a_refazer": ["A"],
                })
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(papel)

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"})
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver(),
                            politica=pol, max_rodadas_reconciliacao=2)
    grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "audit-a1"}})

    inic = [e for e in _eventos(tmp_path) if e["evento"] == "reconciliacao.iniciada"]
    assert inic, "nenhuma reconciliação ocorreu"
    assert set(inic[0]["nos"]) == {"A", "B", "C"}, (
        f"evaluator apontou 'A' como origem, mas a reconciliação cobriu {inic[0]['nos']}"
    )


# ---------------------------------------------------------------- A2 (S4/S5)
def test_A2_spec_do_usuario_pode_elevar_teto_acima_do_bootstrap(tmp_path):
    """grafo.py:497-500 aceita spec do usuário sem confrontar `teto_bootstrap`.

    A checagem existe SÓ no caminho gerado pelo planner (grafo.py:539). Uma spec
    fornecida (o entrypoint suportado da CLI/serviço) roda com teto arbitrário.
    """
    spec = _spec_dep()
    spec["restricoes"]["teto_custo"] = 1_000_000.0
    tetos = []

    def roteador(papel, prompt):
        if papel == "executor":
            return "ok"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        return "FINAL"

    log = LogEventos(tmp_path / "log.jsonl")
    pol = PoliticaGates(auto_mode=True)

    from motor import orcamento as mod_orc
    real_sessao = mod_orc.RepositorioOrcamento.sessao

    def espiao(self, run_id, thread_id, teto):
        tetos.append(Decimal(str(teto)))
        return real_sessao(self, run_id, thread_id, teto)

    mod_orc.RepositorioOrcamento.sessao = espiao
    try:
        grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=InMemorySaver(),
                                politica=pol, teto_bootstrap=Decimal("2.0"))
        grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "audit-a2"}})
    finally:
        mod_orc.RepositorioOrcamento.sessao = real_sessao

    assert max(tetos) <= Decimal("2.0"), (
        f"spec do usuário abriu sessão de orçamento com teto {max(tetos)} > bootstrap 2.0"
    )


# ---------------------------------------------------------------- A3 (K3/S1)
def test_A3_rubrica_e_criterios_em_branco_passam_na_validacao():
    """spec.py:96,125 usam `list[str]`, não `list[NonBlank]`.

    Uma rubrica `["   "]` satisfaz `if not s.rubrica` e o portão verifier passa a
    julgar contra um critério vazio — gate sintático presente, semântico ausente.
    """
    spec = _spec_dep()
    spec["missao"]["criterios_cobertura"] = ["   "]
    for s in spec["subagentes"]:
        s["rubrica"] = ["", "  "]
    with pytest.raises(Exception):
        WorkflowSpec.model_validate(spec)


# ---------------------------------------------------------------- A4 (S1/S2)
def test_A4_validador_declarado_em_no_modelo_e_silenciosamente_ignorado():
    """spec.py:154-172 só checa `valida`/`validador` quando tipo == 'validador'.

    Um nó tipo 'modelo' pode carregar `validador` e um `valida` apontando para id
    INEXISTENTE. A spec valida, e `subagente()` (grafo.py:635-638) nunca executa
    o validador: o portão declarado não existe em runtime, sem erro nem evento.
    """
    spec = _spec_dep()
    spec["subagentes"][0]["valida"] = "nao-existe"
    spec["subagentes"][0]["validador"] = {
        "kind": "contem", "config": {"requer": ["obrigatorio"], "min": 1},
    }
    with pytest.raises(Exception):
        WorkflowSpec.model_validate(spec)


# ---------------------------------------------------------------- A5 (S1)
def test_A5_runtime_do_contem_aceita_min_zero_que_a_spec_proibe():
    """grafo.py:328 faz `minimo = max(0, min(minimo, len(requer)))`.

    `min: 0` (proibido por ConfigContem, spec.py:30) vira aprovação incondicional
    no runtime. O validador determinístico não reexecuta o contrato da spec.
    """
    from motor.grafo import _validar_contem

    aprovado, motivo, _ = _validar_contem("texto sem nada", {"requer": ["X"], "min": 0})
    assert aprovado is False, f"config fora do contrato aprovou tudo: {motivo}"


# ---------------------------------------------------------------- A6 (K3/S1)
def test_A6_fallback_sem_jsonschema_enfraquece_o_portao_silenciosamente():
    """grafo.py:52-57,303-316 — `jsonschema` NÃO está declarado em pyproject.toml.

    Sem ele, `_validar_schema_minimo` ignora enum/minimum/pattern/oneOf e devolve
    exatamente a mesma mensagem "schema_json aprovado". O mesmo spec produz um
    portão mais fraco conforme o ambiente, sem evento que distinga os dois modos.
    """
    from motor import grafo as g

    schema = {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["ok", "erro"]},
                       "n": {"type": "integer", "minimum": 10}},
        "required": ["status", "n"],
    }
    payload = json.dumps({"status": "INVENTADO", "n": 1})

    real = g.validar_jsonschema
    g.validar_jsonschema = None
    try:
        aprovado_sem, motivo_sem, _ = g._validar_schema_json(payload, {"schema": schema})
    finally:
        g.validar_jsonschema = real
    aprovado_com, _, _ = g._validar_schema_json(payload, {"schema": schema})

    assert aprovado_com is False  # com jsonschema: reprova, como esperado
    assert aprovado_sem == aprovado_com, (
        f"sem jsonschema o mesmo payload é aprovado ({motivo_sem}); "
        "o portão depende de uma dependência não declarada"
    )
