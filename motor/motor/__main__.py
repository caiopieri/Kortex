"""CLI mínima do motor v0.5.

  python -m motor --modelos cfg-orcada.json "sua missão aqui"
  python -m motor --modelos cfg-orcada.json --spec exemplos/missao.json
  python -m motor ... --caixa "<dir>"          # gate via nota no vault + resume durável
  python -m motor ... --auto                   # auto-mode: gates resolvem sozinhos (Corte C)
  python -m motor ... --auto --gate cobertura=manual  # tudo auto, MENOS o gate de cobertura
  python -m motor ... --escalar                # verifier reprovou → retry sobe um tier
  python -m motor ... --registro "4. Registry/Modelos"  # catálogo via entidades .md
  python -m motor ... --registro Registry --rota construcao  # estratégia explícita do planner
  python -m motor ... --sandbox "cfg.json"  # backend de comandos em sandbox
  python -m motor ... --workspace runs  # base dos artefatos por execução

A execução de modelo exige composição `orcamento_openai` válida; configurações
legadas falham antes do efeito. Gate do fundador: sem `--caixa`, a decisão é via
input() e o checkpointer é em memória (volátil). Com `--caixa
<dir>`, a decisão vai para uma nota na Caixa do fundador (T3) e o estado do
grafo é persistido em `motor.db` na raiz do repo — religar o processo retoma do
gate pendente.
"""
from __future__ import annotations

import json
import re
import shlex
import sqlite3
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # nome antigo
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from langgraph.checkpoint.sqlite import SqliteSaver

from .caixa import CaixaFundador, rodar_com_caixa
from .composicao_orcamento import (
    compor_orcamento_multi,
    compor_orcamento_omniroute,
    compor_orcamento_openai,
    validar_independencia_orcada,
)
from .eventos import LogEventos
from .grafo import construir_grafo
from .modelos import ClienteClaudeCLI, ClienteModelo, ProvedorIndisponivel, cliente_de_config
from .orcamento import (
    ErroOrcamento,
    Moeda,
    RepositorioOrcamento,
    publicar_pendentes_por_moeda,
)
from .runner import CommandResult, compor_sandbox
from .spec import WorkflowSpec
from .registro import (
    cliente_de_registro,
    ferramentas_de_registro,
    ferramentas_permitidas_de_registro,
    rotas_de_registro,
)


def _merge_cfg(base: dict, over: dict) -> dict:
    """Merge raso por chave de topo (over vence). Usado p/ pôr a config do projeto
    por cima da global (~/.motor/pins.json): provedores/pins/tiers/papeis."""
    out = dict(base)
    for k, v in over.items():
        out[k] = {**out[k], **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _lista_str(valor) -> list[str]:
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(item) for item in valor if str(item).strip()]
    return [str(valor)]


class _SondaModulosSandbox(Protocol):
    def importar_modulo_python(self, executavel: str, modulo: str) -> CommandResult: ...


def _preflight_modulos_sandbox(
    spec: WorkflowSpec, runner: _SondaModulosSandbox, caminho_sandbox: str,
) -> None:
    """Verifica dependências declaradas antes de compor qualquer cliente de modelo."""
    for subagente in spec.subagentes:
        validador = subagente.validador
        if validador is None or validador.kind != "comando":
            continue
        config = validador.config
        modulos = config.modulos_python
        if not modulos:
            continue
        try:
            executavel = shlex.split(config.comando)[0]
        except (IndexError, ValueError) as erro:
            raise ValueError(
                f"validador '{subagente.id}' tem comando inválido para preflight"
            ) from erro
        for modulo in modulos:
            resultado = runner.importar_modulo_python(executavel, modulo)
            if resultado.erro is not None:
                raise ValueError(
                    f"sandbox '{caminho_sandbox}' não pôde verificar módulo Python "
                    f"'{modulo}' exigido pelo validador '{subagente.id}': {resultado.motivo}"
                )
            if resultado.returncode != 0:
                raise ValueError(
                    f"sandbox '{caminho_sandbox}' não contém módulo Python "
                    f"'{modulo}' exigido pelo validador '{subagente.id}'"
                )


