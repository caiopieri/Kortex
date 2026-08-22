# `log-legado-10-runs.jsonl` — ledger legado real, capturado da produção

**Não é sintético.** São os 426 eventos do `motor/log.jsonl` do runner
(192.168.15.50), capturados via `GET /dados` em 2026-08-21, antes de a máquina
entrar em manutenção. Ficam aqui porque é **o único caso real** de um fenômeno
que nenhum checkout local reproduz.

## O que este arquivo tem que nenhum outro tem

**Dez runs concatenadas num arquivo só**, sem nenhuma fronteira detectável:

```
run.perfil      10   nos seq 2, 40, 103, 144, 180, 216, 252, 288, 342, 385
spec.recebida   10   8x ebay-portao-de-processo, 2x cli-tarefas
desfechos        9   nove tarefa.concluida
quebras de seq   0
t retrocede em   —   nunca
```

Três coisas decorrem disso, e são exatamente os casos que precisam de teste:

1. **O heurístico antigo erraria aqui.** Segmentar run por queda de `t` juntaria
   as dez num bloco só, em silêncio. Foi este arquivo que deu evidência empírica
   para remover `test_carregar_runs_separa_jsonl_concatenado_quando_t_reinicia`
   (issue #24). Não é caso construído: é o único ledger de produção que temos.

2. **Uma run parou num portão humano e nunca voltou.** `escalado {para: fundador}`
   no `seq 38`, sem nenhum `decisao.*` nos 426 eventos. É a única das dez sem
   desfecho, e é a primeira (`seq 2-39`). A instrumentação está correta —
   `grafo.py` emite `escalado` → `interrupt()` → `decisao.fundador` na retomada;
   falta porque a retomada nunca aconteceu.

3. **O balde legado se descreve como se fosse uma run** (issue #29). Nenhum
   evento tem `run_id`, então tudo cai em `legado:sem-proveniencia` — e aí
   `missao` sai da primeira `spec.recebida` (`ebay-portao-de-processo`) enquanto
   `estado` sai do último desfecho (que é de uma `cli-tarefas`).

## A armadilha de medição que este arquivo contém

**290 destes eventos carregam `run_id`, e nenhum deles prova que a issue #24
pegou.** São todos `custo.*` — `custo.reservado` 144, `custo.reconciliado` 143,
`custo.bloqueado` 3 — proveniência monetária que já existia antes. Dos 1194
eventos estruturais do corpus completo, zero. Quem contar `run_id` sem separar
por tipo de evento conclui o oposto do que é verdade.

## O que este arquivo NÃO autoriza

O `caminho` dos eventos `artefato.atualizou` contém o `run_id`
(`runs/<hex>/artefatos/...`), porque o motor construiu o caminho a partir dele.
**Isso não é permissão para recuperar identidade por parsing de caminho.** A
decisão da #24 é explícita: identidade é do envelope; caminho é localização, não
identidade. E aqui o caminho é absoluto para outra máquina — comparar por caminho
absoluto faz todo artefato virar órfão em qualquer outro checkout.
