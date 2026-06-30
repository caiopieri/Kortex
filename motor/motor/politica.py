"""Política de gates — quanto o motor pausa pra decisão humana (Corte C).

Cada gate (ex.: "cobertura") pode ser:
  - manual     → o motor PAUSA (interrupt) e espera a decisão (caixa do fundador);
  - automático → o motor resolve sozinho com uma decisão e SEGUE, sem pausar.

`auto_mode` é o master switch: ligado = tudo automático. `overrides` crava a
exceção por gate, com precedência sobre o master:
  - {"cobertura": "manual"}     → ESSE gate fica manual mesmo com auto_mode ligado;
  - {"cobertura": "prosseguir"} → automatiza SÓ esse, mesmo com auto_mode desligado.

Assim "auto-mode ligado = literalmente tudo auto", mas dá pra abrir exceções nos
dois sentidos. Política ausente = tudo manual (comportamento default do motor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Decisão automática default por gate quando auto_mode liga e não há override.
# "prosseguir" (nunca "abortar"): auto = "não me interrompa", não "mate a missão".
AUTO_DEFAULT: dict[str, str] = {"cobertura": "prosseguir"}


@dataclass
class PoliticaGates:
    auto_mode: bool = False
    overrides: dict[str, str] = field(default_factory=dict)  # gate_id → "manual" | "<decisão>"

    def decisao_auto(self, gate_id: str, default: Optional[str] = None) -> Optional[str]:
        """Decisão automática para o gate, ou None se ele for manual (→ interrupt).

        Precedência: override do gate > auto_mode global > manual (None).
        `default` é a decisão automática deste gate (senão usa AUTO_DEFAULT).
        """
        modo = self.overrides.get(gate_id)
        if modo is not None:
            return None if modo == "manual" else modo
        if self.auto_mode:
            return default or AUTO_DEFAULT.get(gate_id, "prosseguir")
        return None


def politica_de_config(cfg: Optional[dict]) -> PoliticaGates:
    """Lê {"auto_mode": bool, "gates": {gate: "manual"|"<decisão>"}}.
    Ausente/None → política toda-manual."""
    cfg = cfg or {}
    return PoliticaGates(
        auto_mode=bool(cfg.get("auto_mode", False)),
        overrides=dict(cfg.get("gates", {})),
    )
