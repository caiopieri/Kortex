"""Loader de modelos-executores a partir do Registry.

R1 troca a fonte do catálogo (JSON escrito à mão -> entidades `.md`) sem mudar a
fronteira do motor: quem chama recebe um ClienteRoteador pronto.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Optional

from .modelos import (
    ClienteClaudeCLI,
    ClienteCodex,
    ClienteOpenAICompat,
    ClienteOpenCode,
    ClienteRoteador,
)


def _valor_frontmatter(valor: str) -> Any:
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in {"'", '"'}:
        return valor[1:-1]
    if valor in {"true", "false"}:
        return valor == "true"
    if valor.startswith("[") and valor.endswith("]"):
        try:
            return json.loads(valor)
        except json.JSONDecodeError:
            pass
        miolo = valor[1:-1].strip()
        if not miolo:
            return []
        return [_valor_frontmatter(item.strip()) for item in miolo.split(",")]
    try:
        return int(valor)
    except ValueError:
        return valor


def _frontmatter(caminho: Path) -> dict[str, Any]:
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    if not linhas or linhas[0].strip() != "---":
        return {}
    fim = next((i for i, linha in enumerate(linhas[1:], start=1) if linha.strip() == "---"), None)
    if fim is None:
        return {}

    dados: dict[str, Any] = {}
    for linha in linhas[1:fim]:
        linha = linha.strip()
        if not linha:
            continue
        chave, sep, valor = linha.partition(":")
        if not sep:
            continue
        dados[chave.strip()] = _valor_frontmatter(valor)
    return dados


def _lista(valor: Any) -> list[str]:
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(item) for item in valor]
    return [str(valor)]


def _modelo(valor: Any) -> Optional[str]:
    if valor in {None, "", "default"}:
        return None
    return str(valor)


def _chave(env: str, quem: str) -> str:
    chave = os.environ.get(env, "")
    if not chave:
        raise ValueError(
            f"env var {env!r} vazia ({quem}) — exporte a chave; ela nunca vai no arquivo")
    return chave


def _cliente_entidade(entidade: dict[str, Any], log: Optional[Any], padrao: ClienteClaudeCLI):
    transporte = entidade.get("transporte")
    modelo = _modelo(entidade.get("modelo"))
    provedor = str(entidade.get("provedor") or transporte)

    if entidade.get("padrao") is True:
        if transporte != "claude-cli":
            raise ValueError("padrao: true só é válido com transporte claude-cli")
        return padrao
    if transporte == "claude-cli":
        return ClienteClaudeCLI(log=log)
    if transporte == "codex":
        return ClienteCodex(modelo=modelo, sandbox=str(entidade.get("sandbox") or "read-only"),
                            busca_ao_vivo=bool(entidade.get("search", False)), log=log)
    if transporte == "opencode":
        return ClienteOpenCode(modelo=modelo, permissao=entidade.get("permissao"),
                               log=log, provedor=provedor)
    if transporte == "openai-compat":
        base_url = entidade.get("base_url")
        api_key_env = entidade.get("api_key_env")
        if not base_url or not api_key_env:
            raise ValueError("openai-compat exige base_url e api_key_env")
        return ClienteOpenAICompat(base_url=str(base_url),
                                   api_key=_chave(str(api_key_env), f"provedor {provedor!r}"),
                                   modelo=modelo or "default", log=log, provedor=provedor)
    raise ValueError(
        f"transporte {transporte!r} desconhecido (use 'codex', 'opencode', "
        "'openai-compat' ou 'claude-cli')")


def cliente_de_registro(pasta: str | Path, log: Optional[Any] = None) -> ClienteRoteador:
    """Monta ClienteRoteador a partir de entidades `.md` do Registry."""
    raiz = Path(pasta)
    entidades: list[tuple[Path, dict[str, Any]]] = []
    for caminho in sorted(raiz.glob("*.md"), key=lambda p: p.name):
        dados = _frontmatter(caminho)
        if dados.get("tipo") != "modelo-executor":
            continue
        entidades.append((caminho, dados))

    padroes = [(c, e) for c, e in entidades if e.get("padrao") is True]
    if len(padroes) > 1:
        nomes = ", ".join(c.name for c, _ in padroes)
        raise ValueError(f"mais de uma entidade padrão no Registry: {nomes}")
    padrao = ClienteClaudeCLI(log=log)

    clientes: list[tuple[Path, Any, dict[str, Any]]] = [
        (caminho, _cliente_entidade(entidade, log, padrao), entidade)
        for caminho, entidade in entidades
    ]

    mapa: dict[str, Any] = {}
    tiers: dict[str, Any] = {}
    catalogo: list[tuple[Any, frozenset[str], int]] = []
    dono_papel: dict[str, str] = {}
    dono_tier: dict[str, str] = {}
    for caminho, cliente, entidade in clientes:
        for papel in _lista(entidade.get("papeis")):
            if papel in mapa:
                raise ValueError(
                    f"papel {papel!r} reivindicado por {dono_papel[papel]} e {caminho.name}")
            mapa[papel] = cliente
            dono_papel[papel] = caminho.name
        for tier in _lista(entidade.get("tiers")):
            if tier in tiers:
                raise ValueError(
                    f"tier {tier!r} reivindicado por {dono_tier[tier]} e {caminho.name}")
            tiers[tier] = cliente
            dono_tier[tier] = caminho.name
        capacidades = _lista(entidade.get("capacidades"))
        if capacidades:
            catalogo.append((cliente, frozenset(capacidades), int(entidade.get("custo_ordem") or 0)))

    cadeia: list[Any] = []
    for _, cliente, _ in clientes:
        if cliente is not padrao and not any(cliente is existente for existente in cadeia):
            cadeia.append(cliente)

    return ClienteRoteador(padrao=padrao, mapa=mapa, tiers=tiers, cadeia=cadeia,
                           catalogo=catalogo, log=log)


def ferramentas_de_registro(pasta: str | Path) -> dict[str, dict[str, Any]]:
    """Carrega entidades `tipo: ferramenta` do Registry, indexadas pelo nome lógico."""
    raiz = Path(pasta)
    ferramentas: dict[str, dict[str, Any]] = {}
    dono: dict[str, str] = {}
    for caminho in sorted(raiz.glob("*.md"), key=lambda p: p.name):
        dados = _frontmatter(caminho)
        if dados.get("tipo") != "ferramenta":
            continue
        nome = str(dados.get("nome") or "").strip()
        if not nome:
            raise ValueError(f"ferramenta sem nome em {caminho.name}")
        if nome in ferramentas:
            raise ValueError(f"ferramenta {nome!r} duplicada em {dono[nome]} e {caminho.name}")
        ferramentas[nome] = dados
        dono[nome] = caminho.name
    return ferramentas
