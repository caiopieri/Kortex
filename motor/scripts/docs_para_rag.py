#!/usr/bin/env python3
"""Gera JSONL RAG a partir dos markdowns internos da meta-fabrica."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MOTOR_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MOTOR_ROOT.parent
DEFAULT_FONTES = [
    PROJECT_ROOT / "docs",
    MOTOR_ROOT / "docs",
    PROJECT_ROOT / "dev-harness" / "docs",
]
DEFAULT_SAIDA = MOTOR_ROOT / "exemplos" / "rag-docs-metafabrica.jsonl"
HEADING_RE = re.compile(r"^#{1,6}\s+\S")


def arquivos_markdown(fontes: list[Path]) -> list[Path]:
    arquivos: list[Path] = []
    for fonte in fontes:
        if fonte.is_file() and fonte.suffix.lower() == ".md":
            arquivos.append(fonte)
        elif fonte.is_dir():
            arquivos.extend(sorted(fonte.glob("*.md")))
    return sorted(dict.fromkeys(arquivos))


def _secoes(texto: str) -> list[str]:
    secoes: list[str] = []
    atual: list[str] = []
    for linha in texto.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        if HEADING_RE.match(linha) and atual:
            secoes.append("\n".join(atual).strip())
            atual = [linha]
        else:
            atual.append(linha)
    if atual:
        secoes.append("\n".join(atual).strip())
    return [secao for secao in secoes if secao]


def _quebrar_bloco(texto: str, max_chars: int) -> list[str]:
    if len(texto) <= max_chars:
        return [texto]
    partes: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fim = min(inicio + max_chars, len(texto))
        corte = texto.rfind(" ", inicio, fim)
        if corte <= inicio:
            corte = fim
        partes.append(texto[inicio:corte].strip())
        inicio = corte
    return [parte for parte in partes if parte]


def chunks_markdown(path: Path, *, max_chars: int = 1400) -> list[str]:
    texto = path.read_text(encoding="utf-8")
    chunks: list[str] = []
    for secao in _secoes(texto):
        paragrafos = [p.strip() for p in re.split(r"\n\s*\n", secao) if p.strip()]
        atual: list[str] = []
        tamanho = 0
        for paragrafo in paragrafos:
            if len(paragrafo) > max_chars:
                if atual:
                    chunks.append("\n\n".join(atual).strip())
                    atual, tamanho = [], 0
                chunks.extend(_quebrar_bloco(paragrafo, max_chars))
                continue
            proximo_tamanho = tamanho + len(paragrafo) + (2 if atual else 0)
            if atual and proximo_tamanho > max_chars:
                chunks.append("\n\n".join(atual).strip())
                atual, tamanho = [paragrafo], len(paragrafo)
            else:
                atual.append(paragrafo)
                tamanho = proximo_tamanho
        if atual:
            chunks.append("\n\n".join(atual).strip())
    return [chunk for chunk in chunks if chunk.strip()]


def gerar_registros(fontes: list[Path], *, max_chars: int = 1400) -> list[dict[str, str]]:
    registros: list[dict[str, str]] = []
    for arquivo in arquivos_markdown(fontes):
        try:
            rel = arquivo.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = arquivo
        for indice, chunk in enumerate(chunks_markdown(arquivo, max_chars=max_chars), start=1):
            registros.append({
                "id": f"{rel.as_posix()}#{indice}",
                "origem": f"{rel.as_posix()}#chunk-{indice}",
                "conteudo": chunk,
            })
    return registros


def escrever_jsonl(registros: list[dict[str, str]], saida: Path) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8") as fp:
        for registro in registros:
            if registro.get("conteudo", "").strip():
                fp.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunka docs internos em JSONL RAG.")
    parser.add_argument("--saida", default=str(DEFAULT_SAIDA))
    parser.add_argument("--max-chars", type=int, default=1400)
    parser.add_argument("--fonte", action="append", help="Arquivo .md ou diretorio com .md; pode repetir.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    fontes = [Path(fonte) for fonte in args.fonte] if args.fonte else DEFAULT_FONTES
    registros = gerar_registros(fontes, max_chars=args.max_chars)
    escrever_jsonl(registros, Path(args.saida))
    print(f"gerados={len(registros)} saida={args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
