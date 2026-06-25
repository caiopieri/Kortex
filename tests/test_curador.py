import json
import subprocess
import sys

from motor.curador import analisar, carregar_runs, formatar_markdown


def _jsonl(tmp_path, nome, eventos, corrompida=False):
    log = tmp_path / nome
    linhas = [json.dumps(evento) for evento in eventos]
    if corrompida:
        linhas.insert(3, "{linha quebrada")
    log.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return log


def _eventos_observador():
    return [
        {"t": 0.0, "evento": "executor.chamado", "executor": "planner", "tentativa": 1},
        {"t": 5.0, "evento": "executor.erro", "executor": "planner", "motivo": "spec invalida", "tentativa": 1},
        {"t": 5.1, "evento": "executor.chamado", "executor": "planner", "tentativa": 2},
        {"t": 9.0, "evento": "spec.criada", "missao": "m1", "subagentes": 2},
        {
            "t": 10.0,
            "evento": "executor.chamado",
            "executor": "sub-a",
            "papel": "executor",
            "tier": "simples",
            "tentativa": 1,
        },
        {"t": 20.0, "evento": "executor.respondeu", "executor": "sub-a", "tentativa": 1},
        {"t": 21.0, "evento": "portao.aprovado", "portao": "verifier:sub-a", "ciclo": 1},
        {
            "t": 30.0,
            "evento": "executor.chamado",
            "executor": "sub-b",
            "papel": "executor",
            "tier": "simples",
            "tentativa": 1,
        },
        {"t": 40.0, "evento": "executor.respondeu", "executor": "sub-b", "tentativa": 1},
        {"t": 41.0, "evento": "portao.reprovado", "portao": "verifier:sub-b", "ciclo": 1, "motivo": "raso"},
        {"t": 42.0, "evento": "executor.escalado", "executor": "sub-b", "de": "simples", "para": "media", "tentativa": 2},
        {
            "t": 43.0,
            "evento": "executor.chamado",
            "executor": "sub-b",
            "papel": "executor",
            "tier": "media",
            "tentativa": 2,
        },
        {"t": 55.0, "evento": "executor.respondeu", "executor": "sub-b", "tentativa": 2},
        {"t": 56.0, "evento": "portao.aprovado", "portao": "verifier:sub-b", "ciclo": 2},
        {
            "t": 60.0,
            "evento": "modelo.falha",
            "papel": "verifier",
            "tentativa": 1,
            "motivo": "HTTPError: HTTP Error 429: Too Many Requests",
        },
        {
            "t": 61.0,
            "evento": "provedor.auto_esgotado",
            "provedor": "nv-kimi",
            "papel": "verifier",
            "motivo": "HTTP 429 no free",
        },
        {"t": 62.0, "evento": "modelo.reroteado_esgotado", "papel": "verifier", "de": "nv-kimi", "para": "nv-llama"},
        {"t": 70.0, "evento": "portao.reprovado", "portao": "cobertura", "motivo": "faltou fechamento"},
        {"t": 71.0, "evento": "reconciliacao.iniciada", "nos": ["a", "b"]},
        {"t": 72.0, "evento": "reconciliacao.iniciada", "nos": ["c"]},
        {"t": 80.0, "evento": "portao.aprovado", "portao": "cobertura"},
    ]


def test_analisar_metricas_sinteticas_do_observador(tmp_path):
    log = _jsonl(tmp_path, "run.jsonl", _eventos_observador(), corrompida=True)

    perfil = analisar([log])

    assert perfil["linhas_malformadas"] == 1
    simples = perfil["por_papel_tier"]["executor"]["simples"]
    assert simples["chamadas"] == 2
    assert simples["respostas"] == 2
    assert simples["verifier_julgados"] == 2
    assert simples["verifier_aprovados_primeira"] == 1
    assert simples["taxa_aprovacao_primeira"] == 0.5
    assert simples["reprovacoes"] == 1
    assert simples["amostras_motivos"] == ["raso"]
    assert simples["escaladas"] == 1
    assert simples["escaladas_convergidas"] == 1
    assert simples["taxa_convergencia_pos_escalada"] == 1.0
    assert simples["latencia"] == {"amostras": 2, "mediana": 10.0, "p90": 10.0}

    media = perfil["por_papel_tier"]["executor"]["media"]
    assert media["chamadas"] == 1
    assert media["respostas"] == 1
    assert media["latencia"]["mediana"] == 12.0

    planner = perfil["por_papel_tier"]["planner"]["sem-tier"]
    assert planner["chamadas"] == 2
    assert planner["erros"] == 1
    assert planner["taxa_erro"] == 0.5

    run = perfil["runs"][0]
    assert run["planner"]["tentativas_ate_spec_criada"] == 2
    assert run["planner"]["latencia_ate_spec_criada"] == 9.0
    assert run["cobertura"] == {
        "reprovada": True,
        "aprovada": True,
        "reprovado_para_aprovado_via_reconciliacao": True,
        "rodadas_reconciliacao": 2,
        "closure_por_rodada": [2, 1],
    }
    assert run["resiliencia"]["provedor_auto_esgotado"] == {"nv-kimi": {"verifier": 1}}
    assert run["resiliencia"]["modelo_reroteado_esgotado"] == {"nv-kimi->nv-llama": {"verifier": 1}}
    assert len(run["resiliencia"]["motivos_429"]) == 2


def test_carregar_runs_separa_jsonl_concatenado_quando_t_reinicia(tmp_path):
    log = _jsonl(
        tmp_path,
        "concat.jsonl",
        [
            {"t": 10.0, "evento": "executor.chamado", "executor": "a"},
            {"t": 11.0, "evento": "executor.respondeu", "executor": "a"},
            {"t": 0.1, "evento": "executor.chamado", "executor": "b"},
        ],
    )

    runs, malformadas = carregar_runs([log])

    assert malformadas == 0
    assert [run["id"] for run in runs] == ["concat.jsonl", "concat.jsonl#2"]
    assert [len(run["eventos"]) for run in runs] == [2, 1]


def test_markdown_e_cli_json(tmp_path):
    log = _jsonl(tmp_path, "run.jsonl", _eventos_observador())
    saida_json = tmp_path / "perfil.json"

    resultado = subprocess.run(
        [sys.executable, "-m", "motor.curador", str(log), "--json", str(saida_json)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Perfil do Curador" in resultado.stdout
    perfil = json.loads(saida_json.read_text(encoding="utf-8"))
    assert perfil["por_papel_tier"]["executor"]["simples"]["chamadas"] == 2
    assert "executor/simples" in formatar_markdown(perfil)
