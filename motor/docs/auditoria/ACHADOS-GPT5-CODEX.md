# ACHADOS — auditoria defensiva do motor

Data: 2026-07-10  
Auditor coordenador: GPT-5 Codex  
Escopo: invariantes A–G de `docs/INVARIANTES.md`

## Veredito executivo

**BLOQUEADO PARA PRODUÇÃO.** O núcleo rastreado continua com a suíte original verde, mas
78 contraexemplos novos demonstram que promessas centrais falham em entradas hostis,
erros parciais, concorrência e retomada pós-crash. Não houve correção de produção nesta
auditoria.

Os bloqueadores mais graves são:

1. o executor de comando não fixa a identidade do binário autorizado e permite bypass por
   `PATH`, caminho alternativo e symlink;
2. gates de qualidade aceitam valores truthy como `"false"` e decisões desconhecidas falham
   abertas;
3. o curador certifica agregados forjados/incomparáveis e a promoção confia apenas no status;
4. a caixa perde idempotência e isolamento sob crash, concorrência e IDs hostis;
5. o log auditável aceita eventos fora do schema, envelope forjado e truncamento do histórico.

## Método e baseline

- O Graphify foi consultado em cada fatia. O índice localizou documentos, mas não ofereceu
  arestas de código confiáveis para vários símbolos; foi usado somente como mapa.
- Cada auditor leu `INVARIANTES.md` integralmente e apenas os 1–3 arquivos de produção da
  fatia. Testes e relatórios preexistentes foram excluídos do julgamento inicial.
- Baseline rastreado, Python 3.11: **333 testes passaram**.
- Gate baseline: Ruff, mypy, Bandit high/high, compileall, build+install e Gitleaks
  (**106 commits**) passaram.
- O worktree já continha `tests/test_auditoria_codex.py` não rastreado, com
  **22 falhas / 333 passes**. Ele não foi lido nem usado como evidência.

## Achados priorizados

### Críticos

#### 1. C1/C4 — allowlist não autoriza uma identidade de executável

O código reduz permissões a basename e depois resolve novamente pelo ambiente. Um binário
homônimo em `PATH`, um caminho absoluto alternativo ou um symlink passa. Lista ausente/vazia
também falha aberta. Para interpretadores permitidos, placeholder controla opções reais como
`-c`; metacaracteres (`;`, `&&`, aspas) permanecem literais e **não** são shell injection.

- Produção: `motor/grafo.py:351-355`, `motor/grafo.py:600-625`;
  `motor/registro.py:192-204`.
- Testes: `tests/test_auditoria_gpt5_d.py:56`, `:83`, `:175`; controles negativos em `:197`.
- Impacto: execução de código fora da ferramenta pretendida quando spec, registro ou `PATH`
  forem controláveis.
- Correção indicada: resolver e fixar identidade/caminho confiável antes da execução, falhar
  fechado sem política e modelar argumentos permitidos por ferramenta.

#### 2. K3 — gates de qualidade falham abertos

Verifier, evaluator e ferramenta tratam `{"aprovado": "false"}` como aprovado. Saída
reprovada ainda entra em `concluidos`, cruza arestas e alimenta dependentes. Depois do teto de
reconciliação, qualquer decisão diferente de aborto vira `prosseguir_parcial`.

- Produção: `motor/grafo.py:560-564`, `:693-698`, `:799-814`, `:852`, `:949-968`.
- Testes: `tests/test_auditoria_gpt5_a.py:107`, `:132`, `:150`;
  `tests/test_auditoria_gpt5_c.py:81`.
- Impacto: regressões e artefatos reprovados alcançam síntese e nós dependentes.
- Correção indicada: schema estrito com booleano real e enum fechado de decisões, sempre
  fail-closed.

#### 3. U2/U3 — certificação e intenção de promoção podem ser forjadas

`certificar_sombra` confia em agregados fornecidos, sem recomputar casos ou exigir amostra,
unicidade e proveniência. Aceita tipos/domínios hostis, custos parciais e valores não finitos.
`preparar_promocao_gated` confia somente em `status="certificado"`.

