"""Retrieval local simples para contexto RAG em specs do motor."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(texto: str) -> set[str]:
    return {tok for m in TOKEN_RE.finditer(texto) if len(tok := m.group(0).lower()) >= 3}


def carregar_dataset(caminho: str | Path) -> list[dict[str, Any]]:
    """Lê um JSONL de registros RAG.

    Linhas inválidas ou objetos sem ``conteudo`` são ignorados. Caminho ausente
    ou ilegível devolve lista vazia para manter o RAG inerte por falha de dado.
    """
    path = Path(caminho)
    try:
        linhas = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    registros: list[dict[str, Any]] = []
    for linha in linhas:
        if not linha.strip():
            continue
        try:
            bruto = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if not isinstance(bruto, dict):
            continue
        conteudo = bruto.get("conteudo")
        if not isinstance(conteudo, str) or not conteudo.strip():
            continue
        registros.append(bruto)
    return registros


def recuperar(dataset: list[dict[str, Any]], consulta: str, k: int) -> list[dict[str, Any]]:
    """Retorna top-k registros por sobreposição crua de tokens com a consulta."""
    tokens_consulta = _tokens(consulta)
    if not dataset or not tokens_consulta or k <= 0:
        return []

    ranqueados: list[tuple[int, int, dict[str, Any]]] = []
    for indice, registro in enumerate(dataset):
        conteudo = registro.get("conteudo")
        if not isinstance(conteudo, str):
            continue
        score = len(tokens_consulta & _tokens(conteudo))
        if score > 0:
            ranqueados.append((score, -indice, registro))
    ranqueados.sort(reverse=True)
    return [registro for _, _, registro in ranqueados[:k]]
