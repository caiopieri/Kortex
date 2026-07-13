# Práticas operacionais com IA

> Práticas do lado **humano** de operar o harness — como pedir, como acompanhar, como padronizar pra
> automatizar. Fonte: artigos do Fabio Akita (2026), **avaliadas contra o nosso contexto**, não acatadas
> por autoridade. O que foi rejeitado (e por quê) está no fim — de propósito.
>
> Complementa o `project-template/AGENTS.md` (que instrui o *agente*); aqui é como o *operador* trabalha.

---

## 1. Como pedir — o template de 4 blocos

A qualidade da entrega é proporcional ao esforço de pedir. Toda tarefa não-trivial se beneficia de
estruturar o pedido em quatro blocos — e o terceiro é o que mais falta na prática:

1. **Objetivo** — o que se quer, claro e verificável.
2. **Método** — como abordar (quando você já tem opinião). Se não tiver, *peça a melhor abordagem* em vez
   de prescrever — depois que o contexto está sólido, perguntar rende mais que mandar.
3. **O que NÃO fazer** — restrições e suposições não-ditas. É o bloco de maior alavancagem e o mais
   esquecido ("nunca deduplicar por nome de arquivo, só por sha1+tamanho"). Operacionaliza o contrato
   anti-bajulação e o security-DoD dentro do próprio pedido.
4. **Critério de validação** — como medir que ficou pronto (espelha o DoD).

Duas práticas que andam junto:
- **Despeje o contexto na frente.** Conhecimento de domínio, restrições de stack, falhas passadas — o
  modelo não osmose o que está só na tua cabeça.
- **Não saia da sala.** Em tarefa longa, acompanhe e ajuste em tempo real; o agente nunca diz "não" —
  você é o freio. (No motor, isso é o gate do fundador; no chat, é presença.)

## 2. Padronização que destrava automação (T1+)

Quando um projeto chega a T1/produção, padronizar a operação entre projetos permite que o agente (e, no
futuro, o motor) execute deploy/release com confiança — "solta a release" só funciona se a estrutura for
previsível. Convenção:

- **`bin/deploy`** idêntico em todo projeto (build → push → subir). Um comando, mesmo nome, sempre.
- **Release por tag** — tag semântica dispara build, empacotamento e publicação.
- Segredos fora do repo (`config/deploy.env`, com `.example` versionado).

Escopo honesto: isto é para projeto que **vai a produção**. Spike/T0 não precisa — montar isto num
descartável custa mais do que economiza (imposto de complexidade).

## 3. O que avaliamos e deliberadamente NÃO adotamos

Registro proposital, pra não reabrir o que já foi decidido:

- **CI por commit como novidade** — já coberto. A Fase 4 (passo 1) define pre-commit local (feedback
  rápido) + CI no push que bloqueia merge. Não há o que adicionar.
- **"CLAUDE.md vivo / common hurdles" como prática nova** — já existe no `project-template/AGENTS.md`,
  seção `[FRIO] Memória recuperável` ("um doc por subsistema... registrando decisões e modos de falha
  conhecidos"). Adicionar seria duplicar.
- **"TDD é mais importante com IA" como regra nova** — o DoD já exige teste. A evidência do Akita (ratio
  ~1,5x teste:código, mais commits/dia com rede de segurança) é *justificativa* do que já fazemos, não
  uma regra a acrescentar.

---
*Fonte avaliada: Akita on Rails — "Como falar com o Claude Code efetivamente", "Boas práticas de projetos
open source com LLM", "Do zero à pós-produção em 1 semana" (2026). Adotado o que passou no nosso contexto.*
