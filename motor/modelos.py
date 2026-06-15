"""Cliente de modelo — a fronteira anti-lock-in.

`chamar(papel, prompt) -> str | None`. O grafo só conhece PAPÉIS
(planner, verifier, evaluator, synthesizer, e os papéis dos subagentes);
qual modelo/provedor atende cada papel é config deste módulo.
Hoje: claude -p (assinatura do Caio). Amanhã: OpenRouter/NVIDIA por papel.
Falha vira None — quem chama decide o fallback (lei: falha vira evento, não crash).
"""
from __future__ import annotations

import json
import os
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

# Mesmo motivo para o codex CLI: o fan-out pode disparar N execuções agênticas
# em paralelo; limitar a concorrência evita throttle/erro de burst do CLI.
_SEM_CODEX = threading.Semaphore(2)

# Idem para o opencode CLI.
_SEM_OPENCODE = threading.Semaphore(2)


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
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]: ...


class ClienteStub:
    """Determinístico para testes: roteador(papel, prompt) -> str | None."""

    def __init__(self, roteador: Callable[[str, str], Optional[str]]):
        self.roteador = roteador
        self.chamadas: list[tuple[str, str]] = []

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]:
        self.chamadas.append((papel, prompt))
        return self.roteador(papel, prompt)


class ClienteRoteador:
    """Multi-provider: roteia papel → cliente. O grafo continua cego a modelos.

    Decisões de design (travadas):
    - Resolução do cliente, em ordem: (1) `tier` da tarefa, se presente e na tabela
      `tiers` — é o roteamento por custo (o planner classifica, a tabela mapeia
      tier→modelo); (2) senão, `mapa` por papel (rota legada); (3) senão, `padrao`.
      Tier presente mas fora da tabela → cai pro papel/padrão (seguro). Evento
      `modelo.roteado_tier`.
    - `mapa`: papel → cliente (DeepSeek/Kimi via OpenAI-compat ou Codex). Papel fora
      do mapa (e sem tier) vai ao `padrao` (claude).
    - Regra dura de ferramentas: se `ferramentas` foi pedido e o cliente resolvido
      declara `suporta_ferramentas = False`, roteia ao `padrao` SEM tentar o barato
      (WebSearch etc.). Evento `modelo.roteado_ferramentas`.
    - Fallback de qualidade-zero: cliente resolvido devolveu None (infra esgotada)
      → tenta o `padrao` uma vez. Evento `modelo.fallback`. Falha vira evento, não crash.
    - O retry de CONTEÚDO continua no grafo (attempt→verifier); aqui só infra.
    """

    def __init__(self, padrao: "ClienteModelo", mapa: Optional[dict[str, "ClienteModelo"]] = None,
                 tiers: Optional[dict[str, "ClienteModelo"]] = None,
                 esgotados: Optional[set[str]] = None,
                 cadeia: Optional[list["ClienteModelo"]] = None,
                 pins: Optional[dict[str, "ClienteModelo"]] = None,
                 log: Optional[Any] = None):
        self.padrao = padrao
        self.mapa = mapa or {}
        self.tiers = tiers or {}   # tier → cliente (roteamento por custo)
        # Pins MANUAIS (decisão do Caio, "não me questiona"): chave papel|tier|"*"
        # → cliente. Precedência MÁXIMA, acima do tier e do papel — o planner não
        # sobrepõe. "*" = vale pra tudo (o "esse no todo"). Evento modelo.pin.
        self.pins = pins or {}
        # Corte B — disponibilidade global: `esgotados` é o conjunto de provedores
        # indisponíveis (ex.: {"claude"} quando o limite acaba). MUTÁVEL de propósito:
        # o Corte C (UI/arquivo) liga/desliga ao vivo. `cadeia` = ordem de fallback
        # de clientes quando o provedor resolvido está esgotado.
        self.esgotados = set(esgotados or ())
        self.cadeia = list(cadeia or ())
        self.log = log

    def _evento(self, tipo: str, **dados) -> None:
        if self.log is not None:
            self.log.evento(tipo, **dados)

    def _disponivel(self, cliente: "ClienteModelo", papel: Optional[str] = None) -> "ClienteModelo":
        """Se o provedor do `cliente` está esgotado, reroteia pro 1º da cadeia (+ padrao)
        que não esteja esgotado. Tudo esgotado → devolve o original (deixa falhar e
        virar evento — nunca trava esperando um provedor que acabou)."""
        if not self.esgotados or getattr(cliente, "provedor", None) not in self.esgotados:
            return cliente
        for alt in [*self.cadeia, self.padrao]:
            if getattr(alt, "provedor", None) not in self.esgotados:
                self._evento("modelo.reroteado_esgotado", papel=papel,
                             de=getattr(cliente, "provedor", None),
                             para=getattr(alt, "provedor", None))
                return alt
        return cliente

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]:
        cliente: "ClienteModelo"
        pin = self.pins.get(papel) or (self.pins.get(tier) if tier else None) or self.pins.get("*")
        if pin is not None:                          # pin manual vence tier e papel
            cliente = pin
            self._evento("modelo.pin", papel=papel, tier=tier)
        elif tier and tier in self.tiers:
            cliente = self.tiers[tier]
            self._evento("modelo.roteado_tier", papel=papel, tier=tier)
        else:
            cliente = self.mapa.get(papel, self.padrao)
        cliente = self._disponivel(cliente, papel)   # provedor esgotado → reroteia
        if cliente is not self.padrao and ferramentas and not getattr(cliente, "suporta_ferramentas", True):
            self._evento("modelo.roteado_ferramentas", papel=papel, ferramentas=ferramentas)
            cliente = self._disponivel(self.padrao, papel)
        resposta = cliente.chamar(papel, prompt, ferramentas=ferramentas, tier=tier, timeout=timeout)
        if resposta is None and cliente is not self.padrao:
            alvo = self._disponivel(self.padrao, papel)
            if alvo is not cliente:
                self._evento("modelo.fallback", papel=papel)
                resposta = alvo.chamar(papel, prompt, ferramentas=ferramentas, tier=tier, timeout=timeout)
        return resposta


