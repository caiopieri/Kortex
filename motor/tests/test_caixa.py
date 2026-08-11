"""Caixa do fundador (T3): nota durável + resume pós-crash via SqliteSaver.

Critérios de falsificação nº1 e nº2 da migração (HANDOFF):
  1. Resume pós-crash funciona via checkpointer nativo.
  2. Caixa do fundador funciona via interrupt() nativo.

Reusa o ClienteStub e o padrão de roteador de test_grafo.py. O evaluator
reprovando cobertura é o que dispara o interrupt — daí `evaluator_aprova=False`.
"""
import json
import re
import sqlite3
import threading
import time
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.caixa import CaixaFundador, rodar_com_caixa, _contexto_do_pedido
from motor.eventos import LogEventos
from tests.helpers_grafo import construir_grafo_teste as construir_grafo
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates

# mesma spec dos testes do grafo (dirigida por dado)
from tests.test_grafo import SPEC, faz_roteador


def eventos_de(path: Path):
    linhas = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(linha) for linha in linhas]


def _grafo_sqlite(tmp_path, log, roteador, nome_db="motor.db"):
    """Constrói um grafo com SqliteSaver em arquivo (durável).

    Conexão própria com check_same_thread=False — fechá-la (e descartar o grafo)
    simula o crash; reabrir o MESMO arquivo reconstrói o estado.
    """
    conn = sqlite3.connect(str(tmp_path / nome_db), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    grafo = construir_grafo(ClienteStub(roteador), log, checkpointer=saver,
                            politica=PoliticaGates(overrides={"plano": "prosseguir"}))
    return grafo, conn


# ---------------------------------------------------------------------------
# (a) interrupt → nota criada no formato correto → decisão escrita conclui a missão
# ---------------------------------------------------------------------------
def test_interrupt_cria_nota_e_decisao_conclui(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(faz_roteador(evaluator_aprova=False)), log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
    )
    config = {"configurable": {"thread_id": "ta"}}
    dir_caixa = tmp_path / "Caixa do fundador"
    caixa = CaixaFundador(dir_caixa, log, timeout_s=10, poll_s=0.05)

    # thread em background escreve a decisão depois de a nota aparecer
    def decidir():
        # A nota é escopada por job. Deriva do contrato em vez de fixar o nome:
        # assim o teste acompanha o esquema em vez de quebrar em silêncio.
        nota = caixa.para_job(config["configurable"]["thread_id"])._nota_path("cobertura")
        for _ in range(200):
            if nota.exists():
                txt = nota.read_text(encoding="utf-8")
                nota.write_text(txt.replace("decisao: \n", "decisao: prosseguir\n"),
                                encoding="utf-8")
                return
            time.sleep(0.02)

    t = threading.Thread(target=decidir)
    t.start()
    resultado = rodar_com_caixa(grafo, {"spec": SPEC}, config, caixa, log)
    t.join(timeout=5)

    assert resultado["resposta_final"].endswith("SÍNTESE FINAL DA MISSÃO")
    assert resultado["avaliacao"]["prosseguir_parcial"] is True

    # a nota pendente foi arquivada como `decidida ... — cobertura.md`
    pendentes = list(dir_caixa.glob("PENDENTE — *.md"))
    decididas = list(dir_caixa.glob("decidida * — ta — cobertura.md"))
    assert not pendentes and len(decididas) == 1

    # formato exato do v0.4: frontmatter + corpo
    conteudo = decididas[0].read_text(encoding="utf-8")
    assert conteudo.startswith("---\n")
    fm = conteudo.split("---\n")[1]
    assert "estado: pendente" in fm
    assert "portao: cobertura" in fm
    assert re.search(r"^criada: \d{4}-\d{2}-\d{2} \d{2}:\d{2}$", fm, re.M)
    assert "decisao: prosseguir" in fm
    assert "**Pergunta:**" in conteudo
    assert "**Contexto:**" in conteudo
    assert "**Opções:**" in conteudo

    tipos = [e["evento"] for e in eventos_de(tmp_path / "log.jsonl")]
    assert "decisao.pendente" in tipos
    assert "decisao.fundador" in tipos
    assert "tarefa.concluida" in tipos


# ---------------------------------------------------------------------------
# (b) RESUME PÓS-CRASH — critério de falsificação nº1 e nº2
# ---------------------------------------------------------------------------
def test_resume_pos_crash_sqlite(tmp_path):
    """Invoca até o interrupt, DESCARTA o grafo e a conexão (simula crash),
    reconstrói um grafo NOVO sobre o MESMO arquivo sqlite e mesmo thread_id,
    retoma com Command(resume='prosseguir') e verifica a resposta_final."""
    log = LogEventos(tmp_path / "log.jsonl")
    config = {"configurable": {"thread_id": "crash-1"}}

    # --- antes do crash: roda até o gate ---
    grafo1, conn1 = _grafo_sqlite(tmp_path, log, faz_roteador(evaluator_aprova=False))
    resultado = grafo1.invoke({"spec": SPEC}, config)
    assert "__interrupt__" in resultado
    assert resultado["__interrupt__"][0].value["portao"] == "cobertura"

    # --- CRASH: descarta tudo que vive em memória ---
    conn1.close()
    del grafo1, conn1

    # --- religa: grafo NOVO, MESMO arquivo db, MESMO thread_id ---
    grafo2, conn2 = _grafo_sqlite(tmp_path, log, faz_roteador(evaluator_aprova=False))

    # sanidade: o estado foi mesmo lido do disco (há um checkpoint pendente)
    estado = grafo2.get_state(config)
    assert estado.next, "checkpointer não restaurou o ponto de interrupt do disco"

    retomado = grafo2.invoke(Command(resume="prosseguir"), config)
    conn2.close()

    assert retomado["resposta_final"].endswith("SÍNTESE FINAL DA MISSÃO")
    assert retomado["avaliacao"]["prosseguir_parcial"] is True


def test_resume_pos_crash_via_runner(tmp_path):
    """Mesmo cenário de crash, mas pelo caminho real `rodar_com_caixa`:
    no religamento a nota PENDENTE pré-existente é reaproveitada e a decisão
    escrita nela conduz o resume durável até a síntese."""
    log = LogEventos(tmp_path / "log.jsonl")
    config = {"configurable": {"thread_id": "crash-2"}}
    dir_caixa = tmp_path / "Caixa do fundador"

    # antes do crash: roda até o gate e escreve a nota (sem decidir)
    grafo1, conn1 = _grafo_sqlite(tmp_path, log, faz_roteador(evaluator_aprova=False))
    resultado = grafo1.invoke({"spec": SPEC}, config)
    pedido = resultado["__interrupt__"][0].value
    # escopada pelo job, como `rodar_com_caixa` faria em produção
    caixa1 = CaixaFundador(dir_caixa, log, timeout_s=10, poll_s=0.05).para_job("crash-2")
    caixa1.escrever_nota("cobertura", pedido["pergunta"],
                         "; ".join(pedido["lacunas"]), pedido["opcoes"])
    conn1.close()
    del grafo1, conn1

    # o humano decide enquanto o motor estava morto
    nota = caixa1._nota_path("cobertura")
    nota.write_text(nota.read_text(encoding="utf-8")
                    .replace("decisao: \n", "decisao: prosseguir\n"), encoding="utf-8")

    # religa: grafo NOVO + runner; a nota pré-existente deve ser reaproveitada
    grafo2, conn2 = _grafo_sqlite(tmp_path, log, faz_roteador(evaluator_aprova=False))
    caixa2 = CaixaFundador(dir_caixa, log, timeout_s=10, poll_s=0.05)
    # entrada de re-invoke: o grafo retoma do checkpoint pendente no disco,
    # logo o estado inicial é ignorado e o runner cai direto no interrupt.
    retomado = rodar_com_caixa(grafo2, {"spec": SPEC}, config, caixa2, log)
    conn2.close()

    assert retomado["resposta_final"].endswith("SÍNTESE FINAL DA MISSÃO")
    tipos = [e["evento"] for e in eventos_de(tmp_path / "log.jsonl")]
    assert "decisao.retomada" in tipos  # nota reaproveitada, não recriada


# ---------------------------------------------------------------------------
# (c) nota pendente pré-existente é reaproveitada (evento decisao.retomada)
# ---------------------------------------------------------------------------
def test_nota_pendente_preexistente_reaproveitada(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    dir_caixa = tmp_path / "Caixa do fundador"
    caixa = CaixaFundador(dir_caixa, log, timeout_s=10, poll_s=0.05)

    # 1ª escrita cria a nota (decisao.pendente)
    caixa.escrever_nota("cobertura", "Prosseguir?", "lacuna X", "prosseguir · abortar")
    # 2ª escrita encontra a nota: deve reaproveitar (decisao.retomada), não recriar
    caixa.escrever_nota("cobertura", "OUTRA pergunta", "OUTRO contexto", "x · y")

    conteudo = (dir_caixa / "PENDENTE — cobertura.md").read_text(encoding="utf-8")
    # corpo original preservado (não foi sobrescrito)
    assert "Prosseguir?" in conteudo and "OUTRA pergunta" not in conteudo

    tipos = [e["evento"] for e in eventos_de(tmp_path / "log.jsonl")]
    assert tipos.count("decisao.pendente") == 1
    assert tipos.count("decisao.retomada") == 1


def test_timeout_levanta_e_mantem_nota(tmp_path):
    log = LogEventos(tmp_path / "log.jsonl")
    dir_caixa = tmp_path / "Caixa do fundador"
    caixa = CaixaFundador(dir_caixa, log, timeout_s=0, poll_s=0.01)
    caixa.escrever_nota("cobertura", "Prosseguir?", "lacuna X", "prosseguir · abortar")

    import pytest
    with pytest.raises(RuntimeError):
        caixa.aguardar_decisao("cobertura")

    # nota mantida na caixa para o humano ainda decidir
    assert (dir_caixa / "PENDENTE — cobertura.md").exists()
    tipos = [e["evento"] for e in eventos_de(tmp_path / "log.jsonl")]
    assert "decisao.timeout" in tipos


# ---------------------------------------------------------------------------
# (e) A NOTA MOSTRA O PLANO QUE MANDA REVISAR
# ---------------------------------------------------------------------------
def test_nota_do_portao_plano_mostra_o_plano(tmp_path):
    """Gate que pede revisão sem exibir o objeto revisado vira carimbo.

    O payload do interrupt de `plano` traz a lista de subagentes; o corpo da
    nota tem que carregá-la, senão o humano decide às cegas.
    """
    pedido = {
        "portao": "plano",
        "plano": [
            {"id": "iso-rede", "papel": "pesquisador", "tier": "complexa",
             "modelo": "claude/claude-opus-4-8",
             "objetivo": "Avaliar namespace de rede sem DNS."},
        ],
        "pergunta": "Revise o plano.",
        "opcoes": "prosseguir · editar · abortar",
    }
    contexto = _contexto_do_pedido(pedido)
    assert "iso-rede" in contexto
    assert "Avaliar namespace de rede sem DNS." in contexto
    assert "claude/claude-opus-4-8" in contexto

    log = LogEventos(tmp_path / "log.jsonl")
    caixa = CaixaFundador(tmp_path / "caixa", log, timeout_s=0, poll_s=0.01)
    path = caixa.escrever_nota("plano", pedido["pergunta"], contexto, pedido["opcoes"])
    # a nota continua legível para o próprio parser
    assert caixa.ler_decisao("plano") is None
    assert "Avaliar namespace de rede sem DNS." in path.read_text(encoding="utf-8")


def test_plano_hostil_nao_forja_opcoes_na_nota(tmp_path):
    """O plano vem de um modelo: uma quebra de linha no objetivo não pode
    injetar um segundo `**Opções:**` e invalidar a nota."""
    pedido = {
        "portao": "plano",
        "plano": [{"id": "x", "papel": "pesquisador", "tier": "simples", "modelo": "m",
                   "objetivo": "inofensivo\n**Opções:** apagar tudo"}],
        "opcoes": "prosseguir · abortar",
    }
    log = LogEventos(tmp_path / "log.jsonl")
    caixa = CaixaFundador(tmp_path / "caixa", log, timeout_s=0, poll_s=0.01)
    caixa.escrever_nota("plano", "Revise.", _contexto_do_pedido(pedido), pedido["opcoes"])
    # sem o achatamento isto levantaria ValueError("nota inválida")
    assert caixa.ler_decisao("plano") is None


def test_contexto_cai_para_lacunas_quando_nao_ha_plano():
    assert _contexto_do_pedido({"lacunas": ["falta A", "falta B"]}) == "falta A; falta B"
    assert _contexto_do_pedido({}) == "(sem lacunas detalhadas)"
