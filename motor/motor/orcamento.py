"""Ledger monetario duravel com migração SQLite e transições atômicas por reserva."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal, Protocol, TypeAlias, cast

from .eventos_schema import valido


Moeda = Literal["BRL", "TOKEN"]
StatusSessao: TypeAlias = Literal["ACTIVE", "INVALIDATED"]
StatusReserva: TypeAlias = Literal["RESERVED", "RECONCILED", "CONTRACT_VIOLATED", "UNKNOWN_COST"]
StatusTentativaTerminal: TypeAlias = Literal[
    "BLOQUEADA", "REPLAY_AMBIGUO", "REPLAY_FINALIZADO", "CONTRACT_VIOLATED", "UNKNOWN_COST",
]
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_MAX_DECIMAL_CHARS = 128
_PRECISAO_SOMA = 2 * _MAX_DECIMAL_CHARS + 1
_MOEDA_DO_REPOSITORIO = object()
_ARQUIVO_POR_MOEDA: dict[Moeda, str] = {
    "BRL": "orcamento.sqlite3",
    "TOKEN": "cota.sqlite3",
}
# BRL primeiro preserva a ordem observável do relay legado; TOKEN vem depois,
# independentemente da ordem de inserção do mapa de dependências.
ORDEM_DRENO_MOEDAS: tuple[Moeda, ...] = ("BRL", "TOKEN")


class ErroOrcamento(ValueError):
    """Contrato financeiro ou de identidade rejeitado antes de efeito externo."""


@dataclass(frozen=True)
class RequisitosTentativaCusteada:
    """Sinais de roteamento que a fabrica deve preservar sem executar efeitos."""

    tier: str | None = None
    ferramentas: str | None = None
    capacidades: tuple[str, ...] | None = None
    evitar_provedor: str | None = None


@dataclass(frozen=True)
class RespostaTentativaCusteada:
    texto: str
    route_id: str
    provider_id: str


@dataclass(frozen=True)
class CotacaoTentativa:
    maximo: Decimal
    moeda: Moeda
    pricing_version: str

    def __post_init__(self) -> None:
        _decimal(self.maximo, positivo=True)
        if (
            type(self.moeda) is not str
            or self.moeda not in _ARQUIVO_POR_MOEDA
            or not _identificador(self.pricing_version)
        ):
            raise ErroOrcamento("cotacao invalida")


@dataclass(frozen=True)
class ResultadoTentativa:
    texto: str | None
    custo_real: Decimal
    moeda: Moeda
    usage_ref: str

    def __post_init__(self) -> None:
        _decimal(self.custo_real)
        if (
            type(self.moeda) is not str
            or self.moeda not in _ARQUIVO_POR_MOEDA
            or not _identificador(self.usage_ref)
        ):
            raise ErroOrcamento("resultado invalido")


@dataclass(frozen=True)
class TentativaReconciliada:
    resultado: ResultadoTentativa


@dataclass(frozen=True)
class TentativaBloqueadaPreEfeito:
    motivo: Literal["sem_adapter", "sem_cotacao", "teto"]


@dataclass(frozen=True)
class TentativaTerminal:
    motivo: str
    status_reserva: StatusTentativaTerminal


ResultadoExecucaoTentativa: TypeAlias = (
    TentativaReconciliada | TentativaBloqueadaPreEfeito | TentativaTerminal
)


@dataclass(frozen=True)
class SessaoOrcamento:
    run_id: str
    thread_id: str
    moeda: Moeda
    teto: Decimal
    gasto: Decimal
    reservado: Decimal
    status: StatusSessao


@dataclass(frozen=True)
class ReservaOrcamento:
    reservation_id: str
    call_id: str
    route_id: str
    attempt: int
    maximo: Decimal
    pricing_version: str
    status: StatusReserva = "RESERVED"


StatusReservaExclusiva: TypeAlias = Literal["NOVA", "REPLAY_AMBIGUO", "REPLAY_FINALIZADO", "BLOQUEADA"]


@dataclass(frozen=True)
class ResultadoReservaExclusiva:
    status: StatusReservaExclusiva
    reserva: ReservaOrcamento
    motivo: str | None = None


@dataclass(frozen=True)
class EventoOrcamentoPendente:
    event_id: str
    tipo: str
    payload: dict[str, object]
    owner: str | None = None
    lease_ate: int | None = None
    tentativas: int = 0


class ClienteTentativaCusteada(Protocol):
    def cotar_tentativa(self) -> CotacaoTentativa: ...
    def tentar_uma_vez(self) -> ResultadoTentativa: ...


class PublicadorEventoOrcamento(Protocol):
    def __call__(self, event_id: str, tipo: str, payload: dict[str, object], /) -> None: ...


@dataclass(frozen=True)
class RotaTentativaCusteada:
    """Candidato da TCB: provider canônico e adaptador de uma tentativa, sem fallback interno."""

    route_id: str
    provider_id: str
    adaptador: ClienteTentativaCusteada
    moeda: Moeda = "BRL"

    def __post_init__(self) -> None:
        if (
            not _identificador(self.route_id)
            or not _identificador(self.provider_id)
            or type(self.moeda) is not str
            or self.moeda not in _ARQUIVO_POR_MOEDA
        ):
            raise ErroOrcamento("identidade de rota custeada invalida")


@dataclass(frozen=True)
class IdentidadeTentativaCusteada:
    reservation_id: str
    call_id: str
    route_id: str
    attempt: int


def _identificador(valor: object) -> bool:
    return (
        type(valor) is str and 0 < len(valor) <= 128 and valor == valor.strip()
        and valor.isprintable() and "/" not in valor and "\\" not in valor
        and ".." not in valor and not re.match(r"[A-Za-z]:", valor)
    )


def _id(valor: object, nome: str) -> str:
    if not _identificador(valor):
        raise ErroOrcamento(f"{nome} invalido")
    return str(valor)


def _decimal(valor: object, *, positivo: bool = False) -> Decimal:
    if type(valor) is not Decimal or not valor.is_finite() or (positivo and valor <= 0) or valor < 0:
        raise ErroOrcamento("decimal invalido")
    _texto_decimal(valor)
    return valor


def _texto_decimal(valor: Decimal) -> str:
    """Expande Decimal sem ``normalize`` ou contexto mutavel e com limite previo."""
    partes = valor.as_tuple()
    digitos, expoente = partes.digits, partes.exponent
    if not isinstance(expoente, int) or len(digitos) > _MAX_DECIMAL_CHARS:
        raise ErroOrcamento("escala invalida")
    tamanho = len(digitos)
    while tamanho > 1 and digitos[tamanho - 1] == 0:
        tamanho -= 1
        expoente += 1
    if digitos[0] == 0:
        return "0"
    ponto = tamanho + expoente
    comprimento = tamanho + expoente if expoente >= 0 else tamanho + 1 if ponto > 0 else 2 - expoente
    if comprimento > _MAX_DECIMAL_CHARS:
        raise ErroOrcamento("escala invalida")
    coeficiente = "".join(map(str, digitos[:tamanho]))
    if expoente >= 0:
        return coeficiente + "0" * expoente
    if ponto > 0:
        return coeficiente[:ponto] + "." + coeficiente[ponto:]
    return "0." + "0" * -ponto + coeficiente


def _texto(valor: Decimal) -> str:
    return _texto_decimal(_decimal(valor))


def _do_texto(valor: object) -> Decimal:
    if type(valor) is not str or len(valor) > _MAX_DECIMAL_CHARS or _DECIMAL.fullmatch(valor) is None:
        raise ErroOrcamento("banco de dados corrompido")
    try:
        numero = Decimal(valor)
    except Exception as erro:
        raise ErroOrcamento("banco de dados corrompido") from erro
    if _texto(numero) != valor:
        raise ErroOrcamento("banco de dados corrompido")
    return numero


def _soma(esquerda: Decimal, direita: Decimal) -> Decimal:
    with localcontext() as contexto:
        contexto.prec = _PRECISAO_SOMA
        contexto.Emax = _MAX_DECIMAL_CHARS
        contexto.Emin = -_MAX_DECIMAL_CHARS
        return esquerda + direita


def _tempo(valor: object, nome: str, *, positivo: bool = False) -> int:
    if type(valor) is not int or (positivo and valor <= 0) or not -(2**63) <= valor < 2**63:
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _validar_identidade(valor: object) -> IdentidadeTentativaCusteada:
    if type(valor) is not IdentidadeTentativaCusteada:
        raise ErroOrcamento("identidade invalida")
    _id(valor.reservation_id, "reservation_id")
    _id(valor.call_id, "call_id")
    _id(valor.route_id, "route_id")
    if type(valor.attempt) is not int or valor.attempt < 1:
        raise ErroOrcamento("attempt invalido")
    return valor


def validar_identidade_tentativa(valor: object) -> IdentidadeTentativaCusteada:
    """Valida uma identidade sem produzir transicao no ledger."""
    return _validar_identidade(valor)


class RepositorioOrcamento:
    def __init__(self, raiz: Path, *, moeda: Moeda = "BRL") -> None:
        self._raiz = raiz.resolve()
        if type(moeda) is not str or moeda not in _ARQUIVO_POR_MOEDA:
            raise ErroOrcamento("moeda invalida")
        self._moeda: Moeda = cast(Moeda, moeda)
        self._nome_arquivo: str = _ARQUIVO_POR_MOEDA[self._moeda]

    @property
    def moeda(self) -> Moeda:
        return self._moeda

    def caminho(self, run_id: str) -> Path:
        run_id = _id(run_id, "run_id")
        esperado = self._raiz / run_id
        esperado.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            diretorio = esperado.lstat()
        except OSError as erro:
            raise ErroOrcamento("diretorio de run nao e seguro") from erro
        if (not stat.S_ISDIR(diretorio.st_mode) or diretorio.st_uid != os.geteuid()
                or stat.S_IMODE(diretorio.st_mode) & 0o022):
            raise ErroOrcamento("diretorio de run nao e seguro")
        arquivo = esperado / self._nome_arquivo
        try:
            fd = os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            pass
        except OSError as erro:
            raise ErroOrcamento("arquivo de ledger inseguro") from erro
        else:
            os.close(fd)
        try:
            arquivo_stat = arquivo.lstat()
        except OSError as erro:
            raise ErroOrcamento("arquivo de ledger inseguro") from erro
        if stat.S_ISLNK(arquivo_stat.st_mode):
            raise ErroOrcamento("symlink nao permitido")
        if (not stat.S_ISREG(arquivo_stat.st_mode) or arquivo_stat.st_uid != os.geteuid()
                or arquivo_stat.st_nlink != 1 or stat.S_IMODE(arquivo_stat.st_mode) != 0o600):
            raise ErroOrcamento("arquivo de ledger inseguro")
        # Ainda ha TOCTOU entre lstat e sqlite.connect; a raiz precisa ser privada ao processo.
        return arquivo

    def possui_ledger(self, run_id: str) -> bool:
        """Consulta existência sem criar diretório, arquivo ou schema."""
        run_id = _id(run_id, "run_id")
        arquivo = self._raiz / run_id / self._nome_arquivo
        try:
            arquivo.lstat()
        except FileNotFoundError:
            return False
        return self.caminho(run_id) == arquivo

    def sessao(self, run_id: str, thread_id: str, teto: Decimal) -> SessaoOrcamento:
        run_id, thread_id = _id(run_id, "run_id"), _id(thread_id, "thread_id")
        teto = _decimal(teto, positivo=True)
        try:
            with self._conexao(run_id) as con:
                con.execute("BEGIN IMMEDIATE")
                linha = con.execute("SELECT teto,gasto,reservado,status FROM budget_session WHERE run_id=? AND thread_id=?", (run_id, thread_id)).fetchone()
                if linha is None:
                    con.execute("INSERT INTO budget_session (run_id,thread_id,teto,moeda,gasto,reservado,status) VALUES (?,?,?,?,?,?,?)", (run_id, thread_id, _texto(teto), self._moeda, "0", "0", "ACTIVE"))
                    linha = (_texto(teto), "0", "0", "ACTIVE")
                dados = tuple(_do_texto(campo) for campo in linha[:3])
                if linha[3] not in ("ACTIVE", "INVALIDATED"):
                    raise ErroOrcamento("banco de dados corrompido")
                teto = _do_texto(_texto(teto))
                if dados[0] != teto:
                    # O teto so aperta. O planner gasta antes de a spec existir,
                    # entao a sessao nasce no teto de bootstrap e e estreitada
                    # quando a missao declara o seu; afrouxar seria contornar a
                    # unica contencao monetaria do sistema.
                    if teto > dados[0]:
                        raise ErroOrcamento("teto divergente para sessao existente")
                    if teto < dados[1] + dados[2]:
                        raise ErroOrcamento("teto abaixo do ja comprometido")
                    con.execute("UPDATE budget_session SET teto=? WHERE run_id=? AND thread_id=?", (_texto(teto), run_id, thread_id))
                    dados = (teto, dados[1], dados[2])
                return SessaoOrcamento(run_id=run_id, thread_id=thread_id, moeda=self._moeda, teto=dados[0], gasto=dados[1], reservado=dados[2], status=linha[3])
        except sqlite3.Error as erro:
            raise ErroOrcamento("ledger indisponivel ou corrompido") from erro

    def reservar(self, sessao: SessaoOrcamento, reserva: ReservaOrcamento) -> ReservaOrcamento:
        """API H12b1 compatível; replay continua idempotente, mas não é seguro para efeito."""
        resultado = self.reservar_exclusiva(sessao, reserva)
        if resultado.status == "BLOQUEADA":
            raise ErroOrcamento(resultado.motivo or "reserva bloqueada")
        return resultado.reserva

    def bloquear(self, sessao: SessaoOrcamento, identidade: IdentidadeTentativaCusteada,
                 motivo: Literal["sem_adapter", "sem_cotacao"]) -> None:
        """Persiste bloqueio pré-efeito sem criar reserva nem alterar saldo."""
        self._validar_sessao(sessao)
        identidade = _validar_identidade(identidade)
        reserva = ReservaOrcamento(
            identidade.reservation_id, identidade.call_id, identidade.route_id,
            identidade.attempt, Decimal("1"), "bloqueado",
        )
        try:
            with self._conexao(sessao.run_id) as con:
                con.execute("BEGIN IMMEDIATE")
                linha = con.execute("SELECT teto,gasto,reservado,status FROM budget_session WHERE run_id=? AND thread_id=?", (sessao.run_id, sessao.thread_id)).fetchone()
                if linha is None:
                    raise ErroOrcamento("sessao ausente")
                self._bloquear(con, sessao, reserva, motivo, linha)
        except sqlite3.Error as erro:
            raise ErroOrcamento("ledger indisponivel ou corrompido") from erro

    def reservar_exclusiva(self, sessao: SessaoOrcamento, reserva: ReservaOrcamento) -> ResultadoReservaExclusiva:
        """Reserva antes do efeito; somente ``NOVA`` pode autorizar uma chamada externa.

        Uma reserva RESERVED já existente é ambígua após crash e nunca deve ser reutilizada
        para executar o transporte outra vez.
        """
        self._validar_sessao(sessao)
        for nome in ("reservation_id", "call_id", "route_id", "pricing_version"):
            _id(getattr(reserva, nome), nome)
        if type(reserva.attempt) is not int or reserva.attempt < 1 or reserva.status != "RESERVED":
            raise ErroOrcamento("reserva invalida")
        maximo = _decimal(reserva.maximo, positivo=True)
        try:
            with self._conexao(sessao.run_id) as con:
                con.execute("BEGIN IMMEDIATE")
                dono = con.execute("SELECT run_id,thread_id,call_id,route_id,attempt FROM budget_reservation WHERE reservation_id=?", (reserva.reservation_id,)).fetchone()
                chave = (sessao.run_id, sessao.thread_id, reserva.call_id, reserva.route_id, reserva.attempt)
                if dono is not None and tuple(dono) != chave:
                    raise ErroOrcamento("reservation_id ja existe")
                existente = con.execute("SELECT reservation_id,call_id,route_id,attempt,maximo,pricing_version,status FROM budget_reservation WHERE run_id=? AND thread_id=? AND call_id=? AND route_id=? AND attempt=?", chave).fetchone()
                if existente is not None:
                    if tuple(existente[:6]) != (reserva.reservation_id, reserva.call_id, reserva.route_id, reserva.attempt, _texto(maximo), reserva.pricing_version):
                        raise ErroOrcamento("replay divergente")
                    if existente[6] == "RESERVED":
                        return ResultadoReservaExclusiva("REPLAY_AMBIGUO", reserva)
                    if existente[6] in ("RECONCILED", "CONTRACT_VIOLATED", "UNKNOWN_COST"):
                        finalizada = ReservaOrcamento(
                            reserva.reservation_id, reserva.call_id, reserva.route_id, reserva.attempt,
                            maximo, reserva.pricing_version, existente[6],
                        )
                        return ResultadoReservaExclusiva("REPLAY_FINALIZADO", finalizada)
                    raise ErroOrcamento("reserva corrompida")
                linha = con.execute("SELECT teto,gasto,reservado,status FROM budget_session WHERE run_id=? AND thread_id=?", (sessao.run_id, sessao.thread_id)).fetchone()
                if linha is None:
                    raise ErroOrcamento("sessao ausente")
                if linha[3] != "ACTIVE":
                    self._bloquear(con, sessao, reserva, "sessao_invalida", linha)
                    return ResultadoReservaExclusiva("BLOQUEADA", reserva, "sessao nao ativa")
                teto, gasto, reservado = (_do_texto(campo) for campo in linha[:3])
                novo_reservado = _soma(reservado, maximo)
                if _soma(gasto, novo_reservado) > teto:
                    self._bloquear(con, sessao, reserva, "teto", linha)
                    return ResultadoReservaExclusiva("BLOQUEADA", reserva, "teto excedido")
                con.execute("INSERT INTO budget_reservation (reservation_id,run_id,thread_id,call_id,route_id,attempt,maximo,real,moeda_real,pricing_version,status,created_at,reconciled_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (reserva.reservation_id, sessao.run_id, sessao.thread_id, reserva.call_id, reserva.route_id, reserva.attempt, _texto(maximo), None, None, reserva.pricing_version, "RESERVED", None, None))
                con.execute("UPDATE budget_session SET reservado=? WHERE run_id=? AND thread_id=?", (_texto(novo_reservado), sessao.run_id, sessao.thread_id))
                self._outbox(con, reserva.reservation_id, "custo.reservado", self._payload(
                    sessao, reserva, teto, gasto, novo_reservado,
                    reservation_id=reserva.reservation_id, maximo=_texto(maximo),
                    pricing_version=reserva.pricing_version))
                return ResultadoReservaExclusiva("NOVA", reserva)
        except sqlite3.Error as erro:
            raise ErroOrcamento("ledger indisponivel ou corrompido") from erro

    def _event_id(self, reservation_id: str, tipo: str) -> str:
        prefixo = "" if self._moeda == "BRL" else f"{self._moeda}\0"
        return hashlib.sha256(f"{prefixo}{reservation_id}\0{tipo}".encode()).hexdigest()

    def _payload(self, sessao: SessaoOrcamento, reserva: ReservaOrcamento,
                 teto: Decimal, gasto: Decimal, reservado: Decimal, **extra: object) -> dict[str, object]:
        return {
            "run_id": sessao.run_id, "thread_id": sessao.thread_id,
            "call_id": reserva.call_id, "rota": reserva.route_id, "tentativa": reserva.attempt,
            "moeda": self._moeda, "teto": _texto(teto), "gasto": _texto(gasto),
            "reservado": _texto(reservado), **extra,
        }

    def _outbox(self, con: sqlite3.Connection, reservation_id: str, tipo: str,
                payload: dict[str, object]) -> None:
        if not self._payload_valido(tipo, payload):
            raise ErroOrcamento("payload invalido")
        event_id = self._event_id(reservation_id, tipo)
        canonico = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        existentes = con.execute(
            "SELECT event_id,reservation_id,tipo,payload FROM budget_outbox "
            "WHERE event_id=? OR (reservation_id=? AND tipo=?)",
            (event_id, reservation_id, tipo),
        ).fetchall()
        esperado = (event_id, reservation_id, tipo, canonico)
        if existentes:
            if any(tuple(linha) != esperado for linha in existentes):
                raise ErroOrcamento("colisao outbox ou payload divergente")
            return
        con.execute(
            "INSERT INTO budget_outbox (event_id,reservation_id,tipo,payload) VALUES (?,?,?,?)",
            esperado,
        )

    def _payload_valido(self, tipo: object, payload: object) -> bool:
        if not isinstance(tipo, str) or not isinstance(payload, dict):
            return False
        if {"evento", "t", "seq"} & payload.keys():
            return False
        return (
            payload.get("moeda") == self._moeda
            and valido({**payload, "evento": tipo, "t": 0.0, "seq": 1})
        )

    def _bloquear(self, con: sqlite3.Connection, sessao: SessaoOrcamento,
                  reserva: ReservaOrcamento, motivo: str, linha: tuple[object, ...]) -> None:
        teto, gasto, reservado = (_do_texto(campo) for campo in linha[:3])
        self._outbox(con, reserva.reservation_id, "custo.bloqueado", self._payload(
            sessao, reserva, teto, gasto, reservado, motivo=motivo))

    def listar_pendentes(self, run_id: str) -> list[EventoOrcamentoPendente]:
        """Lê a outbox em ordem determinística; publicação/ack pertencem a outra fatia."""
        try:
            with sqlite3.connect(f"{self.caminho(run_id).as_uri()}?mode=ro", uri=True) as con:
                tem_claim = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='budget_outbox_claim'").fetchone() is not None
                consulta = (
                    "SELECT o.event_id,o.reservation_id,o.tipo,o.payload,COALESCE(c.estado,'PENDING'),c.owner,c.lease_ate,COALESCE(c.tentativas,0) "
                    "FROM budget_outbox o LEFT JOIN budget_outbox_claim c USING(event_id) WHERE COALESCE(c.estado,'PENDING')!='ACKED' ORDER BY o.rowid"
                    if tem_claim else
                    "SELECT event_id,reservation_id,tipo,payload,'PENDING',NULL,NULL,0 FROM budget_outbox ORDER BY rowid"
                )
                linhas = con.execute(consulta).fetchall()
        except sqlite3.Error as erro:
            raise ErroOrcamento("outbox indisponivel ou corrompida") from erro
        return [self._evento_outbox(linha) for linha in linhas]

    def reivindicar_pendente(self, run_id: str, owner: str, agora: int,
                             lease_s: int) -> EventoOrcamentoPendente | None:
        run_id, owner = _id(run_id, "run_id"), _id(owner, "owner")
        agora, lease_s = _tempo(agora, "agora"), _tempo(lease_s, "lease_s", positivo=True)
        lease_ate = _tempo(agora + lease_s, "lease_ate")
        try:
            with self._conexao(run_id) as con:
                con.execute("BEGIN IMMEDIATE")
                linha = con.execute(
                    "SELECT o.event_id,o.reservation_id,o.tipo,o.payload,COALESCE(c.estado,'PENDING'),"
                    "c.owner,c.lease_ate,COALESCE(c.tentativas,0) FROM budget_outbox o "
                    "LEFT JOIN budget_outbox_claim c USING(event_id) WHERE COALESCE(c.estado,'PENDING')='PENDING' "
                    "OR (c.estado='CLAIMED' AND c.lease_ate<=?) ORDER BY o.rowid LIMIT 1", (agora,)).fetchone()
                if linha is None:
                    return None
                evento = self._evento_outbox(linha)
                if evento.tentativas >= 2**63 - 1:
                    raise ErroOrcamento("tentativas excedidas")
                con.execute(
                    "INSERT INTO budget_outbox_claim VALUES (?, 'CLAIMED', ?, ?, ?) "
                    "ON CONFLICT(event_id) DO UPDATE SET estado='CLAIMED',owner=excluded.owner,"
                    "lease_ate=excluded.lease_ate,tentativas=excluded.tentativas",
                    (evento.event_id, owner, lease_ate, evento.tentativas + 1))
                return EventoOrcamentoPendente(evento.event_id, evento.tipo, evento.payload, owner, lease_ate, evento.tentativas + 1)
        except sqlite3.Error as erro:
            raise ErroOrcamento("outbox indisponivel ou corrompida") from erro

    def confirmar_pendente(self, run_id: str, event_id: str, owner: str) -> None:
        run_id, event_id, owner = _id(run_id, "run_id"), _id(event_id, "event_id"), _id(owner, "owner")
        try:
            with self._conexao(run_id) as con:
                con.execute("BEGIN IMMEDIATE")
                linha = con.execute(
                    "SELECT o.event_id,o.reservation_id,o.tipo,o.payload,COALESCE(c.estado,'PENDING'),"
                    "c.owner,c.lease_ate,COALESCE(c.tentativas,0) FROM budget_outbox o "
                    "LEFT JOIN budget_outbox_claim c USING(event_id) WHERE o.event_id=?", (event_id,)).fetchone()
                if linha is None:
                    raise ErroOrcamento("evento ausente")
                self._evento_outbox(linha)
                alterado = con.execute(
                    "UPDATE budget_outbox_claim SET estado='ACKED',owner=NULL,lease_ate=NULL "
                    "WHERE event_id=? AND estado='CLAIMED' AND owner=?", (event_id, owner)).rowcount
                if alterado != 1:
                    raise ErroOrcamento("claim invalido")
        except sqlite3.Error as erro:
            raise ErroOrcamento("outbox indisponivel ou corrompida") from erro

    def _evento_outbox(self, linha: tuple[object, ...]) -> EventoOrcamentoPendente:
        event_id, reservation_id, tipo, bruto, estado, owner, lease_ate, tentativas = linha
        if not isinstance(bruto, str):
            raise ErroOrcamento("outbox corrompida")
        try:
            payload = json.loads(bruto)
        except (TypeError, json.JSONDecodeError) as erro:
            raise ErroOrcamento("outbox corrompida") from erro
        if (
            not isinstance(event_id, str) or not isinstance(reservation_id, str) or not isinstance(tipo, str)
            or event_id != self._event_id(reservation_id, tipo) or not self._payload_valido(tipo, payload)
            or type(tentativas) is not int or tentativas < 0
            or estado == "PENDING" and (owner is not None or lease_ate is not None)
            or estado == "CLAIMED" and (not _identificador(owner) or type(lease_ate) is not int)
            or estado == "ACKED" and (owner is not None or lease_ate is not None)
            or estado not in ("PENDING", "CLAIMED", "ACKED")
        ):
            raise ErroOrcamento("outbox corrompida")
        return EventoOrcamentoPendente(
            event_id, tipo, payload, cast(str | None, owner), cast(int | None, lease_ate), tentativas
        )

    def reconciliar(
        self,
        sessao: SessaoOrcamento,
        reserva: ReservaOrcamento,
        custo_real: object,
        moeda: object = _MOEDA_DO_REPOSITORIO,
    ) -> ReservaOrcamento:
        self._validar_sessao(sessao)
        if moeda is _MOEDA_DO_REPOSITORIO:
            moeda = self._moeda
        _id(reserva.reservation_id, "reservation_id")
        _id(reserva.call_id, "call_id")
        _id(reserva.route_id, "route_id")
        _id(reserva.pricing_version, "pricing_version")
        if type(reserva.attempt) is not int or reserva.attempt < 1:
            raise ErroOrcamento("reserva invalida")
        try:
            with self._conexao(sessao.run_id) as con:
                con.execute("BEGIN IMMEDIATE")
                linha = con.execute("SELECT call_id,route_id,attempt,maximo,pricing_version,real,moeda_real,status FROM budget_reservation WHERE reservation_id=? AND run_id=? AND thread_id=?", (reserva.reservation_id, sessao.run_id, sessao.thread_id)).fetchone()
                if linha is None:
                    raise ErroOrcamento("reserva ausente")
                maximo = _decimal(reserva.maximo, positivo=True)
                if tuple(linha[:5]) != (reserva.call_id, reserva.route_id, reserva.attempt, _texto(maximo), reserva.pricing_version):
                    raise ErroOrcamento("reserva divergente")
                status, real, moeda_real, consumir = self._resultado(custo_real, moeda, maximo)
                esperado = (status, None if real is None else _texto(real), moeda_real)
                if linha[7] != "RESERVED":
                    if tuple(linha[5:]) != (esperado[1], esperado[2], esperado[0]):
                        raise ErroOrcamento("replay de reconciliacao divergente")
                    return ReservaOrcamento(reserva.reservation_id, reserva.call_id, reserva.route_id, reserva.attempt, maximo, reserva.pricing_version, status)
                sessao_db = con.execute("SELECT teto,gasto,reservado,status FROM budget_session WHERE run_id=? AND thread_id=?", (sessao.run_id, sessao.thread_id)).fetchone()
                if sessao_db is None or sessao_db[3] != "ACTIVE":
                    raise ErroOrcamento("sessao ausente ou inativa")
                teto, gasto, reservado = (_do_texto(valor) for valor in sessao_db[:3])
                novo_gasto, novo_reservado = gasto, reservado
                if status == "RECONCILED":
                    if real is None:
                        raise ErroOrcamento("resultado invalido")
                    novo_gasto, novo_reservado = _soma(gasto, real), _soma(reservado, -maximo)
                elif consumir:
                    if real is None:
                        raise ErroOrcamento("resultado invalido")
                    novo_gasto, novo_reservado = _soma(gasto, real), _soma(reservado, -maximo)
                con.execute("UPDATE budget_reservation SET real=?,moeda_real=?,status=? WHERE reservation_id=?", (esperado[1], esperado[2], esperado[0], reserva.reservation_id))
                con.execute("UPDATE budget_session SET gasto=?,reservado=?,status=? WHERE run_id=? AND thread_id=?", (_texto(novo_gasto), _texto(novo_reservado), "ACTIVE" if status == "RECONCILED" else "INVALIDATED", sessao.run_id, sessao.thread_id))
                if status == "RECONCILED":
                    if real is None:
                        raise ErroOrcamento("resultado invalido")
                    self._outbox(con, reserva.reservation_id, "custo.reconciliado", self._payload(
                        sessao, reserva, teto, novo_gasto, novo_reservado,
                        reservation_id=reserva.reservation_id, maximo=_texto(maximo),
                        custo_real=_texto(real), delta_liberado=_texto(_soma(maximo, -real)),
                        pricing_version=reserva.pricing_version))
                else:
                    motivo = (
                        "custo_invalido" if status == "UNKNOWN_COST"
                        else "moeda_divergente" if moeda_real != self._moeda else "custo_acima_maximo"
                    )
                    self._outbox(con, reserva.reservation_id, "custo.contrato_violado", self._payload(
                        sessao, reserva, teto, novo_gasto, novo_reservado,
                        reservation_id=reserva.reservation_id, maximo=_texto(maximo),
                        custo_real=None if real is None else _texto(real), moeda_recebida=moeda_real or self._moeda,
                        pricing_version=reserva.pricing_version, motivo=motivo))
                return ReservaOrcamento(reserva.reservation_id, reserva.call_id, reserva.route_id, reserva.attempt, maximo, reserva.pricing_version, status)
        except sqlite3.Error as erro:
            raise ErroOrcamento("ledger indisponivel ou corrompido") from erro

    def _resultado(self, custo: object, moeda: object, maximo: Decimal) -> tuple[StatusReserva, Decimal | None, str | None, bool]:
        if type(custo) is not Decimal or not custo.is_finite() or custo < 0:
            return "UNKNOWN_COST", None, self._moeda, False
        real = _decimal(custo)
        if type(moeda) is not str or not _identificador(moeda):
            return "UNKNOWN_COST", None, self._moeda, False
        if moeda != self._moeda:
            return "CONTRACT_VIOLATED", real, moeda, False
        return ("RECONCILED" if real <= maximo else "CONTRACT_VIOLATED"), real, moeda, True

    def _validar_sessao(self, sessao: object) -> SessaoOrcamento:
        if type(sessao) is not SessaoOrcamento or sessao.moeda != self._moeda:
            raise ErroOrcamento("sessao de outra moeda")
        _id(sessao.run_id, "run_id")
        _id(sessao.thread_id, "thread_id")
        return sessao

    def _conexao(self, run_id: str) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho(run_id), isolation_level=None, timeout=2)
        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("BEGIN IMMEDIATE")
            check_moeda = (
                "CHECK (moeda='BRL')"
                if self._moeda == "BRL"
                else "CHECK (moeda='TOKEN')"
            )
            schema_sessao = (
                "CREATE TABLE IF NOT EXISTS budget_session ("
                "run_id TEXT NOT NULL, thread_id TEXT NOT NULL, teto TEXT NOT NULL, "
                "moeda TEXT NOT NULL, gasto TEXT NOT NULL, reservado TEXT NOT NULL, "
                "status TEXT NOT NULL, PRIMARY KEY (run_id, thread_id), "
                + check_moeda
                + ", CHECK (status IN ('ACTIVE','INVALIDATED')), "
                "CHECK (typeof(teto)='text' AND typeof(gasto)='text' "
                "AND typeof(reservado)='text'))"
            )
            con.execute(schema_sessao)
            con.execute("""CREATE TABLE IF NOT EXISTS budget_reservation (
              reservation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, thread_id TEXT NOT NULL,
              call_id TEXT NOT NULL, route_id TEXT NOT NULL, attempt INTEGER NOT NULL, maximo TEXT NOT NULL,
              real TEXT, moeda_real TEXT, pricing_version TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT, reconciled_at TEXT,
              UNIQUE (run_id,thread_id,call_id,route_id,attempt),
              FOREIGN KEY (run_id,thread_id) REFERENCES budget_session(run_id,thread_id),
              CHECK (status IN ('RESERVED','RECONCILED','CONTRACT_VIOLATED','UNKNOWN_COST')),
              CHECK (typeof(maximo)='text' AND (real IS NULL OR typeof(real)='text')))""")
            con.execute("""CREATE TABLE IF NOT EXISTS budget_outbox (
              event_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL, tipo TEXT NOT NULL, payload TEXT NOT NULL,
              UNIQUE (reservation_id,tipo),
              CHECK (tipo IN ('custo.reservado','custo.reconciliado','custo.bloqueado','custo.contrato_violado')),
              CHECK (typeof(payload)='text'))""")
            con.execute("""CREATE TABLE IF NOT EXISTS budget_outbox_claim (
              event_id TEXT PRIMARY KEY, estado TEXT NOT NULL, owner TEXT, lease_ate INTEGER,
              tentativas INTEGER NOT NULL DEFAULT 0, FOREIGN KEY (event_id) REFERENCES budget_outbox(event_id),
              CHECK (estado IN ('PENDING','CLAIMED','ACKED')), CHECK (tentativas>=0),
              CHECK ((estado='CLAIMED' AND owner IS NOT NULL AND lease_ate IS NOT NULL) OR
                     (estado IN ('PENDING','ACKED') AND owner IS NULL AND lease_ate IS NULL)))""")
            con.execute("INSERT INTO budget_outbox_claim (event_id,estado,tentativas) "
                        "SELECT o.event_id,'PENDING',0 FROM budget_outbox o WHERE NOT EXISTS "
                        "(SELECT 1 FROM budget_outbox_claim c WHERE c.event_id=o.event_id)")
            if con.execute(
                "SELECT 1 FROM budget_session WHERE moeda<>? LIMIT 1", (self._moeda,)
            ).fetchone() is not None:
                raise sqlite3.DatabaseError("moeda divergente no ledger")
            if self._moeda == "TOKEN":
                schema = con.execute(
                    "SELECT sql FROM sqlite_master WHERE name='budget_session'"
                ).fetchone()
                if (
                    schema is None
                    or type(schema[0]) is not str
                    or "CHECK (moeda='TOKEN')" not in schema[0]
                ):
                    raise sqlite3.DatabaseError("schema de moeda divergente")
            if "moeda_real" not in {linha[1] for linha in con.execute("PRAGMA table_info(budget_reservation)")}:
                con.execute("ALTER TABLE budget_reservation ADD COLUMN moeda_real TEXT")
            con.commit()
            return con
        except sqlite3.Error:
            con.rollback()
            con.close()
            raise


def executar_tentativa_custeada(
    repositorio: RepositorioOrcamento,
    sessao: SessaoOrcamento,
    identidade: object,
    cliente: object,
) -> ResultadoExecucaoTentativa:
    """Executa uma única tentativa já identificada; retry/fallback pertencem ao caller."""
    if not isinstance(repositorio, RepositorioOrcamento):
        raise ErroOrcamento("repositorio invalido")
    identidade = _validar_identidade(identidade)
    try:
        cotar = object.__getattribute__(cliente, "cotar_tentativa")
        tentar = object.__getattribute__(cliente, "tentar_uma_vez")
    except Exception:
        repositorio.bloquear(sessao, identidade, "sem_adapter")
        return TentativaBloqueadaPreEfeito("sem_adapter")
    if not callable(cotar) or not callable(tentar):
        repositorio.bloquear(sessao, identidade, "sem_adapter")
        return TentativaBloqueadaPreEfeito("sem_adapter")
    try:
        cotacao = cotar()
    except Exception:
        repositorio.bloquear(sessao, identidade, "sem_cotacao")
        return TentativaBloqueadaPreEfeito("sem_cotacao")
    if not _cotacao_tentativa_valida(cotacao, repositorio.moeda):
        repositorio.bloquear(sessao, identidade, "sem_cotacao")
        return TentativaBloqueadaPreEfeito("sem_cotacao")
    reserva = ReservaOrcamento(
        identidade.reservation_id, identidade.call_id, identidade.route_id,
        identidade.attempt, cotacao.maximo, cotacao.pricing_version,
    )
    decisao = repositorio.reservar_exclusiva(sessao, reserva)
    if decisao.status != "NOVA":
        if decisao.status == "BLOQUEADA" and decisao.motivo == "teto excedido":
            return TentativaBloqueadaPreEfeito("teto")
        motivo = {
            "BLOQUEADA": "sessao de orcamento inativa",
            "REPLAY_AMBIGUO": "reserva anterior pode ter produzido efeito",
            "REPLAY_FINALIZADO": "efeito anterior sem resposta recuperavel",
        }[decisao.status]
        return TentativaTerminal(motivo, decisao.status)
    try:
        resultado = tentar()
    except Exception:
        estado = repositorio.reconciliar(sessao, reserva, None)
        return _tentativa_terminal("efeito externo com custo desconhecido", estado.status)
    if not _resultado_tentativa_valido(resultado):
        estado = repositorio.reconciliar(sessao, reserva, None)
        return _tentativa_terminal("resultado sem custo confiavel", estado.status)
    estado = repositorio.reconciliar(sessao, reserva, resultado.custo_real, resultado.moeda)
    if estado.status == "RECONCILED":
        return TentativaReconciliada(resultado)
    return _tentativa_terminal("resultado violou contrato de custo", estado.status)


def _tentativa_terminal(motivo: str, status: StatusReserva) -> TentativaTerminal:
    if status not in ("CONTRACT_VIOLATED", "UNKNOWN_COST"):
        raise ErroOrcamento("estado terminal de tentativa invalido")
    return TentativaTerminal(motivo, status)


def publicar_um_pendente(
    repositorio: RepositorioOrcamento,
    run_id: str,
    owner: str,
    agora: int,
    lease_s: int,
    publicador: PublicadorEventoOrcamento,
) -> bool:
    """Publica no máximo um evento; falha antes do ACK permite redelivery pelo event_id."""
    if not isinstance(repositorio, RepositorioOrcamento):
        raise ErroOrcamento("repositorio invalido")
    if not callable(publicador):
        raise ErroOrcamento("publicador invalido")
    evento = repositorio.reivindicar_pendente(run_id, owner, agora, lease_s)
    if evento is None:
        return False
    publicador(evento.event_id, evento.tipo, deepcopy(evento.payload))
    repositorio.confirmar_pendente(run_id, evento.event_id, owner)
    return True


def publicar_pendentes_por_moeda(
    repositorios: Mapping[Moeda, RepositorioOrcamento],
    run_id: str,
    owner: str,
    agora: int,
    lease_s: int,
    publicador: PublicadorEventoOrcamento,
) -> bool:
    """Drena todos os ledgers existentes em ordem fixa, sem criar os ausentes."""
    if set(repositorios) - set(ORDEM_DRENO_MOEDAS):
        raise ErroOrcamento("mapa de moedas invalido")
    sem_pendencias = True
    for moeda in ORDEM_DRENO_MOEDAS:
        repositorio = repositorios.get(moeda)
        if repositorio is None:
            continue
        if (
            not isinstance(repositorio, RepositorioOrcamento)
            or repositorio.moeda != moeda
        ):
            raise ErroOrcamento("repositorio de moeda divergente")
        if not repositorio.possui_ledger(run_id):
            continue
        while publicar_um_pendente(
            repositorio, run_id, owner, agora, lease_s, publicador,
        ):
            pass
        sem_pendencias = not repositorio.listar_pendentes(run_id) and sem_pendencias
    return sem_pendencias


def _resultado_tentativa_valido(valor: object) -> bool:
    if type(valor) is not ResultadoTentativa:
        return False
    try:
        _decimal(valor.custo_real)
    except ErroOrcamento:
        return False
    return (
        (valor.texto is None or type(valor.texto) is str)
        and type(valor.moeda) is str
        and valor.moeda in _ARQUIVO_POR_MOEDA
        and _identificador(valor.usage_ref)
    )


def _cotacao_tentativa_valida(valor: object, moeda: Moeda) -> bool:
    if type(valor) is not CotacaoTentativa:
        return False
    try:
        _decimal(valor.maximo, positivo=True)
    except ErroOrcamento:
        return False
    return valor.moeda == moeda and _identificador(valor.pricing_version)
