import asyncio
import json

from motor.mcp_servidor import (
    DESCRICAO_DESPACHAR,
    DESCRICAO_RESPONDER_GATE,
    DESCRICAO_RESUMO,
    DESCRICAO_STATUS,
    criar_app,
)
from motor.modelos import ClienteStub
from motor.servico import GerenciadorJobs
from tests.test_grafo import faz_roteador


async def chamar(app, nome: str, args: dict) -> dict:
    blocos = await app.call_tool(nome, args)
    return json.loads(blocos[0].text)


async def aguardar_estado(app, job_id: str, estado: str, timeout_s: float = 3) -> dict:
    fim = asyncio.get_running_loop().time() + timeout_s
    ultimo = None
    while asyncio.get_running_loop().time() < fim:
        ultimo = await chamar(app, "metafabrica.status_missao", {"job_id": job_id})
        if ultimo["estado"] == estado:
            return ultimo
        await asyncio.sleep(0.02)
    raise AssertionError(f"estado {estado!r} não alcançado; último={ultimo!r}")


def test_descricoes_mcp_sao_contrato():
    async def cenario():
        app = criar_app(GerenciadorJobs(cliente=ClienteStub(faz_roteador())))
        ferramentas = {tool.name: tool.description for tool in await app.list_tools()}

        assert ferramentas["metafabrica.despachar_missao"] == DESCRICAO_DESPACHAR
        assert ferramentas["metafabrica.status_missao"] == DESCRICAO_STATUS
        assert ferramentas["metafabrica.responder_gate"] == DESCRICAO_RESPONDER_GATE
        assert ferramentas["metafabrica.resumo_missao"] == DESCRICAO_RESUMO

    asyncio.run(cenario())


def test_mcp_despacha_status_e_responde_gate(tmp_path):
    async def cenario():
        gerenciador = GerenciadorJobs(
            db_path=tmp_path / "motor.db",
            workspace_base=tmp_path / "runs",
            cliente=ClienteStub(faz_roteador()),
        )
        app = criar_app(gerenciador)

        inicio = await chamar(app, "metafabrica.despachar_missao", {
            "objetivo": "pesquise oportunidades",
            "contexto": "teste",
            "restricoes": {"max_subagentes": 2},
        })
        assert inicio["estado"] == "em_execucao"
        assert inicio["job_id"]

        gate = await aguardar_estado(app, inicio["job_id"], "gate_pendente")
        assert gate["gate"]["portao"] == "plano"
        resumo = await chamar(app, "metafabrica.resumo_missao", {"job_id": inicio["job_id"]})
        assert resumo["estado"] == "gate_pendente"
        assert resumo["gate"]["portao"] == "plano"

        retomada = await chamar(app, "metafabrica.responder_gate", {
            "job_id": inicio["job_id"],
            "decisao": "prosseguir",
        })
        assert retomada["estado"] == "em_execucao"

        concluido = await aguardar_estado(app, inicio["job_id"], "concluido")
        assert concluido["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"

    asyncio.run(cenario())


def test_mcp_despachar_aceita_thread_id_explicito(tmp_path):
    async def cenario():
        gerenciador = GerenciadorJobs(
            db_path=tmp_path / "motor.db",
            workspace_base=tmp_path / "runs",
            cliente=ClienteStub(faz_roteador()),
        )
        app = criar_app(gerenciador)

        inicio = await chamar(app, "metafabrica.despachar_missao", {
            "objetivo": "pesquise oportunidades",
            "thread_id": "jarvis-abc",
        })

        assert inicio == {"job_id": "jarvis-abc", "estado": "em_execucao"}

    asyncio.run(cenario())


def test_mcp_despachar_sem_thread_id_gera_id(tmp_path):
    async def cenario():
        gerenciador = GerenciadorJobs(
            db_path=tmp_path / "motor.db",
            workspace_base=tmp_path / "runs",
            cliente=ClienteStub(faz_roteador()),
        )
        app = criar_app(gerenciador)

        inicio = await chamar(app, "metafabrica.despachar_missao", {
            "objetivo": "pesquise oportunidades",
        })

        assert inicio["estado"] == "em_execucao"
        assert isinstance(inicio["job_id"], str)
        assert inicio["job_id"]
        assert inicio["job_id"] != "jarvis-abc"

    asyncio.run(cenario())


def test_mcp_falha_de_provedor_vira_erro_estruturado():
    class GerenciadorFalho:
        def iniciar(self, **kwargs):
            raise RuntimeError("sem provedor")

        def status(self, job_id):
            return {"estado": "em_execucao"}

        def responder_gate(self, job_id, decisao):
            return {"estado": "em_execucao"}

    async def cenario():
        app = criar_app(GerenciadorFalho())
        resposta = await chamar(app, "metafabrica.despachar_missao", {"objetivo": "x"})

        assert resposta == {
            "estado": "erro",
            "erro": {"tipo": "RuntimeError", "mensagem": "sem provedor"},
        }

    asyncio.run(cenario())
