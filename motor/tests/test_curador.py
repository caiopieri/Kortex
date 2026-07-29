import json
import subprocess
import sys

import pytest

from motor.curador import analisar, carregar_runs, certificar_sombra, formatar_custo_markdown, formatar_markdown, preparar_promocao_gated, propor, rodar_sombra


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


def _eventos_modelo(
    papel,
    tier,
    modelo,
    aprovados,
    total,
    latencia=5.0,
    inicio=0.0,
    prefixo="exec",
    template=None,
    versao_template=None,
):
    eventos = []
    t = inicio
    for i in range(total):
        executor = f"{prefixo}-{i}"
        chamado = {
            "t": t,
            "evento": "executor.chamado",
            "executor": executor,
            "papel": papel,
            "tier": tier,
            "tentativa": 1,
            "modelo": modelo,
        }
        if template is not None:
            chamado["template"] = template
        if versao_template is not None:
            chamado["versao_template"] = versao_template
        eventos.append(chamado)
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


def test_curador_exclui_rascunho_por_default_e_inclui_com_flag(tmp_path):
    certificado = _jsonl(
        tmp_path,
        "certificado.jsonl",
        [
            {"t": 0.0, "evento": "run.perfil", "perfil": "certificado"},
            *_eventos_modelo("executor", "simples", "modelo-cert", 1, 1),
        ],
    )
    rascunho = _jsonl(
        tmp_path,
        "rascunho.jsonl",
        [
            {"t": 0.0, "evento": "run.perfil", "perfil": "rascunho"},
            *_eventos_modelo("executor", "simples", "modelo-rascunho", 1, 1, inicio=10.0),
        ],
    )

    perfil = analisar([certificado, rascunho])

    assert [run["id"] for run in perfil["runs"]] == ["certificado.jsonl"]
    assert set(perfil["por_modelo"]) == {"modelo-cert"}

    perfil_com_rascunho = analisar([certificado, rascunho], incluir_rascunho=True)

    assert [run["id"] for run in perfil_com_rascunho["runs"]] == ["certificado.jsonl", "rascunho.jsonl"]
    assert set(perfil_com_rascunho["por_modelo"]) == {"modelo-cert", "modelo-rascunho"}


def test_curador_trata_run_legado_sem_perfil_como_certificado(tmp_path):
    legado = _jsonl(
        tmp_path,
        "legado.jsonl",
        _eventos_modelo("executor", "simples", "modelo-legado", 1, 1),
    )

    runs, malformadas = carregar_runs([legado])
    perfil = analisar([legado])

    assert malformadas == 0
    assert runs[0]["perfil"] == "certificado"
    assert perfil["por_modelo"]["modelo-legado"]["chamadas"] == 1


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


def test_analisar_agrega_por_template_versao_e_desconhecido(tmp_path):
    log = _jsonl(
        tmp_path,
        "templates.jsonl",
        [
            *_eventos_modelo(
                "executor",
                "simples",
                "modelo-a",
                1,
                1,
                inicio=0.0,
                prefixo="v1",
                template="pesquisa",
                versao_template="v1",
            ),
            *_eventos_modelo(
                "executor",
                "simples",
                "modelo-a",
                0,
                1,
                inicio=20.0,
                prefixo="v2",
                template="pesquisa",
                versao_template="v2",
            ),
            *_eventos_modelo("executor", "simples", "modelo-a", 1, 1, inicio=40.0, prefixo="sem-template"),
        ],
    )

    perfil = analisar([log])

    assert set(perfil["por_template_versao"]) == {"desconhecido", "pesquisa@v1", "pesquisa@v2"}
    assert perfil["por_template_versao"]["pesquisa@v1"]["taxa_aprovacao_primeira"] == 1.0
    assert perfil["por_template_versao"]["pesquisa@v2"]["reprovacoes"] == 1
    assert perfil["por_template_versao"]["desconhecido"]["chamadas"] == 1
    markdown = formatar_markdown(perfil)
    assert "## Aptidao por template/versao" in markdown
    assert "- pesquisa@v1:" in markdown


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
    assert "custo_usd_por_chamada" not in slot["ranking"][0]

    insuficiente = _jsonl(
        tmp_path,
        "insuficiente.jsonl",
        _eventos_modelo("especificador", "media", "kimi", 2, 2, inicio=0.0, prefixo="kimi"),
    )
    assert propor(analisar([insuficiente]), min_amostras=3)["slots"]["especificador/media"] == {
        "status": "evidencia_insuficiente",
        "amostras": 2,
    }


