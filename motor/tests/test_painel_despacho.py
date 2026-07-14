"""Testes do despacho real de missão pelo painel (REFAT-D).

POST /dados/missoes e GET /dados/missoes/ativa. `subprocess.Popen` é SEMPRE
substituído por um fake (monkeypatch) — nenhum teste dispara o motor real.
"""
from __future__ import annotations

import json
import os
import sys
import importlib.util
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))


def _load_painel():
    spec = importlib.util.spec_from_file_location(
        "painel_v05_despacho",
        REPO / "motor_painel" / "painel.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


painel = _load_painel()

SPEC_MINIMA = {
    "versao": "0.1",
    "missao": {"id": "m-teste", "objetivo": "x", "criterios_cobertura": ["c"]},
    "subagentes": [{"id": "s1", "objetivo": "x", "resultado_esperado": "y"}],
    "sintese": {"instrucao": "consolide", "formato": "markdown"},
}


class _TCPServerTeste(socketserver.TCPServer):
    allow_reuse_address = True


class _FakeProc:
    pid = 43210


@pytest.fixture
def popen_espiao(monkeypatch):
    """Substitui subprocess.Popen no módulo do painel — NUNCA roda o motor real."""
    chamadas = []

    def fake_popen(argv, **kwargs):
        chamadas.append({"argv": argv, "kwargs": kwargs})
        return _FakeProc()

    monkeypatch.setattr(painel.subprocess, "Popen", fake_popen)
    return chamadas


@pytest.fixture
def despachos(tmp_path, monkeypatch):
    """Isola o diretório de despachos (lock/spec/log) em tmp_path."""
    d = tmp_path / "despachos"
    monkeypatch.setattr(painel.Handler, "despachos_dir", d)
    monkeypatch.setattr(painel.Handler, "log_path", tmp_path / "log.jsonl")
    monkeypatch.setattr(painel.Handler, "db_path", tmp_path / "motor.db")
    return d


def _request(method: str, path: str, body: bytes | None = None,
             headers: dict | None = None) -> tuple[int, str]:
    """Sobe o servidor, faz uma requisição e devolve (status, corpo)."""
    with _TCPServerTeste(("127.0.0.1", 0), painel.Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}{path}"
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json", **(headers or {})},
                method=method,
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status, resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=3)


def _post_missao(payload: dict | bytes, headers: dict | None = None):
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return _request("POST", "/dados/missoes", data, headers)


def _pid_morto() -> int:
    """Encontra um pid sem processo vivo."""
    pid = 99999
    while pid > 1:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass
        pid -= 1
    pytest.fail("não achou pid morto")


# ---------------------------------------------------------------------------
# 1. POST válido → 200, Popen 1x com argv exato, spec gravada, lock criado
# ---------------------------------------------------------------------------

def test_post_missao_valido_despacha(despachos, popen_espiao):
    status, corpo = _post_missao(
        {"spec": SPEC_MINIMA, "opcoes": {"auto": True, "escalar": True}}
    )
    assert status == 200
    resp = json.loads(corpo)
    assert resp["ok"] is True
    assert resp["pid"] == 43210

    # Popen chamado exatamente 1x, sem shell, argv fixo
    assert len(popen_espiao) == 1
    argv = popen_espiao[0]["argv"]
    assert argv == [
        sys.executable, "-m", "motor",
        "--spec", resp["spec"],
        "--caixa", "runs/caixa",
        "--run-id", f"painel-{Path(resp['spec']).stem.removeprefix('spec-')}",
        "--auto", "--escalar",
    ]
    assert isinstance(argv, list)  # nunca string de shell
    assert popen_espiao[0]["kwargs"].get("start_new_session") is True
    assert "shell" not in popen_espiao[0]["kwargs"]

    # spec gravada em arquivo dentro de runs/despachos isolado
    spec_path = Path(resp["spec"])
    assert spec_path.parent == despachos
    assert json.loads(spec_path.read_text(encoding="utf-8")) == SPEC_MINIMA

    # lock criado com o pid do processo
    lock = despachos / ".lock"
    assert lock.exists()
    assert lock.read_text(encoding="utf-8").strip() == "43210"

    # log de despacho criado
    assert Path(resp["log"]).parent == despachos


