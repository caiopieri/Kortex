# HANDOFF CODEX — propositor do curador usa CUSTO REAL ($) no desempate

## Por quê (fecha o elo livro-razão → propositor)
O propositor (`motor/curador.py::propor`) ranqueia modelos por **qualidade → latência → custo**. Hoje o
custo é o proxy `custo_ordem` (ordem barata→cara da config). Mas o **livro-razão** já calcula `custo_usd`
real por modelo (`analisar(..., precos=...)` → `perfil["custo"]["por_modelo"][<modelo>]`). Este handoff
liga os dois: quando há `custo_usd` real, o propositor usa ele no desempate — aí "cada vez mais barato"
deixa de ser sensação e vira critério medido de alocação. Pequeno, aditivo, read-only.

## Mudança (motor/curador.py + tests)
Em `propor(...)`, no critério de **desempate por custo** (que hoje usa `custo`/`custo_ordem`):
- Se `perfil["custo"]["por_modelo"][<modelo>]` existir e tiver `custo_usd` não-nulo, usar como sinal de
  custo o **$ por chamada** = `custo_usd / max(1, chamadas_com_uso)` (menor = melhor). Assim compara
  modelos de forma justa (um modelo caro que roda pouco não parece barato).
- Se não houver `custo_usd` (ex.: modelo CLI sem tokens), cair no proxy atual (`custo`/`custo_ordem`); se
  nem isso, o desempate de custo é neutro (mantém a ordem por qualidade→latência).
- A PRECEDÊNCIA não muda: qualidade primeiro, latência depois, **custo só como desempate final**. Nunca
  recomendar um modelo pior de qualidade só porque é mais barato.
- No ranking retornado, incluir o `custo_usd_por_chamada` (quando houver) junto de score/aprov/latência,
  pra a proposta ser auditável.

## Restrições
- READ-ONLY (propositor não aplica nada). stdlib. Sem chamar modelo.
- Aditivo: sem seção `custo` no perfil / sem `custo_usd`, comportamento idêntico ao de hoje.
- Não mexer na agregação do livro-razão nem no observador; só no desempate de `propor`.

## DoD
1. Slot com 2 modelos de MESMA qualidade e MESMA latência, mas `custo_usd` diferentes (via perfil com
   seção custo) → recomenda o de menor $/chamada.
2. Empate de qualidade+latência SEM `custo_usd` → cai no `custo_ordem` como hoje (regressão intacta).
3. Qualidade diferente → custo NÃO inverte (o de melhor aprovação-1ª vence mesmo sendo mais caro).
4. Suíte verde (262+); compileall; mypy ok.