def test_propor_desempata_por_custo_real_por_chamada_quando_disponivel(tmp_path):
    log = _jsonl(
        tmp_path,
        "real-cost.jsonl",
        [
            *_eventos_modelo("executor", "complexa", "modelo-a", 3, 3, latencia=5.0, inicio=0.0, prefixo="a"),
            *_eventos_modelo("executor", "complexa", "modelo-b", 3, 3, latencia=5.0, inicio=50.0, prefixo="b"),
        ],
    )
    perfil = analisar([log])
    perfil["custo"]["por_modelo"] = {
        "modelo-a": {"custo_usd": 0.30, "chamadas_com_uso": 3},
        "modelo-b": {"custo_usd": 0.03, "chamadas_com_uso": 3},
    }

    slot = propor(perfil, min_amostras=3, custo={"modelo-a": 1, "modelo-b": 2})["slots"]["executor/complexa"]

    assert [item["modelo"] for item in slot["ranking"]] == ["modelo-b", "modelo-a"]
    assert slot["recomendado"] == "modelo-b"
    assert slot["ranking"][0]["custo_usd_por_chamada"] == 0.01
    assert slot["ranking"][1]["custo_usd_por_chamada"] == 0.1


def test_propor_qualidade_nao_perde_para_custo_real_menor(tmp_path):
    log = _jsonl(
        tmp_path,
        "quality-over-cost.jsonl",
        [
            *_eventos_modelo("executor", "media", "bom-caro", 3, 3, latencia=5.0, inicio=0.0, prefixo="bom"),
            *_eventos_modelo("executor", "media", "pior-barato", 2, 3, latencia=5.0, inicio=50.0, prefixo="pior"),
        ],
    )
    perfil = analisar([log])
    perfil["custo"]["por_modelo"] = {
        "bom-caro": {"custo_usd": 3.00, "chamadas_com_uso": 3},
        "pior-barato": {"custo_usd": 0.03, "chamadas_com_uso": 3},
    }

    slot = propor(perfil, min_amostras=3)["slots"]["executor/media"]

    assert [item["modelo"] for item in slot["ranking"]] == ["bom-caro", "pior-barato"]
    assert slot["recomendado"] == "bom-caro"


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


def test_rodar_sombra_agrega_titular_e_candidato():
    proposta = {"slot": "executor/simples", "titular": "modelo-atual", "candidato": "modelo-novo"}
    casos = [
        {"id": "caso-1", "slot": "executor/simples", "entrada": {"prompt": "..."}},
        {"id": "caso-2", "slot": "executor/simples", "entrada": {"prompt": "..."}},
    ]

    # Os DOIS modelos passam pelo runner, nos mesmos casos: o titular nao vem
    # mais de um dict do chamador.
    respostas = {
        ("caso-1", "modelo-atual"): {"aprovado": True, "custo_usd": 0.02},
        ("caso-2", "modelo-atual"): {"aprovado": False, "custo_usd": 0.02},
        ("caso-1", "modelo-novo"): {"aprovado": True, "custo_usd": 0.01, "saida": "ok"},
        ("caso-2", "modelo-novo"): {"aprovado": False, "custo_usd": 0.01, "motivo": "raso"},
    }
    chamadas: list[tuple[str, str]] = []

    def runner(caso, modelo):
        chamadas.append((caso["id"], modelo))
        return dict(respostas[(caso["id"], modelo)])

    evidencia = rodar_sombra(proposta, casos, runner)

    assert sorted(chamadas) == sorted(respostas)

    assert evidencia["status"] == "sombra_concluida"
    assert evidencia["slot"] == "executor/simples"
    assert evidencia["titular"] == {
        "modelo": "modelo-atual",
        "aprovados": 1,
        "total": 2,
        "taxa_aprovacao": 0.5,
        "custo_medio_usd": 0.02,
    }
    assert evidencia["candidato"] == {
        "modelo": "modelo-novo",
        "aprovados": 1,
        "total": 2,
        "taxa_aprovacao": 0.5,
        "custo_medio_usd": 0.01,
    }
    assert len(evidencia["casos"]) == 2
    assert evidencia["casos"][0]["candidato"]["aprovado"] is True
    assert evidencia["casos_ignorados"] == 0


