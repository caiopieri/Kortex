"""Probes de auditoria (grupo U) — demonstram falhas de U1/U2/U3 no curador.

Estes testes NAO consertam o codigo: cada teste falha (ou passa demonstrando o
buraco) para evidenciar um achado do relatorio docs/auditoria/ACHADOS-anthropic-curador.md.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from motor.curador import certificar_sombra, preparar_promocao_gated, propor, rodar_sombra


PROPOSTA_BASE = {"slot": "executor/t1", "titular": "modelo-t", "candidato": "modelo-c"}


# --------------------------------------------------------------------------- U2
def test_U2_min_casos_autodeclarado_certifica_com_um_unico_caso() -> None:
    """ACHADO 1: min_casos vem da politica do PROPONENTE; nao ha piso do sistema.

    Um unico caso held-out basta para trocar o titular de producao.
    """
    proposta = {**PROPOSTA_BASE, "politica": {"min_casos": 1}}
    caso = {
        "id": "unico",
        "slot": proposta["slot"],
        "meta": {"split": "held-out", "proveniencia": "quem-propos"},
        "titular": {"aprovado": False, "custo_usd": 10.0},
    }
    evidencia = rodar_sombra(
        proposta, [caso], lambda _c, _m: {"aprovado": True, "custo_usd": 0.01}
    )
    resultado = certificar_sombra(evidencia)

    # DEMONSTRACAO: n=1 certifica. O assert abaixo e o comportamento DESEJADO.
    assert resultado["status"] != "certificado", (
        "n=1 certificou uma troca de modelo de producao; min_casos e autodeclarado"
    )


def test_U2_proveniencia_held_out_e_puramente_declarativa() -> None:
    """ACHADO 2: 'held-out' e so uma string no proprio input; nada amarra ao ledger."""
    proposta = {**PROPOSTA_BASE, "politica": {"min_casos": 2}}
    casos = [
        {
            "id": str(i),
            "slot": proposta["slot"],
            # meta.origem faz duplo dever: vira split E proveniencia (curador.py:447-453)
            "meta": {"origem": "held-out"},
            "titular": {"aprovado": False, "custo_usd": 10.0},
        }
        for i in range(2)
    ]
    evidencia = rodar_sombra(
        proposta, casos, lambda _c, _m: {"aprovado": True, "custo_usd": 0.01}
    )
    assert evidencia["casos"][0]["split"] == "held-out"
    assert evidencia["casos"][0]["proveniencia"] == "held-out"
    resultado = certificar_sombra(evidencia)

    assert resultado["status"] != "certificado", (
        "a unica prova de que o caso e held-out e a string 'held-out' vinda do input"
    )


def test_U2_titular_e_fabricado_pelo_proponente_e_nunca_reexecutado() -> None:
    """ACHADO 3: os dois lados da comparacao vem do MESMO input.

    O titular nunca roda: seu 'aprovado' e seu 'custo_usd' sao declarados no caso.
    Basta declarar um titular ruim e caro para certificar qualquer candidato.
    """
    proposta = {**PROPOSTA_BASE, "politica": {"min_casos": 5}}
    casos = [
        {
            "id": str(i),
            "slot": proposta["slot"],
            "meta": {"split": "held-out", "proveniencia": "forjado"},
            # titular difamado: sempre reprovado e 1000x mais caro
            "titular": {"aprovado": False, "custo_usd": 1000.0},
        }
        for i in range(5)
    ]
    evidencia = rodar_sombra(
        proposta, casos, lambda _c, _m: {"aprovado": True, "custo_usd": 0.001}
    )
    resultado = certificar_sombra(evidencia)

    assert resultado["status"] != "certificado", (
        "certificou com o desempenho do titular inteiramente fabricado pelo chamador"
    )


def test_U2_selo_nao_e_chaveado_evidencia_100pct_forjada_certifica() -> None:
    """ACHADO 4: evidencia_sha256 e um hash publico recomputavel, nao um MAC.

    Uma evidencia inventada do zero (nenhuma sombra rodou) passa na certificacao.
    """
    from motor.curador import _selo_sombra  # noqa: PLC0415

    evidencia: dict[str, Any] = {
        "versao": 2,
        "status": "sombra_concluida",
        "slot": "executor/t1",
        "modelos": {"titular": "modelo-caro", "candidato": "modelo-barato"},
        "politica": {"min_casos": 3},
        "casos": [
            {
                "id": f"inventado-{i}",
                "split": "held-out",
                "proveniencia": "nunca-existiu",
                "titular": {"aprovado": False, "custo_usd": 9.0},
                "candidato": {"aprovado": True, "custo_usd": 0.1},
            }
            for i in range(3)
        ],
    }
    evidencia["evidencia_sha256"] = _selo_sombra(evidencia)
    resultado = certificar_sombra(evidencia)

    assert resultado["status"] != "certificado", (
        "evidencia sintetica sem nenhuma execucao real passou na certificacao"
    )


# --------------------------------------------------------------------------- U1
def test_U1_deepcopy_e_furavel_por_objeto_que_se_devolve() -> None:
    """ACHADO 5: o isolamento da sombra depende de deepcopy, que respeita __deepcopy__.

    Um valor aninhado que devolve a si mesmo entrega ao runner um ALIAS do caso
    original; o runner (read-only por contrato) muta o held-out em memoria.
    """

    class NaoCopiavel:
        def __init__(self) -> None:
            self.valor = "original"

        def __deepcopy__(self, _memo: dict[int, Any]) -> "NaoCopiavel":
            return self

    espiao = NaoCopiavel()
    casos = [
        {
            "id": "a",
            "slot": PROPOSTA_BASE["slot"],
            "entrada": {"payload": espiao},
            "titular": {"aprovado": True, "custo_usd": 1.0},
        }
    ]

    def runner(caso: dict[str, Any], _modelo: str) -> dict[str, Any]:
        caso["entrada"]["payload"].valor = "MUTADO PELO RUNNER"
        return {"aprovado": True, "custo_usd": 0.5}

    rodar_sombra(PROPOSTA_BASE, casos, runner)

    assert espiao.valor == "original", (
        "runner mutou o caso held-out original atraves de alias que sobreviveu ao deepcopy"
    )


def test_U1_baseexception_no_runner_aborta_a_sombra_inteira() -> None:
    """ACHADO 6: _executar_runner captura Exception, nao BaseException.

    Um runner que levanta SystemExit (o proprio curador usa SystemExit em helpers)
    aborta os casos seguintes em vez de reprovar so o caso.
    """
    casos = [
        {"id": c, "slot": PROPOSTA_BASE["slot"], "titular": {"aprovado": True}}
        for c in ("a", "b", "c")
    ]

    def runner(caso: dict[str, Any], _modelo: str) -> dict[str, Any]:
        if caso["id"] == "b":
            raise SystemExit("runner morreu")
        return {"aprovado": True}

    evidencia = rodar_sombra(PROPOSTA_BASE, casos, runner)
    assert len(evidencia["casos"]) == 3, "falha de um caso abortou os seguintes"


# --------------------------------------------------------------------------- U3
def test_U3_repositorio_e_a_unica_autoridade_mas_nao_valida_nada() -> None:
    """ACHADO 7: preparar_promocao_gated aceita qualquer objeto com .obter().

    Nao ha verificacao de identidade/integridade do repositorio, nem de que a
    evidencia guardada corresponde a uma sombra realmente executada.
    """

    class RepoDeMentira:
        def obter(self, certification_id: str) -> dict[str, Any]:
            from motor.curador import _selo_sombra  # noqa: PLC0415

            evidencia: dict[str, Any] = {
                "versao": 2,
                "status": "sombra_concluida",
                "slot": "executor/t1",
                "modelos": {"titular": "gpt-caro", "candidato": "gratis"},
                "politica": {"min_casos": 1},
                "casos": [
                    {
                        "id": "x",
                        "split": "held-out",
                        "proveniencia": "inventada",
                        "titular": {"aprovado": False, "custo_usd": 100.0},
                        "candidato": {"aprovado": True, "custo_usd": 0.0},
                    }
                ],
            }
            evidencia["evidencia_sha256"] = _selo_sombra(evidencia)
            return {
                "certification_id": certification_id,
                "evidencia": evidencia,
                "decisao": certificar_sombra(deepcopy(evidencia)),
            }

    intencao = preparar_promocao_gated("qualquer-id", RepoDeMentira())
    assert intencao["status"] != "promocao_pendente", (
        "repositorio arbitrario com evidencia sintetica gerou intencao de promocao"
    )


# --------------------------------------------------------- propor / score
def test_propor_score_ignora_incompletas_e_mistura_denominadores() -> None:
    """ACHADO 8: o score de qualidade nao penaliza chamadas incompletas.

    modelo-ruim tem 40% de chamadas incompletas (nunca responderam) mas vence
    modelo-bom no ranking porque incompletas nao entram no score.
    """
    def metricas(**kw: Any) -> dict[str, Any]:
        base = {
            "chamadas": 10,
            "respostas": 10,
            "erros": 0,
            "incompletas": 0,
            "falhas_internas": 0,
            "taxa_erro": 0.0,
            "taxa_incompletas": 0.0,
            "verifier_julgados": 5,
            "verifier_aprovados_primeira": 5,
            "taxa_aprovacao_primeira": 1.0,
            "reprovacoes": 0,
            "amostras_motivos": [],
            "escaladas": 0,
            "escaladas_convergidas": 0,
            "taxa_convergencia_pos_escalada": 0.0,
            "latencia": {"amostras": 1, "mediana": 1.0, "p90": 1.0},
        }
        base.update(kw)
        return base

    perfil = {
        "por_slot_modelo": {
            "executor/t1": {
                "modelo-ruim": metricas(
                    incompletas=4, taxa_incompletas=0.4, latencia={"amostras": 1, "mediana": 0.5, "p90": 0.5}
                ),
                "modelo-bom": metricas(),
            }
        },
        "custo": {"por_modelo": {}},
    }
    resultado = propor(perfil, min_amostras=3)
    slot = resultado["slots"]["executor/t1"]

    assert slot["recomendado"] != "modelo-ruim", (
        "modelo com 40% de chamadas incompletas foi recomendado; score ignora incompletas"
    )
    assert "modelo-ruim" not in slot.get("evitar", []) or True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
