# HANDOFF CODEX — Fase C / corte 1: conserto na fonte CIENTE DE DEPENDÊNCIAS

## Por quê (contexto travado pela arquiteta — run real 2026-06-25)
Com a rota de dependência (`--rota construcao --modelos modelos-free-escalada.json --auto --escalar`):
prevenção funcionou (ondas sequenciais, divergência grosseira sumiu), Fase C escalou E CONVERGIU
(`plano_testes` media→complexa → aprovado ciclo 2). MAS o gate `cobertura` ainda reprovou por
inconsistência FINA cross-artefato (spec parsing linha-a-linha vs arquitetura "parser CSV real" vs
teste T12; JSON pretty vs compacto; semântica de `row`). O nó `revisao_consistencia` IDENTIFICOU os
riscos mas NÃO os reconciliou — revisar aponta, não conserta na origem.

O `preencher_lacunas` (grafo.py ~587) já é um rascunho do conserto, mas insuficiente:
1. só age sobre `reprovados` do verifier — aqui os 4 passaram no verifier, a falha é só no cobertura;
2. casa lacuna↔nó por substring (`sid in lacuna`) — frágil;
3. re-roda o nó em ISOLAMENTO (`subagente(...)` sem deps) — numa cadeia isso re-quebra a consistência;
4. (loop com teto + auto-mode ficam pro CORTE 2 — NÃO fazer agora).

## Objetivo (corte 1)
Quando o gate `cobertura` decide **preencher**, re-disparar os nós que o AVALIADOR nomear como raiz da
inconsistência, RE-RODANDO também os dependentes deles, em ordem de dependência (via deps_txt), como
REVISÃO (reusa o rascunho anterior, não regenera). Uma rodada. Inerte por default (sem nó nomeado e
sem reprovado = no-op = comportamento atual).

## Mudanças (só motor/grafo.py)

### M1 — Avaliador nomeia o nó culpado (`PROMPT_EVALUATOR`, ~119-127)
Acrescentar à saída JSON o campo `nos_a_refazer` e a instrução. NÃO há snapshot deste prompt (o
byte-idêntico é só do PLANNER), então pode editar livre. Nova última parte:
```
Em "nos_a_refazer", liste os ids (EXATAMENTE como aparecem nos resultados) dos subagentes que são a
ORIGEM de cada lacuna/inconsistência — prefira o nó MAIS A MONTANTE responsável (ex.: se a
especificação contradiz a arquitetura, nomeie o nó da especificação), pois refazê-lo re-deriva os que
dependem dele. Se nada precisa refazer, use [].
Responda APENAS um JSON: {{"aprovado": true/false, "lacunas": ["o que falta", ...], "nos_a_refazer": ["id", ...]}}
```

### M2 — `subagente` aceita revisar a partir de um rascunho dado (~330)
Trocar:
```python
feedback, ultima = payload.get("feedback", ""), None
```
por:
```python
feedback, ultima = payload.get("feedback", ""), payload.get("rascunho_anterior")
```
Assim, quando o re-disparo passa `feedback` + `rascunho_anterior`, a 1ª tentativa já entra no bloco de
REVISÃO existente ("NÃO reescreva do zero…"). Inerte: o fluxo normal não passa `rascunho_anterior` →
`ultima=None` → comportamento atual intacto.

### M3 — `avaliar_cobertura` (~552) propaga `nos_a_refazer`
Ao montar o veredito, ler `nos_a_refazer` (default `[]` quando o modelo/stub não retorna) e unir com os
`reprovados` do verifier (que sempre precisam refazer). Devolver no veredito, ex.:
```python
nos = list(dict.fromkeys([*veredito.get("nos_a_refazer", []), *reprovados]))
veredito = {**veredito, "nos_a_refazer": nos}
```
(Manter o append das lacunas "subagente reprovado: {i}" como hoje.)

### M4 — `preencher_lacunas` (~587) vira recompute CIENTE DE DEPENDÊNCIAS
Substituir o corpo por:
1. `alvo = [sid para sid em veredito["nos_a_refazer"] se sid ∈ spec ids]`. Se vazio → `return resultados, []` (no-op).
2. `closure = alvo + todos os subagentes que (transitivamente) dependem de algum alvo` (via `depende_de`).
   Para fan_out (sem `depende_de`), `closure == alvo`.
