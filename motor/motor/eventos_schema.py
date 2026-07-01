"""Contrato versionado dos eventos emitidos pelo motor para superfícies read-only."""
from __future__ import annotations

from typing import Any


SCHEMA_VERSAO = 1


ESQUEMA: dict[str, dict[str, Any]] = {
    "aresta.fluxo": {
        "categoria": "fluxo",
        "campos": ["de", "para"],
        "descricao": "Sinaliza que a execução fluiu de uma dependência para um nó.",
    },
    "artefato.atualizou": {
        "categoria": "artefato",
        "campos": ["nome", "tipo", "subagente", "caminho"],
        "descricao": "Sinaliza criação ou atualização de artefato por subagente.",
    },
    "custo.tick": {
        "categoria": "modelo",
        "campos": ["papel", "provedor", "modelo", "prompt_tokens", "completion_tokens", "total_tokens"],
        "descricao": "Tick incremental de uso/custo derivado de uma chamada de modelo.",
    },
    "decisao.fundador": {
        "categoria": "gate",
        "campos": ["portao", "decisao"],
        "descricao": "Registra decisão humana no gate do fundador.",
    },
    "decisao.pendente": {
        "categoria": "gate",
        "campos": ["portao", "nota"],
        "descricao": "Registra criação de uma decisão pendente na caixa do fundador.",
    },
    "decisao.plano": {
        "categoria": "gate",
        "campos": ["decisao", "edicoes"],
        "descricao": "Registra decisão ou edição humana sobre o plano.",
    },
    "decisao.retomada": {
        "categoria": "gate",
        "campos": ["portao", "nota"],
        "descricao": "Registra retomada de decisão persistida na caixa do fundador.",
    },
    "decisao.timeout": {
        "categoria": "gate",
        "campos": ["portao", "prazo_s"],
        "descricao": "Registra timeout aguardando decisão humana.",
    },
    "escalado": {
        "categoria": "resiliencia",
        "campos": ["para"],
        "descricao": "Sinaliza escalada para revisão humana.",
    },
    "executor.chamado": {
        "categoria": "ciclo",
        "campos": ["executor", "papel", "tier", "tentativa", "modelo"],
        "descricao": "Sinaliza início de chamada a executor, planner, avaliador ou sintetizador.",
    },
    "executor.erro": {
        "categoria": "ciclo",
        "campos": ["executor", "motivo", "tentativa"],
        "descricao": "Registra erro de executor ou planner.",
    },
    "executor.escalado": {
        "categoria": "resiliencia",
        "campos": ["executor", "de", "para", "tentativa"],
        "descricao": "Registra escalada de tier de um executor após reprovação.",
    },
    "executor.respondeu": {
        "categoria": "ciclo",
        "campos": ["executor", "tentativa"],
        "descricao": "Sinaliza que o executor respondeu com conteúdo.",
    },
    "ferramenta.executada": {
        "categoria": "ferramenta",
        "campos": ["ferramenta", "subagente", "aprovado", "metricas"],
        "descricao": "Registra execução de ferramenta externa registrada.",
    },
    "ferramenta.indisponivel": {
        "categoria": "ferramenta",
        "campos": ["ferramenta", "motivo"],
        "descricao": "Registra ferramenta ausente, inválida ou não executável.",
    },
    "ferramenta.saida_invalida": {
        "categoria": "ferramenta",
        "campos": ["ferramenta", "subagente", "motivo"],
        "descricao": "Registra saída de ferramenta que não respeitou contrato.",
    },
    "gate.auto": {
        "categoria": "gate",
        "campos": ["portao", "decisao"],
        "descricao": "Registra resolução automática de gate pela política ativa.",
    },
    "grafo_dep.iniciado": {
        "categoria": "fluxo",
        "campos": ["subagentes"],
        "descricao": "Sinaliza início de execução por grafo de dependências.",
    },
    "grafo_dep.travado": {
        "categoria": "fluxo",
        "campos": ["restantes"],
        "descricao": "Registra bloqueio topológico no grafo de dependências.",
    },
    "juiz.independencia": {
        "categoria": "modelo",
        "campos": ["papel", "evitar", "para"],
        "descricao": "Registra desvio de juiz para provedor independente do executor.",
    },
    "lacuna.preenchida": {
        "categoria": "reconciliacao",
        "campos": ["subagente"],
        "descricao": "Sinaliza recomputação de subagente para preencher lacuna.",
    },
    "modelo.falha": {
        "categoria": "modelo",
        "campos": ["papel", "tentativa", "motivo"],
        "descricao": "Registra falha transitória ou total em cliente de modelo.",
    },
    "modelo.fallback": {
        "categoria": "resiliencia",
        "campos": ["papel", "para"],
        "descricao": "Registra fallback para outro cliente de modelo.",
    },
    "modelo.pin": {
        "categoria": "modelo",
        "campos": ["papel", "tier"],
        "descricao": "Registra seleção por pin manual de modelo.",
    },
    "modelo.reroteado_esgotado": {
        "categoria": "resiliencia",
        "campos": ["papel", "de", "para"],
        "descricao": "Registra reroteamento porque o provedor selecionado estava esgotado.",
    },
    "modelo.roteado_capacidade": {
        "categoria": "modelo",
        "campos": ["papel", "capacidades", "provedor"],
        "descricao": "Registra roteamento por capacidades requeridas.",
    },
    "modelo.roteado_ferramentas": {
        "categoria": "modelo",
        "campos": ["papel", "ferramentas"],
        "descricao": "Registra desvio por incompatibilidade de ferramenta.",
    },
    "modelo.roteado_tier": {
        "categoria": "modelo",
        "campos": ["papel", "tier"],
        "descricao": "Registra roteamento por tier de complexidade/custo.",
    },
    "modelo.uso": {
        "categoria": "modelo",
        "campos": ["papel", "provedor", "modelo", "prompt_tokens", "completion_tokens", "total_tokens"],
        "descricao": "Registra uso de tokens reportado pelo provedor de modelo.",
    },
    "onda.concluida": {
        "categoria": "fluxo",
        "campos": ["ids"],
        "descricao": "Sinaliza conclusão de onda em grafo de dependências.",
    },
    "onda.iniciada": {
        "categoria": "fluxo",
        "campos": ["ids"],
        "descricao": "Sinaliza início de onda em grafo de dependências.",
    },
    "paralelo.concluido": {
        "categoria": "fluxo",
        "campos": ["commitados"],
        "descricao": "Sinaliza conclusão da fase paralela.",
    },
    "paralelo.iniciado": {
        "categoria": "fluxo",
        "campos": ["subagentes"],
        "descricao": "Sinaliza início da fase paralela.",
    },
    "portao.aprovado": {
        "categoria": "gate",
        "campos": ["portao", "ciclo"],
        "descricao": "Registra aprovação de portão de verificação ou cobertura.",
    },
    "portao.reprovado": {
        "categoria": "gate",
        "campos": ["portao", "ciclo", "motivo", "lacunas"],
        "descricao": "Registra reprovação de portão de verificação ou cobertura.",
    },
    "provedor.auto_esgotado": {
        "categoria": "resiliencia",
        "campos": ["provedor", "papel", "motivo"],
        "descricao": "Registra esgotamento automático de provedor por falha.",
    },
    "provedor.esgotado": {
        "categoria": "resiliencia",
        "campos": ["provedores"],
        "descricao": "Registra provedores marcados como esgotados por configuração.",
    },
    "rag.consultado": {
        "categoria": "dados",
        "campos": ["subagente", "fonte", "k", "recuperados", "ids"],
        "descricao": "Registra consulta a dataset RAG local para injeção de contexto.",
    },
    "reconciliacao.concluida": {
        "categoria": "reconciliacao",
        "campos": ["nos"],
        "descricao": "Sinaliza conclusão de rodada de reconciliação.",
    },
    "reconciliacao.esgotada": {
        "categoria": "reconciliacao",
        "campos": ["rodadas"],
        "descricao": "Registra esgotamento das rodadas de reconciliação.",
    },
    "reconciliacao.iniciada": {
        "categoria": "reconciliacao",
        "campos": ["nos"],
        "descricao": "Sinaliza início de rodada de reconciliação.",
    },
    "registro.sem_executor": {
        "categoria": "modelo",
        "campos": ["papel", "capacidades"],
        "descricao": "Registra ausência de executor compatível no registro de capacidades.",
    },
    "rota.escolhida": {
        "categoria": "missao",
        "campos": ["rota", "padrao", "fallback"],
        "descricao": "Registra rota de decomposição escolhida pelo seletor.",
    },
    "spec.criada": {
        "categoria": "missao",
        "campos": ["missao", "subagentes"],
        "descricao": "Registra WorkflowSpec criada pelo planner.",
    },
    "spec.recebida": {
        "categoria": "missao",
        "campos": ["missao", "subagentes"],
        "descricao": "Registra WorkflowSpec fornecida diretamente ao motor.",
    },
    "tarefa.abortada": {
        "categoria": "missao",
        "campos": ["motivo"],
        "descricao": "Sinaliza aborto da tarefa por decisão humana ou política.",
    },
    "tarefa.concluida": {
        "categoria": "missao",
        "campos": ["missao"],
        "descricao": "Sinaliza conclusão da tarefa.",
    },
    "validador.rodou": {
        "categoria": "gate",
        "campos": ["id", "alvo", "kind", "aprovado", "motivo"],
        "descricao": "Registra execução de validador determinístico sobre saída de subagente.",
    },
}


def tipos() -> set[str]:
    return set(ESQUEMA)


def valido(evento: dict[str, Any]) -> bool:
    tipo = evento.get("evento")
    return isinstance(tipo, str) and tipo in ESQUEMA


def categoria_de(tipo: str) -> str:
    return str(ESQUEMA[tipo]["categoria"])
