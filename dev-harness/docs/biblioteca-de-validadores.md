# Biblioteca de validadores (gates)

> O coração anti-alucinação da meta-fábrica. O processo não é agente-conversando-com-agente: é um grafo
> **híbrido** de nós pensantes (agentes) e **nós validadores** que impõem a verdade. Um agente bem
> alucinado entrega bosta com convicção; o validador é quem não deixa.
>
> Esta biblioteca é reutilizável em todos os níveis (agente, casa/harness, conglomerado) e em todas as
> verticais. Cada gate emite um **evento tipado** (`gate.passou` / `gate.reprovou` + referência da
> evidência) — é isso que alimenta a visualização ao vivo e a interceptação. Gate library e event schema
> são a mesma moeda.

---

## 1. Os três tiers de validação

Toda afirmação que importa passa por exatamente um destes — escolhido pelo tier mais barato que cobre a
afirmação:

| Tier | O que é | Pode alucinar? | Quando usar |
|---|---|---|---|
| **Determinístico** | Checagem por algoritmo, sem LLM (teste, schema, compile, matemática, simulação, prova formal) | **Não** | Sempre que existir uma checagem objetiva para a afirmação. É o default. |
| **Adversarial** | Um LLM/agente *diferente* tenta quebrar/criticar a saída contra a spec | Reduz, não elimina | Só quando nenhuma checagem determinística prende a afirmação (design, priorização, "está limpo?"). |
| **Humano** | Você / board | — | Irreversível, alto risco (dinheiro, dado pessoal, segurança física), ou onde nem o adversarial prende. |

## 2. As regras de escolha (a parte que sustenta tudo)

1. **Toda afirmação que importa deixa evidência.** Sem log/diff/resultado/checagem, não passou — é contrato de evidência.
2. **Prefira a checagem determinística mais barata que cobre a afirmação.** Determinístico > adversarial > humano, nessa ordem de preferência.
3. **Sem checagem determinística → adversarial.** Com a regra de que **executor ≠ revisor** (nunca o mesmo agente).
4. **Irreversível ou alto risco → humano.** Independente do resto.
5. **Nenhum nó certifica a própria saída.** Quem produz nunca é quem aprova — é o aluno corrigindo a própria prova. Vale pra agente e pra validador.
6. **Catraca (ratchet): todo achado adversarial/humano que PODE virar checagem determinística, DEVE.** Um bug que o revisor pegou vira teste de regressão; um critério subjetivo que virou objetivo vira gate. Com o tempo, julgamento migra para determinismo — e é assim que o curador aprende e o gap map se preenche.
7. **Risco escala o rigor.** Mudança de baixo risco (texto, docs, refactor mecânico com teste forte) pode ter gate leve; alto risco (auth, pagamento, multi-tenant, migração destrutiva, deploy) exige o gate forte e provavelmente humano.
8. **O piso de determinismo varia por vertical** (§5) — e é ele que define a ordem de construção das verticais e dos modelos especialistas.

## 3. Catálogo de validadores determinísticos

A peça que falta na maioria dos sistemas de agente. Cada família é um tipo de nó plugável no grafo do
motor. "Evidência" é o que o nó emite no evento.

| Família | O que checa | Evidência emitida | Verticais |
|---|---|---|---|
| **Build / compilação** | O artefato compila/builda | exit 0 + artefato | software, hardware (HDL), firmware |
| **Tipos** | Type-check (tsc, mypy) | log exit 0 | software |
| **Lint / formato / convenção** | Regras configuradas (ruff, eslint, formatters) | log exit 0 | software, qualquer texto estruturado |
| **Testes (matriz de QA)** | happy · edge · erro esperado · permissão negada · input malicioso · estado vazio · muitos dados · concorrência · falha de dependência | resultado por caso no CI | software (cobertura é *sinal*, nunca meta) |
| **Schema / contrato de dados** | Saída bate com JSON Schema / OpenAPI / protobuf / pydantic / constraint de banco | validação pass/fail | **todas** — é o exemplo n8n: saída do agente → validador de schema |
| **Property-based / invariantes** | Propriedades e invariantes sob entradas geradas (fuzz, metamórfico) | contra-exemplo ou ok | software, algoritmos críticos |
| **Verificação formal / model checking** | Prova de propriedade (Verilog formal, TLA+, SMT) | prova / contra-exemplo | hardware, lógica crítica |
| **Numérico / matemático** | Recalcula o número de forma determinística e compara; dimensional analysis; reconciliação; checksum | diff numérico = 0 | finanças, engenharia, dados |
| **Segurança estática** | SAST (semgrep/CodeQL), dependency audit, secrets scan (gitleaks), licença/SBOM | achados acima do limite | software, supply chain |
| **Segurança dinâmica / política** | Testes negativos de permissão: cross-tenant, 403, IDOR, webhook sem assinatura, RLS | teste nomeado + resultado | qualquer coisa com auth/dado |
| **Simulação física / engenharia** | FEA, tolerância/DFM, SPICE, cinemática — contra thresholds da spec | relatório vs limite | hardware, mecânico, manufatura |
| **Golden / snapshot / regressão** | Diff contra saída esperada gravada | diff = 0 | todas |
| **Conformidade de escopo** | Diff dentro dos arquivos esperados; PR ≤ ~300 linhas; nada oportunista | diff anotado | todas |
| **Smoke / health / deploy** | Staging responde; healthcheck; smoke test pós-deploy | status + URL/horário | software em produção |
| **Consistência / referência** | Links resolvem; integridade referencial; grafo de dependência acíclico | relatório | dados, docs, knowledge layer |

