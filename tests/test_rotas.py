from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor import __main__ as cli
from motor.eventos import LogEventos
from motor.grafo import construir_grafo, montar_prompt_planner
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.registro import rotas_de_registro
from motor.servico import GerenciadorJobs


RAIZ = Path(__file__).parent.parent
PROMPT_PLANNER_ANTIGO = """Você é o planner da meta-fábrica. Missão do usuário:
\"\"\"{missao}\"\"\"

Produza uma WorkflowSpec versão 0.1 em JSON (responda APENAS o JSON), conforme o schema:
{schema}

Regras: entre 2 e {max_sub} subagentes focados e INDEPENDENTES (depende_de sempre []);
cada subagente com rubrica objetiva e verificável; criterios_cobertura checáveis contra a missão;
padrao = "fan_out_sintese".
Subagentes podem ser executados por modelos de capacidade limitada: escreva cada objetivo sem
ambiguidade nem decisão de design implícita, e rubricas checáveis MECANICAMENTE (formato exigido,
números/evidências presentes, seções obrigatórias) — nunca critérios que dependem de bom gosto.
Cada rubrica deve ter NO MÁXIMO 5 critérios, e cada critério testa a PRESENÇA ou o FORMATO de algo
verificável na própria saída (uma seção, um campo, um número, um exemplo) — não a correção de minúcia
de domínio. NÃO exija versão exata de biblioteca, nomes internos de parâmetros de API, valores-padrão
de funções de terceiros, nem conhecimento factual profundo que um executor de capacidade limitada não
garante: a rubrica é o CONTRATO MÍNIMO do objetivo, não uma prova de erudição.
Para cada subagente, classifique o campo "tier" pela complexidade da tarefa (roteamento por custo):
"simples" (extração/formatação/lookup direto), "media" (pesquisa ou redação com algum raciocínio),
"complexa" (design, trade-offs, modelagem ou síntese que exige um modelo forte).
Para cada subagente, preencha também "capacidades_requeridas": a LISTA de capacidades que a tarefa exige, escolhidas SOMENTE deste vocabulário fixo (use exatamente estas palavras): codigo (escrever/editar/revisar código ou script), redacao (texto natural: relatório, doc, spec, descrição), calculo (quantitativo determinístico: custos, tolerâncias, dimensionamento), pesquisa (levantar info externa: busca, sourcing, lookup), raciocinio-longo (planejamento, trade-offs, design ou síntese multi-passo). Liste só o que a tarefa REALMENTE exige (em geral 1–2 tags). Estas tags valem para qualquer domínio (software, hardware, manufatura): a produção física é de outros executores; aqui você classifica só o trabalho cognitivo.{erro}"""


def _entidade(path: Path, nome: str, padrao: str | None) -> None:
    linha_padrao = f"padrao: {padrao}\n" if padrao is not None else ""
    path.write_text(
        "---\n"
        "tipo: rota\n"
        f"nome: {nome}\n"
        f"{linha_padrao}"
        "quando: teste\n"
        "gabarito: decomponha\n"
        "---\n",
        encoding="utf-8",
    )


def test_prompt_default_permanece_byte_identico():
    valores = {"missao": "missão", "schema": '{"type":"object"}', "max_sub": 10, "erro": ""}

    assert montar_prompt_planner(**valores) == PROMPT_PLANNER_ANTIGO.format(**valores)


def test_loader_carrega_catalogo_semente():
    rotas = rotas_de_registro(RAIZ / "exemplos" / "registro-rotas")

    assert rotas["pesquisa-sintese"]["padrao"] == "fan_out_sintese"
    assert rotas["construcao"]["padrao"] == "grafo_dependencias"


@pytest.mark.parametrize("padrao", [None, "desconhecido"])
def test_loader_rejeita_padrao_ausente_ou_invalido(tmp_path, padrao):
    _entidade(tmp_path / "rota.md", "rota", padrao)

    with pytest.raises(ValueError, match="padrao"):
        rotas_de_registro(tmp_path)


def test_loader_rejeita_nome_duplicado(tmp_path):
    _entidade(tmp_path / "a.md", "duplicada", "fan_out_sintese")
    _entidade(tmp_path / "b.md", "duplicada", "grafo_dependencias")

    with pytest.raises(ValueError, match="duplicada.*a.md.*b.md"):
        rotas_de_registro(tmp_path)


def test_prompt_da_rota_construcao_instrui_dependencias():
    rota = rotas_de_registro(RAIZ / "exemplos" / "registro-rotas")["construcao"]

    prompt = montar_prompt_planner(missao="construa", schema="{}", max_sub=10, rota=rota)

    assert rota["gabarito"] in prompt
    assert 'padrao = "grafo_dependencias"' in prompt
    assert "depende_de sempre []" not in prompt


def test_cli_rejeita_rota_sem_registro(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "argv", ["python -m motor", "missão", "--rota", "construcao"])

    assert cli.main() == 2
    assert "--rota exige --registro" in capsys.readouterr().out


def test_cli_rejeita_rota_inexistente(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["python -m motor", "missão", "--registro", str(tmp_path), "--rota", "ausente"],
    )

    assert cli.main() == 2
    assert "rota 'ausente' não encontrada" in capsys.readouterr().out