- Produção: `motor/curador.py:229-314`, `:345-376`, `:411-432`.
- Testes: `tests/test_auditoria_gpt5_f.py:119`, `:138`, `:149`, `:174`, `:185`,
  `:207`, `:218`.
- Impacto: uma métrica barata ou evidência fabricada recebe selo de qualidade e chega ao gate
  humano com falsa legitimidade.
- Correção indicada: recomputar certificação de casos imutáveis/provenientes e validar tipos,
  finitude, completude, unicidade e amostra mínima.

### Altos

#### 4. F1/F2 — caixa não é idempotente nem confinada sob crash/concorrência

Texto externo responde gate, decisões fora do domínio são aceitas, nota parcial é consumida,
IDs escapam o diretório, arquivos colidem no mesmo segundo e duas esperas/interrupts concorrem.
Há janelas em que a decisão existe no arquivo mas se perde no checkpoint, e o resume reaplica
entrada.

- Produção: `motor/caixa.py:28`, `:47-79`, `:90-118`, `:101-143`.
- Testes: `tests/test_auditoria_gpt5_g.py:59`, `:67`, `:75`, `:83`, `:112`, `:127`,
  `:145`, `:163`, `:181`.
- Impacto: decisão humana pode ser duplicada, perdida, trocada ou escrita fora da caixa.
- Correção indicada: validar IDs/decisões, usar protocolo transacional idempotente e lock/claim
  atômico ligado ao checkpoint/thread.

#### 5. K2/G4 — exceção de modelo derruba o grafo sem resultado reprovado

Exceções do executor e verifier escapam antes de `executor.erro`; somente retorno vazio é
normalizado.

- Produção: `motor/grafo.py:533-560`.
- Testes: `tests/test_auditoria_gpt5_a.py:92`;
  `tests/test_auditoria_gpt5_c.py:102`.
- Impacto: falha parcial vira crash e perde trilha auditável/possibilidade de reconciliação.
- Correção indicada: normalizar exceções na fronteira da capacidade, emitir evento e produzir
  resultado reprovado tipado.

#### 6. E1/E2 — o JSONL não sustenta schema fechado nem histórico append-only

`valido()` checa apenas o nome; payload ausente/extra/tipos errados passam. O gravador aceita
tipo desconhecido e `**dados` sobrescreve `evento`/`t`. `truncar=True` é default e apaga o
histórico ao reabrir.

- Produção: `motor/eventos_schema.py:10-263`; `motor/eventos.py:14-22`.
- Testes: `tests/test_auditoria_gpt5_e.py:18`, `:24`, `:36`, `:47`, `:60`, `:74`.
- Impacto: auditoria pode ser truncada, forjada ou impossível de projetar consistentemente.
- Correção indicada: validar envelope/payload na emissão, reservar campos e tornar append o
  default explícito com política de recuperação de cauda.

#### 7. K1/S1 — spec inválida alcança runtime

Validadores `schema_json`/`contem` sem configuração, comando em branco e timeout inválido são
aceitos. Edição externa no gate altera a spec sem nova validação.

- Produção: `motor/spec.py:101-123`; `motor/grafo.py:387`, `:450-457`.
- Testes: `tests/test_auditoria_gpt5_a.py:68`, `:84`;
  `tests/test_auditoria_gpt5_b.py:43`, `:59`.
- Impacto: o contrato “nada roda sem roteiro válido” não vale após edição ou para configs
  semanticamente vazias.
- Correção indicada: discriminated validators por `kind` e revalidação integral após qualquer
  mutação externa.

#### 8. U1 — sombra não é read-only em profundidade

O runner recebe o caso original e a evidência preserva aliases rasos. Mutação do runner ou do
retorno altera o corpus/evidência original.

- Produção: `motor/curador.py:245-253`, `:381-401`.
- Testes: `tests/test_auditoria_gpt5_f.py:63`, `:77`.
- Correção indicada: deep-copy/estrutura imutável na fronteira e isolamento explícito do runner.

