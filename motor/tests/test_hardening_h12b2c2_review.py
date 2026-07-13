import json
import sqlite3
from decimal import Decimal
import pytest
from motor.orcamento import (
    ErroOrcamento,
    RepositorioOrcamento,
    ReservaOrcamento,
    publicar_um_pendente,
)


def _preparar_repositorio(tmp_path):
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))
    res = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, res)
    return repo


def test_no_maximo_um_evento_e_dedupe(tmp_path):
    repo = _preparar_repositorio(tmp_path)
    chamadas = []

    def pub(eid, tipo, pay):
        chamadas.append((eid, tipo, pay))

    assert publicar_um_pendente(repo, "run", "w1", 10, 5, pub) is True
    assert len(chamadas) == 1

    assert publicar_um_pendente(repo, "run", "w1", 10, 5, pub) is False
    assert len(chamadas) == 1


def test_payload_defensivo(tmp_path):
    repo = _preparar_repositorio(tmp_path)

    def pub_altera(eid, tipo, pay):
        pay["teto"] = "999.0"
        pay["nova_chave"] = "hack"

    assert publicar_um_pendente(repo, "run", "w1", 10, 5, pub_altera) is True

    with sqlite3.connect(repo.caminho("run")) as con:
        bruto = con.execute("SELECT payload FROM budget_outbox").fetchone()[0]
        pay_db = json.loads(bruto)
        assert pay_db["teto"] == "5"
        assert "nova_chave" not in pay_db


def test_publisher_fora_da_transacao(tmp_path):
    repo = _preparar_repositorio(tmp_path)
    db_path = repo.caminho("run")

    def pub_transacao_concorrente(eid, tipo, pay):
        con2 = sqlite3.connect(db_path, isolation_level=None)
        con2.execute("BEGIN IMMEDIATE")
        con2.execute("ROLLBACK")
        con2.close()

    assert (
        publicar_um_pendente(repo, "run", "w1", 10, 5, pub_transacao_concorrente)
        is True
    )


def test_ack_so_apos_sucesso_e_excecao(tmp_path):
    repo = _preparar_repositorio(tmp_path)

    def pub_falha(eid, tipo, pay):
        raise RuntimeError("segredo_api_key_sk_test")

    with pytest.raises(RuntimeError, match="segredo_api_key_sk_test"):
        publicar_um_pendente(repo, "run", "w1", 10, 5, pub_falha)

    pendentes = repo.listar_pendentes("run")
    assert len(pendentes) == 1
    assert pendentes[0].owner == "w1"

    with sqlite3.connect(repo.caminho("run")) as con:
        dump = "\n".join(con.iterdump())
        assert "segredo_api_key" not in dump


def test_redelivery_mesmo_event_id_apos_lease(tmp_path):
    repo = _preparar_repositorio(tmp_path)

    def pub_falha(eid, tipo, pay):
        raise RuntimeError("error")

    with pytest.raises(RuntimeError):
        publicar_um_pendente(repo, "run", "w1", 10, 5, pub_falha)

    recebidos = []

    def pub_ok(eid, tipo, pay):
        recebidos.append(eid)

    assert publicar_um_pendente(repo, "run", "w2", 14, 5, pub_ok) is False
    assert len(recebidos) == 0

    assert publicar_um_pendente(repo, "run", "w2", 15, 5, pub_ok) is True
    assert len(recebidos) == 1

    event_id_original = repo._event_id("r1", "custo.reservado")
    assert recebidos[0] == event_id_original


def test_inputs_hostis_publicar(tmp_path):
    repo = _preparar_repositorio(tmp_path)

    def pub(*_):
        pass

    with pytest.raises(ErroOrcamento, match="repositorio invalido"):
        publicar_um_pendente(object(), "run", "w1", 10, 5, pub)

    with pytest.raises(ErroOrcamento, match="publicador invalido"):
        publicar_um_pendente(repo, "run", "w1", 10, 5, object())

    with pytest.raises(ErroOrcamento, match="run_id invalido"):
        publicar_um_pendente(repo, "invalido/run", "w1", 10, 5, pub)

    with pytest.raises(ErroOrcamento, match="owner invalido"):
        publicar_um_pendente(repo, "run", "invalido/owner", 10, 5, pub)

    with pytest.raises(ErroOrcamento, match="agora invalido"):
        publicar_um_pendente(repo, "run", "w1", "lixo", 5, pub)

    with pytest.raises(ErroOrcamento, match="lease_s invalido"):
        publicar_um_pendente(repo, "run", "w1", 10, "lixo", pub)

    with pytest.raises(ErroOrcamento, match="lease_s invalido"):
        # lease_s precisa ser positivo (> 0)
        publicar_um_pendente(repo, "run", "w1", 10, 0, pub)
