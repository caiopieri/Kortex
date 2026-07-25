# Harness de Hardware — Diagnóstico e Blueprint v0

> Base: o **motor** (grafo LangGraph fixo que interpreta uma WorkflowSpec dinâmica). O dev-harness (software) fica fora — é disciplina de software.
> Princípio: o motor é o **estado final**; o que existe hoje é onde o desenvolvimento parou. Este blueprint é escrito **em degraus**, e cada degrau marca o que **roda hoje** (`fan_out_sintese`) vs. o que **espera o motor v0.2** (ver [[REQUISITOS-MOTOR-harness-hardware]]).

---

## 1. Veredito sobre o plano herdado

O plano de outro agente (agente de reparo → designer de PCB) tem núcleo aproveitável, mas embute armadilhas. Resumo do que entra e do que sai:

| | Item | Decisão |
|---|---|---|
| ✅ | Decomposição em 4 papéis (Ingestão, Arquiteto, Codificador, Validador) | **Aproveitar** — mapeia 1:1 em subagentes + verifier do motor |
| ✅ | DRC do KiCad como gate de máquina | **Aproveitar** — é o "CI verde" do hardware (REQ-4) |
| ✅ | Modelos locais baratos no grosso + frontier só pra caso difícil | **Aproveitar** — é o `ClienteRoteador` + tier (tarefa T5 do motor) que já existe |
| ✅ | Começar por diagnóstico de reparo (read-only) | **Aproveitar** — é o T1 correto, baixo risco, roda hoje |
| ⏸️ | Fine-tuning de modelo 7-8B como fundação | **Adiar** — é otimização de custo pra depois, não base. Começar com prompt + verifier |
| ✂️ | "95% certo no primeiro clique / pular simulação" | **Trocar a métrica** — meta real é *"converge em poucas iterações sob gates fortes"*, com respin |
| ✂️ | Fundir reparo e design numa dependência | **Cortar** — são duas trilhas. Reparo vira **corpus de conhecimento consultável**, não pipeline a montante do design |
| ⚠️ | Reconstruir o Platform Design Guide da Intel de boardview vazado (fase 2) | **Parede legal** — segredo industrial/copyright/DMCA. OK pra aprendizado pessoal; **radioativo como produto**. Decisão sua, registrada como risco |

**O ponto que o plano não viu:** a fase de **design de PCB** é uma *pipeline sequencial com loop* (Arquiteto→Codificador→DRC→volta), e o motor de hoje só faz **paralelo puro**. Isso não é detalhe — é a dependência central, agora especificada em [[REQUISITOS-MOTOR-harness-hardware]].

---

## 2. Arquitetura do harness

A unidade é sempre **missão → WorkflowSpec → funil do motor** (planner → subagentes → verifier → gate → síntese). O que o hardware acrescenta são cinco componentes:

**a) Corpus de referência (componente de 1ª classe).** Boardviews, esquemas, reference designs e o reservatório de reparo. **Não é input solto — é a base que o Arquiteto e o verifier consultam.** É daqui que sai a "regra herdada" que substitui simulação do zero (geometria/topologia/net-class de placas que já funcionam). A parede legal vive aqui: marcar a proveniência de cada fonte.

**b) Papéis** (`papel` → modelo via `ClienteRoteador`): `extrator/ingestor`, `arquiteto`, `codificador-layout`, `validador`. Mais o verifier-modelo (rubrica) e o gate-fundador (`interrupt`) que o motor já provê.

**c) Executores/ferramentas determinísticas.** KiCad `pcbnew` (gera layout via script), `kicad-cli ... drc`, parser de netlist/boardview, resolvedor de BOM (Octopart/Mouser/Digikey). **Produzem artefatos, não texto** → exigem REQ-3/4/5 do motor. **Não são catálogo próprio:** registram-se como o **eixo de domínio do Registry** do motor (mesmo substrato dos modelos-executores), conforme [[RESPOSTA-MOTOR-aos-requisitos]].

**d) Modelo de artefato/estado** *(resolvido aqui — não depende de decisão sua):* artefatos vivem em disco por execução; os **textuais** (netlist, scripts `pcbnew`, `constraints.json`) versionados em **git**; os binários referenciados por caminho+hash. Continuidade vive nos arquivos, igual ao dev-harness. No motor isso é REQ-3 (referência, não conteúdo, no estado).

**e) Pilha de gates — quatro camadas, do barato/cedo ao caro/tarde:**
1. **Verifier-modelo** (rubrica) — julgamento de modelo, já existe.
2. **Gate determinístico de máquina** — DRC; depois **checagem de SI por regra** (comprimento/impedância derivada do stackup/topologia, extraídas da referência); depois **simulação pontual** só nos nets críticos. (REQ-4)
3. **Gate do fundador** (`interrupt`) — nos pontos de alto custo/risco.
4. **Gate físico irredutível** — ver §3.

---

## 3. O loop físico irredutível (a maior diferença pro software)

O gate do software é CI: máquina, instantâneo, grátis. O hardware tem um gate final que é **físico** — fabricar a placa (dinheiro + semanas) e testá-la na bancada, cujo resultado **re-entra no loop**. Os gates virtuais (DRC → SI-regra → sim pontual) existem pra **empurrar o erro pra antes da fabricação** — nunca pra eliminá-la. Consequência de design: o diagnóstico (T1) **não fabrica**; o design de PCB (degrau alto) **fabrica**, e o harness tem que tratar "respin" (nova rodada após bancada) como estado normal, não como falha. Quem se ilude que o DRC fecha a conta projeta uma placa que passa em geometria e falha em silício.

