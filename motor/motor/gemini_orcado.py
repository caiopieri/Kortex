"""Adaptador custeado para uma tentativa direta na Gemini generateContent API.

Espelha `openai_orcado.py` de proposito: mesma forma, mesmas guardas, mesma
disciplina de custo derivado SOMENTE do usage devolvido pelo provedor. Divergir
da forma do adapter existente seria pagar duas vezes o custo de revisar a
fronteira financeira.

ATENCAO -- os precos abaixo sao code-owned e precisam ser verificados contra a
tabela publica antes de qualquer gasto real. `PRICING_VERSION` carrega a data da
verificacao e `PRICING_SOURCE` a origem; a composicao confronta os dois e recusa
snapshot velho. Preco errado aqui e contencao monetaria errada no motor inteiro.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Callable, Mapping, cast

from .orcamento import CotacaoTentativa, ErroOrcamento, ResultadoTentativa


MODELO = "gemini-2.5-pro"
# 200k e a fronteira de faixa de preco, nao um limite do modelo: acima dela
# input dobra e output sobe 50%. O teto fica NA faixa barata de proposito, para
# a tabela abaixo nunca subestimar. Elevar isto sem trocar os precos fura o teto.
MAX_INPUT_TOKENS = 200_000
MAX_OUTPUT_TOKENS = 64_000
PRICING_VERSION = "gemini-2.5-pro-standard-verified-2026-07-28"
PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
# Verificado em 2026-07-28 contra PRICING_SOURCE.
# Faixa de prompt <= 200k tokens; acima disso input vira $2.50 e output $15.00.
# O teto conservador de input (MAX_INPUT_TOKENS) mantem o prompt nesta faixa --
# se alguem elevar esse teto acima de 200k, esta tabela passa a SUBESTIMAR.
_INPUT_USD = Decimal("1.25") / Decimal(1_000_000)
_CACHED_USD = Decimal("0.125") / Decimal(1_000_000)
_OUTPUT_USD = Decimal("10") / Decimal(1_000_000)
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


class ClienteGeminiCusteado:
    """Uma chamada, sem retry, com custo derivado somente do usage do provedor."""

    def __init__(
        self, *, api_key: str, prompt: str, max_input_tokens: int,
        max_completion_tokens: int, fx: SnapshotFX, pricing: SnapshotPricing,
        agora: int, fx_max_age_s: int, pricing_max_age_s: int,
        margem: Decimal, timeout: int, transporte: TransporteHTTP = _http_real,
    ) -> None:
        if not isinstance(api_key, str) or not api_key or not isinstance(prompt, str) or not prompt:
            raise ErroOrcamento("entrada Gemini invalida")
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
            "contents": [{"role": "user", "parts": [{"text": self._prompt}]}],
            "generationConfig": {"maxOutputTokens": self.max_completion_tokens},
        }
        status, headers, bruto = self._transporte(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent",
            json.dumps(payload, separators=(",", ":")).encode(),
            {"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            self._timeout,
        )
        if status != 200:
            raise ErroOrcamento("resposta Gemini ambigua")
        try:
            resposta = cast(dict[str, object], json.loads(bruto))
            # `modelVersion` pode vir com sufixo de build (ex. "gemini-2.5-pro-002"):
            # o contrato e a familia cotada, nao o build exato.
            versao_modelo = resposta.get("modelVersion")
            if not isinstance(versao_modelo, str) or not versao_modelo.startswith(MODELO):
                raise ErroOrcamento("modelo divergente")
            usage = cast(dict[str, object], resposta["usageMetadata"])
            entrada = _inteiro(usage["promptTokenCount"], "promptTokenCount")
            saida = _inteiro(usage["candidatesTokenCount"], "candidatesTokenCount")
            total = _inteiro(usage["totalTokenCount"], "totalTokenCount")
            cached = _inteiro(usage.get("cachedContentTokenCount", 0), "cachedContentTokenCount")
            # `thoughtsTokenCount` e cobrado como saida e NAO entra em
            # candidatesTokenCount. Ignora-lo subfatura o raciocinio do modelo.
            pensamento = _inteiro(usage.get("thoughtsTokenCount", 0), "thoughtsTokenCount")
            saida += pensamento
            if total != entrada + saida or cached > entrada:
                raise ErroOrcamento("usage inconsistente")
            if entrada > self.max_input_tokens or saida > self.max_completion_tokens:
                raise ErroOrcamento("usage excede limites reservados")
            candidato = cast(dict[str, object], cast(list[object], resposta["candidates"])[0])
            conteudo = cast(dict[str, object], candidato["content"])
            partes = cast(list[object], conteudo["parts"])
            texto = "".join(
                str(cast(dict[str, object], parte)["text"])
                for parte in partes
                if isinstance(parte, dict) and isinstance(parte.get("text"), str)
            )
            request_id = next(
                (v for k, v in headers.items() if k.lower() == "x-request-id"), None
            )
            if not texto or not isinstance(request_id, str):
                raise ErroOrcamento("resposta Gemini incompleta")
            custo = self._brl(entrada, cached, saida, margem=False)
            return ResultadoTentativa(texto, custo, "BRL", request_id)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as erro:
            raise ErroOrcamento("resposta Gemini invalida") from erro
