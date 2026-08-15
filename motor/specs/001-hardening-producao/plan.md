# Plano consolidado de hardening

Status: **H00-H13 executados; fechamento global bloqueado**

Este documento preserva a ordem causal do programa de hardening. O estado verificável de
cada frente está em `verification.md`; o detalhamento de orçamento está em `plan-h12b.md`.

## Sequência causal

| Faixa | Contrato | Estado |
|---|---|---|
| H00-H03 | Corpus, tipos estritos, validação de spec e falha parcial | Implementado |
| H04-H05a | Identidade de comando, argv e contrato de sandbox | Implementado |
| H05b | Backend de sandbox real certificado | Bloqueado |
| H06-H07 | Schema de eventos, append, recovery e projeção | Implementado |
| H08-H09 | Sombra imutável, certificação e promoção como intenção | Implementado |
| H10-H11 | Caixa durável, outbox, concorrência e retomada | Implementado |
| H12a | Roteamento runtime por capacidade | Implementado |
| H12b | Reserva e hard-stop de orçamento ponta a ponta | Em andamento |
| H13 | Documentação e gate final | Parcial, depende dos bloqueadores |

## Contratos permanentes

- Erro de parse, policy ausente, decisão desconhecida ou estado ambíguo falha fechado.
- A spec escolhe ferramenta lógica; policy confiável escolhe runner, executável e argv.
- Eventos são validados antes do write e preservam envelope reservado.
- Certificação deriva de casos persistidos; custo não compensa regressão de qualidade.
- Promoção é intenção sujeita a autoridade externa, nunca aplicação automática.
- Ledger e outbox transacionam juntos; entrega entre stores é at-least-once com deduplicação.
- PRs de lógica incluem teste causal, suíte, lint, tipos, SAST, build e scan de segredos.

## Próximas etapas

1. Concluir o relay de orçamento e integrar reservas a todas as chamadas, retries e fallbacks.
2. Fornecer adapters confiáveis de uso/preço e reconciliação.
3. Implementar e certificar um backend de sandbox conforme `sandbox-conformance.md`.
4. Rodar o gate completo e atualizar `verification.md` sem alegar produção antes disso.

## Rollback

- Regressão em comando deixa o runner em default-deny.
- Regressão em eventos deixa o writer read-only; histórico nunca é truncado.
- Regressão no curador veta promoção; K4 permanece inerte.
- Regressão na Caixa preserva ledger e suspende consumo até recuperação explícita.
- Custo desconhecido bloqueia a chamada; não é estimado de forma otimista.

## Onde isto pode dar errado

- Default-deny pode esconder capacidade ausente se for descrito como sandbox funcional.
- Usage tardio ou incompleto pode manter reserva presa; liberar automaticamente reabre overshoot.
- At-least-once sem deduplicação durável pode repetir efeito externo.
- Atualizar somente este plano, sem evidência em `verification.md`, cria certificação documental.
