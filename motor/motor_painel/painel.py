#!/usr/bin/env python3
"""Painel v0.5 — mapa orbital vivo da Meta-fábrica.

Uso: python3 motor_painel/painel.py  →  http://localhost:8378
"""
import json
import sys
import http.server
import socketserver
from urllib.parse import urlparse
from pathlib import Path
import re
import time
import sqlite3
from typing import Any, Optional, cast

PORTA = 8378
BASE = Path(__file__).parent.resolve()
# log.jsonl fica na raiz do repo (um nível acima de motor_painel/)
LOG_PATH = BASE.parent / "log.jsonl"
DB_PATH = BASE.parent / "motor.db"
APP_DIST = BASE / "app" / "dist"

# Preços padrão para cálculo de custos
DEFAULT_PRECOS = {
    "deepseek-reasoner": {"in_por_1k": 0.00055, "out_por_1k": 0.00219},
    "deepseek-chat": {"in_por_1k": 0.00014, "out_por_1k": 0.00028},
    "claude-3-5-sonnet": {"in_por_1k": 0.003, "out_por_1k": 0.015},
    "gemini-1.5-flash": {"in_por_1k": 0.000075, "out_por_1k": 0.0003},
    "gemini-1.5-pro": {"in_por_1k": 0.00125, "out_por_1k": 0.005},
    "gpt-4o": {"in_por_1k": 0.0025, "out_por_1k": 0.010},
    "gpt-4o-mini": {"in_por_1k": 0.00015, "out_por_1k": 0.0006},
}

PRECOS_PATH = BASE.parent / "precos.json"

def carregar_precos() -> dict:
    precos = dict(DEFAULT_PRECOS)
    if PRECOS_PATH.exists():
        try:
            with open(PRECOS_PATH, encoding="utf-8") as f:
                user_precos = json.load(f)
                if isinstance(user_precos, dict):
                    for k, v in user_precos.items():
                        if isinstance(v, dict) and "in_por_1k" in v and "out_por_1k" in v:
                            precos[k] = {
                                "in_por_1k": float(v["in_por_1k"]),
                                "out_por_1k": float(v["out_por_1k"])
                            }
        except Exception:
            pass
    return precos

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
    res = json.loads(linha)  # levanta JSONDecodeError se inválido
    return cast(Optional[dict[Any, Any]], res) if isinstance(res, dict) else None


def parse_eventos(log_path: str | Path | None = None) -> list[dict]:
    """Lê e parseia todas as linhas válidas de log.jsonl."""
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
    """Infere nós e arestas a partir dos eventos."""
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


def agrupar_eventos_por_run(eventos: list[dict]) -> list[list[dict]]:
    """Agrupa a lista de eventos sequenciais em blocos por run.
    Cada vez que o timestamp `t` diminui, identificamos o início de uma nova run.
    """
    if not eventos:
        return []
    runs_events = []
    current_run_events: list[dict] = []
    ultimo_t = None
    for ev in eventos:
        t = ev.get("t")
        if current_run_events and t is not None and ultimo_t is not None and t < ultimo_t:
            runs_events.append(current_run_events)
            current_run_events = []
        current_run_events.append(ev)
        if t is not None:
            ultimo_t = t
    if current_run_events:
        runs_events.append(current_run_events)
    return runs_events


def obter_runs(eventos: list[dict]) -> list[dict]:
    runs_events = agrupar_eventos_por_run(eventos)
    runs_metadata = []
    for idx, run_evs in enumerate(runs_events, start=1):
        # Tenta extrair id da run
        run_id = None
        objetivo = None
        for ev in run_evs:
            if "missao" in ev:
                run_id = ev["missao"]
            elif "run" in ev:
                run_id = ev["run"]
            if "objetivo" in ev:
                objetivo = ev["objetivo"]
                
        if not run_id:
            run_id = f"run_{idx}"
            
        # Determina o estado
        estado = "ativa"
        for ev in run_evs:
            ev_name = ev.get("evento")
            if ev_name == "tarefa.concluida":
                estado = "concluida"
                break
            elif ev_name == "tarefa.abortada":
                estado = "abortada"
                break
                
        # Custo
        custo = 0.0
        model_usages = [ev for ev in run_evs if ev.get("evento") == "modelo.uso"]
        if model_usages:
            precos = carregar_precos()
            for mu in model_usages:
                model = mu.get("modelo")
                prompt = mu.get("prompt_tokens", 0)
                completion = mu.get("completion_tokens", 0)
                if model in precos:
                    custo += (prompt / 1000.0) * precos[model]["in_por_1k"] + (completion / 1000.0) * precos[model]["out_por_1k"]
        else:
            acumulados = [float(ev["acumulado"]) for ev in run_evs if ev.get("acumulado") is not None]
            if acumulados:
                custo = max(acumulados)
                
        inicio = run_evs[0].get("t", 0.0) if run_evs else 0.0
        
        runs_metadata.append({
            "id": run_id,
            "objetivo": objetivo,
            "estado": estado,
            "inicio": inicio,
            "custo": custo,
            "n_eventos": len(run_evs)
        })
        
    return runs_metadata


