import hashlib
import json
import threading
import time

try:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver

from motor.eventos import LogEventos
from motor.eventos_schema import valido
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.servico import GerenciadorJobs
from motor.curador import carregar_runs
from motor_painel.painel import obter_runs
from tests.helpers_grafo import (
    GerenciadorJobsTeste,
    construir_grafo_teste as construir_grafo_offline,
)


def _spec_com_artefato() -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "issue-24",
            "objetivo": "produzir um artefato",
            "contexto": "",
            "criterios_cobertura": ["artefato produzido"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 1, "max_tentativas": 1},
        "subagentes": [{
            "id": "autor",
            "papel": "executor",
            "objetivo": "gerar um arquivo",
            "entradas": {},
            "resultado_esperado": "texto",
            "rubrica": ["tem texto"],
            "produz_artefatos": [{"nome": "saida.txt", "tipo": "txt"}],
        }],
        "gates": [],
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }


def _roteador(papel: str, _prompt: str) -> str:
    if papel == "executor":
        return "CONTEUDO ISSUE 24"
    if papel == "verifier":
        return json.dumps({"aprovado": True, "motivo": "ok"})
    if papel == "evaluator":
        return json.dumps({"aprovado": True, "lacunas": []})
    if papel == "synthesizer":
        return "FINAL"
    raise AssertionError(f"papel inesperado: {papel}")


def _aguardar(gerenciador: GerenciadorJobs, job_id: str, estado: str) -> dict:
    limite = time.monotonic() + 5
    while time.monotonic() < limite:
        status = gerenciador.status(job_id)
        if status["estado"] == estado:
            return status
        time.sleep(0.01)
    raise AssertionError(f"estado {estado!r} nao alcançado")


def test_artefato_declara_run_e_hash_no_evento(tmp_path):
    run_id = "run-issue-24"
    log_path = tmp_path / "log.jsonl"
    grafo = construir_grafo_offline(
        ClienteStub(_roteador),
        LogEventos(log_path),
        checkpointer=MemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        workspace_base=tmp_path / "runs",
    )

    resultado = grafo.invoke(
        {"spec": _spec_com_artefato(), "run_id": run_id, "thread_id": run_id},
        {"configurable": {"thread_id": run_id}},
    )
    eventos = [json.loads(linha) for linha in log_path.read_text().splitlines()]
    evento = next(item for item in eventos if item["evento"] == "artefato.atualizou")
    caminho = resultado["resultados"][0]["artefatos"][0]["caminho"]
    digest = hashlib.sha256(b"CONTEUDO ISSUE 24").hexdigest()

    assert evento["run_id"] == run_id
    assert evento["caminho"] == caminho
    assert evento["hash"] == digest
    assert valido(evento)


def test_evento_legado_sem_run_e_hash_continua_reabrindo(tmp_path):
    evento = {
        "t": 0.0,
        "seq": 1,
        "evento": "artefato.atualizou",
        "nome": "saida.txt",
        "tipo": "txt",
        "subagente": "autor",
        "caminho": str(tmp_path / "saida.txt"),
    }
    path = tmp_path / "legado.jsonl"
    path.write_text(json.dumps(evento) + "\n", encoding="utf-8")

    assert valido(evento)
    LogEventos(path).fechar()


def test_evento_com_proveniencia_alimenta_resumo_do_painel():
    evento = {
        "t": 0.0,
        "seq": 1,
        "evento": "artefato.atualizou",
        "nome": "saida.txt",
        "tipo": "txt",
        "subagente": "autor",
        "caminho": "/runs/run-24/artefatos/saida.txt",
        "run_id": "run-24",
        "hash": "a" * 64,
    }

    assert obter_runs([evento])[0]["id"] == "run-24"
    assert not valido({**evento, "hash": "curto"})
    assert not valido({key: value for key, value in evento.items() if key != "hash"})
    assert not valido({**evento, "run_id": " "})
    assert not valido({
        "t": 0.0, "seq": 1, "evento": "tarefa.concluida",
        "missao": "m", "run_id": " ",
    })


def test_servico_preserva_hash_do_artefato_sem_mudar_lista_legada(tmp_path):
    run_id = "run-servico-24"
    gerenciador = GerenciadorJobsTeste(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(_roteador),
    )
    try:
        gerenciador.iniciar(spec=_spec_com_artefato(), thread_id=run_id)
        _aguardar(gerenciador, run_id, "gate_pendente")
        gerenciador.responder_gate(run_id, "prosseguir")
        status = _aguardar(gerenciador, run_id, "concluido")
    finally:
        gerenciador.fechar()

    caminho = status["artefatos"][0]["caminho"]
    digest = hashlib.sha256(b"CONTEUDO ISSUE 24").hexdigest()
    assert set(status["artefatos"][0]) == {"nome", "tipo", "caminho", "subagente"}
    assert status["artefato_hashes"][caminho] == digest


def test_dois_writers_com_seq_local_repetida_separam_runs_e_legado_fica_orfao(tmp_path):
    barreira = threading.Barrier(2)
    caminhos = {run_id: tmp_path / run_id / "log.jsonl" for run_id in ("run-a", "run-b")}

    def escrever(run_id: str) -> None:
        log = LogEventos(caminhos[run_id], run_id=run_id)
        try:
            log.evento("spec.recebida", missao=run_id, subagentes=1)
            barreira.wait(timeout=5)
            log.evento("tarefa.concluida", missao=run_id)
        finally:
            log.fechar()

    threads = [threading.Thread(target=escrever, args=(run_id,)) for run_id in caminhos]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    eventos: list[dict] = []
    for fonte, caminho in caminhos.items():
        eventos.extend({**json.loads(linha), "__fonte": fonte} for linha in caminho.read_text().splitlines())
    eventos.append({"t": 0.0, "seq": 1, "evento": "tarefa.concluida", "missao": "antiga"})

    resumo = obter_runs(eventos)
    assert {run["id"] for run in resumo} == {"run-a", "run-b", "legado:sem-proveniencia"}
    assert all(run["n_eventos"] == 2 for run in resumo if run["id"] in {"run-a", "run-b"})


def test_servico_recusa_logger_injetado_de_outra_run(tmp_path):
    logger = LogEventos(tmp_path / "log.jsonl", run_id="outra-run")
    gerenciador = GerenciadorJobsTeste(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(_roteador),
        log=logger,
    )
    try:
        gerenciador._executar("run-certa", gerenciador._obter_cliente(), None)
        assert gerenciador._jobs["run-certa"]["estado"] == "erro"
        assert "outra run" in gerenciador._jobs["run-certa"]["erro"]["mensagem"]
    finally:
        gerenciador.fechar()


def test_curador_mantem_legado_em_um_unico_balde_sem_inferir_janela(tmp_path):
    caminho = tmp_path / "legado.jsonl"
    caminho.write_text(
        "\n".join([
            json.dumps({"t": 10.0, "evento": "executor.chamado", "executor": "a"}),
            json.dumps({"t": 0.1, "evento": "executor.chamado", "executor": "b"}),
        ]) + "\n",
        encoding="utf-8",
    )

    runs, malformadas = carregar_runs([caminho])

    assert malformadas == 0
    assert len(runs) == 1
    assert runs[0]["id"] == caminho.name
    assert runs[0]["proveniencia"] == "ausente"
    assert len(runs[0]["eventos"]) == 2
