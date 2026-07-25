# Clarify — decisões travadas para o hardening

| Questão | Decisão | Consequência |
|---|---|---|
| O motor executa comando local por default? | Não. `CommandRunner` default nega. Runner local existe apenas em teste/dev explicitamente habilitado e nunca qualifica produção. | Compatibilidade insegura é quebrada de forma explícita. |
| Quem prova o sandbox de produção? | O motor recebe um runner externo por composição. Sem backend real aprovado pela suíte de conformidade, `kind:"comando"` permanece indisponível em produção; um marker ou fake não certifica. | O pacote pode ser promovido em default-deny, mas a capacidade de comando só é ativada por deployment certificado. |
| Como preservar testes positivos de comando? | Fixture injeta runner fake sem mudar asserções; testes de contrato não são usados como prova do sandbox real. | Teste unitário prova o protocolo, e job de integração prova a fronteira real. |
| Quais limites mínimos o runner impõe? | Workspace é o único mount RW; imagem/base é RO; rede e herança de env ficam desligadas; output combinado máximo de 1 MiB; timeout entre 1 e 300 s; TERM seguido de KILL após 2 s. | C2/C3 tornam-se critérios falsificáveis; limite diferente exige nova versão de policy. |
| JSONL continua fonte de verdade? | Sim, um writer por run, append/lock, `seq` persistente e schema v2. | Writer nunca produz v1; leitura legada é somente consulta/quarentena. |
| Como tratar artefatos v1? | Logs v1 são read-only e não autorizam replay/promoção; specs legadas passam validação v2 e comando fica negado sem policy; notas antigas são projeções, nunca decisões aplicáveis sem migração auditada. | Compatibilidade não restaura autoridade insegura. |
| SQLite substitui notas da Caixa? | SQLite é ledger; notas são projeção humana atômica. Ledger e outbox compartilham transação; checkpoint LangGraph permanece separado. | Não se promete transação distribuída inexistente. |
| Qual garantia a Caixa oferece? | Entrega ao resume é at-least-once; `decision_id` persistido no estado torna o efeito idempotente. `CLAIMED` usa lease recuperável e só vira `APPLIED` após o checkpoint refletir o ID; caso contrário termina `EXPIRED` sem efeito. | Segurança e vivacidade são ambas testadas sob fault injection. |
| Qual é o mínimo held-out? | A política declara `min_casos`; ausência bloqueia certificação de produção. IDs únicos e split/proveniência são obrigatórios ou derivados e selados na ingestão. | Não existe número universal escondido no código. |
| Custo pode compensar qualidade? | Nunca. Qualidade/rubricas são hard gate; custo só é avaliado depois. | Mantém anti-Goodhart e ADR-003. |
| Promoção aceita dict certificado? | Não. Resolve `certification_id` em repositório confiável default-deny; o registro imutável contém casos crus, policy e hash, e a decisão é recomputada antes da intenção. Export JSON/CLI é não autoritativo. | `status="certificado"` ou hash fornecido isoladamente não têm autoridade. |
| Gate sensível pode ter override? | Não. `promocao`, autorização, risco e dinheiro são manual-only. | `auto_mode` não alcança esses gates. |
| Como pousar testes hoje não rastreados? | H00 inventaria 78 falhas novas, 11 controles e 22 falhas preexistentes por `nodeid`, hash e origem. Cada caso só é coletado no mesmo PR da correção causal; duplicata exige disposição humana registrada. | Nenhum PR intermediário nasce vermelho e nenhum caso some silenciosamente. |
| S3 runtime entra no programa? | Sim, `modelos.py` entra apenas para roteamento por capacidade e S4 hard-stop. | Fecha a limitação da auditoria sem ampliar para providers. |
| Como o teto impede overshoot? | Cada rota declara custo máximo confiável. Antes de chamada/retry/failover, o motor reserva custo e só executa quando `gasto + reservado <= teto`; custo desconhecido bloqueia quando há teto. Depois reconcilia reserva com custo real e emite evento. | Medir depois da chamada não é chamado de hard-stop. |

## Onde isto pode dar errado

- “Runner injetado” não pode virar escape para produção sem certificado/config explícita.
- Hash/proveniência identifica evidência; não prova por si só que o dataset é bom.
- At-least-once exige que todo consumidor de decisão mantenha deduplicação por `decision_id`.
