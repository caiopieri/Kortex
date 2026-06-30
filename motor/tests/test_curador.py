import json
import subprocess
import sys

from motor.curador import analisar, carregar_runs, formatar_custo_markdown, formatar_markdown, propor


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


def _eventos_modelo(papel, tier, modelo, aprovados, total, latencia=5.0, inicio=0.0, prefixo="exec"):
    eventos = []
    t = inicio
    for i in range(total):
        executor = f"{prefixo}-{i}"
        eventos.append(
            {
                "t": t,
                "evento": "executor.chamado",
                "executor": executor,
                "papel": papel,
                "tier": tier,
                "tentativa": 1,
                "modelo": modelo,
            }
        )
        eventos.append({"t": t + latencia, "evento": "executor.respondeu", "executor": executor, "tentativa": 1})
        if i < aprovados:
            eventos.append({"t": t + latencia + 0.1, "evento": "portao.aprovado", "portao": f"verifier:{executor}", "ciclo": 1})
        else:
            eventos.append(
                {
                    "t": t + latencia + 0.1,
                    "evento": "portao.reprovado",
                    "portao": f"verifier:{executor}",
                    "ciclo": 1,
                    "motivo": "insuficiente",
                }
            )
        t += latencia + 1.0
    return eventos


def _eventos_custo(executor, papel, tier, modelo, inicio, fim, uso=None, erro=False):
    eventos = [
        {
            "t": inicio,
            "evento": "executor.chamado",
            "executor": executor,
            "papel": papel,
            "tier": tier,
            "tentativa": 1,
            "modelo": modelo,
        }
    ]
    if uso:
        provedor, modelo_uso, prompt, completion, total = uso
        eventos.append(
            {
                "t": inicio + 0.5,
                "evento": "modelo.uso",
                "papel": papel,
                "provedor": provedor,
                "modelo": modelo_uso,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            }
        )
    eventos.append(
        {
            "t": fim,
            "evento": "executor.erro" if erro else "executor.respondeu",
            "executor": executor,
            "tentativa": 1,
        }
    )
    return eventos


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
    assert planner["falhas_internas"] == 0
    assert planner["taxa_erro"] == 0.5

    assert perfil["por_papel_tier"]["verifier"]["sem-tier"]["falhas_internas"] == 1
    assert perfil["por_modelo"]["desconhecido"]["falhas_internas"] == 1
    assert perfil["por_slot_modelo"]["executor/simples"]["desconhecido"]["chamadas"] == 2

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


def test_analisar_agrega_e_ranqueia_por_modelo(tmp_path):
    log = _jsonl(
        tmp_path,
        "modelos.jsonl",
        [
            {
                "t": 0.0,
                "evento": "executor.chamado",
                "executor": "sub-a",
                "papel": "executor",
                "tier": "simples",
                "tentativa": 1,
                "modelo": "zzz-bom",
            },
            {"t": 8.0, "evento": "executor.respondeu", "executor": "sub-a", "tentativa": 1},
            {"t": 9.0, "evento": "portao.aprovado", "portao": "verifier:sub-a", "ciclo": 1},
            {
                "t": 10.0,
                "evento": "executor.chamado",
                "executor": "sub-b",
                "papel": "executor",
                "tier": "simples",
                "tentativa": 1,
                "modelo": "aaa-ruim",
            },
            {"t": 13.0, "evento": "executor.respondeu", "executor": "sub-b", "tentativa": 1},
            {"t": 14.0, "evento": "portao.reprovado", "portao": "verifier:sub-b", "ciclo": 1, "motivo": "raso"},
            {"t": 15.0, "evento": "executor.escalado", "executor": "sub-b", "de": "simples", "para": "media"},
            {
                "t": 16.0,
                "evento": "executor.chamado",
                "executor": "sub-b",
                "papel": "executor",
                "tier": "media",
                "tentativa": 2,
                "modelo": "modelo-medio",
            },
            {"t": 21.0, "evento": "executor.respondeu", "executor": "sub-b", "tentativa": 2},
            {"t": 22.0, "evento": "portao.aprovado", "portao": "verifier:sub-b", "ciclo": 2},
        ],
    )

    perfil = analisar([log])

    bom = perfil["por_modelo"]["zzz-bom"]
    assert bom["chamadas"] == 1
    assert bom["taxa_aprovacao_primeira"] == 1.0
    assert bom["latencia"]["mediana"] == 8.0

    ruim = perfil["por_modelo"]["aaa-ruim"]
    assert ruim["chamadas"] == 1
    assert ruim["reprovacoes"] == 1
    assert ruim["escaladas"] == 1
    assert ruim["escaladas_convergidas"] == 1

    markdown = formatar_markdown(perfil)
    assert "## Aptidao por modelo" in markdown
    assert markdown.index("- zzz-bom:") < markdown.index("- aaa-ruim:")


