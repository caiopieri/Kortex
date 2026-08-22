"""Regressions da issue #29: baldes legados e logs sem eventos."""
from __future__ import annotations

from pathlib import Path

from motor_painel.painel import _runs_do_workspace, dados_painel, obter_runs, parse_eventos


REPO = Path(__file__).parent.parent
LEDGER_LEGADO_REAL = REPO / "exemplos" / "log-legado-10-runs.jsonl"


def test_ledger_real_com_dez_runs_nao_fabrica_um_resumo_unico() -> None:
    eventos = parse_eventos(LEDGER_LEGADO_REAL)

    resumo = next(
        run for run in obter_runs(eventos) if run["id"] == "legado:sem-proveniencia"
    )
    assert resumo["runs_contidas"] == 10
    assert resumo["missao"] is None
    assert resumo["estado"] is None
    assert resumo["inicio"] is None

    canonica = next(
        run
        for run in dados_painel(LEDGER_LEGADO_REAL)["runs"]
        if run["id"] == "legado:sem-proveniencia"
    )
    assert canonica["runs_contidas"] == 10
    assert canonica["missao"] is None
    assert canonica["desfecho"] is None
    assert canonica["motivoDoFim"] is None


def test_log_vazio_nao_e_reportado_como_run_ativa(tmp_path: Path) -> None:
    # Fixture sintética declarada: a medição local não tinha uma run real vazia;
    # os logs vazios observados eram resíduos de testes, não uma missão abortada.
    runs = tmp_path / "runs"
    (runs / "run-vazia" / "log.jsonl").parent.mkdir(parents=True)
    (runs / "run-vazia" / "log.jsonl").write_bytes(b"")

    registros = _runs_do_workspace(runs)

    assert len(registros) == 1
    assert registros[0]["run"]["id"] == "run-vazia"
    assert registros[0]["run"]["estado"] is None
    assert registros[0]["run"]["inicio"] is None
    assert registros[0]["run"]["n_eventos"] == 0
