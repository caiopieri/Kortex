# Requisitos do Motor para o Harness de Hardware

> **Para:** agente responsável pelo motor.
> **De:** harness de hardware (Caio + agente de hardware).
> **O que é:** o conteúdo concreto da **WorkflowSpec v0.2** que o degrau de design de PCB exige.

O harness de hardware roda **sobre** o motor. O padrão `fan_out_sintese` (v0.1) já atende a fatia de **diagnóstico/ingestão** (fan-out paralelo, roda hoje sem mudança). O degrau de **design de PCB** precisa de capacidades que a v0.1 não tem. O próprio `HANDOFF.md` do motor reserva isso: *"padrões novos (chain, tournament) = spec versão 0.2, decisão do orquestrador (Caio)"*. Este documento é essa decisão, detalhada.

**Instrução ao agente do motor:** valide cada requisito contra o **código real** e o **roadmap atual**. Onde já existir, marque atendido. Onde faltar, implemente respeitando as **decisões travadas** (LangGraph puro; nós = funções puras que só falam com `cliente.chamar`; a spec é a dinâmica; eventos JSONL próprios). **Nenhum requisito abaixo pede para relitigar essas decisões** — todos estendem a *spec*, não a filosofia da topologia. Onde houver ambiguidade, **pare e pergunte ao Caio**, não decida.

Os cinco requisitos são coesos: juntos formam um novo `padrao` (sugestão de nome: `grafo_dependencias`) = cadeia ordenada (REQ-1) com passagem de artefato (REQ-5), executores que produzem arquivos (REQ-3), gate determinístico (REQ-4) e loop de revisão (REQ-2).

---

## REQ-1 — Padrão de execução com dependências (DAG / ondas)

**Estado hoje (verificar):** `WorkflowSpec.padrao` é `Literal["fan_out_sintese"]`. O validador em `spec.py` levanta `ValueError` se qualquer subagente usar `depende_de` (mensagem: *"o padrão fan_out_sintese v0 só executa em paralelo"*). O campo `depende_de: list[str]` **já existe**, reservado.

**Necessário:** um novo valor de `padrao` em que `depende_de` é **honrado**. Os subagentes executam em **ordem topológica**, não todos em paralelo. Subagentes sem dependência mútua continuam rodando em paralelo (ondas).

**Contrato:** `depende_de: ["a", "b"]` significa *"este subagente só inicia quando `a` e `b` concluíram com sucesso, e recebe os resultados/artefatos deles como entrada"* (a entrada-artefato é REQ-5). **Ciclo no grafo de dependências = erro de validação.** O loop de revisão é um construto separado e explícito (REQ-2), nunca expresso via `depende_de`.

**Critério de aceite:** uma spec com 4 subagentes em cadeia `A→B→C→D` executa na ordem A,B,C,D; o `log.jsonl` mostra início de B **após** o fim de A; um teste com `ClienteStub` cobre a ordem topológica e rejeita ciclo.

---

## REQ-2 — Loop de revisão com feedback, com teto (bounded)

**Estado hoje (verificar):** existe **retry por subagente** (`Restricoes.max_tentativas`, fluxo attempt→verifier). Mas isso **re-executa o mesmo subagente**. **Não existe** roteamento do resultado de um nó de volta para um nó **upstream diferente**.

**Necessário:** um construto de loop em que a saída (reprovação + lista de erros) de um nó **validador** volta como **entrada** para um nó **upstream nomeado**, que revisa e re-emite, até (a) o validador passar, ou (b) atingir um teto de iterações. **Isto é distinto do retry por subagente.**

**Por quê:** o ciclo de PCB é `Arquiteto → Codificador → Validador(DRC)`. Se o DRC reprova, a correção tem que voltar pro Arquiteto/Codificador — não re-rodar o validador sobre o mesmo artefato.

**Contrato sugerido:** na spec, um bloco
```json
"laco": { "validador": "<id>", "retorna_para": "<id-upstream>", "max_iteracoes": N, "condicao_saida": "<validador passa>" }
```
O resultado estruturado do validador (`pass/fail` + erros) é injetado nas `entradas` do nó upstream na próxima iteração.

**Critério de aceite:** spec com loop onde o validador reprova nas 2 primeiras iterações e passa na 3ª **conclui em 3 voltas**; estouro de `max_iteracoes` encerra com estado explícito *"não-convergiu"* (não trava, não loop infinito); eventos `laco.iteracao` no log. Teste com stub determinístico que falha-falha-passa.

**RESOLVIDO → v0.3.** O motor confirmou (ver [[RESPOSTA-MOTOR-aos-requisitos]]): a v0.2 = REQ-1,3,4,5, com o **humano fechando o loop** (DRC reprova → re-dispara o Arquiteto manualmente). A auto-correção bounded entra só depois de observar os padrões reais de reprovação do DRC — senão se projeta o loop no escuro.

---

## REQ-3 — Executores que produzem artefatos (resultado não-textual) + workspace por execução

**Estado hoje (verificar):** `cliente.chamar(papel, prompt) -> Optional[str]` devolve **texto**. `ferramentas` é uma dica string passada ao `claude -p` (ex.: `"WebSearch"`); `ClienteOpenAICompat.chamar` devolve `None` se ferramentas forem pedidas. **Não há** conceito de resultado-arquivo.

**Necessário:** nós cujo resultado é **um ou mais artefatos em disco** (ex.: `.kicad_pcb`, BOM `.csv`, netlist `.json`, log de DRC), não só texto. O estado do grafo carrega **referências** aos artefatos (caminho + tipo + hash), **nunca o conteúdo**.

