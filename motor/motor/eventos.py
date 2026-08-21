"""Log JSONL event-sourcing — fonte da verdade auditável, independente do framework.

Formato compatível com o painel do motor v0.4: {"t": s_relativos, "evento": tipo, ...}.
O checkpointer do LangGraph cuida de resume; este log cuida de auditoria e painel.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO, NoReturn

from motor.eventos_schema import EVENTOS_MONETARIOS, _identificador_valido, valido


class WriterEventosOcupado(RuntimeError):
    """O writer exclusivo do log já está em uso por outra operação."""


def _constante_json_invalida(valor: str) -> NoReturn:
    raise ValueError(f"constante fora do JSON estrito: {valor}")


def _validar_arquivo_regular(estado: os.stat_result, path: Path) -> None:
    if not stat.S_ISREG(estado.st_mode):
        raise ValueError(f"arquivo nao regular recusado: {path}")
    if estado.st_nlink != 1:
        raise ValueError(f"hardlink recusado: {path}")


def _abrir_regular_sem_links(path: Path, flags: int) -> tuple[int, bool]:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise RuntimeError("plataforma sem suporte a O_NOFOLLOW")
    flags_seguros = flags | nofollow | getattr(os, "O_CLOEXEC", 0)

    for _ in range(3):
        esperado: os.stat_result | None
        try:
            esperado = os.lstat(path)
        except FileNotFoundError:
            esperado = None

        if esperado is None:
            try:
                fd = os.open(path, flags_seguros | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            criado = True
        else:
            _validar_arquivo_regular(esperado, path)
            try:
                fd = os.open(path, flags_seguros)
            except FileNotFoundError:
                continue
            criado = False

        try:
            aberto = os.fstat(fd)
            visivel = os.lstat(path)
            _validar_arquivo_regular(aberto, path)
            _validar_arquivo_regular(visivel, path)
            identidade = (aberto.st_dev, aberto.st_ino)
            if esperado is not None and identidade != (esperado.st_dev, esperado.st_ino):
                raise RuntimeError(f"arquivo trocado durante abertura: {path}")
            if identidade != (visivel.st_dev, visivel.st_ino):
                raise RuntimeError(f"path trocado durante abertura: {path}")
        except BaseException:
            os.close(fd)
            raise
        return fd, criado
    raise RuntimeError(f"path instavel durante abertura: {path}")


def _fsync_diretorio(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise ValueError(f"diretorio invalido: {path}")
        os.fsync(fd)
    finally:
        os.close(fd)


def _travar_writer(arquivo: BinaryIO) -> None:
    try:
        fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            raise WriterEventosOcupado("log de eventos ja possui writer ativo") from exc
        raise


class LogEventos:
    """Writer exclusivo; checks pre-write pressupõem um diretorio pai confiavel."""

    def __init__(self, path: str | Path, truncar: bool = False,
                 run_id: str | None = None):
        self.path = Path(path)
        if run_id is not None and not _identificador_valido(run_id):
            raise ValueError("run_id invalido")
        self.run_id = run_id
        self._run_ids_persistidos: set[str | None] = set()
        self._mutex = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.path.with_name(f".{self.path.name}.lock")
        lock_fd, lock_criado = _abrir_regular_sem_links(self._lock_path, os.O_RDWR)
        try:
            self._lock_f: BinaryIO = os.fdopen(lock_fd, "a+b")
        except BaseException:
            os.close(lock_fd)
            raise
        try:
            _travar_writer(self._lock_f)
        except BaseException:
            self._fechar_descritores()
            raise

        # A flag legada permanece na API, mas o writer v2 sempre abre em append.
        try:
            arquivo_fd, arquivo_criado = _abrir_regular_sem_links(
                self.path, os.O_RDWR | os.O_APPEND
            )
            try:
                self._f: BinaryIO = os.fdopen(arquivo_fd, "a+b")
            except BaseException:
                os.close(arquivo_fd)
                raise
            _travar_writer(self._f)
            if lock_criado:
                os.fsync(self._lock_f.fileno())
            if arquivo_criado:
                os.fsync(self._f.fileno())
            if lock_criado or arquivo_criado:
                _fsync_diretorio(self.path.parent)
            ultimo_seq, ultimo_t, eventos_externos = self._estado_persistido()
        except BaseException:
            self._fechar_descritores()
            raise

        self._proximo_seq = ultimo_seq + 1
        self._ultimo_t = ultimo_t
        if self.run_id is None:
            declarados = {item for item in self._run_ids_persistidos if item is not None}
            if len(declarados) == 1 and declarados == self._run_ids_persistidos:
                self.run_id = next(iter(declarados))
        self._eventos_externos = eventos_externos
        self._base_t = ultimo_t
        self._inicio_monotonico = time.monotonic()

    def _estado_persistido(self) -> tuple[int, float, dict[str, str]]:
        self._f.seek(0)
        conteudo = self._f.read()
        if not conteudo:
            return 0, 0.0, {}
        fim_prefixo = conteudo.rfind(b"\n") + 1
        if not fim_prefixo:
            raise ValueError("log nao possui registro completo recuperavel")
        prefixo = conteudo[:fim_prefixo]
        tail = conteudo[fim_prefixo:]

        ultimo_t = 0.0
        ultimo_seq = 0
        eventos_externos: dict[str, str] = {}
        for numero_linha, linha in enumerate(prefixo.splitlines(), start=1):
            try:
                evento = json.loads(linha, parse_constant=_constante_json_invalida)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"linha {numero_linha} invalida no log") from exc
            if not isinstance(evento, dict):
                raise ValueError(f"linha {numero_linha} nao contem evento")
            if "seq" not in evento:
                raise ValueError("log v1 e somente leitura")
            if not valido(evento):
                raise ValueError(f"linha {numero_linha} fora do schema v2")
            self._run_ids_persistidos.add(evento.get("run_id"))
            if self.run_id is not None and evento.get("run_id") != self.run_id:
                raise ValueError(f"linha {numero_linha} pertence a outra run")
            if evento["seq"] != ultimo_seq + 1:
                raise ValueError(f"sequencia invalida na linha {numero_linha}")
            event_id = evento.get("event_id")
            if event_id is not None:
                if event_id in eventos_externos:
                    raise ValueError(f"event_id duplicado na linha {numero_linha}")
                eventos_externos[event_id] = self._impressao_idempotente(evento)

            instante = float(evento["t"])
            if instante < ultimo_t:
                raise ValueError(f"tempo regressivo na linha {numero_linha}")
            ultimo_seq = evento["seq"]
            ultimo_t = instante

        if tail:
            self._quarentenar_tail(tail, ultimo_seq + 1)
            os.ftruncate(self._f.fileno(), fim_prefixo)
            os.fsync(self._f.fileno())
        self._f.seek(0, 2)
        return ultimo_seq, ultimo_t, eventos_externos

    def _quarentenar_tail(self, tail: bytes, proximo_seq: int) -> None:
        indice = 0
        while True:
            sufixo = "" if indice == 0 else f"-{indice}"
            quarentena = self.path.with_name(
                f"{self.path.name}.tail-{proximo_seq}{sufixo}.quarentena"
            )
            try:
                arquivo = open(quarentena, "xb")
            except FileExistsError:
                indice += 1
                continue
            break

        try:
            with arquivo:
                arquivo.write(tail)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            _fsync_diretorio(self.path.parent)
        except BaseException:
            quarentena.unlink(missing_ok=True)
            raise

    def _tempo_atual(self) -> float:
        decorrido = max(0.0, time.monotonic() - self._inicio_monotonico)
        return max(self._ultimo_t, round(self._base_t + decorrido, 3))

    @staticmethod
    def _validar_identidade_aberta(path: Path, arquivo: BinaryIO, nome: str) -> None:
        try:
            visivel = os.lstat(path)
        except FileNotFoundError as exc:
            raise RuntimeError(f"path do {nome} desapareceu") from exc
        aberto = os.fstat(arquivo.fileno())
        _validar_arquivo_regular(visivel, path)
        if (visivel.st_dev, visivel.st_ino) != (aberto.st_dev, aberto.st_ino):
            raise RuntimeError(f"path do {nome} foi substituido")
        _validar_arquivo_regular(aberto, path)

    def _validar_path_aberto(self) -> None:
        self._validar_identidade_aberta(self._lock_path, self._lock_f, "sidecar")
        self._validar_identidade_aberta(self.path, self._f, "log")

    def evento(self, tipo_evento: str, **dados: Any) -> None:
        if "run_id" in dados and tipo_evento in EVENTOS_MONETARIOS:
            run_id = dados.pop("run_id")
            if not isinstance(run_id, str):
                raise ValueError("run_id invalido")
            self.vincular_run_id(run_id)
        if {"evento", "t", "seq", "event_id", "run_id"} & dados.keys():
            raise ValueError("campo reservado no payload de evento")
        with self._mutex:
            self._escrever(tipo_evento, dados)

    def publicar_orcamento(
        self, event_id: str, tipo_evento: str, payload: dict[str, object], /
    ) -> None:
        """Persiste uma entrega do relay uma vez por ``event_id`` durável."""
        if type(payload) is not dict or {"evento", "t", "seq", "event_id"} & payload.keys():
            raise ValueError("payload externo invalido")
        payload_run_id = payload.get("run_id")
        if not isinstance(payload_run_id, str):
            raise ValueError("payload externo sem run_id")
        dados = {chave: valor for chave, valor in payload.items() if chave != "run_id"}
        dados["event_id"] = event_id
        if not valido({
            "t": 0.0, "seq": 1, "evento": tipo_evento,
            "run_id": payload_run_id, **dados,
        }):
            raise ValueError("evento fora do schema")
        with self._mutex:
            candidato = {"evento": tipo_evento, "run_id": payload_run_id, **dados}
            impressao = self._impressao_idempotente(candidato)
            anterior = self._eventos_externos.get(event_id)
            if anterior is not None:
                if anterior != impressao:
                    raise ValueError("redelivery divergente")
                self._vincular_run_id_unlocked(payload_run_id)
                return
            self._vincular_run_id_unlocked(payload_run_id)
            self._escrever(tipo_evento, dados)
            self._eventos_externos[event_id] = impressao

    @staticmethod
    def _impressao_idempotente(evento: dict[str, Any]) -> str:
        corpo = {chave: valor for chave, valor in evento.items() if chave not in {"t", "seq"}}
        return json.dumps(corpo, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False)

    def _escrever(self, tipo_evento: str, dados: dict[str, Any]) -> None:
        seq = self._proximo_seq
        instante = self._tempo_atual()
        e = {"t": instante, "seq": seq, "evento": tipo_evento, **dados}
        if self.run_id is not None:
            e["run_id"] = self.run_id
        if not valido(e):
            raise ValueError("evento fora do schema")

        linha = (json.dumps(e, ensure_ascii=False, allow_nan=False) + "\n").encode()
        try:
            self._validar_path_aberto()
            self._f.write(linha)
            self._f.flush()
            os.fsync(self._f.fileno())
        except BaseException:
            self._fechar_descritores()
            raise
        self._proximo_seq = seq + 1
        self._ultimo_t = instante

    def vincular_run_id(self, run_id: str) -> None:
        """Vincula o writer a uma execução antes da primeira emissão.

        Um logger já usado sem identidade é legado e não pode ser reclassificado
        retroativamente como uma run nova. Um logger já vinculado também não pode
        ser reutilizado por outra execução.
        """
        if not _identificador_valido(run_id):
            raise ValueError("run_id invalido")
        with self._mutex:
            self._vincular_run_id_unlocked(run_id)

    def _vincular_run_id_unlocked(self, run_id: str) -> None:
        if self.run_id is not None:
            if self.run_id != run_id:
                raise ValueError("logger vinculado a outra run")
            return
        if self._proximo_seq != 1 and self._run_ids_persistidos != {run_id}:
            raise ValueError("logger legado nao pode receber run_id")
        self.run_id = run_id

    def _fechar_descritores(self) -> BaseException | None:
        erro: BaseException | None = None
        arquivo = getattr(self, "_f", None)
        if arquivo is not None and not arquivo.closed:
            fd = arquivo.fileno()
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BaseException as exc:
                erro = exc
            try:
                arquivo.close()
            except BaseException as exc:
                erro = erro or exc
                try:
                    os.close(fd)
                except OSError as close_exc:
                    if close_exc.errno != errno.EBADF:
                        erro = erro or close_exc

        lock = getattr(self, "_lock_f", None)
        if lock is not None and not lock.closed:
            lock_fd = lock.fileno()
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            except BaseException as exc:
                erro = erro or exc
            finally:
                try:
                    lock.close()
                except BaseException as exc:
                    erro = erro or exc
                    try:
                        os.close(lock_fd)
                    except OSError as close_exc:
                        if close_exc.errno != errno.EBADF:
                            erro = erro or close_exc
        return erro

    def fechar(self) -> None:
        with self._mutex:
            erro = self._fechar_descritores()
            if erro is not None:
                raise erro
