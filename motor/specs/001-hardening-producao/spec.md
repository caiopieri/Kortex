# Spec — hardening de produção do motor

Status: **IN PROGRESS — see `verification.md`**
Tier: **T2**
Fonte normativa: `../../docs/INVARIANTES.md`

## Problema

O motor possui uma suíte original verde, mas não sustenta invariantes documentados sob
input hostil, falha parcial, concorrência e retomada. A evidência atual permite execução,
certificação, promoção pretendida ou decisão com contratos incompletos.

## Objetivo

Restaurar todos os invariantes A–G e fechar S4/F3 como contratos de produção, mantendo o
kernel orientado por `WorkflowSpec` e a promoção como intenção manual.

## Escopo — dentro

- Validação estrita de spec, vereditos, decisões, capacidades, custos e orçamento.
- Grafo fail-closed, tratamento de exceções e reconciliação sem propagar reprovação.
- `CommandRunner` explícito, default deny e backend de produção sandboxado.
- Eventos com schema runtime v2, append seguro, ordem e recuperação.
- Sombra imutável, evidência held-out íntegra e certificação não forjável.
- Caixa transacional e idempotente em SQLite; notas Markdown como projeção.
- Compatibilidade de leitura para specs/logs/notas existentes quando segura.

## Escopo — fora

- UI, catálogo, RAG, fine-tuning, novos providers e mudanças na topologia fixa.
- Usar custo para compensar regressão de qualidade.
- Aplicação automática de promoção.
- Declarar execução local não sandboxada como produção.

## Critérios de aceite

- [ ] Nenhum teste existente ou de auditoria é removido, desabilitado ou enfraquecido.
- [ ] H00 reconcilia 78 falhas novas, 11 controles e 22 falhas preexistentes por `nodeid`,
  hash, origem, causa e disposição humana; gate de PR considera somente arquivos rastreados.
- [ ] `pytest motor/` passa sem `xfail`; contagem não diminui por exclusão.
- [ ] Ruff, mypy, Bandit high/high, compileall, build/install e Gitleaks passam.
- [ ] Toda saída externa que decide fluxo usa modelo estrito e falha fechada.
- [ ] Comando sem runner/política/backend real aprovado pela suíte de conformidade é recusado
  antes de subprocesso; fake não satisfaz o gate de produção.
- [ ] Sandbox não lê sentinela fora do workspace, não recebe segredo do host, não usa rede por
  default, limita output combinado a 1 MiB e encerra árvore em até 2 s após timeout.
- [ ] Evento inválido não é escrito; reabertura preserva histórico e ordem.
- [ ] Certificação resolve registro imutável em repositório confiável, recomputa casos íntegros
  e ignora status/hash fornecido fora dessa autoridade.
- [ ] Sob fault injection, decisão elegível converge para `APPLIED` com um único efeito durável,
  ou `EXPIRED` sem efeito; nunca permanece `CLAIMED` após o lease.
- [ ] Gates sensíveis ignoram `auto_mode` e overrides.
- [ ] `teto_custo` é finito; chamada, retry e failover reservam custo antes de executar e
  bloqueiam custo desconhecido ou `gasto + reservado > teto`.
- [ ] K4 permanece verdadeiro: somente intenção `requer_gate=True`.

## Fronteiras

- **Entradas hostis:** spec, resposta de modelo, registro, argv, ambiente, evento, caso
  held-out, arquivo de decisão e payload de resume.
- **Saídas:** resultado tipado, evento schema v2, intenção de promoção e decisão aplicada
  com ID idempotente.
- **Persistência:** JSONL continua ledger de eventos; SQLite passa a ser ledger da Caixa.
- **Migração:** escritor só produz formato novo. Logs v1 são consulta/quarentena; specs legadas
  revalidam em v2; notas antigas não autorizam decisão sem migração auditada.
- **Dependências:** cada PR adiciona o teste causal junto da correção e respeita a sequência
  registrada em `plan.md` e `plan-h12b.md`.

## Restrições

- PR alvo menor ou igual a aproximadamente 300 linhas; teste e produção contam.
- Máximo de duas frentes ativas e arquivos sobrepostos nunca em paralelo.
- `spec.py` continua dinâmica; `grafo.py` não ganha topologia por feature.
- Sandbox é fronteira real de processo/FS/env, não apenas validação de string.
- Aplicar `dev-harness/docs/security-DoD.md` Universal, Ambiente/Autonomia e Bot/LLM.
- Nenhuma alegação `exactly-once` atravessa stores diferentes; o contrato é entrega
  at-least-once com efeito idempotente e liveness comprovada.

## Não-objetivos

- Preservar API insegura apenas para manter compatibilidade.
- Criar framework genérico de policy, event sourcing ou estatística.
- Medir sucesso pela quantidade de testes verdes em vez da causa eliminada.

## Onde isto pode dar errado

- Um backend fake/local pode tornar testes verdes sem satisfazer isolamento de produção.
- Schema estrito e state machine precisam de compatibilidade explícita para artefatos antigos.
- Política anti-Goodhart sem dataset representativo continua teatral mesmo tipada.
