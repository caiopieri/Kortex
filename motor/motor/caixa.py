"""Caixa do fundador — gate humano durável via nota no vault (formato do v0.4).

Quando o grafo chega a `interrupt()` (cobertura reprovada), o motor não pode
decidir sozinho: escala ao fundador escrevendo uma nota Markdown na caixa e
faz *poll* da linha `decisao:` do frontmatter até o humano responder.

Durabilidade tem duas camadas independentes:
- o **checkpointer** (SQLite) segura o estado do grafo no ponto do interrupt, de
  modo que `rodar_com_caixa` pode ser religado após um crash e retomar;
- a **nota** é a interface humana e também é durável: uma nota `PENDENTE` que
  sobrevive ao crash é *reaproveitada* (evento `decisao.retomada`), não recriada.

Espelha `caixa_fundador` do motor v0.4 (vault, `5. Motor v0/motor.py`): mesmo
frontmatter (`estado/portao/criada/decisao`), mesmo corpo (Pergunta/Contexto/
Opções), mesmos eventos (`decisao.pendente/.retomada/.fundador/.timeout`) e o
mesmo renomear para `decidida <timestamp> — <portao>.md` ao concluir.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, cast

from langgraph.types import Command

_RE_CAMPO_NOTA = re.compile(r"^(estado|portao|criada|decisao):[ \t]*(.*)$")
_RE_OPCOES = re.compile(r"^\*\*Opções:\*\*[ \t]*(.*)$", re.M)
_CAMPOS_NOTA = {"estado", "portao", "criada", "decisao"}
_RE_ID_LEDGER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SCHEMA_LEDGER = 1
_SQLITE_INT_MAX = 2**63 - 1
_LEASE_APPLIED = ":APPLIED:"
# Lease do consumer da CLI. É constante, e não literal repetido, porque `claim` e
# `consumir` PRECISAM concordar: quem reivindica com 30s mas consome sem declarar
# o lease nunca sobe a thread de renovação — e aí uma retomada mais longa que a
# janela aplica o efeito e falha no ACK, deixando a linha da outbox reelegível.
_LEASE_CLI_S = 30


class LedgerCaixa:
    """Ledger/outbox atômicos para workers no mesmo host e relógio de parede."""
    def __init__(self, db_path: str | Path, *, clock: Callable[[], float] = time.time):
        if sqlite3.sqlite_version_info < (3, 35):
            raise RuntimeError("LedgerCaixa exige SQLite >= 3.35 (UPDATE RETURNING)")
        if str(db_path) == ":memory:":
            raise ValueError("LedgerCaixa exige arquivo persistente")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None, timeout=5)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        journal = str(self._conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        self._conn.execute("PRAGMA synchronous = FULL")
        if (self._conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1
                or self._conn.execute("PRAGMA synchronous").fetchone()[0] != 2
                or journal != "wal"):
            self._conn.close()
            raise RuntimeError("SQLite não oferece durabilidade exigida pelo LedgerCaixa")
        try:
            tem_meta = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'caixa_meta'"
            ).fetchone() is not None
            row_versao = self._conn.execute(
                "SELECT schema_version FROM caixa_meta WHERE singleton = 1"
            ).fetchone() if tem_meta else None
            versao = int(row_versao[0]) if row_versao is not None else 0
        except (sqlite3.DatabaseError, TypeError, ValueError) as ex:
            self._conn.close()
            raise RuntimeError("metadados do LedgerCaixa inválidos") from ex
        if tem_meta and versao != _SCHEMA_LEDGER:
            self._conn.close()
            raise RuntimeError(f"schema do LedgerCaixa incompatível: {versao}")
        if versao == 0 and self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('caixa_ledger', 'caixa_outbox') LIMIT 1"
        ).fetchone() is not None:
            self._conn.close()
            raise RuntimeError("schema legado do LedgerCaixa requer migração explícita")
        self._conn.row_factory = sqlite3.Row
        with self._transacao():
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS caixa_meta (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_version INTEGER NOT NULL
                )
            """)
            self._conn.execute(
                "INSERT OR IGNORE INTO caixa_meta(singleton, schema_version) VALUES (1, ?)",
                (_SCHEMA_LEDGER,),
            )
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS caixa_ledger (
                    decisao_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                    portao TEXT NOT NULL, decisao TEXT NOT NULL,
                    registrada_em REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS caixa_outbox (
                    outbox_id INTEGER PRIMARY KEY,
                    decisao_id TEXT NOT NULL UNIQUE
                        REFERENCES caixa_ledger(decisao_id),
                    payload TEXT NOT NULL, criada_em REAL NOT NULL,
                    lease_owner TEXT, lease_ate REAL,
                    lease_version INTEGER NOT NULL DEFAULT 0
                        CHECK (lease_version BETWEEN 0 AND 9223372036854775807),
                    CHECK ((lease_owner IS NULL) = (lease_ate IS NULL))
                )
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS caixa_outbox_claim "
                               "ON caixa_outbox(lease_ate, outbox_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS caixa_ledger_job "
                               "ON caixa_ledger(job_id, decisao_id)")

    @contextmanager
    def _transacao(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._conn.execute("COMMIT")
        except BaseException:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise

    @staticmethod
    def _texto(nome: str, valor: str, limite: int, *, identificador: bool = False) -> str:
        if (
            not isinstance(valor, str)
            or not valor
            or valor != valor.strip()
            or not valor.isprintable()
            or len(valor) > limite
            or (identificador and _RE_ID_LEDGER.fullmatch(valor) is None)
        ):
            raise ValueError(f"{nome} inválido")
        return valor

    def _agora(self) -> float:
        bruto = self._clock()
        try:
            agora = float(bruto)
        except (TypeError, ValueError, OverflowError) as ex:
            raise ValueError("clock inválido") from ex
        if not math.isfinite(agora):
            raise ValueError("clock inválido")
        return agora

    @staticmethod
    def _duracao(lease_s: float) -> float:
        if isinstance(lease_s, bool) or not isinstance(lease_s, (int, float)):
            raise ValueError("lease_s inválido")
        try:
            duracao = float(lease_s)
        except (TypeError, ValueError, OverflowError) as ex:
            raise ValueError("lease_s inválido") from ex
        if not math.isfinite(duracao) or duracao <= 0:
            raise ValueError("lease_s inválido")
        return duracao

    def _janela_lease(self, lease_s: float) -> tuple[float, float]:
        agora = self._agora()
        lease_ate = agora + self._duracao(lease_s)
        if not math.isfinite(lease_ate) or lease_ate <= agora:
            raise ValueError("prazo de lease inválido")
        return agora, lease_ate

    def registrar_decisao(self, *, decisao_id: str, job_id: str,
                          portao: str, decisao: str) -> int:
        """Persiste decisão e mensagem juntas; reentrada idêntica é estável."""
        decisao_id = self._texto("decisao_id", decisao_id, 128, identificador=True)
        job_id = self._texto("job_id", job_id, 128, identificador=True)
        portao = self._texto("portao", portao, 128)
        decisao = self._texto("decisao", decisao, 1000)
        dados = {"decisao": decisao, "decisao_id": decisao_id,
                 "job_id": job_id, "portao": portao}
        payload = json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._transacao():
            agora = self._agora()
            inserida = self._conn.execute("""
                INSERT INTO caixa_ledger
                    (decisao_id, job_id, portao, decisao, registrada_em)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(decisao_id) DO NOTHING
                RETURNING decisao_id
            """, (decisao_id, job_id, portao, decisao, agora)).fetchone()
            if inserida is not None:
                row = self._conn.execute("""
                    INSERT INTO caixa_outbox(decisao_id, payload, criada_em)
                    VALUES (?, ?, ?) RETURNING outbox_id
                """, (decisao_id, payload, agora)).fetchone()
                if row is None:
                    raise RuntimeError("outbox não foi persistida")
                return int(row["outbox_id"])

            existente = self._conn.execute("""
                SELECT l.job_id, l.portao, l.decisao, o.outbox_id, o.payload
                FROM caixa_ledger AS l
                LEFT JOIN caixa_outbox AS o USING (decisao_id)
                WHERE l.decisao_id = ?
            """, (decisao_id,)).fetchone()
            esperado = (job_id, portao, decisao, payload)
            if existente is None or tuple(existente[chave] for chave in
                    ("job_id", "portao", "decisao", "payload")) != esperado:
                raise ValueError("decisao_id conflita com registro existente")
            return int(existente["outbox_id"])

    @staticmethod
    def _claim(row: sqlite3.Row) -> dict[str, Any]:
        claim = dict(row)
        claim["payload"] = json.loads(claim["payload"])
        return claim

    def claim(self, owner_id: str, *, lease_s: float,
              decisao_id: str | None = None,
              job_id: str | None = None) -> dict[str, Any] | None:
        """Concede atomicamente no máximo um lease elegível ao owner."""
        owner_id = self._texto("owner_id", owner_id, 128, identificador=True)
        filtros = ""
        parametros_filtro: list[str] = []
        if decisao_id is not None:
            decisao_id = self._texto(
                "decisao_id", decisao_id, 128, identificador=True
            )
            filtros += " AND o.decisao_id = ?"
            parametros_filtro.append(decisao_id)
        if job_id is not None:
            job_id = self._texto("job_id", job_id, 128, identificador=True)
            filtros += " AND l.job_id = ?"
            parametros_filtro.append(job_id)
        with self._transacao():
            agora, lease_ate = self._janela_lease(lease_s)
            row = self._conn.execute(f"""
                UPDATE caixa_outbox
                SET lease_owner = ?, lease_ate = ?, lease_version = lease_version + 1
                WHERE outbox_id = (
                    SELECT o.outbox_id FROM caixa_outbox AS o
                    JOIN caixa_ledger AS l USING (decisao_id)
                    WHERE (o.lease_ate IS NULL OR o.lease_ate <= ?)
                      AND (o.lease_owner IS NULL OR o.lease_owner <> ?)
                      AND o.lease_version < 9223372036854775807
                      AND NOT EXISTS (
                          SELECT 1 FROM caixa_outbox AS ativa
                          JOIN caixa_ledger AS ledger_ativa USING (decisao_id)
                          WHERE ledger_ativa.job_id = l.job_id
                            AND ativa.lease_owner IS NOT NULL
                            AND ativa.lease_owner <> ?
                            AND ativa.lease_ate > ?
                      )
                      {filtros}
                    ORDER BY o.outbox_id LIMIT 1
                )
                AND (lease_ate IS NULL OR lease_ate <= ?)
                AND (lease_owner IS NULL OR lease_owner <> ?)
                AND lease_version < 9223372036854775807
                RETURNING outbox_id, decisao_id, payload,
                          lease_owner, lease_ate, lease_version
            """, (
                owner_id, lease_ate, agora, _LEASE_APPLIED,
                _LEASE_APPLIED, agora, *parametros_filtro,
                agora, _LEASE_APPLIED,
            )).fetchone()
            return self._claim(row) if row is not None else None

    def renovar_claim(self, outbox_id: int, owner_id: str, *,
                      lease_version: int, lease_s: float) -> dict[str, Any]:
        """Renova somente o lease vivo identificado por owner e versão (CAS)."""
        if any(isinstance(v, bool) or not isinstance(v, int)
               or v <= 0 or v > _SQLITE_INT_MAX
               for v in (outbox_id, lease_version)):
            raise ValueError("identificador de lease inválido")
        owner_id = self._texto("owner_id", owner_id, 128, identificador=True)
        with self._transacao():
            agora, lease_ate = self._janela_lease(lease_s)
            row = self._conn.execute("""
                UPDATE caixa_outbox
                SET lease_ate = MAX(lease_ate, ?),
                    lease_version = lease_version + 1
                WHERE outbox_id = ? AND lease_owner = ?
                  AND lease_version = ? AND lease_ate > ?
                  AND lease_version < 9223372036854775807
                RETURNING outbox_id, decisao_id, payload,
                          lease_owner, lease_ate, lease_version
            """, (lease_ate, outbox_id, owner_id, lease_version, agora)).fetchone()
            if row is None:
                raise ValueError("transição de lease inválida")
            return self._claim(row)

    def ack(self, outbox_id: int, owner_id: str, *, lease_version: int) -> str:
        """Confirma um claim vivo por CAS e deixa tombstone `APPLIED`."""
        if any(isinstance(v, bool) or not isinstance(v, int)
               or v <= 0 or v > _SQLITE_INT_MAX
               for v in (outbox_id, lease_version)):
            raise ValueError("identificador de lease inválido")
        owner_id = self._texto("owner_id", owner_id, 128, identificador=True)
        with self._transacao():
            agora = self._agora()
            row = self._conn.execute("""
                UPDATE caixa_outbox
                SET lease_owner = ?, lease_ate = ?
                WHERE outbox_id = ? AND lease_owner = ?
                  AND lease_version = ? AND lease_ate > ?
                RETURNING decisao_id
            """, (
                _LEASE_APPLIED, agora, outbox_id, owner_id, lease_version, agora,
            )).fetchone()
            if row is None:
                raise ValueError("transição de lease inválida")
            return str(row["decisao_id"])

    def buscar_decisao(self, decisao_id: str) -> dict[str, Any] | None:
        """Consulta payload e estado durável sem tornar a mensagem elegível."""
        decisao_id = self._texto("decisao_id", decisao_id, 128, identificador=True)
        row = self._conn.execute("""
            SELECT outbox_id, decisao_id, payload, lease_owner, lease_ate, lease_version
            FROM caixa_outbox WHERE decisao_id = ?
        """, (decisao_id,)).fetchone()
        if row is None:
            return None
        registro = self._claim(row)
        if registro["lease_owner"] == _LEASE_APPLIED:
            registro["estado"] = "APPLIED"
        elif registro["lease_owner"] is None:
            registro["estado"] = "PENDING"
        elif registro["lease_ate"] <= self._agora():
            registro["estado"] = "EXPIRED"
        else:
            registro["estado"] = "CLAIMED"
        return registro

    def tem_historico(self, *, job_id: str, portao: str) -> bool:
        job_id = self._texto("job_id", job_id, 128, identificador=True)
        portao = self._texto("portao", portao, 128)
        return self._conn.execute(
            "SELECT 1 FROM caixa_ledger WHERE job_id = ? AND portao = ? LIMIT 1",
            (job_id, portao),
        ).fetchone() is not None

    def consumir(self, claim: dict[str, Any],
                 aplicar: Callable[[dict[str, Any]], Any], *,
                 fault: Callable[[str], None] | None = None,
                 lease_s: float | None = None) -> Any:
        """Entrega at-least-once; `aplicar` deve deduplicar por `decisao_id`."""
        claim = self._validar_claim_para_entrega(claim)
        outbox_id = claim.get("outbox_id")
        owner_id = claim.get("lease_owner")
        lease_version = claim.get("lease_version")
        payload = claim.get("payload")
        if (
            not isinstance(payload, dict)
            or not isinstance(owner_id, str)
            or not isinstance(outbox_id, int)
            or not isinstance(lease_version, int)
        ):
            raise ValueError("claim inválido")
        if fault is not None:
            fault("apos_claim")
        parar_renovacao = threading.Event()
        claim_atual = claim
        lock_claim = threading.Lock()
        erro_renovacao: list[BaseException] = []
        renovador: threading.Thread | None = None
        if lease_s is not None:
            duracao = self._duracao(lease_s)

            def renovar() -> None:
                ledger = LedgerCaixa(self.db_path, clock=self._clock)
                try:
                    while not parar_renovacao.wait(duracao / 3):
                        with lock_claim:
                            atual = dict(claim_atual)
                        renovado = ledger.renovar_claim(
                            atual["outbox_id"], atual["lease_owner"],
                            lease_version=atual["lease_version"], lease_s=duracao,
                        )
                        with lock_claim:
                            claim_atual.update(renovado)
                except BaseException as ex:
                    erro_renovacao.append(ex)
                    parar_renovacao.set()
                finally:
                    ledger.fechar()

            renovador = threading.Thread(
                target=renovar,
                name=f"caixa-lease-{outbox_id}",
                daemon=True,
            )
            renovador.start()
        try:
            resultado = aplicar(payload)
        finally:
            parar_renovacao.set()
            if renovador is not None:
                renovador.join()
        if erro_renovacao:
            raise RuntimeError("falha ao renovar lease da decisão") from erro_renovacao[0]
        if fault is not None:
            fault("apos_aplicar")
        with lock_claim:
            lease_version = claim_atual["lease_version"]
        self.ack(outbox_id, owner_id, lease_version=lease_version)
        if fault is not None:
            fault("apos_ack")
        return resultado

    def _validar_claim_para_entrega(self, claim: dict[str, Any]) -> dict[str, Any]:
        outbox_id = claim.get("outbox_id")
        lease_version = claim.get("lease_version")
        owner_id = claim.get("lease_owner")
        if (
            isinstance(outbox_id, bool)
            or not isinstance(outbox_id, int)
            or isinstance(lease_version, bool)
            or not isinstance(lease_version, int)
            or not isinstance(owner_id, str)
        ):
            raise ValueError("claim inválido")
        with self._transacao():
            agora = self._agora()
            row = self._conn.execute("""
                SELECT outbox_id, decisao_id, payload,
                       lease_owner, lease_ate, lease_version
                FROM caixa_outbox
                WHERE outbox_id = ? AND lease_owner = ?
                  AND lease_version = ? AND lease_ate > ?
            """, (outbox_id, owner_id, lease_version, agora)).fetchone()
        if row is None:
            raise ValueError("claim inválido ou expirado")
        persistido = self._claim(row)
        if any(
            claim.get(chave) != persistido[chave]
            for chave in (
                "outbox_id", "decisao_id", "payload", "lease_owner",
                "lease_ate", "lease_version",
            )
        ):
            raise ValueError("claim diverge da outbox persistida")
        return persistido

    def fechar(self) -> None:
        self._conn.close()


class CaixaFundador:
    """Gate humano durável por nota no diretório `dir_caixa`.

    A decisão é dada editando a linha `decisao:` do frontmatter da nota e
    salvando. `poll_s` e `timeout_s` são configuráveis: o vault no iCloud tem
    latência de sync, então em produção convém `poll_s >= 5`; nos testes usamos
    valores pequenos com uma decisão escrita previamente (ou por thread).
    """

    def __init__(self, dir_caixa: str | Path, log: Any,
                 timeout_s: int = 600, poll_s: int = 5,
                 job_id: str | None = None):
        self.dir_caixa = Path(dir_caixa)
        self.log = log
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self.job_id = self._validar_componente(job_id) if job_id is not None else None

    def para_job(self, job_id: str) -> "CaixaFundador":
        """Devolve uma Caixa vinculada a este job.

        O vault de `--caixa <dir>` é compartilhado por construção. Sem vínculo,
        a nota se chamaria só pelo portão e a decisão arquivada de um job seria
        encontrada por outro — o humano aprova o projeto A e o projeto B segue
        sozinho. O vínculo põe o job no nome do arquivo e no glob.
        """
        return CaixaFundador(
            self.dir_caixa, self.log,
            timeout_s=self.timeout_s, poll_s=self.poll_s, job_id=job_id,
        )

    @staticmethod
    def _validar_componente(valor: str) -> str:
        if (
            not isinstance(valor, str)
            or not valor
            or valor != valor.strip()
            or not valor.isprintable()
            or valor in {".", ".."}
            or any(separador in valor for separador in ("/", "\\", "\0"))
        ):
            raise ValueError("portao inválido")
        return valor

    def _escopo(self, portao: str) -> str:
        """Sufixo que identifica nota e arquivo. Inclui o job quando vinculado."""
        portao = self._validar_componente(portao)
        return f"{self.job_id} — {portao}" if self.job_id is not None else portao

    def _nota_path(self, portao: str) -> Path:
        return self.dir_caixa / f"PENDENTE — {self._escopo(portao)}.md"

    @staticmethod
    def _ler_nota(path: Path, portao: str) -> tuple[str, set[str]]:
        if path.is_symlink() or not path.is_file():
            raise ValueError("nota inválida")
        try:
            texto = path.read_text(encoding="utf-8")
            frontmatter, corpo = texto.removeprefix("---\n").split("\n---\n", 1)
        except (OSError, UnicodeError, ValueError) as ex:
            raise ValueError("nota inválida") from ex
        if not texto.startswith("---\n"):
            raise ValueError("nota inválida")

        campos: dict[str, str] = {}
        for linha in frontmatter.splitlines():
            match = _RE_CAMPO_NOTA.fullmatch(linha)
            if match is None or match.group(1) in campos:
                raise ValueError("nota inválida")
            campos[match.group(1)] = match.group(2).strip()
        opcoes = _RE_OPCOES.findall(corpo)
        if (
            set(campos) != _CAMPOS_NOTA
            or campos["estado"] != "pendente"
            or campos["portao"] != portao
            or not campos["criada"]
            or len(opcoes) != 1
            or "**Pergunta:**" not in corpo
            or "**Contexto:**" not in corpo
        ):
            raise ValueError("nota inválida")
        valores = {
            opcao.strip()
            for opcao in re.split(r"[|·]", opcoes[0])
            if opcao.strip()
        }
        return campos["decisao"], valores

    def escrever_nota(self, portao: str, pergunta: str,
                      contexto: str, opcoes: str) -> Path:
        """Cria a nota `PENDENTE — <portao>.md` se não existir.

        Se já existir (motor religado após crash com gate pendente), NÃO
        sobrescreve — emite `decisao.retomada` e reaproveita a nota intacta,
        preservando o que o humano já tenha digitado.
        """
        self.dir_caixa.mkdir(parents=True, exist_ok=True)
        path = self._nota_path(portao)
        if path.is_symlink():
            raise ValueError("nota inválida")
        if path.exists():
            self._ler_nota(path, portao)
            self.log.evento("decisao.retomada", portao=portao, nota=path.name)
            return path
        path.write_text(
            "---\n"
            "estado: pendente\n"
            f"portao: {portao}\n"
            f"criada: {time.strftime('%Y-%m-%d %H:%M')}\n"
            "decisao: \n"
            "---\n"
            "# Decisão aguardando o fundador\n"
            "\n"
            f"**Pergunta:** {pergunta}\n"
            "\n"
            f"**Contexto:** {contexto}\n"
            "\n"
            f"**Opções:** {opcoes}\n"
            "\n"
            f"> Escreva sua decisão na linha `decisao:` do frontmatter acima e "
            f"salve. O motor verifica a cada {self.poll_s}s (prazo: {self.timeout_s}s).\n",
            encoding="utf-8",
        )
        self.log.evento("decisao.pendente", portao=portao, nota=path.name)
        return path

    def ler_decisao(self, portao: str) -> Optional[str]:
        """Lê a decisão da nota sem bloquear. None se ainda não decidida."""
        path = self._nota_path(portao)
        if path.is_symlink():
            raise ValueError("nota inválida")
        if not path.exists():
            return None
        decisao, opcoes = self._ler_nota(path, portao)
        if decisao and decisao in opcoes:
            return decisao
        return None

    def aguardar_decisao(self, portao: str, *,
                         antes_de_arquivar: Callable[[str], None] | None = None) -> str:
        """Faz poll da nota até decidir; ao decidir, arquiva e retorna a decisão.

        Timeout → evento `decisao.timeout` + RuntimeError (a nota é mantida na
        caixa para o humano ainda poder decidir/depurar).
        """
        path = self._nota_path(portao)
        fim = time.monotonic() + self.timeout_s
        while True:
            decisao = self.ler_decisao(portao)
            if decisao is not None:
                self.log.evento("decisao.fundador", portao=portao, decisao=decisao)
                if antes_de_arquivar is not None:
                    antes_de_arquivar(decisao)
                self._arquivar(path, portao)
                return decisao
            restante = fim - time.monotonic()
            if restante <= 0:
                self.log.evento("decisao.timeout", portao=portao, prazo_s=self.timeout_s)
                raise RuntimeError(
                    f"fundador não decidiu '{portao}' no prazo — nota mantida na caixa"
                )
            time.sleep(min(self.poll_s, restante))

    def _arquivar(self, path: Path, portao: str) -> None:
        if not path.exists():
            if self._decisao_arquivada(portao) is not None:
                return
            raise FileNotFoundError(path)
        escopo = self._escopo(portao)
        instante = time.strftime("%Y%m%d-%H%M%S")
        novo = self.dir_caixa / f"decidida {instante} — {escopo}.md"
        sequencia = 2
        while novo.exists():
            novo = self.dir_caixa / f"decidida {instante}-{sequencia} — {escopo}.md"
            sequencia += 1
        try:
            path.replace(novo)
        except FileNotFoundError:
            if self._decisao_arquivada(portao) is None:
                raise

    def _decisao_arquivada(self, portao: str) -> str | None:
        escopo = self._escopo(portao)  # valida antes de interpolar no glob
        for path in sorted(self.dir_caixa.glob(f"decidida * — {escopo}.md"), reverse=True):
            decisao, opcoes = self._ler_nota(path, portao)
            if decisao and decisao in opcoes:
                return decisao
        return None


def _achatar(valor: Any) -> str:
    """Colapsa o valor em uma única linha.

    Achatar não é estética: o plano vem de um modelo, e uma quebra de linha no
    texto dele bastaria para forjar um segundo `**Opções:**` no corpo e tornar
    a própria nota ilegível para `_ler_nota`.
    """
    return " ".join(str(valor).split()) if valor is not None else "?"


def _contexto_do_pedido(pedido: dict[str, Any]) -> str:
    """O que o humano precisa ver para decidir: o plano, quando houver um."""
    plano = pedido.get("plano")
    if isinstance(plano, list) and plano:
        linhas = [f"plano com {len(plano)} subagente(s):", ""]
        linhas += [
            f"{i}. `{_achatar(no.get('id'))}` — {_achatar(no.get('papel'))}"
            f" · tier {_achatar(no.get('tier'))} · modelo {_achatar(no.get('modelo'))}"
            f"\n   {_achatar(no.get('objetivo'))}"
            for i, no in enumerate(plano, 1)
            if isinstance(no, dict)
        ]
        return "\n".join(linhas)
    lacunas = pedido.get("lacunas") or []
    if lacunas:
        return "; ".join(_achatar(lac) for lac in lacunas)
    return "(sem lacunas detalhadas)"


def rodar_com_caixa(grafo, entrada, config, caixa: CaixaFundador, log: Any, *,
                    ledger: LedgerCaixa | None = None,
                    fault: Callable[[str], None] | None = None) -> dict:
    """Invoca o grafo; em cada interrupt escala ao fundador via nota e retoma.

    `entrada` pode ser a entrada inicial (dict) ou já um `Command` (resume).
    Enquanto o resultado contiver `__interrupt__`, escreve/reaproveita a nota
    com o payload do interrupt (portao/pergunta/lacunas/opcoes), aguarda a
    decisão humana e retoma pelo mapa `{decision_id: decisao}`. Retorna o estado
    final (sem `__interrupt__`).
    """
    configuravel = config.get("configurable") if isinstance(config, dict) else None
    job_id = configuravel.get("thread_id") if isinstance(configuravel, dict) else None
    if not isinstance(job_id, str) or _RE_ID_LEDGER.fullmatch(job_id) is None:
        raise ValueError("config.configurable.thread_id inválido")
    # Vincula a Caixa a ESTE job antes de tocar em qualquer nota. O vault é
    # compartilhado; sem o vínculo, a decisão que o humano deu para outro job
    # é encontrada pelo glob e consumida aqui, sem nenhuma interação.
    caixa = caixa.para_job(job_id)
    proprio_ledger = ledger is None
    ledger = ledger or LedgerCaixa(caixa.dir_caixa / ".ledger.sqlite")
    owner_id = f"runner-{id(caixa):x}"

    def aplicar(payload: dict[str, Any]) -> dict:
        return cast(
            dict[Any, Any],
            grafo.invoke(
                Command(resume={payload["decisao_id"]: payload["decisao"]}), config
            ),
        )

    try:
        resultado = None
        while claim := ledger.claim(owner_id, lease_s=_LEASE_CLI_S, job_id=job_id):
            pendente = caixa._nota_path(claim["payload"]["portao"])
            if pendente.exists():
                caixa._arquivar(pendente, claim["payload"]["portao"])
            resultado = ledger.consumir(
                claim, aplicar, fault=fault, lease_s=_LEASE_CLI_S
            )
        if resultado is None:
            snapshot = grafo.get_state(config)
            if getattr(snapshot, "created_at", None) is None:
                resultado = grafo.invoke(entrada, config)
            elif getattr(snapshot, "next", ()):
                resultado = dict(snapshot.values)
                resultado["__interrupt__"] = list(snapshot.interrupts)
            else:
                resultado = dict(snapshot.values)

        while "__interrupt__" in resultado:
            interrupcao = resultado["__interrupt__"][0]
            pedido = interrupcao.value
            decisao_id = interrupcao.id
            portao = pedido.get("portao", "decisao")
            registro = ledger.buscar_decisao(decisao_id)
            if registro is None:
                decisao = caixa.ler_decisao(portao)
                if decisao is not None:
                    caixa.escrever_nota(
                        portao=portao,
                        pergunta=pedido.get("pergunta", "Decisão necessária."),
                        contexto=_contexto_do_pedido(pedido),
                        opcoes=pedido.get("opcoes", ""),
                    )
                if (
                    decisao is None
                    and not caixa._nota_path(portao).exists()
                    and not ledger.tem_historico(job_id=job_id, portao=portao)
                ):
                    decisao = caixa._decisao_arquivada(portao)
                if decisao is None:
                    caixa.escrever_nota(
                        portao=portao,
                        pergunta=pedido.get("pergunta", "Decisão necessária."),
                        contexto=_contexto_do_pedido(pedido),
                        opcoes=pedido.get("opcoes", ""),
                    )

                    def registrar(valor: str) -> None:
                        ledger.registrar_decisao(
                            decisao_id=decisao_id, job_id=job_id,
                            portao=portao, decisao=valor,
                        )
                        if fault is not None:
                            fault("apos_registrar")

                    caixa.aguardar_decisao(
                        portao, antes_de_arquivar=registrar
                    )
                else:
                    ledger.registrar_decisao(
                        decisao_id=decisao_id, job_id=job_id,
                        portao=portao, decisao=decisao,
                    )
                    if fault is not None:
                        fault("apos_registrar")
                    caixa._arquivar(caixa._nota_path(portao), portao)
                if fault is not None:
                    fault("apos_arquivar")

            claim = ledger.claim(
                owner_id, lease_s=_LEASE_CLI_S, decisao_id=decisao_id
            )
            if claim is not None:
                resultado = ledger.consumir(
                    claim, aplicar, fault=fault, lease_s=_LEASE_CLI_S
                )
            else:
                atual = ledger.buscar_decisao(decisao_id)
                if atual is not None and atual["estado"] == "APPLIED":
                    resultado = aplicar(atual["payload"])
                else:
                    raise RuntimeError("decisão já está sendo aplicada por outro consumer")
        return cast(dict[Any, Any], resultado)
    finally:
        if proprio_ledger:
            ledger.fechar()
