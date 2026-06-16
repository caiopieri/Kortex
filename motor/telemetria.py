"""Resumo de telemetria a partir do log JSONL do motor.

Este módulo só agrega eventos já emitidos. Custo em tokens/$ exige evento próprio
de uso de modelo e fica para outro corte.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def carregar(log_path: str | Path) -> list[dict]:
    """Carrega eventos de um log JSONL, reaproveitando o parser do painel quando existe."""
    try:
        from motor_painel.painel import parse_eventos

        return parse_eventos(log_path)
    except ImportError:
        path = Path(log_path)
        if not path.exists():
            return []
        eventos = []
        with open(path, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    eventos.append(json.loads(linha))
        return eventos


def resumir(eventos: list[dict]) -> dict:
    """Resume contadores operacionais do motor a partir de eventos parseados."""
    resumo: dict[str, Any] = {
        "missao": None,
        "subagentes": 0,
        "chamadas_por_papel": {},
        "reprovacoes_verifier": 0,
        "reroteamentos": {"esgotado": 0, "juiz": 0, "ferramentas": 0},
        "gates": {"auto": 0, "manual": 0},
        "falhas_modelo": 0,
        "concluida": False,
    }

    for ev in eventos:
        tipo = ev.get("evento")

        if tipo in ("spec.criada", "spec.recebida"):
            resumo["missao"] = ev.get("missao")
            resumo["subagentes"] = int(ev.get("subagentes") or 0)
        elif tipo == "executor.chamado":
            papel = ev.get("papel")
            if papel:
                chamadas = resumo["chamadas_por_papel"]
                chamadas[papel] = chamadas.get(papel, 0) + 1
        elif tipo == "portao.reprovado" and str(ev.get("portao", "")).startswith("verifier:"):
            resumo["reprovacoes_verifier"] += 1
        elif tipo == "modelo.reroteado_esgotado":
            resumo["reroteamentos"]["esgotado"] += 1
        elif tipo == "juiz.independencia":
            resumo["reroteamentos"]["juiz"] += 1
        elif tipo == "modelo.roteado_ferramentas":
            resumo["reroteamentos"]["ferramentas"] += 1
        elif tipo == "gate.auto":
            resumo["gates"]["auto"] += 1
        elif tipo == "escalado":
            resumo["gates"]["manual"] += 1
        elif tipo == "modelo.falha":
            resumo["falhas_modelo"] += 1
        elif tipo == "tarefa.concluida":
            resumo["concluida"] = True

    return resumo


def _formatar_valor(valor: Any) -> str:
    if isinstance(valor, dict):
        return json.dumps(valor, ensure_ascii=False, indent=2)
    return str(valor)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("uso: python3 -m motor.telemetria <caminho/log.jsonl>", file=sys.stderr)
        return 2

    resumo = resumir(carregar(args[0]))
    for chave, valor in resumo.items():
        print(f"{chave}: {_formatar_valor(valor)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
