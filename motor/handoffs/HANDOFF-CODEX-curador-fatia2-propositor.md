# HANDOFF CODEX — Curador, fatia 2: PROPOSITOR (ranqueia modelo por papel/tier, read-only)

## Por quê (grounded em dado real, 2026-06-29)
Run multi-modelo real (CSV→JSON, planner=Kimi, juiz/synth=Codex, executores llama→kimi→codex) deu o
primeiro "Aptidao por modelo" limpo. Insight que define a política: **o mesmo modelo é ótimo num papel e
ruim noutro** — codex/gpt-5.4 = executor forte+rápido (arquiteto/complexa aprovado 1ª, 38s) MAS falha
como planner (3/3 JSON inválido); kimi-k2.6 = planner viável (recupera em 1 retry) + executor media ok,
porém mais lento (91s). Conclusão: ranking tem que ser POR (papel, tier), não global. E como o dado
ainda é fino (1 run), o propositor PRECISA ser honesto sobre confiança (calar quando amostra < limiar).

A fatia 1 (Observador) já agrega `por_papel_tier` e `por_modelo`, mas NENHUM cruza os dois. Para
recomendar "no slot (especificador, media), use X em vez de Y" é preciso métrica por (papel, tier, modelo).

## Objetivo (fatia 2)
1. Adicionar ao Observador a agregação por SLOT×MODELO: métricas por (papel, tier, modelo).
2. `propor(perfil, min_amostras=3, custo=None)` que, para cada slot (papel, tier), ranqueia os modelos
   com evidência suficiente e emite uma PROPOSTA read-only (recomendado + ranking + evidência) ou
   "evidência insuficiente". NÃO aplica nada (mudar catálogo = fatia 3, com sombra+certificação).
3. CLI `--propor` que imprime a proposta. Tudo determinístico, read-only, stdlib.

## Mudanças (motor/curador.py + tests/test_curador.py)

### M1 — agregação por slot×modelo
No `_Agregador`, além de `metricas[papel][tier]`, manter `metricas_slot_modelo[(papel, tier, modelo)]`
com as MESMAS métricas (chamadas, respostas, erros, taxa_erro, verifier_julgados,
verifier_aprovados_primeira, taxa_aprovacao_primeira, reprovacoes, escaladas, escaladas_convergidas,
taxa_convergencia_pos_escalada, falhas_internas, latência). O `modelo` já vem no `executor.chamado`
(PR de telemetria-por-modelo); propagá-lo na info do executor e creditar as métricas ao trio. Quando o
modelo for ausente → "desconhecido". Expor em `analisar(...)` como `por_slot_modelo`:
`{ "<papel>/<tier>": { "<modelo>": {métricas...} , ... }, ... }`.

### M2 — `propor(perfil, min_amostras=3, custo=None) -> dict`
Para cada slot de `por_slot_modelo`:
- Candidatos = modelos do slot com `verifier_julgados >= min_amostras` (evidência de qualidade real).
  Se nenhum atinge → `{"status": "evidencia_insuficiente", "amostras": <maior verifier_julgados do slot>}`.
- Score por candidato (determinístico, transparente; documentar a fórmula no código):
  1. QUALIDADE primeiro: `taxa_aprovacao_primeira` maior é melhor; penalizar `taxa_erro` e
     `(1 - taxa_convergencia_pos_escalada)` quando houve escaladas.
  2. desempate por LATÊNCIA: `latencia.mediana` menor é melhor (None vai por último).
  3. desempate final por CUSTO: se `custo` (dict provedor→ordem, ex. {"nv-llama":1,"nv-kimi":2,"codex":3})
     for dado, menor custo é melhor; sem custo, ignora.
- Saída por slot: `{"recomendado": <modelo>, "ranking": [{modelo, score, aprov_1a, taxa_erro, latencia_mediana, amostras}], "evitar": [<modelos com 0% aprov ou taxa_erro alta sobre >=min_amostras>]}`.
- NUNCA recomendar com base em < min_amostras. NUNCA aplicar — só propor.

### M3 — CLI `--propor`
`python3 -m motor.curador <logs> --propor [--min-amostras N] [--custo <json>]` → imprime markdown da
proposta (slot a slot: recomendado + tabela de ranking + evitar + "insuficiente" onde for o caso).
Sem `--propor`, comportamento atual intacto.

## Restrições (inerte / seguro)
- READ-ONLY total: não chama modelo, não muta catálogo/config/roteamento, stdlib puro.
- Aditivo: `analisar` ganha `por_slot_modelo`; CLI sem `--propor` = saída de hoje idêntica.
- Honestidade estatística é REQUISITO, não enfeite: amostra pequena → "insuficiente", não um chute.

## DoD (todos precisam passar)
1. Fixtures sintéticos: (a) slot com 2 modelos, ambos >= min_amostras, qualidades diferentes → recomenda
   o de maior aprovação-1ª; (b) empate de qualidade → desempata por latência; (c) com `custo`, empate de
   qualidade+latência → desempata por custo; (d) slot com amostra < min → "evidencia_insuficiente";
   (e) modelo com 0% aprovação sobre >= min_amostras → aparece em "evitar".
2. `por_slot_modelo` correto: um run com (especificador/media/kimi) e (arquiteto/complexa/codex) gera as
   duas chaves de slot com o modelo certo.
3. CLI `--propor` imprime a proposta; sem a flag a saída é idêntica à atual.
4. Suíte verde (234+); compileall ok.

## Validação do Caio (depois do commit) — NÃO é código
`python3 -m motor.curador logs/ log.jsonl --propor` → ver as recomendações por slot. Com 1-2 runs ainda
vai dar muito "evidência insuficiente" (esperado e correto); o valor cresce conforme acumula runs. Quando
houver evidência, a proposta deve refletir o que já sabemos (planner: evitar codex/gpt-5.4; executor
complexo: codex forte+rápido; etc.).

## DEPOIS (fatia 3, NÃO agora)
Aplicar a proposta com segurança: testar o modelo candidato em SOMBRA (rodar em paralelo sem afetar
produção) + certificação/auditoria antes de mudar o catálogo. É o "testar modelo quando eu adiciono um".
Aptidão por TAGS granulares (codigo-simples/codigo-complexo) entra aqui, sem inverter tier>capacidade.
