# ROADMAP — [nome do projeto]

> A camada **acima** da spec. O spec-kit fatia *uma* feature; este arquivo decide *quais fatias,
> em que ordem*, no produto inteiro. É o seu "começar pouco a pouco e ir consolidando", formalizado.
>
> Formato: **Now / Next / Later** (por horizonte, não por data — data vira mentira). Cada item em
> "Now" é uma fatia que cabe no fluxo spec-kit (`/speckit.specify` → ... → `/speckit.implement`).
> Vive na raiz do repo, versionado. Atualize quando a realidade mudar — é esperado, não falha.

## Estado atual
Em uma frase: onde o produto está hoje, o que já funciona.

## Now (em execução — máx 1-2 fatias)
> O que está no fluxo spec-kit agora. Poucas, fechadas, entregáveis. Mais que 2 = foco diluído.

- [ ] **[fatia]** — tier [T0/T1/T2]. Dor que resolve: [...]. Hipótese que valida: [...]. Spec: `specs/00X-...`

## Next (fila priorizada — o que entra quando "Now" esvaziar)
> Ordenado por valor × risco. Ainda não tem spec; tem só a frase de intenção e o tier estimado.

1. **[fatia]** — tier [?]. Por quê agora-depois: [...]
2. **[fatia]** — tier [?]. Por quê: [...]

## Later (capturado, não comprometido)
> Ideias válidas que NÃO entram ainda. Existir aqui evita perder a ideia e evita começá-la cedo demais.

- **[ideia]** — depende de: [o que precisa ser verdade/pronto antes]
- **[ideia]** — bloqueada por: [...]

## Princípios de sequenciamento (deste projeto)
- **Fatia vertical, não camada horizontal.** Cada item entrega valor ponta-a-ponta (UI→banco), não "só o backend". Espelha as user stories P1/P2/P3 independentes do spec-kit.
- **A primeira fatia ataca a hipótese mais arriscada** (vem do Discovery), não a mais fácil.
- **Consolidar antes de avançar.** Fatia em produção com bug não vira "Later" — vira "Now" de novo. Não empilhe sobre base instável.
- **Promoção de tier é decisão consciente.** Uma fatia T1 que precisa virar T2 ganha uma entrada própria no roadmap, não acontece por inércia.

## Onde isto pode dar errado
- Roadmap vira lista de desejos infinita. "Later" sem critério de entrada é gaveta de lixo. Cada item precisa da dependência/bloqueio explícito.
- Datas voltam disfarçadas de horizonte. Now/Next/Later é ordem, não calendário; resista a "Next = próximo mês".
- "Now" com 5 itens. Isso não é roadmap, é caos. O orquestrador é você e o gargalo é você — segure 1-2.