def test_analisar_agrega_por_slot_modelo(tmp_path):
    log = _jsonl(
        tmp_path,
        "slots.jsonl",
        [
            *_eventos_modelo("especificador", "media", "kimi", 1, 1, inicio=0.0, prefixo="esp"),
            *_eventos_modelo("arquiteto", "complexa", "codex", 1, 1, inicio=20.0, prefixo="arq"),
        ],
    )

    perfil = analisar([log])

    assert set(perfil["por_slot_modelo"]) == {"arquiteto/complexa", "especificador/media"}
    assert perfil["por_slot_modelo"]["especificador/media"]["kimi"]["verifier_julgados"] == 1
    assert perfil["por_slot_modelo"]["arquiteto/complexa"]["codex"]["verifier_aprovados_primeira"] == 1


def test_propor_ranqueia_desempata_e_respeita_amostras(tmp_path):
    qualidade = _jsonl(
        tmp_path,
        "qualidade.jsonl",
        [
            *_eventos_modelo("executor", "media", "bom", 3, 3, inicio=0.0, prefixo="bom"),
            *_eventos_modelo("executor", "media", "ruim", 1, 3, inicio=50.0, prefixo="ruim"),
            *_eventos_modelo("executor", "media", "zero", 0, 3, inicio=100.0, prefixo="zero"),
        ],
    )
    slot = propor(analisar([qualidade]), min_amostras=3)["slots"]["executor/media"]
    assert slot["status"] == "proposto"
    assert [item["modelo"] for item in slot["ranking"]] == ["bom", "ruim", "zero"]
    assert slot["recomendado"] == "bom"
    assert slot["evitar"] == ["zero"]

    latencia = _jsonl(
        tmp_path,
        "latencia.jsonl",
        [
            *_eventos_modelo("executor", "simples", "lento", 3, 3, latencia=8.0, inicio=0.0, prefixo="lento"),
            *_eventos_modelo("executor", "simples", "rapido", 3, 3, latencia=2.0, inicio=50.0, prefixo="rapido"),
        ],
    )
    slot = propor(analisar([latencia]), min_amostras=3)["slots"]["executor/simples"]
    assert [item["modelo"] for item in slot["ranking"]] == ["rapido", "lento"]

    custo = _jsonl(
        tmp_path,
        "custo.jsonl",
        [
            *_eventos_modelo("executor", "complexa", "modelo-a", 3, 3, latencia=5.0, inicio=0.0, prefixo="a"),
            *_eventos_modelo("executor", "complexa", "modelo-b", 3, 3, latencia=5.0, inicio=50.0, prefixo="b"),
        ],
    )
    slot = propor(analisar([custo]), min_amostras=3, custo={"modelo-a": 2, "modelo-b": 1})["slots"]["executor/complexa"]
    assert [item["modelo"] for item in slot["ranking"]] == ["modelo-b", "modelo-a"]
    assert slot["recomendado"] == "modelo-b"
    assert "_custo" not in slot["ranking"][0]

    insuficiente = _jsonl(
        tmp_path,
        "insuficiente.jsonl",
        _eventos_modelo("especificador", "media", "kimi", 2, 2, inicio=0.0, prefixo="kimi"),
    )
    assert propor(analisar([insuficiente]), min_amostras=3)["slots"]["especificador/media"] == {
        "status": "evidencia_insuficiente",
        "amostras": 2,
    }


def test_incompleta_inferida_por_chamada_sem_resposta_ou_erro(tmp_path):
    log = _jsonl(
        tmp_path,
        "incompleta.jsonl",
        [
            {
                "t": 0.0,
                "evento": "executor.chamado",
                "executor": "ok",
                "papel": "executor",
                "tier": "media",
                "tentativa": 1,
                "modelo": "modelo-m",
            },
            {"t": 1.0, "evento": "executor.respondeu", "executor": "ok", "tentativa": 1},
            {
                "t": 2.0,
                "evento": "executor.chamado",
                "executor": "travado",
                "papel": "executor",
                "tier": "media",
                "tentativa": 1,
                "modelo": "modelo-m",
            },
        ],
    )

    perfil = analisar([log])

    modelo = perfil["por_modelo"]["modelo-m"]
    assert modelo["chamadas"] == 2
    assert modelo["respostas"] == 1
    assert modelo["incompletas"] == 1
    assert modelo["taxa_incompletas"] == 0.5
    slot = perfil["por_slot_modelo"]["executor/media"]["modelo-m"]
    assert slot["incompletas"] == 1
    assert slot["taxa_incompletas"] == 0.5
    assert "incompletas 1 (50.0%)" in formatar_markdown(perfil)


