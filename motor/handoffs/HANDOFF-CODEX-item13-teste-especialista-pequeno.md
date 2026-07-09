# HANDOFF CODEX (EXPERIMENTO) — a tese do especialista pequeno tem um teste barato não rodado

> Red-team item 13 (endossado): a versão FRACA da tese central do flywheel — "**pequeno + RAG +
> ferramenta bate o generalista em custo+qualidade numa tarefa estreita já medida**" — é testável
> **hoje, sem treinar nada**: o gate determinístico existe, o livro-razão existe, o roteamento por
> modelo existe. Nunca rodou. Se falhar aqui — na tarefa mais estreita, com o grader mais barato,
> com conhecimento injetado — a tese precisa de revisão **antes** de qualquer investimento em
> data-house/fine-tune. Se passar, é o 1º dado real a favor.

## Por quê
Toda a estratégia de longo prazo (fábrica de especialistas, data-house) aposta nessa tese. Ela é a
suposição central ainda não provada do PRD. Custo do teste: horas, não semanas.

## O que fazer (rodar A/B + trazer números)
Tarefa: **o nó mais estreito e já medido** — o transformador CSV→JSON (ou uma subtarefa isolada do
Logisti). Fixar a MESMA missão/spec e variar só o executor daquele nó:
- **Braço (a) — especialista barato:** modelo pequeno free (ex.: llama-3.3-70b ou um coder pequeno
  via NVIDIA/opencode) + `fonte_rag` apontando pro dev-harness/docs relevantes + nó ferramenta
  (teste determinístico) se aplicável.
- **Braço (b) — generalista topo:** o modelo forte (Codex/Claude) no mesmo nó, sem RAG.

Rodar **N≥15–20 por braço** (repetições), coletando por braço:
- **Qualidade:** taxa de aprovação do **gate determinístico** (não o verifier LLM — usar
  `--somente-metrica-deterministica` onde couber, pra neutralizar juiz instável).
- **Custo:** do livro-razão (`curador --custo`), lembrando que é **$ estimado** (tabela manual).
- **Latência:** mediana/p90.

Pode usar/estender `scripts/experimento_rag.py` como molde (ele já faz repetições e liga/desliga
`fonte_rag`); se precisar, um `scripts/experimento_especialista.py` que troca o executor do nó-alvo
entre os dois braços com a mesma spec.

## DoD
1. Os dois braços rodam N repetições sobre a MESMA tarefa.
2. Tabela lado a lado: aprovação determinística · $ estimado/run · latência p50/p90 — por braço.
3. Veredito honesto: (a) bate (b) em custo **e** qualidade? empata? perde? **Trazer os números
   crus, não a conclusão maquiada** — resultado negativo é sinal valioso (refuta a tese cedo).
- Higiene de git: add específicos; nunca `git add -A`.

## O que isto prova e o que NÃO prova
Prova (ou refuta) a tese **na forma fraca, sem treino** — a mais barata de testar. NÃO prova a
forma forte (fine-tune governado) — mas se a forma fraca já falha, a forte não se justifica.
