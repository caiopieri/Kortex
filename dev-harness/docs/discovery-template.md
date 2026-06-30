# Discovery — [nome da ideia]

> A fase de "tirar do papel". Vem **antes** de `/speckit.specify`.
> Objetivo: transformar "tô pensando em fazer isso, isso e aquilo" em um problema moldado,
> com tier decidido e a primeira fatia escolhida. Curto de propósito — se passar de uma página,
> você está planejando, não descobrindo.
>
> A função da IA aqui é **desafiar a ideia contra o problema**, não montar o que você pediu.
> (Anti-bajulação: o bloco de risco no fim é obrigatório.)

## 1. A dor real
Que dor concreta isto resolve, e de quem? (1-3 frases. Se não consegue escrever, ainda não entendeu — pare aqui e converse mais.)

## 2. A hipótese mais arriscada
Qual a suposição que, se for falsa, mata o projeto inteiro? (Ex.: "usuários querem X", "dá pra fazer Y com a stack Z", "o custo de A cabe no orçamento".) Só uma — a mais letal.

## 3. O menor teste
Qual a **menor coisa** que valida ou mata essa hipótese? É daqui que sai a primeira fatia do roadmap. (Não é "o MVP inteiro" — é o experimento mínimo.)

## 4. O tier — define quanto processo roda
> Marque um. O tier liga/desliga o resto do harness. Subestimar tier = dívida garantida.

- [ ] **T0 — Spike.** Validar hipótese técnica. Descartável. Só roda; sem spec/gate/teste.
- [ ] **T1 — MVP.** Validar o *problema* com usuário real. Discovery + spec-lite + segurança inegociável (RLS, segredos, autorização) + teste só no caminho crítico + deploy simples. **Sem** NFR pesado, observabilidade ou SLO.
- [ ] **T2 — Produção/Escala.** Aguentar usuário de verdade. Fluxo completo + ciclo de vida da Fase 4 (gate CI, pirâmide de testes, NFR, observabilidade, postmortem).

## 5. Fora do escopo (explícito)
O que esta ideia deliberadamente **não** tenta fazer agora. (Evita inflar o primeiro passo.)

## Ponte para o spec-kit
Quando os 5 itens estiverem claros:
1. Adicione/atualize a fatia escolhida no `ROADMAP.md` do projeto (Now/Next/Later).
2. Rode `/speckit.specify` descrevendo **a fatia** (o quê e porquê — sem stack).
3. Rode `/speckit.clarify` para fechar os vãos antes do `/speckit.plan`.

## Onde isto pode dar errado
- Discovery vira PRD gigante. Se está detalhando solução, parou de descobrir. Volte ao problema.
- Tier inflado "por garantia" → overhead que mata a velocidade do MVP. Tier de menos → dívida. É julgamento; reveja se a fatia crescer.
- A hipótese mais arriscada é confortável demais. Se ela não dá medo, provavelmente não é a mais arriscada.
