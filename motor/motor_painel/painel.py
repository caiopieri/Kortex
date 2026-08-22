#!/usr/bin/env python3
"""Painel v0.5 — mapa orbital vivo da Meta-fábrica.

Uso: python3 motor_painel/painel.py  →  http://localhost:8378
"""
import json
import os
import shutil
import subprocess
import sys
import http.server
import socketserver
from urllib.parse import parse_qs, unquote, urlparse
from pathlib import Path
import re
import time
import sqlite3
from typing import Any, NoReturn, Optional, cast
from uuid import uuid4

from motor.eventos_schema import valido

PORTA = 8378
BASE = Path(__file__).parent.resolve()
# log.jsonl na raiz é mantido apenas como legado de leitura (um nível acima de
# motor_painel/); missões novas ficam em RUNS_PATH/<run_id>/log.jsonl.


def _valor_env(nome: str) -> str | None:
    """Retorna somente overrides afirmados com conteúdo não vazio."""
    return os.environ.get(nome) or None


def _resolver_caminho(
    nome: str,
    padrao_relativo_a_base: str | None,
    *,
    valor: str | None = None,
    raiz: Path | None = None,
) -> Path:
    bruto = _valor_env(nome) if valor is None else (valor or None)
    if bruto is None:
        if padrao_relativo_a_base is None:
            raise ValueError(f"{nome} sem valor")
        return (BASE / padrao_relativo_a_base).resolve()
    caminho = Path(bruto).expanduser()
    if raiz is not None:
        raiz_absoluta = raiz.resolve()
        candidato = (
            (raiz_absoluta / caminho).resolve()
            if not caminho.is_absolute()
            else caminho.resolve()
        )
        if not candidato.is_relative_to(raiz_absoluta):
            raise ValueError(f"{nome} fora do workspace; recebeu {bruto!r}")
        return candidato
    if not caminho.is_absolute():
        raise ValueError(
            f"{nome} deve ser um caminho absoluto; recebeu {bruto!r}"
        )
    return caminho


LOG_PATH = _resolver_caminho("MOTOR_LOG", "../log.jsonl")
RUNS_PATH = _resolver_caminho("MOTOR_WORKSPACE", "../runs")
DB_PATH = BASE.parent / "motor.db"
APP_DIST = BASE / "app" / "dist"

# ---------------------------------------------------------------------------
# Lógica de parse — importável pelos testes
# ---------------------------------------------------------------------------


def _constante_json_invalida(valor: str) -> NoReturn:
    raise ValueError(f"constante fora do JSON estrito: {valor}")


def parse_linha(linha: str) -> dict | None:
    """Parseia uma linha JSONL. Retorna None se inválida ou vazia."""
    linha = linha.strip()
    if not linha:
        return None
    res = json.loads(linha, parse_constant=_constante_json_invalida)
    return cast(Optional[dict[Any, Any]], res) if isinstance(res, dict) else None


def parse_eventos(log_path: str | Path | None = None, *, estrito: bool = False) -> list[dict]:
    """Lê linhas completas; em modo estrito, ausência/vazio vira erro declarado."""
    path = Path(log_path) if log_path is not None else LOG_PATH
    if not path.is_file():
        if estrito:
            raise FileNotFoundError(f"ledger nao encontrado: {path}")
        return []
    if estrito and path.stat().st_size == 0:
        raise ValueError(f"ledger vazio: {path}")
    eventos: list[dict] = []
    ultimo_seq = 0
    ultimo_t: int | float = 0
    conteudo = path.read_bytes()
    linhas = conteudo.split(b"\n")
    linhas_completas = linhas[:-1]
    for numero_linha, linha in enumerate(linhas_completas, start=1):
        texto = linha.decode("utf-8")
        ev = parse_linha(texto)
        if ev is None:
            if texto.strip():
                raise ValueError(f"linha {numero_linha} nao contem evento")
            continue
        if "seq" in ev:
            if not valido(ev):
                raise ValueError(f"linha {numero_linha} fora do schema v2")
            if ev["seq"] != ultimo_seq + 1:
                raise ValueError(f"sequencia invalida na linha {numero_linha}")
            if ev["t"] < ultimo_t:
                raise ValueError(f"tempo regressivo na linha {numero_linha}")
            ultimo_seq = ev["seq"]
            ultimo_t = ev["t"]
        eventos.append(ev)
    if estrito and not eventos:
        raise ValueError(f"ledger sem eventos: {path}")
    return eventos


