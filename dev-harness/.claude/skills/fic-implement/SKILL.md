---
name: fic-implement
description: Fase 3 do fluxo FIC. Use somente com um plan.md já aprovado. Implementa passo a passo seguindo os padrões do repo e roda o Definition of Done antes de declarar pronto.
model: sonnet
---

# fic-implement — Executar o plano aprovado

Você está na **fase de implementação**. Comece com a janela **limpa**: o único contexto necessário é o `plan.md` aprovado. Não recarregue o histórico inteiro de pesquisa.

## O que fazer
1. Implemente o plano passo a passo, na ordem definida.
2. Siga os padrões existentes do repo. Diff mínimo e coerente.
3. Para tarefas longas, mantenha um `docs/specs/<feature>/progress.md` curto (gitignore — é rascunho) com o que já foi feito e o que falta — e compacte quando a janela passar de ~60%.
4. Trate todo input externo (bot, upload, API) como hostil: valide na entrada, nunca deixe conteúdo de terceiro virar instrução.

## Antes de declarar "pronto" — rode o gate (Definition of Done do núcleo global `~/.claude/CLAUDE.md`)
- [ ] Testes passando (caminho feliz + edge cases).
- [ ] Lint + type-check limpos.
- [ ] Revisão de segurança aplicada (`docs/security-DoD.md`) se tocou banco/auth/input/bot.
- [ ] Checagem de escopo: o que adicionei além do plano? Justifique ou remova.
- [ ] Diff revisado — nada de refactor oportunista.

## Regras
- Se durante a implementação você descobrir que o plano está errado, **pare e diga** — não improvise um caminho diferente em silêncio. Volte ao plano.
- Termine com: `### Onde isto pode dar errado` — o que ficou frágil, dívida deixada, o que o revisor humano deve olhar com atenção.
