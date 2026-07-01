# COMO USAR o motor (uso real, hoje)

> O motor já roda missões de verdade. Este guia é o mínimo pra você usar sem esperar o resto ser
> construído. Visão: `../docs/LEIA-PRIMEIRO.md`. Como funciona por dentro: `docs/EVOLUCAO.md`.

## Rodar uma missão

```bash
cd ~/Desktop/Projects/Orquestrador/motor
source ~/.zshrc >/dev/null 2>&1          # carrega NVIDIA_API_KEY
python3 -m motor "SEU OBJETIVO AQUI" \
  --registro exemplos/registro \
  --modelos exemplos/modelos-free-escalada.json
```

- **Sem `--auto`** (recomendado pra trabalho real): o motor **pausa** e te mostra o **plano** antes de
  executar (você digita `prosseguir` / `editar` / `abortar`) e pausa de novo no gate de **cobertura** se
  algo ficar inconsistente. Esse gate é o anti-retrabalho — é onde você aprova o de cima antes de
  comprometer o de baixo.
- **Com `--auto`**: corre sozinho, sem pausar (bom pra tarefa pequena/exploratória).
- Reconciliação automática (conserta inconsistência na fonte): adicione `--gate cobertura=preencher --reconciliar 3`.
- Consumir um dataset como contexto (RAG): a spec do subagente aceita `fonte_rag` (ver
  `docs/RUNBOOK-EXPERIMENTO-RAG.md`).

## O que você recebe

- **Resposta final** (a síntese) impressa no fim.
- **Artefatos** em `runs/<run_id>/artefatos/` — as saídas de cada papel (arquitetura, spec, testes…),
  gravadas **antes** da síntese. Mesmo se a síntese falhar, os artefatos já estão lá.
- **Log** de eventos em `log.jsonl` (auditoria; é o que o curador e o painel leem).

## Tipos de missão que funcionam bem hoje

- Pesquisa/síntese com verificação (`fan_out_sintese`, o default).
- Construção em etapas com dependência (arquitetura → spec → testes) — use `--rota construcao`:
  `python3 -m motor "..." --registro exemplos/registro --rota construcao --modelos exemplos/modelos-free-escalada.json`

## Arestas ásperas (honestidade — pra você não se assustar)

- **Lento.** Uma missão leva minutos (latência por chamada do provedor). É normal.
- **Juiz Codex pode pendurar.** No fim (evaluator/synthesizer), o `codex` às vezes trava sem retornar. Se
  acontecer: `Ctrl-C` — **os artefatos dos papéis já estão salvos em `runs/`**. Alternativas: rode com
  `--esgotado claude` (reroteia o julgamento), ou use uma config só-NVIDIA. É problema conhecido do
  provedor, não do motor.
- **Planner às vezes erra o JSON na 1ª tentativa** e recupera na 2ª — normal, ele reinjeta o erro.
- **Precisa de `NVIDIA_API_KEY`** exportada (o `source ~/.zshrc` acima resolve).

## Trocar de modelo/provedor

É só trocar o `--modelos <arquivo>`:
- `exemplos/modelos-free-escalada.json` — NVIDIA grátis, planner Kimi, escada llama→kimi→codex (padrão).
- Outras configs em `exemplos/` (codex, opencode, multi). O motor é provider-agnóstico: mudar de provedor
  = editar JSON, não código.

## Onde pedir mais

Falta o quê e o que vem depois: `../docs/ROADMAP.md`. Como o motor evolui: `docs/EVOLUCAO.md`.
