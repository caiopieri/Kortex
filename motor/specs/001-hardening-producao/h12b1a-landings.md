# Landings H12b1a

- **H12b1a1 — core:** tipos, path seguro, schema, sessao e reserva `RESERVED` (212 linhas de producao+teste).
- **H12b1a2 — hardening:** 83 linhas adicionais de producao + 181 de teste adversarial;
  contexto Decimal, canonizacao limitada, DB adversarial, symlink, hardlink e erros SQLite (264 linhas).

H12b1b continua reservado para reconciliacao, invalidacao, crash e multiprocesso.

## H12b1b

43 linhas adicionais de produção + 79 de testes (122 linhas): transições SQLite, replay,
crash, isolamento e concorrência. Eventos não são publicados nesta fase, portanto não há
outbox a tornar atômica antes de H12b2. Risco residual: SQLite depende de locking confiável
e não garante exactly-once da chamada externa.

## H12b1b2

Migração transacional, identidade integral e replay concorrente: 42 linhas de produção +
224 de review (266, <=300), sem outbox antes de H12b2.

## H12b2a1

Reserva exclusiva (`NOVA`, `REPLAY_AMBIGUO`, `BLOQUEADA`) e outbox na mesma transacao
SQLite: aproximadamente 107 linhas de producao + 92 de testes focados (199, <=300).

## H12b2a2

Red-team da consistencia estado/outbox: aproximadamente 45 linhas de producao + 218 de
testes adversariais (263, <=300). Colisao divergente agora causa rollback; leitura e escrita
validam integridade do `event_id` e o schema H12b0. Gate independente: 63 testes, Ruff,
mypy, Bandit high/high, compileall e `git diff --check` verdes.

Relay/claim/ack nao pertence a H12b2a. Ate essa fatia posterior, a outbox e duravel e
consultavel, mas nao entrega eventos externamente.

## H12b2b1

Protocolo fake-only e helper de tentativa unica: 89 linhas de producao + 93 de testes
(182, <=300). A reserva `NOVA` e commitada antes do unico efeito; falta de adapter/cotacao,
replay e teto produzem zero chamadas. Resultado conhecido reconcilia mesmo com texto nulo;
resultado desconhecido invalida sem retry ou fallback automatico.

## H12b2b2

Hardening adversarial da fronteira dinamica: 28 linhas de producao + 165 de review
(193, <=300). Cotacao e resultado sao revalidados depois da construcao, descriptors hostis
nao vazam erro bruto, identidade invalida vira erro de dominio e replay terminal identico
converge como `REPLAY_FINALIZADO` sem novo efeito. Gate independente da cadeia: 77 testes,
Ruff, mypy, Bandit high/high, compileall e `git diff --check` verdes.

O helper ainda nao integra `ClienteRoteador`, adapters reais ou callsites do grafo. Cada
retry/fallback deve receber identidade distinta em H12b3. Relay/ack continua pendente.

## H12b2c1a

Maquina de estado da entrega (`PENDING`, `CLAIMED`, `ACKED`) em tabela companheira, sem
alterar a ABI de quatro colunas de `budget_outbox`: 77 linhas de producao + 75 de testes
(152, <=300). Claim usa `BEGIN IMMEDIATE`, lease e tempo explicitos; confirmacao usa CAS por
owner. Concorrencia foi exercitada em threads e processos.

## H12b2c1b

Red-team de migracao read-only, overflow, fault injection, corrida de owner, corrupcao e
cardinalidade fisica: 9 linhas de producao + 225 de review (234, <=300). O review excedeu em
cinco linhas o alvo operacional de 220, sem exceder o gate constitucional de 300. Gate da
cadeia: 88 testes; apos ajuste apenas de tipagem no teste, 11 testes H12b2c1 passaram. Ruff,
mypy, Bandit high/high, compileall e `git diff --check` verdes.

H12b2c1 nao chama publicador. Crash apos publicacao e antes de ack continuara produzindo
duplicata at-least-once; H12b2c2 deve definir o relay e transportar `event_id` ao consumidor.

## H12b2c2

Relay generico publica no maximo um evento por chamada, fora da transacao SQLite, e entrega
`event_id`, tipo e copia defensiva do payload. ACK ocorre apenas depois do retorno do
publicador; falha deixa o claim ate o lease expirar e permite redelivery com o mesmo ID para
deduplicacao pelo consumidor. Sao 26 linhas de producao + 255 de testes (281, <=300).

Gate focado: 12 testes; cadeia H12b0-H12b2c2: 100 testes. Ruff, mypy, Bandit high/high,
compileall e `git diff --check` verdes. A suite ampla teve 724 passes e uma falha preexistente
fora da fatia no manifesto H00, que ainda exige regressao substituta do oraculo K2.
