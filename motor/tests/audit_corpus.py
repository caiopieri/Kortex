from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Sequence
from xml.etree import ElementTree

MOTOR = Path(__file__).parents[1]
SPEC = MOTOR / "specs/001-hardening-producao"
MANIFEST = SPEC / "reproducer-manifest.jsonl"
CORPUS = SPEC / "reproducer-corpus-60d4f4002e35f55b.tar"
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


def executar_lote(
    corpus: Path, nodeids: Sequence[str], plugins: tuple[str, ...] = (),
) -> dict[str, str | None]:
    """Roda TODOS os casos de um dono num subprocesso só; devolve nodeid → falha.

    Um subprocesso por caso custava ~4,7s cada, e quase tudo era arranque de
    interpretador mais import de langchain/langgraph -- o trabalho útil é de
    milissegundos. Com 99 casos, isso sozinho passava de 460s e estourou o
    orçamento de 5 minutos do gate determinista da carta.

    O lote paga o arranque UMA vez por dono e continua atribuindo falha por
    caso, lendo o JUnit XML em vez de interpretar o texto do pytest -- que muda
    de formato entre versões e é péssimo para casar veredito com nodeid.

    Semanticamente, rodar os casos de um dono juntos é a condição NATURAL deles:
    eles vieram do mesmo arquivo de auditoria e sempre rodaram no mesmo processo
    lá. O que se perde é o isolamento de interpretador entre casos, que nunca foi
    parte do que estes reprodutores provam.
    """
    env = {**os.environ, "PYTHONPATH": str(MOTOR)}
    plugin_args = [arg for plugin in plugins for arg in ("-p", plugin)]
    relatorio = corpus / "_lote-junit.xml"
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short",
         f"--junit-xml={relatorio}", *plugin_args, *nodeids],
        cwd=corpus, env=env, capture_output=True, text=True,
        timeout=30 + 10 * len(nodeids), check=False,
    )
    if not relatorio.exists():
        # Sem relatório não dá para atribuir nada; falhar TODOS é o certo --
        # tratar como sucesso transformaria erro de coleta em gate verde.
        saida = resultado.stdout + resultado.stderr
        return {nodeid: f"lote nao produziu relatorio:\n{saida}" for nodeid in nodeids}

    falhas: dict[str, str | None] = {nodeid: None for nodeid in nodeids}
    vistos: set[str] = set()
    raiz = ElementTree.parse(relatorio).getroot()
    for caso in raiz.iter("testcase"):
        problema = next(
            (filho for filho in caso if filho.tag in {"failure", "error"}), None,
        )
        alvos = [
            n for n in nodeids
            if _mesmo_caso(n, str(caso.get("classname") or ""),
                           str(caso.get("name") or ""))
        ]
        for alvo in alvos:
            vistos.add(alvo)
            if problema is not None:
                falhas[alvo] = (problema.get("message") or "") + "\n" + (problema.text or "")
    for nodeid in nodeids:
        if nodeid not in vistos:
            # Caso que sumiu do corpus é regressão do manifesto, não aprovação.
            falhas[nodeid] = "caso nao foi coletado pelo lote"
    return falhas


def _mesmo_caso(nodeid_manifesto: str, classname: str, nome: str) -> bool:
    """Casa nodeid do manifesto com a identidade que o JUnit realmente emite.

    O atributo `file` vem VAZIO; quem carrega a identidade é `classname`, no
    formato de módulo pontilhado (`tests.test_auditoria_gpt5_f`) — e, para teste
    dentro de classe, com a classe no fim. Daí a comparação ser por segmento, e
    não por caminho.
    """
    arquivo, _, nome_manifesto = nodeid_manifesto.partition("::")
    # `nodeid` de teste em classe vem "arquivo::Classe::teste"; o JUnit junta a
    # classe no classname, então só o último segmento é o nome do caso.
    nome_manifesto = nome_manifesto.rpartition("::")[2]
    modulo = Path(arquivo).stem
    return nome_manifesto == nome and modulo in classname.split(".")