def test_propor_evita_modelo_com_muitas_incompletas_sem_julgamentos(tmp_path):
    log = _jsonl(
        tmp_path,
        "travado.jsonl",
        [
            {
                "t": float(i),
                "evento": "executor.chamado",
                "executor": f"travado-{i}",
                "papel": "executor",
                "tier": "simples",
                "tentativa": 1,
                "modelo": "modelo-travado",
            }
            for i in range(3)
        ],
    )

    slot = propor(analisar([log]), min_amostras=3)["slots"]["executor/simples"]

    assert slot["status"] == "evidencia_insuficiente"
    assert slot["evitar"] == ["modelo-travado"]


def test_propor_aplica_piso_de_qualidade_e_marca_candidato_unico(tmp_path):
    abaixo = _jsonl(
        tmp_path,
        "abaixo.jsonl",
        _eventos_modelo("pesquisador", "complexa", "codex", 1, 3, inicio=0.0, prefixo="codex"),
    )

    slot = propor(analisar([abaixo]), min_amostras=3, piso_aprovacao=0.6)["slots"][
        "pesquisador/complexa"
    ]

    assert slot["status"] == "melhor_disponivel_abaixo_do_piso"
    assert slot["recomendado"] == "codex"
    assert slot["unico_candidato"] is True
    assert "aprovacao 33.3% < piso 60.0%" in slot["aviso"]

    acima = _jsonl(
        tmp_path,
        "acima.jsonl",
        _eventos_modelo("especificador", "media", "kimi", 3, 3, inicio=0.0, prefixo="kimi"),
    )

    slot = propor(analisar([acima]), min_amostras=3, piso_aprovacao=0.6)["slots"]["especificador/media"]

    assert slot["status"] == "proposto"
    assert slot["unico_candidato"] is True


def test_modelo_falha_conta_como_falha_interna_sem_inflar_taxa_erro(tmp_path):
    log = _jsonl(
        tmp_path,
        "falhas.jsonl",
        [
            {
                "t": 0.0,
                "evento": "executor.chamado",
                "executor": "sub-a",
                "papel": "executor",
                "tier": "simples",
                "tentativa": 1,
                "modelo": "modelo-x",
            },
            {"t": 1.0, "evento": "modelo.falha", "papel": "executor", "tentativa": 1, "motivo": "429"},
            {"t": 2.0, "evento": "modelo.falha", "papel": "executor", "tentativa": 2, "motivo": "429"},
            {"t": 3.0, "evento": "modelo.falha", "papel": "executor", "tentativa": 3, "motivo": "429"},
            {"t": 4.0, "evento": "executor.erro", "executor": "sub-a", "tentativa": 1, "motivo": "sem resposta"},
        ],
    )

    perfil = analisar([log])

    modelo = perfil["por_modelo"]["modelo-x"]
    assert modelo["chamadas"] == 1
    assert modelo["erros"] == 1
    assert modelo["falhas_internas"] == 3
    assert modelo["taxa_erro"] == 1.0

    papel = perfil["por_papel_tier"]["executor"]["simples"]
    assert papel["falhas_internas"] == 3
    assert papel["taxa_erro"] == 1.0


def test_custo_agrega_tokens_por_modelo_run_e_slot(tmp_path):
    log = _jsonl(
        tmp_path,
        "custo.jsonl",
        [
            *_eventos_custo("a", "executor", "simples", "nvidia/modelo-a", 0.0, 2.0,
                            ("nvidia", "modelo-a", 100, 50, 150)),
            *_eventos_custo("b", "executor", "media", "openrouter/modelo-b", 3.0, 5.0,
                            ("openrouter", "modelo-b", 200, 25, 225), erro=True),
        ],
    )

    perfil = analisar(
        [log],
        precos={
            "nvidia/modelo-a": {"in_por_1k": 0.01, "out_por_1k": 0.03},
            "openrouter/modelo-b": {"in_por_1k": 0.02, "out_por_1k": 0.04},
        },
    )

    custo = perfil["custo"]
    assert custo["total"]["tokens_prompt"] == 300
    assert custo["total"]["tokens_completion"] == 75
    assert custo["total"]["tokens_total"] == 375
    assert custo["total"]["tempo_total_s"] == 4.0
    assert custo["total"]["custo_usd"] == 0.0075

    modelo_a = custo["por_modelo"]["nvidia/modelo-a"]
    assert modelo_a["tokens_prompt"] == 100
    assert modelo_a["tokens_completion"] == 50
    assert modelo_a["tempo_total_s"] == 2.0
    assert modelo_a["chamadas_com_uso"] == 1
    assert modelo_a["custo_usd"] == 0.0025

    slot_a = custo["por_slot_modelo"]["executor/simples"]["nvidia/modelo-a"]
    assert slot_a["tokens_total"] == 150
    assert slot_a["tempo_total_s"] == 2.0
    assert custo["por_run"][0]["id"] == "custo.jsonl"
    assert custo["por_run"][0]["tokens_total"] == 375