def test_rodar_sombra_nao_quebra_com_excecao_do_runner():
    proposta = {"slot": "s", "titular": "t", "candidato": "c"}
    casos = [
        {"id": "a", "slot": "s", "entrada": {}, "titular": {"modelo": "t", "aprovado": True}},
        {"id": "b", "slot": "s", "entrada": {}, "titular": {"modelo": "t", "aprovado": True}},
    ]

    def runner(caso, modelo):
        if caso["id"] == "b":
            raise RuntimeError("boom")
        return {"aprovado": True, "custo_usd": 0.01}

    evidencia = rodar_sombra(proposta, casos, runner)

    assert evidencia["candidato"]["total"] == 2
    assert evidencia["candidato"]["aprovados"] == 1
    caso_b = evidencia["casos"][1]["candidato"]
    assert caso_b["aprovado"] is False
    assert "RuntimeError" in caso_b["motivo"]


def test_rodar_sombra_emite_evento_read_only():
    proposta = {"slot": "executor/simples", "titular": "t", "candidato": "c"}
    casos = [
        {
            "id": "x",
            "slot": "executor/simples",
            "entrada": {},
            "titular": {"modelo": "t", "aprovado": True, "custo_usd": 0.02},
        },
    ]

    def runner(caso, modelo):
        return {"aprovado": True, "custo_usd": 0.01}

    eventos = []

    def capturar(nome, payload):
        eventos.append((nome, payload))

    proposta_antes = json.loads(json.dumps(proposta))
    casos_antes = json.loads(json.dumps(casos))

    evidencia = rodar_sombra(proposta, casos, runner, emitir_evento=capturar)

    assert eventos
    nome, payload = eventos[0]
    assert nome == "curador.sombra"
    assert payload["slot"] == "executor/simples"
    assert payload["titular"] == "t"
    assert payload["candidato"] == "c"
    assert payload["aprovados_titular"] == 1
    assert payload["aprovados_candidato"] == 1
    assert proposta == proposta_antes
    assert casos == casos_antes
    assert evidencia["status"] == "sombra_concluida"


# Chave de teste. A real mora fora do repo; o que importa aqui e que exista uma,
# porque sem chave `certificar_sombra` recusa tudo -- e um teste que passasse sem
# chave estaria provando o caminho errado.
CHAVE = b"chave-de-teste-do-curador-32bytes!!"


@pytest.fixture(autouse=True)
def chave_no_ambiente(tmp_path_factory, monkeypatch):
    """Publica a MESMA chave em `KORTEX_CURADOR_CHAVE`.

    Autouse porque `preparar_promocao_gated` e a CLI nao recebem a chave por
    parametro -- eles carregam do ambiente, que e o caminho de producao. Sem
    isto, esses testes passariam a exercitar o caminho "sem chave" achando que
    exercitam o caminho feliz.
    """
    arquivo = tmp_path_factory.mktemp("chave") / "curador.key"
    arquivo.write_bytes(CHAVE)
    arquivo.chmod(0o600)
    monkeypatch.setenv("KORTEX_CURADOR_CHAVE", str(arquivo))
    return arquivo


