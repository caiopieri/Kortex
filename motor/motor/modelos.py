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
from typing import Any, Callable, Optional, Protocol, cast

# Limita chamadas simultâneas ao claude CLI para evitar burst throttle (rc=1).
# O fan-out do LangGraph pode disparar N subagentes em paralelo; sem este semáforo
# 6+ processos concorrentes retornam rc=1 imediatamente.
_SEM_CLAUDE = threading.Semaphore(2)

# Mesmo motivo para o codex CLI: o fan-out pode disparar N execuções agênticas
# em paralelo; limitar a concorrência evita throttle/erro de burst do CLI.
_SEM_CODEX = threading.Semaphore(2)

# Idem para o opencode CLI.
_SEM_OPENCODE = threading.Semaphore(2)


class ProvedorIndisponivel(RuntimeError):
    """Nenhum provedor de modelo utilizável (ex.: `claude` CLI fora do PATH e sem config)."""


def extrai_json(texto: str) -> Optional[dict]:
    if not texto:
        return None
    s = texto.strip()
    # 1) tira cercas de código markdown (```json ... ``` ou ``` ... ```)
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
    if fence:
        s = fence.group(1).strip()
    # 2) tenta o texto inteiro
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # 3) varre o primeiro objeto {...} BALANCEADO (respeita strings/escapes),
    #    robusto a prosa ou chaves soltas antes/depois do JSON.
    inicio = s.find("{")
    while inicio != -1:
        profundidade = 0
        em_string = False
        escape = False
        for i in range(inicio, len(s)):
            c = s[i]
            if em_string:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    em_string = False
            elif c == '"':
                em_string = True
            elif c == "{":
                profundidade += 1
            elif c == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        obj = json.loads(s[inicio:i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break  # bloco inválido → tenta o próximo '{'
        inicio = s.find("{", inicio + 1)
    return None


def _chave_provedor(cliente: Any) -> str:
    prov = getattr(cliente, "provedor", None)
    return str(prov) if prov is not None else f"__sem_provedor__:{id(cliente)}"


def _modelo_de(cliente: Any, papel: str) -> Any:
    mapa = getattr(cliente, "mapa_papeis", None)
    if isinstance(mapa, dict) and papel in mapa:
        return mapa[papel]
    return getattr(cliente, "modelo", None)


def _descricao_cliente(cliente: Any, papel: str) -> Optional[str]:
    prov = getattr(cliente, "provedor", None)
    modelo = _modelo_de(cliente, papel)
    if prov and modelo:
        return f"{prov}/{modelo}"
    return str(prov) if prov else (str(modelo) if modelo else None)


def _custo_ordem_cliente(cliente: Any) -> tuple[int, int]:
    custo = getattr(cliente, "custo_ordem", None)
    try:
        if custo is None:
            return (1, 0)
        return (0, int(custo))
    except (TypeError, ValueError):
        return (1, 0)


def _ordenar_cadeia_por_custo(clientes: list[Any]) -> list[Any]:
    vistos: set[str] = set()
    candidatos: list[tuple[tuple[int, int], int, Any]] = []
    for indice, cliente in enumerate(clientes):
        if cliente is None:
            continue
        chave = _chave_provedor(cliente)
        if chave in vistos:
            continue
        vistos.add(chave)
        candidatos.append((_custo_ordem_cliente(cliente), indice, cliente))
    candidatos.sort()
    return [cliente for _, _, cliente in candidatos]


class ClienteModelo(Protocol):
    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]: ...


class ClienteStub:
    """Determinístico para testes: roteador(papel, prompt) -> str | None."""

    roteamento_capacidades_runtime = True

    def __init__(self, roteador: Callable[[str, str], Optional[str]], sempre_none: bool = False):
        self.roteador = roteador
        self.sempre_none = sempre_none
        self.chamadas: list[tuple[str, str]] = []
        self.provedor: str | None = None
        self.modelo: str | None = None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
        self.chamadas.append((papel, prompt))
        if self.sempre_none:
            return None
        return self.roteador(papel, prompt)


class ClienteRoteador:
    """Multi-provider: roteia papel → cliente. O grafo continua cego a modelos.

    Decisões de design (travadas):
    - Sem capacidades, preserva a resolução legada pin → tier → papel → padrão.
      Quando capacidades são declaradas, todo caminho (inclusive pin, tier e
      fallback) exige uma entrada íntegra de catálogo que cubra todas elas;
      ausência ou ambiguidade falha fechada com `registro.sem_executor`.
    - `mapa`: papel → cliente (DeepSeek/Kimi via OpenAI-compat ou Codex). Papel fora
      do mapa (e sem tier) vai ao `padrao` (claude).
    - Regra dura de ferramentas: no legado, cliente sem suporte desvia ao `padrao`;
      com capacidades, só uma entrada capaz e com suporte pode ser selecionada.
    - Fallback de qualidade-zero: cliente resolvido devolveu None (infra esgotada)
      → legado tenta o `padrao`; rota por capacidade tenta apenas outro capaz.
      Evento `modelo.fallback`. Falha vira evento, não crash.
    - O retry de CONTEÚDO continua no grafo (attempt→verifier); aqui só infra.
    """

    roteamento_capacidades_runtime = True

    def __init__(self, padrao: "ClienteModelo", mapa: Optional[dict[str, "ClienteModelo"]] = None,
                 tiers: Optional[dict[str, "ClienteModelo"]] = None,
                 esgotados: Optional[set[str]] = None,
                 cadeia: Optional[list["ClienteModelo"]] = None,
                 pins: Optional[dict[str, "ClienteModelo"]] = None,
                 catalogo: Optional[list[tuple["ClienteModelo", frozenset[str], int]]] = None,
                 auto_esgotar: bool = False,
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
        self.catalogo = (list(catalogo) if isinstance(catalogo, list)
                         else ([] if catalogo is None else [catalogo]))
        self.auto_esgotar = auto_esgotar
        self.log = log

    def _evento(self, tipo: str, **dados) -> None:
        if self.log is not None:
            self.log.evento(tipo, **dados)

    def _auto_esgotar(self, cliente: "ClienteModelo", papel: str, motivo: str) -> None:
        prov = getattr(cliente, "provedor", None)
        if prov and prov not in self.esgotados:
            self.esgotados.add(prov)
            self._evento("provedor.auto_esgotado", provedor=prov, papel=papel, motivo=motivo)

    def _cadeia_failover(self) -> list["ClienteModelo"]:
        vistos: set[str] = set()
        saida: list["ClienteModelo"] = []
        for alt in [*self.cadeia, self.padrao]:
            prov = getattr(alt, "provedor", None)
            chave = _chave_provedor(alt)
            if chave in vistos or prov in self.esgotados:
                continue
            vistos.add(chave)
            saida.append(alt)
        return saida

    def _disponivel(self, cliente: "ClienteModelo", papel: Optional[str] = None,
                    emitir: bool = True) -> "ClienteModelo":
        """Se o provedor do `cliente` está esgotado, reroteia pro 1º da cadeia (+ padrao)
        que não esteja esgotado. Tudo esgotado → devolve o original (deixa falhar e
        virar evento — nunca trava esperando um provedor que acabou)."""
        if not self.esgotados or getattr(cliente, "provedor", None) not in self.esgotados:
            return cliente
        for alt in [*self.cadeia, self.padrao]:
            if getattr(alt, "provedor", None) not in self.esgotados:
                if emitir:
                    self._evento("modelo.reroteado_esgotado", papel=papel,
                                 de=getattr(cliente, "provedor", None),
                                 para=getattr(alt, "provedor", None))
                return alt
        return cliente

    def _eh_pin(self, papel: str, tier: Optional[str]) -> bool:
        return bool(self.pins.get(papel) or (self.pins.get(tier) if tier else None) or self.pins.get("*"))

    @staticmethod
    def _usa_capacidades(capacidades: Any) -> bool:
        return capacidades is not None and not (
            isinstance(capacidades, list) and not capacidades
        )

    @staticmethod
    def _normalizar_capacidades(capacidades: Any) -> frozenset[str] | None:
        if not isinstance(capacidades, list) or not capacidades:
            return None
        normalizadas: set[str] = set()
        for capacidade in capacidades:
            if not isinstance(capacidade, str):
                return None
            valor = capacidade.strip()
            if (
                not valor
                or valor != capacidade
                or len(valor) > 128
                or any(ord(c) < 32 for c in valor)
            ):
                return None
            normalizadas.add(valor)
        return frozenset(normalizadas)

    def _catalogo_validado(self) -> list[tuple["ClienteModelo", frozenset[str], int]] | None:
        catalogo: list[tuple["ClienteModelo", frozenset[str], int]] = []
        clientes: set[int] = set()
        for entrada in self.catalogo:
            if not isinstance(entrada, tuple) or len(entrada) != 3:
                return None
            cliente, capacidades, ordem = entrada
            provedor = getattr(cliente, "provedor", None)
            suporta_ferramentas = getattr(cliente, "suporta_ferramentas", True)
            if (
                not callable(getattr(cliente, "chamar", None))
                or (provedor is not None and (
                    not isinstance(provedor, str) or not provedor.strip()
                ))
                or not isinstance(suporta_ferramentas, bool)
                or not isinstance(capacidades, frozenset)
                or not capacidades
                or isinstance(ordem, bool)
                or not isinstance(ordem, int)
                or ordem < 0
                or id(cliente) in clientes
            ):
                return None
            normalizadas = self._normalizar_capacidades(list(capacidades))
            if normalizadas is None or normalizadas != capacidades:
                return None
            clientes.add(id(cliente))
            catalogo.append((cliente, capacidades, ordem))
        return catalogo or None

    def _candidatos_capazes(
        self,
        capacidades: Any,
        *,
        evitar: str | None = None,
        ferramentas: str | None = None,
        excluir: "ClienteModelo" | None = None,
    ) -> list["ClienteModelo"] | None:
        req = self._normalizar_capacidades(capacidades)
        catalogo = self._catalogo_validado()
        if req is None or catalogo is None:
            return None
        candidatos = [
            (ordem, indice, cliente)
            for indice, (cliente, declaradas, ordem) in enumerate(catalogo)
            if req <= declaradas
            and cliente is not excluir
            and getattr(cliente, "provedor", None) not in self.esgotados
            and (evitar is None or getattr(cliente, "provedor", None) != evitar)
            and (not ferramentas or getattr(cliente, "suporta_ferramentas", True))
        ]
        candidatos.sort(key=lambda item: (item[0], item[1]))
        return [cliente for _, _, cliente in candidatos]

    def selecionar_por_capacidade(self, capacidades, evitar=None, emitir: bool = True):
        """Escolhe o cliente mais barato que cobre todas as capacidades pedidas."""
        candidatos = self._candidatos_capazes(capacidades, evitar=evitar)
        return candidatos[0] if candidatos else None

    def _resolver(self, papel: str, tier: Optional[str], ferramentas: Optional[str],
                  capacidades: Optional[list[str]] = None, evitar: Optional[str] = None,
                  emitir: bool = True) -> Optional["ClienteModelo"]:
        """Resolve o cliente: pin > tier > capacidade > papel > padrão, depois esgotamento e desvio
        de ferramentas. `emitir=False` para consulta sem efeitos (provedor_de)."""
        campos_rota = (papel, tier, ferramentas, evitar)
        if (
            not isinstance(papel, str)
            or not papel.strip()
            or any(valor is not None and (
                not isinstance(valor, str) or not valor.strip()
            ) for valor in campos_rota[1:])
        ):
            if emitir and capacidades is not None:
                caps_evento = (
                    [c for c in capacidades if isinstance(c, str)]
                    if isinstance(capacidades, list) else []
                )
                self._evento(
                    "registro.sem_executor",
                    papel=papel if isinstance(papel, str) and papel.strip() else "<invalido>",
                    capacidades=caps_evento,
                )
            return None
        pin = self.pins.get(papel) or (self.pins.get(tier) if tier else None) or self.pins.get("*")
        if self._usa_capacidades(capacidades):
            assert capacidades is not None
            candidatos = self._candidatos_capazes(
                capacidades,
                evitar=None if pin is not None else evitar,
                ferramentas=ferramentas,
            )
            if not candidatos:
                if emitir:
                    caps_evento = [c for c in capacidades if isinstance(c, str)] if isinstance(capacidades, list) else []
                    self._evento("registro.sem_executor", papel=papel, capacidades=caps_evento)
                return None
            preferido = pin or (self.tiers.get(tier) if tier else None)
            if preferido is not None:
                if preferido not in candidatos:
                    if emitir:
                        self._evento("registro.sem_executor", papel=papel,
                                     capacidades=list(capacidades))
                    return None
                cliente = preferido
                if emitir:
                    evento = "modelo.pin" if pin is not None else "modelo.roteado_tier"
                    self._evento(evento, papel=papel, tier=tier)
            else:
                cliente = candidatos[0]
                if emitir:
                    self._evento("modelo.roteado_capacidade", papel=papel,
                                 capacidades=list(capacidades),
                                 provedor=getattr(cliente, "provedor", None))
            return cliente
        if pin is not None:                          # pin manual vence tier e papel
            cliente = pin
            if emitir:
                self._evento("modelo.pin", papel=papel, tier=tier)
        elif tier and tier in self.tiers:
            cliente = self.tiers[tier]
            if emitir:
                self._evento("modelo.roteado_tier", papel=papel, tier=tier)
        else:
            cliente = self.mapa.get(papel, self.padrao)
        cliente = self._disponivel(cliente, papel, emitir=emitir)   # provedor esgotado → reroteia
        if cliente is not self.padrao and ferramentas and not getattr(cliente, "suporta_ferramentas", True):
            if emitir:
                self._evento("modelo.roteado_ferramentas", papel=papel, ferramentas=ferramentas)
            cliente = self._disponivel(self.padrao, papel, emitir=emitir)
        return cliente

    def provedor_de(self, papel: str, tier: Optional[str] = None,
                    ferramentas: Optional[str] = None,
                    capacidades: Optional[list[str]] = None) -> Optional[str]:
        """Qual provedor ATENDERIA esta chamada, sem executá-la nem logar. Usado pelo
        grafo p/ o guard de independência do juiz (verifier ≠ provedor do executor)."""
        return getattr(self._resolver(papel, tier, ferramentas, capacidades=capacidades,
                                      emitir=False), "provedor", None)

    def descricao_de(self, papel: str, tier: Optional[str] = None,
                     ferramentas: Optional[str] = None,
                     capacidades: Optional[list[str]] = None) -> Optional[str]:
        """Identidade concreta que atenderia a chamada, sem executar nem emitir eventos."""
        cliente = self._resolver(papel, tier, ferramentas, capacidades=capacidades, emitir=False)
        return _descricao_cliente(cliente, papel)

    def _outro_provedor(self, evitar: str | None,
                        capacidades: Optional[list[str]] = None,
                        ferramentas: Optional[str] = None,
                        excluir: "ClienteModelo" | None = None) -> Optional["ClienteModelo"]:
        """Primeiro cliente disponível (cadeia + padrao) cujo provedor != `evitar`."""
        if self._usa_capacidades(capacidades):
            candidatos = self._candidatos_capazes(
                capacidades, evitar=evitar, ferramentas=ferramentas, excluir=excluir)
            return candidatos[0] if candidatos else None
        for alt in [*self.cadeia, self.padrao]:
            prov = getattr(alt, "provedor", None)
            if prov != evitar and prov not in self.esgotados:
                return alt
        return None

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
        cliente = self._resolver(papel, tier, ferramentas, capacidades=capacidades, evitar=evitar)
        if cliente is None:
            return None
        # Guard de independência do juiz: o verifier não pode rodar no MESMO provedor
        # do executor que ele julga (senão o modelo se auto-aprova). `evitar` = provedor
        # do executor. Um PIN explícito do Caio vence o guard (decisão consciente).
        if evitar and not self._eh_pin(papel, tier) and getattr(cliente, "provedor", None) == evitar:
            alt = self._outro_provedor(evitar, capacidades, ferramentas)
            if alt is not None:
                self._evento("juiz.independencia", papel=papel, evitar=evitar,
                             para=getattr(alt, "provedor", None))
                cliente = alt
        resposta = cliente.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                                  timeout=timeout, capacidades=capacidades)
        if resposta is not None:
            return resposta
        if not self.auto_esgotar:
            if self._usa_capacidades(capacidades):
                alvo = self._outro_provedor(
                    getattr(cliente, "provedor", None), capacidades, ferramentas, cliente)
                if alvo is not cliente:
                    if alvo is None:
                        return None
                    self._evento("modelo.fallback", papel=papel)
                    resposta = alvo.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                                           timeout=timeout, capacidades=capacidades)
            elif cliente is not self.padrao:
                alvo = self._disponivel(self.padrao, papel)
                if alvo is not cliente:
                    self._evento("modelo.fallback", papel=papel)
                    resposta = alvo.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                                           timeout=timeout, capacidades=capacidades)
            return resposta

        self._auto_esgotar(cliente, papel, motivo="sem resposta")
        ja_tentados = {_chave_provedor(cliente)}
        alternativas = (self._candidatos_capazes(capacidades, ferramentas=ferramentas)
                        if self._usa_capacidades(capacidades) else self._cadeia_failover())
        for alt in alternativas or []:
            if getattr(alt, "provedor", None) in self.esgotados:
                continue
            chave = _chave_provedor(alt)
            if chave in ja_tentados:
                continue
            ja_tentados.add(chave)
            self._evento("modelo.fallback", papel=papel, para=getattr(alt, "provedor", None))
            resposta = alt.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                                  timeout=timeout, capacidades=capacidades)
            if resposta is not None:
                return resposta
            self._auto_esgotar(alt, papel, motivo="sem resposta")
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
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
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
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
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
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
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
            return cast(dict[Any, Any], json.loads(resp.read().decode("utf-8")))

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
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
                conteudo = cast(str, resp["choices"][0]["message"]["content"].strip())
                if conteudo:
                    uso = resp.get("usage") or {}
                    if self.log is not None and uso:
                        dados_uso = dict(
                            papel=papel,
                            provedor=self.provedor,
                            modelo=self.mapa_papeis.get(papel, self.modelo),
                            prompt_tokens=uso.get("prompt_tokens"),
                            completion_tokens=uso.get("completion_tokens"),
                            total_tokens=uso.get("total_tokens"),
                        )
                        self.log.evento("modelo.uso", **dados_uso)
                        self.log.evento("custo.tick", **dados_uso)
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
        capacidades_validas = {
            "codigo", "redacao", "calculo", "pesquisa", "raciocinio-longo",
        }

        def _capacidades_config(valor: Any, quem: str) -> frozenset[str] | None:
            if valor is None:
                return None
            if (
                not isinstance(valor, list)
                or not valor
                or any(not isinstance(item, str) for item in valor)
                or len(set(valor)) != len(valor)
                or not set(valor) <= capacidades_validas
            ):
                raise ValueError(f"{quem}: capacidades invalidas")
            return frozenset(valor)

        clientes_destino: dict[str, Any] = {"padrao": padrao}

        def _cliente_destino(destino: str, quem: str):
            """Constrói UM cliente para 'provedor/modelo' (ou 'padrao')."""
            if destino in clientes_destino:
                return clientes_destino[destino]
            prov, sep, modelo = destino.partition("/")
            if not sep or not modelo or prov not in cfg["provedores"]:
                raise ValueError(
                    f"{quem}: destino {destino!r} deve ser 'provedor/modelo' (ou 'padrao'); "
                    f"provedores declarados: {list(cfg['provedores'])}")
            p = cfg["provedores"][prov]
            tipo = p.get("tipo", "openai-compat")
            cliente: Any
            if tipo == "codex":
                cliente = ClienteCodex(modelo=modelo, sandbox=p.get("sandbox", "read-only"),
                                       busca_ao_vivo=p.get("search", False), log=log)
            elif tipo == "opencode":
                cliente = ClienteOpenCode(modelo=modelo, permissao=p.get("permissao"),
                                          log=log, provedor=prov)
            elif tipo == "openai-compat":
                cliente = ClienteOpenAICompat(
                    base_url=p["base_url"], api_key=_chave(p["api_key_env"], f"provedor {prov!r}"),
                    modelo=modelo, log=log, provedor=prov)
            else:
                raise ValueError(
                    f"provedor {prov!r}: tipo {tipo!r} desconhecido "
                    f"(use 'codex', 'opencode' ou 'openai-compat')")
            if p.get("custo_ordem") is not None:
                setattr(cliente, "custo_ordem", p.get("custo_ordem"))
            clientes_destino[destino] = cliente
            return cliente

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
            if p.get("custo_ordem") is not None:
                setattr(cliente, "custo_ordem", p.get("custo_ordem"))

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
        cadeia = _ordenar_cadeia_por_custo(cadeia)
        catalogo: list[tuple[Any, frozenset[str], int]] = []
        vistos_catalogo: set[int] = set()
        for cliente in [*cadeia, padrao]:
            if id(cliente) in vistos_catalogo:
                continue
            provedor = getattr(cliente, "provedor", None)
            if cliente is padrao:
                capacidades = _capacidades_config(
                    cfg.get("capacidades_padrao"), "capacidades_padrao"
                )
                ordem = cfg.get("custo_ordem_padrao", 100)
            else:
                provedor_cfg = cfg["provedores"].get(provedor, {})
                capacidades = _capacidades_config(
                    provedor_cfg.get("capacidades"),
                    f"provedor {provedor!r}",
                )
                ordem = provedor_cfg.get("custo_ordem", 0)
            if capacidades is not None:
                catalogo.append((cliente, capacidades, ordem))
                vistos_catalogo.add(id(cliente))
        return ClienteRoteador(padrao=padrao, mapa=mapa, tiers=tiers_map, pins=pins_map,
                               esgotados=set(cfg.get("esgotados", [])), cadeia=cadeia,
                               catalogo=catalogo,
                               auto_esgotar=bool(cfg.get("auto_esgotar", False)), log=log)

    # formato v1 — um provedor
    barato = ClienteOpenAICompat(
        base_url=cfg["base_url"], api_key=_chave(cfg["api_key_env"], "provedor único"),
        modelo=cfg["modelo"], mapa_papeis=cfg.get("mapa_papeis_modelo"), log=log,
        provedor=cfg.get("provedor", "openai-compat"))
    if cfg.get("custo_ordem") is not None:
        setattr(barato, "custo_ordem", cfg.get("custo_ordem"))
    return ClienteRoteador(padrao=padrao,
                           mapa={p: barato for p in cfg.get("papeis_baratos", [])},
                           esgotados=set(cfg.get("esgotados", [])),
                           cadeia=_ordenar_cadeia_por_custo([barato]),
                           auto_esgotar=bool(cfg.get("auto_esgotar", False)), log=log)
