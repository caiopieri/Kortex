"""A chave do artefato é a MESMA nos dois lados, ou disco e ledger divergem.

`painel.py::_chave_de_artefato` decide o que é órfão (issue #22, medido: 9 de 49
artefatos em disco sem evento). `estante.js::chaveRelativa` decide o que é um
cartão da estante. Se as duas derivarem chaves diferentes para o mesmo caminho,
a tela lista um artefato que o servidor conta como órfão — ou o contrário — e
nada falha: os dois números continuam internamente consistentes e discordam.

Irmão do `test_issue15_grafo_canonico` e do `test_3d_mesma_topologia`: mesma
regra, duas linguagens, um teste que roda as duas.

A chave é RELATIVA (``<run_id>/<resto>`` a partir de ``artefatos/``) e nunca o
caminho absoluto, porque o ``caminho`` do evento aponta para o checkout onde a
run rodou: comparar por absoluto faria todo artefato virar órfão ao clonar o
repositório noutro diretório.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from motor_painel.painel import _chave_de_artefato

RAIZ = Path(__file__).parents[1].parent
MODULO = "./motor/motor_painel/app/src/pages/estanteDoLedger.js"

CAMINHOS = [
    # o caso normal, e o mesmo artefato em duas máquinas
    "/Users/x/Kortex/motor/runs/r1/artefatos/codificador__ebay.py",
    "/home/cap/Kortex/motor/runs/r1/artefatos/codificador__ebay.py",
    # subdiretório dentro de artefatos/
    "/x/runs/r1/artefatos/a/b.py",
    # recusas
    "/tmp/solto.py",
    "artefatos/solto.py",
    "/x/runs/r1/artefatos",
    # lixo de ferramenta: não é produto da fábrica
    "/x/runs/r1/artefatos/__pycache__/a.cpython-313.pyc",
    "/x/runs/r1/artefatos/.pytest_cache/v/cache",
    # nome de run que parece caminho
    "/x/runs/20260623-120814-29c0d6/artefatos/subagente-1__boas_praticas",
]


def _do_javascript(caminhos: list[str]) -> list[str | None]:
    script = f"""
import fs from 'node:fs';
import {{ chaveRelativa }} from '{MODULO}';
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(entrada.map(chaveRelativa)));
"""
    saida = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(caminhos),
        text=True,
        capture_output=True,
        check=True,
        cwd=RAIZ,
    )
    return json.loads(saida.stdout)


def _do_python(caminho: str) -> str | None:
    chave = _chave_de_artefato(caminho)
    return f"{chave[0]}/{chave[1]}" if chave else None


def test_as_duas_linguagens_derivam_a_mesma_chave() -> None:
    do_js = _do_javascript(CAMINHOS)
    do_py = [_do_python(c) for c in CAMINHOS]

    assert do_js == do_py, "\n".join(
        f"  {c}\n    js={j!r}\n    py={p!r}"
        for c, j, p in zip(CAMINHOS, do_js, do_py)
        if j != p
    )


def test_a_chave_e_relativa_nos_dois_lados() -> None:
    """O caso que motiva o arquivo: dois checkouts, uma chave."""
    mac = "/Users/x/Kortex/motor/runs/r1/artefatos/codificador__ebay.py"
    linux = "/home/cap/Kortex/motor/runs/r1/artefatos/codificador__ebay.py"

    assert _do_python(mac) == _do_python(linux) == "r1/codificador__ebay.py"
    assert _do_javascript([mac]) == _do_javascript([linux])


def test_derivar_chave_nao_julga_se_e_produto() -> None:
    """Os dois lados dão chave para `__pycache__` — e é assim que tem de ser.

    Derivar chave é uma coisa; julgar se algo é produto da fábrica é outra. O
    julgamento mora onde o DISCO é percorrido (``orfaos_de_artefato`` e seu
    ``_DEBRIS``), porque é lá que lixo de ferramenta aparece: medido em
    produção, 109 arquivos de ferramenta contra 49 de produto. Nenhum evento
    aponta para ``__pycache__``.

    A primeira versão deste arquivo filtrava lixo só no lado JavaScript, e o
    teste cruzado pegou: as duas linguagens davam respostas diferentes para o
    mesmo caminho, cada uma internamente consistente.
    """
    lixo = "/x/runs/r1/artefatos/__pycache__/a.cpython-313.pyc"

    assert _do_python(lixo) == "r1/__pycache__/a.cpython-313.pyc"
    assert _do_javascript([lixo]) == [_do_python(lixo)]


def test_a_pasta_artefatos_sozinha_nao_e_artefato() -> None:
    """Divergência real que este arquivo encontrou.

    ``/x/runs/r1/artefatos`` devolvia ``("r1", "")`` no Python — uma chave que
    nomeia uma run e um artefato vazio — e ``null`` no JavaScript. Corrigido no
    Python, que era o lado errado.
    """
    assert _do_python("/x/runs/r1/artefatos") is None
    assert _do_javascript(["/x/runs/r1/artefatos"]) == [None]
