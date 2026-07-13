# Arquitetura da superfície MCP

O servidor MCP é uma camada fina sobre `GerenciadorJobs` e o grafo. Ele expõe execução e
estado tipados sem transferir autoridade organizacional para o motor.

## Fronteira

- O **host** interpreta intenção, autentica o chamador, classifica risco e decide se solicita
  uma resposta humana.
- O **servidor MCP** valida entrada, despacha jobs, expõe status e transporta decisões.
- O **motor** executa a `WorkflowSpec`, persiste eventos e pausa em gates.
- O **runner externo** é a única fronteira autorizada para comandos; o default é negar.

Conteúdo produzido por modelos é dado não confiável. Ele nunca vira instrução para o host,
decisão de permissão ou argumento estrutural de comando sem validação determinística.

## Superfície

### `metafabrica.despachar_missao`

Recebe objetivo e restrições validadas, inicia uma execução durável e retorna imediatamente
`{job_id, estado}`.

### `metafabrica.status_missao`

Retorna `em_execucao`, `gate_pendente`, `concluido` ou `erro`. Gates carregam payload cru e
`decision_id`; resultados carregam referências de artefatos, nunca blobs arbitrários.

### `metafabrica.responder_gate`

Transporta uma decisão externa para `Command(resume=...)`. Reenvio idêntico é idempotente;
ID ou conteúdo divergente falha fechado. Gates sensíveis não são auto-resolvidos.

### Projeções read-only

`resumo_missao` e `eventos_missao` derivam projeções limitadas do estado e do ledger. Elas
não alteram a execução nem substituem o evento autoritativo.

## Execução durável

- `thread_id` fornecido pelo chamador é a chave de correlação; ausência gera UUID.
- O checkpointer permite retomar o grafo, mas não substitui o ledger de eventos.
- Outbox com claim, lease e ack fecha perda após crash.
- Entrega entre stores é at-least-once; consumidores deduplicam por `decision_id`/`event_id`.
- O chamador deve fechar explicitamente o `GerenciadorJobs`.

## Segurança

| Fronteira | Regra |
|---|---|
| Credenciais | Injetadas pelo host; nunca persistidas pelo motor |
| Input MCP | Schema estrito, limites de tamanho e IDs validados |
| Output de modelo | Tratado como dado hostil |
| Gates | Autoridade permanece fora do modelo e do motor |
| Comandos | `DenyCommandRunner` até existir sandbox certificado |
| Orçamento | Reserva antes da chamada; custo desconhecido bloqueia |

O contrato de sandbox está em `../specs/001-hardening-producao/sandbox-conformance.md`.
O estado de produção está em `../specs/001-hardening-producao/verification.md`.

## Onde isto pode dar errado

- Um host pode ignorar a classificação de risco; gates sensíveis mantêm defesa local mínima.
- Checkpoint e ledger podem divergir após crash; reconciliação precisa ser idempotente.
- Descrições MCP vagas podem rotear tarefas erradas mesmo com implementação segura.
- Default-deny contém a ausência de sandbox, mas não prova C2/C3.