3. Re-rodar o `closure` em ORDEM DE DEPENDÊNCIA (mesma lógica de ondas de `executar_grafo_dep`),
   SEMEANDO `concluidos` com os resultados EXISTENTES dos nós FORA do closure (pra deps a montante
   fluírem). Para cada nó do closure, chamar `subagente({...})` com:
   - `deps` = `{d: texto_dependencia(concluidos[d]) for d in sub.depende_de}` (deps já recomputadas/seed),
   - `entradas` resolvidas via `resolver_refs_artefato(..., concluidos)`,
   - `feedback` = lacunas pertinentes (junte as lacunas que citam o id; se nenhuma, use todas as lacunas;
     para um dependente cujo alvo mudou, inclua algo como "uma dependência foi revista; realinhe-se a ela"),
   - `rascunho_anterior` = saída anterior daquele nó (de `por_id_resultado[sid]["saida"]`).
   - emitir `log.evento("lacuna.preenchida", subagente=sid)` por nó (mantém o evento existente).
4. Logar `reconciliacao.iniciada` (nos=closure) no começo e `reconciliacao.concluida` no fim.
5. `return mesclar_resultados(resultados, novos), novos`.

O resto de `avaliar` (decisão preencher → recompute → re-avalia UMA vez → aprovado/final) permanece.

## Restrições (inerte / não-quebra)
- NÃO implementar loop com teto nem auto-preencher (isso é o CORTE 2). Continua UMA rodada, disparada
  pela decisão "preencher" (override `--gate cobertura=preencher` ou gate humano sem `--auto`).
- NÃO tocar em PROMPT_PLANNER (snapshot byte-idêntico), modelos.py, __main__.py, registro.py.
- Default sem `nos_a_refazer`/reprovados = no-op.

## DoD (todos precisam passar)
1. **GUARD backward-compat**: `tests/test_grafo.py::test_gate_cobertura_preencher_reexecuta_reprovado_uma_vez`
   continua VERDE sem edição (fan_out, 1 reprovado nomeado → 1 `lacuna.preenchida`, 1 rodada).
2. **NOVO — conserto na fonte em cadeia**: spec `grafo_dependencias` com nós A→B→C (B depende de A, C
   de B); verifier APROVA todos; cobertura reprova com `nos_a_refazer:["B"]` (e aprova na 2ª avaliação).
   Asserções: recompute re-roda B **e** C (não A); o re-disparo de C vê a nova saída de B em `deps`
   (capture o prompt/deps); eventos `reconciliacao.iniciada` com nos contendo B e C, e `lacuna.preenchida`
   para B e C; resultado final aprovado.
3. **NOVO — revisão, não regeneração**: no re-disparo, o prompt do nó alvo contém o bloco "NÃO reescreva
   do zero" + o rascunho anterior (via `rascunho_anterior`).
4. **Inerte**: cobertura reprova com `nos_a_refazer:[]` e nenhum reprovado → nenhum re-disparo
   (`preencher` é no-op), nenhum evento `reconciliacao.*`.
5. Suíte completa verde (`python3 -m pytest -q`), 206+ passed. `python3 -m compileall -q motor tests` ok.

## Validação do Caio (depois do commit) — NÃO faz parte do código
Rodar SEM `--auto`, escolhendo `preencher` no gate cobertura (ou `--gate cobertura=preencher`):
`python3 -m motor "<missão CSV→JSON>" --registro exemplos/registro --rota construcao --modelos exemplos/modelos-free-escalada.json --escalar --gate cobertura=preencher`
Métrica: o cobertura, após o re-disparo da spec (+ testes re-derivados), passa a APROVAR — ou as lacunas
finas (parsing multilinha, JSON compacto, semântica de `row`) somem? Trazer log.jsonl.

## CORTE 2 (próximo handoff, NÃO agora)
Loop com teto `max_rodadas_reconciliacao` (config + CLI, inerte default 0/1) + integração auto-mode
(sob `--auto`, cobertura resolve "preencher" enquanto houver rodadas, depois "prosseguir"), com estado
de não-convergência. Falsificar que para no teto e não entra em loop infinito.