def test_post_missao_sem_opcoes_argv_base(despachos, popen_espiao):
    status, corpo = _post_missao({"spec": SPEC_MINIMA})
    assert status == 200
    resp = json.loads(corpo)
    argv = popen_espiao[0]["argv"]
    assert argv == [
        sys.executable, "-m", "motor",
        "--spec", resp["spec"],
        "--caixa", "runs/caixa",
        "--run-id", f"painel-{Path(resp['spec']).stem.removeprefix('spec-')}",
    ]


# ---------------------------------------------------------------------------
# 2. Lock com pid vivo → 409 e Popen NÃO chamado
# ---------------------------------------------------------------------------

def test_post_missao_lock_vivo_409(despachos, popen_espiao):
    despachos.mkdir(parents=True)
    (despachos / ".lock").write_text(str(os.getpid()), encoding="utf-8")
    status, corpo = _post_missao({"spec": SPEC_MINIMA, "opcoes": {}})
    assert status == 409
    assert "despacho em curso" in corpo
    assert popen_espiao == []


def test_post_missao_lock_morto_sobrescreve(despachos, popen_espiao):
    despachos.mkdir(parents=True)
    (despachos / ".lock").write_text(str(_pid_morto()), encoding="utf-8")
    status, _corpo = _post_missao({"spec": SPEC_MINIMA})
    assert status == 200
    assert len(popen_espiao) == 1
    assert (despachos / ".lock").read_text(encoding="utf-8").strip() == "43210"


# ---------------------------------------------------------------------------
# 3. JSON inválido / spec vazia / body gigante → 400, sem Popen
# ---------------------------------------------------------------------------

def test_post_missao_json_invalido_400(despachos, popen_espiao):
    status, _ = _post_missao(b"{isso nao e json")
    assert status == 400
    assert popen_espiao == []


def test_post_missao_spec_vazia_400(despachos, popen_espiao):
    for payload in ({"spec": {}}, {"spec": "nao-dict"}, {"opcoes": {}}):
        status, corpo = _post_missao(payload)
        assert status == 400
        assert "spec" in corpo
    assert popen_espiao == []


def test_post_missao_body_gigante_400(despachos, popen_espiao):
    gigante = json.dumps({"spec": {"x": "a" * (65 * 1024)}}).encode("utf-8")
    status, corpo = _post_missao(gigante)
    assert status == 400
    assert "64KB" in corpo
    assert popen_espiao == []


# ---------------------------------------------------------------------------
# 4. Origin estranha → 403, sem Popen
# ---------------------------------------------------------------------------

def test_post_missao_origin_estranha_403(despachos, popen_espiao):
    status, corpo = _post_missao(
        {"spec": SPEC_MINIMA},
        headers={"Origin": "http://malicioso.example"},
    )
    assert status == 403
    assert "Origem nao permitida" in corpo
    assert popen_espiao == []


# ---------------------------------------------------------------------------
# 5. GET /dados/missoes/ativa reflete lock vivo/morto
# ---------------------------------------------------------------------------

def test_get_missao_ativa_sem_lock(despachos):
    status, corpo = _request("GET", "/dados/missoes/ativa")
    assert status == 200
    assert json.loads(corpo) == {"ativa": False, "pid": None}


def test_get_missao_ativa_lock_vivo(despachos):
    despachos.mkdir(parents=True)
    (despachos / ".lock").write_text(str(os.getpid()), encoding="utf-8")
    status, corpo = _request("GET", "/dados/missoes/ativa")
    assert status == 200
    assert json.loads(corpo) == {"ativa": True, "pid": os.getpid()}


def test_get_missao_ativa_lock_morto(despachos):
    despachos.mkdir(parents=True)
    (despachos / ".lock").write_text(str(_pid_morto()), encoding="utf-8")
    status, corpo = _request("GET", "/dados/missoes/ativa")
    assert status == 200
    assert json.loads(corpo) == {"ativa": False, "pid": None}