def obter_gates_pendentes(eventos: list[dict]) -> list[dict]:
    runs_events = agrupar_eventos_por_run(eventos)
    gates_pendentes: list[dict] = []
    
    for idx, run_evs in enumerate(runs_events, start=1):
        run_id = None
        for ev in run_evs:
            if "missao" in ev:
                run_id = ev["missao"]
            elif "run" in ev:
                run_id = ev["run"]
        if not run_id:
            run_id = f"run_{idx}"
            
        active_gates = {}
        for i, ev in enumerate(run_evs):
            ev_name = ev.get("evento")
            if ev_name == "escalado" and ev.get("para") == "fundador":
                portao = ev.get("portao")
                if not portao:
                    for prev_ev in reversed(run_evs[:i]):
                        if prev_ev.get("evento") in ("portao.reprovado", "portao.aprovado"):
                            portao = prev_ev.get("portao")
                            if portao:
                                break
                    if not portao:
                        portao = "cobertura"
                
                pergunta = "Decisão necessária."
                opcoes = ["prosseguir", "corrigir", "abortar"]
                
                if portao == "cobertura":
                    for prev_ev in reversed(run_evs[:i]):
                        if prev_ev.get("evento") == "portao.reprovado" and prev_ev.get("portao") == "cobertura":
                            lacunas = prev_ev.get("lacunas", [])
                            if lacunas:
                                pergunta = f"Cobertura insuficiente. Lacunas: {', '.join(lacunas)}"
                            break
                            
                active_gates[portao] = {
                    "portao": portao,
                    "pergunta": pergunta,
                    "opcoes": opcoes,
                    "run": run_id,
                    "estado": "pendente"
                }
            elif ev_name == "decisao.pendente":
                portao = ev.get("portao", "cobertura")
                active_gates[portao] = {
                    "portao": portao,
                    "pergunta": ev.get("pergunta", "Decisão necessária."),
                    "opcoes": ev.get("opcoes") or ["prosseguir", "corrigir", "abortar"],
                    "run": run_id,
                    "estado": "pendente"
                }
            elif ev_name in ("decisao.fundador", "decisao.timeout"):
                portao = ev.get("portao")
                if portao:
                    active_gates.pop(portao, None)
                    
        gates_pendentes.extend(active_gates.values())
        
    return gates_pendentes


def obter_catalogo() -> list[dict]:
    caminhos_busca = [
        BASE.parent / "Registry",
        BASE.parent / "registry",
        BASE.parent / "exemplos" / "registro"
    ]
    pasta_reg = None
    for p in caminhos_busca:
        if p.exists() and p.is_dir():
            pasta_reg = p
            break
            
    if not pasta_reg:
        return []
        
    catalogo = []
    for caminho in sorted(pasta_reg.glob("*.md"), key=lambda x: x.name):
        try:
            texto = caminho.read_text(encoding="utf-8")
            linhas = texto.splitlines()
            if not linhas or linhas[0].strip() != "---":
                continue
            fim = next((i for i, linha in enumerate(linhas[1:], start=1) if linha.strip() == "---"), None)
            if fim is None:
                continue
                
            dados = {}
            for linha in linhas[1:fim]:
                linha = linha.strip()
                if not linha:
                    continue
                chave, sep, valor = linha.partition(":")
                if sep:
                    val_str = valor.strip()
                    if len(val_str) >= 2 and val_str[0] == val_str[-1] and val_str[0] in {"'", '"'}:
                        val_str = val_str[1:-1]
                    dados[chave.strip()] = val_str
            
            if dados.get("tipo") != "rota":
                continue
                
            corpo = "\n".join(linhas[fim+1:]).strip()
            
            sub_val = dados.get("subagentes", "[]")
            if isinstance(sub_val, str):
                if sub_val.startswith("[") and sub_val.endswith("]"):
                    try:
                        subagentes = json.loads(sub_val)
                    except Exception:
                        subagentes = [x.strip() for x in sub_val[1:-1].split(",") if x.strip()]
                else:
                    subagentes = [sub_val] if sub_val else []
            else:
                subagentes = list(sub_val)
                
            catalogo.append({
                "id": dados.get("nome", caminho.stem),
                "nome": dados.get("nome", caminho.stem),
                "descricao": corpo,
                "subagentes": subagentes,
                "versao": dados.get("versao", "1.0.0")
            })
        except Exception:
            pass
    return catalogo


