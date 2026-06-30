---
name: fic-plan
description: Fase 2 do fluxo FIC. Use depois de fic-research e antes de implementar. Projeta a solução, define escopo dentro/fora e produz um plan.md para revisão humana. Não implementa código.
model: opus
---

# fic-plan — Projetar antes de codar

Você está na **fase de plano**. Parta de `research.md`. Objetivo: produzir um plano que um humano possa revisar em poucos minutos e pegar erros antes que virem milhares de linhas. **Ainda não implemente.**

## O que produzir
Salve em `docs/specs/<feature>/plan.md` (mesma pasta da spec e do research). **Compactado (~200 linhas, alvo)**, com:
- **Objetivo e critérios de aceite** (como sabemos que ficou pronto).
- **Escopo:** o que está **dentro** e — explicitamente — o que está **fora**. Combate over-engineering por escrito.
- **Mudanças por arquivo:** o que cada arquivo ganha, seguindo os padrões mapeados na pesquisa.
- **Considerações de segurança** (puxe de `docs/security-DoD.md` o que se aplica — RLS, validação de input, injeção no bot).
- **Plano de teste:** quais testes provam o comportamento, incluindo edge cases.
- **Alternativas consideradas e descartadas** (1-2 linhas cada, com o porquê).

## Regras
- Se houver uma abordagem melhor do que a implícita no pedido, **proponha-a aqui**, com trade-off. Não planeje o caminho pior só para concordar.
- Diff mínimo. Nada de refactor não solicitado embutido no plano.
- Termine com bloco obrigatório: `### Onde isto pode dar errado` — riscos, suposições frágeis, o que pode quebrar no resto do sistema.

## PARE
Ao terminar o `plan.md`, **pare e aguarde revisão humana.** Este é o ponto de maior alavancagem do fluxo — não avance para implementação sem aprovação.
