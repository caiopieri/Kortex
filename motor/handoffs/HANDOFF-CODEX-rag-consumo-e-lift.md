# HANDOFF CODEX — consumir dado (RAG) + medir o lift (fecha o loop da data-house)

## Por quê (o beat que justifica a data-house)
A data-house entregou o 1º dataset real (`rust-book-ownership-errors/v0.1`, 36 registros, `MIT OR
Apache-2.0`). Mas **nada na meta-fábrica consome dataset ainda** → a data-house produz no vácuo. Este
handoff constrói a **metade da meta-fábrica** do contrato: um subagente pode consumir um dataset como
**fonte de RAG**, e a gente **mede se melhora** (com vs sem), gateado pelo verifier que já existe.

Disciplina (LEIA-PRIMEIRO / EVOLUCAO): **conhecimento antes de peso** — isto é RAG, NÃO fine-tuning (zero
risco de collapse). Falsificável-cheap-first: retrieval **cru** primeiro (o objetivo é medir o GANHO, não
construir motor de retrieval). Inerte por default (sem `fonte_rag` → nada muda; suíte segue verde).

Dois PRs em ordem, cada um seu commit + testes.

---

## PR 1 — hook de RAG no motor (spec + retrieval + injeção + evento)

### 1a. Campo na spec (`motor/spec.py`, modelo `Subagente`)
Adicionar, opcionais e inertes:
```python
fonte_rag: Optional[str] = Field(default=None, description="caminho de um dataset (JSONL de registros) a consultar como contexto RAG; ausente → sem RAG")
rag_k: int = Field(default=5, description="nº máximo de registros recuperados e injetados")
```
Sem `fonte_rag` = comportamento atual idêntico.

### 1b. Helper de retrieval (novo `motor/rag.py`, stdlib puro)
```python
def carregar_dataset(caminho) -> list[dict]        # lê JSONL; ignora linha malformada; cada registro tem ao menos "conteudo" (e opcional id/licenca/origem)
def recuperar(dataset, consulta: str, k: int) -> list[dict]   # top-k por sobreposição de tokens (crua, case-insensitive) entre `consulta` e registro["conteudo"]; sem embeddings
```
- Retrieval CRU (overlap de tokens) é suficiente pra 36 registros; nada de embeddings/vetor.
- Robusto: dataset inexistente/vazio → `[]` (não quebra; loga e segue sem RAG).

### 1c. Injeção no nó `subagente` (`motor/grafo.py`, onde monta `PROMPT_SUBAGENTE`)
Quando `sub.get("fonte_rag")`:
- `consulta = objetivo + " " + entradas` (o que descreve a tarefa);
- `recs = recuperar(carregar_dataset(fonte_rag), consulta, sub.get("rag_k", 5))`;
- prepor ao prompt um bloco:
  `\n\nCONTEXTO RECUPERADO (fonte: <fonte_rag>, use se relevante; NÃO invente além disto):\n<conteudos concatenados, cada um com sua origem se houver>`;
- emitir evento `rag.consultado` `{subagente, fonte, k, recuperados: <n>, ids: [...]}`.
- Se `recs` vazio → não injeta bloco, mas ainda pode logar `rag.consultado` com `recuperados: 0` (útil pro gap map: "consultou e não achou").
NÃO mudar mais nada do fluxo (rubrica/revisão/escalada intactos).

### 1d. Declarar o evento (`motor/eventos_schema.py`)
Adicionar `rag.consultado` ao ESQUEMA (categoria: `modelo` ou nova `dados`; campos: subagente, fonte, k,
recuperados, ids) — a **guarda anti-drift exige** que todo `log.evento` esteja no esquema.

### PR1 DoD
- Fixture: dataset JSONL minúsculo (3-4 registros com `conteudo`). Subagente com `fonte_rag` apontando pra
  ele → o prompt do subagente contém o bloco "CONTEXTO RECUPERADO" com o(s) registro(s) mais relevante(s),
  e `rag.consultado` é emitido com `recuperados>0`. (Capturar o prompt via ClienteStub, como os testes de
  revisão já fazem.)
- Sem `fonte_rag` → prompt idêntico ao de hoje; nenhum `rag.consultado`. (inerte)
- `fonte_rag` apontando pra caminho inexistente → não quebra, segue sem RAG.
- Teste anti-drift do eventos_schema segue verde (novo evento declarado).
- Suíte verde (249+); compileall; mypy ok.

---

## PR 2 — experimento do lift (com vs sem) + runbook

Objetivo: medir se o dataset gate-verificado melhora o especialista. O CÓDIGO é fino; a MEDIÇÃO real o
Caio roda com modelos reais (como as outras validações).

### 2a. Spec de teste (`exemplos/rag-rust-ownership.json`)
Um `fan_out_sintese` (ou 1 subagente) com uma tarefa de **Rust ownership/error-handling** — ex.: "explique
e corrija o erro de ownership no trecho X" ou "escreva uma função idiomática de tratamento de erro em
Rust" — com rubrica de substância (aborda borrow/move/Result/?, dá exemplo compilável). O subagente
declara `fonte_rag` (deixar como placeholder de caminho, o Caio aponta pro dataset da data-house).

### 2b. Script de comparação (`scripts/experimento_rag.py`)
Roda a MESMA spec **duas vezes**: (a) com `fonte_rag` setado, (b) com `fonte_rag` removido. Para cada,
captura o veredito do verifier (aprovado + motivo) e o resultado do cobertura. Imprime lado a lado:
`SEM RAG: aprovado? / motivo` vs `COM RAG: aprovado? / motivo`. Como LLM é não-determinístico, aceitar um
parâmetro `--repeticoes N` (default 3) e reportar **taxa de aprovação** com vs sem.

### 2c. Runbook curto (`docs/RUNBOOK-EXPERIMENTO-RAG.md`)
Como o Caio roda: setar o caminho do dataset da data-house, `python3 scripts/experimento_rag.py --spec exemplos/rag-rust-ownership.json --fonte-rag <caminho> --repeticoes 3`. Métrica de sucesso: **aprovação
COM-RAG ≥ SEM-RAG** (idealmente melhor). Se sim → loop provado (dado gate-verificado → especialista
melhor), sem treinar nada.

### PR2 DoD
- `scripts/experimento_rag.py` roda com ClienteStub num teste (determinístico): confirma que ele executa
  a spec com e sem `fonte_rag` e coleta os dois vereditos (não precisa de modelo real no teste).
- `exemplos/rag-rust-ownership.json` valida contra o schema (WorkflowSpec).
- Runbook claro. Suíte verde; compileall; mypy ok.

## Validação do Caio (depois dos 2 commits) — não é código
Apontar `fonte_rag` pro dataset `rust-book-ownership-errors/v0.1` da data-house e rodar o experimento.
Trazer o lado-a-lado (aprovação com vs sem). **É a primeira prova ponta a ponta do flywheel** (data-house
→ curador consome → medição), na forma mais barata (RAG). Se provar em software (grader barato), escala.

## Fronteira (não fazer)
- NÃO fine-tuning aqui (é conhecimento, não peso). Fine-tune é Later, gated, quando volume justificar.
- NÃO construir motor de retrieval de produção (embeddings/vetor) — cru serve pro corte. Otimiza depois.
- NÃO acoplar o transporte MCP da data-house agora — ler o dataset local basta pro 1º loop; MCP quando
  houver muitos datasets.
- `fonte_rag` é dado da spec (inerte por default); nada de nó novo no grafo nem autoridade no motor.
