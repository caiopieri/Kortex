#!/usr/bin/env python3
"""Painel v0.5 — mapa orbital vivo da Meta-fábrica.

Uso: python3 motor_painel/painel.py  →  http://localhost:8378

Diferenças em relação ao v0.4 (painel da Fase 3 do vault):
- Não lê o Registry de .md no vault; lê apenas o log.jsonl da raiz do repo.
- Nós dinâmicos: subagentes, portões e executor global são extraídos dos
  eventos (paralelo.iniciado.subagentes, portao.*, executor.*) — não são
  hardcoded.
- Reconhece todos os tipos de evento do v0.5:
    spec.criada, spec.recebida,
    paralelo.iniciado (campo subagentes=[ids]),
    paralelo.concluido,
    executor.chamado, executor.respondeu, executor.erro,
    portao.aprovado, portao.reprovado (portao "verifier:<id>" e "cobertura"),
    modelo.falha, escalado,
    decisao.pendente, decisao.retomada, decisao.fundador, decisao.timeout,
    tarefa.concluida, tarefa.abortada.
- Função parse_eventos() exposta como importável (usada em tests/test_painel.py).
- Porta 8378 (v0.4 usava 8377).
"""
import json
import os
import sys
import http.server
import socketserver
from pathlib import Path

PORTA = 8378
BASE = Path(__file__).parent.resolve()
# log.jsonl fica na raiz do repo (um nível acima de motor_painel/)
LOG_PATH = BASE.parent / "log.jsonl"


# ---------------------------------------------------------------------------
# Lógica de parse — importável pelos testes
# ---------------------------------------------------------------------------

TIPOS_EVENTO = {
    "spec.criada", "spec.recebida",
    "paralelo.iniciado", "paralelo.concluido",
    "executor.chamado", "executor.respondeu", "executor.erro",
    "portao.aprovado", "portao.reprovado",
    "modelo.falha",
    "escalado",
    "decisao.pendente", "decisao.retomada", "decisao.fundador", "decisao.timeout",
    "tarefa.concluida", "tarefa.abortada",
}


def parse_linha(linha: str) -> dict | None:
    """Parseia uma linha JSONL. Retorna None se inválida ou vazia."""
    linha = linha.strip()
    if not linha:
        return None
    return json.loads(linha)  # levanta JSONDecodeError se inválido


def parse_eventos(log_path: str | Path | None = None) -> list[dict]:
    """Lê e parseia todas as linhas válidas de log.jsonl.

    Retorna lista de eventos (dict). Linhas vazias são ignoradas;
    linhas com JSON inválido levantam JSONDecodeError.
    """
    path = Path(log_path) if log_path is not None else LOG_PATH
    if not path.exists():
        return []
    eventos = []
    with open(path, encoding="utf-8") as f:
        for linha in f:
            ev = parse_linha(linha)
            if ev is not None:
                eventos.append(ev)
    return eventos


def grafo_do_log(eventos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Infere nós e arestas a partir dos eventos.

    Nós especiais fixos: "motor" (núcleo), "planner", "synthesizer",
    "global_evaluator".
    Nós dinâmicos: subagentes extraídos de paralelo.iniciado + executor.*
    Portões: extraídos de portao.*
    """
    nos_map: dict[str, dict] = {}
    arestas: list[dict] = []

    def garante_no(nid: str, tipo: str):
        if nid not in nos_map:
            nos_map[nid] = {"id": nid, "tipo": tipo}

    garante_no("motor", "nucleo")

    for ev in eventos:
        tipo_ev = ev.get("evento", "")

        # Spec
        if tipo_ev in ("spec.criada", "spec.recebida"):
            garante_no("planner", "executor")

        # Subagentes dinâmicos
        if tipo_ev == "paralelo.iniciado":
            subs = ev.get("subagentes", [])
            for sid in subs:
                garante_no(sid, "subagente")
                arestas.append({"de": "motor", "para": sid})

        # Executores nomeados (planner, synthesizer, global_evaluator, subagente por nome)
        if tipo_ev in ("executor.chamado", "executor.respondeu", "executor.erro"):
            exec_id = ev.get("executor", "")
            if exec_id:
                tipo_exec = "executor"
                if exec_id in ("planner", "synthesizer", "global_evaluator"):
                    tipo_exec = "executor"
                else:
                    tipo_exec = "subagente"
                garante_no(exec_id, tipo_exec)

        # Portões
        if tipo_ev in ("portao.aprovado", "portao.reprovado"):
            portao = ev.get("portao", "")
            if portao:
                garante_no(portao, "portao")
                # aresta do subagente associado (verifier:<id>)
                if portao.startswith("verifier:"):
                    sid = portao.split(":", 1)[1]
                    arestas.append({"de": sid, "para": portao})
                elif portao == "cobertura":
                    arestas.append({"de": "global_evaluator", "para": portao})

        # Decisão do fundador
        if tipo_ev in ("escalado", "decisao.fundador", "decisao.pendente",
                       "decisao.retomada", "decisao.timeout"):
            garante_no("fundador", "decisor")

        # Global evaluator aparece quando executor.chamado com executor=global_evaluator
        if tipo_ev == "executor.chamado" and ev.get("executor") == "global_evaluator":
            garante_no("global_evaluator", "executor")
            garante_no("cobertura", "portao")

        # Synthesizer
        if tipo_ev == "executor.chamado" and ev.get("executor") == "synthesizer":
            garante_no("synthesizer", "executor")

    return list(nos_map.values()), arestas


def dados_painel(log_path: str | Path | None = None) -> dict:
    """Retorna o payload completo para o frontend."""
    eventos = parse_eventos(log_path)
    nos, arestas = grafo_do_log(eventos)
    return {"nos": nos, "arestas": arestas, "eventos": eventos}


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------

HTML_PATH = BASE / "painel.html"


class Handler(http.server.BaseHTTPRequestHandler):
    log_path: Path = LOG_PATH  # substituível em testes

    def log_message(self, *a):
        pass  # silencia o log padrão do BaseHTTPRequestHandler

    def _json(self, obj: object):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/dados":
            return self._json(dados_painel(self.log_path))
        if self.path == "/healthz":
            return self._json({"ok": True})
        html = HTML_PATH.read_bytes()
        self._html(html)


def serve(porta: int = PORTA, log_path: Path = LOG_PATH):
    Handler.log_path = log_path
    with socketserver.TCPServer(("", porta), Handler) as s:
        s.allow_reuse_address = True
        print(f"Painel v0.5: http://localhost:{porta}", flush=True)
        s.serve_forever()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else PORTA
    serve(porta)
