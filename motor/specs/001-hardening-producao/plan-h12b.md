# Plano - H12b hard-stop de orcamento

Status: **APROVADO PELO USUARIO; EM IMPLEMENTACAO**
Data: 2026-07-12
Aprovacao da Opcao A, SQLite por run e hardening H00-H13: 2026-07-13.
Escopo de discovery: `spec.py`, `modelos.py` e `grafo.py`, lidos integralmente apos Graphify.

## Problema Causal

O contrato atual nao permite afirmar hard-stop:

- `Restricoes.teto_custo` e obrigatorio, finito, positivo e tem default `2.0` em BRL. Nao
  existe modo `None`/sem teto na spec v0.1.
- `ClienteModelo.chamar()` retorna somente `str | None`.
- Claude, Codex, OpenCode e OpenAI-compat executam retries de infraestrutura internamente.
  O roteador ve apenas o resultado agregado e depois controla fallback.
- OpenAI-compat emite tokens somente depois de sucesso. Nao existe conversao monetaria
  confiavel, custo de tentativa falha nem versao/proveniencia de preco.
- O terceiro campo do catalogo e `custo_ordem`, uma ordenacao relativa, nao limite monetario.
- O fan-out compartilha o cliente. Saldo mutavel no roteador ou no grafo misturaria jobs.
- O payload de subagente nao carrega hoje a identidade completa da run.
- `custo.tick` e telemetria de tokens; seu schema nao representa reserva, reconciliacao,
  bloqueio ou violacao de contrato monetario.

Medir depois da chamada, reservar uma vez por `chamar()` ou cobrar o maximo como se fosse
custo real nao satisfazem o contrato aprovado.

## Decisao De Persistencia

Recomendacao: SQLite dedicado por run, em caminho derivado de identidade validada, por
exemplo `runs/<run_id>/orcamento.sqlite3`.

Justificativa:

- `BEGIN IMMEDIATE` serializa reservas concorrentes entre threads e processos.
- O estado sobrevive a crash/resume; memoria local e `ContextVar` nao sobrevivem.
- Um arquivo por run impede mistura de jobs por construcao. `thread_id` continua parte da
  chave para impedir reutilizacao cruzada dentro da mesma run.
- Nao reutilizar o ledger da Caixa: custo e decisao humana possuem lifecycle e transacoes
  distintos; uni-los criaria acoplamento sem transacao distribuida com o checkpoint.
- Nao usar o checkpointer LangGraph como mutex: sua API nao oferece CAS monetario nem
  transacao que englobe a chamada externa.

Valores monetarios serao `Decimal` canonico armazenado como texto e recalculado dentro de
`BEGIN IMMEDIATE`. SQLite `REAL` fica proibido. A moeda do teto e BRL; rota faturada em outra
moeda precisa cotacao confiavel, versao, timestamp e arredondamento conservador, ou bloqueia.

## API Tipada Minima

```python
@dataclass(frozen=True)
class CotacaoTentativa:
    maximo: Decimal
    moeda: Literal["BRL"]
    pricing_version: str

@dataclass(frozen=True)
class ResultadoTentativa:
    texto: str | None
    custo_real: Decimal
    moeda: Literal["BRL"]
    usage_ref: str

class ClienteTentativaCusteada(Protocol):
    tentativas: int
    def cotar_tentativa(...) -> CotacaoTentativa: ...
    def tentar_uma_vez(...) -> ResultadoTentativa: ...

class RepositorioOrcamento(Protocol):
    def sessao(self, run_id: str, thread_id: str, teto: Decimal) -> SessaoOrcamento: ...
```

O transporte tipado executa exatamente uma tentativa e nunca faz retry oculto. O roteador
passa a controlar cada tentativa e cada fallback. Cliente sem os dois metodos ou sem cotacao
confiavel e bloqueado antes de efeito externo.

`ResultadoTentativa` nao aceita custo informado pelo modelo. O adaptador calcula custo a
partir de usage autenticado do provedor e pricing versionado. Excecao sem custo conhecido
invalida a sessao; nao libera a reserva como se a tentativa fosse gratuita.

## Modelo De Estado

Sessao:

```text
ACTIVE -> INVALIDATED
ACTIVE -> ACTIVE       (reserva/reconciliacao validas)
```

Reserva:

```text
RESERVED -> RECONCILED
RESERVED -> CONTRACT_VIOLATED
RESERVED -> UNKNOWN_COST
```

Tabelas minimas:

