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
    tipo: Literal["modelo", "ferramenta", "validador"] = "modelo"
    papel: Optional[str] = Field(default=None, description="papel de modelo (mapeado no cliente: pesquisador, redator...)")
    ferramenta: Optional[str] = Field(default=None, description="nome lógico da ferramenta determinística")
    valida: Optional[str] = Field(default=None, description="id do subagente cuja saída este nó valida")
    validador: Optional[dict[str, Any]] = Field(
        default=None,
        description="{'kind': 'schema_json'|'contem', 'config': {...}}",
    )
    objetivo: str = Field(min_length=1)
    entradas: dict[str, Any] = Field(default_factory=dict)
    resultado_esperado: str = Field(min_length=1)
    rubrica: list[str] = Field(default_factory=list, description="critérios objetivos que o verifier checa")
    ferramentas: Optional[str] = Field(default=None, description="ex.: 'WebSearch' para claude -p")
    fonte_rag: Optional[str] = Field(
        default=None,
        description="caminho de um dataset JSONL de registros a consultar como contexto RAG; ausente → sem RAG",
    )
    rag_k: int = Field(default=5, ge=1, description="nº máximo de registros recuperados e injetados")
    tier: Optional[str] = Field(default=None, description="classe de complexidade p/ roteamento por custo (ex.: simples/media/complexa); o planner classifica, a tabela tiers do cliente mapeia tier→modelo. Ausente → roteia por papel.")
    capacidades_requeridas: list[str] = Field(
        default_factory=list,
        description="capacidades que a tarefa exige (ex.: codigo, redacao, calculo). "
                    "Vazio → roteia por tier/papel como antes. O cliente escolhe o "
                    "executor mais barato que cobre TODAS estas capacidades.")
    depende_de: list[str] = Field(default_factory=list, description="ids de subagentes dos quais este depende")
    produz_artefatos: list[dict[str, Any]] = Field(default_factory=list, description="artefatos textuais produzidos pelo nó")
    produz: list[dict[str, Any]] = Field(default_factory=list, description="artefatos declarados por nó-ferramenta")


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
    template: Optional[str] = Field(default=None, description="nome do template de workflow que originou a missão")
    versao_template: Optional[str] = Field(default=None, description="versão do template de workflow usado")


class Sintese(BaseModel):
    instrucao: str = Field(min_length=1)
    formato: Literal["markdown", "json"] = "markdown"


class WorkflowSpec(BaseModel):
    versao: str = VERSAO_SUPORTADA
    padrao: Literal["fan_out_sintese", "grafo_dependencias"] = "fan_out_sintese"
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
        id_set = set(ids)
        if len(ids) > self.restricoes.max_subagentes:
            raise ValueError(f"{len(ids)} subagentes excede max_subagentes={self.restricoes.max_subagentes}")
        for s in self.subagentes:
            if s.tipo == "modelo":
                if not s.papel:
                    raise ValueError(f"subagente '{s.id}' do tipo modelo exige papel")
                if not s.rubrica:
                    raise ValueError(f"subagente '{s.id}' do tipo modelo exige rubrica")
            if s.tipo == "ferramenta" and not s.ferramenta:
                raise ValueError(f"subagente '{s.id}' do tipo ferramenta exige ferramenta")
            if s.tipo == "validador":
                if not s.valida:
                    raise ValueError(f"subagente '{s.id}' do tipo validador exige valida")
                if s.valida not in id_set:
                    raise ValueError(f"subagente '{s.id}' valida id inexistente '{s.valida}'")
                if s.valida == s.id:
                    raise ValueError(f"subagente '{s.id}' não pode validar a si mesmo")
                if s.valida not in s.depende_de:
                    raise ValueError(f"subagente '{s.id}' do tipo validador exige valida em depende_de")
                if not isinstance(s.validador, dict):
                    raise ValueError(f"subagente '{s.id}' do tipo validador exige validador")
                kind = s.validador.get("kind")
                if kind not in {"schema_json", "contem"}:
                    raise ValueError(f"subagente '{s.id}' usa validador kind inválido: {kind}")
            if len(s.produz_artefatos) > 1:
                raise ValueError(f"subagente '{s.id}' declara mais de um artefato")
            for artefato in [*s.produz_artefatos, *s.produz]:
                if not str(artefato.get("nome", "")).strip():
                    raise ValueError(f"subagente '{s.id}' declara artefato sem nome")
                if not str(artefato.get("tipo", "")).strip():
                    raise ValueError(f"subagente '{s.id}' declara artefato sem tipo")
        if self.padrao == "fan_out_sintese":
            for s in self.subagentes:
                if s.depende_de:
                    raise ValueError(
                        f"subagente '{s.id}' usa depende_de — o padrão fan_out_sintese v0 "
                        "só executa em paralelo; ondas/dependências entram em padrão futuro"
                    )
            return self

        deps_por_id = {s.id: list(s.depende_de) for s in self.subagentes}
        for s in self.subagentes:
            for dep in s.depende_de:
                if dep not in id_set:
                    raise ValueError(f"subagente '{s.id}' depende de id inexistente '{dep}'")
                if dep == s.id:
                    raise ValueError(f"subagente '{s.id}' não pode depender de si mesmo")

        visitando: set[str] = set()
        visitados: set[str] = set()
        pilha: list[str] = []

        def visitar(sid: str) -> None:
            if sid in visitados:
                return
            if sid in visitando:
                inicio = pilha.index(sid) if sid in pilha else 0
                ciclo = pilha[inicio:] + [sid]
                raise ValueError(f"ciclo em depende_de: {', '.join(ciclo)}")
            visitando.add(sid)
            pilha.append(sid)
            for dep in deps_por_id[sid]:
                visitar(dep)
            pilha.pop()
            visitando.remove(sid)
            visitados.add(sid)

        for sid in ids:
            visitar(sid)

        def refs_artefato(valor: Any) -> list[dict[str, Any]]:
            refs: list[dict[str, Any]] = []
            if isinstance(valor, dict):
                ref = valor.get("ref_artefato")
                if isinstance(ref, dict):
                    refs.append(ref)
                for item in valor.values():
                    refs.extend(refs_artefato(item))
            elif isinstance(valor, list):
                for item in valor:
                    refs.extend(refs_artefato(item))
            return refs

        sub_por_id = {s.id: s for s in self.subagentes}
        for s in self.subagentes:
            deps = set(s.depende_de)
            for ref in refs_artefato(s.entradas):
                origem = str(ref.get("de") or "")
                nome = str(ref.get("nome") or "")
                if origem not in deps:
                    raise ValueError(
                        f"ref_artefato de '{s.id}' aponta para '{origem}', que não está em depende_de"
                    )
                declarados = [
                    str(a.get("nome") or "")
                    for a in [*sub_por_id[origem].produz_artefatos, *sub_por_id[origem].produz]
                ]
                if nome not in declarados:
                    raise ValueError(
                        f"ref_artefato de '{s.id}' aponta para artefato '{nome}' não declarado por '{origem}'"
                    )
        return self
