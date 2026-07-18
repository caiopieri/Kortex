from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

MOTOR = Path(__file__).parents[1]
SPEC = MOTOR / "specs/001-hardening-producao"
MANIFEST = SPEC / "reproducer-manifest.jsonl"
CORPUS = SPEC / "reproducer-corpus-20f270dc95646f01.tar"
LANDING_DISPOSITIONS = {"accepted", "duplicate", "retain_control"}


def casos(owner: str) -> list[str]:
    rows = map(json.loads, MANIFEST.read_text(encoding="utf-8").splitlines())
    return [
        row["nodeid"]
        for row in rows
        if (
            row["owner"] == owner
            and row["landing"] == "owner_pr"
            and row["disposition"] in LANDING_DISPOSITIONS
        )
    ]


def materializar_corpus(destino: Path) -> Path:
    with tarfile.open(CORPUS, "r:") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            assert member.isfile() and not path.is_absolute() and ".." not in path.parts
            source = archive.extractfile(member)
            assert source is not None
            target = Path(destino, *path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
    return destino


def executar_caso(corpus: Path, nodeid: str, plugins: tuple[str, ...] = ()) -> None:
    env = {**os.environ, "PYTHONPATH": str(MOTOR)}
    plugin_args = [arg for plugin in plugins for arg in ("-p", plugin)]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *plugin_args, nodeid],
        cwd=corpus,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
