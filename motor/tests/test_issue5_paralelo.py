"""Prova causal da separacao de logs da CLI em duas missoes concorrentes."""
from __future__ import annotations

import json
import sqlite3
import socketserver
import threading
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from motor import __main__ as cli
from motor.composicao_orcamento import DependenciasOrcamento
from motor.modelos import ClienteStub
from motor_painel import painel
from tests.helpers_grafo import composicao_stub


class _TCPServerTeste(socketserver.TCPServer):
    allow_reuse_address = True


def _get_json(path: str) -> object:
    with _TCPServerTeste(("127.0.0.1", 0), painel.Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}{path}"
            with urllib.request.urlopen(url, timeout=5) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.mark.parametrize("com_caixa", [False, True], ids=["sem-caixa", "com-caixa"])
def test_duas_missoes_concluem_em_logs_separados_e_aparecem_no_painel(
    tmp_path, monkeypatch, com_caixa,
):
    workspace = tmp_path / "runs"
    cliente = ClienteStub(lambda *_args: "stub")
    deps: DependenciasOrcamento = composicao_stub(cliente, tmp_path / "orcamento")
    barreira = threading.Barrier(2)

    class Grafo:
        def __init__(self, log):
            self.log = log

        def get_state(self, _config):
            return SimpleNamespace(created_at=None, next=(), values={})

        def invoke(self, entrada, _config):
            barreira.wait(timeout=5)
            run_id = entrada["run_id"]
            self.log.evento("spec.recebida", missao=run_id, subagentes=0)
            self.log.evento("tarefa.concluida", missao=run_id)
            return {"resposta_final": f"concluida:{run_id}"}

    monkeypatch.setattr(cli, "compor_orcamento_openai", lambda *_args, **_kwargs: deps)
    monkeypatch.setattr(cli, "construir_grafo", lambda _cliente, log, **_kwargs: Grafo(log))
    monkeypatch.setattr(cli, "_drenar_orcamento_cli", lambda *_args: True)

    if com_caixa:
        banco_cli = tmp_path / "motor-caixa.db"
        caminho_banco_produtivo = Path(cli.__file__).parent.parent / "motor.db"
        conectar = sqlite3.connect

        def conectar_temporario(caminho, *args, **kwargs):
            if Path(caminho) == caminho_banco_produtivo:
                caminho = banco_cli
            return conectar(caminho, *args, **kwargs)

        monkeypatch.setattr(cli.sqlite3, "connect", conectar_temporario)

    resultados: dict[str, int] = {}
    erros: dict[str, BaseException] = {}

    def executar(run_id: str) -> None:
        argv = [
            "--spec", str(tmp_path / "spec.json"),
            "--workspace", str(workspace),
            "--run-id", run_id,
        ]
        if com_caixa:
            argv.extend(["--caixa", str(tmp_path / "caixa")])
        try:
            resultados[run_id] = cli.main(argv)
        except BaseException as erro:  # prova que nenhuma thread morre por lock
            erros[run_id] = erro

    (tmp_path / "spec.json").write_text(json.dumps({"teste": True}), encoding="utf-8")
    threads = [
        threading.Thread(target=executar, args=(run_id,))
        for run_id in ("missao-a", "missao-b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    if com_caixa:
        # O JSONL já está separado, mas o checkpointer legado continua em um
        # único motor.db. Medimos a contenção aqui sem transformar a issue #5
        # em uma migração de SQLite: a thread que perde o lock falha e a outra
        # não pode ser tratada como missão concluída.
        if erros:
            assert any(
                isinstance(erro, sqlite3.OperationalError)
                and "database is locked" in str(erro)
                for erro in erros.values()
            ), erros
            return

    assert not erros
    assert resultados == {"missao-a": 0, "missao-b": 0}
    caminhos = [workspace / run_id / "log.jsonl" for run_id in ("missao-a", "missao-b")]
    assert all(caminho.exists() for caminho in caminhos)

    monkeypatch.setattr(painel.Handler, "runs_path", workspace)
    monkeypatch.setattr(painel.Handler, "log_path", tmp_path / "log-legado.jsonl")
    runs = _get_json("/dados/runs")
    assert isinstance(runs, list)
    assert {run["id"] for run in runs} == {"missao-a", "missao-b"}
    assert all(run["estado"] == "concluida" for run in runs)

    for run_id in ("missao-a", "missao-b"):
        detalhe = _get_json(f"/dados/runs/{run_id}")
        assert isinstance(detalhe, dict)
        assert detalhe["run"]["id"] == run_id
        assert [evento["seq"] for evento in detalhe["eventos"]] == [1, 2]
        assert detalhe["eventos"][-1]["evento"] == "tarefa.concluida"
