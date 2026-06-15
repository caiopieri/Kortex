"""WorkflowSpec v0.1 — o artefato central do motor.

A dinâmica da meta-fábrica vive AQUI (dado serializado, inspecionável,
reexecutável), não no código do grafo. Mudou a missão → muda a spec,
nunca se improvisa no grafo. Schema próprio, framework-agnóstico.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

VERSAO_SUPORTADA = "0.1"


class Restricoes(BaseModel):
    teto_custo: float = Field(default=2.0, gt=0, description="R$ máximos da missão (hook; medição na fabricação)")
    max_subagentes: int = Field(default=10, ge=1, le=100)
    max_tentativas: int = Field(default=3, ge=1, le=5, description="tentativas por subagente (attempt→verifier)")


class Subagente(BaseModel):
    id: str = Field(min_length=1)
    papel: str = Field(min_length=1, description="papel de modelo (mapeado no cliente: pesquisador, redator...)")
    objetivo: str = Field(min_length=1)
    entradas: dict[str, Any] = Field(default_factory=dict)
    resultado_esperado: str = Field(min_length=1)
    rubrica: list[str] = Field(min_length=1, description="critérios objetivos que o verifier checa")
    ferramentas: Optional[str] = Field(default=None, description="ex.: 'WebSearch' para claude -p")
    tier: Optional[str] = Field(default=None, description="classe de complexidade p/ roteamento por custo (ex.: simples/media/complexa); o planner classifica, a tabela tiers do cliente mapeia tier→modelo. Ausente → roteia por papel.")
    depende_de: list[str] = Field(default_factory=list, description="reservado; v0 só executa fan-out paralelo")


class GateFundador(BaseModel):
    id: str
    condicao: str = Field(description="quando escalar (avaliado pelo evaluator)")
    pergunta: str
    opcoes: str


class Missao(BaseModel):
    id: str = Field(min_length=1)
    objetivo: str = Field(min_length=1)
    contexto: str = ""
    criterios_cobertura: list[str] = Field(min_length=1, description="o que precisa estar coberto antes da síntese")


class Sintese(BaseModel):
    instrucao: str = Field(min_length=1)
    formato: Literal["markdown", "json"] = "markdown"


class WorkflowSpec(BaseModel):
    versao: str = VERSAO_SUPORTADA
    padrao: Literal["fan_out_sintese"] = "fan_out_sintese"
    missao: Missao
    restricoes: Restricoes = Field(default_factory=Restricoes)
    subagentes: list[Subagente] = Field(min_length=1)
    gates: list[GateFundador] = Field(default_factory=list)
    sintese: Sintese

    @model_validator(mode="after")
    def _consistencia(self) -> "WorkflowSpec":
        if self.versao != VERSAO_SUPORTADA:
            raise ValueError(f"versão '{self.versao}' não suportada (motor fala {VERSAO_SUPORTADA})")
        ids = [s.id for s in self.subagentes]
        if len(ids) != len(set(ids)):
            raise ValueError("ids de subagentes duplicados")
        if len(ids) > self.restricoes.max_subagentes:
            raise ValueError(f"{len(ids)} subagentes excede max_subagentes={self.restricoes.max_subagentes}")
        for s in self.subagentes:
            if s.depende_de:
                raise ValueError(
                    f"subagente '{s.id}' usa depende_de — o padrão fan_out_sintese v0 "
                    "só executa em paralelo; ondas/dependências entram em padrão futuro"
                )
        return self
