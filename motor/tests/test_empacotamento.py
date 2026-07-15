from pathlib import Path


RAIZ = Path(__file__).parents[1]
ARTEFATOS_SDIST = {
    "tests/audit_corpus.py",
    "tests/runner_fake.py",
    "tools/validar_manifest_reprodutores.py",
    "specs/001-hardening-producao/invariant-matrix.jsonl",
    "specs/001-hardening-producao/reproducer-manifest.jsonl",
    "specs/001-hardening-producao/reproducer-corpus-1655f6059e06c318.tar",
}


def test_sdist_inclui_dependencias_dos_packs_de_hardening() -> None:
    declarados = {
        linha.removeprefix("include ")
        for linha in (RAIZ / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
        if linha.startswith("include ")
    }

    assert ARTEFATOS_SDIST <= declarados
    assert all((RAIZ / caminho).is_file() for caminho in ARTEFATOS_SDIST)
