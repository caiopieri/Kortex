"""CLI mínima do motor v0.5.

  python -m motor "sua missão aqui"            # planner cria a WorkflowSpec
  python -m motor --spec exemplos/missao.json  # missão dirigida por spec pronta
  python -m motor ... --caixa "<dir>"          # gate via nota no vault + resume durável
  python -m motor ... --modelos exemplos/modelos-nvidia.json  # papéis baratos → DeepSeek/Kimi
                                               # (exige env var da chave, ex. NVIDIA_API_KEY)
  python -m motor ... --modelos cfg.json --esgotado claude     # claude indisponível →
                                               # reroteia pro fallback (Corte B). Repetível.
  python -m motor ... --auto                   # auto-mode: gates resolvem sozinhos (Corte C)
  python -m motor ... --auto --gate cobertura=manual  # tudo auto, MENOS o gate de cobertura
  python -m motor ... --modelos cfg.json --pin synthesizer=oc/openai/gpt-5.5  # fixa modelo
                                               # numa chave (papel|tier|"*"), precedência máxima.
                                               # Pins globais (todos os projetos): ~/.motor/pins.json
  python -m motor ... --registro "4. Registry/Modelos"  # catálogo via entidades .md
  python -m motor ... --registro Registry --rota construcao  # estratégia explícita do planner
  python -m motor ... --workspace runs  # base dos artefatos por execução

Requer `claude` CLI no PATH (Mac do Caio). Gate do fundador: sem `--caixa`, a
decisão é via input() e o checkpointer é em memória (volátil). Com `--caixa
<dir>`, a decisão vai para uma nota na Caixa do fundador (T3) e o estado do
grafo é persistido em `motor.db` na raiz do repo — religar o processo retoma do
gate pendente.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # nome antigo
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from langgraph.checkpoint.sqlite import SqliteSaver

from .caixa import CaixaFundador, rodar_com_caixa
from .eventos import LogEventos
from .grafo import construir_grafo
from .modelos import ClienteClaudeCLI, ClienteModelo, ProvedorIndisponivel, cliente_de_config
from .registro import cliente_de_registro, ferramentas_de_registro, rotas_de_registro


def _merge_cfg(base: dict, over: dict) -> dict:
    """Merge raso por chave de topo (over vence). Usado p/ pôr a config do projeto
    por cima da global (~/.motor/pins.json): provedores/pins/tiers/papeis."""
    out = dict(base)
    for k, v in over.items():
        out[k] = {**out[k], **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def construir_cliente(cfg_modelos: dict | None, dir_registro: str | None,
                      log: LogEventos | None = None) -> ClienteModelo:
    """Monta o cliente de modelo para uso programático.

    Diferente da CLI, esta fronteira levanta erro tipado quando o fallback local
    (`claude`) não está disponível, deixando o chamador decidir como reportar.
    """
    if dir_registro is not None:
        return cliente_de_registro(dir_registro, log=log)
    if cfg_modelos and ("provedores" in cfg_modelos or "base_url" in cfg_modelos):
        return cliente_de_config(cfg_modelos, log=log)
    if not ClienteClaudeCLI.disponivel():
        raise ProvedorIndisponivel(
            "`claude` CLI não encontrado no PATH — rode no Mac do Caio ou use o ClienteStub em testes."
        )
    return ClienteClaudeCLI(log=log)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    # --caixa <dir>: gate via nota no vault + checkpointer SQLite durável.
    dir_caixa = None
    if "--caixa" in args:
        i = args.index("--caixa")
        dir_caixa = args[i + 1]
        args = args[:i] + args[i + 2:]

    workspace_base = "runs"
    if "--workspace" in args:
        i = args.index("--workspace")
        workspace_base = args[i + 1]
        args = args[:i] + args[i + 2:]

    # --modelos <cfg.json>: multi-provider (papéis baratos → OpenAI-compat;
    # resto → claude). Sem a flag, comportamento intacto: tudo no claude.
    cfg_modelos = None
    if "--modelos" in args:
        i = args.index("--modelos")
        cfg_modelos = json.loads(Path(args[i + 1]).read_text(encoding="utf-8"))
        args = args[:i] + args[i + 2:]

    dir_registro = None
    if "--registro" in args:
        i = args.index("--registro")
        dir_registro = args[i + 1]
        args = args[:i] + args[i + 2:]
    if cfg_modelos is not None and dir_registro is not None:
        print("erro: use --registro OU --modelos, não os dois.")
        return 2

    nome_rota = None
    if "--rota" in args:
        i = args.index("--rota")
        nome_rota = args[i + 1]
        args = args[:i] + args[i + 2:]
    if nome_rota is not None and dir_registro is None:
        print("erro: --rota exige --registro.")
        return 2
    rota = None
    if nome_rota is not None:
        try:
            rotas = rotas_de_registro(dir_registro)
        except ValueError as ex:
            print(f"erro: {ex}")
            return 2
        rota = rotas.get(nome_rota)
        if rota is None:
            print(f"erro: rota {nome_rota!r} não encontrada no Registry.")
            return 2

    # --pin <chave>=<provedor/modelo>: pin manual (repetível). chave = papel|tier|"*".
    # Precisa de 'provedores' (via --modelos ou ~/.motor/pins.json) pra resolver.
    pins_cli: dict[str, str] = {}
    while "--pin" in args:
        i = args.index("--pin")
        chave, _, dest = args[i + 1].partition("=")
        pins_cli[chave] = dest
        args = args[:i] + args[i + 2:]

    # Config GLOBAL (todos os projetos): ~/.motor/pins.json — mesma forma de uma
    # config de --modelos {provedores, pins, tiers, ...}. O projeto SOBREPÕE a global.
    global_path = Path.home() / ".motor" / "pins.json"
    if global_path.exists():
        cfg_global = json.loads(global_path.read_text(encoding="utf-8"))
        cfg_modelos = _merge_cfg(cfg_global, cfg_modelos or {})
    if pins_cli:
        cfg_modelos = cfg_modelos or {}
        cfg_modelos["pins"] = {**cfg_modelos.get("pins", {}), **pins_cli}

    # --esgotado <provedor>: marca um provedor como indisponível (Corte B). Repetível.
    # Ex.: `--esgotado claude` → reroteia o julgamento pro fallback (Codex). Exige --modelos.
    esgotados: list[str] = []
    while "--esgotado" in args:
        i = args.index("--esgotado")
        esgotados.append(args[i + 1])
        args = args[:i] + args[i + 2:]

    # --auto / --gate <id>=<modo>: política de gates (Corte C). --auto liga o
    # master (tudo automático); --gate crava exceção por gate (repetível). Também
    # lê "politica_gates" da config de --modelos. CLI tem precedência.
    from .politica import politica_de_config
    politica = politica_de_config((cfg_modelos or {}).get("politica_gates"))
    if "--auto" in args:
        politica.auto_mode = True
        args.remove("--auto")
    while "--gate" in args:
        i = args.index("--gate")
        gid, _, modo = args[i + 1].partition("=")
        politica.overrides[gid] = modo or "manual"
        args = args[:i] + args[i + 2:]

    entrada: dict
    if args[0] == "--spec":
        entrada = {"spec": json.loads(Path(args[1]).read_text(encoding="utf-8"))}
    else:
        entrada = {"missao_texto": " ".join(args)}

    raiz = Path(__file__).parent.parent
    log = LogEventos(raiz / "log.jsonl")
    config = {"configurable": {"thread_id": "cli"}}
    ferramentas = ferramentas_de_registro(dir_registro) if dir_registro is not None else {}
    if cfg_modelos and cfg_modelos.get("pins") and not (
        "provedores" in cfg_modelos or "base_url" in cfg_modelos
    ):
        print("aviso: pins ignorados — precisam de 'provedores' (via --modelos ou ~/.motor/pins.json).")
    try:
        cliente = construir_cliente(cfg_modelos, dir_registro, log=log)
    except ProvedorIndisponivel as ex:
        print(f"erro: {ex}")
        return 1
    if esgotados:
        if hasattr(cliente, "esgotados"):
            cliente.esgotados |= set(esgotados)
            log.evento("provedor.esgotado", provedores=esgotados)
        else:
            print(f"aviso: --esgotado {esgotados} ignorado (precisa de --modelos com roteador).")

    if dir_caixa:
        # Persistente: sobrevive a crash. Conexão própria (check_same_thread=False)
        # para não fechar ao sair de um context manager — durabilidade real exige
        # que o arquivo motor.db permaneça consistente entre execuções.
        conn = sqlite3.connect(str(raiz / "motor.db"), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()
        grafo = construir_grafo(cliente, log, checkpointer=checkpointer, politica=politica,
                                workspace_base=workspace_base, ferramentas=ferramentas,
                                rota=rota)
        caixa = CaixaFundador(dir_caixa, log)
        resultado = rodar_com_caixa(grafo, entrada, config, caixa, log)
        conn.close()
    else:
        # Comportamento default intacto: input() + InMemorySaver (volátil).
        grafo = construir_grafo(cliente, log, checkpointer=InMemorySaver(), politica=politica,
                                workspace_base=workspace_base, ferramentas=ferramentas,
                                rota=rota)
        resultado = grafo.invoke(entrada, config)
        while "__interrupt__" in resultado:  # gate do fundador
            pedido = resultado["__interrupt__"][0].value
            print(f"\n[GATE {pedido['portao']}] {pedido['pergunta']}")
            print(f"  lacunas: {pedido.get('lacunas')}\n  opções: {pedido['opcoes']}")
            decisao = input("decisão> ").strip()
            resultado = grafo.invoke(Command(resume=decisao), config)

    print("\n=== RESPOSTA FINAL ===\n")
    print(resultado.get("resposta_final", "(missão abortada)"))
    log.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
