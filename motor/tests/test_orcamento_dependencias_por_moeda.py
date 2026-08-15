from decimal import Decimal

from motor.composicao_orcamento import OrcamentoMoeda
from motor.orcamento import (
    RepositorioOrcamento,
    ReservaOrcamento,
)
from motor.servico import GerenciadorJobs


def _reservar(repo: RepositorioOrcamento, run_id: str, reservation_id: str) -> None:
    sessao = repo.sessao(run_id, run_id, Decimal("10"))
    reserva = ReservaOrcamento(
        reservation_id, f"call-{reservation_id}", "rota", 1, Decimal("1"), "v1")
    assert repo.reservar_exclusiva(sessao, reserva).status == "NOVA"


def test_servico_drena_brl_antes_de_token_independente_da_insercao(tmp_path) -> None:
    repo_brl = RepositorioOrcamento(tmp_path)
    repo_token = RepositorioOrcamento(tmp_path, moeda="TOKEN")
    _reservar(repo_brl, "run", "reserva-brl")
    _reservar(repo_token, "run", "reserva-token")
    moedas: list[object] = []
    gerenciador = object.__new__(GerenciadorJobs)
    gerenciador._orcamentos = {
        "TOKEN": OrcamentoMoeda(repo_token, Decimal("100")),
        "BRL": OrcamentoMoeda(repo_brl, Decimal("10")),
    }
    gerenciador._owner_orcamento = "worker"
    gerenciador._outbox_lease_s = 5

    class Log:
        def publicar_orcamento(self, _event_id, _tipo, payload):
            moedas.append(payload["moeda"])

    assert gerenciador._drenar_orcamento("run", Log())  # type: ignore[arg-type]
    assert moedas == ["BRL", "TOKEN"]


def test_relay_nao_cria_ledger_ausente_ao_varrer_moedas(tmp_path) -> None:
    repo_brl = RepositorioOrcamento(tmp_path)
    repo_token = RepositorioOrcamento(tmp_path, moeda="TOKEN")
    _reservar(repo_brl, "run", "reserva-brl")
    gerenciador = object.__new__(GerenciadorJobs)
    gerenciador._orcamentos = {
        "BRL": OrcamentoMoeda(repo_brl, Decimal("10")),
        "TOKEN": OrcamentoMoeda(repo_token, Decimal("100")),
    }
    gerenciador._owner_orcamento = "worker"
    gerenciador._outbox_lease_s = 5

    class Log:
        def publicar_orcamento(self, _event_id, _tipo, _payload):
            return None

    assert gerenciador._drenar_orcamento("run", Log())  # type: ignore[arg-type]
    assert not (tmp_path / "run" / "cota.sqlite3").exists()
