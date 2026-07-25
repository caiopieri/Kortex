# Item 3B - Frente A - diagnostico de vazamento

Data do run: 2026-07-04

Comando:

```bash
python3 scripts/experimento_rag.py \
  --spec exemplos/lift-controle-negativo.json \
  --fonte-rag exemplos/rag-controle-negativo-jargoes.jsonl \
  --repeticoes 1 \
  --modelos exemplos/modelos-codex-mini.json \
  --somente-metrica-deterministica \
  --workspace exemplos/saidas-item3B/frente-A-workspace \
  --dump-prompts exemplos/saidas-item3B/frente-A-prompts
```

Modelo/provedor sob teste: `codex/gpt-5.4-mini` via provedor `codex`.

Resultado cru:

```text
SEM RAG: 1/1 aprovadas (100%)
COM RAG: 1/1 aprovadas (100%)
SEM RAG contem: 1/1 aprovadas (100%)
COM RAG contem: 1/1 aprovadas (100%)
logs: exemplos/saidas-item3B/frente-A-workspace
rodada 1: SEM RAG aprovado=True motivo=ok | COM RAG aprovado=True motivo=ok | contem SEM=True COM=True
```

Prompts crus anexados:

- SEM RAG: `exemplos/saidas-item3B/frente-A-prompts/executor-01.txt`
- COM RAG irrelevante: `exemplos/saidas-item3B/frente-A-prompts/executor-02.txt`

## Respostas do diagnostico

1. O prompt inclui `rubrica` / `resultado_esperado` / `contexto` da missao?

Sim. O prompt SEM RAG inclui:

- `Contexto`: "Controle negativo do item 3 red-team: o dataset RAG menciona os mesmos jargoes do lift v2..."
- `Resultado esperado`: pede "nomes proprios usados nos docs internos".
- `rubrica`: pede "tres pilares da Fase C pelos nomes usados nos docs recuperados" e contraste entre V1, verifier LLM e avaliador global.

Esses campos nao trazem literalmente os 7 termos do validador, mas telegrafam a familia da resposta: Fase C, docs internos, validacao V1, verifier LLM, avaliador global e nomes proprios. Isso torna a pergunta adivinhavel para um modelo que ja tenha visto o repo/docs ou que infira a terminologia pelo prompt.

2. Algo do no validador chega ao executor?

No prompt SEM RAG capturado, nao. Os 7 termos do validador (`prevenção`, `escalada de tier`, `reconciliação na fonte`, `dependência em ondas`, `loop bounded`, `determinístico`, `gate de cobertura`) nao aparecem no prompt SEM RAG. Eles aparecem no prompt COM RAG porque o JSONL irrelevante os injeta como contexto recuperado.

3. O feedback de reconciliacao/re-fire nomeia os termos faltantes?

Neste run nao houve retry: `max_tentativas` e 1 e o executor passou na primeira tentativa. Portanto nao ha evidencia de vazamento por feedback de retry nesta Frente A. O vetor continua plausivel para specs com retry se o feedback citar termos faltantes, mas nao foi exercitado aqui.

## Leitura

O controle negativo passou SEM RAG mesmo sem os termos do validador no prompt executor. Portanto a anomalia nao e explicada por vazamento direto da config `contem` ao executor neste run. A explicacao mais consistente e que a propria pergunta/rubrica/resultado esperado tornam a resposta adivinhavel ou recuperavel por conhecimento previo do modelo sobre o projeto. Isso invalida os termos do lift v2 como fatos nao-adivinhaveis.
