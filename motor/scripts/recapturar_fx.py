#!/usr/bin/env python3
"""Recaptura a cotacao USD/BRL e grava o bloco `fx` das configs custeadas.

O snapshot de FX vence em 24h (`FX_MAX_AGE_LIMITE_S`). Vencido, o motor recusa
arrancar -- por desenho, porque cambio velho e teto monetario velho. Sem
ferramenta, toda sessao comeca refazendo isso a mao, e a barreira de frescor
acaba tornando a fabrica inutilizavel: o gate certo vira atrito diario.

O QUE ESTE SCRIPT NAO FAZ: adiantar a data. `capturado_em` e `cotacao_venda`
saem os dois da MESMA resposta da API -- e por isso nao ha como carimbar
frescor sem ter buscado o numero. Adiantar so a data manteria o valor velho, e
e exatamente o que o erro de snapshot vencido recusa.

Pricing NAO e automatizado aqui, de proposito: renovar preco exige RECONFERIR a
tabela publica de cada vendor contra `PRICING_SOURCE` e confirmar que a tabela
code-owned segue sendo teto conservador. Isso e julgamento, nao coleta.

Uso:
    python3 scripts/recapturar_fx.py                 # grava as configs padrao
    python3 scripts/recapturar_fx.py --conferir      # so mostra, nao grava
    python3 scripts/recapturar_fx.py --config a.json --config b.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MOTOR_ROOT = Path(__file__).resolve().parents[1]
FONTE = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
FONTE_ID = "awesomeapi-usdbrl"
TIMEOUT_S = 15

DEFAULT_CONFIGS = [
    MOTOR_ROOT / "exemplos" / "cfg-omniroute.json",
    MOTOR_ROOT / "exemplos" / "cfg-omniroute-gemini.json",
    MOTOR_ROOT / "exemplos" / "cfg-omniroute-sem-codex.json",
    MOTOR_ROOT / "exemplos" / "cfg-orcada-multi.json",
]

# Faixa de sanidade. Nao e previsao de cambio: e recusa de resposta corrompida,
# truncada ou de endpoint trocado. Cotacao fora disto exige olho humano.
MIN_PLAUSIVEL = Decimal("3")
MAX_PLAUSIVEL = Decimal("15")


class ErroRecaptura(RuntimeError):
    """Falha que impede gravar um snapshot confiavel."""


def _decimal_positivo(bruto: Any, campo: str) -> Decimal:
    if not isinstance(bruto, str) or not bruto.strip():
        raise ErroRecaptura(f"campo '{campo}' ausente ou nao textual na resposta")
    try:
        valor = Decimal(bruto)
    except InvalidOperation as exc:
        raise ErroRecaptura(f"campo '{campo}' nao e decimal: {bruto!r}") from exc
    if valor <= 0:
        raise ErroRecaptura(f"campo '{campo}' nao positivo: {valor}")
    return valor


def buscar_cotacao() -> tuple[Decimal, int]:
    """Devolve (cotacao_venda, capturado_em) da fonte publica.

    Usa `ask` (venda) e nao `bid`: venda e o lado caro do spread, entao o teto
    em BRL fica conservador. `capturado_em` vem do timestamp da propria
    resposta -- nao do relogio local -- para o carimbo dizer quando o mercado
    foi lido, nao quando o script rodou.
    """
    requisicao = urllib.request.Request(FONTE, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_S) as resposta:  # noqa: S310
            bruto = resposta.read()
    except OSError as exc:
        raise ErroRecaptura(f"falha ao consultar {FONTE}: {exc}") from exc

    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ErroRecaptura(f"resposta de {FONTE} nao e JSON valido") from exc

    par = dados.get("USDBRL") if isinstance(dados, dict) else None
    if not isinstance(par, dict):
        raise ErroRecaptura("resposta sem o objeto 'USDBRL'")

    venda = _decimal_positivo(par.get("ask"), "ask")
    if not MIN_PLAUSIVEL <= venda <= MAX_PLAUSIVEL:
        raise ErroRecaptura(
            f"cotacao {venda} fora da faixa de sanidade "
            f"[{MIN_PLAUSIVEL}, {MAX_PLAUSIVEL}] -- conferir a fonte a mao"
        )

    carimbo = par.get("timestamp")
    if not isinstance(carimbo, str) or not carimbo.isdigit():
        raise ErroRecaptura(f"timestamp ausente ou nao numerico: {carimbo!r}")
    capturado_em = int(carimbo)

    agora = int(datetime.now(tz=timezone.utc).timestamp())
    if capturado_em > agora + 300:
        raise ErroRecaptura(f"timestamp da fonte esta no futuro: {capturado_em}")

    return venda, capturado_em


def montar_bloco(venda: Decimal, capturado_em: int) -> dict[str, Any]:
    dia = datetime.fromtimestamp(capturado_em, tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "versao": f"{FONTE_ID}-{dia}",
        "capturado_em": capturado_em,
        "cotacao_venda": str(venda),
    }


def gravar(caminho: Path, bloco: dict[str, Any]) -> str:
    cfg = json.loads(caminho.read_text(encoding="utf-8"))
    if "fx" not in cfg:
        return "sem bloco fx, ignorado"
    antes = cfg["fx"].get("cotacao_venda", "?")
    cfg["fx"] = bloco
    caminho.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return f"{antes} -> {bloco['cotacao_venda']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", action="append", type=Path, default=None,
        help="config a atualizar (repetivel); ausente usa as configs custeadas padrao",
    )
    parser.add_argument(
        "--conferir", action="store_true",
        help="so mostra a cotacao buscada; nao grava nada",
    )
    args = parser.parse_args(argv)

    try:
        venda, capturado_em = buscar_cotacao()
    except ErroRecaptura as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    bloco = montar_bloco(venda, capturado_em)
    lido_em = datetime.fromtimestamp(capturado_em, tz=timezone.utc)
    print(f"USD/BRL venda {venda}  (lido em {lido_em:%Y-%m-%d %H:%M:%S}Z)")

    if args.conferir:
        print(json.dumps(bloco, indent=2))
        return 0

    alvos = args.config if args.config else DEFAULT_CONFIGS
    faltando = [caminho for caminho in alvos if not caminho.is_file()]
    if faltando:
        for caminho in faltando:
            print(f"erro: config inexistente: {caminho}", file=sys.stderr)
        return 1

    for caminho in alvos:
        print(f"  {caminho.name}: {gravar(caminho, bloco)}")
    print("\nfx renovado. pricing NAO -- ver PRICING_CAPTURADO_EM em composicao_orcamento.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