def atualizar_nota_caixa(gate_id: str, decisao: str) -> bool:
    caminhos_busca = [
        BASE.parent,
        BASE.parent / "runs",
        BASE.parent / "caixa",
        BASE / "caixa"
    ]
    for pasta in caminhos_busca:
        if not pasta.exists():
            continue
        nota_path = pasta / f"PENDENTE — {gate_id}.md"
        if nota_path.exists():
            try:
                conteudo = nota_path.read_text(encoding="utf-8")
                novo_conteudo = re.sub(r"^decisao:[ \t]*.*$", f"decisao: {decisao}", conteudo, flags=re.M)
                nota_path.write_text(novo_conteudo, encoding="utf-8")
                return True
            except Exception:
                pass
    return False


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------

HTML_PATH = BASE / "painel.html"
GRAFO3D_HTML_PATH = BASE / "grafo3d.html"


class ReaproveitavelTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class Handler(http.server.BaseHTTPRequestHandler):
    log_path: Path = LOG_PATH  # substituível em testes
    db_path: Path = DB_PATH    # substituível em testes

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
        path = urlparse(self.path).path
        
        # 1. Endpoints do contrato de dados (/dados/*)
        if path == "/dados":
            return self._json(dados_painel(self.log_path))
            
        if path == "/dados/runs":
            eventos = parse_eventos(self.log_path)
            runs = obter_runs(eventos)
            return self._json(runs)
            
        if path.startswith("/dados/runs/"):
            run_id = path.split("/")[-1]
            eventos = parse_eventos(self.log_path)
            runs = obter_runs(eventos)
            run = next((r for r in runs if r["id"] == run_id), None)
            if not run:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Run nao encontrada")
                return
            
            # Filtra eventos desta run
            runs_events = agrupar_eventos_por_run(eventos)
            run_evs = []
            for idx, r_evs in enumerate(runs_events, start=1):
                rid = None
                for ev in r_evs:
                    if "missao" in ev:
                        rid = ev["missao"]
                    elif "run" in ev:
                        rid = ev["run"]
                if not rid:
                    rid = f"run_{idx}"
                if rid == run_id:
                    run_evs = r_evs
                    break
                    
            # Coleta gate-related events da run
            gates = [ev for ev in run_evs if ev.get("evento") in ("escalado", "decisao.pendente", "decisao.fundador", "decisao.timeout") or ev.get("evento", "").startswith("portao.")]
            
            # Coleta artefatos
            artefatos = []
            for ev in run_evs:
                if "artefato" in ev:
                    artefatos.append(ev["artefato"])
                elif "caminho" in ev and "artefato" in ev.get("evento", ""):
                    artefatos.append(ev["caminho"])
            
            return self._json({
                "run": run,
                "eventos": run_evs,
                "artefatos": artefatos,
                "gates": gates
            })
            
        if path == "/dados/gates":
            eventos = parse_eventos(self.log_path)
            gates = obter_gates_pendentes(eventos)
            return self._json(gates)
            
        if path == "/dados/agentes":
            eventos = parse_eventos(self.log_path)
            agentes_dict = {}
            for ev in eventos:
                ev_name = ev.get("evento")
                if ev_name == "executor.chamado":
                    exec_id = ev.get("executor")
                    if exec_id:
                        if exec_id not in agentes_dict:
                            agentes_dict[exec_id] = {
                                "id": exec_id,
                                "papel": ev.get("papel") or exec_id,
                                "chamadas": 0,
                                "falhas": 0
                            }
                        agentes_dict[exec_id]["chamadas"] += 1
                elif ev_name in ("executor.erro", "modelo.falha"):
                    exec_id = ev.get("executor")
                    if exec_id:
                        if exec_id not in agentes_dict:
                            agentes_dict[exec_id] = {
                                "id": exec_id,
                                "papel": exec_id,
                                "chamadas": 0,
                                "falhas": 0
                            }
                        agentes_dict[exec_id]["falhas"] += 1
            return self._json(list(agentes_dict.values()))
            
        if path == "/dados/custos":
            eventos = parse_eventos(self.log_path)
            precos = carregar_precos()
            runs_events = agrupar_eventos_por_run(eventos)
            
            total_custo = 0.0
            total_tokens = 0
            n_chamadas = 0
            
            por_run = []
            por_modelo = {}
            
            for idx, r_evs in enumerate(runs_events, start=1):
                rid = None
                for ev in r_evs:
                    if "missao" in ev:
                        rid = ev["missao"]
                    elif "run" in ev:
                        rid = ev["run"]
                if not rid:
                    rid = f"run_{idx}"
                    
                r_custo = 0.0
                r_tokens = 0
                r_chamadas = 0
                
                for ev in r_evs:
                    ev_name = ev.get("evento")
                    if ev_name == "executor.chamado":
                        n_chamadas += 1
                        r_chamadas += 1
                    elif ev_name == "modelo.uso":
                        prompt = ev.get("prompt_tokens", 0)
                        completion = ev.get("completion_tokens", 0)
                        tokens = ev.get("total_tokens", prompt + completion)
                        model = ev.get("modelo")
                        
                        cost = 0.0
                        if model and model in precos:
                            cost = (prompt / 1000.0) * precos[model]["in_por_1k"] + (completion / 1000.0) * precos[model]["out_por_1k"]
                            
                        total_custo += cost
                        total_tokens += tokens
                        r_custo += cost
                        r_tokens += tokens
                        
                        if model:
                            if model not in por_modelo:
                                por_modelo[model] = {"modelo": model, "custo_total": 0.0, "tokens_total": 0, "n_chamadas": 0}
                            por_modelo[model]["custo_total"] += cost
                            por_modelo[model]["tokens_total"] += tokens
                            por_modelo[model]["n_chamadas"] += 1
                            
                por_run.append({
                    "id": rid,
                    "custo_total": r_custo,
                    "tokens_total": r_tokens,
                    "n_chamadas": r_chamadas
                })
                
            return self._json({
                "por_run": por_run,
                "por_modelo": list(por_modelo.values()),
                "total": {
                    "custo_total": total_custo,
                    "tokens_total": total_tokens,
                    "n_chamadas": n_chamadas
                }
            })
            
        if path == "/dados/catalogo":
            catalogo = obter_catalogo()
            return self._json(catalogo)
            
        if path == "/healthz":
            return self._json({"ok": True})
            
        # 2. Servir a interface (React app ou painel.html original de fallback)
        if path == "/grafo3d":
            return self._html(GRAFO3D_HTML_PATH.read_bytes())
            
        if not APP_DIST.exists():
            return self._html(HTML_PATH.read_bytes())
            
        rel_path = path.lstrip("/")
        if not rel_path:
            rel_path = "index.html"
            
        try:
            # Resolve caminhos para evitar path traversal
            target_file = (APP_DIST / rel_path).resolve()
            dist_resolved = APP_DIST.resolve()
            if not target_file.is_relative_to(dist_resolved):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Acesso proibido (Path Traversal)")
                return
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Caminho invalido")
            return
            
        if not target_file.exists() or target_file.is_dir():
            target_file = APP_DIST / "index.html"
            
        if not target_file.exists():
            return self._html(HTML_PATH.read_bytes())
            
        ext = target_file.suffix.lower()
        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "text/javascript",
            ".jsx": "text/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon"
        }
        content_type = content_types.get(ext, "application/octet-stream")
        
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if "text" in content_type or "json" in content_type else content_type)
        body = target_file.read_bytes()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/dados/gates/"):
            # Validação de Origem para prevenir CSRF
            origin = self.headers.get("Origin")
            if origin:
                host = self.headers.get("Host", "")
                origin_clean = origin.replace("http://", "").replace("https://", "")
                if origin_clean != host and not (host.startswith("127.0.0.1") and origin_clean.startswith("localhost")):
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"Erro CSRF: Origem nao permitida")
                    return

            gate_id = path.split("/")[-1]
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode("utf-8"))
            except Exception:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"JSON invalido")
                return
                
            decisao = body.get("decisao")
            if not decisao:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"decisao obrigatoria")
                return
                
            eventos = parse_eventos(self.log_path)
            gates_pendentes = obter_gates_pendentes(eventos)
            gate = next((g for g in gates_pendentes if g["portao"] == gate_id), None)
            
            if not gate:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Gate nao encontrado ou nao esta pendente")
                return
                
            if decisao not in gate["opcoes"]:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Decisao invalida. Opcoes permitidas: {gate['opcoes']}".encode("utf-8"))
                return
                
            db_path = getattr(self, "db_path", DB_PATH)
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("CREATE TABLE IF NOT EXISTS caixa (id TEXT PRIMARY KEY, decisao TEXT, respondido_em TEXT)")
                conn.execute(
                    "INSERT OR REPLACE INTO caixa (id, decisao, respondido_em) VALUES (?, ?, ?)",
                    (gate_id, decisao, time.strftime('%Y-%m-%d %H:%M'))
                )
                conn.commit()
                conn.close()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Erro ao salvar no banco: {e}".encode("utf-8"))
                return
                
            atualizar_nota_caixa(gate_id, decisao)
            
            return self._json({"ok": True, "gate": gate_id, "decisao": decisao})
            
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Endpoint nao encontrado")


def serve(porta: int = PORTA, log_path: Path = LOG_PATH, db_path: Path = DB_PATH):
    Handler.log_path = log_path
    Handler.db_path = db_path
    with ReaproveitavelTCPServer(("", porta), Handler) as s:
        print(f"Painel v0.5: http://localhost:{porta}", flush=True)
        s.serve_forever()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else PORTA
    serve(porta)
