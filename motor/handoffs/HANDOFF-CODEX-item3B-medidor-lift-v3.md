# HANDOFF CODEX (item 3B) — medidor de lift v3 + diagnóstico de vazamento (pacote único)

> Sequência do item 3. Veredito do Arquiteto (2026-07-04, `LOG-VERIFICACAO.md`): o lift v2 foi
> **invalidado duplamente** — (1) o controle negativo passou 3/3 (a métrica `contem` mede transporte
> de substring); (2) a MESMA pergunta passou 2/2 **sem RAG nenhum**, contradizendo o baseline 0/3 de
> 2026-07-02 (os 7 termos são palavras adivinháveis, min 5/7 — o 0/3 era ruído de amostragem/roteamento).
> Consequência já aplicada nos docs: data-house **pausada** atrás deste medidor.
>
> Este handoff empacota **4 frentes relacionadas em um pacote só** (pedido do dono: reduzir ciclos).
> Podem virar commits separados (A+B juntos se pequenos; C; D), mas o relato é um só.

## Por quê

Sem uma régua de lift confiável, nenhuma decisão sobre RAG/data-house/"conhecimento antes de peso" tem
lastro. Gate antes de flywheel: **a régua é o gargalo**. Este pacote refaz a régua e explica a anomalia.

---

## Frente A — diagnóstico de vazamento (fazer PRIMEIRO; informa o resto)

Explicar *por que* a pergunta do lift passou sem RAG. Capturar o **prompt exato** que o executor
recebe rodando `exemplos/lift-controle-negativo.json` SEM RAG (1 repetição basta).

- Preferir mecanismo existente (a telemetria/log já registra o prompt?). Se não houver, flag de debug
  **só em `scripts/experimento_rag.py`** (ex.: `--dump-prompts DIR` salvando o prompt de cada chamada).
  **Não tocar no motor core.**
- Responder no relato, com o prompt cru anexado:
  1. O prompt inclui `rubrica` / `resultado_esperado` / `contexto` da missão? (Se sim, quanto desses
     campos telegrafa os termos do validador?)
  2. Algo do **nó validador** (os 7 termos, a config `contem`) chega ao executor por qualquer via?
  3. O feedback de reconciliação/re-fire nomeia os termos faltantes? (Vetor de vazamento em retry.)

## Frente B — lift-recuperação v3 (a régua refeita)

**Regra central anti-tautologia:** cada fato exigido deve ser um **nome próprio arbitrário do projeto**
que (a) existe verbatim em ≥1 chunk de `exemplos/rag-docs-metafabrica.jsonl`; (b) **não aparece** na
pergunta, rubrica, objetivo, contexto da missão nem em nada visível ao executor; (c) não é adivinhável
por fluência — e o braço SEM RAG é o teste *empírico* disso, não opinião.

