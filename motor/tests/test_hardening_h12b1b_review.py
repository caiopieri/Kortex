from decimal import Decimal
import os
import sqlite3
import concurrent.futures
import pytest

from motor.orcamento import RepositorioOrcamento, ReservaOrcamento, ErroOrcamento
from motor.eventos_schema import valido


def test_migracao_h12b1a_para_h12b1b(tmp_path):
    """
    (1) Falha de migração real de banco H12b1a sem a coluna moeda_real.
    Esperado: O motor deve abrir o banco legado, aplicar a migração (adicionando a coluna) e
    executar reservas e reconciliações usando comandos SQL com colunas explícitas.
    Proteção: a migração adiciona a coluna e todos os INSERTs nomeiam as colunas.
    """
    # Cria o banco com o schema legado da H12b1a (sem a coluna moeda_real)
    caminho_dir = tmp_path / "run1"
    caminho_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    caminho_db = caminho_dir / "orcamento.sqlite3"

    con = sqlite3.connect(caminho_db)
    con.executescript("""
        CREATE TABLE budget_session (
          run_id TEXT NOT NULL, thread_id TEXT NOT NULL, teto TEXT NOT NULL, moeda TEXT NOT NULL,
          gasto TEXT NOT NULL, reservado TEXT NOT NULL, status TEXT NOT NULL,
          PRIMARY KEY (run_id, thread_id), CHECK (moeda='BRL'), CHECK (status IN ('ACTIVE','INVALIDATED')),
          CHECK (typeof(teto)='text' AND typeof(gasto)='text' AND typeof(reservado)='text'));
        CREATE TABLE budget_reservation (
          reservation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, thread_id TEXT NOT NULL,
          call_id TEXT NOT NULL, route_id TEXT NOT NULL, attempt INTEGER NOT NULL, maximo TEXT NOT NULL,
          real TEXT, pricing_version TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT, reconciled_at TEXT,
          UNIQUE (run_id,thread_id,call_id,route_id,attempt),
          FOREIGN KEY (run_id,thread_id) REFERENCES budget_session(run_id,thread_id),
          CHECK (status IN ('RESERVED','RECONCILED','CONTRACT_VIOLATED','UNKNOWN_COST')),
          CHECK (typeof(maximo)='text' AND (real IS NULL OR typeof(real)='text')));
    """)
    # Usamos o valor do teto canônico '2' para evitar o erro de banco de dados corrompido
    con.execute(
        "INSERT INTO budget_session VALUES ('run1', 'thread1', '2', 'BRL', '0', '0', 'ACTIVE')"
    )
    con.commit()
    con.close()

    # Ajustamos as permissões exigidas pelo repositório (0o600 para arquivo, 0o700 para diretório)
    os.chmod(caminho_db, 0o600)

    # Instanciamos o RepositorioOrcamento H12b1b
    repo = RepositorioOrcamento(tmp_path)

    # A abertura da sessão e reserva de orçamento deve ocorrer sem erros de SQL
    sessao = repo.sessao("run1", "thread1", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call1", "rota", 1, Decimal("1.0"), "price-v1")

    repo.reservar(sessao, reserva)
    with sqlite3.connect(caminho_db) as banco:
        assert "moeda_real" in {
            linha[1] for linha in banco.execute("PRAGMA table_info(budget_reservation)")
        }
    assert repo.reconciliar(sessao, reserva, Decimal("0.5")).status == "RECONCILED"


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("call_id", "call-divergente"),
        ("route_id", "outra-rota"),
        ("attempt", 2),
        ("attempt", True),
        ("maximo", Decimal("2.0")),
        ("pricing_version", "price-v2"),
    ],
)
def test_reconciliar_rejeita_reserva_divergente(tmp_path, campo, valor):
    """
    (2) Falha ao validar metadados da ReservaOrcamento na reconciliação.
    Esperado: O método reconciliar deve validar se a ReservaOrcamento passada possui
    os mesmos metadados (call_id, route_id, attempt, maximo, pricing_version) salvos no banco.
    Proteção: todos os metadados persistidos são conferidos antes da transição.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run1", "thread1", Decimal("5.0"))
    reserva = ReservaOrcamento("r1", "call1", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao, reserva)

    dados = dict(
        call_id="call1",
        route_id="rota",
        attempt=1,
        maximo=Decimal("1.0"),
        pricing_version="price-v1",
    )
    dados[campo] = valor
    reserva_divergente = ReservaOrcamento("r1", **dados)

    with pytest.raises(ErroOrcamento, match="reserva divergente|reserva invalida"):
        repo.reconciliar(sessao, reserva_divergente, Decimal("0.5"))


def test_moeda_divergente_persiste_custo_e_moeda_para_evento(tmp_path):
    """
    (3) Falha ao persistir custo_real e moeda quando há moeda divergente.
    Esperado: Ao reconciliar com moeda divergente, o motor deve reter a reserva (conservar),
    mas salvar no banco a moeda recebida e o custo_real para permitir gerar o evento
    custo.contrato_violado em conformidade com o eventos_schema.
    Proteção: custo e moeda recebidos são preservados sem consumir a reserva em BRL.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run1", "thread1", Decimal("5.0"))
    reserva = ReservaOrcamento("r1", "call1", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao, reserva)

    # Reconciliação com moeda divergente
    repo.reconciliar(sessao, reserva, Decimal("1.5"), "USD")

    caminho = repo.caminho("run1")
    with sqlite3.connect(caminho) as con:
        linha = con.execute(
            "SELECT maximo,real,moeda_real,status FROM budget_reservation WHERE reservation_id='r1'"
        ).fetchone()
        real_db = linha[1]
        moeda_db = linha[2]

        # O eventos_schema.py exige que 'custo_real' não seja None e a moeda seja 'USD'
        # para montar o evento custo.contrato_violado com motivo 'moeda_divergente'.
        assert real_db is not None
        assert Decimal(real_db) == Decimal("1.5")
        assert moeda_db == "USD"

        # O evento simulado deve passar na validação de esquema
        evento_simulado = {
            "evento": "custo.contrato_violado",
            "t": 123456789.0,
            "seq": 1,
            "run_id": "run1",
            "thread_id": "thread1",
            "call_id": "call1",
            "rota": "rota",
            "tentativa": 1,
            "moeda": "BRL",
            "teto": "5.0",
            "gasto": "0",
            "reservado": "1.0",
            "reservation_id": "r1",
            "maximo": "1.0",
            "custo_real": real_db,
            "moeda_recebida": moeda_db,
            "pricing_version": "price-v1",
            "motivo": "moeda_divergente",
        }
        assert valido(evento_simulado) is True