#### 9. C3 — timeout não limita árvore nem recursos

`subprocess.run(timeout=...)` termina a espera do pai, mas descendentes sobrevivem; stdout e
stderr são acumulados sem limite. Tipos de timeout inválidos escapam como exceção.

- Produção: `motor/grafo.py:627-645`, `:673`, `:760`.
- Testes: `tests/test_auditoria_gpt5_d.py:128`, `:135`, `:161`.
- Correção indicada: sessão/process-group próprio, kill da árvore, limites de output e
  validação positiva do timeout.

#### 10. F3 — promoção sensível pode ser auto-respondida

`auto_mode` e overrides retornam decisão automática para `promocao`/gate sensível; valores
inválidos também são propagados.

- API observada: `motor/politica.py:26`; caminho de caixa `motor/caixa.py:68-108`.
- Testes: `tests/test_auditoria_gpt5_g.py:205`, `:209`.
- Correção indicada: classificar gates sensíveis em enum não automatizável e validar decisão.

### Médios

#### 11. C2 — `cwd` correto não é sandbox

A promessa literal de executar com `cwd=workspace` se sustenta (`motor/grafo.py:759-763`),
mas caminhos absolutos/traversal acessam fora e o filho herda segredos do ambiente. Ferramenta
não recebe o mesmo `cwd` em `motor/grafo.py:656-674`.

- Testes: `tests/test_auditoria_gpt5_d.py:97`, `:113`.
- Correção indicada: sandbox de processo/FS, ambiente mínimo e política coerente para todas as
  rotas de comando.

#### 12. S3/S4 — capacidades e orçamento têm contrato fraco

Capacidades vazias são válidas; `teto_custo` aceita `inf`/booleano e continua sem hard-stop.

- Produção: `motor/spec.py:16`, `:43-47`.
- Testes: `tests/test_auditoria_gpt5_b.py:71`, `:80`.
- Correção indicada: strings não vazias, números finitos estritos e enforcement runtime do teto.

#### 13. Eventos permitem JSON não estrito e tempo regressivo

`NaN` é persistido; `time.time()` pode recuar e o relógio relativo reinicia no append.

- Produção: `motor/eventos.py:18-22`.
- Testes: `tests/test_auditoria_gpt5_e.py:90`, `:117`, `:135`.
- Correção indicada: `allow_nan=False`, relógio monotônico e semântica temporal persistida.

#### 14. Eventos do curador estão fora dos 49 tipos

`curador.sombra`, `curador.certificou`, `curador.rejeitou` e
`curador.promocao_pendente` não aparecem no schema.

- Produção: `motor/curador.py:265`, `:325-331`, `:372`.
- Teste: `tests/test_auditoria_gpt5_f.py:249`.
- Correção indicada: registrar esses tipos e payloads no mesmo schema validado pelo gravador.

## ADR-003

**A fronteira “promoção é intenção, não aplicação” se sustenta no arquivo auditado.**
`preparar_promocao_gated` retorna `requer_gate=True`, emite intenção pendente e não aplica
catálogo/config/roteamento (`motor/curador.py:358-376`; controle
`tests/test_auditoria_gpt5_f.py:228`). O defeito é anterior: uma certificação forjada consegue
gerar essa intenção. O gate continua necessário, mas recebe evidência sem integridade.

## Matriz dos invariantes

