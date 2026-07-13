# Discovery — hardening de produção do motor

## 1. A dor real

A auditoria A–G encontrou 78 contraexemplos para invariantes que o roadmap tratava como
fechados. O motor não pode ser promovido enquanto entradas hostis, falhas parciais,
concorrência e crash-resume puderem atravessar gates ou corromper a evidência.

## 2. A hipótese mais arriscada

É possível eliminar as famílias causais mapeadas pela auditoria sem reescrever o kernel,
sem automatizar promoção e sem quebrar specs válidas que não dependam de comportamento
inseguro. A matriz H00 deve provar essa decomposição para os 24 invariantes, em vez de
presumir uma contagem de causas.

## 3. O menor teste

Primeiro pouso: H00 inventaria 100 falhas observadas e 11 controles sem coletar testes
vermelhos no CI. A primeira onda de implementação, H01/H02, fecha contratos fail-closed para
`aprovado`, decisões, configuração de validador, capacidade e custo, mantendo os 333 testes
originais verdes.

## 4. O tier

- [x] **T2 — Produção/Escala.** Gate completo, segurança, migração compatível,
  observabilidade e recuperação pós-crash são parte do aceite.

## 5. Fora do escopo

- Interface/P0, catálogo de workflows e novas capacidades de produto.
- Troca de LangGraph, provedores ou topologia fixa do kernel.
- Otimizações de custo que não sejam o hard-stop já prometido por S4.
- Alterar K4: promoção continua sendo intenção com gate humano.

## Ponte para o spec-kit

- Auditoria: `docs/auditoria/ACHADOS-GPT5-CODEX.md`.
- Spec: `spec.md`.
- Decisões fechadas: `clarifications.md`.
- Plano para revisão humana: `plan.md`.

## Onde isto pode dar errado

- Tratar os 78 testes como 78 tarefas gera patches locais sem fechar as fronteiras.
- Compatibilidade não pode significar preservar comportamento inseguro; nesses casos o
  fallback é negar e exigir configuração explícita.
