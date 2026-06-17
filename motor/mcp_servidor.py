"""Servidor MCP fino da meta-fábrica.

Exposição stdio para o Jarvis: o servidor só embrulha GerenciadorJobs. Gates
sobem crus e a decisão volta por responder_gate; não há porteiro dentro do motor.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from .servico import GerenciadorJobs


DESCRICAO_DESPACHAR = """Entrega uma missão complexa à meta-fábrica: pesquisa multi-fonte, produção
  verificada e síntese. Use quando a tarefa exige vários passos/verificação
  adversarial e excede uma resposta direta do assistente. Não use para perguntas
  simples nem ações de sistema. Retorna um job_id para acompanhar; a execução é
  assíncrona (consulte status_missao)."""

DESCRICAO_STATUS = """Consulta o estado de uma missão: em_execucao | gate_pendente | concluido | erro.
  Se gate_pendente, traz o payload do gate (decisão humana necessária). Se concluido,
  traz resposta_final e referências de artefato. Não bloqueia."""

DESCRICAO_RESPONDER_GATE = """Responde um gate pendente de uma missão e retoma a execução. USO INTERNO do
  fluxo de autorização do chamador (porteiro), não é ferramenta de uso livre do
  modelo. A decisão vem da escada de risco do Jarvis, nunca do julgamento de um modelo."""


def criar_app(gerenciador: GerenciadorJobs | None = None) -> FastMCP:
    app = FastMCP("metafabrica")
    jobs = gerenciador or GerenciadorJobs()

    @app.tool(name="metafabrica.despachar_missao", description=DESCRICAO_DESPACHAR)
    def despachar_missao(objetivo: str, contexto: str | None = None,
                         restricoes: dict[str, Any] | None = None) -> dict:
        try:
            partes = [objetivo]
            if contexto:
                partes.append(f"\n\nContexto:\n{contexto}")
            if restricoes:
                partes.append("\n\nRestrições:\n" + json.dumps(restricoes, ensure_ascii=False))
            return jobs.iniciar(missao_texto="".join(partes), thread_id=uuid4().hex)
        except Exception as ex:
            return {"estado": "erro", "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)}}

    @app.tool(name="metafabrica.status_missao", description=DESCRICAO_STATUS)
    def status_missao(job_id: str) -> dict:
        try:
            return jobs.status(job_id)
        except Exception as ex:
            return {"estado": "erro", "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)}}

    @app.tool(name="metafabrica.responder_gate", description=DESCRICAO_RESPONDER_GATE)
    def responder_gate(job_id: str, decisao: str) -> dict:
        try:
            return jobs.responder_gate(job_id, decisao)
        except Exception as ex:
            return {"estado": "erro", "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)}}

    return app


def main() -> None:
    criar_app().run(transport="stdio")


if __name__ == "__main__":
    main()