def test_custo_sem_precos_mantem_tokens_e_custo_usd_none(tmp_path):
    log = _jsonl(
        tmp_path,
        "sem-preco.jsonl",
        _eventos_custo("a", "executor", "simples", "nvidia/modelo-a", 0.0, 2.0,
                       ("nvidia", "modelo-a", 10, 5, 15)),
    )

    custo = analisar([log])["custo"]

    assert custo["total"]["tokens_total"] == 15
    assert custo["total"]["tempo_total_s"] == 2.0
    assert custo["total"]["custo_usd"] is None
    assert custo["por_modelo"]["nvidia/modelo-a"]["custo_usd"] is None
    assert "| nvidia/modelo-a | 1 | 10 | 5 | 15 | 2.000s |  |" in formatar_custo_markdown(custo)


def test_custo_modelo_cli_sem_usage_aparece_por_tempo(tmp_path):
    log = _jsonl(
        tmp_path,
        "cli.jsonl",
        _eventos_custo("pesquisa", "pesquisador", "complexa", "codex/default", 10.0, 14.5),
    )

    cli = analisar([log])["custo"]["por_modelo"]["codex/default"]

    assert cli["tokens_total"] == 0
    assert cli["tempo_total_s"] == 4.5
    assert cli["chamadas_com_uso"] == 0
    assert cli["custo_usd"] is None


def test_eventos_orfaos_caem_em_desconhecido_sem_papel_fantasma(tmp_path):
    log = _jsonl(
        tmp_path,
        "orfaos.jsonl",
        [
            {"t": 1.0, "evento": "executor.respondeu", "executor": "fantasma", "tentativa": 1},
            {"t": 2.0, "evento": "portao.reprovado", "portao": "verifier:fantasma", "ciclo": 1, "motivo": "sem chamada"},
        ],
    )

    perfil = analisar([log])

    assert "fantasma" not in perfil["por_papel_tier"]
    desconhecido = perfil["por_papel_tier"]["desconhecido"]["sem-tier"]
    assert desconhecido["respostas"] == 1
    assert desconhecido["verifier_julgados"] == 1
    assert desconhecido["reprovacoes"] == 1
    assert perfil["por_modelo"]["desconhecido"]["respostas"] == 1


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
    assert "## Aptidao por modelo" in resultado.stdout
    assert resultado.stdout == formatar_markdown(analisar([log]))
    perfil = json.loads(saida_json.read_text(encoding="utf-8"))
    assert perfil["por_papel_tier"]["executor"]["simples"]["chamadas"] == 2
    assert "por_modelo" in perfil
    assert "executor/simples" in formatar_markdown(perfil)

    proposta = subprocess.run(
        [
            sys.executable,
            "-m",
            "motor.curador",
            str(log),
            "--propor",
            "--min-amostras",
            "1",
            "--piso",
            "0.9",
            "--limiar-falha",
            "0.4",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# Proposta do Curador" in proposta.stdout
    assert "## executor/simples" in proposta.stdout
    assert "- status: melhor_disponivel_abaixo_do_piso" in proposta.stdout
    assert "| modelo | score | aprov_1a | taxa_erro | incompletas | taxa_incompletas |" in proposta.stdout

    log_custo = _jsonl(
        tmp_path,
        "ledger.jsonl",
        _eventos_custo("a", "executor", "simples", "nvidia/modelo-a", 0.0, 1.0,
                       ("nvidia", "modelo-a", 100, 50, 150)),
    )
    precos = tmp_path / "precos.json"
    precos.write_text(
        json.dumps({"nvidia/modelo-a": {"in_por_1k": 0.01, "out_por_1k": 0.03}}),
        encoding="utf-8",
    )
    ledger = subprocess.run(
        [sys.executable, "-m", "motor.curador", str(log_custo), "--custo", str(precos)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# Livro-razão de Custo" in ledger.stdout
    assert "| nvidia/modelo-a | 1 | 100 | 50 | 150 | 1.000s | 0.002500 |" in ledger.stdout