**Contrato sugerido:**
- **Workspace por execução:** diretório `runs/<run_id>/artefatos/` onde os artefatos vivem.
- **Resultado estruturado de um nó:** `{ "resumo_texto": str, "artefatos": [{ "nome", "caminho", "tipo", "hash" }] }`. O `resumo_texto` é o que entra no `log.jsonl` e alimenta síntese/verifier; os `artefatos` ficam **referenciados** no estado.
- O cliente continua podendo ser um **modelo** (devolve texto → zero artefatos) **ou** um **executor determinístico** (REQ-4). A interface atual `chamar(...) -> Optional[str]` **não deve quebrar**; o novo retorno estruturado é um caminho adicional, não substituto.

**Critério de aceite:** um nó produz um arquivo em `runs/<id>/artefatos/`; o estado carrega a referência; um nó downstream lê o arquivo **pela referência**. Teste com stub que escreve um arquivo fake e o lê adiante. Resume pós-crash preserva as referências (artefatos não são perdidos pelo checkpointer).

---

## REQ-4 — Nó de ferramenta determinística (sem modelo) como cidadão de 1ª classe

**Estado hoje (verificar):** o verifier do motor é um **subagente-modelo com rubrica** (julgamento de modelo). **Não há** um tipo de nó que seja *"rode este programa local e me dê pass/fail objetivo"*.

**Necessário:** um tipo de nó que executa um **comando local determinístico** (subprocess) — ex.: `kicad-cli pcb drc`, parser de netlist, resolvedor de BOM — **sem chamar modelo**, e cujo resultado estruturado (`pass/fail` + lista de erros) (a) pode **gatear a síntese** e/ou (b) **alimenta o laço da REQ-2**. Esse nó emite eventos no **mesmo** `log.jsonl` e é checkpointado como qualquer nó.

**Distinção importante — três tipos de "gate" não se confundem:**
1. **Verifier-modelo** por subagente (rubrica, julgamento de modelo) — **já existe**.
2. **Gate determinístico de máquina** = ESTE (o "CI verde" do hardware) — **a criar**.
3. **Gate do fundador** via `interrupt()` (humano) — **já existe**.

O harness de hardware usa **os três**.

**Contrato sugerido:** na spec, nó com `"tipo": "ferramenta"`, `"comando": "<executável + args, com placeholders para artefatos de entrada>"`, `"interpreta_saida": "<como extrair pass/fail e erros de exit-code/stdout/arquivo>"`. Um **registro de ferramentas** mapeia nome lógico → executável local. Ferramenta ausente na máquina → **falha explícita** (evento `ferramenta.indisponivel`), nunca silenciosa.

**Convergência aceita (do motor):** esse "registro de ferramentas" **não é catálogo paralelo** — é o **eixo de domínio do Registry** que o motor já ganhou (modelos-executores viraram entidades `.md` com capacidade+custo). Ferramentas determinísticas viram entidades do mesmo Registry; o nó-ferramenta resolve o executável **consultando o Registry**, igual o nó-modelo resolve o modelo. Substrato único. Ver [[RESPOSTA-MOTOR-aos-requisitos]].

**Critério de aceite:** um nó-ferramenta roda um script que sai com código 0 (passa) / 1 (falha + erros no stdout); o motor interpreta **os dois casos** corretamente, emite evento e o resultado gateia/alimenta o loop. Teste com script fake determinístico.

---

## REQ-5 — Passagem de artefato entre subagentes, declarada na spec

**Estado hoje (verificar):** `Subagente.entradas: dict[str, Any]` é **dado estático** declarado na spec. **Não há** como dizer *"minha entrada é o artefato de saída do subagente X"*.

**Necessário:** `entradas` capaz de **referenciar o artefato de saída de outro subagente**, por (`id`, `nome-do-artefato`). Junto com REQ-1 (ordem) e REQ-3 (artefatos), é isto que faz a cadeia `Arquiteto → Codificador → Validador` passar arquivos adiante.

**Contrato sugerido:** um valor de entrada na forma
```json
{ "ref_artefato": { "de": "<id-subagente>", "nome": "<nome-artefato>" } }
```
que o motor resolve para o **caminho real** em tempo de execução.

**Critério de aceite:** subagente B declara entrada referenciando artefato de A; em runtime B recebe o **caminho do artefato real** de A; a validação **rejeita** referência a `id` inexistente ou a subagente **não-ancestral** (sem `depende_de` correspondente).

---

## Fronteira: o que NÃO muda

Nada aqui toca: roteamento por papel/tier (`ClienteRoteador`), `interrupt()` do fundador, formato do `log.jsonl`, LangGraph puro, ou os 12 testes existentes do stub. Tudo é **extensão de spec** + nós novos. A fatia de **diagnóstico** do harness **não precisa de nenhum** destes cinco — roda em `fan_out_sintese` v0.1 hoje. Eles são pré-requisito **só** do degrau de design de PCB.

## Perguntas de volta ao orquestrador (Caio) — RESPONDIDAS

Resolvidas pelo agente do motor em [[RESPOSTA-MOTOR-aos-requisitos]]:

1. Nome do padrão → **`grafo_dependencias`**, aceito.
2. REQ-2 → **v0.3**; v0.2 = REQ-1,3,4,5 com humano fechando o loop.
3. Workspace → **configurável**, default `runs/<run_id>/` (artefato binário não incha o git do motor; o harness de hardware aponta pro seu diretório de fabricação; o estado carrega referência, não conteúdo).

**Ordem de construção da v0.2** (definida pelo motor, por dependência): REQ-3 → REQ-4 (resolvendo executável pelo Registry) → REQ-1 → REQ-5 → (v0.3) REQ-2.

---

*Documento-irmão: [[HARNESS-HARDWARE-diagnostico-e-blueprint]] — onde estes requisitos viram degraus.*
