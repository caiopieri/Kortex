"""Servidor MCP fino da meta-fábrica.

Exposição stdio para hosts MCP: o servidor só embrulha GerenciadorJobs. Gates
sobem crus e a decisão volta por responder_gate; não há porteiro dentro do motor.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from .servico import GerenciadorJobs


DESCRICAO_DESPACHAR = """Entrega uma missão complexa à meta-fábrica: pesquisa multi-fonte, produção
  verificada e síntese. Use quando a tarefa exige vários passos/verificação
  adversarial e excede uma resposta direta do assistente. Não use para perguntas
  simples nem ações de sistema. Retorna um job_id para acompanhar; a execução é
  assíncrona (consulte status_missao). Passe `thread_id` para reusar/correlacionar
  uma missão; se omitido, um id é gerado."""

DESCRICAO_STATUS = """Consulta o estado de uma missão: em_execucao | gate_pendente | concluido | erro.
  Se gate_pendente, traz o payload do gate (decisão humana necessária). Se concluido,
  traz resposta_final e referências de artefato. Não bloqueia."""

DESCRICAO_RESPONDER_GATE = """Responde um gate pendente de uma missão e retoma a execução. USO INTERNO do
  fluxo de autorização do chamador (porteiro), não é ferramenta de uso livre do
  modelo. A decisão vem da política de risco do host, nunca do julgamento de um modelo."""

DESCRICAO_RESUMO = """Resumo compacto de uma missão para acompanhamento conversacional: progresso,
  marcos, gate pendente e referências de artefato — sem despejar logs ou conteúdo.
  Use para responder 'como está a missão X'."""

DESCRICAO_EVENTOS = """Stream incremental read-only dos eventos JSONL de uma missão. Use `desde=0`
  na primeira chamada e depois `desde=proximo_offset` para polling sem repetir eventos."""

MAX_OBJETIVO = 8_192
MAX_CONTEXTO = 32_768
MAX_RESTRICOES_JSON = 8_192
MAX_DECISAO = 4_096
MAX_RESPOSTA_JSON = 65_536
MAX_MENSAGEM_ERRO = 512


def _texto_limitado(valor: object, nome: str, maximo: int, *, vazio: bool = False) -> str:
    if not isinstance(valor, str) or len(valor) > maximo or (not vazio and not valor.strip()):
        raise ValueError(f"{nome} inválido")
    return valor


def _restricoes_limitadas(valor: dict[str, Any] | None) -> str | None:
    if valor is None:
        return None
    try:
        serializado = json.dumps(valor, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as erro:
        raise ValueError("restrições inválidas") from erro
    if len(serializado) > MAX_RESTRICOES_JSON:
        raise ValueError("restrições inválidas")
    return serializado


def _erro_limitado(erro: BaseException) -> dict[str, Any]:
    return {
        "estado": "erro",
        "erro": {
            "tipo": type(erro).__name__[:128],
            "mensagem": str(erro)[:MAX_MENSAGEM_ERRO],
        },
    }


def _resposta_limitada(valor: object) -> dict[str, Any]:
    if not isinstance(valor, dict):
        return _erro_limitado(ValueError("resposta MCP inválida"))
    try:
        serializado = json.dumps(
            valor, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        return _erro_limitado(ValueError("resposta MCP inválida"))
    if len(serializado) > MAX_RESPOSTA_JSON:
        return _erro_limitado(ValueError("resposta MCP excede limite"))
    return valor


def _gerenciador_de_env() -> GerenciadorJobs:
    modelos = os.environ.get("MOTOR_MODELOS")
    registro = os.environ.get("MOTOR_REGISTRO")
    cfg_modelos = json.loads(Path(modelos).read_text(encoding="utf-8")) if modelos else None
    return GerenciadorJobs(
        db_path=os.environ.get("MOTOR_DB", "motor.db"),
        workspace_base=os.environ.get("MOTOR_WORKSPACE", "runs"),
        cfg_modelos=cfg_modelos,
        dir_registro=registro,
    )


def criar_app(gerenciador: GerenciadorJobs | None = None) -> FastMCP:
    app = FastMCP("metafabrica")
    jobs = gerenciador or _gerenciador_de_env()

    @app.tool(name="metafabrica.despachar_missao", description=DESCRICAO_DESPACHAR)
    def despachar_missao(objetivo: str, contexto: str | None = None,
                         restricoes: dict[str, Any] | None = None,
                         thread_id: str | None = None) -> dict:
        try:
            partes = [_texto_limitado(objetivo, "objetivo", MAX_OBJETIVO)]
            if contexto is not None:
                partes.append(
                    f"\n\nContexto:\n{_texto_limitado(contexto, 'contexto', MAX_CONTEXTO)}"
                )
            restricoes_json = _restricoes_limitadas(restricoes)
            if restricoes_json is not None:
                partes.append("\n\nRestrições:\n" + restricoes_json)
            return _resposta_limitada(
                jobs.iniciar(missao_texto="".join(partes), thread_id=thread_id or uuid4().hex)
            )
        except Exception as ex:
            return _erro_limitado(ex)

    @app.tool(name="metafabrica.status_missao", description=DESCRICAO_STATUS)
    def status_missao(job_id: str) -> dict:
        try:
            return _resposta_limitada(jobs.status(job_id))
        except Exception as ex:
            return _erro_limitado(ex)

    @app.tool(name="metafabrica.responder_gate", description=DESCRICAO_RESPONDER_GATE)
    def responder_gate(job_id: str, decisao: str, decision_id: str | None = None) -> dict:
        try:
            decisao = _texto_limitado(decisao, "decisão", MAX_DECISAO)
            return _resposta_limitada(jobs.responder_gate(job_id, decisao, decision_id))
        except Exception as ex:
            return _erro_limitado(ex)

    @app.tool(name="metafabrica.resumo_missao", description=DESCRICAO_RESUMO)
    def resumo_missao(job_id: str) -> dict:
        try:
            return _resposta_limitada(jobs.resumo(job_id))
        except Exception as ex:
            return _erro_limitado(ex)

    @app.tool(name="metafabrica.eventos", description=DESCRICAO_EVENTOS)
    def eventos(job_id: str, desde: int = 0) -> dict:
        try:
            return _resposta_limitada(jobs.eventos(job_id, desde=desde))
        except Exception as ex:
            return _erro_limitado(ex)

    return app


def main() -> None:
    criar_app().run(transport="stdio")


if __name__ == "__main__":
    main()
