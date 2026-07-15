"""Serviço programático do motor: jobs duráveis e não-bloqueantes.

O caminho de serviço estaciona em gates via interrupt/checkpointer e devolve o
controle ao chamador. Ele não decide gate, não usa input() e não liga auto-mode.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .caixa import LedgerCaixa
from .composicao_orcamento import compor_orcamento_openai
from .eventos import LogEventos
from .eventos_schema import SCHEMA_VERSAO
from .grafo import construir_grafo
from .modelos import ClienteModelo
from .orcamento import (
    RepositorioOrcamento, RequisitosTentativaCusteada, RotaTentativaCusteada,
    publicar_um_pendente,
)
from .politica import PoliticaGates
from .registro import ferramentas_de_registro, ferramentas_permitidas_de_registro, rotas_de_registro


PADRAO_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _validar_job_id(job_id: str) -> None:
    if (
        not isinstance(job_id, str)
        or job_id in {".", ".."}
        or ".." in job_id
        or not PADRAO_JOB_ID.fullmatch(job_id)
    ):
        raise ValueError("job_id inválido")


def _lista_str(valor: Any) -> list[str]:
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(item) for item in valor if str(item).strip()]
    return [str(valor)]


def _segundos_positivos(nome: str, valor: float) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{nome} inválido")
    try:
        segundos = float(valor)
    except (TypeError, ValueError, OverflowError) as ex:
        raise ValueError(f"{nome} inválido") from ex
    if not math.isfinite(segundos) or segundos <= 0:
        raise ValueError(f"{nome} inválido")
    return segundos


class _LogConsulta:
    """Interface sem writer para compilar o grafo em consultas de snapshot."""

    def __init__(self, path: Path):
        self.path = path

    def evento(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("consulta de snapshot não pode emitir eventos")

    def fechar(self) -> None:
        return None


class GerenciadorJobs:
    def __init__(self, *, db_path: str | Path = "motor.db",
                 workspace_base: str | Path = "runs",
                 cfg_modelos: dict | None = None,
                 dir_registro: str | Path | None = None,
                 politica: PoliticaGates | None = None,
                 log: LogEventos | None = None,
                 cliente: ClienteModelo | None = None,
                 repositorio_orcamento: RepositorioOrcamento | None = None,
                 fabrica_tentativas_orcadas: Callable[
                     [str, str, int, RequisitosTentativaCusteada],
                     list[RotaTentativaCusteada],
                 ] | None = None,
                 ferramentas: dict[str, dict[str, Any]] | None = None,
                 fault: Callable[[str], None] | None = None,
                 outbox_poll_s: float = 0.5,
                 outbox_lease_s: float = 30.0):
        self._outbox_poll_s = _segundos_positivos("outbox_poll_s", outbox_poll_s)
        self._outbox_lease_s = _segundos_positivos("outbox_lease_s", outbox_lease_s)
        self.db_path = Path(db_path)
        self.workspace_base = Path(workspace_base)
        if (repositorio_orcamento is None) != (fabrica_tentativas_orcadas is None):
            raise ValueError("repo e fabrica orcados devem ser fornecidos juntos")
        if cliente is None:
            if repositorio_orcamento is not None:
                raise ValueError("deps orcadas explicitas exigem cliente")
            deps = compor_orcamento_openai(cfg_modelos or {}, self.workspace_base)
            cliente = deps.cliente
            repositorio_orcamento = deps.repositorio
            fabrica_tentativas_orcadas = deps.fabrica
        elif repositorio_orcamento is None:
            raise ValueError("cliente injetado exige repo e fabrica orcados")
        self.cfg_modelos = cfg_modelos
        self.dir_registro = str(dir_registro) if dir_registro is not None else None
        self.politica = politica or PoliticaGates()
        self.log = log
        self._cliente = cliente
        self._repositorio_orcamento = repositorio_orcamento
        self._fabrica_tentativas_orcadas = fabrica_tentativas_orcadas
        self._fault = fault
        self.ferramentas = (ferramentas if ferramentas is not None else
                            ferramentas_de_registro(self.dir_registro) if self.dir_registro else {})
        self.ferramentas_permitidas = _lista_str((cfg_modelos or {}).get("ferramentas_permitidas"))
        if not self.ferramentas_permitidas and self.dir_registro:
            self.ferramentas_permitidas = ferramentas_permitidas_de_registro(self.dir_registro)
        self.rotas = rotas_de_registro(self.dir_registro) if self.dir_registro else {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._threads: set[threading.Thread] = set()
        self._stop_reconciliador = threading.Event()
        self._fechado = False
        self._conn_fechada = False
        self._owner_reconciliador = f"reconciliador-{uuid.uuid4().hex}"
        self._owner_orcamento = f"servico-orcamento-{uuid.uuid4().hex}"
        self._erro_reconciliador: Exception | None = None

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._checkpointer.setup()
        ledger = LedgerCaixa(self.db_path)
        ledger.fechar()
        self._reconciliador = threading.Thread(
            target=self._reconciliar_outbox,
            name=f"motor-outbox-{uuid.uuid4().hex[:8]}",
            daemon=True,
        )
        try:
            self._reconciliador.start()
        except BaseException:
            self._conn.close()
            self._conn_fechada = True
            raise

    def iniciar(self, *, missao_texto: str | None = None,
                spec: dict[str, Any] | None = None,
                thread_id: str) -> dict:
        """Dispara a execução em background e retorna imediatamente."""
        with self._lock:
            self._exigir_aberto()
        if bool(missao_texto) == bool(spec):
            raise ValueError("exige missao_texto XOR spec")
        if not thread_id:
            raise ValueError("thread_id é obrigatório")
        _validar_job_id(thread_id)

        cliente = self._obter_cliente()
        entrada: dict[str, Any] = (
            {"missao_texto": missao_texto} if missao_texto is not None else {"spec": spec}
        )
        entrada["run_id"] = thread_id
        entrada["thread_id"] = thread_id
        with self._lock:
            self._exigir_aberto()
            self._jobs[thread_id] = {"estado": "em_execucao"}
            self._iniciar_thread(thread_id, cliente, entrada)
        return {"job_id": thread_id, "estado": "em_execucao"}

    def status(self, job_id: str) -> dict:
        """Estado atual sem bloquear."""
        _validar_job_id(job_id)
        with self._lock:
            self._exigir_aberto()
            registro = self._jobs.get(job_id)
            if registro and registro.get("estado") != "em_execucao":
                return self._resposta_de_registro(job_id, registro)
            if registro:
                return {"estado": "em_execucao"}
        return self._status_duravel(job_id)

    def responder_gate(self, job_id: str, decisao,
                       decision_id: str | None = None) -> dict:
        """Retoma um job pausado com a decisão humana fornecida pelo chamador."""
        with self._lock:
            self._exigir_aberto()
        _validar_job_id(job_id)
        if decision_id is not None and (
            not isinstance(decision_id, str)
            or not PADRAO_JOB_ID.fullmatch(decision_id)
        ):
            return {
                "estado": "erro",
                "erro": {"tipo": "DecisaoInvalida", "mensagem": "decision_id inválido"},
            }

        gates = self._gates_duraveis(job_id)
        if decision_id is None:
            if len(gates) > 1:
                return {
                    "estado": "erro",
                    "erro": {
                        "tipo": "DecisaoIdObrigatorio",
                        "mensagem": "decision_id é obrigatório para múltiplos gates",
                    },
                }
            if gates:
                decision_id = gates[0]["decision_id"]
                gate = gates[0]
            else:
                gate = None
        else:
            gate = next(
                (item for item in gates if item.get("decision_id") == decision_id),
                None,
            )

        if gate is None:
            if decision_id is not None:
                if self._decisao_ja_aceita(decision_id, job_id, decisao):
                    return {"estado": "em_execucao"}
                return {
                    "estado": "erro",
                    "erro": {
                        "tipo": "EstadoInvalido",
                        "mensagem": "decision_id não corresponde a gate pendente",
                    },
                }
            if decision_id is None:
                legado = self.status(job_id)
                gate_legado = legado.get("gate") or {}
                if (
                    legado.get("estado") == "gate_pendente"
                    and "gates" not in legado
                    and not isinstance(gate_legado.get("decision_id"), str)
                ):
                    with self._lock:
                        self._exigir_aberto()
                        if self._jobs.get(job_id, {}).get("estado") == "em_execucao":
                            return {
                                "estado": "erro",
                                "erro": {
                                    "tipo": "EstadoInvalido",
                                    "mensagem": "gate já respondido",
                                },
                            }
                        self._jobs[job_id] = {"estado": "em_execucao"}
                        self._iniciar_thread(
                            job_id, self._obter_cliente(), Command(resume=decisao)
                        )
                    return {"estado": "em_execucao"}
            if self._recuperar_outbox(job_id):
                return {"estado": "em_execucao"}
            return {
                "estado": "erro",
                "erro": {
                    "tipo": "EstadoInvalido",
                    "mensagem": "job não está em gate_pendente",
                },
            }
        if not isinstance(decision_id, str):
            raise RuntimeError("gate durável sem decision_id")

        try:
            ledger = LedgerCaixa(self.db_path)
            try:
                ledger.registrar_decisao(
                    decisao_id=decision_id, job_id=job_id,
                    portao=gate.get("portao", "decisao"), decisao=decisao,
                )
                claim = ledger.claim(
                    f"servico-{uuid.uuid4().hex}", lease_s=self._outbox_lease_s,
                    decisao_id=decision_id,
                )
                aceito_por_outro = False
                if claim is None:
                    registro = ledger.buscar_decisao(decision_id)
                    aceito_por_outro = (
                        registro is not None
                        and registro["estado"] in {"PENDING", "CLAIMED", "APPLIED"}
                    )
            finally:
                ledger.fechar()
        except ValueError as ex:
            return {
                "estado": "erro",
                "erro": {"tipo": "DecisaoInvalida", "mensagem": str(ex)},
            }
        if claim is None:
            if aceito_por_outro:
                return {"estado": "em_execucao"}
            return {
                "estado": "erro",
                "erro": {"tipo": "EstadoInvalido", "mensagem": "gate já respondido"},
            }
        with self._lock:
            self._exigir_aberto()
            self._jobs[job_id] = {"estado": "em_execucao"}
            self._iniciar_thread(job_id, self._obter_cliente(), None, claim)
        return {"estado": "em_execucao"}

    def _decisao_ja_aceita(self, decision_id: str, job_id: str,
                           decisao: Any) -> bool:
        ledger = LedgerCaixa(self.db_path)
        try:
            registro = ledger.buscar_decisao(decision_id)
        finally:
            ledger.fechar()
        if registro is None or registro["estado"] not in {
            "PENDING", "CLAIMED", "APPLIED",
        }:
            return False
        payload = registro.get("payload")
        return (
            isinstance(payload, dict)
            and payload.get("job_id") == job_id
            and payload.get("decisao") == decisao
        )

    def _gates_duraveis(self, job_id: str) -> list[dict[str, Any]]:
        log = self._log_do_job(job_id, truncar=False)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            grafo = construir_grafo(
                self._obter_cliente(),
                log,
                checkpointer=SqliteSaver(conn),
                politica=self.politica,
                workspace_base=self.workspace_base,
                ferramentas=self.ferramentas,
                ferramentas_permitidas=self.ferramentas_permitidas,
                rotas=self.rotas,
                repositorio_orcamento=self._repositorio_orcamento,
                fabrica_tentativas_orcadas=self._fabrica_tentativas_orcadas,
            )
            snapshot = grafo.get_state(self._config(job_id))
            return self._gates(getattr(snapshot, "interrupts", ()))
        finally:
            conn.close()
            if log is not self.log:
                log.fechar()

    def resumo(self, job_id: str) -> dict:
        """Digest compacto, derivado de state + log.jsonl. Nunca devolve log cru."""
        _validar_job_id(job_id)
        status = self.status(job_id)
        eventos = self._eventos_do_job(job_id)
        digest = {
            "estado": status["estado"],
            "progresso": self._progresso(eventos),
            "gate": self._gate_resumo(status.get("gate")) if status["estado"] == "gate_pendente" else None,
            "marcos": self._marcos(eventos),
            "resumo_resposta": None,
            "artefatos": status.get("artefatos", []),
            "run": status.get("run", self._run(job_id, job_id)),
        }
        if status["estado"] == "concluido":
            digest["resumo_resposta"] = self._resumir_resposta(status.get("resposta_final", ""))
        if status["estado"] == "erro":
            erro = status.get("erro", {})
            digest["marcos"] = [*digest["marcos"], f"erro: {erro.get('tipo', 'Erro')}"]
        return digest

    def eventos(self, job_id: str, desde: int = 0) -> dict:
        """Stream incremental read-only do log JSONL de um job."""
        _validar_job_id(job_id)
        eventos = self._eventos_do_job(job_id)
        offset = max(0, int(desde))
        return {
            "eventos": eventos[offset:],
            "proximo_offset": len(eventos),
            "schema_versao": SCHEMA_VERSAO,
        }

    def _obter_cliente(self) -> ClienteModelo:
        return self._cliente

    def _iniciar_thread(self, job_id: str, cliente: ClienteModelo, entrada: Any,
                        claim: dict[str, Any] | None = None) -> None:
        def executar() -> None:
            try:
                self._executar(job_id, cliente, entrada, claim)
            finally:
                with self._lock:
                    self._threads.discard(threading.current_thread())

        thread = threading.Thread(
            target=executar,
            name=f"motor-job-{job_id}",
            daemon=True,
        )
        with self._lock:
            self._exigir_aberto()
            self._threads.add(thread)
            try:
                thread.start()
            except BaseException:
                self._threads.discard(thread)
                raise

    def _executar(self, job_id: str, cliente: ClienteModelo, entrada: Any,
                  claim: dict[str, Any] | None = None) -> None:
        log = self._log_do_job(job_id)
        registro: dict[str, Any]
        try:
            grafo = construir_grafo(
                cliente,
                log,
                checkpointer=self._checkpointer,
                politica=self.politica,
                workspace_base=self.workspace_base,
                ferramentas=self.ferramentas,
                ferramentas_permitidas=self.ferramentas_permitidas,
                rotas=self.rotas,
                repositorio_orcamento=self._repositorio_orcamento,
                fabrica_tentativas_orcadas=self._fabrica_tentativas_orcadas,
            )
            if claim is None:
                resultado = grafo.invoke(entrada, self._config(job_id))
            else:
                ledger = LedgerCaixa(self.db_path)
                try:
                    resultado = ledger.consumir(
                        claim,
                        lambda payload: grafo.invoke(
                            Command(resume={payload["decisao_id"]: payload["decisao"]}),
                            self._config(job_id),
                        ),
                        fault=self._fault,
                    )
                finally:
                    ledger.fechar()
            registro = self._registro_de_resultado(resultado)
        except Exception as ex:  # erro tratável: o gerenciador não cai
            registro = {
                "estado": "erro",
                "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)},
            }
        try:
            if not self._drenar_orcamento(job_id, log):
                raise RuntimeError("relay monetario pendente")
        except Exception as ex:
            registro = {
                "estado": "erro",
                "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)},
            }
        try:
            if log is not self.log:
                log.fechar()
        except Exception as ex:
            registro = {
                "estado": "erro",
                "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)},
            }
        with self._lock:
            self._jobs[job_id] = registro

    def _drenar_orcamento(self, job_id: str, log: LogEventos) -> bool:
        if self._repositorio_orcamento is None:
            return True
        while publicar_um_pendente(
            self._repositorio_orcamento,
            job_id,
            self._owner_orcamento,
            int(time.time()),
            max(1, math.ceil(self._outbox_lease_s)),
            log.publicar_orcamento,
        ):
            pass
        return self._repositorio_orcamento.listar_pendentes(job_id) == []

    def _recuperar_outbox(self, job_id: str) -> bool:
        with self._lock:
            self._exigir_aberto()
        ledger = LedgerCaixa(self.db_path)
        try:
            claim = ledger.claim(
                f"servico-{uuid.uuid4().hex}",
                lease_s=self._outbox_lease_s,
                job_id=job_id,
            )
        finally:
            ledger.fechar()
        if claim is None:
            return False
        with self._lock:
            self._exigir_aberto()
            self._jobs[job_id] = {"estado": "em_execucao"}
            self._iniciar_thread(job_id, self._obter_cliente(), None, claim)
        return True

    def _reconciliar_outbox(self) -> None:
        while not self._stop_reconciliador.is_set():
            try:
                ledger = LedgerCaixa(self.db_path)
                try:
                    claim = ledger.claim(
                        self._owner_reconciliador,
                        lease_s=self._outbox_lease_s,
                    )
                finally:
                    ledger.fechar()
                if claim is None:
                    self._stop_reconciliador.wait(self._outbox_poll_s)
                    continue
                payload = claim.get("payload")
                job_id = payload.get("job_id") if isinstance(payload, dict) else None
                if not isinstance(job_id, str):
                    raise ValueError("payload sem job_id válido")
                _validar_job_id(job_id)
                if self._stop_reconciliador.is_set():
                    return
                with self._lock:
                    if self._fechado:
                        return
                    self._jobs[job_id] = {"estado": "em_execucao"}
                    self._erro_reconciliador = None
                self._executar(job_id, self._obter_cliente(), None, claim)
            except Exception as ex:
                with self._lock:
                    self._erro_reconciliador = ex
                self._stop_reconciliador.wait(self._outbox_poll_s)

    def fechar(self, *, timeout_s: float = 5.0) -> None:
        """Para workers e só então fecha o checkpointer compartilhado."""
        timeout = _segundos_positivos("timeout_s", timeout_s)
        with self._lock:
            if self._conn_fechada:
                return
            self._fechado = True
            self._stop_reconciliador.set()
            threads = [self._reconciliador, *self._threads]

        limite = time.monotonic() + timeout
        for thread in threads:
            restante = max(0.0, limite - time.monotonic())
            thread.join(restante)
        if any(thread.is_alive() for thread in threads):
            raise TimeoutError("workers não encerraram no prazo")

        with self._lock:
            if self._threads or self._reconciliador.is_alive():
                raise TimeoutError("workers não encerraram no prazo")
            if not self._conn_fechada:
                self._conn.close()
                self._conn_fechada = True

    def _exigir_aberto(self) -> None:
        if self._fechado:
            raise RuntimeError("GerenciadorJobs fechado")

    def _status_duravel(self, job_id: str) -> dict:
        if (
            self._repositorio_orcamento is not None
            and self._repositorio_orcamento.possui_ledger(job_id)
        ):
            log_relay = self.log or LogEventos(self._caminho_log(job_id), truncar=False)
            try:
                if not self._drenar_orcamento(job_id, log_relay):
                    return {"estado": "em_execucao"}
            finally:
                if log_relay is not self.log:
                    log_relay.fechar()
        log = self._log_do_job(job_id, truncar=False)
        grafo = construir_grafo(
            self._obter_cliente(),
            log,
            checkpointer=self._checkpointer,
            politica=self.politica,
            workspace_base=self.workspace_base,
            ferramentas=self.ferramentas,
            ferramentas_permitidas=self.ferramentas_permitidas,
            rotas=self.rotas,
            repositorio_orcamento=self._repositorio_orcamento,
            fabrica_tentativas_orcadas=self._fabrica_tentativas_orcadas,
        )
        try:
            snapshot = grafo.get_state(self._config(job_id))
            if getattr(snapshot, "interrupts", None):
                gates = self._gates(snapshot.interrupts)
                return {
                    "estado": "gate_pendente",
                    "gates": gates,
                    "gate": gates[0],
                }
            if snapshot.values.get("resposta_final") or snapshot.values.get("avaliacao", {}).get("abortada"):
                return self._resultado_concluido(job_id, snapshot.values)
            return {"estado": "em_execucao"}
        finally:
            if log is not self.log:
                log.fechar()

    def _registro_de_resultado(self, resultado: dict[str, Any]) -> dict[str, Any]:
        if "__interrupt__" in resultado:
            gates = self._gates(resultado["__interrupt__"])
            return {
                "estado": "gate_pendente",
                "gates": gates,
                "gate": gates[0],
            }
        if resultado.get("avaliacao", {}).get("abortada"):
            return {
                "estado": "erro",
                "erro": {
                    "tipo": "MissaoAbortada",
                    "mensagem": resultado["avaliacao"].get("motivo", "missão abortada"),
                },
            }
        return {"estado": "concluido", "resultado": resultado}

    def _resposta_de_registro(self, job_id: str, registro: dict[str, Any]) -> dict:
        if registro["estado"] == "gate_pendente":
            gates = registro.get("gates", [registro["gate"]])
            return {"estado": "gate_pendente", "gates": gates, "gate": gates[0]}
        if registro["estado"] == "concluido":
            return self._resultado_concluido(job_id, registro["resultado"])
        return {"estado": "erro", "erro": registro["erro"]}

    def _resultado_concluido(self, job_id: str, resultado: dict[str, Any]) -> dict:
        artefatos = []
        metricas = {}
        for item in resultado.get("resultados", []):
            sid = item.get("id")
            for artefato in item.get("artefatos", []):
                artefatos.append({
                    "nome": artefato.get("nome", ""),
                    "tipo": artefato.get("tipo", ""),
                    "caminho": artefato.get("caminho", ""),
                    "subagente": sid,
                })
            if sid and item.get("metricas"):
                metricas[sid] = item["metricas"]
        run_id = resultado.get("run_id") or job_id
        saida = {
            "estado": "concluido",
            "resposta_final": resultado.get("resposta_final", ""),
            "artefatos": artefatos,
            "run": self._run(job_id, run_id),
        }
        if metricas:
            saida["metricas"] = metricas
        return saida

    def _log_do_job(self, job_id: str, truncar: bool = True) -> LogEventos:
        if self.log is not None:
            return self.log
        if not truncar:
            return cast(LogEventos, _LogConsulta(self._caminho_log(job_id)))
        return LogEventos(self._caminho_log(job_id), truncar=truncar)

    def _caminho_log(self, job_id: str) -> Path:
        if self.log is not None:
            return self.log.path
        return self.workspace_base / job_id / "log.jsonl"

    def _eventos_do_job(self, job_id: str) -> list[dict[str, Any]]:
        caminho = self._caminho_log(job_id)
        if not caminho.exists():
            return []
        eventos = []
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            try:
                eventos.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
        return eventos

    def _run(self, job_id: str, run_id: str) -> dict:
        return {"job_id": job_id, "workspace": str(self.workspace_base / run_id), "log": "log.jsonl"}

    @staticmethod
    def _gates(interrupcoes: Any) -> list[dict[str, Any]]:
        gates = []
        for interrupcao in interrupcoes:
            decision_id = getattr(interrupcao, "id", None)
            if not isinstance(decision_id, str):
                raise RuntimeError("interrupt sem decision_id válido")
            gate = dict(interrupcao.value)
            gate["decision_id"] = decision_id
            gates.append(gate)
        return gates

    @staticmethod
    def _gate_resumo(gate: dict[str, Any] | None) -> dict[str, Any] | None:
        if not gate:
            return None
        return {chave: gate[chave] for chave in ("portao", "pergunta", "opcoes") if chave in gate}

    @staticmethod
    def _progresso(eventos: list[dict[str, Any]]) -> str:
        total = 0
        concluidos: set[str] = set()
        onda_atual: list[str] = []
        for evento in eventos:
            tipo = evento.get("evento")
            if tipo in {"spec.recebida", "spec.criada"}:
                total = int(evento.get("subagentes") or total or 0)
            elif tipo == "portao.aprovado" and str(evento.get("portao", "")).startswith("verifier:"):
                concluidos.add(str(evento["portao"]).split(":", 1)[1])
            elif tipo == "ferramenta.executada" and evento.get("aprovado"):
                concluidos.add(str(evento.get("subagente")))
            elif tipo == "onda.iniciada":
                onda_atual = [str(i) for i in evento.get("ids", [])]
            elif tipo == "onda.concluida":
                onda_atual = []
        if not total:
            return "progresso ainda não disponível"
        progresso = f"{len(concluidos)}/{total} subagentes concluídos"
        if onda_atual:
            progresso += f"; onda atual: {onda_atual}"
        return progresso

    @staticmethod
    def _marcos(eventos: list[dict[str, Any]]) -> list[str]:
        marcos: list[str] = []
        for evento in eventos:
            tipo = evento.get("evento")
            if tipo in {"spec.recebida", "spec.criada"}:
                marcos.append(f"planner: spec com {evento.get('subagentes', 0)} subagentes")
            elif tipo == "onda.iniciada":
                marcos.append(f"onda iniciada: {evento.get('ids', [])}")
            elif tipo == "onda.concluida":
                marcos.append(f"onda concluída: {evento.get('ids', [])}")
            elif tipo == "portao.reprovado" and evento.get("portao") == "cobertura":
                marcos.append(f"cobertura: reprovada — {len(evento.get('lacunas', []))} lacuna(s)")
            elif tipo == "portao.aprovado" and evento.get("portao") == "cobertura":
                marcos.append("cobertura: aprovada")
            elif tipo == "escalado":
                marcos.append(f"gate: escalado para {evento.get('para')}")
            elif tipo == "gate.auto":
                marcos.append(f"gate: {evento.get('portao')} auto={evento.get('decisao')}")
            elif tipo == "ferramenta.executada" and not evento.get("aprovado"):
                marcos.append(f"ferramenta: {evento.get('ferramenta')} reprovada")
            elif tipo == "tarefa.concluida":
                marcos.append("tarefa: concluída")
            elif tipo == "tarefa.abortada":
                marcos.append("tarefa: abortada")
        return marcos[-8:]

    @staticmethod
    def _resumir_resposta(resposta: str) -> str | None:
        texto = " ".join(str(resposta or "").split())
        if not texto:
            return None
        frases = re.split(r"(?<=[.!?])\s+", texto)
        resumo = " ".join(frases[:3]).strip()
        return resumo[:500]

    @staticmethod
    def _config(job_id: str) -> dict:
        return {"configurable": {"thread_id": job_id}}
