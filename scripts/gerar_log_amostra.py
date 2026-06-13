#!/usr/bin/env python3
"""Gera exemplos/log-amostra.jsonl (amostra do painel — separada do log vivo log.jsonl).

Monta o grafo com ClienteStub (padrão de tests/test_grafo.py) usando
exemplos/missao-pesquisa.json e simula:
  - spec recebida
  - fan-out com dois subagentes (pesquisa-alfa, pesquisa-beta)
  - verifier reprova pesquisa-beta na 1ª tentativa (portao.reprovado)
  - verifier aprova pesquisa-beta na 2ª tentativa (portao.aprovado)
  - evaluator reprova cobertura global (portao.reprovado portao=cobertura)
  - escalado ao fundador → interrupt → resume "prosseguir" (decisao.fundador)
  - síntese e tarefa.concluida

Uso: python3 scripts/gerar_log_amostra.py
Saída: exemplos/log-amostra.jsonl.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Garante que o pacote motor é encontrado ao rodar como script
REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from langgraph.types import Command

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub

SPEC = json.loads((REPO / "exemplos" / "missao-pesquisa.json").read_text(encoding="utf-8"))
LOG_PATH = REPO / "exemplos" / "log-amostra.jsonl"


def faz_roteador():
    """Stub determinístico que simula:
    - verifier reprova pesquisa-beta uma vez
    - evaluator reprova cobertura global (força gate de fundador)
    """
    estado = {"beta_reprovado": False}

    def roteador(papel: str, prompt: str):
        if papel == "planner":
            return json.dumps(SPEC, ensure_ascii=False)
        if papel == "pesquisador":
            if "pesquisa-alfa" in prompt:
                return "RESULTADO ALFA: 3 oportunidades em Mercado Livre com evidências concretas."
            return "RESULTADO BETA: 3 oportunidades de receita recorrente (assinaturas B2B)."
        if papel == "verifier":
            if "pesquisa-beta" in prompt and not estado["beta_reprovado"]:
                estado["beta_reprovado"] = True
                return json.dumps({"aprovado": False, "motivo": "faltou evidência quantitativa"})
            return json.dumps({"aprovado": True, "motivo": "critérios atendidos"})
        if papel == "evaluator":
            # Reprova cobertura global para forçar o gate do fundador
            return json.dumps({
                "aprovado": False,
                "lacunas": ["canal beta sem evidência quantitativa de ticket médio"]
            })
        if papel == "synthesizer":
            return "SÍNTESE FINAL: Oportunidades ranqueadas por impacto com premissas explícitas."
        raise AssertionError(f"papel inesperado: {papel}")

    return roteador


def main():
    log = LogEventos(LOG_PATH, truncar=True)
    grafo = construir_grafo(ClienteStub(faz_roteador()), log, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "amostra-1"}}

    # 1ª invocação — pausa no interrupt (gate do fundador)
    resultado1 = grafo.invoke({"spec": SPEC}, config)
    assert "__interrupt__" in resultado1, "Esperava interrupt no gate de cobertura"

    interr = resultado1["__interrupt__"][0].value
    assert interr["portao"] == "cobertura"
    print(f"[gerar_log_amostra] interrupt recebido — portão: {interr['portao']}")
    print(f"  lacunas: {interr.get('lacunas', [])}")

    # 2ª invocação — resume com "prosseguir" (decisão do fundador)
    resultado2 = grafo.invoke(Command(resume="prosseguir"), config)
    assert resultado2.get("resposta_final"), "Esperava resposta_final após resume"
    assert resultado2["avaliacao"].get("prosseguir_parcial"), "Esperava prosseguir_parcial=True"
    print(f"[gerar_log_amostra] tarefa concluída → {LOG_PATH}")

    log.fechar()

    # Valida o log gerado
    linhas = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    eventos = [json.loads(l) for l in linhas]
    tipos = [e["evento"] for e in eventos]
    print(f"[gerar_log_amostra] {len(eventos)} eventos gravados:")
    for ev in eventos:
        extras = {k: v for k, v in ev.items() if k not in ("t", "evento")}
        print(f"  {ev['t']:.3f}s  {ev['evento']}  {extras}")

    # Verificações mínimas de completude
    assert "spec.recebida" in tipos
    assert "paralelo.iniciado" in tipos
    assert "portao.reprovado" in tipos   # verifier reprovou beta na 1ª tentativa
    assert "portao.aprovado" in tipos    # verifier aprovou na 2ª
    assert "escalado" in tipos           # gate de fundador ativado
    assert "decisao.fundador" in tipos   # fundador decidiu prosseguir
    assert "tarefa.concluida" in tipos
    print("[gerar_log_amostra] todas as verificações passaram.")


if __name__ == "__main__":
    main()
