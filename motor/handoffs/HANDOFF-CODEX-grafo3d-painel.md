# HANDOFF CODEX — Grafo 3D no painel (design aprovado → página real)

> Design aprovado pelo dono no Claude Design (P2 "Grafo 3D real" do projeto de interface).
> Mock importado em `docs/design/mockups/Grafo3D.dc.html` — é a **referência visual canônica**
> (cores, HUD, pills, glow, partículas). Os dados do mock são fictícios; a implementação liga
> ao sinal real do painel.

## Por quê (amarra à arquitetura)
Princípio do brief de design: **vivacidade = sinal real** — nada anima sem evento do motor.
O painel (`motor/motor_painel/painel.py`) já serve `/dados` = `{nos, arestas, eventos}`
derivado do `log.jsonl`. O Grafo 3D é uma **vista nova sobre o mesmo payload** — zero mudança
no motor, zero endpoint novo além da rota da página.

## O que fazer (1 commit)
1. **`motor/motor_painel/grafo3d.html`** (novo): página autocontida que:
   - Carrega `three@0.160.0` e `3d-force-graph@1.73.4` via unpkg (como no mock).
   - Faz `fetch('/dados')` e mapeia o grafo real: nós `{id, tipo}` do payload
     (tipos hoje: `nucleo/executor/subagente/portao/decisor` — ver `grafo_do_log`) e
     `arestas {de, para}` → `{source, target}`.
   - **Cores por tipo real** (adaptar a paleta do mock): motor/executores=azul `#3E63DD`,
     subagentes=branco `#E8E6E1`, portões aprovados=verde `#30A46C`, portão reprovado/decisão
     pendente do fundador=âmbar `#E8A33D` (o "precisa de você"), sem evento recente=cinza `#5A5F66`.
   - **Aresta "live"** (partículas âmbar) só se o nó de destino tem evento nos últimos N eventos
     do log (fluxo só onde há run ativo — nada anima sem sinal).
   - HUD conforme o mock: legenda no topo, pills embaixo (pausar física, ⚡ fluxo, slider de
     opacidade de arestas), card lateral ao clicar num nó (id, tipo, último evento, status).
     Camadas macro/completo podem ficar de fora (não há hierarquia projeto/workflow no payload
     ainda) — se omitir, remova as pills, não deixe botão morto.
   - Refresh: re-fetch de `/dados` a cada ~3s atualizando `graphData` (sem recriar a cena).
2. **`motor/motor_painel/painel.py`**: rota `GET /grafo3d` servindo o arquivo novo; link
   discreto "3D" no `painel.html` existente (uma âncora, nada mais).
3. **Teste** (`motor/tests/test_painel.py`): rota `/grafo3d` responde 200 com `ForceGraph3D`
   no corpo; `/dados` e `/` intactos (regressão).

## Restrições
- Aditivo: `painel.html` muda só o link; `painel.py` só a rota; **nada no motor/**.
- Sem build step, sem npm — HTML único, CDN, como o resto do painel.
- Higiene de git: add específicos (`grafo3d.html`, `painel.py`, `painel.html`,
  `test_painel.py`, e o mock em `docs/design/mockups/` + este handoff); nunca `git add -A`.

## DoD (falsificável)
1. `python3 motor_painel/painel.py` + abrir `http://localhost:8378/grafo3d` com um `log.jsonl`
   real (ex.: copiar `motor/exemplos/log-amostra.jsonl`) → grafo 3D renderiza os nós do log
   (não os fictícios do mock).
2. Log com `portao.reprovado`/`decisao.pendente` → nó correspondente âmbar.
3. `log.jsonl` vazio/ausente → página abre sem erro (grafo vazio, sem exception no console).
4. Suíte verde (incl. teste novo da rota); `/` e `/dados` intactos.

## O que isto prova e o que NÃO prova
Prova que o design 3D roda sobre sinal real do motor. NÃO é a interface viva completa (multi-
projeto/workflow/entidades do mock exigem eventos que ainda não existem — camada macro entra
quando a telemetria tiver esse eixo) e NÃO cobre tema light.
