"""Issues #22 e #23 — a superfície declara o que não sabe, e não fabrica o que não tem.

#22: o ledger não era durável. Numa medição sobre o checkout de produção havia
29 workspaces de run em disco com 26 explicados, e 49 artefatos de produto com 40
cobertos por evento. Uma tela que lista só o que o ledger explica é silenciosamente incompleta.
A correção é declarar o resto **como resto** — nunca reconstruí-lo a partir do
diretório, porque "existe por estar no ledger ou numa spec" é a regra canônica.

#23: o painel fabricava catálogo. Aqui fica travada a metade de servidor: versão
que ninguém declarou não vira "1.0.0".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from motor_painel.painel import (  # noqa: E402
    _chave_de_artefato,
    obter_catalogo,
    orfaos_de_artefato,
)


def _run_com_artefato(raiz: Path, run_id: str, nome: str) -> Path:
    pasta = raiz / run_id / "artefatos"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / nome
    arquivo.write_text("conteudo", encoding="utf-8")
    return arquivo


def _evento(caminho: Path, nome: str = "x.py") -> dict:
    return {
        "t": 0.1,
        "seq": 1,
        "evento": "artefato.atualizou",
        "nome": nome,
        "tipo": "python",
        "subagente": "codificador",
        "caminho": str(caminho),
    }


# ---------------------------------------------------------------------------
# #22 — órfão é contado, e continua órfão
# ---------------------------------------------------------------------------


def test_artefato_sem_evento_conta_como_orfao(tmp_path):
    """O caso causal: arquivo em disco, ledger silencioso."""
    _run_com_artefato(tmp_path, "run-a", "solucao.py")

    resumo = orfaos_de_artefato([], tmp_path)

    assert resumo["artefatos_em_disco"] == 1
    assert resumo["artefatos_orfaos"] == 1
    assert resumo["artefatos_com_evento"] == 0
    assert resumo["amostra"] == ["run-a/artefatos/solucao.py"]


def test_orfao_nao_ganha_run_tipo_nem_tempo_derivados(tmp_path):
    """Não reconstruir o passado: o órfão sai como caminho e nada mais.

    O diretório *sugere* run e extensão sugere tipo — e é exatamente essa
    inferência que a regra proíbe. Se algum dia a amostra virar objeto com
    `run`/`tipo`, este teste cai.
    """
    _run_com_artefato(tmp_path, "run-a", "modelo.stl")

    resumo = orfaos_de_artefato([], tmp_path)

    assert all(isinstance(item, str) for item in resumo["amostra"])
    assert "tipo" not in json.dumps(resumo["amostra"])


def test_artefato_com_evento_nao_e_orfao(tmp_path):
    arquivo = _run_com_artefato(tmp_path, "run-a", "solucao.py")

    resumo = orfaos_de_artefato([_evento(arquivo)], tmp_path)

    assert resumo["artefatos_em_disco"] == 1
    assert resumo["artefatos_orfaos"] == 0
    assert resumo["artefatos_com_evento"] == 1


def test_evento_de_outro_checkout_ainda_casa_com_o_arquivo(tmp_path):
    """A identidade é ``<run_id>/artefatos/<resto>``, nunca o caminho absoluto.

    O `caminho` gravado no evento aponta para o checkout onde a run rodou. Se a
    comparação fosse por absoluto, clonar o repositório noutro diretório faria
    **todo** artefato virar órfão de uma vez — um alarme de 100% que não
    significa nada. Trocar `_chave_de_artefato` por comparação de path absoluto
    derruba este teste.
    """
    arquivo = _run_com_artefato(tmp_path, "run-a", "solucao.py")
    evento = _evento(Path("/outra/maquina/motor/runs/run-a/artefatos/solucao.py"))

    resumo = orfaos_de_artefato([evento], tmp_path)

    assert arquivo.exists()
    assert resumo["artefatos_orfaos"] == 0


def test_debris_de_ferramenta_nao_conta_como_artefato(tmp_path):
    """__pycache__ dentro de artefatos/ não é produto da fábrica.

    Na medição real eram 109 arquivos de ferramenta contra 49 de produto:
    contá-los infla o número de órfãos até ele não querer dizer nada.
    """
    _run_com_artefato(tmp_path, "run-a", "solucao.py")
    cache = tmp_path / "run-a" / "artefatos" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "solucao.cpython-313.pyc").write_bytes(b"\x00")

    resumo = orfaos_de_artefato([], tmp_path)

    assert resumo["artefatos_em_disco"] == 1
    assert resumo["arquivos_de_ferramenta_ignorados"] == 1


def test_run_com_artefato_e_sem_log_e_declarada_orfa(tmp_path):
    _run_com_artefato(tmp_path, "run-muda", "saida.md")
    com_log = tmp_path / "run-falante"
    com_log.mkdir()
    (com_log / "log.jsonl").write_text("", encoding="utf-8")

    resumo = orfaos_de_artefato([], tmp_path)

    assert resumo["runs_em_disco"] == 2
    assert resumo["runs_explicadas"] == 1
    assert resumo["runs_orfas"] == ["run-muda"]


def test_pasta_que_nao_e_run_nao_vira_run_orfa(tmp_path):
    """Nem toda pasta sob runs/ e uma run.

    Medido em producao: `caixa`, `despachos`, `orcamento` e `lift-docs-*` moram
    sob runs/ e sao outra coisa — sem log e sem artefatos/. Conta-las inflava a
    contagem de 3 para 8 runs orfas, o que e inventar run a partir de nome de
    diretorio: o espelho do defeito que esta funcao corrige.
    """
    (tmp_path / "caixa").mkdir()
    (tmp_path / "caixa" / "decidida.md").write_text("x", encoding="utf-8")
    (tmp_path / "despachos").mkdir()
    _run_com_artefato(tmp_path, "run-de-verdade", "saida.md")

    resumo = orfaos_de_artefato([], tmp_path)

    assert resumo["runs_em_disco"] == 1
    assert resumo["runs_orfas"] == ["run-de-verdade"]


def test_workspace_inexistente_nao_inventa_alarme(tmp_path):
    resumo = orfaos_de_artefato([], tmp_path / "nao-existe")

    assert resumo["artefatos_orfaos"] == 0
    assert resumo["runs_em_disco"] == 0
    assert resumo["runs_orfas"] == []


def test_amostra_truncada_declara_que_truncou(tmp_path):
    """Truncar em silêncio faria a tela mentir por omissão."""
    for i in range(55):
        _run_com_artefato(tmp_path, "run-a", f"arq-{i:03d}.py")

    resumo = orfaos_de_artefato([], tmp_path)

    assert resumo["artefatos_orfaos"] == 55
    assert len(resumo["amostra"]) == 50
    assert resumo["amostra_truncada"] is True


def test_chave_de_artefato_recusa_caminho_sem_pasta_artefatos():
    assert _chave_de_artefato("/tmp/solto.py") is None
    assert _chave_de_artefato("artefatos/solto.py") is None
    assert _chave_de_artefato("runs/r1/artefatos/a/b.py") == ("r1", "a/b.py")


# ---------------------------------------------------------------------------
# #23 — o servidor não inventa versão
# ---------------------------------------------------------------------------


def test_catalogo_nao_inventa_versao_ausente(tmp_path, monkeypatch):
    """Nenhum arquivo do registro declara `versao`. Antes saía "1.0.0"."""
    registro = tmp_path / "registro"
    registro.mkdir()
    (registro / "rota.md").write_text(
        "---\ntipo: rota\nnome: construcao\npadrao: grafo_dependencias\n---\nDescricao.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("motor_painel.painel._pasta_registro", lambda: registro)

    catalogo = obter_catalogo()

    assert len(catalogo) == 1
    assert catalogo[0]["versao"] is None


def test_catalogo_preserva_versao_quando_declarada(tmp_path, monkeypatch):
    registro = tmp_path / "registro"
    registro.mkdir()
    (registro / "rota.md").write_text(
        "---\ntipo: rota\nnome: construcao\nversao: '2.1'\n---\nDescricao.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("motor_painel.painel._pasta_registro", lambda: registro)

    assert obter_catalogo()[0]["versao"] == "2.1"


def test_registro_vazio_produz_catalogo_vazio(tmp_path, monkeypatch):
    """Sem fonte, lista vazia — nunca conteúdo de exemplo (issue #23)."""
    registro = tmp_path / "registro"
    registro.mkdir()
    monkeypatch.setattr("motor_painel.painel._pasta_registro", lambda: registro)

    assert obter_catalogo() == []