| Invariante | Status | Síntese |
|---|---|---|
| K1 | Quebrado | config e edição pós-gate escapam validação |
| K2 | Quebrado | exceção e eventos fora do schema não ficam auditáveis |
| K3 | Quebrado | truthiness, propagação reprovada e decisão fail-open |
| K4 | Sustentado no escopo | intenção gateada, sem apply automático |
| S1 | Quebrado | configuração semanticamente inválida aceita |
| S2 | Sustentado | alvo/dependência e refazer do alvo confirmados |
| S3 | Parcial/quebrado | entrada de capacidade falha; roteador fora da fatia |
| S4 | Quebrado/dívida | teto inválido e sem hard-stop |
| G1 | Sustentado | ordem topológica e injeção confirmadas |
| G2 | Sustentado | refaz culpado e fecho, preserva ramo independente |
| G3 | Quebrado | limite existe, decisão pós-limite falha aberta |
| G4 | Quebrado | exceções escapam do grafo |
| C1 | Quebrado | allowlist por basename/fail-open |
| C2 | Parcial | `cwd` correto; sem confinamento real |
| C3 | Quebrado | descendentes/output/tipos não controlados |
| C4 | Quebrado | sem shell injection, mas com injeção de opção |
| E1 | Quebrado | nome fechado apenas nominalmente; drift `curador.*` |
| E2 | Quebrado | truncamento, JSON/tempo inconsistentes |
| U1 | Quebrado | sombra mutável/aliases |
| U2 | Quebrado | anti-Goodhart aceita evidência hostil |
| U3 | Quebrado | status forjado gera intenção |
| F1 | Quebrado | crash/resume não idempotente |
| F2 | Quebrado | validação, concorrência, path e timeout |
| F3 | Quebrado | gate sensível automatizável |

## Testes e Gate pós-auditoria

| Fatia | Resultado isolado |
|---|---|
| A | 8 falhas esperadas |
| B | 13 falhas esperadas |
| C | 3 falhas esperadas |
| D | 13 falhas esperadas, 5 controles passam |
| E | 10 falhas esperadas |
| F | 17 falhas esperadas, 6 controles passam |
| G | 14 falhas esperadas |

Consolidado: **78 falhas esperadas, 11 controles passam**. Ruff e mypy estão limpos após
anotações estritamente estáticas nos doubles de teste. Bandit high/high e compileall passam.
A suíte original, excluindo arquivos `test_auditoria_*`, permanece **333 passed**.

O `pytest motor/`/job de CI fica vermelho ao incluir os reprodutores. Isso é o resultado
intencional da auditoria, não uma regressão introduzida em produção. Cada teste deve virar
verde por correção da implementação, nunca por exclusão/`xfail`.

Execução final do worktree: **100 falhas, 344 passes** — 78 falhas desta auditoria, 11
controles novos aprovados e as 22 falhas do arquivo preexistente não rastreado.

## Dívida silenciosa e força dos testes antigos

A suíte rastreada verde coexistia com contraexemplos para as próprias promessas documentadas.
Logo, os testes citados em `INVARIANTES.md` provavam caminhos felizes ou propriedades mais
estreitas, não os invariantes completos. As três dívidas já declaradas (C4, S4, F3) eram reais,
mas não abrangiam os bypasses adicionais de gate, curador, eventos, crash e concorrência.

## Artefatos

- `tests/test_auditoria_gpt5_a.py` … `tests/test_auditoria_gpt5_g.py`
- `docs/auditoria/FRAGMENTO-D-MAESTRI.md`
- `docs/auditoria/FRAGMENTO-F-MAESTRI.md`
- `docs/auditoria/FRAGMENTO-G-MAESTRI.md`

## Limitações

- O escopo imposto não abriu `modelos.py`; a parte runtime de S3 não foi confirmada.
- Consumidores externos de eventos/promoção não foram auditados.
- Probes de concorrência são determinísticos no ambiente local, mas não substituem stress
  multi-processo prolongado.
- Ausência de apply automático foi provada somente em `curador.py`, não em consumidores.
- Nenhum arquivo de produção foi alterado.

### Onde isto pode dar errado

- A explorabilidade de subprocesso depende de quem controla spec, registro e ambiente; ACLs
  externas podem reduzir probabilidade, não corrigir o bypass.
- Alguns testes expressam requisitos defensivos ainda implícitos (amostra mínima, proveniência,
  domínio de decisão). Eles devem ser formalizados antes da correção para evitar trocar uma
  falsificação por outra.
- O Gate continuará vermelho até as correções; remover ou marcar esses testes como `xfail`
  destruiria a evidência desta auditoria.
