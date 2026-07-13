"""Testes do painel v0.5 — validam parse de eventos e lógica de grafo derivado do log.

Não fazem chamadas de rede: usam apenas motor_painel/painel.py como módulo importável.
Cobrem:
- parse_linha: linhas válidas, vazias, inválidas
- parse_eventos: lê todas as linhas do log de amostra sem erro
- grafo_do_log: nós dinâmicos (subagentes, portões) e tipos de evento v0.5
- dados_painel: integração completa sobre o log de amostra
"""
from __future__ import annotations

import json
import sys
import importlib
import importlib.util
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Adiciona a raiz do repo ao sys.path para import de motor_painel
REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

def _load_painel():
    spec = importlib.util.spec_from_file_location(
        "painel_v05",
        REPO / "motor_painel" / "painel.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

painel = _load_painel()
parse_linha   = painel.parse_linha
parse_eventos = painel.parse_eventos
grafo_do_log  = painel.grafo_do_log
dados_painel  = painel.dados_painel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LOG_AMOSTRA = REPO / "exemplos" / "log-amostra.jsonl"  # amostra commitada — NUNCA o log vivo

TODOS_TIPOS_EVENTO = [
    "spec.criada", "spec.recebida",
    "paralelo.iniciado", "paralelo.concluido",
    "executor.chamado", "executor.respondeu", "executor.erro",
    "portao.aprovado", "portao.reprovado",
    "modelo.falha",
    "escalado",
    "decisao.pendente", "decisao.retomada", "decisao.fundador", "decisao.timeout",
    "tarefa.concluida", "tarefa.abortada",
]

# Log sintético cobrindo TODOS os tipos de evento do v0.5
LOG_COMPLETO_LINHAS = [
    json.dumps({"t": i * 0.1, "evento": tipo, "executor": "planner" if "executor" in tipo else None})
    for i, tipo in enumerate(TODOS_TIPOS_EVENTO)
]


# ---------------------------------------------------------------------------
# parse_linha
# ---------------------------------------------------------------------------

def test_parse_linha_valida():
    linha = '{"t": 0.01, "evento": "spec.recebida", "missao": "x"}'
    ev = parse_linha(linha)
    assert ev["evento"] == "spec.recebida"
    assert ev["t"] == 0.01


def test_parse_linha_vazia_retorna_none():
    assert parse_linha("") is None
    assert parse_linha("   \n") is None


def test_parse_linha_json_invalido_levanta():
    with pytest.raises(json.JSONDecodeError):
        parse_linha("{isso nao e json}")


# ---------------------------------------------------------------------------
# parse_eventos com log de amostra real
# ---------------------------------------------------------------------------

def test_parse_eventos_log_amostra_sem_erro():
    """Todas as linhas do log gerado por gerar_log_amostra.py devem ser parseadas."""
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    eventos = parse_eventos(LOG_AMOSTRA)
    assert len(eventos) > 0


def test_parse_eventos_log_amostra_contem_tipos_esperados():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    eventos = parse_eventos(LOG_AMOSTRA)
    tipos = {e["evento"] for e in eventos}
    # Tipos obrigatórios no log de amostra
    for t in ("spec.recebida", "paralelo.iniciado", "portao.reprovado",
              "portao.aprovado", "escalado", "decisao.fundador", "tarefa.concluida"):
        assert t in tipos, f"tipo ausente no log de amostra: {t}"


def test_parse_eventos_arquivo_inexistente_retorna_lista_vazia(tmp_path):
    result = parse_eventos(tmp_path / "nao_existe.jsonl")
    assert result == []


def test_parse_eventos_todos_os_tipos_v05(tmp_path):
    """parse_eventos aceita todas as 17 linhas com tipos de evento do v0.5."""
    log = tmp_path / "full.jsonl"
    log.write_text("\n".join(LOG_COMPLETO_LINHAS) + "\n", encoding="utf-8")
    eventos = parse_eventos(log)
    assert len(eventos) == len(TODOS_TIPOS_EVENTO)
    tipos_obtidos = {e["evento"] for e in eventos}
    assert tipos_obtidos == set(TODOS_TIPOS_EVENTO)


def test_parse_eventos_ignora_linhas_vazias(tmp_path):
    log = tmp_path / "sparse.jsonl"
    log.write_text(
        '\n{"t": 0.1, "evento": "spec.recebida"}\n\n{"t": 0.2, "evento": "tarefa.concluida"}\n',
        encoding="utf-8",
    )
    eventos = parse_eventos(log)
    assert len(eventos) == 2
    assert eventos[0]["evento"] == "spec.recebida"
    assert eventos[1]["evento"] == "tarefa.concluida"


# ---------------------------------------------------------------------------
# grafo_do_log — nós dinâmicos
# ---------------------------------------------------------------------------

def _ev(*items):
    """Monta lista de eventos para grafo_do_log."""
    return list(items)


def test_grafo_subagentes_dinamicos():
    """Nós de subagente vêm do evento paralelo.iniciado, não hardcoded."""
    eventos = _ev(
        {"t": 0.0, "evento": "paralelo.iniciado", "subagentes": ["alfa", "beta", "gama"]},
    )
    nos, arestas = grafo_do_log(eventos)
    ids = {n["id"] for n in nos}
    assert {"alfa", "beta", "gama"}.issubset(ids)
    for n in nos:
        if n["id"] in ("alfa", "beta", "gama"):
            assert n["tipo"] == "subagente"


def test_grafo_portao_verifier():
    eventos = _ev(
        {"t": 0.0, "evento": "paralelo.iniciado", "subagentes": ["sub-x"]},
        {"t": 0.1, "evento": "portao.reprovado", "portao": "verifier:sub-x", "ciclo": 1, "motivo": "insuficiente"},
        {"t": 0.2, "evento": "portao.aprovado", "portao": "verifier:sub-x", "ciclo": 2},
    )
    nos, arestas = grafo_do_log(eventos)
    ids = {n["id"] for n in nos}
    assert "verifier:sub-x" in ids
    tipos = {n["id"]: n["tipo"] for n in nos}
    assert tipos["verifier:sub-x"] == "portao"
    # aresta sub-x → verifier:sub-x
    assert any(a["de"] == "sub-x" and a["para"] == "verifier:sub-x" for a in arestas)


def test_grafo_portao_cobertura_e_fundador():
    eventos = _ev(
        {"t": 0.0, "evento": "portao.reprovado", "portao": "cobertura", "lacunas": ["x"]},
        {"t": 0.1, "evento": "escalado", "para": "fundador"},
        {"t": 0.2, "evento": "decisao.fundador", "portao": "cobertura", "decisao": "prosseguir"},
    )
    nos, arestas = grafo_do_log(eventos)
    ids = {n["id"] for n in nos}
    assert "fundador" in ids
    tipos = {n["id"]: n["tipo"] for n in nos}
    assert tipos["fundador"] == "decisor"


def test_grafo_log_amostra_tem_nos_esperados():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    eventos = parse_eventos(LOG_AMOSTRA)
    nos, arestas = grafo_do_log(eventos)
    ids = {n["id"] for n in nos}
    # Os dois subagentes da missão de pesquisa
    assert "pesquisa-alfa" in ids
    assert "pesquisa-beta" in ids
    # Portões de verifier
    assert "verifier:pesquisa-alfa" in ids
    assert "verifier:pesquisa-beta" in ids
    # Gate de cobertura e decisor
    assert "cobertura" in ids
    assert "fundador" in ids


# ---------------------------------------------------------------------------
# dados_painel — integração
# ---------------------------------------------------------------------------

def test_dados_painel_estrutura(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text(
        json.dumps({"t": 0.0, "evento": "spec.recebida", "missao": "x", "subagentes": 2}) + "\n"
        + json.dumps({"t": 0.1, "evento": "paralelo.iniciado", "subagentes": ["a", "b"]}) + "\n"
        + json.dumps({"t": 0.5, "evento": "tarefa.concluida", "missao": "x"}) + "\n",
        encoding="utf-8",
    )
    d = dados_painel(log)
    assert "nos" in d and "arestas" in d and "eventos" in d
    assert len(d["eventos"]) == 3
    ids = {n["id"] for n in d["nos"]}
    assert {"a", "b"}.issubset(ids)


def test_dados_painel_sem_log(tmp_path):
    d = dados_painel(tmp_path / "inexistente.jsonl")
    assert d == {"nos": [{"id": "motor", "tipo": "nucleo"}], "arestas": [], "eventos": []}


# ---------------------------------------------------------------------------
# Rotas HTTP
# ---------------------------------------------------------------------------

class _TCPServerTeste(socketserver.TCPServer):
    allow_reuse_address = True


def _http_get(path: str, log_path: Path) -> tuple[int, str, str]:
    painel.Handler.log_path = log_path
    with _TCPServerTeste(("127.0.0.1", 0), painel.Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_address[1]}{path}",
                timeout=3,
            ) as resp:
                body = resp.read().decode("utf-8")
                content_type = resp.headers.get("Content-Type", "")
                return resp.status, content_type, body
        finally:
            server.shutdown()
            thread.join(timeout=3)


def test_rota_grafo3d_responde_html_com_forcegraph(tmp_path, monkeypatch):
    monkeypatch.setattr(painel, "APP_DIST", tmp_path / "nao_existe")
    log = tmp_path / "log.jsonl"
    log.write_text(
        json.dumps({"t": 0.0, "evento": "spec.recebida", "missao": "x"}) + "\n",
        encoding="utf-8",
    )

    status, content_type, body = _http_get("/grafo3d", log)

    assert status == 200
    assert "text/html" in content_type
    assert "ForceGraph3D" in body
    assert "fetch(\"/dados\"" in body


def test_rotas_dados_e_painel_2d_intactas(tmp_path, monkeypatch):
    monkeypatch.setattr(painel, "APP_DIST", tmp_path / "nao_existe")
    log = tmp_path / "log.jsonl"
    log.write_text(
        json.dumps({"t": 0.0, "evento": "paralelo.iniciado", "subagentes": ["a"]}) + "\n",
        encoding="utf-8",
    )

    status_dados, content_type_dados, body_dados = _http_get("/dados", log)
    status_home, content_type_home, body_home = _http_get("/", log)

    payload = json.loads(body_dados)
    assert status_dados == 200
    assert "application/json" in content_type_dados
    assert payload["nos"]
    assert status_home == 200
    assert "text/html" in content_type_home
    assert "Meta-fábrica v0.5" in body_home


# ---------------------------------------------------------------------------
# Rotas HTTP v1 — endpoints de leitura (GET /dados/*)
# ---------------------------------------------------------------------------

def test_get_dados_runs():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    status, content_type, body = _http_get("/dados/runs", LOG_AMOSTRA)
    payload = json.loads(body)
    assert status == 200
    assert "application/json" in content_type
    assert isinstance(payload, list)
    assert len(payload) >= 1
    ids = [r["id"] for r in payload]
    assert "pesquisa-receita-exemplo" in ids
    run = next(r for r in payload if r["id"] == "pesquisa-receita-exemplo")
    assert set(run.keys()) == {"id", "objetivo", "estado", "inicio", "custo", "n_eventos"}
    assert run["estado"] == "concluida"


def test_get_dados_runs_id_existente():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    status, content_type, body = _http_get(
        "/dados/runs/pesquisa-receita-exemplo", LOG_AMOSTRA
    )
    payload = json.loads(body)
    assert status == 200
    assert "application/json" in content_type
    for chave in ("run", "eventos", "artefatos", "gates"):
        assert chave in payload, f"chave ausente em /dados/runs/<id>: {chave}"
    assert payload["run"]["id"] == "pesquisa-receita-exemplo"
    assert isinstance(payload["eventos"], list) and len(payload["eventos"]) > 0


def test_get_dados_runs_id_inexistente():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    import urllib.error
    try:
        _http_get("/dados/runs/missao-inexistente", LOG_AMOSTRA)
    except urllib.error.HTTPError as e:
        assert e.code == 404
    else:
        pytest.fail("esperado 404 para run inexistente")


def test_get_dados_agentes():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    status, content_type, body = _http_get("/dados/agentes", LOG_AMOSTRA)
    payload = json.loads(body)
    assert status == 200
    assert "application/json" in content_type
    assert isinstance(payload, list)
    assert len(payload) >= 1
    ids = {a["id"] for a in payload}
    assert "pesquisa-alfa" in ids
    ag = next(a for a in payload if a["id"] == "pesquisa-alfa")
    assert set(ag.keys()) == {"id", "papel", "chamadas", "falhas"}
    assert ag["papel"] == "pesquisador"
    assert ag["chamadas"] >= 1


def test_get_dados_custos():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    status, content_type, body = _http_get("/dados/custos", LOG_AMOSTRA)
    payload = json.loads(body)
    assert status == 200
    assert "application/json" in content_type
    for chave in ("por_run", "por_modelo", "total"):
        assert chave in payload, f"chave ausente em /dados/custos: {chave}"
    assert isinstance(payload["por_run"], list)
    assert isinstance(payload["por_modelo"], list)
    assert set(payload["total"].keys()) == {"custo_total", "tokens_total", "n_chamadas"}
    assert payload["total"]["custo_total"] is None


def test_get_dados_catalogo():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada — rode scripts/gerar_log_amostra.py")
    status, content_type, body = _http_get("/dados/catalogo", LOG_AMOSTRA)
    payload = json.loads(body)
    assert status == 200
    assert "application/json" in content_type
    assert isinstance(payload, list)
    # Não quebra mesmo se array vazio; se houver, respeita o schema.
    for item in payload:
        assert set(item.keys()) == {"id", "nome", "descricao", "subagentes", "versao"}


# ---------------------------------------------------------------------------
# Gates — GET /dados/gates e POST /dados/gates/<id> (contrato v1)
# ---------------------------------------------------------------------------
def _http_post(path: str, body: dict, log_path: Path, db_path: Path):
    """POST JSON; devolve (status, content_type, body_text) ou levanta HTTPError em 4xx."""
    painel.Handler.log_path = log_path
    painel.Handler.db_path = db_path
    data = json.dumps(body).encode("utf-8")
    with _TCPServerTeste(("127.0.0.1", 0), painel.Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}{path}"
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                corpo = resp.read().decode("utf-8")
                return resp.status, resp.headers.get("Content-Type", ""), corpo
        finally:
            server.shutdown()
            thread.join(timeout=3)


def _http_post_safe(path: str, body: dict, log_path: Path, db_path: Path):
    """POST que captura HTTPError (4xx) devolvendo (status, body)."""
    try:
        s, ct, b = _http_post(path, body, log_path, db_path)
        return s, b
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


_LOG_GATE_PENDENTE = [
    json.dumps({"t": 0.0, "seq": 1, "evento": "spec.recebida",
                "missao": "m-gate", "subagentes": 1}),
    json.dumps({"t": 0.1, "seq": 2, "evento": "portao.reprovado",
                "portao": "cobertura", "lacunas": ["falta x"]}),
    json.dumps({"t": 0.2, "seq": 3, "evento": "escalado", "para": "fundador"}),
]


def test_get_dados_gates():
    if not LOG_AMOSTRA.exists():
        pytest.skip("amostra não encontrada")
    status, content_type, body = _http_get("/dados/gates", LOG_AMOSTRA)
    payload = json.loads(body)
    assert status == 200
    assert "application/json" in content_type
    assert isinstance(payload, list)
    # Amostra: escalado seguido de decisao.fundador → nenhum pendente
    assert payload == []


def test_get_dados_gates_pendente(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(_LOG_GATE_PENDENTE) + "\n", encoding="utf-8")
    status, _ct, body = _http_get("/dados/gates", log)
    payload = json.loads(body)
    assert status == 200
    assert len(payload) == 1
    g = payload[0]
    assert set(g.keys()) == {"portao", "pergunta", "opcoes", "run", "estado"}
    assert g["portao"] == "cobertura"
    assert g["estado"] == "pendente"
    assert g["opcoes"] == ["prosseguir", "corrigir", "abortar"]
    assert "falta x" in g["pergunta"]


def test_post_dados_gates_valido(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(_LOG_GATE_PENDENTE) + "\n", encoding="utf-8")
    db = tmp_path / "motor.db"
    status, body = _http_post_safe("/dados/gates/cobertura", {"decisao": "prosseguir"}, log, db)
    assert status == 200
    resp = json.loads(body)
    assert resp == {"ok": True, "gate": "cobertura", "decisao": "prosseguir"}
    # valida gravação no SQLite
    import sqlite3
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute(
            "SELECT decisao, respondido_em FROM caixa WHERE id = ?", ("cobertura",)
        ).fetchone()
        assert row is not None
        assert row[0] == "prosseguir"
        assert row[1] is not None and row[1] != ""
    finally:
        conn.close()


def test_post_dados_gates_inexistente(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(_LOG_GATE_PENDENTE) + "\n", encoding="utf-8")
    db = tmp_path / "motor.db"
    status, _body = _http_post_safe(
        "/dados/gates/inexistente", {"decisao": "prosseguir"}, log, db
    )
    assert status == 404


def test_post_dados_gates_decisao_invalida(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(_LOG_GATE_PENDENTE) + "\n", encoding="utf-8")
    db = tmp_path / "motor.db"
    status, _body = _http_post_safe(
        "/dados/gates/cobertura", {"decisao": "invalidar"}, log, db
    )
    assert status == 400
