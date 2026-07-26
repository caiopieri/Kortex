# Painel do Kortex — app React

A interface própria da meta-fábrica. Cada tela é uma **view fina** sobre o contrato de dados
exposto por `../painel.py` (`/dados/*`). O log é a fonte da verdade; a tela só lê.

O plano de implementação e a ordem dos tiers estão em [`../PLANO-PAINEL.md`](../PLANO-PAINEL.md).

## Rodar

```bash
npm ci          # NÃO use `npm install` — ver abaixo
npm run dev     # desenvolvimento com HMR
npm run build   # build de produção -> dist/
npm run lint    # oxlint
```

O `painel.py` precisa estar no ar para as telas terem dado:

```bash
cd .. && python3 painel.py
```

## Por que `npm ci` e não `npm install`

`npm install` **reescreve o `package-lock.json`**: ao reinstalar do zero, ele resolveu
dependências opcionais de outra arquitetura e sujou o lock com 23 linhas que ninguém pediu.
`npm ci` instala exatamente o que está versionado e **falha** em vez de reescrever — que é o
comportamento certo para algo que se quer reproduzível.

Mesma lógica do `select` explícito do ruff em `../../pyproject.toml`: ferramenta de gate não
pode mudar de resultado dependendo do que o resolvedor escolheu naquele dia.

## Contrato de dados

As telas consomem `/dados/*` do `painel.py`. Rota `/dados/` desconhecida responde **404** de
propósito — antes caía no fallback estático e devolvia `index.html` com status 200, o que fazia
o `res.json()` estourar parseando HTML, com um erro que não dizia nada sobre a causa real
(normalmente um painel no ar mais velho que o código).

Se uma tela precisar de dado que o contrato não expõe: **não invente e não mocke**. Estado vazio
honesto, e o endpoint entra em `painel.py` primeiro.