def test_concorrencia_banco_unico_reserved_e_reservado_exato(tmp_path):
    """
    (4) Concorrência deve deixar uma única row RESERVED e o total reservado exato no banco de dados.
    Esperado: O motor deve garantir que, mesmo sob concorrência direta de processos ou threads
    tentando reservar e reconciliar, o estado físico do banco de dados permaneça perfeitamente exato.
    Proteção: o estado físico final comprova uma única reserva e total exato.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2.0"))

    # Reservas com IDs diferentes mas mesma chave única (call_id, route_id, attempt)
    r1 = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    r2 = ReservaOrcamento("r2", "call", "rota", 1, Decimal("1.0"), "price-v1")

    # Executa em paralelo. Esperamos que apenas uma reserva seja inserida no banco
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(repo.reservar, sessao, r1),
            executor.submit(repo.reservar, sessao, r2),
        ]
        concurrent.futures.wait(futures)

    caminho = repo.caminho("run")
    with sqlite3.connect(caminho) as con:
        reservas = con.execute(
            "SELECT reservation_id, status FROM budget_reservation WHERE run_id='run' AND thread_id='thread' AND call_id='call'"
        ).fetchall()
        # Deve haver exatamente 1 reserva ativa
        assert len(reservas) == 1

        reservado_sessao = con.execute(
            "SELECT reservado FROM budget_session WHERE run_id='run' AND thread_id='thread'"
        ).fetchone()[0]
        # O valor reservado na sessão deve ser exatamente 1.0 (não 2.0 ou corrompido)
        assert Decimal(reservado_sessao) == Decimal("1.0")


def test_idempotent_replay_concorrente_falha_com_lock(tmp_path):
    """
    (4) Replay idempotente sob concorrência.
    Esperado: Duas chamadas concorrentes idênticas de reserva (replay) devem ambas retornar
    sucesso de forma idempotente, sem que a contenção temporária levante ErroOrcamento.
    Proteção: a espera limitada do SQLite permite que o segundo replay observe o primeiro.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")

    # Rodamos o mesmo reservar concorrentemente em 2 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(repo.reservar, sessao, reserva) for _ in range(2)]
        resultados = []
        erros = []
        for f in concurrent.futures.as_completed(futures):
            try:
                resultados.append(f.result())
            except Exception as e:
                erros.append(e)

    # Ambas as chamadas idênticas deveriam completar com sucesso (sem erros)
    assert len(erros) == 0


def test_replay_reconciliacao_restart_valida_metadados(tmp_path):
    """
    (5) Falha na idempotência de replay de reconciliação após restart.
    Esperado: O replay da reconciliação após restart deve validar se os metadados do cliente
    concordam com o registro original no banco de dados.
    Proteção: o replay após restart revalida a identidade integral da reserva.
    """
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run1", "thread1", Decimal("5.0"))
    reserva = ReservaOrcamento("r1", "call1", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao, reserva)
    repo.reconciliar(sessao, reserva, Decimal("0.5"))

    # Simula restart
    repo_restart = RepositorioOrcamento(tmp_path)
    sessao_restart = repo_restart.sessao("run1", "thread1", Decimal("5.0"))

    # Tentativa de replay de reconciliação com metadados inconsistentes na reserva
    reserva_divergente = ReservaOrcamento(
        "r1", "call-divergente-restart", "rota", 1, Decimal("1.0"), "price-v1"
    )

    with pytest.raises(
        ErroOrcamento, match="reserva divergente|metadados de replay divergentes"
    ):
        repo_restart.reconciliar(sessao_restart, reserva_divergente, Decimal("0.5"))
