from pathlib import Path


RAIZ = Path(__file__).parents[1]
ARTEFATOS_SDIST = {
    "tests/audit_corpus.py",
    "tests/helpers_grafo.py",
    "tests/runner_fake.py",
    "tools/validar_manifest_reprodutores.py",
    "motor_painel/painel.html",
    "specs/001-hardening-producao/invariant-matrix.jsonl",
    "specs/001-hardening-producao/reproducer-manifest.jsonl",
    "specs/001-hardening-producao/reproducer-corpus-60d4f4002e35f55b.tar",
}


def test_sdist_inclui_dependencias_dos_packs_de_hardening() -> None:
    linhas = (RAIZ / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    declarados = {
        linha.removeprefix("include ")
        for linha in linhas
        if linha.startswith("include ")
    }

    assert ARTEFATOS_SDIST <= declarados
    assert all((RAIZ / caminho).is_file() for caminho in ARTEFATOS_SDIST)
    assert "recursive-include exemplos *.json *.jsonl *.md" in linhas
    assert "recursive-include scripts *.py" in linhas
    assert 'motor_painel = ["*.html"]' in (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