class ClienteClaudeCLI:
    """Backend real via `claude -p` (Claude Code do Mac do Caio).

    `papel` hoje não muda o modelo (uma assinatura), mas mantém o contrato:
    quando houver multi-provider, o roteamento por papel entra AQUI, sem tocar o grafo.
    """

    def __init__(self, mapa_papeis: Optional[dict[str, str]] = None,
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0):
        self.mapa_papeis = mapa_papeis or {}
        self.provedor = "claude"      # rótulo p/ o roteador marcar esgotamento (Corte B)
        self.log = log                # LogEventos opcional: falha vira evento, não silêncio
        self.tentativas = tentativas  # retentativas para falha TRANSIENTE de infra (throttle/erro do CLI)
        self.backoff = backoff        # segundos × tentativa (linear)

    @staticmethod
    def disponivel() -> bool:
        return shutil.which("claude") is not None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]:
        """Chama `claude -p`, retentando falhas transientes de infra.

        `tier` é ignorado aqui (sinal de roteamento consumido pelo ClienteRoteador);
        faz parte do contrato uniforme do Protocol.

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


class ClienteCodex:
    """Backend real via `codex exec` (Codex CLI da OpenAI, assinatura ChatGPT do Caio).

    Papel deste cliente no motor: **EXECUTOR** (alto volume). O julgamento
    (planner/verifier/evaluator/synthesizer) fica no claude — separação
    cross-model que combate viés de auto-preferência (lei do harness). O
    `ClienteRoteador` decide o mapa papel→cliente; aqui só o transporte.

    `codex exec` roda uma sessão até o fim sem TUI, streama o progresso pro
    stderr e imprime **só a mensagem final do agente no stdout** — daí o mesmo
    contrato de subprocess do ClienteClaudeCLI. Flags fixas:
      - sandbox read-only (default): os nós do motor são texto-entra/texto-sai;
        o executor devolve o artefato como TEXTO, não edita o repo aqui.
      - `--skip-git-repo-check`: o motor pode rodar fora de um repo git.
      - `--ephemeral`: não acumula arquivos de rollout em disco.

    Auth: reusa o login salvo do CLI (`codex login`) — a assinatura do Caio,
    sem chave de API no arquivo (mesma fronteira do claude -p).
    """

    # Codex É agêntico (web search, leitura de arquivos, MCP). Ao contrário dos
    # clientes HTTP baratos, ELE atende papéis com ferramentas — não desvia ao
    # claude. WebSearch do papel → `--search` (busca ao vivo).
    suporta_ferramentas = True

    def __init__(self, modelo: Optional[str] = None,
                 mapa_papeis: Optional[dict[str, str]] = None,
                 sandbox: str = "read-only", busca_ao_vivo: bool = False,
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0):
        self.modelo = modelo            # None/"default" → usa o modelo padrão do codex
        self.mapa_papeis = mapa_papeis or {}
        self.provedor = "codex"         # rótulo p/ esgotamento (Corte B)
        # read-only por default: os nós do motor são texto-entra/texto-sai; o
        # executor devolve artefato como TEXTO. Quem precisar que o Codex EDITE
        # o repo (executor de código) seta sandbox="workspace-write" na config.
        self.sandbox = sandbox
        self.busca_ao_vivo = busca_ao_vivo  # True → sempre --search (mesmo sem ferramenta pedida)
        self.log = log
        self.tentativas = tentativas
        self.backoff = backoff

    @staticmethod
    def disponivel() -> bool:
        return shutil.which("codex") is not None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]:
        """Chama `codex exec`, retentando falhas transientes de infra. `tier` é
        ignorado aqui (roteamento é do ClienteRoteador); parte do contrato uniforme.

        Regras (espelham o contrato dos outros clientes):

        1. **Ferramentas**: papel que pede ferramenta (ex.: WebSearch) → adiciona
           ``--search`` (browsing ao vivo). Codex usa as próprias ferramentas
           agênticas dentro do sandbox — não há desvio ao claude.
        2. Modelo = ``mapa_papeis.get(papel, self.modelo)``; só vira ``-m <id>``
           se não for vazio/"default" (senão usa o padrão do codex login).
        3. ``codex exec`` imprime só a mensagem final no stdout → ``.strip()``.
        4. Falha transiente (rc≠0, stdout vazio, timeout, exceção) → evento
           ``modelo.falha`` no log e retry linear (``backoff × tentativa``).
        5. Esgotou → ``None``. Falha vira evento, não crash.
        """
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral",
               "--sandbox", self.sandbox]
        modelo = self.mapa_papeis.get(papel, self.modelo)
        if modelo and modelo != "default":
            cmd += ["-m", modelo]
        if ferramentas or self.busca_ao_vivo:
            cmd.append("--search")
        cmd.append(prompt)
        motivo = "?"
        for tentativa in range(1, self.tentativas + 1):
            try:
                with _SEM_CODEX:
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


class ClienteOpenCode:
    """Backend real via `opencode run` (CLI open source da SST, model-agnostic).

    Papel no motor: EXECUTOR pros OUTROS modelos — qualquer provider/model que o
    opencode suporta (openai/gpt-5.5, anthropic/..., openrouter/..., local...).
    Útil quando o Caio NÃO está pagando o Codex mas quer GPT-5.5 pago por token,
    ou pra rodar modelos que nem Codex nem claude expõem.

    `opencode run "prompt"` roda não-interativo, imprime a resposta no stdout e sai;
    `-m provider/model` escolhe o modelo (daí o "modelo" aqui é "provider/model",
    não só o id). Auth: `opencode auth login` (creds próprias), SEM chave no nosso
    arquivo — mesma fronteira do claude/codex.

    Segurança: em `run`, o opencode AUTO-APROVA as permissões da sessão. Como os nós
    do motor são texto-entra/texto-sai, dá pra travar via `permissao` (vira a env
    OPENCODE_PERMISSION, ex.: '{"edit":"deny","bash":"deny"}'); ausente = default do
    opencode. Configurável no provedor.
    """

    suporta_ferramentas = True  # opencode é agêntico (igual ao Codex)

    def __init__(self, modelo: Optional[str] = None,
                 mapa_papeis: Optional[dict[str, str]] = None,
                 permissao: Optional[str] = None,
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0,
                 provedor: str = "opencode"):
        self.modelo = modelo            # "provider/model" (ou None/"default")
        self.mapa_papeis = mapa_papeis or {}
        self.permissao = permissao      # JSON p/ OPENCODE_PERMISSION (opcional)
        self.provedor = provedor        # rótulo p/ esgotamento (Corte B)
        self.log = log
        self.tentativas = tentativas
        self.backoff = backoff

    @staticmethod
    def disponivel() -> bool:
        return shutil.which("opencode") is not None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]:
        """Chama `opencode run`, retentando falhas transientes de infra.
        `ferramentas`/`tier` não viram flag aqui (o roteador já decidiu o modelo)."""
        cmd = ["opencode", "run"]
        modelo = self.mapa_papeis.get(papel, self.modelo)
        if modelo and modelo != "default":
            cmd += ["-m", modelo]
        cmd.append(prompt)
        env = os.environ.copy()
        if self.permissao:
            env["OPENCODE_PERMISSION"] = self.permissao
        motivo = "?"
        for tentativa in range(1, self.tentativas + 1):
            try:
                with _SEM_OPENCODE:
                    r = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=timeout, stdin=subprocess.DEVNULL, env=env)
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
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0,
                 provedor: str = "openai-compat"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.modelo = modelo
        self.mapa_papeis = mapa_papeis or {}
        self.provedor = provedor      # rótulo p/ esgotamento (Corte B); cliente_de_config seta o nome real
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
               tier: Optional[str] = None, timeout: int = 300) -> Optional[str]:
        """Chama o endpoint OpenAI-compatível com retry linear de infra. `tier` é
        ignorado aqui (roteamento é do ClienteRoteador); parte do contrato uniforme.

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

    Um provedor pode declarar ``"tipo": "codex"`` — cliente CLI (`codex exec`,
    assinatura ChatGPT, SEM chave de API). Usado para por o Codex como EXECUTOR:
      {"provedores": {"codex": {"tipo": "codex", "sandbox": "read-only", "search": false}},
       "papeis": {"pesquisador": "codex/default"}}
    O modelo após a barra vira ``-m`` (ou "default" = padrão do codex login).
    ``sandbox`` (default "read-only"; "workspace-write" deixa o Codex editar o
    repo) e ``search`` (default false = web search cached; true = ao vivo) são
    opcionais. Codex atende papéis com ferramentas (não desvia ao claude).
    O padrão dos provedores é "openai-compat" (HTTP, exige api_key_env).

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
        def _cliente_destino(destino: str, quem: str):
            """Constrói UM cliente para 'provedor/modelo' (ou 'padrao')."""
            if destino == "padrao":
                return padrao
            prov, sep, modelo = destino.partition("/")
            if not sep or not modelo or prov not in cfg["provedores"]:
                raise ValueError(
                    f"{quem}: destino {destino!r} deve ser 'provedor/modelo' (ou 'padrao'); "
                    f"provedores declarados: {list(cfg['provedores'])}")
            p = cfg["provedores"][prov]
            tipo = p.get("tipo", "openai-compat")
            if tipo == "codex":
                return ClienteCodex(modelo=modelo, sandbox=p.get("sandbox", "read-only"),
                                    busca_ao_vivo=p.get("search", False), log=log)
            if tipo == "opencode":
                return ClienteOpenCode(modelo=modelo, permissao=p.get("permissao"),
                                       log=log, provedor=prov)
            if tipo == "openai-compat":
                return ClienteOpenAICompat(
                    base_url=p["base_url"], api_key=_chave(p["api_key_env"], f"provedor {prov!r}"),
                    modelo=modelo, log=log, provedor=prov)
            raise ValueError(
                f"provedor {prov!r}: tipo {tipo!r} desconhecido "
                f"(use 'codex', 'opencode' ou 'openai-compat')")

        # Rota legada papel→modelo: um cliente por provedor, compartilhado, com mapa_papeis.
        por_prov: dict[str, dict[str, str]] = {}  # provedor -> {papel: modelo}
        for papel, destino in cfg.get("papeis", {}).items():
            prov, sep, modelo = destino.partition("/")
            if not sep or not modelo or prov not in cfg["provedores"]:
                raise ValueError(
                    f"papel {papel!r}: destino {destino!r} deve ser 'provedor/modelo' "
                    f"com provedor declarado em 'provedores' ({list(cfg['provedores'])})")
            por_prov.setdefault(prov, {})[papel] = modelo
        mapa: dict[str, Any] = {}
        for prov, papeis in por_prov.items():
            p = cfg["provedores"][prov]
            tipo = p.get("tipo", "openai-compat")
            if tipo == "codex":
                cliente: Any = ClienteCodex(
                    mapa_papeis=papeis, sandbox=p.get("sandbox", "read-only"),
                    busca_ao_vivo=p.get("search", False), log=log)
            elif tipo == "opencode":
                cliente = ClienteOpenCode(mapa_papeis=papeis, permissao=p.get("permissao"),
                                          log=log, provedor=prov)
            elif tipo == "openai-compat":
                cliente = ClienteOpenAICompat(
                    base_url=p["base_url"], api_key=_chave(p["api_key_env"], f"provedor {prov!r}"),
                    modelo=next(iter(papeis.values())), mapa_papeis=papeis, log=log, provedor=prov)
            else:
                raise ValueError(
                    f"provedor {prov!r}: tipo {tipo!r} desconhecido "
                    f"(use 'codex', 'opencode' ou 'openai-compat')")
            for papel in papeis:
                mapa[papel] = cliente

        # Roteamento por custo: tier→modelo. "padrao" referencia o claude.
        tiers_map: dict[str, Any] = {
            tier: _cliente_destino(destino, f"tier {tier!r}")
            for tier, destino in cfg.get("tiers", {}).items()
        }
        # Pins manuais: chave (papel|tier|"*") → modelo, precedência máxima.
        pins_map: dict[str, Any] = {
            chave: _cliente_destino(destino, f"pin {chave!r}")
            for chave, destino in cfg.get("pins", {}).items()
        }
        # Cadeia de fallback p/ esgotamento (Corte B): clientes distintos (não-padrao),
        # em ordem estável. O padrao (claude) é o último recurso, tratado no roteador.
        cadeia: list[Any] = []
        for c in [*pins_map.values(), *tiers_map.values(), *mapa.values()]:
            if c is not padrao and not any(c is x for x in cadeia):
                cadeia.append(c)
        return ClienteRoteador(padrao=padrao, mapa=mapa, tiers=tiers_map, pins=pins_map,
                               esgotados=set(cfg.get("esgotados", [])), cadeia=cadeia, log=log)

    # formato v1 — um provedor
    barato = ClienteOpenAICompat(
        base_url=cfg["base_url"], api_key=_chave(cfg["api_key_env"], "provedor único"),
        modelo=cfg["modelo"], mapa_papeis=cfg.get("mapa_papeis_modelo"), log=log,
        provedor=cfg.get("provedor", "openai-compat"))
    return ClienteRoteador(padrao=padrao,
                           mapa={p: barato for p in cfg.get("papeis_baratos", [])},
                           esgotados=set(cfg.get("esgotados", [])), cadeia=[barato], log=log)