def _evidencia(taxa_t, custo_t, taxa_c, custo_c, slot="executor/simples", titular="t", candidato="c"):
    # 40 casos: acima do PISO_CASOS de 30. Com 10 nao ha o que certificar, e essa
    # e a mudanca -- amostra minuscula deixou de ser uma opcao do proponente.
    total = 40
    casos = [{
        "id": str(i),
        "slot": slot,
        "meta": {"split": "held-out", "proveniencia": "suite-curador"},
    } for i in range(total)]

    def runner(caso, modelo):
        taxa, custo = (taxa_t, custo_t) if modelo == titular else (taxa_c, custo_c)
        return {"aprovado": int(caso["id"]) < round(taxa * total), "custo_usd": custo}

    return rodar_sombra(
        {"slot": slot, "titular": titular, "candidato": candidato,
         "politica": {"min_casos": 30}},
        casos,
        runner,
        chave=CHAVE,
    )


def test_certificar_aprova_quando_candidato_melhor_em_qualidade_e_custo():
    evid = _evidencia(taxa_t=0.5, custo_t=0.02, taxa_c=0.8, custo_c=0.01)

    resultado = certificar_sombra(evid, chave=CHAVE)

    assert resultado["status"] == "certificado"
    assert "candidato vence titular" in resultado["motivo"]


def test_certificar_rejeita_candidato_mais_barato_com_qualidade_menor():
    evid = _evidencia(taxa_t=0.8, custo_t=0.02, taxa_c=0.5, custo_c=0.01)

    resultado = certificar_sombra(evid, chave=CHAVE)

    assert resultado["status"] == "rejeitado"
    assert "nao vence titular" in resultado["motivo"]


def test_certificar_rejeita_qualidade_igual_mesmo_com_custo_menor():
    evid = _evidencia(taxa_t=0.8, custo_t=0.02, taxa_c=0.8, custo_c=0.01)

    resultado = certificar_sombra(evid, chave=CHAVE)

    assert resultado["status"] == "rejeitado"
    assert "nao vence titular" in resultado["motivo"]


def test_certificar_rejeita_custo_ausente():
    # Vantagem de qualidade grande de proposito: o veto por custo so e alcancado
    # depois que a qualidade passa no teste, entao 0.8 vs 0.9 (p=0.0625) pararia
    # antes e o teste estaria medindo outra coisa.
    evid = _evidencia(taxa_t=0.5, custo_t=None, taxa_c=0.9, custo_c=0.01)

    resultado = certificar_sombra(evid, chave=CHAVE)

    assert resultado["status"] == "rejeitado"
    assert resultado["motivo"] == "custo incomparavel"


def test_certificar_rejeita_custo_candidato_ausente():
    evid = _evidencia(taxa_t=0.5, custo_t=0.02, taxa_c=0.8, custo_c=None)

    resultado = certificar_sombra(evid, chave=CHAVE)

    assert resultado["status"] == "rejeitado"
    assert resultado["motivo"] == "custo incomparavel"


def test_certificar_emite_evento_certificou():
    eventos = []
    evid = _evidencia(taxa_t=0.5, custo_t=0.02, taxa_c=0.9, custo_c=0.01)

    certificar_sombra(
        evid, emitir_evento=lambda nome, payload: eventos.append((nome, payload)),
        chave=CHAVE,
    )

    assert len(eventos) == 1
    assert eventos[0][0] == "curador.certificou"
    assert eventos[0][1]["slot"] == "executor/simples"


