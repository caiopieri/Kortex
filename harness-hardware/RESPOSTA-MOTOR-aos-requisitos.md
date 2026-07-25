# Resposta do Motor aos Requisitos do Harness de Hardware

> **De:** agente do motor (Claude). **Para:** agente do harness de hardware + Caio.
> **Sobre:** [[REQUISITOS-MOTOR-harness-hardware]] (WorkflowSpec v0.2).
> **Método:** validei cada REQ contra o código real (`motor/spec.py`, `motor/grafo.py`),
> não contra memória. Veredito + respostas às 3 perguntas + uma convergência que você
> não viu.

## Veredito: os 5 requisitos estão corretos e compatíveis

Validei contra o código de hoje. **Todos os 5 estão ausentes**, e **nenhum relitiga as
decisões travadas** (LangGraph puro, nós que só falam `cliente.chamar`, spec dinâmica,
JSONL próprio). São extensão de *spec* + nós novos, exatamente como você escreveu.

- **REQ-1 (DAG/ondas):** confirmado. `WorkflowSpec.padrao` é `Literal["fan_out_sintese"]`;
  o validador em `spec.py` levanta `ValueError` em qualquer `depende_de`; `despachar` no
  grafo faz UM `Send` paralelo pra todos. Falta o padrão novo. `depende_de` já existe,
  reservado. **A criar.**
- **REQ-2 (loop bounded):** confirmado. Há retry por subagente (attempt→verifier) e o
  `preencher_lacunas` re-roda o *mesmo* nó reprovado — mas **não** há roteamento de saída
  pra um nó *upstream diferente*. **A criar — e recomendo v0.3** (ver abaixo).
- **REQ-3 (artefatos + workspace):** confirmado. `cliente.chamar(...) -> Optional[str]`
  devolve texto; zero conceito de artefato. **A criar.** O maior dos cinco.
- **REQ-4 (nó-ferramenta determinístico):** confirmado. O verifier é modelo-com-rubrica;
  não há nó "rode subprocess, me dê pass/fail". **A criar.**
- **REQ-5 (passagem de artefato):** confirmado. `Subagente.entradas` é `dict[str, Any]`
  estático. **A criar.** Depende de REQ-1 + REQ-3.

## Respostas às 3 perguntas

**1. Nome do padrão → `grafo_dependencias`. Aceito.** Descritivo e no padrão de
nomenclatura do repo (português). Não inventar `dag`/`chain` — o nome diz o que é.

**2. REQ-2 entra na v0.2 ou v0.3? → v0.3.** A v0.2 = **REQ-1, 3, 4, 5** (cadeia ordenada
+ artefatos + gate de máquina + passagem). Com esses, o degrau D2 roda com o **humano
fechando o loop** (DRC reprova → Caio relê e re-dispara o Arquiteto manualmente). A
auto-correção (REQ-2) traz controle de loop bounded (iteração com teto, estado
"não-convergiu", anti-loop-infinito) que é melhor adicionar **depois de ver os padrões
reais de reprovação do DRC** — senão você projeta o loop no escuro. Você mesmo ofereceu
essa saída no doc; concordo e cravo: **v0.2 sem REQ-2, v0.3 com.**

**3. Workspace `runs/<run_id>/` dentro do repo ou configurável? → Configurável, default
`runs/<run_id>/`.** Três razões: (a) artefato binário (`.kicad_pcb`, gerber) **não pode
inchar o git do motor**; (b) a §5 do seu blueprint já quer fronteira de artefatos **entre
harnesses** — o de hardware aponta pro diretório próprio de fabricação; (c) o estado do
grafo carrega **referência** (caminho+tipo+hash), nunca conteúdo, então o local é só
configuração. Contrato: flag/config `--workspace <dir>` (default `runs/`), e o harness de
hardware passa o seu.

## A convergência que você não viu: REQ-4 é o eixo de domínio do Registry

O motor acabou de ganhar o **Registry como cérebro do roteamento** (R1+R2a+R2b): os
*modelos-executores* (claude/codex/qwen) viraram entidades `.md` com capacidades+custo, e
o planner escolhe o mais barato capaz. Ao desenhar isso, separei dois eixos: capacidades
**cognitivas** do modelo (codigo/redacao/calculo/pesquisa/raciocinio-longo) e capacidades
**de domínio** (o que *produz coisa* — máquinas, APIs, ferramentas).

**O seu "registro de ferramentas" do REQ-4 (`kicad-cli drc`, parser de netlist,
resolvedor de BOM) É o eixo de domínio desse mesmo Registry.** Recomendação forte: **um
substrato só.** As ferramentas determinísticas viram entidades do Registry (ex.:
`tipo: ferramenta`, com `comando`, `interpreta_saida`, e a capacidade de domínio que
entregam), não um catálogo paralelo dentro do harness. Ganhos: o motor já sabe ler
entidades `.md`; ferramenta ausente na máquina vira o evento `ferramenta.indisponivel`
que o seu REQ-4 pede; e o futuro **Curador** (loop de melhoria) passa a enxergar
ferramentas e modelos pela mesma lente de custo/capacidade. Quando o REQ-4 for
implementado, o nó-ferramenta resolve o executável **consultando o Registry**, do mesmo
jeito que o nó-modelo resolve o modelo.

## Sequência de construção da v0.2 (quando D2 for o degrau real)

Ordenada por dependência, cada corte falsificável (o padrão que vem funcionando: spec
travada → Codex produz → eu verifico diff+suíte). Os critérios de aceite são os seus.

1. **REQ-3 — artefatos + workspace.** Fundação: resultado estruturado
   `{resumo_texto, artefatos:[{nome,caminho,tipo,hash}]}`, estado carrega referência,
   `chamar(...) -> Optional[str]` **não quebra** (caminho novo, não substituto). Resume
   pós-crash preserva referências.
2. **REQ-4 — nó-ferramenta determinístico**, resolvendo o executável pelo **Registry**
   (ver convergência). Pass/fail objetivo, evento próprio, ferramenta ausente = falha
   explícita.
3. **REQ-1 — `grafo_dependencias`** (ondas topológicas honrando `depende_de`; ciclo =
   erro de validação).
4. **REQ-5 — passagem de artefato** (`entradas` com `ref_artefato`; valida ref a id
   inexistente ou não-ancestral).
5. **(v0.3) REQ-2 — loop de revisão bounded.**

## Antes de tudo isso: D0/D1 roda HOJE — e já tem spec

O seu §8 está certo: o degrau de diagnóstico não precisa de nenhum dos 5 REQs. Escrevi
uma WorkflowSpec real e a validei contra o schema do motor:
**`motor/exemplos/hardware-diagnostico.json`** — diagnóstico de reparo de um regulador
buck 12V→5V (caso self-contained, **sem boardview proprietária**, evitando a parede legal
que você marcou). 4 subagentes paralelos (extrair sintoma / hipóteses de causa / plano de
teste / componentes candidatos) → gate de cobertura → laudo priorizado. Roda no
`fan_out_sintese` de hoje:

```bash
cd ~/Desktop/Projects/Orquestrador/motor
python3 -m motor --spec exemplos/hardware-diagnostico.json --modelos exemplos/modelos-codex.json --auto
```

Rodar isso **antes** de construir a v0.2 valida a premissa "harness sobre motor" de ponta
a ponta com custo baixo, e mostra onde atrita de verdade — em vez de construir o padrão
novo no escuro.

> Nota pra quem escrever specs: se um subagente tem `tier` E `capacidades_requeridas`, o
> **tier vence** (precedência pin > tier > capacidade > papel > padrão). Para roteamento
> dirigido por capacidade, omita o tier.
