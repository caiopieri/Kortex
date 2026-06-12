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
import threading
import time
from typing import Any, Callable, Optional, Protocol

# Limita chamadas simultâneas ao claude CLI para evitar burst throttle (rc=1).
# O fan-out do LangGraph pode disparar N subagentes em paralelo; sem este semáforo
# 6+ processos concorrentes retornam rc=1 imediatamente.
_SEM_CLAUDE = threading.Semaphore(2)


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


class ClienteRoteador:
    """Multi-provider: roteia papel → cliente. O grafo continua cego a modelos.

    Decisões de design (travadas):
    - `mapa`: papel → cliente barato (DeepSeek/Kimi via OpenAI-compat). Papel fora
      do mapa vai ao `padrao` (claude).
    - Regra dura de ferramentas: se `ferramentas` foi pedido e o cliente mapeado
      declara `suporta_ferramentas = False`, roteia ao `padrao` SEM tentar o barato
      (WebSearch etc. só existem no claude -p). Evento `modelo.roteado_ferramentas`.
    - Fallback de qualidade-zero: cliente mapeado devolveu None (infra esgotada)
      → tenta o `padrao` uma vez. Evento `modelo.fallback`. Falha vira evento, não crash.
    - O retry de CONTEÚDO continua no grafo (attempt→verifier); aqui só infra.
    """

    def __init__(self, padrao: "ClienteModelo", mapa: Optional[dict[str, "ClienteModelo"]] = None,
                 log: Optional[Any] = None):
        self.padrao = padrao
        self.mapa = mapa or {}
        self.log = log

    def _evento(self, tipo: str, **dados) -> None:
        if self.log is not None:
            self.log.evento(tipo, **dados)

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               timeout: int = 300) -> Optional[str]:
        cliente = self.mapa.get(papel, self.padrao)
        if cliente is not self.padrao and ferramentas and not getattr(cliente, "suporta_ferramentas", True):
            self._evento("modelo.roteado_ferramentas", papel=papel, ferramentas=ferramentas)
            cliente = self.padrao
        resposta = cliente.chamar(papel, prompt, ferramentas=ferramentas, timeout=timeout)
        if resposta is None and cliente is not self.padrao:
            self._evento("modelo.fallback", papel=papel)
            resposta = self.padrao.chamar(papel, prompt, ferramentas=ferramentas, timeout=timeout)
        return resposta


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
                with _SEM_CLAUDE:
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