def test_rota_construcao_flui_ate_executor_de_dependencias(tmp_path):
    spec = json.loads((RAIZ / "exemplos" / "grafo-dep-minimo.json").read_text(encoding="utf-8"))
    rota = rotas_de_registro(RAIZ / "exemplos" / "registro-rotas")["construcao"]
    prompts_planner: list[str] = []

    def roteador(papel: str, prompt: str):
        if papel == "planner":
            prompts_planner.append(prompt)
            return json.dumps(spec, ensure_ascii=False)
        if papel in {"raciocinador", "codificador", "validador"}:
            return f"SAÍDA {papel}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        rota=rota,
    )

    resultado = grafo.invoke(
        {"missao_texto": "construa em etapas"},
        {"configurable": {"thread_id": "rota-construcao"}},
    )
    eventos = [
        json.loads(linha)
        for linha in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert resultado["resposta_final"] == "FINAL"
    assert "depende_de sempre []" not in prompts_planner[0]
    assert any(evento["evento"] == "grafo_dep.iniciado" for evento in eventos)


def _eventos(path: Path) -> list[dict]:
    return [json.loads(linha) for linha in path.read_text(encoding="utf-8").splitlines()]


def _rodar_com_selecao(tmp_path, resposta_seletor: str):
    spec = json.loads((RAIZ / "exemplos" / "grafo-dep-minimo.json").read_text(encoding="utf-8"))
    rotas = rotas_de_registro(RAIZ / "exemplos" / "registro-rotas")
    chamadas_planner = 0

    def roteador(papel: str, prompt: str):
        nonlocal chamadas_planner
        if papel == "planner":
            chamadas_planner += 1
            if chamadas_planner == 1:
                return resposta_seletor
            return json.dumps(spec, ensure_ascii=False)
        if papel in {"raciocinador", "codificador", "validador"}:
            return f"SAÍDA {papel}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log_path = tmp_path / "log.jsonl"
    log = LogEventos(log_path)
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        rotas=rotas,
    )
    resultado = grafo.invoke(
        {"missao_texto": "construa em etapas"},
        {"configurable": {"thread_id": "selecao-automatica"}},
    )
    return resultado, _eventos(log_path), chamadas_planner


def test_planner_escolhe_rota_do_catalogo(tmp_path):
    resultado, eventos, chamadas = _rodar_com_selecao(
        tmp_path,
        json.dumps({"rota": "construcao"}),
    )

    assert resultado["spec"]["padrao"] == "grafo_dependencias"
    assert resultado["resposta_final"] == "FINAL"
    assert chamadas == 2
    assert any(
        evento["evento"] == "rota.escolhida"
        and evento["rota"] == "construcao"
        and evento["padrao"] == "grafo_dependencias"
        and evento["fallback"] is False
        for evento in eventos
    )
    assert any(evento["evento"] == "grafo_dep.iniciado" for evento in eventos)


@pytest.mark.parametrize("resposta_seletor", [
    "lixo",
    json.dumps({"rota": "rota-inventada"}),
])
def test_escolha_invalida_cai_na_rota_default(tmp_path, resposta_seletor):
    spec = json.loads((RAIZ / "exemplos" / "missao-pesquisa.json").read_text(encoding="utf-8"))
    rotas = rotas_de_registro(RAIZ / "exemplos" / "registro-rotas")
    chamadas_planner = 0

    def roteador(papel: str, prompt: str):
        nonlocal chamadas_planner
        if papel == "planner":
            chamadas_planner += 1
            return resposta_seletor if chamadas_planner == 1 else json.dumps(spec, ensure_ascii=False)
        if papel == "pesquisador":
            return "RESULTADO"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log_path = tmp_path / "log.jsonl"
    grafo = construir_grafo(
        ClienteStub(roteador),
        LogEventos(log_path),
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        rotas=rotas,
    )

    resultado = grafo.invoke(
        {"missao_texto": "missão ambígua"},
        {"configurable": {"thread_id": "fallback-rota"}},
    )
    eventos = _eventos(log_path)

    assert resultado["spec"]["padrao"] == "fan_out_sintese"
    assert resultado["resposta_final"] == "FINAL"
    assert any(
        evento["evento"] == "rota.escolhida"
        and evento["rota"] == "pesquisa-sintese"
        and evento["padrao"] == "fan_out_sintese"
        and evento["fallback"] is True
        for evento in eventos
    )


def test_rota_explicita_vence_catalogo_sem_chamar_seletor(tmp_path):
    spec = json.loads((RAIZ / "exemplos" / "grafo-dep-minimo.json").read_text(encoding="utf-8"))
    rotas = rotas_de_registro(RAIZ / "exemplos" / "registro-rotas")
    chamadas_planner: list[str] = []

    def roteador(papel: str, prompt: str):
        if papel == "planner":
            chamadas_planner.append(prompt)
            return json.dumps(spec, ensure_ascii=False)
        if papel in {"raciocinador", "codificador", "validador"}:
            return f"SAÍDA {papel}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log_path = tmp_path / "log.jsonl"
    grafo = construir_grafo(
        ClienteStub(roteador),
        LogEventos(log_path),
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        rota=rotas["construcao"],
        rotas=rotas,
    )

    resultado = grafo.invoke(
        {"missao_texto": "construa"},
        {"configurable": {"thread_id": "rota-explicita"}},
    )

    assert resultado["spec"]["padrao"] == "grafo_dependencias"
    assert len(chamadas_planner) == 1
    assert '"rota": "<nome>"' not in chamadas_planner[0]
    assert not any(evento["evento"] == "rota.escolhida" for evento in _eventos(log_path))


def test_servico_carrega_catalogo_de_rotas_uma_vez(tmp_path):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        dir_registro=RAIZ / "exemplos" / "registro-rotas",
        cliente=ClienteStub(lambda papel, prompt: None),
    )

    assert set(gerenciador.rotas) == {"pesquisa-sintese", "construcao"}
