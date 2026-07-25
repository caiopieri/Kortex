# HANDOFF CODEX — marca de perfil de execução (certificado vs rascunho) + curador exclui

> Red-team item 1 (verificado): `grep -r certificad motor/*.py` = 0. A decisão V7/DECISÃO §7
> promete que run "MVP/rascunho" sai marcado e **fora do corpus do curador**, mas isso **não
> existe no código** — `curador.analisar(caminhos)` consome qualquer JSONL sem filtro. A trava
> anti-collapse é hoje só prosa. Este handoff a torna real.

## Por quê (amarra à arquitetura)
Princípio pétreo: **só dado gate-verificado treina/alimenta o curador** (anti-collapse). Sem uma
marca, todo run barato (gates soltos) polui o perfil que o curador usa pra propor catálogo. Fechar
isso é pré-requisito da fatia 3.

## O que fazer (1 commit)
1. **CLI** (`motor/__main__.py`): flag `--rascunho` (default ausente = **certificado**). Quando
   presente, o run é marcado como rascunho.
2. **Evento** (`motor/eventos_schema.py`): declarar tipo novo `run.perfil` com campo
   `perfil` ∈ {"certificado","rascunho"} (categoria adequada). Emitir **uma vez no início do run**
   (onde hoje sai `spec.recebida`/`spec.criada`), com o perfil escolhido.
3. **Curador** (`motor/curador.py`): ao carregar runs, ler o `run.perfil` de cada run; por
   **default EXCLUIR** runs `rascunho` da agregação (observador, por_modelo, por_slot, custo,
   propositor). Flag `--incluir-rascunho` (CLI do curador) inclui. Run **sem** o evento (telemetria
   antiga) = tratado como **certificado** (legado, inerte).

## Restrições
- Aditivo/inerte: sem `--rascunho` e sem o evento, comportamento **idêntico** ao de hoje.
- stdlib; sem chamar modelo. Não mexer no roteador/grafo além de emitir o evento.
- Higiene de git: `git status` + add específicos; nunca `git add -A`.

## DoD (falsificável)
1. Run com `--rascunho` emite `run.perfil` perfil=rascunho; sem a flag, perfil=certificado.
2. `curador` sobre um dir com 1 run certificado + 1 rascunho: por default agrega **só** o
   certificado; com `--incluir-rascunho`, agrega os dois.
3. Run legado (JSONL sem `run.perfil`) é agregado como certificado (regressão intacta).
4. Guarda anti-drift do schema passa (o novo tipo declarado). Suíte verde; mypy ok.

## O que isto prova e o que NÃO prova
Prova que rascunho é marcável e excluível. NÃO limpa a telemetria **já** coletada sem marca —
vale uma auditoria à parte (o Caio decide) antes da fatia 3.