def _drenar_orcamento_cli(
    repositorios: Mapping[Moeda, RepositorioOrcamento],
    run_id: str,
    log: LogEventos,
    *,
    agora: int | None = None,
) -> bool:
    instante = int(time.time()) if agora is None else agora
    owner = f"cli-{uuid4().hex}"
    return publicar_pendentes_por_moeda(
        repositorios, run_id, owner, instante, 30, log.publicar_orcamento,
    )


def _caminho_log_da_run(workspace_base: str | Path, run_id: str) -> Path:
    """Retorna o log isolado da run, no mesmo layout do serviço."""
    return Path(workspace_base) / run_id / "log.jsonl"


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
            "`claude` CLI não encontrado no PATH; instale o CLI ou use o ClienteStub em testes."
        )
    return ClienteClaudeCLI(log=log)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return 2

    # --caixa <dir>: gate via nota no vault + checkpointer SQLite durável.
    dir_caixa = None
    if "--caixa" in args:
        i = args.index("--caixa")
        dir_caixa = args[i + 1]
        args = args[:i] + args[i + 2:]

    # --sandbox <cfg.json>: habilita execução real de comando em container
    # isolado. Sem a flag, `command_runner` continua sendo DenyCommandRunner e
    # nenhum comando roda -- que é o default seguro, não um bug.
    command_runner = None
    caminho_sandbox: str | None = None
    if "--sandbox" in args:
        i = args.index("--sandbox")
        if i + 1 >= len(args):
            print("erro: --sandbox exige o caminho de uma config.")
            return 2
        try:
            caminho_sandbox = args[i + 1]
            command_runner, evidencia_sandbox = compor_sandbox(caminho_sandbox)
        except (OSError, ValueError, json.JSONDecodeError,
                subprocess.SubprocessError) as erro:
            print(f"erro: sandbox indisponível: {erro}")
            return 2
        # A identidade efetiva vai para o operador ANTES da missão começar. Ela
        # é evidência de deployment, não certificação: rodar em macOS/Docker
        # Desktop satisfaz o preflight e ainda assim não é o runner Linux
        # dedicado que `sandbox-conformance.md` exige.
        print(f"sandbox: {evidencia_sandbox.engine_version} "
              f"{evidencia_sandbox.os_type} {evidencia_sandbox.policy_version} "
              f"{evidencia_sandbox.effective_repo_digest}")
        args = args[:i] + args[i + 2:]

    workspace_base = "runs"
    if "--workspace" in args:
        i = args.index("--workspace")
        workspace_base = args[i + 1]
        args = args[:i] + args[i + 2:]

    run_id = uuid4().hex
    run_id_explicito = False
    if "--run-id" in args:
        i = args.index("--run-id")
        if i + 1 >= len(args):
            print("erro: --run-id exige um valor.")
            return 2
        run_id = args[i + 1]
        run_id_explicito = True
        args = args[:i] + args[i + 2:]
    if (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id) is None
            or ".." in run_id):
        print("erro: --run-id inválido.")
        return 2
    if dir_caixa is not None and not run_id_explicito:
        print("erro: --caixa exige --run-id estável para permitir retomada.")
        return 2

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

    nome_rota = None
    if "--rota" in args:
        i = args.index("--rota")
        nome_rota = args[i + 1]
        args = args[:i] + args[i + 2:]
    if nome_rota is not None and dir_registro is None:
        print("erro: --rota exige --registro.")
        return 2
    rota = None
    rotas = None
    if dir_registro is not None:
        try:
            rotas = rotas_de_registro(dir_registro)
        except ValueError as ex:
            print(f"erro: {ex}")
            return 2
    if nome_rota is not None:
        if rotas is None:
            print("erro: --rota exige --registro.")
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
    from .politica import GATES_SENSIVEIS, politica_de_config
    politica = politica_de_config((cfg_modelos or {}).get("politica_gates"))
    if "--auto" in args:
        politica.auto_mode = True
        args.remove("--auto")
    while "--gate" in args:
        i = args.index("--gate")
        gid, _, modo = args[i + 1].partition("=")
        politica.overrides[gid] = modo or "manual"
        args = args[:i] + args[i + 2:]

    escalar_em_retry = "--escalar" in args
    if escalar_em_retry:
        args.remove("--escalar")

    perfil_execucao = "rascunho" if "--rascunho" in args else "certificado"
    if "--rascunho" in args:
        args.remove("--rascunho")

    max_rodadas_reconciliacao = 1
    if "--reconciliar" in args:
        i = args.index("--reconciliar")
        max_rodadas_reconciliacao = int(args[i + 1])
        args = args[:i] + args[i + 2:]

    if not args:
        print("erro: informe uma missão ou --spec.")
        return 2
    # O que sobrou vira TEXTO DE MISSÃO. Sem esta checagem, uma flag digitada
    # errada -- ou `--help`, que este parser manual nunca tratou -- é despachada
    # ao planner e gasta orçamento antes de qualquer erro aparecer.
    if args[0] != "--spec" and any(arg.startswith("--") for arg in args):
        desconhecidas = [arg for arg in args if arg.startswith("--")]
        print(f"erro: opção desconhecida: {' '.join(desconhecidas)}")
        print(__doc__)
        return 2
    entrada: dict
    if args[0] == "--spec":
        entrada = {"spec": json.loads(Path(args[1]).read_text(encoding="utf-8"))}
        if command_runner is not None and caminho_sandbox is not None:
            try:
                _preflight_modulos_sandbox(
                    WorkflowSpec.model_validate(entrada["spec"]),
                    command_runner,
                    caminho_sandbox,
                )
            except ValueError as erro:
                print(f"erro: pareamento spec/sandbox inválido: {erro}")
                return 2
    else:
        entrada = {"missao_texto": " ".join(args)}
    entrada.update({"run_id": run_id, "thread_id": run_id})

    raiz = Path(__file__).parent.parent
    log = LogEventos(_caminho_log_da_run(workspace_base, run_id))
    repositorios_orcamento: dict[Moeda, RepositorioOrcamento] = {}
    dreno_emergencial_habilitado = False
    dreno_final_tentado = False
    try:
        config = {"configurable": {"thread_id": run_id}}
        ferramentas = ferramentas_de_registro(dir_registro) if dir_registro is not None else {}
        ferramentas_permitidas = _lista_str((cfg_modelos or {}).get("ferramentas_permitidas"))
        if not ferramentas_permitidas and dir_registro is not None:
            ferramentas_permitidas = ferramentas_permitidas_de_registro(dir_registro)
        if cfg_modelos and cfg_modelos.get("pins") and not (
            "provedores" in cfg_modelos or "base_url" in cfg_modelos
        ):
            print("aviso: pins ignorados — precisam de 'provedores' (via --modelos ou ~/.motor/pins.json).")
        try:
            # A config escolhe o arranjo por presenca POSITIVA dos blocos multi.
            # Ausencia nao elege nada: config sem bloco nenhum tem que continuar
            # caindo no compositor antigo e falhando com a mensagem dele, senao
            # troca-se um erro conhecido por outro so porque o default mudou.
            cfg_orcada = cfg_modelos or {}
            if "omniroute" in cfg_orcada:
                compor = compor_orcamento_omniroute
            elif {"gemini", "anthropic"} <= set(cfg_orcada):
                compor = compor_orcamento_multi
            else:
                compor = compor_orcamento_openai
            deps_orcamento = compor(cfg_orcada, workspace_base)
            validar_independencia_orcada(deps_orcamento.rotas_certificadas)
            cliente = deps_orcamento.cliente
            orcamento_brl = deps_orcamento.orcamentos.get("BRL")
            if orcamento_brl is None:
                raise ErroOrcamento("orcamento BRL ausente")
            repositorios_orcamento = {
                moeda: orcamento.repositorio
                for moeda, orcamento in deps_orcamento.orcamentos.items()
            }
            medicao_monetaria_desligada = deps_orcamento.medicao_monetaria_desligada
            if medicao_monetaria_desligada:
                log.evento(
                    "medicao.monetaria_desligada",
                    motivo="operador declarou sem_contencao_monetaria",
                )
            else:
                if not _drenar_orcamento_cli(repositorios_orcamento, run_id, log):
                    raise ErroOrcamento("relay monetario pendente")
                dreno_emergencial_habilitado = True
        except ErroOrcamento as ex:
            print(f"erro: orçamento indisponível: {ex}")
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
            try:
                checkpointer = SqliteSaver(conn)
                checkpointer.setup()
                grafo = construir_grafo(cliente, log, checkpointer=checkpointer, politica=politica,
                                        workspace_base=workspace_base, ferramentas=ferramentas,
                                        rota=rota, rotas=rotas,
                                        escalar_em_retry=escalar_em_retry,
                                        max_rodadas_reconciliacao=max_rodadas_reconciliacao,
                                        perfil_execucao=perfil_execucao,
                                        ferramentas_permitidas=ferramentas_permitidas,
                                        repositorio_orcamento=(
                                            None if medicao_monetaria_desligada
                                            else orcamento_brl.repositorio
                                        ),
                                        medicao_monetaria_desligada=medicao_monetaria_desligada,
                                        fabrica_tentativas_orcadas=deps_orcamento.fabrica,
                                        teto_bootstrap=orcamento_brl.teto_bootstrap,
                                        command_runner=command_runner)
                caixa = CaixaFundador(dir_caixa, log)
                resultado = rodar_com_caixa(grafo, entrada, config, caixa, log)
            finally:
                conn.close()
        else:
            # Comportamento default intacto: input() + InMemorySaver (volátil).
            grafo = construir_grafo(cliente, log, checkpointer=InMemorySaver(), politica=politica,
                                    workspace_base=workspace_base, ferramentas=ferramentas,
                                    rota=rota, rotas=rotas,
                                    escalar_em_retry=escalar_em_retry,
                                    max_rodadas_reconciliacao=max_rodadas_reconciliacao,
                                    perfil_execucao=perfil_execucao,
                                    ferramentas_permitidas=ferramentas_permitidas,
                                    repositorio_orcamento=(
                                        None if medicao_monetaria_desligada
                                        else orcamento_brl.repositorio
                                    ),
                                    medicao_monetaria_desligada=medicao_monetaria_desligada,
                                    fabrica_tentativas_orcadas=deps_orcamento.fabrica,
                                    teto_bootstrap=orcamento_brl.teto_bootstrap,
                                    command_runner=command_runner)
            resultado = grafo.invoke(entrada, config)
            while "__interrupt__" in resultado:  # gate do fundador
                pedido = resultado["__interrupt__"][0].value
                print(f"\n[GATE {pedido['portao']}] {pedido['pergunta']}")
                print(f"  lacunas: {pedido.get('lacunas')}\n  opções: {pedido['opcoes']}")
                portao = pedido["portao"]
                manual_intencional = (
                    politica.overrides.get(portao) == "manual"
                    or portao in GATES_SENSIVEIS
                )
                if (politica.auto_mode and not manual_intencional) or not sys.stdin.isatty():
                    print(
                        f"erro: gate '{portao}' requer decisão humana; "
                        "execução desassistida encerrada"
                    )
                    return 1
                decisao = input("decisão> ").strip()
                resultado = grafo.invoke(Command(resume=decisao), config)

        try:
            dreno_final_tentado = True
            if (not medicao_monetaria_desligada
                    and not _drenar_orcamento_cli(repositorios_orcamento, run_id, log)):
                raise ErroOrcamento("relay monetario pendente")
        except Exception as ex:
            print(f"erro: relay monetário indisponível: {ex}")
            return 1
        print("\n=== RESPOSTA FINAL ===\n")
        print(resultado.get("resposta_final", "(missão abortada)"))
        return 0
    finally:
        try:
            if dreno_emergencial_habilitado and not dreno_final_tentado:
                try:
                    if not _drenar_orcamento_cli(
                        repositorios_orcamento, run_id, log,
                    ):
                        raise ErroOrcamento("relay monetario pendente")
                except Exception as erro_relay:
                    raise ErroOrcamento(
                        "execucao falhou e relay monetario ficou pendente"
                    ) from erro_relay
        finally:
            log.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
