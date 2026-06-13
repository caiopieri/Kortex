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
import urllib.request
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


class ClienteOpenAICompat:
    """Transporte HTTP OpenAI-compatível (NVIDIA/DeepSeek/Kimi) para papéis baratos.

    Esta classe é só o transporte — não decide roteamento, não interpreta
    respostas além de extrair ``choices[0].message.content``.
    O ``ClienteRoteador`` decide quem atende cada papel; aqui só se codifica
    o contrato HTTP + retry linear de infra.

    Atributo de classe:
      ``suporta_ferramentas = False`` — o roteador lê isto para desviar
      papéis que pedem ferramentas (WebSearch etc.) ao cliente padrão.
    """

    suporta_ferramentas = False

    def __init__(self, base_url: str, api_key: str, modelo: str,
                 mapa_papeis: Optional[dict[str, str]] = None,
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.modelo = modelo
        self.mapa_papeis = mapa_papeis or {}
        self.log = log
        self.tentativas = tentativas
        self.backoff = backoff

    def _post(self, payload: dict, timeout: int) -> dict:
        """POST {base_url}/chat/completions — stdlib urllib, sem dependências.

        Exceções de rede/HTTP sobem para ``chamar()`` tratar como falha
        transiente (retry + evento ``modelo.falha``).
        """
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               timeout: int = 300) -> Optional[str]:
        """Chama o endpoint OpenAI-compatível com retry linear de infra.

        Regras (contrato T5 — os testes são o DoD):

        1. **Ferramentas pedidas → None imediato** (sem chamar ``_post``).
           Clientes baratos não suportam tool-use; o roteador desvia ao padrão.
        2. Monta payload: ``model`` = ``mapa_papeis.get(papel, modelo)``,
           ``messages`` = único turno user com o prompt.
        3. Extrai ``choices[0].message.content`` e aplica ``.strip()``.
        4. Falha transiente (exceção do ``_post``, JSON sem o campo,
           conteúdo vazio) → evento ``modelo.falha`` no log e retry,
           até ``tentativas`` vezes, sleep ``backoff × tentativa`` (linear).
        5. Esgotou → ``None``. Falha vira evento, não crash.
        """
        if ferramentas:
            return None
        payload: dict[str, Any] = {
            "model": self.mapa_papeis.get(papel, self.modelo),
            "messages": [{"role": "user", "content": prompt}],
        }
        motivo = "?"
        for tentativa in range(1, self.tentativas + 1):
            try:
                resp = self._post(payload, timeout)
                conteudo = resp["choices"][0]["message"]["content"].strip()
                if conteudo:
                    return conteudo
                motivo = "conteúdo vazio"
            except Exception as ex:
                motivo = f"{type(ex).__name__}: {ex}"
            if self.log is not None:
                self.log.evento("modelo.falha", papel=papel, tentativa=tentativa, motivo=motivo)
            if tentativa < self.tentativas:
                time.sleep(self.backoff * tentativa)
        return None


def cliente_de_config(cfg: dict, log: Optional[Any] = None) -> "ClienteModelo":
    """Monta o cliente do motor a partir de config JSON — zero segredo no arquivo.

    Formato multi-plataforma (ver exemplos/modelos-multi.json) — N provedores
    OpenAI-compat (NVIDIA, OpenRouter, OpenAI, Together, Groq...):

      {"provedores": {
         "nvidia":     {"base_url": "https://integrate.api.nvidia.com/v1",
                        "api_key_env": "NVIDIA_API_KEY"},
         "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                        "api_key_env": "OPENROUTER_API_KEY"}},
       "papeis": {
         "redator":     "nvidia/deepseek-ai/deepseek-v4",
         "synthesizer": "openrouter/moonshotai/kimi-k2.6"}}

    Cada papel aponta para "provedor/modelo" (o 1º '/' separa; o resto é o id
    do modelo na plataforma). Só provedores USADOS exigem chave no ambiente.

    Formato v1 (um provedor; exemplos/modelos-nvidia.json) continua aceito:
      {"base_url", "api_key_env", "modelo", "mapa_papeis_modelo"?, "papeis_baratos"}

    Em ambos: planner/verifier/evaluator ficam no padrão (claude) a menos que
    listados explicitamente — rebaixar julgamento é decisão consciente, nunca
    default. Papéis com ferramentas são desviados ao padrão pelo ClienteRoteador.
    """
    import os

    def _chave(env: str, quem: str) -> str:
        chave = os.environ.get(env, "")
        if not chave:
            raise ValueError(
                f"env var {env!r} vazia ({quem}) — exporte a chave; ela nunca vai no arquivo")
        return chave

    padrao = ClienteClaudeCLI(log=log)

    if "provedores" in cfg:  # formato multi-plataforma
        por_prov: dict[str, dict[str, str]] = {}  # provedor -> {papel: modelo}
        for papel, destino in cfg["papeis"].items():
            prov, sep, modelo = destino.partition("/")
            if not sep or not modelo or prov not in cfg["provedores"]:
                raise ValueError(
                    f"papel {papel!r}: destino {destino!r} deve ser 'provedor/modelo' "
                    f"com provedor declarado em 'provedores' ({list(cfg['provedores'])})")
            por_prov.setdefault(prov, {})[papel] = modelo
        mapa: dict[str, Any] = {}
        for prov, papeis in por_prov.items():
            p = cfg["provedores"][prov]
            cliente = ClienteOpenAICompat(
                base_url=p["base_url"], api_key=_chave(p["api_key_env"], f"provedor {prov!r}"),
                modelo=next(iter(papeis.values())), mapa_papeis=papeis, log=log)
            for papel in papeis:
                mapa[papel] = cliente
        return ClienteRoteador(padrao=padrao, mapa=mapa, log=log)

    # formato v1 — um provedor
    barato = ClienteOpenAICompat(
        base_url=cfg["base_url"], api_key=_chave(cfg["api_key_env"], "provedor único"),
        modelo=cfg["modelo"], mapa_papeis=cfg.get("mapa_papeis_modelo"), log=log)
    return ClienteRoteador(padrao=padrao,
                           mapa={p: barato for p in cfg.get("papeis_baratos", [])}, log=log)
