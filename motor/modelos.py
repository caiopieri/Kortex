"""Cliente de modelo — a fronteira anti-lock-in.

`chamar(papel, prompt) -> str | None`. O grafo só conhece PAPÉIS
(planner, verifier, evaluator, synthesizer, e os papéis dos subagentes);
qual modelo/provedor atende cada papel é config deste módulo.
Hoje: claude -p (assinatura do Caio). Amanhã: OpenRouter/NVIDIA por papel.
Falha vira None — quem chama decide o fallback (lei: falha vira evento, não crash).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Callable, Optional, Protocol


def extrai_json(texto: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class ClienteModelo(Protocol):
    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               timeout: int = 300) -> Optional[str]: ...


class ClienteStub:
    """Determinístico para testes: roteador(papel, prompt) -> str | None."""

    def __init__(self, roteador: Callable[[str, str], Optional[str]]):
        self.roteador = roteador
        self.chamadas: list[tuple[str, str]] = []

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               timeout: int = 300) -> Optional[str]:
        self.chamadas.append((papel, prompt))
        return self.roteador(papel, prompt)


class ClienteClaudeCLI:
    """Backend real via `claude -p` (Claude Code do Mac do Caio).

    `papel` hoje não muda o modelo (uma assinatura), mas mantém o contrato:
    quando houver multi-provider, o roteamento por papel entra AQUI, sem tocar o grafo.
    """

    def __init__(self, mapa_papeis: Optional[dict[str, str]] = None):
        self.mapa_papeis = mapa_papeis or {}

    @staticmethod
    def disponivel() -> bool:
        return shutil.which("claude") is not None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               timeout: int = 300) -> Optional[str]:
        cmd = ["claude", "-p", prompt]
        if ferramentas:
            cmd += ["--allowedTools", ferramentas, "--max-turns", "6"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL)
            if r.returncode != 0 or not r.stdout.strip():
                return None
            return r.stdout.strip()
        except Exception:
            return None
