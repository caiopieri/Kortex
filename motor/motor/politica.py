"""Política de gates — quanto o motor pausa pra decisão humana (Corte C).

Cada gate (ex.: "cobertura") pode ser:
  - manual     → o motor PAUSA (interrupt) e espera a decisão (caixa do fundador);
  - automático → o motor resolve sozinho com uma decisão e SEGUE, sem pausar.

`auto_mode` automatiza apenas gates conhecidos e não sensíveis. `overrides` crava
a exceção por gate, com precedência sobre o master:
  - {"cobertura": "manual"}     → ESSE gate fica manual mesmo com auto_mode ligado;
  - {"cobertura": "prosseguir"} → automatiza SÓ esse, mesmo com auto_mode desligado.

Gates sensíveis ignoram ambos. Política ausente = tudo manual.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Decisão automática default por gate quando auto_mode liga e não há override.
# "prosseguir" (nunca "abortar"): auto = "não me interrompa", não "mate a missão".
AUTO_DEFAULT: dict[str, str] = {"plano": "prosseguir", "cobertura": "prosseguir"}
DECISOES_POR_GATE: dict[str, frozenset[str]] = {
    "plano": frozenset({"prosseguir", "abortar"}),
    "cobertura": frozenset({"prosseguir", "preencher", "abortar"}),
    "promocao": frozenset({"aprovar", "rejeitar"}),
    "autorizacao": frozenset({"aprovar", "negar"}),
    "risco": frozenset({"aceitar", "rejeitar"}),
    "dinheiro": frozenset({"aprovar", "negar"}),
}
GATES_SENSIVEIS = frozenset({"promocao", "autorizacao", "risco", "dinheiro"})


@dataclass
class PoliticaGates:
    auto_mode: bool = False
    overrides: dict[str, str] = field(default_factory=dict)  # gate_id → "manual" | "<decisão>"

    def __post_init__(self) -> None:
        if type(self.auto_mode) is not bool:
            raise TypeError("auto_mode exige booleano")
        if not isinstance(self.overrides, dict):
            raise TypeError("overrides exige mapa")
        for gate_id, decisao in self.overrides.items():
            if not isinstance(gate_id, str) or not isinstance(decisao, str):
                raise TypeError("override exige gate e decisao string")
            permitidas = DECISOES_POR_GATE.get(gate_id)
            if permitidas is None or (decisao != "manual" and decisao not in permitidas):
                raise ValueError(f"decisao invalida para gate '{gate_id}'")

    def decisao_auto(self, gate_id: str, default: Optional[str] = None) -> Optional[str]:
        """Decisão automática para o gate, ou None se ele for manual (→ interrupt).

        Precedência: override do gate > auto_mode global > manual (None).
        `default` é a decisão automática deste gate (senão usa AUTO_DEFAULT).
        """
        if gate_id in GATES_SENSIVEIS:
            return None
        permitidas = DECISOES_POR_GATE.get(gate_id)
        if permitidas is None:
            return None
        modo = self.overrides.get(gate_id)
        if modo is not None:
            if modo == "manual":
                return None
            if modo not in permitidas:
                raise ValueError(f"decisao invalida para gate '{gate_id}'")
            return modo
        if self.auto_mode:
            decisao = default if default is not None else AUTO_DEFAULT.get(gate_id)
            if decisao is None:
                return None
            if decisao not in permitidas:
                raise ValueError(f"decisao default invalida para gate '{gate_id}'")
            return decisao
        return None


def politica_de_config(cfg: Optional[dict]) -> PoliticaGates:
    """Lê {"auto_mode": bool, "gates": {gate: "manual"|"<decisão>"}}.
    Ausente/None → política toda-manual."""
    if cfg is None:
        return PoliticaGates()
    if not isinstance(cfg, dict):
        raise TypeError("politica_gates exige objeto")
    auto_mode = cfg.get("auto_mode", False)
    gates = cfg.get("gates", {})
    if type(auto_mode) is not bool:
        raise TypeError("auto_mode exige booleano")
    if not isinstance(gates, dict):
        raise TypeError("gates exige mapa")
    return PoliticaGates(
        auto_mode=auto_mode,
        overrides=dict(gates),
    )