def test_certificar_emite_evento_rejeitou():
    eventos = []
    evid = _evidencia(taxa_t=0.5, custo_t=None, taxa_c=0.9, custo_c=0.01)

    certificar_sombra(
        evid, emitir_evento=lambda nome, payload: eventos.append((nome, payload)),
        chave=CHAVE,
    )

    assert len(eventos) == 1
    assert eventos[0][0] == "curador.rejeitou"
    assert eventos[0][1]["motivo"] == "custo incomparavel"


def test_rodar_sombra_cust_none_nao_vira_zero_na_evidencia():
    proposta = {"slot": "s", "titular": "t", "candidato": "c"}
    casos = [
        {
            "id": "1",
            "slot": "s",
            "entrada": {},
            "titular": {"modelo": "t", "aprovado": True},
        },
    ]

    def runner(caso, modelo):
        return {"aprovado": True, "custo_usd": None}

    evidencia = rodar_sombra(proposta, casos, runner)

    assert evidencia["titular"]["custo_medio_usd"] is None
    assert evidencia["candidato"]["custo_medio_usd"] is None


class _RepositorioCertificacoesFake:
    def __init__(self, registro):
        self.registro = registro

    def obter(self, certification_id):
        if certification_id != self.registro["certification_id"]:
            return None
        return self.registro


def _registro_certificacao(*, aprovado=True):
    evidencia = _evidencia(
        taxa_t=0.5,
        custo_t=0.02,
        taxa_c=1.0 if aprovado else 0.5,
        custo_c=0.01,
        titular="modelo-t",
        candidato="modelo-c",
    )
    certification_id = "cert-1"
    registro = {
        "certification_id": certification_id,
        "evidencia": evidencia,
        "decisao": certificar_sombra(evidencia),
    }
    return certification_id, _RepositorioCertificacoesFake(registro)


def test_preparar_promocao_gera_intencao_pendente_quando_certificado():
    certification_id, repo = _registro_certificacao()
    intencao = preparar_promocao_gated(certification_id, repo)

    assert intencao["status"] == "promocao_pendente"
    assert intencao["slot"] == "executor/simples"
    assert intencao["de"] == "modelo-t"
    assert intencao["para"] == "modelo-c"
    assert intencao["requer_gate"] is True
    assert intencao["evidencia"]["titular"]["taxa_aprovacao"] == 0.5
    assert intencao["evidencia"]["candidato"]["taxa_aprovacao"] == 1.0
    assert intencao["evidencia"]["motivo_certificacao"] is not None


def test_preparar_promocao_veta_certificacao_rejeitada():
    certification_id, repo = _registro_certificacao(aprovado=False)
    intencao = preparar_promocao_gated(certification_id, repo)

    assert intencao["status"] == "promocao_vetada"
    assert "nao aprovada" in intencao["motivo"]


def test_preparar_promocao_veta_certificacao_com_status_desconhecido():
    intencao = preparar_promocao_gated({"status": "sombra_concluida"})

    assert intencao["status"] == "promocao_vetada"


def test_preparar_promocao_emite_evento_pendente():
    eventos = []
    certification_id, repo = _registro_certificacao()
    intencao = preparar_promocao_gated(
        certification_id,
        repo,
        emitir_evento=lambda nome, payload: eventos.append((nome, payload)),
    )

    assert len(eventos) == 1
    assert eventos[0][0] == "curador.promocao_pendente"
    assert eventos[0][1]["slot"] == "executor/simples"
    assert eventos[0][1]["de"] == "modelo-t"
    assert eventos[0][1]["para"] == "modelo-c"
    assert intencao["status"] == "promocao_pendente"


def test_preparar_promocao_nao_emite_evento_quando_vetada():
    eventos = []
    certification_id, repo = _registro_certificacao(aprovado=False)
    intencao = preparar_promocao_gated(
        certification_id,
        repo,
        emitir_evento=lambda nome, payload: eventos.append((nome, payload)),
    )

    assert eventos == []
    assert intencao["status"] == "promocao_vetada"


