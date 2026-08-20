# DECISÃO — Harness: alugar o laço, ser dono dos invariantes

> **Canônico** sobre a relação do Kortex com harnesses de agente (Claude Code, Codex CLI,
> DeepSeek Harness, opencode). Registrado em 2026-08-19, com evidência medida.
>
> Aplica a decisão pétrea #5 e o vetor V4 (`motor/docs/EVOLUCAO.md`) a um caso novo.

---

## 1. O fato que motivou a decisão

**O Kortex não é um harness, e isso foi verificado, não presumido.** Busca por
`tool_call`, `tools=` e `function_call` em `motor/`: **zero ocorrências**. O executor
devolve `-> str` (`omniroute_orcado.py:471`).

Consequência prática: um subagente executor **não consegue** ler arquivo, rodar código,
iterar sobre o resultado ou olhar o repositório. Ele escreve texto no escuro; quem executa
é um nó validador separado, depois, no sandbox — e o executor nunca vê o resultado, exceto
como feedback textual na tentativa seguinte.

Isso explica um limite observado: a missão `cli-tarefas` funciona porque o programa cabe
num arquivo que um modelo escreve de uma vez. **Software que não cabe numa tacada não é
representável num nó hoje.** O limite não é qualidade de modelo; é a assinatura do executor.

## 2. A decisão

**Não construir harness próprio. Alugar o laço, ser dono dos invariantes.**

O harness é a camada que mais rápido comoditiza no mercado — a DeepSeek publicou um em
2026-08-13 que passou de 170 mil estrelas em seis dias, e Anthropic e OpenAI iteram os
deles semanalmente. Competir ali é reescrever para sempre uma coisa que times grandes
entregam de graça.

O que é escasso é a camada de processo: portão determinístico, ledger com schema fechado,
reserva antes do efeito, curador com sombra e certificação, sandbox conforme. **Isso não
existe em nenhum harness**, e não está comoditizando porque é trabalho chato que não vira
demo.

Regra prática, herdada do V4 (*"resistir à tentação de inchar o motor é o que mantém ele
músculo"*):

| camada | de quem é |
|---|---|
| laço do agente, ferramentas, contexto, compactação, sessão | **alugado** — do harness |
| envelope de orçamento · roteamento de execução · emissão de evidência | **nosso**, sempre |

**Ser dono onde muda o resultado. Zero manutenção onde não muda.**

## 3. A costura é o produto, não o harness escolhido

O padrão já existe no repo, duas vezes, e este é o terceiro caso:

- `CommandRunner` é `Protocol`; backend novo é certificado contra
  `sandbox-conformance.md`, **nunca por auto-declaração** (`AGENTS.md`).
- Provedor de inferência é **configuração**, não código: *"aggregation of inference is a
  configuration concern"* (`AGENTS.md`).

Harness ganha a mesma forma: **costura tipada + backends certificados**. Nenhum fornecedor
vira aposta única; trocar backend não toca o motor.

**Preferir extensão a fork.** Forkar um projeto que oferece pontos de extensão tipados joga
fora exatamente o que o torna valioso, e reinstala a esteira de merge com um projeto que
promete quebrar compatibilidade. Customização funda é fork disfarçado.

## 4. Evidência — o experimento de 2026-08-19

A objeção contra alugar era concreta: *se a costura não conseguir impor contenção e
roteamento de comando, ter harness próprio deixa de ser preferência e vira necessidade.*

Testado contra o DeepSeek Harness (`dsh-0.1.0-rc.8`), com adaptador mock — sem rede, sem
credencial, sem custo. Um plugin Cordis de ~40 linhas, montando os três invariantes:

| invariante | ponto de extensão | resultado |
|---|---|---|
| execução só pelo runner certificado | `ctx.tools.guard()` | ferramenta negada, **não rodou**, modelo recebeu `isError` |
| evidência no nosso ledger | `tools/result` | eventos no envelope do Kortex, `seq` monotônico |
| envelope de orçamento | `tools/execute` | recusado **antes do efeito**, ferramenta não rodou |

Saída real do ledger, emitida de dentro do laço deles:

```json
[{"seq":1,"evento":"custo.tick","ferramenta":"echo","acumulado":100},
 {"seq":2,"evento":"validador.rodou","id":"echo","kind":"comando","aprovado":true}]
```

**Testes portadores de carga**, provado por mutação um de cada vez: neutralizar o guarda de
execução derruba **só** o teste de execução; neutralizar o envelope derruba **só** o de
orçamento. Falha cirúrgica, não colateral. Restaurado: 3 de 3 verdes.

Detalhe que pesou na decisão: o `ToolGuard` deles é fail-closed por construção —
*"guards have no allow result, listener ordering cannot turn a denial back into
permission"*. Um guarda que só nega, nunca libera, imune à ordem dos listeners. É o mesmo
princípio do motor, alcançado de forma independente.

## 5. O que o experimento NÃO provou

Registrado para ninguém citar esta decisão como mais forte do que ela é:

- Foi o **laço deles com adaptador mock**, não o motor do Kortex. Integração real com
  `CommandRunner`, com `LogEventos` (que abre sob flock) e com `RepositorioOrcamento`
  (SQLite, reserva durável) **não foi testada**. O trabalho mora aí.
- O envelope de orçamento do experimento é **fingido**: custo fixo por ferramenta. O
  problema real — não saber o custo de um laço agêntico antes de rodar — **segue sem
  resposta**. Provou-se o ponto de encaixe, não a solução.
- Não se rodou a suíte deles inteira, nem se avaliou qualidade de saída.

## 6. Consequências

- **Executor com ferramenta deixa de ser bloqueio de capacidade e vira trabalho de costura.**
- Quanto melhores os harnesses ficarem, melhor para o Kortex: executor mais forte sem
  escrever linha. O contrário não vale — nenhum harness ganha portão de processo por
  evolução deles.
- O risco de "ficar para trás" não vem de não ter harness próprio; vem de **não ter encaixe
  onde qualquer harness entre**. Isso é o contrato tipado de V5+V7 — a mesma peça, de novo.
- Rodar modelo de um fornecedor no laço afinado para outro tem custo de qualidade não
  medido. Se um harness virar padrão, medir isso vira obrigatório.

## 7. Onde isto pode dar errado

- **A comoditização pode inverter.** Se harness virar o produto e processo virar commodity,
  esta decisão fica errada. Sinal a vigiar: os pacotes `guard`, `token-meter` e `sandbox`
  do DSH. Se crescerem para portões e evidência, a diferenciação do Kortex encolhe.
- **Interceptação profunda é acoplamento profundo.** Quanto mais processo depender dos
  pontos de extensão de terceiro, mais "compatibility-breaking changes" nos atinge — agora
  dentro do que nós escrevemos.
- **"Alugar o laço" tem custo escondido:** depurar código que não é seu, com prioridades que
  não são suas.
- **172 mil estrelas em seis dias é sinal de hype, não de durabilidade.** Comunidade grande
  acelera features e também acelera churn e fragmentação.
- **Nada disto está construído.** É decisão com experimento, não funcionalidade. O
  `ESTADO.md` continua sendo quem diz o que existe.
