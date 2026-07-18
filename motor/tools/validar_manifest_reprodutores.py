"""Valida o inventario H00 sem executar os reprodutores vermelhos."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

MOTOR = Path(__file__).resolve().parents[1]
SPEC = MOTOR / "specs/001-hardening-producao"
MANIFEST = SPEC / "reproducer-manifest.jsonl"
MATRIX = SPEC / "invariant-matrix.jsonl"
CORPUS = SPEC / "reproducer-corpus-0bdbb677dd281edc.tar"
REQUIRED = {
    "nodeid", "file_sha256", "corpus_member", "origin", "baseline", "invariant",
    "cause", "owner", "disposition", "disposition_by", "disposition_reason", "landing",
}
INVARIANTS = {
    "K1", "K2", "K3", "K4", "S1", "S2", "S3", "S4", "G1", "G2", "G3", "G4",
    "C1", "C2", "C3", "C4", "E1", "E2", "U1", "U2", "U3", "F1", "F2", "F3",
}
OWNER = re.compile(r"H(?:0[0-9]|1[0-3])(?:[ab])?\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DISPOSITION_LANDING = {
    ("accepted", "owner_pr"),
    ("duplicate", "owner_pr"),
    ("retain_control", "owner_pr"),
    ("rejected_contract", "not_landed"),
    ("oracle_migrated", "replacement_test"),
}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validar() -> list[str]:
    erros: list[str] = []
    rows = _jsonl(MANIFEST)
    matrix = _jsonl(MATRIX)
    nodeids = [str(row.get("nodeid", "")) for row in rows]
    erros += [f"linha {i}: campos ausentes {sorted(REQUIRED - row.keys())}" for i, row in enumerate(rows, 1) if REQUIRED - row.keys()]
    lanes = Counter((row.get("origin"), row.get("baseline")) for row in rows)
    esperado = {
        ("gpt5-audit", "failure"): 78,
        ("gpt5-audit", "control"): 11,
        ("codex-preexisting", "failure"): 22,
    }
    if lanes != esperado:
        erros.append("particao deve ser exatamente 78 failures + 11 controls GPT5 e 22 failures Codex")
    if len(nodeids) != len(set(nodeids)):
        erros.append("nodeid duplicado")
    for row in rows:
        if not SHA256.fullmatch(str(row.get("file_sha256", ""))):
            erros.append(f"hash invalido: {row.get('nodeid')}")
        if not OWNER.fullmatch(str(row.get("owner", ""))):
            erros.append(f"owner invalido: {row.get('nodeid')}")
        if row.get("invariant") not in INVARIANTS:
            erros.append(f"invariante invalido: {row.get('nodeid')}")
        if str(row.get("nodeid", "")).split("::", 1)[0] != row.get("corpus_member"):
            erros.append(f"nodeid nao pertence ao membro: {row.get('nodeid')}")
        if row.get("origin") == "codex-preexisting" and "mantenedor humano" not in str(row.get("disposition_by")):
            erros.append(f"disposicao Codex sem aprovador humano: {row.get('nodeid')}")
        par_disposicao = (row.get("disposition"), row.get("landing"))
        if par_disposicao not in DISPOSITION_LANDING:
            erros.append(f"disposicao/landing invalidos: {row.get('nodeid')}")
        if row.get("disposition") == "oracle_migrated":
            replacement = str(row.get("replacement_nodeid", ""))
            arquivo, separador, teste = replacement.partition("::")
            alvo = MOTOR / arquivo
            nome_teste = teste.split("[", 1)[0]
            if (
                not separador
                or replacement == row.get("nodeid")
                or not alvo.is_file()
                or f"def {nome_teste}(" not in alvo.read_text(encoding="utf-8")
            ):
                erros.append(f"oraculo migrado sem regressao substituta: {row.get('nodeid')}")

    matrix_ids = {str(row.get("invariant")) for row in matrix}
    if len(matrix) != 24 or matrix_ids != INVARIANTS:
        erros.append("matriz deve cobrir uma vez cada um dos 24 invariantes")
    for row in matrix:
        if not row.get("owners") or any(not OWNER.fullmatch(str(owner)) for owner in row["owners"]):
            erros.append(f"ownership invalido na matriz: {row.get('invariant')}")

    corpus_hash = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if corpus_hash[:16] not in CORPUS.name:
        erros.append("nome content-addressed diverge do hash do corpus")
    with tarfile.open(CORPUS, "r:") as archive, tempfile.TemporaryDirectory() as temp:
        members = archive.getmembers()
        referenced = {str(row.get("corpus_member")) for row in rows}
        if {member.name for member in members} != referenced:
            erros.append("membros do corpus divergem do manifest")
        for member in members:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or path.parts[:1] != ("tests",):
                erros.append(f"membro inseguro no corpus: {member.name}")
                continue
            content = archive.extractfile(member)
            assert content is not None
            data = content.read()
            expected = {str(row["file_sha256"]) for row in rows if row["corpus_member"] == member.name}
            if expected != {hashlib.sha256(data).hexdigest()}:
                erros.append(f"hash divergente: {member.name}")
            target = Path(temp, *path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        env = {**os.environ, "PYTHONPATH": str(MOTOR)}
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", *sorted(referenced)],
            cwd=temp, env=env, capture_output=True, text=True, check=False,
        )
        collected = {line for line in result.stdout.splitlines() if line.startswith("tests/") and "::" in line}
        if result.returncode or collected != set(nodeids):
            erros.append("nodeids coletados do corpus divergem do manifest")
    return erros


if __name__ == "__main__":
    problemas = validar()
    if problemas:
        print("\n".join(problemas), file=sys.stderr)
        raise SystemExit(1)
    print("manifest H00 valido: 100 failures, 11 controls, 24 invariantes")
