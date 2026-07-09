# HANDOFF OPENCODE — Curador Fatia 3.2: Certificador Anti-Goodhart

## Objetivo
Adicionar `certificar_sombra(...)` em `motor/motor/curador.py`, consumindo a evidencia gerada por
`rodar_sombra(...)`.

## Regra de certificacao
Certifica somente se:

- `taxa_aprovacao(candidato) > taxa_aprovacao(titular)`
- `custo_medio_usd(candidato) < custo_medio_usd(titular)`

Se qualquer custo for `None`, nao certifica por custo incomparavel.

## Testes obrigatorios
- Candidato melhor em qualidade e custo => certificado.
- Candidato mais barato mas com qualidade menor => rejeitado.
- Candidato qualidade igual e custo menor => rejeitado.
- Custo ausente => rejeitado.

## Eventos
Emitir `curador.certificou` quando passar e `curador.rejeitou` quando falhar, via callback opcional.

## DoD
- Testes em `motor/tests/test_curador.py`.
- `pytest`, `ruff`, `mypy` verdes no arquivo.
- Diff limitado a curador e testes.

## Onde isto pode dar errado
- Usar economia de custo como criterio suficiente viola o anti-Goodhart.
- Aceitar empate de qualidade como "bateu" enfraquece a catraca.