## 4. Os dois tiers não-determinísticos

**Adversarial (LLM vs LLM).** Quando não há checagem objetiva — "este design está coerente?", "a copy
casa com a marca?", "o plano cobre os riscos?". Regras: executor ≠ revisor; usar **rubricas
verificáveis** (não "código limpo", e sim "usuário sem permissão recebe 403"); rodar com mais de um
modelo quando possível (pass@k); **rejeitar critério subjetivo em gate crítico**. Limite honesto: reduz
alucinação, não elimina — agentes podem concordar entre si numa solução errada.

**Humano (gate do fundador / board).** Para o irreversível e o de alto risco. É o `interrupt()` do motor
e o approvals do control-plane. Não-bloqueante por padrão na observação; bloqueante na promoção. É onde
a tua sensação de controle do Paperclip vira poder real: você intercepta no gate.

## 5. Piso de determinismo por vertical (define a ordem)

Quanto mais barata e objetiva a checagem do domínio, mais cedo a vertical e o modelo especialista
entram. Não é gosto — é onde o gate prende.

| Vertical | Piso de determinismo | Consequência |
|---|---|---|
| **Software / Verilog** | Alto (teste, compile, formal, sim baratos) | Primeira vertical. Onde o especialista é mais confiável. |
| **Hardware / mecânico** | Médio (simulação existe, mas cara/lenta; físico exige bancada) | Depois; o gate "evidência" vira resultado de simulação/teste físico no mesmo contrato. |
| **Jurídico / design** | Baixo (muito julgamento; pouca checagem objetiva) | Mais tarde; dependem fortemente de adversarial + humano e da catraca. |

## 6. A catraca e o curador

A regra 6 é o que faz o sistema ficar melhor sozinho: cada coisa que hoje só o humano ou o adversarial
pega, quando puder virar checagem determinística, vira. O **curador** opera essa catraca — observa onde
os gates reprovam (e onde *deveriam* ter reprovado e não pegaram = gap map), e transforma julgamento
recorrente em validador permanente. Assim a biblioteca de gates cresce com o uso, e a fábrica fica mais
à prova de alucinação a cada ciclo, sem depender de o modelo melhorar.

## 7. Ligação com controle e interface

Cada nó (pensante ou validador) emite eventos tipados: `agente.iniciou`, `ferramenta.chamada`,
`validador.rodou`, `gate.passou` / `gate.reprovou` (+ referência de evidência), `checkpoint.pediu_humano`.
Esse stream **é** a interface viva — os caminhos que piscam, o gate que fica verde/vermelho, o ponto onde
você intercepta. Por isso o esquema de eventos motor→superfície (item do roadmap) e esta biblioteca são a
mesma coisa vista de dois lados: o validador produz a verdade; o evento a torna visível e interceptável.
É o controle do Paperclip — e mais, porque aqui o que você vê não é só "agente fez", é "evidência passou".

### Quando `contem` mede algo (anti-tautologia — aprendido no red-team item 3, 2026-07-04)

1. O termo exigido deve ser **não-adivinhável** (nome próprio arbitrário, não palavra comum) e
   **ausente de tudo que o executor vê** (pergunta, rubrica, contexto, feedback de retry).
2. Se o termo está no contexto injetado (RAG/deps), `contem` mede **transporte de substring**, não
   conhecimento. Isso ainda é útil (mede recuperação), mas nomeie a claim corretamente.
3. Nunca alegue lift sem braço de controle SEM-fonte com **n≥5 e baseline estável** — um 0/3 de
   amostra pequena é ruído, não piso.
4. `schema_json` com `pattern` regex sobre **texto livre** é frágil (falso-reprova prosa correta);
   regex só sobre valores mecânicos (IDs, enums, formatos).

## Onde isto pode dar errado

- **Gate determinístico mal escrito vira falso conforto.** Teste que não testa, schema frouxo, SAST com
  limiar errado — passam bosta com selo verde. A catraca ajuda, mas validador também precisa de revisão.
- **Adversarial conluiado.** Dois LLMs podem concordar numa solução errada. Por isso adversarial é o
  segundo tier, não o primeiro, e modelos diferentes quando possível.
- **Determinismo onde não cabe.** Forçar checagem binária em algo que é genuinamente julgamento (estética,
  estratégia) gera métrica falsa. Nesses nós, assuma o adversarial/humano — não finja objetividade.
- **Maleabilidade corroendo o gate.** A rota pode ser flexível; o gate não. Se "maleável" começar a virar
  "pula o gate", perdeu-se o valor inteiro. Flexibilidade no caminho, rigor no checkpoint.
- **Validador caro no lugar errado.** Simulação/formal em fatia T0 custa mais do que vale. Risco escala o
  rigor; spike não carrega o gate forte.