```text
budget_session(run_id, thread_id, teto, moeda, gasto, reservado, status, version)
budget_reservation(reservation_id, call_id, route_id, attempt, maximo, real,
                   pricing_version, status, created_at, reconciled_at)
```

Chaves e transicoes:

- `PRIMARY KEY(run_id, thread_id)` na sessao.
- `UNIQUE(run_id, thread_id, call_id, route_id, attempt)` na reserva.
- Reserva atomica exige `status=ACTIVE` e
  `gasto + reservado + novo_maximo <= teto` dentro do mesmo `BEGIN IMMEDIATE`.
- Reconciliacao exige reserva `RESERVED`, custo real finito e nao negativo, moeda igual e
  `real <= maximo`; entao subtrai o maximo reservado e soma o real gasto.
- `real > maximo` registra violacao, contabiliza o real quando valido e invalida a sessao.
- Custo ausente/NaN/infinito conserva a reserva e invalida a sessao; nenhuma nova chamada.
- `call_id` e deterministico por run, no, fase, rodada, tentativa e rota. Replay nunca cria
  duas reservas para a mesma tentativa.

O ledger limita gasto, mas nao promete exactly-once da chamada externa. Crash depois da
resposta e antes do checkpoint pode exigir reconciliacao operacional; a reserva permanece
e impede overshoot.

## Integracao No Grafo

Toda chamada passa por um unico helper orcado:

- seletor de rota;
- cada tentativa do planner;
- executor;
- verifier;
- evaluator em cada rodada de reconciliacao;
- synthesizer;
- cada retry de infraestrutura e cada fallback.

`run_id` e `thread_id` sao validados antes de abrir path/ledger e propagados aos `Send` do
fan-out. Nenhum saldo reside no objeto `ClienteRoteador` compartilhado.

Para spec fornecida pelo usuario, o teto validado abre a sessao antes de qualquer modelo.
Para missao sem spec, o planner precisa de teto de bootstrap confiavel. Proposta: usar o
default constitucional de `Restricoes`, nunca permitir que a spec gerada aumente esse teto
e adotar o menor entre teto bootstrap e teto gerado. Esta regra requer aprovacao humana.

## Eventos Necessarios - H12b0

Fatia fresh de `eventos_schema.py`/`eventos.py`, antes da logica de custo:

- `custo.reservado`: IDs de run/sessao/call/reserva, rota, tentativa, maximo, moeda,
  pricing version e totais apos reserva.
- `custo.reconciliado`: custo real, delta liberado e totais apos reconciliacao.
- `custo.bloqueado`: motivo (`sem_cotacao`, `sem_adapter`, `teto`, `sessao_invalida`) e
  snapshot dos totais sem dado secreto.
- `custo.contrato_violado`: custo real maior que maximo, moeda divergente ou custo invalido.

`custo.tick` permanece telemetria legada e nao autoriza transicao financeira. Schema v2,
AST anti-drift, painel e qualquer projecao devem reconhecer os novos tipos sem tratar tokens
como dinheiro.

## Landings

| Landing | Escopo | Limite |
|---|---|---|
| H12b0 | Eventos monetarios, schema e testes anti-drift | <=300 linhas fisicas |
| H12b1 | Tipos, SQLite por run e transicoes atomicas | <=300 linhas fisicas |
| H12b2 | Roteador de tentativa unica, retry/fallback e custo desconhecido | <=300 linhas fisicas |
| H12b3 | Sink JSONL real com `event_id` e deduplicacao duravel do relay | <=300 linhas fisicas |
| H12b4 | Adaptadores reais, pricing/FX versionado e conformidade | <=300 por adaptador |

Cada landing pousa com seus testes; nao acumular H12b0-H12b4 em um unico PR.
Integracao de callsites, identidade de run e fan-out continua como bloqueador separado; nao
foi absorvida por H12b3 nem pelos adapters H12b4.

### Evidencia H12b2c2

O relay generico publica no maximo um evento pendente por chamada e transporta `event_id`,
tipo e uma copia defensiva do payload. A chamada ao publicador ocorre fora da transacao
SQLite; o ACK so ocorre depois de seu retorno. Falha antes do ACK conserva o claim ate o
lease expirar e permite redelivery com o mesmo `event_id`, exigindo deduplicacao duravel no
consumidor. Esse contrato e at-least-once e nao promete exactly-once.

Evidencia da integracao sobre `901ce2c`: 100 testes focados H12b0-H12b2c2 e 726 testes na
suite completa. Ruff, mypy, Bandit high/high, compileall e `git diff --check` passaram.

### Contrato H12b3

