from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from motor.curador import certificar_sombra, preparar_promocao_gated, rodar_sombra
from motor.eventos_schema import ESQUEMA, tipos, valido
from tests.audit_corpus import casos, executar_caso, materializar_corpus


CONTRATOS_CURADOR = {
    "curador.sombra": (
        "slot",
        "titular",
        "candidato",
        "casos",
        "aprovados_titular",
        "aprovados_candidato",
    ),
    "curador.certificou": ("slot", "titular", "candidato", "motivo"),
    "curador.rejeitou": ("slot", "titular", "candidato", "motivo"),
    "curador.promocao_pendente": ("slot", "de", "para"),
}


@pytest.mark.parametrize("nodeid", casos("H06b"))
def test_reprodutores_h06b(tmp_path: Path, nodeid: str) -> None:
    executar_caso(materializar_corpus(tmp_path), nodeid)


def _eventos_emitidos() -> list[dict[str, Any]]:
    eventos: list[dict[str, Any]] = []

    def emitir(tipo: str, payload: Any) -> None:
        assert isinstance(payload, dict)
        eventos.append({"evento": tipo, "t": 0.0, "seq": len(eventos) + 1, **payload})

    proposta = {
        "slot": "redator/T1",
        "titular": "modelo-atual",
        "candidato": "modelo-novo",
        "politica": {"min_casos": 1},
    }
    evidencia = rodar_sombra(
        proposta,
        [
            {
                "id": "caso-1",
                "slot": "redator/T1",
                "meta": {"split": "held-out", "proveniencia": "suite-h06b"},
                "titular": {"aprovado": False, "custo_usd": 2.0},
            }
        ],
        lambda _caso, modelo: {"modelo": modelo, "aprovado": True, "custo_usd": 1.0},
        emitir,
    )
    certificacao = certificar_sombra(evidencia, emitir)
    certificar_sombra(
        {
            "slot": "redator/T1",
            "titular": {"modelo": "modelo-atual", "taxa_aprovacao": 1.0, "custo_medio_usd": 1.0},
            "candidato": {"modelo": "modelo-novo", "taxa_aprovacao": 0.0, "custo_medio_usd": 2.0},
        },
        emitir,
    )
    certification_id = "h06b-control"
    registro = {
        "certification_id": certification_id,
        "evidencia": evidencia,
        "decisao": certificacao,
    }

    class RepoFake:
        def obter(self, _certification_id: str) -> dict[str, Any]:
            return registro

    preparar_promocao_gated(certification_id, RepoFake(), emitir)
    return eventos


def test_schema_curador_declara_apenas_payloads_publicos_completos() -> None:
    assert {tipo for tipo in tipos() if tipo.startswith("curador.")} == set(CONTRATOS_CURADOR)

    reservados = {"evento", "t", "seq"}
    for tipo, campos in CONTRATOS_CURADOR.items():
        assert ESQUEMA[tipo]["categoria"] == "curador"
        assert tuple(ESQUEMA[tipo]["campos"]) == campos
        assert reservados.isdisjoint(campos)


def test_payloads_emitidos_pelo_curador_satisfazem_schema_v2() -> None:
    eventos = _eventos_emitidos()
    assert [evento["evento"] for evento in eventos] == list(CONTRATOS_CURADOR)

    for evento in eventos:
        campos = set(CONTRATOS_CURADOR[evento["evento"]])
        assert set(evento) == {"evento", "t", "seq"} | campos
        assert valido(evento)


def test_payloads_curador_falham_fechado_quando_mutados() -> None:
    for evento in _eventos_emitidos():
        for campo in CONTRATOS_CURADOR[evento["evento"]]:
            ausente = dict(evento)
            ausente.pop(campo)
            assert not valido(ausente), (evento["evento"], campo, "ausente")

            tipo_errado = dict(evento)
            tipo_errado[campo] = True if type(evento[campo]) is int else 1
            assert not valido(tipo_errado), (evento["evento"], campo, "tipo")

        extra = {**evento, "campo_nao_declarado": "hostil"}
        assert not valido(extra), (evento["evento"], "extra")