1. Criar `exemplos/lift-v3-fatos.json`: 1 executor com ~5 perguntas curtas cujas respostas são 5 fatos
   assim; validador `contem` com `requer` = os 5 tokens, `min: 4` (tolera 1 falha de retrieval sem
   contaminar o veredito; a presença por fato é relatada à parte). Fatos **já verificados presentes**
   no corpus atual: `auto_esgotar` (chunk LEIA-PRIMEIRO#14), `aresta.fluxo` e `custo.tick` (ROADMAP#14).
   Achar +2 pelo mesmo critério (grep no JSONL; provar no relato).
   - Exemplo de pergunta boa: "Qual é o nome da política de failover por custo no roteamento de
     modelos?" → resposta `auto_esgotar` (a pergunta não contém o token nem o parafraseia).
2. Criar `exemplos/rag-controle-negativo-sem-fatos.jsonl`: chunks fora de domínio que **não contêm
   nenhum** dos 5 tokens (grep provando ausência). Este é o controle negativo correto para recuperação:
   testa se "RAG qualquer" ajuda, sem oferecer as strings.
3. Rodar **3 braços × 5 repetições**, `--somente-metrica-deterministica`, **mesmo modelo pinado nos 3
   braços** (registrar modelo+provedor+data no relato; se o provedor cair no meio, re-rodar o braço
   inteiro no substituto — não misturar):
   - (1) SEM RAG · (2) COM RAG relevante (`rag-docs-metafabrica.jsonl`) · (3) COM RAG irrelevante-sem-fatos.
4. **Critério de falsificação pré-registrado:** lift real = SEM RAG ≤1/5 **e** irrelevante ≤1/5 **e**
   relevante ≥4/5. Se SEM RAG >1/5 → o fato vazou ou é adivinhável: identificar qual (presença por
   fato), substituí-lo e re-rodar, relatando a troca. Qualquer outra combinação = **sem lift provado**;
   trazer os números crus sem interpretação.

**Nota honesta de escopo:** esta métrica prova **recuperação** (o RAG traz fato que o base não tem) —
que é o mínimo pra data-house voltar à mesa. Não prova síntese/uso combinado; isso é a Frente C.

## Frente C — lift-síntese (redesenho do derivado; sem juiz automático nesta rodada)

O 1/3 vs 1/3 do derivado foi **inconclusivo por construção**: os `pattern` regex do schema criam piso
artificial (resposta semanticamente certa reprova por ordem de palavras) e n=3 não separa nada.

1. Editar `exemplos/lift-derivado.json`: **remover todos os `pattern`** do schema (manter só
   `required`/`type`/`minItems`/`minLength`). O `schema_json` passa a medir apenas formato — é o que
   ele sabe medir.
2. Rodar COM vs SEM RAG, n=3, mesmo modelo pinado; **salvar a resposta crua de cada repetição** em
   arquivos (ex.: `motor/exemplos/saidas-lift-derivado/`) e apontar os caminhos no relato.
3. **Não concluir** lift/não-lift de síntese: o julgamento sobre as respostas cruas é do Arquiteto.
   Automatizar um grader de síntese (juiz com gabarito escondido) é decisão separada, tomada depois
   do resultado da Frente B.

## Frente E — matriz 2×2 do especialista pequeno (completa o item 13)

Veredito do item 13 (LOG 2026-07-04): o A/B mudou duas variáveis de uma vez (modelo E RAG), então
não atribui o ganho a nada. Completar a matriz **2×2: modelo × RAG on/off**, n≥5 por célula:

- **Modelos:** o pequeno do item 13 (codex gpt-5.4-mini) vs um generalista maior **não-Claude**
  (codex/opencode/gemini — o que estiver estável; registrar qual).
- **Tarefas (2):**
  1. A mesma do item 13 (`especialista-csv-json.json`, schema_json) — é o piso; esperamos que o
     pequeno passe ATÉ sem RAG (se passar, o ganho do item 13 era só tier, não RAG).
  2. Uma tarefa onde o pequeno **sem conhecimento falha**: reusar a spec da Frente B
     (`lift-v3-fatos.json`) — fatos não-adivinháveis só recuperáveis do corpus. É aqui que a tese
     "especialista barato **+RAG**" é de fato testada.
- Mesmas métricas do item 13 (taxa de aprovação no validador + custo estimado + latência), mesmo
  pin por célula, números crus em tabela 2×2 por tarefa.
- **Leitura pré-registrada:** a tese só avança se `pequeno+RAG` ≈ ou > generalista na tarefa 2
  **e** mais barato. Se o pequeno sem RAG já resolve tudo, relatar isso — é roteamento por tier,
  não especialista+RAG.

## Frente D — registrar o aprendizado na biblioteca de validadores

Append em `dev-harness/docs/biblioteca-de-validadores.md`, seção nova (texto pronto, ajustar só o encaixe):

> ### Quando `contem` mede algo (anti-tautologia — aprendido no red-team item 3, 2026-07-04)
> 1. O termo exigido deve ser **não-adivinhável** (nome próprio arbitrário, não palavra comum) e
>    **ausente de tudo que o executor vê** (pergunta, rubrica, contexto, feedback de retry).
> 2. Se o termo está no contexto injetado (RAG/deps), `contem` mede **transporte de substring**, não
>    conhecimento. Isso ainda é útil (mede recuperação), mas nomeie a claim corretamente.
> 3. Nunca alegue lift sem braço de controle SEM-fonte com **n≥5 e baseline estável** — um 0/3 de
>    amostra pequena é ruído, não piso.
> 4. `schema_json` com `pattern` regex sobre **texto livre** é frágil (falso-reprova prosa correta);
>    regex só sobre valores mecânicos (IDs, enums, formatos).

---

## Restrições

- **Regra do Fundador (2026-07-04): nenhum braço de experimento usa Claude como modelo sob teste** —
  pinar em codex/opencode/gemini. (Claude não gasta cota em teste do motor.)
- **Inerte-por-default:** nenhuma mudança em `motor/motor/` core; no máximo a flag de debug no
  `scripts/experimento_rag.py` (Frente A). Se a telemetria já expõe o prompt, zero código novo.
- **Não maquiar.** Números crus lado a lado; anomalia relatada é mais valiosa que resultado bonito.
- Higiene de git: adds específicos; nunca `git add -A`; nada deletado.

## DoD (critérios de falsificação)

1. Prompt cru do executor anexado + as 3 perguntas de vazamento respondidas (Frente A).
2. `lift-v3-fatos.json` valida contra a WorkflowSpec; relato prova por grep: cada fato **existe** no
   corpus relevante, **ausente** da spec visível ao executor e **ausente** do JSONL irrelevante.
3. Tabela braço × repetição (15 runs) + presença por fato + modelo/provedor registrado; veredito
   contra o critério pré-registrado da Frente B.4 (ou "sem lift provado", cru).
4. Derivado sem regex rodado (3×2); respostas cruas salvas e caminhos apontados.
5. Biblioteca de validadores com a seção nova.
6. Matriz 2×2 (Frente E) rodada nas 2 tarefas, n≥5 por célula, tabelas cruas + modelos/provedores
   registrados; veredito contra a leitura pré-registrada (ou "inconclusivo", cru).
7. Suíte inteira verde; mypy ok se tocou código.

## O que isto prova e o que NÃO prova / Onde isto pode dar errado

- Prova, no máximo, **recuperação com régua honesta** — suficiente pra reavaliar a data-house, não
  pra declarar "conhecimento antes de peso validado" (isso exige síntese, Frente C + grader futuro).
- **Provedor instável** (pendência conhecida) pode impedir o pin consistente — sem pin, o resultado
  não vale; melhor atrasar que misturar modelos.
- **Retrieval pode não trazer o chunk do fato** (k, embedding): por isso min 4/5 e presença por fato —
  se um fato falhar sistematicamente nos 3 braços, é retrieval, não conhecimento; relatar separado.
- n=5 por braço ainda é amostra pequena: o resultado é **sinal forte**, não estatística. Se der
  fronteiriço (ex.: relevante 3/5), não force veredito — devolva os números.
