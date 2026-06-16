import json

from motor.telemetria import carregar, resumir


def test_resumir_contadores_do_log():
    eventos = [
        {"evento": "spec.criada", "missao": "m1", "subagentes": 2},
        {"evento": "executor.chamado", "papel": "pesquisador"},
        {"evento": "executor.chamado", "papel": "pesquisador"},
        {"evento": "portao.reprovado", "portao": "verifier:x"},
        {"evento": "gate.auto", "portao": "plano"},
        {"evento": "modelo.reroteado_esgotado", "papel": "pesquisador"},
        {"evento": "tarefa.concluida", "missao": "m1"},
    ]

    assert resumir(eventos) == {
        "missao": "m1",
        "subagentes": 2,
        "chamadas_por_papel": {"pesquisador": 2},
        "reprovacoes_verifier": 1,
        "reroteamentos": {"esgotado": 1, "juiz": 0, "ferramentas": 0},
        "gates": {"auto": 1, "manual": 0},
        "falhas_modelo": 0,
        "concluida": True,
    }


def test_resumir_vazio_devolve_zeros():
    assert resumir([]) == {
        "missao": None,
        "subagentes": 0,
        "chamadas_por_papel": {},
        "reprovacoes_verifier": 0,
        "reroteamentos": {"esgotado": 0, "juiz": 0, "ferramentas": 0},
        "gates": {"auto": 0, "manual": 0},
        "falhas_modelo": 0,
        "concluida": False,
    }


def test_carregar_le_jsonl(tmp_path):
    log = tmp_path / "log.jsonl"
    eventos = [
        {"evento": "spec.recebida", "missao": "m2", "subagentes": 1},
        {"evento": "escalado", "para": "plano"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8")

    assert carregar(log) == eventos
