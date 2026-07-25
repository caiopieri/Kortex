# HANDOFF CODEX (EXPERIMENTO) — o lift do RAG é conhecimento ou cópia?

> Red-team item 3/5 (verificado): a lift-spec usa validador `contem` (`grafo.py:275` =
> substring casefold) exigindo 5 de 7 jargões que o RAG injeta **dos próprios docs**. O "0/3→3/3"
> pode medir só "com o texto na janela, o modelo repete os termos do texto". Este experimento
> separa **recuperação** (trazer o jargão) de **uso do conhecimento**.

## Por quê
Duas decisões de peso se apoiam nisso: "conhecimento antes de peso **validado**" e "começar a
data-house agora". Se o lift é só cópia, a métrica não sustenta o investimento. Barato de checar.

## O que fazer (rodar + trazer números; código mínimo)
Reusar `scripts/experimento_rag.py` e o dataset de docs (`docs_para_rag.py`). Dois testes:

**(a) Controle negativo — mede se a métrica é só presença de string.**
Criar `exemplos/lift-controle-negativo.json`: MESMO validador `contem` (mesmos jargões), mas o
`fonte_rag` aponta pra um JSONL de **chunks irrelevantes que MENCIONAM os jargões** (ex.: um texto
que cita "prevenção", "reconciliação" etc. em contexto errado/aleatório — gerar um JSONL pequeno à
mão ou por script). Rodar COM esse RAG.
- **Se ainda passar 3/3** → a métrica mede substring, não conhecimento (confirma item 3).
- Se cair → a métrica exige algo do contexto certo (lift mais real do que parecia).

**(b) Métrica derivada — exige combinar, não citar.**
Criar `exemplos/lift-derivado.json`: pergunta cuja resposta **cruza dois docs** e cujo validador
NÃO seja `contem` de jargão presente, e sim `schema_json` sobre uma resposta estruturada (ex.:
exigir campos cuja resposta certa só sai de *relacionar* os docs), ou um verificador com gabarito
escondido do executor. Rodar COM vs SEM RAG (`--repeticoes 3`, `--somente-metrica-deterministica`).

## DoD
1. Os 2 specs validam contra a WorkflowSpec.
2. Rodou COM/SEM (controle negativo e derivado) e **trouxe as taxas** lado a lado.
3. Relato honesto: se o controle negativo passar 3/3, dizer que o lift v2 media cópia; se o
   derivado der lift, é o 1º sinal de uso real. **Não maquiar.**
- Higiene de git: add específicos; nunca `git add -A`.

## O que isto prova e o que NÃO prova
Resolve se a nossa evidência atual de lift é forte ou tautológica. NÃO é a palavra final sobre RAG
em geral — é sobre se **esta** métrica sustenta as decisões que a citam.
