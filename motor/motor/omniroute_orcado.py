"""Adaptador custeado para uma tentativa via OmniRoute (proxy OpenAI-compativel).

O OmniRoute expoe `/v1/chat/completions` com o formato da OpenAI e roteia para
varios upstreams. Isso permite alcancar Gemini, GPT e Claude com uma credencial
so -- ao custo de duas concessoes que precisam ficar explicitas:

1. O MOTOR PERDE A CAPACIDADE DE VERIFICAR A INDEPENDENCIA. `provider_id` aqui e
   declarado por config, nao observado: se o proxy for reconfigurado e mandar
   executor e verifier para o mesmo modelo, o motor nao tem como perceber.
   Produtor != juiz vira promessa do OmniRoute, nao garantia do kernel. Aceitavel
   para MVP; NAO aceitavel para o curador decidir promocao de modelo.

2. O CUSTO REPORTADO PELO PROXY E IGNORADO DE PROPOSITO. O header
   `x-omniroute-response-cost` observado em 2026-07-28 vinha `0.0000000000`, e
   `x-omniroute-tokens-in` (7) discordava de `usage.prompt_tokens` (2007) porque
   o proxy injeta contexto proprio que nao contabiliza no header. Custear pelo
   que ele diz tornaria o teto decorativo -- tudo custaria zero e nada estouraria.
   Aqui o custo sai do `usage` do CORPO, que inclui o contexto injetado, contra
   uma tabela code-owned. Conservador e conferivel.

ATENCAO -- os precos sao code-owned e o roteamento passa por um gateway que pode
ter markup proprio. A tabela e um PISO do custo real, nao a fatura. Verificar
contra a cobranca do gateway antes de confiar no teto para valores altos.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Callable, Mapping, cast

from .orcamento import CotacaoTentativa, ErroOrcamento, ResultadoTentativa


MAX_INPUT_TOKENS = 200_000
MAX_OUTPUT_TOKENS = 64_000
PRICING_VERSION = "omniroute-openrouter-verified-2026-07-28"
PRICING_SOURCE = "https://openrouter.ai/models"
_QUANTUM_BRL = Decimal("0.000001")
_MILHAO = Decimal(1_000_000)


@dataclass(frozen=True)
class PrecoModelo:
    """USD por 1M tokens. `cached` e leitura de cache, nao escrita."""

    entrada: Decimal
    cached: Decimal
    saida: Decimal


# Modelos habilitados, verificados respondendo pelo proxy em 2026-07-28.
# A chave e o id COMPLETO do OmniRoute; `modelo_upstream` e o que a resposta
# ecoa em `model` (o proxy remove o prefixo do gateway).
PRECOS: dict[str, PrecoModelo] = {
    # --- rotas de assinatura do fundador (Claude, Antigravity/Gemini) ---
    #
    # ATENCAO: sob assinatura o custo MARGINAL por token e zero -- ja foi pago.
    # Precificar em zero, porem, tornaria o teto decorativo: nada nunca
    # estouraria e o motor perderia a unica contencao que tem. Aqui os precos
    # sao os da API publica do modelo equivalente. Isso NAO e a fatura; e um
    # orcamento de USO, que impede uma missao de consumir a assinatura inteira.
    "claude/claude-opus-4-8": PrecoModelo(
        Decimal("5"), Decimal("0.50"), Decimal("25"),
    ),
    "claude/claude-opus-4-7": PrecoModelo(
        Decimal("5"), Decimal("0.50"), Decimal("25"),
    ),
    "claude/claude-opus-4-6": PrecoModelo(
        Decimal("5"), Decimal("0.50"), Decimal("25"),
    ),
    "agy/claude-sonnet-4-6": PrecoModelo(
        Decimal("3"), Decimal("0.30"), Decimal("15"),
    ),
    # Gemini 3.1 Pro nao tem tabela publica conferida; cotado pelo teto da
    # familia Pro (faixa longa) para nunca subestimar.
    "agy/gemini-3.1-pro-high": PrecoModelo(
        Decimal("2.50"), Decimal("0.25"), Decimal("15"),
    ),
    "agy/gemini-3.1-pro-low": PrecoModelo(
        Decimal("2.50"), Decimal("0.25"), Decimal("15"),
    ),
    "agy/gemini-3.5-flash-high": PrecoModelo(
        Decimal("0.30"), Decimal("0.03"), Decimal("2.50"),
    ),
    # Codex pela assinatura. Cotado pela tabela publica do gpt-5.x equivalente
    # (2026-07-28) -- ver kortex-preco-modelo-perecivel.
    "codex/gpt-5.3-codex": PrecoModelo(
        Decimal("2.50"), Decimal("0.25"), Decimal("15"),
    ),
    "codex/gpt-5.2-codex": PrecoModelo(
        Decimal("2.50"), Decimal("0.25"), Decimal("15"),
    ),

    # --- rotas via openrouter (pay-as-you-go; sem credito em 2026-07-28) ---
    "openrouter/google/gemini-3.5-flash": PrecoModelo(
        Decimal("0.30"), Decimal("0.03"), Decimal("2.50"),
    ),
    "openrouter/openai/gpt-5.4": PrecoModelo(
        Decimal("2.50"), Decimal("0.25"), Decimal("15"),
    ),
    "openrouter/anthropic/claude-sonnet-4.5": PrecoModelo(
        Decimal("3"), Decimal("0.30"), Decimal("15"),
    ),
}


@dataclass(frozen=True)
class SnapshotFX:
    versao: str
    capturado_em: int
    cotacao_venda: Decimal


@dataclass(frozen=True)
class SnapshotPricing:
    versao: str
    capturado_em: int
    fonte: str


RespostaHTTP = tuple[int, Mapping[str, str], bytes]
TransporteHTTP = Callable[[str, bytes, Mapping[str, str], int], RespostaHTTP]


def _inteiro(valor: object, nome: str) -> int:
    if type(valor) is not int or valor < 0:
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _decimal_positivo(valor: object, nome: str) -> Decimal:
    if type(valor) is not Decimal or not valor.is_finite() or valor <= 0:
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _arredondar_brl(valor: Decimal) -> Decimal:
    return valor.quantize(_QUANTUM_BRL, rounding=ROUND_CEILING)


def _http_real(url: str, corpo: bytes, headers: Mapping[str, str], timeout: int) -> RespostaHTTP:
    requisicao = urllib.request.Request(url, data=corpo, headers=dict(headers), method="POST")
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        return resposta.status, dict(resposta.headers.items()), resposta.read()


class ClienteOmniRouteCusteado:
    """Uma chamada, sem retry, com custo derivado somente do usage do provedor."""

    def __init__(
        self, *, api_key: str, base_url: str, modelo: str, prompt: str,
        max_input_tokens: int, max_completion_tokens: int,
        fx: SnapshotFX, pricing: SnapshotPricing, agora: int,
        fx_max_age_s: int, pricing_max_age_s: int,
        margem: Decimal, timeout: int, transporte: TransporteHTTP = _http_real,
    ) -> None:
        if not isinstance(api_key, str) or not api_key or not isinstance(prompt, str) or not prompt:
            raise ErroOrcamento("entrada OmniRoute invalida")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ErroOrcamento("base_url OmniRoute invalida")
        if modelo not in PRECOS:
            # Fail-closed: modelo sem preco declarado nao roda. Deixar passar seria
            # executar com custo desconhecido, que e pior que nao executar.
            raise ErroOrcamento(f"modelo sem preco declarado: {modelo}")
        self.modelo = modelo
        self.preco = PRECOS[modelo]
        self.max_input_tokens = _inteiro(max_input_tokens, "max_input_tokens")
        self.max_completion_tokens = _inteiro(max_completion_tokens, "max_completion_tokens")
        # `max_input_tokens` e CONFIGURAVEL aqui, ao contrario dos adapters
        # diretos, porque a reserva e feita pelo pior caso: fixar em 200k faz
        # cada tentativa reservar ~40x o que um prompt real (~2k tokens) consome,
        # e ai o teto barra missao legitima. O limite continua sendo um TETO --
        # prompt maior que ele e recusado antes do envio, fail-closed.
        if (self.max_input_tokens == 0 or self.max_input_tokens > MAX_INPUT_TOKENS
                or self.max_completion_tokens == 0
                or self.max_completion_tokens > MAX_OUTPUT_TOKENS):
            raise ErroOrcamento("limites de token invalidos")
        if len(prompt.encode("utf-8")) > self.max_input_tokens:
            raise ErroOrcamento("prompt excede limite conservador")
        if (type(agora) is not int or type(fx_max_age_s) is not int or fx_max_age_s <= 0
                or type(pricing_max_age_s) is not int or pricing_max_age_s <= 0):
            raise ErroOrcamento("janela de snapshot invalida")
        if type(fx) is not SnapshotFX or not fx.versao or type(fx.capturado_em) is not int:
            raise ErroOrcamento("snapshot FX invalido")
        if fx.capturado_em > agora or agora - fx.capturado_em > fx_max_age_s:
            raise ErroOrcamento("snapshot FX stale")
        if (type(pricing) is not SnapshotPricing
                or pricing.versao != PRICING_VERSION or pricing.fonte != PRICING_SOURCE
                or type(pricing.capturado_em) is not int):
            raise ErroOrcamento("snapshot pricing invalido")
        if pricing.capturado_em > agora or agora - pricing.capturado_em > pricing_max_age_s:
            raise ErroOrcamento("snapshot pricing stale")
        self.fx, self.pricing = fx, pricing
        self.margem = _decimal_positivo(margem, "margem")
        _decimal_positivo(fx.cotacao_venda, "cotacaoVenda")
        if self.margem < 1:
            raise ErroOrcamento("margem subestima custo")
        if type(timeout) is not int or timeout <= 0 or not callable(transporte):
            raise ErroOrcamento("transporte invalido")
        self._api_key, self._prompt = api_key, prompt
        self._base_url = base_url.rstrip("/")
        self._timeout, self._transporte = timeout, transporte

    def _brl(self, entrada: int, cached: int, saida: int, *, margem: bool) -> Decimal:
        usd = ((entrada - cached) * self.preco.entrada / _MILHAO
               + cached * self.preco.cached / _MILHAO
               + saida * self.preco.saida / _MILHAO)
        multiplicador = self.margem if margem else Decimal(1)
        return _arredondar_brl(usd * self.fx.cotacao_venda * multiplicador)

    def cotar_tentativa(self) -> CotacaoTentativa:
        maximo = self._brl(self.max_input_tokens, 0, self.max_completion_tokens, margem=True)
        versao = (
            f"{self.pricing.versao}@{self.pricing.capturado_em}"
            f"+fx:{self.fx.versao}+margin:{self.margem}"
        )
        return CotacaoTentativa(maximo, "BRL", versao)

    def tentar_uma_vez(self) -> ResultadoTentativa:
        payload = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": self._prompt}],
            "max_tokens": self.max_completion_tokens,
            # Obrigatorio: sem isto o proxy responde SSE mesmo sem pedir stream,
            # e o corpo deixa de ser JSON parseavel.
            "stream": False,
        }
        status, headers, bruto = self._transporte(
            f"{self._base_url}/chat/completions",
            json.dumps(payload, separators=(",", ":")).encode(),
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            self._timeout,
        )
        if status != 200:
            raise ErroOrcamento("resposta OmniRoute ambigua")
        try:
            resposta = cast(dict[str, object], json.loads(bruto))
            if "error" in resposta:
                raise ErroOrcamento("upstream do OmniRoute recusou")
            # O proxy ecoa o modelo SEM o prefixo do gateway
            # ("openrouter/openai/gpt-5.4" -> "openai/gpt-5.4"), entao a
            # comparacao e por sufixo. Igualdade estrita reprovaria toda resposta.
            ecoado = resposta.get("model")
            if not isinstance(ecoado, str) or not self.modelo.endswith(ecoado):
                raise ErroOrcamento("modelo divergente")
            usage = cast(dict[str, object], resposta["usage"])
            entrada = _inteiro(usage["prompt_tokens"], "prompt_tokens")
            saida = _inteiro(usage["completion_tokens"], "completion_tokens")
            total = _inteiro(usage["total_tokens"], "total_tokens")
            detalhes = usage.get("prompt_tokens_details", {})
            if not isinstance(detalhes, dict):
                raise ErroOrcamento("usage invalido")
            cached = _inteiro(detalhes.get("cached_tokens", 0), "cached_tokens")
            # Modelos com raciocinio (Gemini, o-series) contam os tokens de
            # "pensamento" no `total_tokens` mas NAO em `completion_tokens`, e o
            # provedor os cobra como SAIDA. Exigir `total == entrada + saida`
            # reprovava toda resposta desses modelos; ignora-los subfaturaria a
            # linha mais cara. O residuo entra como saida.
            saida_detalhe = usage.get("completion_tokens_details", {})
            declarado = (
                _inteiro(saida_detalhe.get("reasoning_tokens", 0), "reasoning_tokens")
                if isinstance(saida_detalhe, dict) else 0
            )
            residuo = total - entrada - saida
            if residuo < 0 or cached > entrada:
                raise ErroOrcamento("usage inconsistente")
            saida += max(declarado, residuo)
            if entrada > self.max_input_tokens or saida > self.max_completion_tokens:
                raise ErroOrcamento("usage excede limites reservados")
            escolha = cast(dict[str, object], cast(list[object], resposta["choices"])[0])
            mensagem = cast(dict[str, object], escolha["message"])
            conteudo = mensagem["content"]
            request_id = next(
                (v for k, v in headers.items() if k.lower() == "x-request-id"), None
            )
            if not isinstance(conteudo, str) or not conteudo or not isinstance(request_id, str):
                raise ErroOrcamento("resposta OmniRoute incompleta")
            custo = self._brl(entrada, cached, saida, margem=False)
            return ResultadoTentativa(conteudo, custo, "BRL", request_id)
        except ErroOrcamento:
            raise
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as erro:
            raise ErroOrcamento("resposta OmniRoute invalida") from erro
