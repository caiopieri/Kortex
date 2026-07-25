# HANDOFF CODEX — lift-test v2 (corpus que o base IGNORA + métrica que não satura)

## Por quê (o v1 mediu a coisa errada)
Lift-test v1: SEM RAG 3/3, COM RAG 3/3 — sem lift, mas por dois defeitos de DESENHO, não porque RAG não
sirva: (1) métrica binária aprovado/reprovado **saturou** (baseline 100% → cega a melhoria); (2) o corpus
(Rust ownership) é dos mais treinados que existem — o modelo base **já sabe**, então RAG não tem o que
adicionar. RAG só mostra ganho sobre corpus que o base **ignora**, medido por sinal **discriminante**.

Este v2 conserta os dois: corpus = **nossos próprios docs** (o base ignora nosso jargão) + métrica =
**validador determinístico `contem`** (V1) checando termos/fatos específicos que só os docs fornecem.

## O que fazer

### 1. Corpus ignorante (nossos docs → JSONL)
Script `scripts/docs_para_rag.py` que chunka nossos markdowns internos em `rag-flat.jsonl` (mesmo formato
da data-house: uma linha/chunk, campo `conteudo` + `origem`). Fontes: `../docs/*.md`, `docs/*.md`
(motor), `../dev-harness/docs/*.md`. Chunk por seção/parágrafo, tamanho moderado. Saída:
`exemplos/rag-docs-metafabrica.jsonl` (não commitar o jsonl se preferir; é artefato de experimento).

### 2. Spec com pergunta sobre NOSSO interno + validador determinístico como métrica
`exemplos/lift-docs-metafabrica.json`: um subagente cujo objetivo é responder uma pergunta cuja resposta
só está nos nossos docs — ex.: *"Explique os três pilares da Fase C do motor e como o validador
determinístico difere do verifier."* + um nó **`validador` `contem`** (V1) que exige os termos corretos e
específicos do nosso vocabulário, ex.: `requer: ["prevenção", "escalada de tier", "reconciliação",
"determinístico", "cobertura"]`, `min: 4`. (Ajuste os termos ao que os docs realmente dizem — confira nos
arquivos; a graça é que são jargão nosso, não adivinhável.)

O validador `contem` é a **métrica discriminante**: sem RAG, o base não produz nosso jargão específico →
reprova; com RAG, produz → aprova. Não satura como o "aprovado: ok" genérico.

### 3. Rodar com vs sem (mesma comparação do experimento)
`python3 scripts/experimento_rag.py --spec exemplos/lift-docs-metafabrica.json --fonte-rag exemplos/rag-docs-metafabrica.jsonl --repeticoes 3 --modelos exemplos/modelos-free-escalada.json`
(o `experimento_rag.py` já roda com/sem `fonte_rag`). Reporte a **taxa em que o validador `contem`
passou COM vs SEM RAG** — não só o verifier LLM.

## DoD
1. `docs_para_rag.py` gera o JSONL a partir dos docs (cada linha com `conteudo`+`origem`; ignora vazio).
2. A spec valida contra o WorkflowSpec e inclui o nó validador `contem` com termos do NOSSO jargão.
3. O experimento roda e imprime COM vs SEM pela métrica do validador determinístico (não só o verifier).
4. Traga os números. **Esperado:** SEM RAG passa pouco/nada no `contem` (base ignora nosso jargão); COM
   RAG passa alto → **lift visível**. Se COM ainda ≈ SEM, é sinal REAL (retrieval não trouxe o chunk
   certo, ou chunking ruim) — reporte, não maquie.
- Antes de qualquer commit: `git status` + `git checkout --` em tracked deletado (mount instável); nunca `git add -A`.

## Nota (o que este teste prova e o que não prova)
Prova (se der lift): a máquina **RAG + V1 + medição** enxerga ganho quando o corpus é ignorado pelo base —
é o beat do flywheel. NÃO prova ainda que RAG ajuda em QUALQUER tarefa (depende do corpus vs conhecimento
do base) — mas é isso mesmo: o valor da data-house é justamente dado que o modelo não tem. Corpus externo
obscuro/recente vem depois, com a data-house; usar nossos docs agora é o teste mais barato e convincente.