`LogEventos.publicar_orcamento` consome diretamente o protocolo do relay e persiste o
`event_id` no JSONL schema-validado. Ao reabrir, o writer reconstrói o indice de dedupe do
proprio ledger: redelivery identico nao repete o append; payload ou tipo divergente falha
fechado e impede o ACK. O efeito e fsyncado antes de o relay confirmar a outbox. A entrega
entre SQLite e JSONL continua at-least-once e nao promete exactly-once entre stores.

Evidencia sobre `df1a3f4`: cadeia H12b0-H12b3 com 104 testes e suite completa com 730
testes. Ruff, mypy, Bandit high/high, compileall, diff-check e Gitleaks passaram. Producao e
testes adicionaram 159 linhas, sem integracao de callsites, adapters ou pricing.

## Testes Causais

- Chamada inicial reserva antes de o fake observar qualquer efeito.
- Sem adapter, cotacao, moeda ou custo maximo: zero chamadas externas.
- Retry de infraestrutura cria uma reserva por tentativa; tentativa anterior e reconciliada.
- Retry de conteudo reserva novamente executor e verifier.
- Fallback so executa se sua propria reserva couber; reserva inicial nao autoriza fallback.
- Barreira com duas threads e teto para uma chamada: exatamente uma reserva e uma chamada.
- Duas runs/thread IDs com mesmo teto nao compartilham gasto ou bloqueio.
- Custo real menor libera a diferenca; igual consome tudo.
- Custo real maior, ausente, booleano, NaN ou infinito invalida a sessao.
- Crash depois de `RESERVED` deixa a reserva duravel e bloqueia overshoot no restart.
- Replay do mesmo `call_id` nao duplica reserva.
- Planner bootstrap nao pode elevar o teto; spec gerada abaixo do gasto falha fechada.
- Eventos emitidos passam schema e refletem a mesma transicao SQLite.

## Gate Por Landing

- Testes causais da landing e controles H12a/S3.
- Suite original e hardening coletados juntos, sem xfail/skip novo.
- Ruff, mypy incluindo testes alterados, Bandit high/high e compileall.
- Fault injection SQLite e teste concorrente repetido em processos independentes.
- diff-check, Gitleaks, build/install e smoke de wheel no fechamento H12b4.
- Diff de producao+teste <=300 linhas fisicas por landing.
- Security DoD de input externo, autonomia e dado financeiro; `N/A` exige justificativa.

## Opcoes Para Decisao

### Opcao A - Arquitetura Completa

Executar H12b0-H12b4. Mantem o motor funcional somente para rotas com adapter, pricing e
cotacao confiaveis. E a unica opcao que fecha S4 com uso real.

### Opcao B - Default-Deny Total Sem Cost Contract

Landar apenas schema de bloqueio e guard: como toda spec v0.1 possui teto, qualquer cliente
sem adapter/cotacao/custo maximo e bloqueado antes da primeira chamada. Isso impede overshoot,
mas deixa planner e demais papeis indisponiveis ate H12b4; nao deve ser apresentado como
orcamento funcional, apenas contencao segura.

## PARADA PARA REVISAO HUMANA

Decidir antes de editar producao:

1. Opcao A ou B.
2. Aprovar SQLite dedicado por run e o modelo de estados.
3. Aprovar BRL como moeda canonica e politica de FX/pricing.
4. Aprovar teto bootstrap do planner e proibir elevacao pela spec gerada.
5. Definir quais provedores possuem usage/preco confiavel suficiente para H12b4.

## Onde isto pode dar errado

- Um `custo_maximo` subestimado permite gasto real acima da reserva; isso invalida a sessao,
  mas a violacao externa ja ocorreu. Cotacao precisa ser limite confiavel, nao media.
- Usage do provider pode chegar atrasado ou faltar em erro. Sem custo real validado, a
  reserva fica presa e exige runbook; libera-la automaticamente reabre overshoot.
- SQLite em NFS ou filesystem sem locking confiavel nao satisfaz o contrato. Deployment deve
  certificar o volume ou usar store transacional equivalente com CAS.
- Retentar uma reserva `RESERVED` sem saber se a chamada saiu pode duplicar efeito/custo.
  O plano garante teto, nao exactly-once da API externa.
- FX mutavel pode transformar uma cotacao valida em limite falso. Versao, timestamp e margem
  conservadora sao parte da evidencia.
- Opcao B e segura, mas torna o motor inutil para workflows com modelo. Nao deve ser escolhida
  para esconder a ausencia dos adaptadores reais.
