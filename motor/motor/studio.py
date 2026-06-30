"""Ponto de entrada pro LangGraph Studio (`langgraph dev`).

O Studio é a UI oficial do LangGraph: visualiza o grafo, o estado, os interrupts
(caixa do fundador) e o trace de cada run — de graça, porque o motor JÁ é um grafo
LangGraph. Aqui só montamos o grafo com as dependências reais (cliente + log +
política) e devolvemos COMPILADO SEM checkpointer — o servidor do Studio injeta a
persistência dele (não passe o seu).

Config de modelos: lê exemplos/modelos-codex.json (Codex executor + Claude
julgamento + tiers). Troque o arquivo se quiser outro roteamento.
"""
from __future__ import annotations

import json
from pathlib import Path

from .grafo import construir_grafo
from .modelos import ClienteClaudeCLI, cliente_de_config
from .politica import politica_de_config

_RAIZ = Path(__file__).parent.parent
_CFG = _RAIZ / "exemplos" / "modelos-codex.json"
_CFG_DADOS = json.loads(_CFG.read_text(encoding="utf-8")) if _CFG.exists() else None


class _LogStudio:
    """Log no-op para evitar I/O síncrono no event loop do LangGraph Studio."""

    def evento(self, tipo: str, **dados) -> None:
        return None

    def fechar(self) -> None:
        return None


def make_graph():
    """Factory chamada pelo servidor do Studio. Sem checkpointer — o Studio põe o dele."""
    log = _LogStudio()
    if _CFG_DADOS is not None:
        cliente = cliente_de_config(_CFG_DADOS, log=log)
        politica = politica_de_config(_CFG_DADOS.get("politica_gates"))
    else:  # fallback: tudo no claude, política manual
        cliente, politica = ClienteClaudeCLI(log=log), politica_de_config(None)
    return construir_grafo(cliente, log, checkpointer=None, politica=politica)
