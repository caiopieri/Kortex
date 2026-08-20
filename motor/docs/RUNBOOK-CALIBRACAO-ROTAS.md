# Runbook — Run real de calibração das rotas (B2) + dados pra Fase C

> **Quem roda:** Caio, no Mac. **Objetivo duplo:** (1) calibrar a escolha automática de rota
> (B2) e (2) gerar dados reais de execução/reprovação que a Fase C (loop de auto-correção)
> precisa. **Sem mexer em código** — é só rodar e trazer o log.

## Pré-requisitos
- No diretório `Orquestrador/motor`, com o ambiente do motor (langgraph instalado; `codex` e
  `claude` no PATH — você já tem).
- O run usa `exemplos/registro/` (já criei): contém **modelos + rotas no mesmo diretório**
  (claude=juiz/fallback, codex=executor, e as 2 rotas pesquisa-sintese/construcao). É esse "tudo
  junto" que o `--registro` exige pra escolher rota E rotear modelo de uma vez.

## Os dois prompts (escolhidos pra DISCRIMINAR as rotas)
- **Prompt A — deve escolher `construcao`** (etapas dependentes → grafo_dependencias):
  > Projete um pequeno utilitário de linha de comando que converte um arquivo CSV em JSON com
  > validação de cabeçalho. Entregue em etapas: a arquitetura e decisões de design; a
  > especificação da implementação baseada nessa arquitetura; e um plano de testes que valide a
  > implementação contra o design.
- **Prompt B — deve escolher `pesquisa-sintese`** (frentes independentes + síntese):
  > Compare três abordagens de parsing de CSV em Python (csv da stdlib, pandas, polars) e
  > recomende uma para um utilitário CLI leve, com prós e contras de cada.

## Comandos (rode os dois, um de cada vez)
```bash
cd ~/Desktop/Projects/Orquestrador/motor

# Prompt A (espera-se rota = construcao)
python3 -m motor "Projete um pequeno utilitário de linha de comando que converte um arquivo CSV em JSON com validação de cabeçalho. Entregue em etapas: a arquitetura e decisões de design; a especificação da implementação baseada nessa arquitetura; e um plano de testes que valide a implementação contra o design." --registro exemplos/registro

# Prompt B (espera-se rota = pesquisa-sintese)
python3 -m motor "Compare três abordagens de parsing de CSV em Python (csv da stdlib, pandas, polars) e recomende uma para um utilitário CLI leve, com prós e contras de cada." --registro exemplos/registro
```
- O run **pausa no gate de revisão do plano** (default). Aí você vê o plano; digite `prosseguir`
  pra seguir (ou `abortar`). É de propósito: você confirma a rota/plano antes de gastar.
- **Opcional, pra poupar seu limite do Claude:** acrescente `--esgotado claude` no fim — reroteia
  o juiz/síntese pro Codex (perde a independência cross-model, mas não toca o Claude). Pra
  calibração de ROTA tanto faz; use se quiser economizar.
- **Opcional, sem pausa:** acrescente `--auto` pra correr sem parar no gate (inspeciona depois no log).

## O que observar (e me trazer)
O motor escreve eventos em `runs/<run_id>/log.jsonl` (ou no workspace passado por
`--workspace`). Depois de cada run, aponte o comando para o log daquela run:
```bash
grep "rota.escolhida" runs/<run_id>/log.jsonl     # a linha-chave da calibração
```
Me traga, pra cada prompt:
1. **A linha `rota.escolhida`** — tem `rota`, `padrao`, `fallback`. É o sinal central:
   - A esperada: Prompt A → `rota=construcao, padrao=grafo_dependencias, fallback=false`;
     Prompt B → `rota=pesquisa-sintese, fallback=false`.
   - Se vier **errado** (ex.: A escolheu pesquisa-sintese, ou `fallback=true`) → é exatamente o
     dado de calibração. Eu afino o texto do `PROMPT_SELETOR_ROTA` (não mexe no mecanismo).
2. **Concluiu ou travou?** Se concluiu, ótimo (engine ponta-a-ponta com rotas vivo). Se algum
   subagente/portão reprovou, **me traga as linhas de `portao.reprovado`, `ferramenta.*`, ou
   `(synthesizer não respondeu)`/`evaluator sem JSON`** — esses são os **padrões de falha reais**
   que vão desenhar a Fase C (o loop de auto-correção).
3. (Opcional) o `log.jsonl` inteiro de cada run, se quiser que eu leia o trace completo — mas
   o `grep` acima + onde travou já basta pra calibração.

## Por que este run
- Valida o engine inteiro num **prompt aberto** com a rota sendo escolhida sozinha (o que B2
  destravou) — não um spec à mão.
- Os dois prompts juntos provam que o seletor **discrimina** rota (não escolhe sempre a mesma).
- O que reprovar vira o insumo da **Fase C** — assim eu desenho o loop com dados reais, não no escuro.

> Nota: se `codex`/`claude` derem throttle (limite), o run pode falhar rápido — não tem problema,
> é dado também (mostra robustez do roteamento). Traga o que aparecer no log.
