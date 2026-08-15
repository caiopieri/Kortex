"""Adaptador custeado para uma tentativa direta na OpenAI Chat Completions API."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Callable, Mapping, cast

from .orcamento import CotacaoTentativa, ErroOrcamento, ResultadoTentativa


MODELO = "gpt-5.6-terra"
MAX_INPUT_TOKENS = 400_000
MAX_OUTPUT_TOKENS = 128_000
PRICING_VERSION = "openai-gpt56terra-standard-verified-2026-08-10"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"
# Verificado em 2026-08-10 contra PRICING_SOURCE.
#
# ATENCAO -- ate 2026-07-28 este adapter cotava `gpt-5-2025-08-07` a
# $1.25/$0.125/$10, que era o preco de LANCAMENTO de agosto/2025. A linha
# vigente e gpt-5.4/5.5/5.6 e o `gpt-5` daquela tabela nao existe mais. Ou seja:
# o motor subfaturava ~4x na entrada e ~3x na saida, na unica contencao
# monetaria que ele tem. Preco de modelo e dado PERECIVEL -- PRICING_MAX_AGE_S
# existe para forcar a reconferencia, e ela precisa ser real, nao carimbo.
_INPUT_USD = Decimal("2.5") / Decimal(1_000_000)
_CACHED_USD = Decimal("0.25") / Decimal(1_000_000)
_OUTPUT_USD = Decimal("15") / Decimal(1_000_000)
_QUANTUM_BRL = Decimal("0.000001")


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


class ClienteOpenAICusteado:
    """Uma chamada, sem retry, com custo derivado somente do usage do provedor."""

    def __init__(
        self, *, api_key: str, prompt: str, max_input_tokens: int,
        max_completion_tokens: int, fx: SnapshotFX, pricing: SnapshotPricing,
        agora: int, fx_max_age_s: int, pricing_max_age_s: int,
        margem: Decimal, timeout: int, transporte: TransporteHTTP = _http_real,
    ) -> None:
        if not isinstance(api_key, str) or not api_key or not isinstance(prompt, str) or not prompt:
            raise ErroOrcamento("entrada OpenAI invalida")
        self.max_input_tokens = _inteiro(max_input_tokens, "max_input_tokens")
        self.max_completion_tokens = _inteiro(max_completion_tokens, "max_completion_tokens")
        if (self.max_input_tokens != MAX_INPUT_TOKENS
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
        self._timeout, self._transporte = timeout, transporte

    def _brl(self, input_tokens: int, cached_tokens: int, output_tokens: int, *, margem: bool) -> Decimal:
        usd = ((input_tokens - cached_tokens) * _INPUT_USD
               + cached_tokens * _CACHED_USD + output_tokens * _OUTPUT_USD)
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
            "model": MODELO,
            "messages": [{"role": "user", "content": self._prompt}],
            "max_completion_tokens": self.max_completion_tokens,
        }
        status, headers, bruto = self._transporte(
            "https://api.openai.com/v1/chat/completions",
            json.dumps(payload, separators=(",", ":")).encode(),
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            self._timeout,
        )
        if status != 200:
            raise ErroOrcamento("resposta OpenAI ambigua")
        try:
            resposta = cast(dict[str, object], json.loads(bruto))
            if resposta.get("model") != MODELO:
                raise ErroOrcamento("modelo divergente")
            usage = cast(dict[str, object], resposta["usage"])
            entrada = _inteiro(usage["prompt_tokens"], "prompt_tokens")
            saida = _inteiro(usage["completion_tokens"], "completion_tokens")
            total = _inteiro(usage["total_tokens"], "total_tokens")
            detalhes = usage.get("prompt_tokens_details", {})
            if not isinstance(detalhes, dict):
                raise ErroOrcamento("usage invalido")
            cached = _inteiro(detalhes.get("cached_tokens", 0), "cached_tokens")
            if total != entrada + saida or cached > entrada:
                raise ErroOrcamento("usage inconsistente")
            if entrada > self.max_input_tokens or saida > self.max_completion_tokens:
                raise ErroOrcamento("usage excede limites reservados")
            texto = cast(dict[str, object], cast(list[object], resposta["choices"])[0])["message"]
            conteudo = cast(dict[str, object], texto)["content"]
            request_id = next((v for k, v in headers.items() if k.lower() == "x-request-id"), None)
            if not isinstance(conteudo, str) or not conteudo or not isinstance(request_id, str):
                raise ErroOrcamento("resposta OpenAI incompleta")
            custo = self._brl(entrada, cached, saida, margem=False)
            return ResultadoTentativa(conteudo, custo, "BRL", request_id)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as erro:
            raise ErroOrcamento("resposta OpenAI invalida") from erro
