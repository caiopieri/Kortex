import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from motor.orcamento import CotacaoTentativa, ErroOrcamento, IdentidadeTentativaCusteada
from motor.orcamento import RepositorioOrcamento, ReservaOrcamento, ResultadoTentativa
from motor.orcamento import TentativaBloqueadaPreEfeito, executar_tentativa_custeada


def _reserva(reservation_id: str = "reserva") -> ReservaOrcamento:
    return ReservaOrcamento(reservation_id, "call", "rota", 1, Decimal("1"), "pricing-v1")


def test_brl_preserva_arquivo_schema_e_event_id_existentes(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2"))
    repo.reservar(sessao, _reserva())

    caminho = repo.caminho("run")
    assert caminho.name == "orcamento.sqlite3"
    assert sessao.moeda == "BRL"
    with sqlite3.connect(caminho) as con:
        schema = con.execute("SELECT sql FROM sqlite_master WHERE name='budget_session'").fetchone()[0]
        assert "CHECK (moeda='BRL')" in schema
        assert con.execute("SELECT moeda FROM budget_session").fetchone() == ("BRL",)

    evento = repo.listar_pendentes("run")[0]
    esperado = hashlib.sha256(b"reserva\0custo.reservado").hexdigest()
    assert evento.event_id == esperado
    assert evento.payload["moeda"] == "BRL"


def test_ledgers_brl_e_token_sao_isolados_ate_no_event_id(tmp_path: Path) -> None:
    repo_brl = RepositorioOrcamento(tmp_path)
    repo_token = RepositorioOrcamento(tmp_path, moeda="TOKEN")
    sessao_brl = repo_brl.sessao("run", "thread", Decimal("2"))
    sessao_token = repo_token.sessao("run", "thread", Decimal("20"))

    with pytest.raises(ErroOrcamento, match="outra moeda"):
        repo_token.reservar(sessao_brl, _reserva("cruzada"))

    repo_brl.reservar(sessao_brl, _reserva())
    repo_token.reservar(sessao_token, _reserva())
    reconciliada = repo_token.reconciliar(sessao_token, _reserva(), Decimal("0.5"))

    assert repo_brl.caminho("run").name == "orcamento.sqlite3"
    assert repo_token.caminho("run").name == "cota.sqlite3"
    assert reconciliada.status == "RECONCILED"
    evento_brl = repo_brl.listar_pendentes("run")[0]
    evento_token = repo_token.listar_pendentes("run")[0]
    assert evento_brl.event_id != evento_token.event_id
    assert evento_token.payload["moeda"] == "TOKEN"


@pytest.mark.parametrize(("moeda", "outra"), [("BRL", "TOKEN"), ("TOKEN", "BRL")])
def test_schema_de_cada_arquivo_recusa_a_outra_moeda(
    tmp_path: Path, moeda: str, outra: str
) -> None:
    repo = RepositorioOrcamento(tmp_path, moeda=moeda)  # type: ignore[arg-type]
    caminho = repo.caminho("run")
    repo.sessao("run", "thread", Decimal("2"))

    with sqlite3.connect(caminho) as con, pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO budget_session VALUES (?,?,?,?,?,?,?)",
            ("outra-run", "outra-thread", "2", outra, "0", "0", "ACTIVE"),
        )


def test_cota_preexistente_sem_check_de_token_falha_fechado(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path, moeda="TOKEN")
    caminho = repo.caminho("run")
    with sqlite3.connect(caminho) as con:
        con.execute(
            "CREATE TABLE budget_session ("
            "run_id TEXT, thread_id TEXT, teto TEXT, moeda TEXT, gasto TEXT, "
            "reservado TEXT, status TEXT, PRIMARY KEY(run_id,thread_id))"
        )

    with pytest.raises(ErroOrcamento, match="ledger indisponivel ou corrompido"):
        repo.sessao("run", "thread", Decimal("2"))


def test_outbox_recusa_payload_de_outra_moeda_no_arquivo_token(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path, moeda="TOKEN")
    sessao = repo.sessao("run", "thread", Decimal("2"))
    repo.reservar(sessao, _reserva())
    caminho = repo.caminho("run")
    with sqlite3.connect(caminho) as con:
        payload = json.loads(con.execute("SELECT payload FROM budget_outbox").fetchone()[0])
        payload["moeda"] = "BRL"
        con.execute(
            "UPDATE budget_outbox SET payload=?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
        )

    with pytest.raises(ErroOrcamento, match="outbox corrompida"):
        repo.listar_pendentes("run")


@pytest.mark.parametrize("moeda", ["", "USD", None, 0])
def test_moeda_invalida_falha_antes_de_criar_ledger(tmp_path: Path, moeda: object) -> None:
    raiz = tmp_path / "ledgers"
    with pytest.raises(ErroOrcamento, match="moeda invalida"):
        RepositorioOrcamento(raiz, moeda=moeda)  # type: ignore[arg-type]
    assert not raiz.exists()


@pytest.mark.parametrize(
    ("moeda_repo", "moeda_cotacao"), [("BRL", "TOKEN"), ("TOKEN", "BRL")]
)
def test_cotacao_de_outra_moeda_bloqueia_antes_do_transporte(
    tmp_path: Path, moeda_repo: str, moeda_cotacao: str
) -> None:
    class ClienteCruzado:
        chamadas = 0

        def cotar_tentativa(self) -> CotacaoTentativa:
            return CotacaoTentativa(Decimal("10"), moeda_cotacao, "cota-v1")  # type: ignore[arg-type]

        def tentar_uma_vez(self) -> ResultadoTentativa:
            self.chamadas += 1
            return ResultadoTentativa(
                "nao deve rodar", Decimal("1"), moeda_cotacao, "usage"  # type: ignore[arg-type]
            )

    repo = RepositorioOrcamento(tmp_path, moeda=moeda_repo)  # type: ignore[arg-type]
    sessao = repo.sessao("run", "thread", Decimal("20"))
    cliente = ClienteCruzado()
    identidade = IdentidadeTentativaCusteada("reserva", "call", "rota", 1)

    assert isinstance(
        executar_tentativa_custeada(repo, sessao, identidade, cliente),
        TentativaBloqueadaPreEfeito,
    )
    assert cliente.chamadas == 0
    evento = repo.listar_pendentes("run")[0]
    assert evento.tipo == "custo.bloqueado"
    assert evento.payload["motivo"] == "sem_cotacao"
    with sqlite3.connect(repo.caminho("run")) as con:
        assert con.execute("SELECT COUNT(*) FROM budget_reservation").fetchone() == (0,)
