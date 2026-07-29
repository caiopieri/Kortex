"""Contrato versionado dos eventos emitidos pelo motor para superfícies read-only."""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, cast


SCHEMA_VERSAO = 2

EVENTOS_MONETARIOS = frozenset({
    "custo.reservado", "custo.reconciliado", "custo.bloqueado", "custo.contrato_violado",
})
_CAMPOS_ORCAMENTO = ["run_id", "thread_id", "call_id", "rota", "tentativa", "moeda", "teto", "gasto", "reservado", "event_id"]
_MAX_DECIMAL_CHARS = 128
_PRECISAO_DECIMAL = 2 * _MAX_DECIMAL_CHARS + 1
_DECIMAL_TEXTO = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


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
        "campos": ["papel", "provedor", "modelo", "prompt_tokens", "completion_tokens", "total_tokens", "estimado"],
        "descricao": "Tick incremental de uso/custo derivado de uma chamada de modelo.",
    },
    "custo.reservado": {
        "categoria": "orcamento",
        "campos": [*_CAMPOS_ORCAMENTO, "reservation_id", "maximo", "pricing_version"],
        "descricao": "Registra reserva monetaria aceita e os totais da sessao apos a reserva.",
    },
    "custo.reconciliado": {
        "categoria": "orcamento",
        "campos": [*_CAMPOS_ORCAMENTO, "reservation_id", "maximo", "custo_real",
                   "delta_liberado", "pricing_version"],
        "descricao": "Registra custo real reconciliado e os totais resultantes da sessao.",
    },
    "custo.bloqueado": {
        "categoria": "orcamento",
        "campos": [*_CAMPOS_ORCAMENTO, "motivo"],
        "descricao": "Registra bloqueio antes de efeito externo com snapshot monetario sanitizado.",
    },
    "custo.contrato_violado": {
        "categoria": "orcamento",
        "campos": [*_CAMPOS_ORCAMENTO, "reservation_id", "maximo", "custo_real",
                   "moeda_recebida", "pricing_version", "motivo"],
        "descricao": "Registra violacao de maximo, moeda ou custo real do contrato monetario.",
    },
    "curador.certificou": {
        "categoria": "curador",
        "campos": ["slot", "titular", "candidato", "motivo"],
        "descricao": "Registra certificacao do candidato avaliado em sombra.",
    },
    "curador.promocao_pendente": {
        "categoria": "curador",
        "campos": ["slot", "de", "para"],
        "descricao": "Registra intencao de promocao sujeita a gate humano.",
    },
    "curador.rejeitou": {
        "categoria": "curador",
        "campos": ["slot", "titular", "candidato", "motivo"],
        "descricao": "Registra rejeicao do candidato avaliado em sombra.",
    },
    "curador.sombra": {
        "categoria": "curador",
        "campos": ["slot", "titular", "candidato", "casos", "aprovados_titular", "aprovados_candidato"],
        "descricao": "Resume a comparacao read-only entre titular e candidato.",
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
        "campos": ["executor", "papel", "tier", "tentativa", "modelo", "template", "versao_template"],
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
        "campos": ["papel", "provedor", "modelo", "prompt_tokens", "completion_tokens", "total_tokens", "estimado"],
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
    "run.perfil": {
        "categoria": "missao",
        "campos": ["perfil"],
        "descricao": "Registra se o run é certificado ou rascunho para consumo pelo curador.",
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
    "gate.escalado": {
        "categoria": "gate",
        "campos": ["portao", "evitando", "tentativa"],
        "descricao": (
            "Portao reprovado subiu para juiz independente. `evitando` e o provedor "
            "que ja julgou: escalar para o mesmo provedor e pedir a mesma opiniao "
            "mais alto, nao uma segunda opiniao."
        ),
    },
    "escalada.esgotada": {
        "categoria": "gate",
        "campos": ["portao", "escaladas"],
        "descricao": "Teto de escaladas atingido; o portao degrada para decisao humana.",
    },
    "escalada.indisponivel": {
        "categoria": "gate",
        "campos": ["portao"],
        "descricao": (
            "Nao havia juiz independente disponivel. Falta de segunda opiniao nao e "
            "aprovacao: degrada para humano."
        ),
    },
    "tarefa.reprovada": {
        "categoria": "missao",
        "campos": ["missao", "reprovados"],
        "descricao": (
            "Missao terminou com no reprovado ou cobertura liberada com lacunas. "
            "Existe porque 'tarefa.concluida' sozinho fazia run reprovado ser "
            "indistinguivel de run aprovado para quem le o log de fora."
        ),
    },
    "evidencia.cobertura": {
        "categoria": "missao",
        "campos": ["missao", "execucao", "artefatos"],
        "descricao": (
            "Quantos artefatos da missao passaram por portao de EXECUCAO, de um "
            "total de artefatos produzidos. E a razao processo/opiniao medida no "
            "log: sem ela, missao sem nenhum portao de processo era indistinguivel "
            "de missao com a suite passando."
        ),
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


NoneType = type(None)
NUMERO = (int, float)
SEQUENCIA = (list, tuple)
BOOL_OU_NULO = (bool, NoneType)
DICT_OU_NULO = (dict, NoneType)
INT_OU_NULO = (int, NoneType)
STR_OU_NULO = (str, NoneType)
SEQUENCIA_OU_NULO = (SEQUENCIA, NoneType)

TIPOS_CAMPO: dict[str, Any] = {
    "alvo": str,
    "aprovado": bool,
    "aprovados_candidato": int,
    "aprovados_titular": int,
    "capacidades": SEQUENCIA,
    "caminho": str,
    "candidato": str,
    "casos": int,
    "call_id": str,
    "ciclo": INT_OU_NULO,
    "commitados": int,
    "completion_tokens": int,
    "custo_real": str,
    "de": str,
    "decisao": str,
    "delta_liberado": str,
    "edicoes": DICT_OU_NULO,
    "estimado": BOOL_OU_NULO,
    "event_id": str,
    "evitar": str,
    "executor": str,
    "fallback": bool,
    "ferramenta": str,
    "ferramentas": SEQUENCIA,
    "fonte": str,
    "gasto": str,
    "id": str,
    "ids": SEQUENCIA,
    "k": int,
    "kind": str,
    "lacunas": SEQUENCIA_OU_NULO,
    "reprovados": SEQUENCIA_OU_NULO,
    "escaladas": int,
    "execucao": int,
    "artefatos": int,
    "evitando": str,
    "metricas": DICT_OU_NULO,
    "missao": str,
    "moeda": str,
    "moeda_recebida": STR_OU_NULO,
    "modelo": str,
    "maximo": str,
    "motivo": str,
    "nome": str,
    "nos": SEQUENCIA,
    "nota": str,
    "padrao": str,
    "papel": str,
    "para": str,
    "perfil": str,
    "portao": str,
    "prazo_s": NUMERO,
    "pricing_version": str,
    "prompt_tokens": int,
    "provedor": str,
    "provedores": SEQUENCIA,
    "recuperados": int,
    "reservation_id": str,
    "reservado": str,
    "restantes": SEQUENCIA,
    "rodadas": int,
    "rota": str,
    "run_id": str,
    "slot": str,
    "subagente": str,
    "subagentes": SEQUENCIA,
    "template": str,
    "tentativa": int,
    "teto": str,
    "thread_id": str,
    "tier": str,
    "tipo": str,
    "titular": str,
    "total_tokens": int,
    "versao_template": str,
}

TIPOS_POR_EVENTO: dict[str, dict[str, Any]] = {
    "custo.contrato_violado": {"custo_real": STR_OU_NULO},
    "decisao.plano": {"decisao": STR_OU_NULO},
    "executor.chamado": {
        "modelo": STR_OU_NULO,
        "papel": STR_OU_NULO,
        "template": STR_OU_NULO,
        "tentativa": INT_OU_NULO,
        "tier": STR_OU_NULO,
        "versao_template": STR_OU_NULO,
    },
    "modelo.roteado_capacidade": {"provedor": STR_OU_NULO},
    "portao.reprovado": {"motivo": STR_OU_NULO},
    "spec.criada": {"subagentes": int},
    "spec.recebida": {"subagentes": int},
    "validador.rodou": {"motivo": STR_OU_NULO},
}

CAMPOS_OPCIONAIS: dict[str, set[str]] = {
    **{tipo: {"event_id"} for tipo in EVENTOS_MONETARIOS},
    "custo.tick": {"estimado"},
    "decisao.plano": {"decisao", "edicoes"},
    "executor.chamado": {
        "modelo",
        "papel",
        "template",
        "tentativa",
        "tier",
        "versao_template",
    },
    "ferramenta.executada": {"metricas"},
    "modelo.uso": {"estimado"},
    "portao.aprovado": {"ciclo"},
    "portao.reprovado": {"ciclo", "lacunas", "motivo"},
    "validador.rodou": {"motivo"},
}


def _tipo_esperado(tipo_evento: str, campo: str) -> Any:
    return TIPOS_POR_EVENTO.get(tipo_evento, {}).get(campo, TIPOS_CAMPO.get(campo))


def _tipo_valido(valor: Any, esperado: Any) -> bool:
    if isinstance(esperado, tuple):
        return any(_tipo_valido(valor, alternativa) for alternativa in esperado)
    if esperado is bool:
        return type(valor) is bool
    if esperado is int:
        return type(valor) is int
    if esperado is float:
        return type(valor) in (int, float) and math.isfinite(valor)
    return isinstance(esperado, type) and isinstance(valor, esperado)


def _identificador_valido(valor: Any) -> bool:
    return type(valor) is str and 0 < len(valor) <= 256 and valor == valor.strip() and valor.isprintable()


def _decimal_canonico(valor: Any) -> Decimal | None:
    if type(valor) is not str or not 0 < len(valor) <= _MAX_DECIMAL_CHARS or _DECIMAL_TEXTO.fullmatch(valor) is None:
        return None
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        return None
    return numero if numero.is_finite() else None


def _soma_exata(esquerda: Decimal, direita: Decimal) -> Decimal:
    # Cobre os dois textos inteiros mais um carry, inclusive com escalas opostas.
    with localcontext() as contexto:
        contexto.prec = _PRECISAO_DECIMAL
        return esquerda + direita


def _subtracao_exata(esquerda: Decimal, direita: Decimal) -> Decimal:
    with localcontext() as contexto:
        contexto.prec = _PRECISAO_DECIMAL
        return esquerda - direita


def _dominio_monetario_valido(tipo: str, evento: dict[str, Any]) -> bool:
    if tipo not in EVENTOS_MONETARIOS:
        return True

    ids = ("run_id", "thread_id", "call_id", "rota")
    if not all(_identificador_valido(evento[campo]) for campo in ids):
        return False
    if "event_id" in evento and re.fullmatch(r"[0-9a-f]{64}", evento["event_id"]) is None:
        return False
    for campo in ("reservation_id", "pricing_version"):
        if campo in evento and not _identificador_valido(evento[campo]):
            return False
    if evento["moeda"] != "BRL" or evento["tentativa"] < 1:
        return False

    teto = _decimal_canonico(evento["teto"])
    gasto = _decimal_canonico(evento["gasto"])
    reservado = _decimal_canonico(evento["reservado"])
    if teto is None or teto <= 0 or gasto is None or reservado is None:
        return False
    comprometido = _soma_exata(gasto, reservado)

    motivo = evento.get("motivo")
    snapshot_regular = tipo in {"custo.reservado", "custo.reconciliado"} or (
        tipo == "custo.bloqueado" and motivo != "sessao_invalida"
    )
    if snapshot_regular and comprometido > teto:
        return False

    if tipo == "custo.bloqueado":
        return motivo in {"sem_cotacao", "sem_adapter", "teto", "sessao_invalida"}

    maximo = _decimal_canonico(evento["maximo"])
    if maximo is None or maximo <= 0:
        return False
    if tipo == "custo.reservado":
        return reservado >= maximo

    custo_real_raw = evento["custo_real"]
    custo_real = None if custo_real_raw is None else _decimal_canonico(custo_real_raw)
    if custo_real_raw is not None and custo_real is None:
        return False

    if tipo == "custo.reconciliado":
        delta = _decimal_canonico(evento["delta_liberado"])
        return (
            custo_real is not None
            and custo_real <= maximo
            and delta is not None
            and delta == _subtracao_exata(maximo, custo_real)
            and gasto >= custo_real
        )

    moeda_recebida = evento["moeda_recebida"]
    if motivo == "custo_acima_maximo":
        return (
            custo_real is not None
            and custo_real > maximo
            and moeda_recebida == "BRL"
            and gasto >= custo_real
        )
    if motivo == "moeda_divergente":
        return (
            custo_real is not None
            and _identificador_valido(moeda_recebida)
            and moeda_recebida != "BRL"
            and comprometido <= teto
            and reservado >= maximo
        )
    return (
        motivo == "custo_invalido"
        and custo_real is None
        and moeda_recebida == "BRL"
        and comprometido <= teto
        and reservado >= maximo
    )


def valido(evento: dict[str, Any]) -> bool:
    if not isinstance(evento, dict):
        return False

    tipo = evento.get("evento")
    instante = evento.get("t")
    if not isinstance(tipo, str) or tipo not in ESQUEMA:
        return False
    if not _tipo_valido(instante, NUMERO):
        return False
    if cast(int | float, instante) < 0:
        return False
    if "seq" not in evento or not _tipo_valido(evento["seq"], int):
        return False
    if cast(int, evento["seq"]) < 1:
        return False

    campos = set(ESQUEMA[tipo]["campos"])
    payload = set(evento) - {"evento", "t", "seq"}
    if not payload <= campos:
        return False

    opcionais = CAMPOS_OPCIONAIS.get(tipo, set())
    for campo in campos:
        esperado = _tipo_esperado(tipo, campo)
        if esperado is None:
            return False
        if campo not in evento:
            if campo not in opcionais:
                return False
        elif not _tipo_valido(evento[campo], esperado):
            return False

    if tipo == "decisao.plano" and not payload & {"decisao", "edicoes"}:
        return False
    return _dominio_monetario_valido(tipo, evento)


def categoria_de(tipo: str) -> str:
    return str(ESQUEMA[tipo]["categoria"])
