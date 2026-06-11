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
import time
from typing import Any, Callable, Optional, Protocol


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

    def __init__(self, mapa_papeis: Optional[dict[str, str]] = None,
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0):
        self.mapa_papeis = mapa_papeis or {}
        self.log = log                # LogEventos opcional: falha vira evento, não silêncio
        self.tentativas = tentativas  # retentativas para falha TRANSIENTE de infra (throttle/erro do CLI)
        self.backoff = backoff        # segundos × tentativa (linear)

    @staticmethod
    def disponivel() -> bool:
        return shutil.which("claude") is not None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               timeout: int = 300) -> Optional[str]:
        """Chama `claude -p`, retentando falhas transientes de infra.

        Distinto da retentativa do grafo (attempt→verifier, que é por CONTEÚDO
        reprovado): aqui tratamos a falha de INFRA — rc≠0, stdout vazio, timeout —
        que sob carga (burst após geração pesada concorrente) o CLI devolve em ~2s.
        Sem isto, a falha vira um None silencioso que degrada a missão inteira.
        """
        cmd = ["claude", "-p", prompt]
        if ferramentas:
            cmd += ["--allowedTools", ferramentas, "--max-turns", "6"]
        motivo = "?"
        for tentativa in range(1, self.tentativas + 1):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=timeout, stdin=subprocess.DEVNULL)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
                motivo = f"rc={r.returncode} stderr={r.stderr.strip()[:200]!r}"
            except Exception as ex:
                motivo = f"exceção: {type(ex).__name__}: {ex}"
            if self.log is not None:
                self.log.evento("modelo.falha", papel=papel, tentativa=tentativa, motivo=motivo)
            if tentativa < self.tentativas:
                time.sleep(self.backoff * tentativa)
        return None
