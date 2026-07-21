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

from motor.eventos_schema import valido


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


class LogEventos:
    """Writer exclusivo; checks pre-write pressupõem um diretorio pai confiavel."""

    def __init__(self, path: str | Path, truncar: bool = False):
        self._thread_lock = threading.RLock()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.path.with_name(f".{self.path.name}.lock")
        lock_fd, lock_criado = _abrir_regular_sem_links(self._lock_path, os.O_RDWR)
        try:
            self._lock_f: BinaryIO = os.fdopen(lock_fd, "a+b")
        except BaseException:
            os.close(lock_fd)
            raise
        try:
            fcntl.flock(self._lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            self._fechar_descritores()
            if isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EAGAIN):
                raise RuntimeError("log de eventos ja possui writer ativo") from exc
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
            if lock_criado:
                os.fsync(self._lock_f.fileno())
            if arquivo_criado:
                os.fsync(self._f.fileno())
            if lock_criado or arquivo_criado:
                _fsync_diretorio(self.path.parent)
            ultimo_seq, ultimo_t = self._estado_persistido()
        except BaseException:
            self._fechar_descritores()
            raise

        self._proximo_seq = ultimo_seq + 1
        self._ultimo_t = ultimo_t
        self._base_t = ultimo_t
        self._inicio_monotonico = time.monotonic()

    def _estado_persistido(self) -> tuple[int, float]:
        self._f.seek(0)
        conteudo = self._f.read()
        if not conteudo:
            return 0, 0.0
        fim_prefixo = conteudo.rfind(b"\n") + 1
        if not fim_prefixo:
            raise ValueError("log nao possui registro completo recuperavel")
        prefixo = conteudo[:fim_prefixo]
        tail = conteudo[fim_prefixo:]

        ultimo_t = 0.0
        ultimo_seq = 0
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
            if evento["seq"] != ultimo_seq + 1:
                raise ValueError(f"sequencia invalida na linha {numero_linha}")

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
        return ultimo_seq, ultimo_t

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

    def _validar_path_aberto(self) -> None:
        try:
            visivel = os.lstat(self.path)
        except FileNotFoundError as exc:
            raise RuntimeError("path do log desapareceu") from exc
        aberto = os.fstat(self._f.fileno())
        _validar_arquivo_regular(visivel, self.path)
        if (visivel.st_dev, visivel.st_ino) != (aberto.st_dev, aberto.st_ino):
            raise RuntimeError("path do log foi substituido")
        _validar_arquivo_regular(aberto, self.path)

    def evento(self, tipo_evento: str, **dados: Any) -> None:
        with self._thread_lock:
            if "evento" in dados or "t" in dados or "seq" in dados:
                raise ValueError("campo reservado no payload de evento")

            seq = self._proximo_seq
            instante = self._tempo_atual()
            e = {"t": instante, "seq": seq, "evento": tipo_evento, **dados}
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

    def _fechar_descritores(self) -> BaseException | None:
        erro: BaseException | None = None
        arquivo = getattr(self, "_f", None)
        if arquivo is not None and not arquivo.closed:
            fd = arquivo.fileno()
            try:
                arquivo.close()
            except BaseException as exc:
                erro = exc
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
        with self._thread_lock:
            erro = self._fechar_descritores()
            if erro is not None:
                raise erro
