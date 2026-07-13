import decimal
from decimal import Decimal
import os
import sqlite3
import stat
import pytest

from motor.orcamento import (
    RepositorioOrcamento,
    ReservaOrcamento,
    ErroOrcamento,
)


def test_decimal_context_global_arredondamento(tmp_path):
    """
    1. Fraqueza: Decimal com contexto global que arredonda gasto+reservado+maximo.
    Esperado: O repositório deve ser imune ao contexto de precisão global do decimal da thread.
    Proteção: a soma usa contexto local com precisão suficiente para o limite textual.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-glob", "thread-glob", Decimal("2.00"))

    r1 = ReservaOrcamento("r1", "c1", "rota", 1, Decimal("1.04"), "price-v1")
    repo.reservar(sessao, r1)

    orig_prec = decimal.getcontext().prec
    try:
        decimal.getcontext().prec = 2
        r2 = ReservaOrcamento("r2", "c2", "rota", 1, Decimal("0.004"), "price-v1")
        repo.reservar(sessao, r2)

        caminho = repo.caminho("run-glob")
        with sqlite3.connect(caminho) as con:
            reservado_db = con.execute("SELECT reservado FROM budget_session").fetchone()[0]
            # A reserva precisa persistir o acumulado exato, apesar do contexto global hostil.
            assert Decimal(reservado_db) == Decimal("1.044")
    finally:
        decimal.getcontext().prec = orig_prec


def test_decimal_expoente_enorme_sem_rejeicao_antecipada():
    """
    2. Fraqueza: Decimal com expoente enorme causando expansão/DoS.
    Esperado: Rejeitar decimais com expoentes/escalas absurdas levantando ErroOrcamento.
    Proteção: a escala é limitada antes de qualquer expansão textual.
    """
    val = Decimal('1e128')
    from motor.orcamento import _decimal
    with pytest.raises(ErroOrcamento, match="decimal invalido|escala invalida"):
        _decimal(val)


def test_canonicalidade_teto_replay_divergente(tmp_path):
    """
    3. Fraqueza: Canonicalidade de 1, 1.0, 1.00 em teto de sessão.
    Esperado: O replay/idempotência da sessão deve aceitar representações de Decimais matematicamente idênticos.
    Proteção: valores matematicamente iguais têm a mesma representação persistida.
    """
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run-canon", "thread-canon", Decimal("2.0"))

    repo.sessao("run-canon", "thread-canon", Decimal("2"))


def test_canonicalidade_reserva_replay_divergente(tmp_path):
    """
    3. Fraqueza (continuação): Canonicalidade de 1, 1.0, 1.00 em reservas.
    Esperado: O replay da reserva deve aceitar escalas diferentes para valores numericamente idênticos.
    Proteção: o replay compara o decimal canônico, não sua escala de entrada.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-canon-res", "thread-canon-res", Decimal("5.0"))

    reserva1 = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao, reserva1)

    reserva2 = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1"), "price-v1")
    repo.reservar(sessao, reserva2)


def test_reservation_id_reutilizado_outra_chave(tmp_path):
    """
    4. Fraqueza: reservation_id reutilizado em outra chave.
    Esperado: Reutilização do reservation_id deve ser validada e lançar ErroOrcamento.
    Proteção: a reutilização é detectada antes da escrita e vira erro de domínio.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-res", "thread-res", Decimal("5.0"))

    r1 = ReservaOrcamento("shared-id", "call-1", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao, r1)

    r2 = ReservaOrcamento("shared-id", "call-2", "rota", 1, Decimal("1.0"), "price-v1")
    with pytest.raises(ErroOrcamento, match="reserva invalida|reservation_id ja existe"):
        repo.reservar(sessao, r2)


def test_db_corrompido_campos_text_nao_numericos(tmp_path):
    """
    5. Fraqueza: DB corrompido ou campos TEXT não numéricos.
    Esperado: Detecção de banco de dados inválido/corrompido levantando ErroOrcamento.
    Proteção: texto financeiro inválido é convertido em erro de domínio.
    """
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run-corrupt", "thread-corrupt", Decimal("2.0"))

    caminho = repo.caminho("run-corrupt")
    with sqlite3.connect(caminho) as con:
        # Inserimos "lixo" no campo 'gasto' para forçar a conversão de Decimal
        con.execute("UPDATE budget_session SET gasto='lixo' WHERE run_id='run-corrupt'")

    with pytest.raises(ErroOrcamento, match="banco de dados corrompido|decimal invalido"):
        repo.sessao("run-corrupt", "thread-corrupt", Decimal("2.0"))


def test_symlink_path_toctou_hijack(tmp_path):
    """
    6. Fraqueza: Link simbólico / TOCTOU no caminho do banco.
    Esperado: O motor deve recusar operar caso o arquivo final do banco de dados seja um link simbólico.
    Proteção: links simbólicos e arquivos finais não regulares são recusados.
    """
    repo = RepositorioOrcamento(tmp_path)
    run_id = "run-symlink"
    esperado = tmp_path / run_id
    esperado.mkdir(parents=True, exist_ok=True)

    alvo = tmp_path / "alvo.txt"
    alvo.write_text("conteudo secreto")

    db_symlink = esperado / "orcamento.sqlite3"
    os.symlink(alvo, db_symlink)

    with pytest.raises(ErroOrcamento, match="diretorio de run nao e seguro|symlink nao permitido"):
        repo.sessao(run_id, "thread-symlink", Decimal("2.0"))


def test_idempotencia_concorrente_threads(tmp_path):
    """
    7. Fraqueza: Idempotência sob duas conexões concorrentes.
    Esperado: O tratamento de concorrência deve isolar falhas de infraestrutura (como banco travado)
    e convertê-las em ErroOrcamento.
    Proteção: falhas SQLite atravessam a API apenas como ErroOrcamento.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-concorrente", "thread-concorrente", Decimal("5.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")

    # Bloqueamos o banco de dados com uma transação em uma conexão paralela
    caminho = repo.caminho("run-concorrente")
    con_bloqueio = sqlite3.connect(caminho, isolation_level=None)
    con_bloqueio.execute("BEGIN IMMEDIATE")

    try:
        # A chamada de reservar na outra conexão deve levantar ErroOrcamento (de forma encapsulada),
        with pytest.raises(ErroOrcamento):
            repo.reservar(sessao, reserva)
    finally:
        con_bloqueio.execute("ROLLBACK")
        con_bloqueio.close()


def test_hardlink_do_ledger_e_recusado(tmp_path):
    repo = RepositorioOrcamento(tmp_path)
    diretorio = tmp_path / "run-hardlink"
    diretorio.mkdir(mode=0o700)
    alvo = tmp_path / "alvo.sqlite3"
    alvo.write_text("nao e ledger")
    os.link(alvo, diretorio / "orcamento.sqlite3")
    with pytest.raises(ErroOrcamento, match="arquivo de ledger inseguro"):
        repo.sessao("run-hardlink", "thread", Decimal("1"))


def test_ledger_novo_tem_dono_regular_link_unico_e_modo_0600(tmp_path):
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run-modo", "thread", Decimal("1"))
    arquivo_stat = repo.caminho("run-modo").lstat()
    assert stat.S_ISREG(arquivo_stat.st_mode)
    assert arquivo_stat.st_uid == os.geteuid()
    assert arquivo_stat.st_nlink == 1
    assert stat.S_IMODE(arquivo_stat.st_mode) == 0o600