---

## 4. A escada de degraus

| Degrau | Produz | Roda hoje? | Gate principal |
|---|---|---|---|
| **D0 — Corpus & ingestão** | Reparo: transcrição→ficha JSON. Boardview→netlist. | ✅ `fan_out_sintese` | Verifier-modelo + parser determinístico |
| **D1 — Diagnóstico de reparo** | Dado sintoma+board, sugere causa/teste/valor de componente | ✅ `fan_out_sintese` | Verifier-modelo contra casos do corpus |
| **D2 — Design de bloco simples** | Ex.: regulador, breakout de baixa velocidade. Arquiteto→Codificador(`pcbnew`)→DRC | ⛔ espera motor v0.2 (REQ-1,3,4,5) | DRC + SI-lite |
| **D3 — Bloco de alta velocidade** | Ex.: roteamento DDR/PCIe de um sub-bloco, guiado por referência | ⛔ espera v0.2 + checker de SI por regra | SI-regra + sim pontual + fundador |
| **D4 (alto) — Placa compatível i7 + DDR5** | Placa-mãe derivada, guiada por gabarito de referência | ⛔ espera tudo de D3 + corpus robusto + loop (REQ-2) + fab/bancada | Pilha completa + gate físico |

A progressão é a mesma lógica de tier do dev-harness (T1→T2): **endurece degrau a degrau**, não tudo de uma vez. A métrica de sucesso de D4 **não é** "primeiro clique" — é **convergência em poucas iterações sob a pilha de gates**, com respin físico contado como parte do ciclo.

---

## 5. Interface inter-harness (sua decisão A)

Mecânica/gabinete = **outro harness**. Mas projetos futuros combinam mecânica + hardware + software. Para não criar acoplamento entre harnesses, a regra é **microserviço, não monólito: falam por contrato, nunca importam o grafo um do outro.**

**Mecanismo:** cada harness **publica e consome artefatos** numa **fronteira declarada em disco**, com um pequeno **manifesto de interface** (quais artefatos, schema, versão). Exemplos do que o harness de hardware exporia:
- **Publica** pra mecânica: `board-outline.dxf`, `connector-placement.json`, `mounting-holes.json`, `thermal-envelope.json`.
- **Consome** da mecânica: `enclosure-constraints.json` (dimensões, zonas de exclusão, furos).

**No motor isso reusa REQ-3/REQ-5** (artefatos referenciáveis) — a diferença é que a referência **cruza a fronteira de execução**: a saída de um run/harness vira corpus/entrada de outro. Nenhuma primitiva nova de motor é estritamente necessária além das já pedidas.

**Compromisso de design assumível já:** garantir que o harness de hardware **produz seus artefatos de fronteira num formato neutro** (DXF/JSON/STEP), **não preso ao KiCad**. O manifesto formal só precisa ser definido quando o **1º projeto combinado** aparecer — antes disso, seria especular sobre uma interface sem cliente.

---

## 6. A "constituição de hardware" (a redigir — pontos mapeados)

Análogo da constitution + security-DoD do dev-harness. Ainda não preenchida, mas os capítulos obrigatórios estão mapeados:
- **DFM-DoD** (manufaturabilidade): regras de fab do fornecedor — clearances, tamanho de via, anel anular, stackup disponível.
- **Safety-DoD físico**: elétrico (isolação, corrente/trilha), térmico (envelope, dissipação).
- **Regulatório**: ANATEL (BR), FCC (US), CE (EU) — quando o tier exige.
- **Tiers físicos**: T1 = protótipo (impresso/breadboard, sem certificação) → T2 = produção (tolerância, certificação, respin controlado).

---

## 7. Roadmap consolidado

**Depende do motor** (repassar [[REQUISITOS-MOTOR-harness-hardware]] ao agente do motor): REQ-1..5 → habilita D2 em diante.

**Trabalho do harness, independe do motor (pode começar já):**
- Montar corpus + ingestão (D0/D1) — roda em `fan_out_sintese` hoje.
- Especificar papéis e rubricas; escrever os executores determinísticos (parser de netlist, wrapper de DRC, resolvedor de BOM) como ferramentas.
- Definir o **checker de SI por regra** (o diferencial técnico do degrau alto).
- Redigir a constituição de hardware (§6).

**Fora de escopo aqui:** mecânica (outro harness; só o contrato de fronteira em §5); a fase-2 legal da Intel como produto.

---

## 8. Próximo passo concreto

A 1ª WorkflowSpec real de D0/D1 **já existe e foi validada** contra o schema do motor (sem rede/modelo): `motor/exemplos/hardware-diagnostico.json` — diagnóstico de um buck 12V→5V, caso self-contained, **sem boardview proprietária** (evita a parede legal). Roda no `fan_out_sintese` de hoje, zero REQs.

Passo: **rodar** (na sua máquina, com o CLI de modelo) pra ver onde atrita de verdade, *antes* de construir a v0.2:

```bash
cd motor
python3 -m motor --spec exemplos/hardware-diagnostico.json --modelos exemplos/modelos-codex.json --auto
```

É exatamente o *"fazer com o que tem agora e anotar o roadmap do resto"* que você pediu — validar a premissa "harness sobre motor" ponta-a-ponta com custo baixo, em vez de construir o padrão novo no escuro.

---

*Requisitos para os degraus D2+ devem entrar como specs versionadas antes da implementação.*
