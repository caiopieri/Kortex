"""O que impede o curador de trocar um modelo por engano ou por mentira.

Três achados da auditoria viviam aqui e eram a razão de o flywheel estar travado:
o titular nunca era executado (U-04), o selo era um hash público (U-06b) e o
tamanho da amostra era autodeclarado sem teste de significância (U-07).

Os três tinham o mesmo formato de falha: a certificação PARECIA rigorosa e o
resultado dela reescreve o catálogo do motor. Estes testes provam os dois
desfechos de cada portão — porque um portão que aprova tudo é indistinguível de
um que funciona quando o normal é aprovar.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any

import pytest

from motor import curador
from motor.curador import (
    ALFA,
    PISO_CASOS,
    _p_mcnemar,
    carregar_chave_selo,
    certificar_sombra,
    rodar_sombra,
)

CHAVE = b"chave-de-teste-do-rigor-com-32-by!!"
PROPOSTA: dict[str, Any] = {
    "slot": "executor/t1",
    "titular": "modelo-t",
    "candidato": "modelo-c",
    "politica": {"min_casos": PISO_CASOS},
}


def _casos(n: int = PISO_CASOS) -> list[dict[str, Any]]:
    return [{
        "id": str(i),
        "slot": "executor/t1",
        "meta": {"split": "held-out", "proveniencia": "suite-rigor"},
    } for i in range(n)]


def _sombra(
    aprova_titular, aprova_candidato, *, n: int = PISO_CASOS,
    custo_t: float = 2.0, custo_c: float = 1.0, min_casos: int = PISO_CASOS,
) -> dict[str, Any]:
    def runner(caso: dict[str, Any], modelo: str) -> dict[str, Any]:
        i = int(caso["id"])
        if modelo == "modelo-t":
            return {"aprovado": aprova_titular(i), "custo_usd": custo_t}
        return {"aprovado": aprova_candidato(i), "custo_usd": custo_c}

    proposta = {**PROPOSTA, "politica": {"min_casos": min_casos}}
    return rodar_sombra(proposta, _casos(n), runner, chave=CHAVE)


# ------------------------------------------------------------------ U-04
def test_titular_e_executado_no_runner_e_nao_lido_do_arquivo() -> None:
    """O ponto de U-04: quem monta os casos não pode mais escolher o placar.

    Antes, `caso["titular"]` era aceito como resultado. Um proponente honesto e
    um proponente interessado produziam evidências indistinguíveis.
    """
    chamadas: list[tuple[str, str]] = []

    def runner(caso: dict[str, Any], modelo: str) -> dict[str, Any]:
        chamadas.append((caso["id"], modelo))
        return {"aprovado": modelo == "modelo-c", "custo_usd": 1.0}

    casos = _casos(3)
    for caso in casos:
        # Placar plantado: o titular "acertou tudo" e sai de graça. Se ainda
        # fosse lido, o candidato jamais venceria — e a evidência mentiria.
        caso["titular"] = {"aprovado": True, "custo_usd": 0.0}

    evidencia = rodar_sombra(
        {**PROPOSTA, "politica": {"min_casos": 3}}, casos, runner, chave=CHAVE,
    )

    assert sorted(chamadas) == sorted(
        (str(i), m) for i in range(3) for m in ("modelo-t", "modelo-c")
    )
    assert evidencia["titular"]["aprovados"] == 0
    assert evidencia["titular"]["custo_medio_usd"] == 1.0


def test_titular_e_candidato_veem_exatamente_os_mesmos_casos() -> None:
    """Pareamento não é detalhe: é o que autoriza McNemar.

    Se cada lado rodasse um subconjunto diferente, os discordantes deixariam de
    ser pares e o teste estaria medindo ruído com nome de rigor.
    """
    vistos: dict[str, list[str]] = {"modelo-t": [], "modelo-c": []}

    def runner(caso: dict[str, Any], modelo: str) -> dict[str, Any]:
        vistos[modelo].append(caso["id"])
        return {"aprovado": True, "custo_usd": 1.0}

    rodar_sombra(PROPOSTA, _casos(), runner, chave=CHAVE)

    assert vistos["modelo-t"] == vistos["modelo-c"] != []


# ------------------------------------------------------------------ U-06b
def test_evidencia_selada_com_outra_chave_nao_certifica() -> None:
    evidencia = _sombra(lambda i: i == 0, lambda _i: True)
    assert certificar_sombra(evidencia, chave=CHAVE)["status"] == "certificado"

    outra = certificar_sombra(evidencia, chave=b"outra-chave-qualquer-com-32-bytes!")
    assert outra["motivo"] == "evidencia de sombra nao selada"


def test_evidencia_adulterada_apos_selada_nao_certifica() -> None:
    """Selo cobre os casos, não só o cabeçalho: mexer no placar invalida."""
    evidencia = _sombra(lambda i: i == 0, lambda _i: True)
    evidencia["casos"][0]["titular"]["aprovado"] = False

    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == (
        "evidencia de sombra nao selada"
    )


def test_sem_chave_a_sombra_nao_sai_selada() -> None:
    evidencia = rodar_sombra(
        PROPOSTA, _casos(), lambda _c, _m: {"aprovado": True, "custo_usd": 1.0},
        chave=None,
    )
    assert evidencia["evidencia_mac"] is None


@pytest.mark.parametrize("modo", [0o644, 0o640, 0o604])
def test_chave_legivel_por_terceiros_e_recusada(tmp_path, modo: int) -> None:
    """Chave que outro processo lê não autentica — e aceitar seria pior que nada.

    Recusar em silêncio é o comportamento certo aqui: `carregar_chave_selo`
    devolve None e a certificação falha fechada logo depois.
    """
    arquivo = tmp_path / "curador.key"
    arquivo.write_bytes(CHAVE)
    arquivo.chmod(modo)
    assert carregar_chave_selo(arquivo) is None


def test_chave_curta_demais_e_recusada(tmp_path) -> None:
    arquivo = tmp_path / "curta.key"
    arquivo.write_bytes(b"curta")
    arquivo.chmod(0o600)
    assert carregar_chave_selo(arquivo) is None


def test_chave_boa_e_aceita(tmp_path) -> None:
    arquivo = tmp_path / "boa.key"
    arquivo.write_bytes(CHAVE)
    arquivo.chmod(0o600)
    assert carregar_chave_selo(arquivo) == CHAVE


def test_chave_ausente_do_ambiente_nao_estoura(monkeypatch) -> None:
    monkeypatch.delenv("KORTEX_CURADOR_CHAVE", raising=False)
    assert carregar_chave_selo() is None


# ------------------------------------------------------------------ U-07
def test_min_casos_abaixo_do_piso_e_recusado() -> None:
    """O caso literal da auditoria: certificação com n=1.

    Não bastava exigir amostra maior na política — a política é escrita pelo
    proponente. O piso mora no código.
    """
    evidencia = _sombra(lambda _i: False, lambda _i: True, n=1, min_casos=1)
    resultado = certificar_sombra(evidencia, chave=CHAVE)

    assert resultado["status"] == "rejeitado"
    assert f"piso e {PISO_CASOS}" in resultado["motivo"]


def test_vantagem_pequena_demais_nao_certifica_mesmo_sendo_positiva() -> None:
    """`>` estrito entre proporções certificava 1 discordante de vantagem.

    Aqui o candidato REALMENTE vence — 4 a 0 — e ainda assim não passa: p=0.0625.
    Placar de 4 a 0 sai de moeda honesta uma vez a cada 16.
    """
    evidencia = _sombra(lambda i: i >= 4, lambda _i: True)
    resultado = certificar_sombra(evidencia, chave=CHAVE)

    assert resultado["status"] == "rejeitado"
    assert resultado["pareado"] == {"so_candidato": 4, "so_titular": 0, "p_valor": 0.0625}


def test_vantagem_suficiente_certifica() -> None:
    evidencia = _sombra(lambda i: i >= 6, lambda _i: True)
    resultado = certificar_sombra(evidencia, chave=CHAVE)

    assert resultado["status"] == "certificado"
    assert resultado["pareado"]["p_valor"] < ALFA


def test_vitorias_trocadas_entre_os_lados_nao_certificam() -> None:
    """Candidato ganha 8 e perde 7: taxa maior, diferença indistinguível de sorte.

    É o caso que a comparação de proporções soltas aprovava e que mais importa —
    dois modelos parecidos, cada um bom numa coisa.
    """
    evidencia = _sombra(
        lambda i: i >= 8, lambda i: not (8 <= i < 15),
    )
    resultado = certificar_sombra(evidencia, chave=CHAVE)

    assert resultado["candidato"]["taxa_aprovacao"] > resultado["titular"]["taxa_aprovacao"]
    assert resultado["status"] == "rejeitado"
    assert resultado["pareado"]["so_candidato"] == 8
    assert resultado["pareado"]["so_titular"] == 7


@pytest.mark.parametrize(
    ("so_candidato", "so_titular", "esperado"),
    [
        (0, 0, 1.0),        # ninguem discorda: nada a concluir
        (5, 0, 0.03125),    # 1/32, primeiro placar limpo que cruza ALFA
        (4, 0, 0.0625),     # 1/16, ainda nao cruza
        (0, 5, 1.0),        # candidato perde feio: p unilateral maximo
        (3, 3, 0.65625),
    ],
)
def test_p_mcnemar_confere_com_a_binomial(
    so_candidato: int, so_titular: int, esperado: float,
) -> None:
    assert _p_mcnemar(so_candidato, so_titular) == pytest.approx(esperado)


def test_menos_de_cinco_discordantes_nunca_certifica() -> None:
    """Consequência deliberada do teste exato, fixada para não regredir por acaso.

    Com 4 ou menos discordâncias, nem o placar perfeito alcança ALFA. Alguém
    poderia "consertar" isso trocando para a aproximação qui-quadrado e o portão
    voltaria a aprovar ruído sem nenhum teste ficar vermelho — este fica.
    """
    for n in range(5):
        assert _p_mcnemar(n, 0) >= ALFA
    assert _p_mcnemar(5, 0) < ALFA


def test_C03_caminho_autoritativo_nunca_passa_chave_do_chamador() -> None:
    """`chave=` é costura de teste; produção tem que carregar do ambiente.

    Achado da trava GPT-5 (2026-07-29, C-03): quem chama pode inventar uma chave,
    selar com ela e certificar com ela — a ausência de chave configurada deixa de
    barrar. Não é explorável hoje (exige editar o código), mas é o degrau exato
    para o defeito voltar: basta um caller futuro repassar chave.

    Este teste trava o caminho autoritativo. `preparar_promocao_gated` é o único
    ponto que produz intenção de promoção, e ele não pode ter essa liberdade.
    """
    fonte = inspect.getsource(curador.preparar_promocao_gated)

    assert "certificar_sombra(evidencia)" in fonte
    assert "chave=" not in fonte


def test_C03_certificar_sem_chave_configurada_recusa_de_verdade(monkeypatch) -> None:
    """O outro desfecho de C-03, pelo caminho de produção.

    Sem `chave=` e sem `KORTEX_CURADOR_CHAVE`, evidência legítima e bem formada
    não certifica. Se este teste ficar verde por acidente algum dia, o piso
    inteiro do selo terá evaporado.
    """
    monkeypatch.delenv("KORTEX_CURADOR_CHAVE", raising=False)
    evidencia = _sombra(lambda i: i == 0, lambda _i: True)

    assert certificar_sombra(evidencia)["motivo"] == "evidencia de sombra nao selada"


def test_C05_permissao_e_leitura_olham_o_mesmo_inode(tmp_path, monkeypatch) -> None:
    """A chave lida tem que ser a chave cuja permissão foi checada.

    Achado da 2ª rodada da trava GPT-5: checar permissão por caminho e depois ler
    por caminho são dois inodes diferentes se alguém trocar o arquivo na janela.

    A troca é disparada pela PRIMEIRA checagem de permissão, seja ela
    `Path.stat` (implementação antiga, por caminho) ou `os.fstat` (atual, pelo
    descritor). Assim o teste reprova a versão vulnerável em vez de só exercitar
    a corrigida — reprodutor que só passa na correção não prova nada.
    """
    alvo = tmp_path / "curador.key"
    alvo.write_bytes(CHAVE)
    alvo.chmod(0o600)

    intruso = tmp_path / "intruso.key"
    intruso.write_bytes(b"chave-do-atacante-com-32-bytes!!!!")
    intruso.chmod(0o600)

    stat_real, fstat_real = Path.stat, os.fstat
    trocado: list[bool] = []

    def trocar() -> None:
        if not trocado:
            trocado.append(True)
            alvo.unlink()
            intruso.replace(alvo)

    def stat_espiao(self, **kwargs):  # implementação por caminho
        resultado = stat_real(self, **kwargs)
        trocar()
        return resultado

    def fstat_espiao(fd):  # implementação por descritor
        resultado = fstat_real(fd)
        trocar()
        return resultado

    monkeypatch.setattr(Path, "stat", stat_espiao)
    monkeypatch.setattr(os, "fstat", fstat_espiao)

    lida = carregar_chave_selo(alvo)

    assert trocado, "a troca nem chegou a acontecer; o teste não testou nada"
    assert lida == CHAVE, "leu a chave do atacante: permissão e leitura viram inodes diferentes"
