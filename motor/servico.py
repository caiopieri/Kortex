"""Serviço programático do motor: jobs duráveis e não-bloqueantes.

O caminho de serviço estaciona em gates via interrupt/checkpointer e devolve o
controle ao chamador. Ele não decide gate, não usa input() e não liga auto-mode.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .__main__ import construir_cliente
from .eventos import LogEventos
from .grafo import construir_grafo
from .modelos import ClienteModelo
from .politica import PoliticaGates
from .registro import ferramentas_de_registro


class GerenciadorJobs:
    def __init__(self, *, db_path: str | Path = "motor.db",
                 workspace_base: str | Path = "runs",
                 cfg_modelos: dict | None = None,
                 dir_registro: str | Path | None = None,
                 politica: PoliticaGates | None = None,
                 log: LogEventos | None = None,
                 cliente: ClienteModelo | None = None,
                 ferramentas: dict[str, dict[str, Any]] | None = None):
        self.db_path = Path(db_path)
        self.workspace_base = Path(workspace_base)
        self.cfg_modelos = cfg_modelos
        self.dir_registro = str(dir_registro) if dir_registro is not None else None
        self.politica = politica or PoliticaGates()
        self.log = log
        self._cliente = cliente
        self.ferramentas = (ferramentas if ferramentas is not None else
                            ferramentas_de_registro(self.dir_registro) if self.dir_registro else {})
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._checkpointer.setup()

    def iniciar(self, *, missao_texto: str | None = None,
                spec: dict[str, Any] | None = None,
                thread_id: str) -> dict:
        """Dispara a execução em background e retorna imediatamente."""
        if bool(missao_texto) == bool(spec):
            raise ValueError("exige missao_texto XOR spec")
        if not thread_id:
            raise ValueError("thread_id é obrigatório")

        cliente = self._obter_cliente()
        entrada = {"missao_texto": missao_texto} if missao_texto is not None else {"spec": spec}
        entrada["run_id"] = thread_id
        with self._lock:
            self._jobs[thread_id] = {"estado": "em_execucao"}
        self._iniciar_thread(thread_id, cliente, entrada)
        return {"job_id": thread_id, "estado": "em_execucao"}

    def status(self, job_id: str) -> dict:
        """Estado atual sem bloquear."""
        with self._lock:
            registro = self._jobs.get(job_id)
            if registro and registro.get("estado") != "em_execucao":
                return self._resposta_de_registro(job_id, registro)
            if registro:
                return {"estado": "em_execucao"}
        return self._status_duravel(job_id)

    def responder_gate(self, job_id: str, decisao) -> dict:
        """Retoma um job pausado com a decisão humana fornecida pelo chamador."""
        atual = self.status(job_id)
        if atual.get("estado") != "gate_pendente":
            return {
                "estado": "erro",
                "erro": {
                    "tipo": "EstadoInvalido",
                    "mensagem": "job não está em gate_pendente",
                },
            }

        cliente = self._obter_cliente()
        with self._lock:
            self._jobs[job_id] = {"estado": "em_execucao"}
        self._iniciar_thread(job_id, cliente, Command(resume=decisao))
        return {"estado": "em_execucao"}

    def _obter_cliente(self) -> ClienteModelo:
        if self._cliente is not None:
            return self._cliente
        return construir_cliente(self.cfg_modelos, self.dir_registro, log=self.log)

    def _iniciar_thread(self, job_id: str, cliente: ClienteModelo, entrada: Any) -> None:
        thread = threading.Thread(
            target=self._executar,
            args=(job_id, cliente, entrada),
            name=f"motor-job-{job_id}",
            daemon=True,
        )
        thread.start()

    def _executar(self, job_id: str, cliente: ClienteModelo, entrada: Any) -> None:
        log = self._log_do_job(job_id)
        try:
            grafo = construir_grafo(
                cliente,
                log,
                checkpointer=self._checkpointer,
                politica=self.politica,
                workspace_base=self.workspace_base,
                ferramentas=self.ferramentas,
            )
            resultado = grafo.invoke(entrada, self._config(job_id))
            with self._lock:
                self._jobs[job_id] = self._registro_de_resultado(resultado)
        except Exception as ex:  # erro tratável: o gerenciador não cai
            with self._lock:
                self._jobs[job_id] = {
                    "estado": "erro",
                    "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)},
                }
        finally:
            if log is not self.log:
                log.fechar()

    def _status_duravel(self, job_id: str) -> dict:
        log = self._log_do_job(job_id, truncar=False)
        grafo = construir_grafo(
            self._obter_cliente(),
            log,
            checkpointer=self._checkpointer,
            politica=self.politica,
            workspace_base=self.workspace_base,
            ferramentas=self.ferramentas,
        )
        try:
            snapshot = grafo.get_state(self._config(job_id))
            if getattr(snapshot, "interrupts", None):
                return {
                    "estado": "gate_pendente",
                    "gate": snapshot.interrupts[0].value,
                }
            if snapshot.values.get("resposta_final") or snapshot.values.get("avaliacao", {}).get("abortada"):
                return self._resultado_concluido(job_id, snapshot.values)
            return {"estado": "em_execucao"}
        finally:
            if log is not self.log:
                log.fechar()

    def _registro_de_resultado(self, resultado: dict[str, Any]) -> dict[str, Any]:
        if "__interrupt__" in resultado:
            return {
                "estado": "gate_pendente",
                "gate": resultado["__interrupt__"][0].value,
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
            return {"estado": "gate_pendente", "gate": registro["gate"]}
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
            "run": {
                "job_id": job_id,
                "workspace": str(self.workspace_base / run_id),
                "log": "log.jsonl",
            },
        }
        if metricas:
            saida["metricas"] = metricas
        return saida

    def _log_do_job(self, job_id: str, truncar: bool = True) -> LogEventos:
        if self.log is not None:
            return self.log
        return LogEventos(self.workspace_base / job_id / "log.jsonl", truncar=truncar)

    @staticmethod
    def _config(job_id: str) -> dict:
        return {"configurable": {"thread_id": job_id}}