def grafo_do_log(eventos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Projeta o grafo canônico do ledger.

    O payload de ``/dados`` é a fonte compartilhada pelas superfícies. Nós só
    entram quando o ledger os declara (ou quando um evento de execução os
    nomeia), e arestas de fluxo só entram quando o ledger as emite. Eventos de
    portão ainda dão a relação visual do portão com seu alvo; a lista é
    deduplicada porque um retry não cria uma segunda relação topológica.
    """
    nos_map: dict[str, dict] = {}
    arestas: list[dict] = []
    arestas_vistas: set[tuple[str, str]] = set()

    def garante_no(nid: str, tipo: str, papel: str | None = None) -> None:
        if not isinstance(nid, str) or not nid.strip():
            return
        if nid not in nos_map:
            nos_map[nid] = {"id": nid, "tipo": tipo}
            if nid != "motor":
                nos_map[nid]["papel"] = papel
                nos_map[nid]["onda"] = None
        elif papel and not nos_map[nid].get("papel"):
            nos_map[nid]["papel"] = papel

    def garante_aresta(de: str, para: str) -> None:
        chave = (de, para)
        if de in nos_map and para in nos_map and chave not in arestas_vistas:
            arestas_vistas.add(chave)
            arestas.append({"de": de, "para": para})

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
                garante_aresta("motor", sid)

        # Grafo de dependências: esta é a declaração moderna da topologia.
        if tipo_ev == "grafo_dep.iniciado":
            for sid in ev.get("subagentes", []):
                garante_no(sid, "subagente")
                garante_aresta("motor", sid)

        if tipo_ev == "onda.iniciada":
            for sid in ev.get("ids", []):
                garante_no(sid, "subagente")

        # Arestas de fluxo são fatos do ledger, não inferência do painel.
        if tipo_ev == "aresta.fluxo":
            garante_aresta(ev.get("de", ""), ev.get("para", ""))

        # Executores nomeados (planner, synthesizer, global_evaluator, subagente por nome)
        if tipo_ev in ("executor.chamado", "executor.respondeu", "executor.erro"):
            exec_id = ev.get("executor", "")
            if exec_id:
                tipo_exec = "executor"
                if exec_id in ("planner", "synthesizer", "global_evaluator"):
                    tipo_exec = "executor"
                else:
                    tipo_exec = "subagente"
                garante_no(exec_id, tipo_exec, ev.get("papel"))

        if tipo_ev == "validador.rodou":
            garante_no(ev.get("id", ""), "validador", "validador")

        # Portões
        if tipo_ev in ("portao.aprovado", "portao.reprovado"):
            portao = ev.get("portao", "")
            if portao:
                garante_no(portao, "portao")
                # aresta do subagente associado (verifier:<id>)
                if portao.startswith("verifier:"):
                    sid = portao.split(":", 1)[1]
                    garante_aresta(sid, portao)
                elif portao == "cobertura":
                    garante_no("global_evaluator", "executor")
                    garante_aresta("global_evaluator", portao)
                elif portao.startswith("dependencias:"):
                    sid = portao.split(":", 1)[1]
                    garante_aresta(sid, portao)

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

    # A onda é a única camada topológica emitida pelo motor. Nós sem onda ficam
    # depois das ondas declaradas, de forma determinística.
    camada = 0
    for ev in eventos:
        if ev.get("evento") != "onda.iniciada":
            continue
        for sid in ev.get("ids", []):
            if sid in nos_map and sid != "motor" and nos_map[sid].get("onda") is None:
                nos_map[sid]["onda"] = camada
        camada += 1
    for no in nos_map.values():
        if no["id"] != "motor" and no.get("onda") is None:
            no["onda"] = camada

    motor = nos_map.pop("motor")
    nos = [motor] + sorted(nos_map.values(), key=lambda no: (no.get("onda", 0), no["id"]))
    return nos, arestas


RUN_LEGADO_SEM_PROVENIENCIA = "legado:sem-proveniencia"


def _identidade_run(evento: dict) -> str | None:
    run_id = evento.get("run_id")
    return run_id if isinstance(run_id, str) and run_id else None


def agrupar_eventos_por_run(eventos: list[dict]) -> list[list[dict]]:
    """Agrupa por ``run_id`` declarado; legado fica num único balde.

    ``seq`` e ``t`` são locais ao arquivo e não são identidade. Uma linha sem
    ``run_id`` é deliberadamente não atribuível: ela não é repartida por janela,
    caminho ou missão inferida.
    """
    grupos: dict[str, list[dict]] = {}
    for evento in eventos:
        identidade = _identidade_run(evento) or RUN_LEGADO_SEM_PROVENIENCIA
        grupos.setdefault(identidade, []).append(evento)
    return list(grupos.values())


def _runs_do_log(eventos: list[dict]) -> list[list[dict]]:
    """Separa runs pela identidade do envelope, preservando logs legados."""
    return agrupar_eventos_por_run(eventos)


def _id_do_grupo(eventos: list[dict]) -> str:
    for evento in eventos:
        run_id = _identidade_run(evento)
        if run_id:
            return run_id
    return RUN_LEGADO_SEM_PROVENIENCIA


def _run_canonica(eventos: list[dict], indice: int) -> dict:
    nos, arestas = grafo_do_log(eventos)
    seqs = [ev["seq"] for ev in eventos if isinstance(ev.get("seq"), int)]
    seq_de = seqs[0] if seqs else None
    specs = [ev for ev in eventos if ev.get("evento") == "spec.recebida"]
    multiplas_runs = len(specs) > 1
    fim = next(
        (ev for ev in reversed(eventos) if ev.get("evento") in ("tarefa.concluida", "tarefa.abortada")),
        None,
    )
    resumo = {
        "fonte": "cli",
        "id": _id_do_grupo(eventos),
        "perfil": next((ev.get("perfil") for ev in eventos if ev.get("evento") == "run.perfil"), None),
        "seqDe": seq_de,
        "seqAte": seqs[-1] if seqs else None,
        "missao": None if multiplas_runs else specs[0].get("missao") if specs else None,
        "desfecho": None if multiplas_runs else fim.get("evento") if fim else "aberta",
        "motivoDoFim": None if multiplas_runs else fim.get("motivo") if fim else None,
        "eventos": eventos,
        "nos": nos,
        "arestas": arestas,
    }
    if multiplas_runs:
        resumo["runs_contidas"] = len(specs)
    return resumo


def dados_painel(
    log_path: str | Path | None = None,
    *,
    eventos: list[dict] | None = None,
) -> dict:
    """Retorna o payload completo para o frontend."""
    if eventos is None:
        eventos = parse_eventos(log_path)
    nos, arestas = grafo_do_log(eventos)
    dados = {"nos": nos, "arestas": arestas, "eventos": eventos}
    if eventos:
        dados["runs"] = [_run_canonica(run, i) for i, run in enumerate(_runs_do_log(eventos), 1)]
    return dados


def obter_runs(eventos: list[dict]) -> list[dict]:
    runs_events = agrupar_eventos_por_run(eventos)
    runs_metadata = []
    for idx, run_evs in enumerate(runs_events, start=1):
        run_id = _id_do_grupo(run_evs)
        specs = [ev for ev in run_evs if ev.get("evento") == "spec.recebida"]
        multiplas_runs = len(specs) > 1
        objetivo = None
        missao = None
        for ev in run_evs:
            if "objetivo" in ev:
                objetivo = ev["objetivo"]
            if missao is None and "missao" in ev:
                missao = ev["missao"]
            
        # Determina o estado
        estado = None if multiplas_runs else "ativa"
        for ev in run_evs:
            ev_name = ev.get("evento")
            if not multiplas_runs and ev_name == "tarefa.concluida":
                estado = "concluida"
                break
            elif not multiplas_runs and ev_name == "tarefa.abortada":
                estado = "abortada"
                break
                
        # Telemetria de tokens nao possui autoridade monetaria.
        custo = None
                
        inicio = None if multiplas_runs else run_evs[0].get("t", 0.0) if run_evs else 0.0

        resumo = {
            "id": run_id,
            "missao": None if multiplas_runs else missao,
            "objetivo": objetivo,
            "estado": estado,
            "inicio": inicio,
            "custo": custo,
            "n_eventos": len(run_evs)
        }
        if multiplas_runs:
            resumo["runs_contidas"] = len(specs)
        runs_metadata.append(resumo)
        
    return runs_metadata


def _resumo_run(run_id: str, eventos: list[dict]) -> dict:
    """Deriva um resumo sem substituir identidade declarada pela pasta."""
    resumo = obter_runs(eventos)
    if resumo:
        resultado = dict(resumo[0])
    else:
        resultado = {
            "objetivo": None,
            "estado": None,
            "inicio": None,
            "custo": None,
            "n_eventos": 0,
        }
    declarado = _id_do_grupo(eventos)
    if declarado != RUN_LEGADO_SEM_PROVENIENCIA and declarado != run_id:
        resultado.update({
            "id": declarado,
            "estado": "log_invalido",
            "erro": f"run_id {declarado!r} diverge do diretorio {run_id!r}",
        })
    else:
        resultado["id"] = run_id if declarado == RUN_LEGADO_SEM_PROVENIENCIA else declarado
    resultado["n_eventos"] = len(eventos)
    return resultado


def _registros_legado(eventos: list[dict]) -> list[dict]:
    """Mantém legado num balde e preserva identidades declaradas."""
    registros: list[dict] = []
    for grupo in agrupar_eventos_por_run(eventos):
        resumo = obter_runs(grupo)
        if not resumo:
            continue
        run = resumo[0]
        if run["id"] == RUN_LEGADO_SEM_PROVENIENCIA:
            run = {**run, "proveniencia": "ausente"}
        registros.append({"run": run, "eventos": grupo})
    return registros


def _runs_do_workspace(runs_path: str | Path, legado: str | Path | None = None) -> list[dict]:
    """Lê cada ``<workspace>/<run_id>/log.jsonl`` sem juntar sequências distintas."""
    raiz = Path(runs_path)
    registros: list[dict] = []
    if raiz.is_dir() and not raiz.is_symlink():
        for diretorio in sorted(raiz.iterdir(), key=lambda item: item.name):
            if (not diretorio.is_dir() or diretorio.is_symlink()
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", diretorio.name)
                    or ".." in diretorio.name):
                continue
            caminho = diretorio / "log.jsonl"
            if caminho.is_symlink() or not caminho.is_file():
                continue
            try:
                eventos = parse_eventos(caminho)
                resumo = _resumo_run(diretorio.name, eventos)
                registros.append({"run": resumo, "eventos": eventos})
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as erro:
                registros.append({
                    "run": {
                        "id": diretorio.name,
                        "estado": "log_invalido",
                        "objetivo": None,
                        "inicio": 0.0,
                        "custo": None,
                        "n_eventos": 0,
                        "erro": str(erro),
                    },
                    "eventos": [],
                })

    legado_path = Path(legado) if legado is not None else None
    if legado_path is not None and legado_path.is_file() and not legado_path.is_symlink():
        try:
            eventos = parse_eventos(legado_path)
            ids_workspace = {registro["run"]["id"] for registro in registros}
            for registro in _registros_legado(eventos):
                if registro["run"]["id"] in ids_workspace:
                    registro["run"]["id"] = f"legacy:{registro['run']['id']}"
                registros.append(registro)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as erro:
            registros.append({
                "run": {
                    "id": "legacy-root",
                    "estado": "log_invalido",
                    "objetivo": None,
                    "inicio": 0.0,
                    "custo": None,
                    "n_eventos": 0,
                    "erro": str(erro),
                },
                "eventos": [],
            })
    return registros


def obter_gates_pendentes(eventos: list[dict]) -> list[dict]:
    # Eventos v1 permanecem visiveis, mas nunca possuem autoridade operacional.
    runs_events = agrupar_eventos_por_run([ev for ev in eventos if "seq" in ev])
    gates_pendentes: list[dict] = []
    
    for idx, run_evs in enumerate(runs_events, start=1):
        run_id = _id_do_grupo(run_evs)
            
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


def _pasta_registro() -> Path | None:
    """Localiza a pasta do registry, ou None se não houver."""
    for p in (BASE.parent / "Registry", BASE.parent / "registro",
              BASE.parent / "registry", BASE.parent / "exemplos" / "registro"):
        if p.exists() and p.is_dir():
            return p
    return None


def _frontmatter_registro(caminho: Path) -> dict | None:
    """Lê o frontmatter YAML-ish de uma entidade do registry."""
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not linhas or linhas[0].strip() != "---":
        return None
    fim = next((i for i, linha in enumerate(linhas[1:], start=1)
                if linha.strip() == "---"), None)
    if fim is None:
        return None
    dados: dict[str, str] = {}
    for linha in linhas[1:fim]:
        chave, sep, valor = linha.strip().partition(":")
        if not sep:
            continue
        val = valor.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        dados[chave.strip()] = val
    return dados


def _lista_frontmatter(valor: str | None) -> list[str]:
    if not valor:
        return []
    bruto = valor.strip()
    if bruto.startswith("[") and bruto.endswith("]"):
        bruto = bruto[1:-1]
    return [item.strip().strip("'\"") for item in bruto.split(",") if item.strip()]


def obter_inventario() -> list[dict]:
    """Entidades do registry — a fonte é o disco, não o log.

    Retorna [] quando não há registry: estado vazio honesto, sem inventar.
    """
    pasta = _pasta_registro()
    if pasta is None:
        return []
    inventario = []
    for caminho in sorted(pasta.glob("*.md"), key=lambda x: x.name):
        dados = _frontmatter_registro(caminho)
        if not dados:
            continue
        inventario.append({
            "id": dados.get("nome", caminho.stem),
            "tipo": dados.get("tipo", "desconhecido"),
            "papel": _lista_frontmatter(dados.get("papeis")),
            "origem": str(caminho.relative_to(BASE.parent)),
        })
    return inventario


# Como cada transporte comprova credencial. CLI = a própria auth da ferramenta
# (basta o executável existir); chave = variável de ambiente definida.
_CREDENCIAL_POR_TRANSPORTE: dict[str, tuple[str, str]] = {
    "claude-cli": ("cli", "claude"),
    "codex": ("cli", "codex"),
    "opencode": ("cli", "opencode"),
    "openai-compat": ("env", "OPENAI_API_KEY"),
}


def obter_conexoes() -> list[dict]:
    """Conexões da fábrica com provedores de modelo, do registry.

    NUNCA expõe o segredo — só o fato `tem_credencial`. Para transporte por CLI
    a prova é o executável estar no PATH; para chave, a variável estar definida.
    Transporte desconhecido responde `None`: não sabemos, e mentir "sim" ou
    "não" seria pior.
    """
    pasta = _pasta_registro()
    if pasta is None:
        return []
    conexoes = []
    for caminho in sorted(pasta.glob("*.md"), key=lambda x: x.name):
        dados = _frontmatter_registro(caminho)
        if not dados or dados.get("tipo") != "modelo-executor":
            continue
        transporte = dados.get("transporte", "")
        regra = _CREDENCIAL_POR_TRANSPORTE.get(transporte)
        if regra is None:
            tem_credencial = None
        elif regra[0] == "cli":
            tem_credencial = shutil.which(regra[1]) is not None
        else:
            tem_credencial = bool(os.environ.get(regra[1]))
        conexoes.append({
            "id": caminho.stem,
            "nome": dados.get("nome", caminho.stem),
            "tipo": transporte or "desconhecido",
            "tem_credencial": tem_credencial,
            "origem": str(caminho.relative_to(BASE.parent)),
        })
    return conexoes


def obter_catalogo() -> list[dict]:
    # Usa `_pasta_registro()` em vez de repetir a busca: a lista local aqui
    # divergia dela (nao continha "registro"), entao duas funcoes do mesmo
    # arquivo respondiam diferente para "onde fica o registry".
    pasta_reg = _pasta_registro()
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
                # `versao` ausente sai None, nao "1.0.0". Os arquivos do
                # registro nao declaram versao; inventar uma faz a tela afirmar
                # um fato de versionamento que ninguem escreveu (issue #23).
                "versao": dados.get("versao") or None,
            })
        except Exception:
            pass
    return catalogo


# ---------------------------------------------------------------------------
# Órfãos — o que existe em disco e o ledger não explica
# ---------------------------------------------------------------------------

# Debris de ferramenta que cai dentro de artefatos/ e não é produto da fábrica.
# Contá-los como artefato infla o número e o torna inútil: numa medição real
# eram 109 arquivos de ferramenta contra 49 de produto. O filtro fica aqui, no
# claro, e a tela declara que ele existe — em vez de ficar escondido no olho de
# quem lê o diretório.
_DEBRIS = ("__pycache__", ".pytest_cache", ".git", ".venv", "node_modules")


def _chave_de_artefato(caminho: str | Path) -> tuple[str, str] | None:
    """Identidade estável de um artefato: ``(run_id, resto)`` relativo a ``artefatos/``.

    NÃO comparar por caminho absoluto. O ``caminho`` gravado no evento é
    absoluto e aponta para o checkout onde a run rodou; o mesmo repositório
    clonado noutro lugar faria todo artefato virar órfão de uma vez. A parte
    estável é o trecho a partir de ``<run_id>/artefatos/``.
    """
    partes = Path(caminho).parts
    if "artefatos" not in partes:
        return None
    i = partes.index("artefatos")
    # A própria pasta `artefatos/`, sem arquivo dentro, devolvia ``(run, "")`` —
    # uma chave que nomeia uma run e um artefato vazio. Não é artefato nenhum.
    if i == len(partes) - 1:
        return None
    if i == 0:
        return None
    return (partes[i - 1], "/".join(partes[i + 1:]))


def orfaos_de_artefato(eventos: list[dict], runs_path: str | Path) -> dict:
    """Conta o que o disco tem e o ledger não explica. NÃO inventa evento.

    Motivo (issue #22): o ledger não era durável. Numa medição sobre o checkout
    de produção, 34 runs em disco e o log explicava 26; 49 artefatos de produto
    e 40 com evento. Uma superfície que lista só o que o ledger explica é
    silenciosamente incompleta — e "completo sem procedência" seria pior.
    Então: mostra-se o que o ledger explica, e declara-se o resto **como resto**.

    O órfão sai com o caminho e nada mais. Não recebe run, tipo nem tempo
    derivados do diretório: existir em disco não é existir no ledger, e inferir
    o evento a partir do arquivo é exatamente a reconstrução que a regra
    canônica proíbe.
    """
    raiz = Path(runs_path)
    com_evento = {
        chave
        for ev in eventos
        if ev.get("evento") == "artefato.atualizou" and ev.get("caminho")
        for chave in [_chave_de_artefato(ev["caminho"])]
        if chave is not None
    }

    orfaos: list[str] = []
    em_disco = 0
    debris = 0
    runs_em_disco: set[str] = set()
    runs_com_log: set[str] = set()

    if raiz.is_dir() and not raiz.is_symlink():
        for diretorio in sorted(raiz.iterdir(), key=lambda item: item.name):
            if not diretorio.is_dir() or diretorio.is_symlink():
                continue
            tem_log = (diretorio / "log.jsonl").is_file()
            tem_artefatos = (diretorio / "artefatos").is_dir()
            # Nem toda pasta sob runs/ e uma run. Medido em producao: `caixa`,
            # `despachos`, `orcamento` e `lift-docs-*` moram ali e sao outra
            # coisa. Chama-las de "run orfa" seria inventar run a partir de nome
            # de diretorio — o espelho exato do defeito que esta funcao existe
            # para corrigir. Sem log e sem artefatos/, nao ha evidencia de que
            # foi uma run, entao nao se afirma que foi.
            if not tem_log and not tem_artefatos:
                continue
            runs_em_disco.add(diretorio.name)
            if tem_log:
                runs_com_log.add(diretorio.name)
            for arquivo in sorted(diretorio.glob("artefatos/**/*")):
                if not arquivo.is_file() or arquivo.is_symlink():
                    continue
                if any(parte in _DEBRIS for parte in arquivo.parts):
                    debris += 1
                    continue
                em_disco += 1
                chave = _chave_de_artefato(arquivo)
                if chave is not None and chave not in com_evento:
                    orfaos.append(f"{chave[0]}/artefatos/{chave[1]}")

    runs_explicadas = runs_em_disco & (runs_com_log | {chave[0] for chave in com_evento})
    return {
        "artefatos_em_disco": em_disco,
        "artefatos_com_evento": em_disco - len(orfaos),
        "artefatos_orfaos": len(orfaos),
        "arquivos_de_ferramenta_ignorados": debris,
        "runs_em_disco": len(runs_em_disco),
        "runs_explicadas": len(runs_explicadas),
        "runs_orfas": sorted(runs_em_disco - runs_explicadas),
        # Lista truncada: o número acima é o fato, esta é só a amostra que cabe
        # na tela. Truncar em silêncio faria a tela mentir por omissão.
        "amostra": sorted(orfaos)[:50],
        "amostra_truncada": len(orfaos) > 50,
    }


def _pid_vivo(pid: int) -> bool:
    """True se o processo com este pid existe (os.kill(pid, 0))."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe, mas é de outro usuário
    return True


def _ler_pid_lock(lock: Path) -> int | None:
    """Lê o pid gravado no lock de despacho; None se ausente/ilegível."""
    if not lock.exists():
        return None
    try:
        return int(lock.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


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

_RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _desde_byte(query: str) -> int:
    """Valida o deslocamento externo sem aceitar uma leitura ambígua."""
    valores = parse_qs(query, keep_blank_values=True).get("desde_byte", [])
    if len(valores) > 1 or (valores and not re.fullmatch(r"[0-9]+", valores[0])):
        raise ValueError("desde_byte deve ser um inteiro nao-negativo")
    return int(valores[0]) if valores else 0


def _ler_snapshot_fd(fd: int) -> tuple[bytes, int]:
    """Lê no máximo o tamanho observado no mesmo fd somente-leitura."""
    tamanho_observado = os.fstat(fd).st_size
    if hasattr(os, "pread"):
        dados = os.pread(fd, tamanho_observado, 0)
    else:  # pragma: no cover - fallback para plataformas sem pread
        os.lseek(fd, 0, os.SEEK_SET)
        dados = os.read(fd, tamanho_observado)
    # Um truncamento concorrente pode devolver menos bytes que o fstat inicial.
    # O header acompanha o corpo efetivamente capturado, nunca promete bytes que
    # não foram lidos; crescimento fica para a próxima requisição.
    return dados, len(dados)


def _offset_alinhado(dados: bytes, offset: int) -> bool:
    """Offsets válidos começam no início ou logo após uma linha completa."""
    return offset == 0 or offset == len(dados) or dados[offset - 1:offset] == b"\n"

# Rotas que EXISTIRAM e nao existem mais. A mensagem diz para onde a capacidade
# foi, porque 404 mudo faz o operador achar que o painel esta quebrado.
ROTAS_REMOVIDAS = {
    "/grafo3d": (
        b"rota removida: o grafo 3D agora e um modo de vista do canvas, "
        b"sobre a mesma projecao do ledger que o 2D"
    ),
}


class ReaproveitavelTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class Handler(http.server.BaseHTTPRequestHandler):
    log_path: Path = LOG_PATH  # substituível em testes
    runs_path: Path = RUNS_PATH  # substituível em testes
    db_path: Path = DB_PATH    # substituível em testes
    despachos_dir: Path = RUNS_PATH / "despachos"  # substituível em testes

    def log_message(self, *a):
        pass  # silencia o log padrão do BaseHTTPRequestHandler

    def _json(self, obj: object):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _origem_permitida(self) -> bool:
        """Validação de Origem para prevenir CSRF (mesmo padrão nos POSTs)."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        origin_clean = origin.replace("http://", "").replace("https://", "")
        if origin_clean != host and not (host.startswith("127.0.0.1") and origin_clean.startswith("localhost")):
            return False
        return True

    def _erro(self, status: int, msg: bytes):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(msg)

    def _html(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _responder_ledger(
        self,
        status: int,
        body: bytes,
        tamanho: int,
        *,
        offset_corrigido: int | None = None,
    ):
        self.send_response(status)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Ledger-Tamanho", str(tamanho))
        if offset_corrigido is not None:
            self.send_header("X-Ledger-Offset-Corrigido", str(offset_corrigido))
        self.end_headers()
        self.wfile.write(body)

    def _caminho_ledger_run(self, trecho: str) -> Path:
        """Resolve um run_id sem permitir caminho ou symlink fora do workspace."""
        run_id = unquote(trecho)
        if (
            not _RUN_ID_RE.fullmatch(run_id)
            or Path(run_id).is_absolute()
            or "/" in run_id
            or "\\" in run_id
        ):
            raise ValueError("run_id invalido")
        raiz = self.runs_path.resolve()
        diretorio = _resolver_caminho("run_id", None, valor=run_id, raiz=raiz)
        caminho = (diretorio / "log.jsonl").resolve()
        if not caminho.is_relative_to(raiz):
            raise ValueError("run_id fora do workspace")
        return caminho

    def _servir_ledger(self, caminho: Path, *, raiz: bool, desde: int):
        """Transporta bytes de um ledger sem parsear, reparar ou escrever."""
        try:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            # A raiz é um caminho de configuração confiável; para logs por run,
            # O_NOFOLLOW fecha a última janela de troca de symlink após resolve().
            if not raiz:
                flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(caminho, flags)
        except FileNotFoundError:
            if raiz and _valor_env("MOTOR_LOG") is None:
                return self._responder_ledger(200, b"", 0)
            return self._erro(503 if raiz else 404, b"ledger nao disponivel")
        except (OSError, ValueError):
            if raiz and _valor_env("MOTOR_LOG") is None:
                return self._responder_ledger(200, b"", 0)
            return self._erro(503 if raiz else 404, b"ledger nao disponivel")

        try:
            try:
                dados, tamanho = _ler_snapshot_fd(fd)
            except OSError:
                if raiz and _valor_env("MOTOR_LOG") is None:
                    return self._responder_ledger(200, b"", 0)
                return self._erro(503 if raiz else 404, b"ledger nao disponivel")
        finally:
            os.close(fd)

        if raiz and tamanho == 0 and _valor_env("MOTOR_LOG") is not None:
            return self._erro(503, b"ledger configurado indisponivel: ledger vazio")
        if desde > tamanho:
            return self._responder_ledger(200, b"", tamanho)
        if not _offset_alinhado(dados, desde):
            anterior = dados.rfind(b"\n", 0, desde) + 1
            return self._responder_ledger(
                416,
                b"desde_byte nao esta no inicio de uma linha completa",
                tamanho,
                offset_corrigido=anterior,
            )
        return self._responder_ledger(200, dados[desde:], tamanho)

    def _get_ledger(self, path: str):
        try:
            desde = _desde_byte(urlparse(self.path).query)
        except ValueError as erro:
            return self._erro(400, str(erro).encode("utf-8"))

        if path == "/ledger/log.jsonl":
            return self._servir_ledger(self.log_path, raiz=True, desde=desde)

        prefixo = "/ledger/runs/"
        sufixo = "/log.jsonl"
        if path.startswith(prefixo) and path.endswith(sufixo):
            trecho = path[len(prefixo):-len(sufixo)]
            try:
                caminho = self._caminho_ledger_run(trecho)
            except ValueError as erro:
                return self._erro(400, str(erro).encode("utf-8"))
            return self._servir_ledger(caminho, raiz=False, desde=desde)
        if path.startswith(prefixo):
            return self._erro(400, b"run_id invalido")
        return self._erro(404, b"ledger nao encontrado")

    def _falha_ledger_configurado(self) -> bool:
        # O arquivo legado é opcional no caminho normal: missões novas escrevem
        # em runs/<run_id>/log.jsonl. O modo estrito só vale quando o operador
        # afirmou MOTOR_LOG, para distinguir erro de configuração de ausência
        # normal do legado.
        if _valor_env("MOTOR_LOG") is None:
            return False
        try:
            self._eventos_ledger(estrito=True)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as erro:
            self._erro(503, f"ledger configurado indisponivel: {erro}".encode("utf-8"))
            return True
        return False

    def _eventos_ledger(self, *, estrito: bool = False) -> list[dict]:
        """Lê o ledger uma vez por requisição, preservando o modo declarado."""
        cache = cast(list[dict] | None, getattr(self, "_eventos_ledger_cache", None))
        if cache is not None:
            return cache
        eventos = parse_eventos(self.log_path, estrito=estrito)
        self._eventos_ledger_cache = eventos
        return eventos

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/ledger/log.jsonl" or path.startswith("/ledger/runs/"):
            return self._get_ledger(path)

        if (
            path in {"/dados", "/dados/gates", "/dados/agentes", "/dados/custos"}
            and self._falha_ledger_configurado()
        ):
            return

        eventos_projecao: list[dict] | None = None
        if path in {"/dados", "/dados/gates", "/dados/agentes", "/dados/custos"}:
            eventos_projecao = self._eventos_ledger()
        
        # 1. Endpoints do contrato de dados (/dados/*)
        if path == "/dados":
            return self._json(dados_painel(eventos=eventos_projecao or []))
            
        if path == "/dados/runs":
            registros = _runs_do_workspace(self.runs_path, self.log_path)
            return self._json([registro["run"] for registro in registros])
            
        if path.startswith("/dados/runs/"):
            run_id = path.split("/")[-1]
            registros = _runs_do_workspace(self.runs_path, self.log_path)
            registro = next((item for item in registros if item["run"]["id"] == run_id), None)
            if registro is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Run nao encontrada")
                return
            run = registro["run"]
            run_evs = registro["eventos"]
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
            eventos = eventos_projecao or []
            gates = obter_gates_pendentes(eventos)
            return self._json(gates)
            
        if path == "/dados/agentes":
            eventos = eventos_projecao or []
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
            eventos = eventos_projecao or []
            runs_events = agrupar_eventos_por_run(eventos)

            total_tokens = 0
            n_chamadas = 0
            
            por_run = []
            por_modelo = {}
            
            for r_evs in runs_events:
                rid = _id_do_grupo(r_evs)
                    
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
                        
                        total_tokens += tokens
                        r_tokens += tokens

                        if model:
                            if model not in por_modelo:
                                por_modelo[model] = {"modelo": model, "custo_total": None, "tokens_total": 0, "n_chamadas": 0}
                            por_modelo[model]["tokens_total"] += tokens
                            por_modelo[model]["n_chamadas"] += 1
                            
                por_run.append({
                    "id": rid,
                    "custo_total": None,
                    "tokens_total": r_tokens,
                    "n_chamadas": r_chamadas
                })
                
            return self._json({
                "por_run": por_run,
                "por_modelo": list(por_modelo.values()),
                "total": {
                    "custo_total": None,
                    "tokens_total": total_tokens,
                    "n_chamadas": n_chamadas
                }
            })
            
        if path == "/dados/catalogo":
            catalogo = obter_catalogo()
            return self._json(catalogo)

        if path == "/dados/orfaos":
            # Esta e a rota que reporta ledger incompleto, entao ela precisa
            # sobreviver a um ledger ilegivel — se ela morresse junto, o caso
            # pior ficaria invisivel. `_runs_do_workspace` ja tolera log por
            # log; o legado da raiz e tolerado aqui, e a falha vai declarada.
            eventos: list[dict] = []
            legado_ilegivel = None
            try:
                eventos = self._eventos_ledger(
                    estrito=_valor_env("MOTOR_LOG") is not None,
                )
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as erro:
                legado_ilegivel = str(erro)
            for registro in _runs_do_workspace(self.runs_path):
                eventos = eventos + registro["eventos"]
            resumo = orfaos_de_artefato(eventos, self.runs_path)
            resumo["legado_ilegivel"] = legado_ilegivel
            return self._json(resumo)

        if path == "/dados/inventario":
            return self._json(obter_inventario())

        if path == "/dados/conexoes":
            return self._json(obter_conexoes())

        if path == "/dados/missoes/ativa":
            pid = _ler_pid_lock(self.despachos_dir / ".lock")
            ativa = pid is not None and _pid_vivo(pid)
            return self._json({"ativa": ativa, "pid": pid if ativa else None})
            
        if path == "/healthz":
            return self._json({"ok": True})

        # Rota de dados desconhecida NÃO cai no fallback estático. Antes ela
        # devolvia index.html com 200 text/html: a tela via `res.ok` passar e o
        # `res.json()` estourava parseando HTML, com erro que não dizia nada
        # sobre a causa real (normalmente um painel no ar mais velho que o
        # código). 404 faz o sintoma apontar para o problema.
        if path == "/dados" or path.startswith("/dados/"):
            return self._erro(404, b"rota de dados desconhecida")

        # 2. Rotas REMOVIDAS respondem 404 explicito.
        #
        # `/grafo3d` servia uma superficie com projecao PROPRIA de estado -- mais
        # fraca que a do canvas, sem falha nenhuma no modelo, derivando "ativo" de
        # o no ter aparecido nos ultimos 24 eventos do arquivo, e lendo o agregado
        # de todas as runs em vez do grafo de uma. Medida na rota viva do runner
        # com a run ja encerrada (`tarefa.concluida`): cabecalho "AO VIVO", quatro
        # nos na cor cuja legenda e "PRECISA DE VOCE", particulas animando sob o
        # rotulo "fluxo so onde ha run ativo". Buscava `three` no unpkg.com, entao
        # nao abria sem internet publica.
        #
        # O 404 e EXPLICITO de proposito. Sem ele a rota cairia no fallback abaixo
        # e responderia 200 com a pagina de "painel nao construido" -- que manda
        # rodar `npm run build`, conselho que nunca traria esta rota de volta. E
        # sem uma regra nomeada nao ha o que testar: rota removida sem teste de
        # remocao ressuscita num merge e nada falha.
        if path in ROTAS_REMOVIDAS:
            return self._erro(404, ROTAS_REMOVIDAS[path])

        # 3. Servir a interface React. Sem `app/dist`, a `painel.html` DECLARA que
        # o painel nao foi construido -- ela nao e mais uma segunda interface.
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

    def _post_missao(self):
        """POST /dados/missoes — despacha o motor de verdade (consome créditos).

        Salvaguardas: Origin validado, body ≤64KB, spec dict não-vazia,
        lock de despacho único (pid vivo → 409), spec gravada em arquivo
        (nenhum campo do body vira argumento), Popen sem shell.
        """
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 64 * 1024:
            self.rfile.read(content_length)  # drena p/ a resposta chegar ao cliente
            return self._erro(400, b"corpo excede 64KB")
        post_data = self.rfile.read(content_length)  # lê antes de responder — evita RST no cliente

        if not self._origem_permitida():
            return self._erro(403, b"Erro CSRF: Origem nao permitida")

        try:
            body = json.loads(post_data.decode("utf-8"))
        except Exception:
            return self._erro(400, b"JSON invalido")
        if not isinstance(body, dict):
            return self._erro(400, b"JSON invalido")

        spec = body.get("spec")
        if not isinstance(spec, dict) or not spec:
            return self._erro(400, b"spec deve ser um objeto nao-vazio")
        opcoes = body.get("opcoes")
        if not isinstance(opcoes, dict):
            opcoes = {}

        despachos = self.despachos_dir
        despachos.mkdir(parents=True, exist_ok=True)
        lock = despachos / ".lock"
        pid_lock = _ler_pid_lock(lock)
        if pid_lock is not None and _pid_vivo(pid_lock):
            return self._erro(409, b"ja existe despacho em curso")

        ts = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        spec_path = despachos / f"spec-{ts}.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        run_log = despachos / f"run-{ts}.log"

        argv = [
            sys.executable, "-m", "motor", "--spec", str(spec_path),
            "--caixa", "runs/caixa", "--run-id", f"painel-{ts}",
            "--workspace", str(self.runs_path),
        ]
        modelos = os.environ.get("MOTOR_MODELOS")
        if modelos:
            argv.extend(["--modelos", modelos])
        sandbox = os.environ.get("MOTOR_SANDBOX")
        if sandbox:
            argv.extend(["--sandbox", sandbox])
        if opcoes.get("auto") is True:
            argv.append("--auto")
        if opcoes.get("escalar") is True:
            argv.append("--escalar")

        with open(run_log, "wb") as log_f:
            proc = subprocess.Popen(
                argv,
                cwd=str(BASE.parent),
                stdout=log_f,
                stderr=log_f,
                start_new_session=True,
            )
        lock.write_text(str(proc.pid), encoding="utf-8")
        return self._json({"ok": True, "pid": proc.pid, "spec": str(spec_path), "log": str(run_log)})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/dados/missoes":
            return self._post_missao()

        if path.startswith("/dados/gates/"):
            if not self._origem_permitida():
                return self._erro(403, b"Erro CSRF: Origem nao permitida")

            if self._falha_ledger_configurado():
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
                
            eventos = self._eventos_ledger(
                estrito=_valor_env("MOTOR_LOG") is not None,
            )
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


def serve(porta: int = PORTA, log_path: Path = LOG_PATH, db_path: Path = DB_PATH,
          runs_path: Path = RUNS_PATH):
    Handler.log_path = log_path
    Handler.db_path = db_path
    Handler.runs_path = runs_path
    with ReaproveitavelTCPServer(("", porta), Handler) as s:
        print(f"Painel v0.5: http://localhost:{porta}", flush=True)
        s.serve_forever()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else PORTA
    serve(porta)