def test_cli_sombra_certificacao_e_promocao_read_only(tmp_path):
    sombra_json = tmp_path / "sombra.json"
    evidencia_out = tmp_path / "evidencia-out.json"
    sombra_json.write_text(
        json.dumps({
            "proposta": {
                "slot": "executor/simples",
                "titular": "modelo-t",
                "candidato": "modelo-c",
                "politica": {"min_casos": 1},
            },
            "casos": [
                {
                    "id": "caso-1",
                    "slot": "executor/simples",
                    "entrada": {"prompt": "held-out"},
                    "meta": {"split": "held-out", "proveniencia": "suite-cli"},
                    "titular": {"modelo": "modelo-t", "aprovado": True, "custo_usd": 0.02},
                    "candidato": {"aprovado": True, "custo_usd": 0.01, "motivo": "ok"},
                }
            ],
        }),
        encoding="utf-8",
    )

    sombra = subprocess.run(
        [sys.executable, "-m", "motor.curador", "--sombra", str(sombra_json), "--json", str(evidencia_out)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Evidencia de Sombra" in sombra.stdout
    assert "- slot: executor/simples" in sombra.stdout
    assert "- modelo: modelo-c" in sombra.stdout
    evidencia_cli = json.loads(evidencia_out.read_text(encoding="utf-8"))
    # `sombra_simulada`, nao `sombra_concluida`: o runner do `--sombra` da CLI so
    # ecoa o campo `candidato` do arquivo de entrada -- nenhum modelo foi chamado.
    # Este teste ANTES exigia `sombra_concluida`, ou seja, travava o defeito: uma
    # evidencia escrita a mao saia selada e passava na certificacao.
    assert evidencia_cli["status"] == "sombra_simulada"
    assert evidencia_cli["candidato"]["custo_medio_usd"] == 0.01

    evidencia_json = tmp_path / "evidencia.json"
    certificacao_out = tmp_path / "certificacao-out.json"
    evidencia_json.write_text(
        json.dumps(_evidencia(taxa_t=0.5, custo_t=0.02, taxa_c=1.0, custo_c=0.01)),
        encoding="utf-8",
    )

    certificacao = subprocess.run(
        [sys.executable, "-m", "motor.curador", "--certificar", str(evidencia_json), "--json", str(certificacao_out)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Certificacao de Sombra" in certificacao.stdout
    assert "- status: certificado" in certificacao.stdout
    certificacao_cli = json.loads(certificacao_out.read_text(encoding="utf-8"))
    assert certificacao_cli["status"] == "certificado"

    certificacao_json = tmp_path / "certificacao.json"
    promocao_out = tmp_path / "promocao-out.json"
    certificacao_json.write_text(json.dumps(certificacao_cli), encoding="utf-8")

    promocao = subprocess.run(
        [sys.executable, "-m", "motor.curador", "--promocao", str(certificacao_json), "--json", str(promocao_out)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# Intencao de Promocao" in promocao.stdout
    assert "- status: promocao_vetada" in promocao.stdout
    assert "curador.promoveu" not in promocao.stdout
    promocao_cli = json.loads(promocao_out.read_text(encoding="utf-8"))
    assert promocao_cli["status"] == "promocao_vetada"


def test_evidencia_do_runner_cli_nao_pode_ser_certificada() -> None:
    """U-06a: o `--sombra` da CLI fabricava evidência certificável.

    `_runner_cli_read_only` ecoa `caso["candidato"]` do arquivo de entrada e a
    evidência saía selada como `sombra_concluida` — zero chamada de modelo, e
    passava na certificação. Qualquer um que escrevesse o JSON certificava a
    troca de modelo que quisesse.

    A marca é `sombra_simulada`, e a certificação a recusa. Este teste falha se
    alguém devolver o status antigo ao caminho da CLI.
    """
    from motor.curador import _runner_cli_read_only, certificar_sombra, rodar_sombra

    proposta = {
        "slot": "executor/simples",
        "titular": "modelo-t",
        "candidato": "modelo-c",
        "politica": {"min_casos": 1},
    }
    casos = [{
        "id": "c1",
        "slot": "executor/simples",
        "meta": {"origem": "held-out", "split": "held-out", "proveniencia": "real"},
        "titular": {"modelo": "modelo-t", "aprovado": False, "custo_usd": 0.02},
        "candidato": {"modelo": "modelo-c", "aprovado": True, "custo_usd": 0.01},
    }]

    simulada = rodar_sombra(
        proposta, casos, _runner_cli_read_only, runner_executa_modelo=False,
    )
    assert simulada["status"] == "sombra_simulada"
    assert certificar_sombra(simulada)["status"] != "certificado"

    # O mesmo caminho, declarando execução real, segue produzindo evidência apta:
    # o fix marca a PROVENIÊNCIA, não quebra a sombra.
    real = rodar_sombra(proposta, casos, _runner_cli_read_only)
    assert real["status"] == "sombra_concluida"


def test_modelo_atendeu_resolve_o_modelo_generico_do_omniroute(tmp_path):
    """Sob OmniRoute, `executor.chamado` só diz `omniroute/roteado`.

    O curador perfila aptidão POR MODELO lendo esse campo. Sem resolver, Gemini,
    Opus e Codex caem no mesmo balde e o perfil por modelo — a entrada do
    flywheel — vira uma linha só. Descoberto rodando a missão do eBay pelo
    Gemini em 2026-07-29; o log dizia um modelo e o ledger dizia outro.
    """
    log = _jsonl(tmp_path, "roteado.jsonl", [
        {"t": 0.0, "evento": "executor.chamado", "executor": "a", "papel": "executor",
         "tier": "simples", "tentativa": 1, "modelo": "omniroute/roteado"},
        {"t": 0.1, "evento": "modelo.atendeu", "papel": "executor", "fase": "executor",
         "modelo": "agy-gemini-3.1-pro-high", "provedor": "google", "tentativa": 1},
        {"t": 1.0, "evento": "executor.respondeu", "executor": "a", "tentativa": 1},
        {"t": 1.1, "evento": "modelo.atendeu", "papel": "verifier", "fase": "verifier",
         "modelo": "agy-claude-opus-4-6-thinking", "provedor": "anthropic", "tentativa": 1},
        {"t": 2.0, "evento": "executor.chamado", "executor": "b", "papel": "synthesizer",
         "tentativa": 1, "modelo": "omniroute/roteado"},
        {"t": 2.1, "evento": "modelo.atendeu", "papel": "synthesizer", "fase": "synthesizer",
         "modelo": "codex-gpt-5.6-luna", "provedor": "openai", "tentativa": 1},
        {"t": 3.0, "evento": "executor.respondeu", "executor": "b", "tentativa": 1},
    ])

    perfil = analisar([log])

    assert set(perfil["por_modelo"]) == {"agy-gemini-3.1-pro-high", "codex-gpt-5.6-luna"}
    assert perfil["por_slot_modelo"]["executor/simples"].keys() == {"agy-gemini-3.1-pro-high"}


def test_log_sem_modelo_atendeu_passa_intacto(tmp_path):
    """Log antigo não pode ser corrompido pela resolução.

    O outro desfecho: sem isto, "resolveu tudo" seria indistinguível de
    "apagou o modelo de todo log anterior ao evento novo".
    """
    log = _jsonl(tmp_path, "antigo.jsonl", [
        {"t": 0.0, "evento": "executor.chamado", "executor": "a", "papel": "executor",
         "tier": "simples", "tentativa": 1, "modelo": "modelo-antigo"},
        {"t": 1.0, "evento": "executor.respondeu", "executor": "a", "tentativa": 1},
    ])

    assert set(analisar([log])["por_modelo"]) == {"modelo-antigo"}
