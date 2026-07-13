# Plan — hardening de produção do motor

Status: **APROVADO PARA H00/H01/H02**  
Regra: `tasks.md` e implementação ficam limitados a H00/H01/H02 nesta onda.

## Estratégia

Corrigir por causa causal, com contenção fail-closed primeiro. O pack de auditoria será
reorganizado com um manifest 1:1, nunca reduzido. Cada PR pousa verde e mede também os
controles positivos da fatia.

## DAG de PRs

| ID | Mudança | Depende | Testes que devem virar verdes |
|---|---|---|---|
| H00 | Manifest 100 falhas + 11 controles, matriz dos 24 invariantes e baseline limpo | — | Nenhum; somente rastreabilidade |
| H01 | Veredito/decisão strict + gates sensíveis manual-only | H00 | A gate bool/decisão; C G3; G F3 |
| H02 | Validadores discriminados, capacidade/custo finitos e revalidação pós-gate | H01 | A K1 config/edição; B S1/S3/S4 |
| H03 | Exceções tipadas e bloqueio de dependentes reprovados | H01,H02 | A K2/K3; C G4 |
| H04 | `CommandRunner`, default deny, identidade e argv tipado | H02,H03 | D C1/C4; controles de metacaractere |
| H05a | Contrato de sandbox externo, env/FS/rede default-deny | H04 | D C2 env/path + conformidade |
| H05b | Timeout, process group, output limitado e job com backend real | H05a | D C3 + integração real |
| H06a | Envelope de evento v2, campos reservados e validação antes do write | H01 | E envelope/tipos |
| H06b | Payloads v2 completos + tipos `curador.*` | H06a | E payload; F evento público |
| H07 | Append/lock/seq/recovery JSONL e quarentena v1 | H06b | E histórico/NaN/tempo |
| H08 | Sombra imutável e erro de runner por caso | H07 | F U1 e controle de exceção |
| H09a | Evidência held-out v2 e certificação recomputada | H08 | F U2 |
| H09b | Repositório confiável, promoção vinculada e regressão K4 | H09a | F U3; controle K4 |
| H10a | Caixa: IDs, decisões, paths, notas e deadline | H01 | G validação/path/nota/timeout |
| H10b | Ledger SQLite + outbox transacional + lease de claim | H10a | G base de crash/concorrência |
| H11 | Consumer at-least-once, dedupe no estado e resume idempotente | H10b | G concorrência/crash/resume |
| H12a | Roteamento runtime por capacidade S3 | H02,H07 | B capacidade + novos testes runtime |
| H12b | Reserva e hard-stop de orçamento S4 | H02,H07 | B teto + retry/failover runtime |
| H13 | Atualizar invariantes, ADRs, runbooks e roadmap; Gate completo | H03,H05b,H07,H09b,H11,H12a,H12b | `pytest motor/` e CI completos |

## Ondas de execução

1. **Onda 0:** H00 -> H01 -> H02; ambos tocam `grafo.py` e são deliberadamente sequenciais.
2. **Onda 1:** H03, H06a e H10a; dependências da tabela são obrigatórias.
3. **Onda 2:** H04, H06b e H10b; no máximo duas frentes.
4. **Onda 3:** H05a -> H05b; H07 -> H08 -> H09a -> H09b; H11 após H10b.
5. **Onda 4:** H12a/H12b após H07; depois H13.

## Contratos de implementação

- **Fail-closed:** erro de parse, policy ausente, decisão desconhecida ou estado ambíguo bloqueia.
- **Comando:** spec escolhe ferramenta lógica; policy confiável escolhe runner/argv. Payload
  externo nunca escolhe executável ou flag estrutural.
- **Eventos:** validação ocorre antes do write; `evento`, `seq` e timestamps são reservados.
- **Curador:** certificação deriva dos casos persistidos, não de agregados recebidos.
- **Caixa:** ledger+outbox transacionam juntos; entrega é at-least-once e o estado deduplica
  `decision_id`. `CLAIMED` tem lease e converge para `APPLIED|EXPIRED`.
- **Compatibilidade:** legado é classificado por artefato; leitura nunca restaura autoridade.

## Gate por PR

- Testes causais da fatia + suíte original.
- Controles positivos da auditoria permanecem verdes.
- Ruff, mypy, Bandit high/high, compileall, build/install e Gitleaks.
- Security-DoD Universal em todo PR de lógica; Bot/LLM nas fronteiras externas e
  Ambiente/Autonomia em H04-H05b. `N/A` exige justificativa registrada.
- Diff de produção + teste menor ou igual a aproximadamente 300 linhas; se exceder, dividir.
- Nenhum `xfail`, skip, relaxamento de assertion ou exclusão de coleta.

## Rollback

- H01/H02/H03: reverter por versão de contrato, nunca voltar a parse permissivo.
- H04/H05a/H05b: rollback deixa comando negado; não reativa runner local inseguro.
- H06a/H06b/H07: writer volta somente para modo read-only; logs existentes não são truncados.
- H09a/H09b: promoção fica vetada; K4 permanece inerte.
- H10a/H10b/H11: ledger entra read-only e notas não são consumidas até recuperação explícita.

## Matriz de ownership dos invariantes

| IDs | Owner de correção/regressão |
|---|---|
| K1 | H02 |
| K2 | H03,H06a |
| K3 | H01,H03 |
| K4 | H09b |
| S1,S2 | H02 |
| S3 | H02,H12a |
| S4 | H02,H12b |
| G1,G2 | H03 |
| G3 | H01,H03 |
| G4 | H03 |
| C1,C4 | H04 |
| C2 | H05a,H05b |
| C3 | H05b |
| E1 | H06a,H06b |
| E2 | H07 |
| U1 | H08 |
| U2 | H09a |
| U3 | H09b |
| F1 | H10b,H11 |
| F2 | H10a,H10b,H11 |
| F3 | H01 |

## Critério de conclusão

- Todos os invariantes K1–F3 têm teste adversarial e status sustentado.
- Pack completo e suíte original passam juntos.
- Roadmap deixa de declarar componentes falsamente fechados.
- Runbook de operação cobre sandbox indisponível, log corrompido, replay e veto do curador.

## Aprovação do plano

- Status: **APROVADO**
- Aprovador: Caio Amaral de Pieri (aprovação explícita em chat)
- Data: 2026-07-11
- Revisão/hash aprovado: `bundle-sha256:987253c388b739fa2271f94803f9a1803953e019cd8e7a4e96bc53147e09b8c1`
  (fingerprint do pacote antes dos metadados administrativos de aprovação)
- Regra: qualquer mudança em `discovery.md`, `clarifications.md`, `spec.md` ou `plan.md`
  restaura este bloco para **PENDENTE** e exige nova revisão.

## PARADA PARA REVISÃO HUMANA

Revisar principalmente: default-deny do comando, JSONL v1 em quarentena, outbox+idempotência
da Caixa, repositório confiável do curador, política held-out e ordem H01–H13. Após aprovação,
gerar `tasks.md` apenas para H00/H01/H02; não expandir todas as ondas de uma vez.

## Onde isto pode dar errado

- H04/H05a/H05b podem parecer uma correção única; separar policy de sandbox evita PR grande e
  deixa claro que validação não é confinamento.
- H10b/H11 exigem fault injection; mocks felizes não provam segurança nem liveness.
- Pousar todos os testes antes das correções quebraria CI; pousar sem manifest perderia evidência.
