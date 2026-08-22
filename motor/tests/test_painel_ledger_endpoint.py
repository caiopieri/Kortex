"""Contrato de transporte somente-leitura para os ledgers do painel."""
from __future__ import annotations

import importlib.util
import socketserver
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))


def _load_painel():
    spec = importlib.util.spec_from_file_location(
        "painel_ledger_endpoint",
        REPO / "motor_painel" / "painel.py",
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


painel = _load_painel()


class _TCPServerTeste(socketserver.TCPServer):
    allow_reuse_address = True


def _get(path: str, monkeypatch, *, log: Path, runs: Path):
    monkeypatch.setattr(painel.Handler, "log_path", log)
    monkeypatch.setattr(painel.Handler, "runs_path", runs)
    with _TCPServerTeste(("127.0.0.1", 0), painel.Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}{path}"
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    return response.status, response.headers, response.read()
            except urllib.error.HTTPError as erro:
                return erro.code, erro.headers, erro.read()
        finally:
            server.shutdown()
            thread.join(timeout=3)


def test_root_e_run_usam_o_mesmo_header_de_snapshot(tmp_path, monkeypatch):
    monkeypatch.delenv("MOTOR_LOG", raising=False)
    root = tmp_path / "log.jsonl"
    root_bytes = b'{"evento":"raiz"}\n'
    root.write_bytes(root_bytes)
    runs = tmp_path / "runs"
    run = runs / "run-1"
    run.mkdir(parents=True)
    run_bytes = '{"evento":"servico","texto":"caf\u00e9"}\n'.encode()
    (run / "log.jsonl").write_bytes(run_bytes)

    status, headers, body = _get("/ledger/log.jsonl?desde_byte=0", monkeypatch, log=root, runs=runs)
    assert status == 200
    assert body == root_bytes
    assert headers["x-ledger-tamanho"] == str(len(root_bytes))

    status, headers, body = _get(
        "/ledger/runs/run-1/log.jsonl?desde_byte=0",
        monkeypatch,
        log=root,
        runs=runs,
    )
    assert status == 200
    assert body == run_bytes
    assert headers["x-ledger-tamanho"] == str(len(run_bytes))


@pytest.mark.parametrize("query", ["desde_byte=-1", "desde_byte=abc", "desde_byte="])
def test_desde_byte_invalido_retorna_400(tmp_path, monkeypatch, query):
    root = tmp_path / "log.jsonl"
    root.write_bytes(b'{"evento":"x"}\n')
    status, _headers, _body = _get(
        f"/ledger/log.jsonl?{query}", monkeypatch, log=root, runs=tmp_path / "runs"
    )
    assert status == 400


def test_desde_byte_maior_que_snapshot_retorna_vazio_com_tamanho_atual(tmp_path, monkeypatch):
    root = tmp_path / "log.jsonl"
    root.write_bytes(b'{"evento":"x"}\n')
    status, headers, body = _get(
        "/ledger/log.jsonl?desde_byte=999", monkeypatch, log=root, runs=tmp_path / "runs"
    )
    assert status == 200
    assert body == b""
    assert headers["x-ledger-tamanho"] == str(root.stat().st_size)


def test_desde_byte_no_meio_de_utf8_ou_json_retorna_limite_de_recuperacao(tmp_path, monkeypatch):
    root = tmp_path / "log.jsonl"
    primeira = '{"evento":"café"}\n'.encode()
    segunda = b'{"evento":"seguinte"}\n'
    terceira = b'{"evento":"terceira"}\n'
    dados = primeira + segunda + terceira
    root.write_bytes(dados)
    meio_utf8 = dados.index("é".encode()) + 1

    status, headers, _body = _get(
        f"/ledger/log.jsonl?desde_byte={meio_utf8}",
        monkeypatch,
        log=root,
        runs=tmp_path / "runs",
    )
    assert status == 416
    assert headers["x-ledger-offset-corrigido"] == "0"
    assert headers["x-ledger-tamanho"] == str(len(dados))

    inicio_terceira = len(primeira) + len(segunda)
    status, headers, _body = _get(
        f"/ledger/log.jsonl?desde_byte={inicio_terceira + 2}",
        monkeypatch,
        log=root,
        runs=tmp_path / "runs",
    )
    assert status == 416
    assert headers["x-ledger-offset-corrigido"] == str(inicio_terceira)

    status, headers, _body = _get(
        "/ledger/log.jsonl?desde_byte=2", monkeypatch, log=root, runs=tmp_path / "runs"
    )
    assert status == 416
    assert headers["x-ledger-offset-corrigido"] == "0"


def test_ledger_run_confina_travessia_absoluto_e_symlink(tmp_path, monkeypatch):
    root = tmp_path / "log.jsonl"
    root.write_bytes(b"")
    runs = tmp_path / "runs"
    runs.mkdir()
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "log.jsonl").write_bytes(b"segredo\n")
    (runs / "run-link").symlink_to(fora, target_is_directory=True)
    run_file = runs / "run-file"
    run_file.mkdir()
    (run_file / "log.jsonl").symlink_to(fora / "log.jsonl")

    for url in (
        "/ledger/runs/..%2Ffora/log.jsonl",
        "/ledger/runs/%2Ftmp%2Ffora/log.jsonl",
        "/ledger/runs/run-link/log.jsonl",
        "/ledger/runs/run-file/log.jsonl",
    ):
        status, _headers, _body = _get(url, monkeypatch, log=root, runs=runs)
        assert status == 400


def test_ledger_ausente_nao_cria_arquivo_e_503_so_com_override(tmp_path, monkeypatch):
    root = tmp_path / "ausente" / "log.jsonl"
    runs = tmp_path / "runs"
    monkeypatch.delenv("MOTOR_LOG", raising=False)
    status, _headers, body = _get("/ledger/log.jsonl", monkeypatch, log=root, runs=runs)
    assert status == 200
    assert body == b""
    assert not root.exists()

    monkeypatch.setenv("MOTOR_LOG", str(root))
    status, _headers, _body = _get("/ledger/log.jsonl", monkeypatch, log=root, runs=runs)
    assert status == 503
    assert not root.exists()

    root.parent.mkdir(parents=True)
    root.write_bytes(b"")
    status, _headers, _body = _get("/ledger/log.jsonl", monkeypatch, log=root, runs=runs)
    assert status == 503
    assert root.read_bytes() == b""


def test_run_sem_log_ainda_nao_gravado_retorna_404(tmp_path, monkeypatch):
    root = tmp_path / "log.jsonl"
    root.write_bytes(b"")
    runs = tmp_path / "runs"
    (runs / "run-recente").mkdir(parents=True)
    status, _headers, _body = _get(
        "/ledger/runs/run-recente/log.jsonl", monkeypatch, log=root, runs=runs
    )
    assert status == 404
