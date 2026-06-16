from __future__ import annotations

import json
from pathlib import Path

import pytest

from motor.modelos import ClienteClaudeCLI, cliente_de_config
from motor.registro import cliente_de_registro


RAIZ = Path(__file__).parent.parent


def _provedores(cliente):
    sondas = [
        ("pesquisador", None),
        ("qualquer", "simples"),
        ("qualquer", "media"),
        ("qualquer", "complexa"),
        ("synthesizer", None),
    ]
    return [cliente.provedor_de(papel, tier) for papel, tier in sondas]


def test_registro_equivale_ao_modelos_codex_json():
    cfg = json.loads((RAIZ / "exemplos/modelos-codex.json").read_text(encoding="utf-8"))
    por_json = cliente_de_config(cfg)
    por_registro = cliente_de_registro(RAIZ / "exemplos/registro-modelos")
    assert _provedores(por_registro) == _provedores(por_json)


def test_registro_conflito_de_tier_falha(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\n"
        "tipo: modelo-executor\n"
        "transporte: codex\n"
        "tiers: [simples]\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text(
        "---\n"
        "tipo: modelo-executor\n"
        "transporte: opencode\n"
        "modelo: openai/gpt-5.5\n"
        "tiers: [simples]\n"
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="a.md.*b.md"):
        cliente_de_registro(tmp_path)


def test_registro_multiplos_padroes_falha(tmp_path):
    for nome in ["a.md", "b.md"]:
        (tmp_path / nome).write_text(
            "---\n"
            "tipo: modelo-executor\n"
            "transporte: claude-cli\n"
            "padrao: true\n"
            "---\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="mais de uma entidade padrão"):
        cliente_de_registro(tmp_path)


def test_registro_sem_padrao_cai_no_claude(tmp_path):
    (tmp_path / "codex.md").write_text(
        "---\n"
        "tipo: modelo-executor\n"
        "transporte: codex\n"
        "tiers: [simples]\n"
        "---\n",
        encoding="utf-8",
    )
    r = cliente_de_registro(tmp_path)
    assert isinstance(r.padrao, ClienteClaudeCLI)
    assert r.provedor_de("qualquer", None) == "claude"


def test_registro_ignora_arquivo_sem_tipo(tmp_path):
    (tmp_path / "_indice.md").write_text(
        "---\n"
        "titulo: índice\n"
        "---\n",
        encoding="utf-8",
    )
    r = cliente_de_registro(tmp_path)
    assert r.mapa == {}
    assert r.tiers == {}
    assert r.cadeia == []


def test_registro_openai_compat_sem_env_falha(tmp_path, monkeypatch):
    monkeypatch.delenv("CHAVE_AUSENTE", raising=False)
    (tmp_path / "barato.md").write_text(
        "---\n"
        "tipo: modelo-executor\n"
        "transporte: openai-compat\n"
        "provedor: nvidia\n"
        "modelo: deepseek-ai/deepseek-v4\n"
        "base_url: https://integrate.api.nvidia.com/v1\n"
        "api_key_env: CHAVE_AUSENTE\n"
        "papeis: [redator]\n"
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exporte a chave; ela nunca vai no arquivo"):
        cliente_de_registro(tmp_path)


def test_registro_monta_catalogo_de_capacidades(tmp_path):
    (tmp_path / "codex.md").write_text(
        "---\n"
        "tipo: modelo-executor\n"
        "transporte: codex\n"
        "capacidades: [codigo, ferramentas]\n"
        "custo_ordem: 3\n"
        "---\n",
        encoding="utf-8",
    )

    r = cliente_de_registro(tmp_path)

    assert len(r.catalogo) == 1
    cliente, capacidades, custo = r.catalogo[0]
    assert getattr(cliente, "provedor", None) == "codex"
    assert capacidades == frozenset({"codigo", "ferramentas"})
    assert custo == 3
