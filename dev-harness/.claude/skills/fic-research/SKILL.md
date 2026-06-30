---
name: fic-research
description: Fase 1 do fluxo FIC. Use no início de qualquer tarefa não-trivial, antes de planejar ou codar. Entende o código relevante, o fluxo de dados e as restrições, e produz um research.md compactado. Não escreve código de produção.
model: opus
---

# fic-research — Entender antes de planejar

Você está na **fase de pesquisa**. Objetivo: entender o suficiente do código e do problema para que um plano correto seja possível. **Não escreva código de produção nesta fase.**

## O que fazer
1. Localize os arquivos relevantes ao problema. Mapeie como a informação flui entre eles (quem chama quem, onde o dado entra e sai).
2. Identifique os padrões e convenções já usados no repo para coisas parecidas. O novo trabalho deve imitá-los, não inventar.
3. Levante restrições: arquitetura, segurança, dependências, contratos de API existentes.
4. Liste o que ainda é **incerto ou ambíguo** — o que, se eu interpretar errado, custaria caro depois.

## O que produzir
Salve em `docs/specs/<feature>/research.md` (mesma pasta da spec). **Compactado (~200 linhas, alvo)**, com:
- **Problema** em uma frase.
- **Arquivos e fluxo** relevantes (caminho + papel de cada um).
- **Padrões a seguir** (com exemplo de onde já existem no repo).
- **Restrições** (incluindo segurança, se toca banco/auth/input externo).
- **Perguntas em aberto / riscos de interpretação.**

## Regras
- Compacte. Distile o que descobriu; não cole histórico bruto de busca.
- Se uma ambiguidade for cara, **pare e pergunte** em vez de assumir.
- Termine com: `### Onde isto pode dar errado` — o que você ainda não entende e poderia derrubar o plano.
