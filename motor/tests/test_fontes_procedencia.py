"""Os binários de fonte são o que o `LEIA.md` diz que são.

A issue #26 trouxe dois `.woff2` de fora do repositório e registrou a
procedência ao lado: URL de origem, tamanho e sha256 de cada um. Só que **nada
conferia esse sha**. Hash que ninguém confere é documentação, não controle: o
arquivo pode ser trocado e o registro continua afirmando o contrário, com a
autoridade de um número.

Este arquivo fecha isso, e a fonte da verdade continua sendo **uma só** — os
hashes são lidos do próprio `LEIA.md`, não copiados para cá. Duplicar o hash
aqui criaria um segundo lugar para atualizar e, no dia em que alguém atualizasse
só um, o teste passaria a defender o valor errado.

Roda no pytest, e não no `node --test` do painel, por três razões:

1. O que se protege é **arquivo do repositório**, não código de front. A
   verificação não tem nada a ver com o bundle.
2. O gate do Python roda sem instalação nenhuma. O `npm test` exige
   `node_modules`, que um checkout novo não tem — e o `npm ci` já esteve
   quebrado (issue #16). Controle de integridade não pode depender de um passo
   que pode falhar antes dele.
3. Rodar a verificação sob o mesmo ecossistema cujos artefatos ela confere é
   circular. Se o que estiver comprometido for o `node_modules`, o verificador
   está dentro do que ele deveria verificar.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

FONTES = Path(__file__).parents[1] / "motor_painel" / "app" / "src" / "fontes"
LEIA = FONTES / "LEIA.md"

# `| `arquivo.woff2` | peso | bytes | `sha256` |` — a tabela do LEIA.
LINHA = re.compile(
    r"^\|\s*`(?P<arquivo>[^`]+\.woff2)`\s*"
    r"\|\s*(?P<peso>\d+)\s*"
    r"\|\s*(?P<bytes>\d+)\s*"
    r"\|\s*`(?P<sha>[0-9a-f]{64})`\s*\|",
    re.M,
)


def _declarados() -> dict[str, dict]:
    """O que o LEIA afirma. Falhar aqui já é o teste falhando: um LEIA que
    deixou de ser parseável é um LEIA que parou de declarar."""
    texto = LEIA.read_text(encoding="utf-8")
    achados = {
        m.group("arquivo"): {
            "sha": m.group("sha"),
            "bytes": int(m.group("bytes")),
            "peso": m.group("peso"),
        }
        for m in LINHA.finditer(texto)
    }
    assert achados, (
        f"nenhuma linha de procedência reconhecida em {LEIA}. "
        "O formato da tabela mudou, ou as entradas sumiram — e sem elas nada "
        "está sendo verificado."
    )
    return achados


def _em_disco() -> dict[str, Path]:
    return {p.name: p for p in sorted(FONTES.glob("*.woff2"))}


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_o_diretorio_de_fontes_existe_com_o_leia() -> None:
    assert FONTES.is_dir(), f"o diretório de fontes sumiu: {FONTES}"
    assert LEIA.is_file(), "as fontes existem e a procedência não — é o pior estado"


def test_cada_binario_casa_com_o_sha_declarado() -> None:
    """Pega os dois lados: binário trocado, e sha editado no LEIA.

    São a mesma comparação vista de duas direções, e é de propósito — a
    pergunta não é "quem mudou", é "o arquivo é o que o registro diz".
    """
    declarados = _declarados()
    disco = _em_disco()

    divergentes = []
    for nome, esperado in declarados.items():
        caminho = disco.get(nome)
        if caminho is None:
            continue  # coberto por `test_declarado_existe_em_disco`
        real = _sha256(caminho)
        if real != esperado["sha"]:
            divergentes.append(f"  {nome}\n    LEIA:  {esperado['sha']}\n    disco: {real}")

    assert not divergentes, (
        "binário de fonte não casa com o sha256 declarado em LEIA.md:\n"
        + "\n".join(divergentes)
        + "\n\nOu o arquivo foi trocado, ou o registro foi editado sem o arquivo. "
        "Confira com `shasum -a 256 " + str(FONTES) + "/*.woff2`."
    )


def test_cada_binario_casa_com_o_tamanho_declarado() -> None:
    """O tamanho é redundante com o sha e vale mesmo assim: um arquivo truncado
    falha aqui com uma mensagem que diz o que aconteceu, em vez de um hash
    diferente que não diz nada."""
    disco = _em_disco()
    erros = [
        f"  {nome}: LEIA diz {d['bytes']} B, disco tem {disco[nome].stat().st_size} B"
        for nome, d in _declarados().items()
        if nome in disco and disco[nome].stat().st_size != d["bytes"]
    ]
    assert not erros, "tamanho declarado não bate:\n" + "\n".join(erros)


def test_fonte_em_disco_sem_entrada_no_leia() -> None:
    """Adicionar fonte sem declarar é o mesmo defeito de declarar o que não está
    lá, na direção oposta — e é o mais fácil de cometer sem perceber, porque a
    tela funciona.
    """
    nao_declarados = sorted(set(_em_disco()) - set(_declarados()))

    assert not nao_declarados, (
        "arquivo .woff2 em disco sem entrada no LEIA.md: "
        + ", ".join(nao_declarados)
        + ".\nToda fonte no repositório precisa de origem, tamanho e sha256 "
        "declarados — binário sem procedência é o que este arquivo existe para impedir."
    )


def test_declarado_no_leia_sem_arquivo_em_disco() -> None:
    """O espelho: o registro promete um arquivo que não está lá."""
    faltando = sorted(set(_declarados()) - set(_em_disco()))

    assert not faltando, (
        "LEIA.md declara procedência de arquivo que não existe: "
        + ", ".join(faltando)
    )


def test_a_licenca_acompanha_os_binarios() -> None:
    """OFL exige manter o aviso; e um binário redistribuído sem o texto da
    licença ao lado é uma pendência jurídica silenciosa."""
    licenca = FONTES / "LICENCA-OFL.txt"
    assert licenca.is_file(), "os .woff2 estão aqui e o texto da licença não"
    texto = licenca.read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in texto
