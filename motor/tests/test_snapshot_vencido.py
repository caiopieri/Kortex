"""Snapshot vencido tem que recusar E dizer o que houve.

A recusa sempre esteve certa: precificar em BRL com câmbio velho torna o teto
ficção. O que estava errado era a mensagem — `ErroOrcamento("snapshot FX stale")`
engolido por um `except Exception` chegava ao operador como "(missão abortada)",
depois de o motor já ter planejado e gasto. Custou um ciclo de debug numa run
real em 2026-07-29.
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest

from motor import grafo, omniroute_orcado
from motor.composicao_orcamento import compor_orcamento_omniroute
from motor.orcamento import ErroOrcamento

CFG = Path(__file__).parents[1] / "exemplos" / "cfg-omniroute.json"
HORA = 3600


def _cfg(**fx: Any) -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(CFG.read_text(encoding="utf-8"))
    dados["fx"].update(fx)
    return dados


def test_mensagem_diz_idade_limite_versao_e_o_que_fazer() -> None:
    agora = 1785345696
    with pytest.raises(ErroOrcamento) as capturado:
        omniroute_orcado.exigir_snapshot_fresco(
            "FX", "awesomeapi-usdbrl-2026-07-28", agora - 26 * HORA, 24 * HORA, agora,
        )
    msg = str(capturado.value)

    assert "26.0h" in msg and "24.0h" in msg
    assert "awesomeapi-usdbrl-2026-07-28" in msg
    # A frase que impede o "conserto" errado: adiantar a data e seguir mantém o
    # número velho, e aí o motor confia num câmbio errado por ter parado de
    # desconfiar.
    assert "adiantar so a data mantem o numero velho" in msg


def test_snapshot_do_futuro_tambem_recusa() -> None:
    with pytest.raises(ErroOrcamento, match="futuro"):
        omniroute_orcado.exigir_snapshot_fresco("FX", "v", 2000, 86400, 1000)


def test_snapshot_dentro_do_prazo_passa() -> None:
    agora = 1785345696
    omniroute_orcado.exigir_snapshot_fresco("FX", "v", agora - 23 * HORA, 24 * HORA, agora)


def test_composicao_recusa_antes_de_planejar(tmp_path, monkeypatch) -> None:
    """Falha na composição, não na primeira chamada de modelo.

    O cliente é construído por chamada, então antes disso o motor já tinha
    planejado e tentado executar três vezes antes de morrer.
    """
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-teste")
    cfg = _cfg(capturado_em=1)

    with pytest.raises(ErroOrcamento, match="snapshot FX vencido"):
        compor_orcamento_omniroute(cfg, tmp_path)


def test_composicao_com_snapshot_fresco_compoe(tmp_path, monkeypatch) -> None:
    """O outro desfecho: sem ele, "recusa sempre" passaria por correção."""
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-teste")
    agora = json.loads(CFG.read_text(encoding="utf-8"))["fx"]["capturado_em"] + 60

    compor_orcamento_omniroute(_cfg(), tmp_path, relogio=lambda: agora)


def test_erro_do_executor_registra_a_causa_no_log_e_nao_no_prompt() -> None:
    """Diagnóstico e prompt têm públicos diferentes.

    O log precisa distinguir "FX vencido" de "credencial ausente" de "upstream
    fora do ar" — antes eram a mesma frase fixa. O prompt do modelo, não: mandar
    exceção crua para dentro dele entrega detalhe interno a quem só precisa saber
    que falhou.
    """
    fonte = inspect.getsource(grafo.construir_grafo)
    trecho = fonte[fonte.index('feedback = "falha externa do executor"'):]
    trecho = trecho[:400]

    assert 'motivo=f"{feedback}: {type(erro).__name__}: {erro}"' in trecho
    # Dentro do bloco, `feedback` -- o que vai para o prompt -- continua literal.
    assert "\n                feedback = f" not in trecho


def test_env_do_teste_nao_vaza(monkeypatch) -> None:
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    assert os.environ.get("OMNIROUTE_API_KEY") is None
