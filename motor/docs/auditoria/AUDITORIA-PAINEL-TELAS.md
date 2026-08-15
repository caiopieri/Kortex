# Auditoria do painel — tela por tela (2026-07-11)

> **STATUS 2026-07-11 (pós-refatoração):** os achados abaixo foram o diagnóstico inicial
> (❌). Todos endereçados nos Lotes A/B/C/D e **verificados ✅** (ver `LOG-VERIFICACAO.md`,
> entrada de 2026-07-11 "Refatoração do painel"). Resumo do que mudou:
> - **9 bugs de fiação** (tabela abaixo) — corrigidos e conferidos no diff item-a-item.
> - **Teatro** — KPIs/séries fabricados viram dado real ou "—" com legenda; NovaMissao agora
>   monta spec real + comando CLI copiável **e** despacha de verdade via `POST /dados/missoes`
>   (lock de run única, consentimento explícito, Popen sem shell); Conexoes/Agentes/Skills/
>   Runners marcados "estático"; chats falsos desabilitados.
> - **Grafo 3D** ligado ao `/dados` real e respeitando o tema claro (cores por CSS var).
> - **Configurações** (densidade/animações/streaming) agora têm consumidores reais.
> - Suíte relevante **432 passed**; guardas do despacho (403/400) confirmadas por curl sem
>   disparar run. As 52 falhas da suíte total são os experimentos red-team `test_auditoria_*`
>   (untracked, motor core, pré-existentes — sem relação com o painel).
> O texto original é preservado abaixo como registro do diagnóstico.

> Verificação do Arquiteto (Fable): navegador real (Chrome) sobre instância isolada
> (porta 8390, log sintético com 3 runs + gate pendente; `motor/log.jsonl` e `motor.db`
> intocados) + auditoria estática de todos os `onClick`/fetch por subagente Explore
> (confirmada por amostragem). Estado vazio verificado na instância real (8378).
>
> Classificação: **REAL** (chama API/navega) · **LOCAL-ok** (estado local legítimo) ·
> **ENGANOSO** (finge acionar o motor) · **MORTO** (sem handler) · **FABRICADO** (dado inventado no client).

## Veredito em uma linha

**A espinha dorsal está correta** — todas as chamadas passam por `api.js` e batem 1:1 com os
endpoints reais do `painel.py`; Runs, detalhe de run, Caixa do Fundador (POST do gate → nota
`PENDENTE — <portão>.md` + tabela `caixa`), Logs, Datahouse*, Curador*, Mapa geral* e os KPIs
de custo são fiação genuína. **Mas uma camada grossa de teatro foi construída por cima**:
botões primários mortos, formulários que fingem gravar credenciais, gráficos senoidais
apresentados como série real e um Grafo 3D quase inteiramente mock "AO VIVO".
(*com os bugs pontuais abaixo.)

## Bugs de fiação reais (corrigir primeiro)

| # | Onde | Defeito |
|---|---|---|
| 1 | `Datahouse.jsx:12` | Filtra `artefato.gravado`/`artefato.atualizado`, mas o evento real do schema é **`artefato.atualizou`** (`eventos_schema.py:16`) → a tela mostra 0 artefatos para sempre. |
| 2 | `MapaGeral.jsx:50` e `Curador.jsx:39` | `Object.entries()` sobre o **array** de `/dados/agentes` → nome do agente vira índice ("0","1","2"); painel "Agentes" ilegível. |
| 3 | `MapaGeral.jsx` / `Curador.jsx` | Leem `info.erros`, mas o campo do backend é **`falhas`** → erros sempre 0. |
| 4 | `Topbar.jsx:29` | Botão primário **"+ Nova missão" está MORTO** (sem onClick; a página `/nova-missao` existe). Sino 🔔 (linha 32) e pill "Projeto: Todos ▾" (22) também mortos. |
| 5 | `Dashboard.jsx:360` | "Grafo 3D →" navega para `/grafo` (2D). `CaixaFundador.jsx:485` "Abrir Mapa geral" também vai para `/grafo` em vez de `/mapa`. |
| 6 | `Sidebar.jsx` | `/runners` tem página mas ficou fora do menu (órfã). Workflows/Datahouse renderizam indentados como se fossem sub-itens de "Grafo 3D". |
| 7 | `Board.jsx:53,61` | "empurrar p/ produção →" (`onDispatch` nunca definido) e "arquivar" são MORTOS; run **abortada** cai na coluna "Planejamento" com botão de produção. |
| 8 | `MapaGeral.jsx:40` | Contagem "eventos" por projeto filtra `ev.missao\|\|ev.run` — só o 1º evento da run carrega `missao`, então mostra 2 quando são 22. |
| 9 | `Logs.jsx` | `t` relativo (0.013s) formatado como hora de relógio → todas as linhas "21:00:00". |

## Teatro (enganoso/fabricado — decidir: ligar de verdade ou marcar como mock)

- **NovaMissao (`handleConfirm`, linha 52)** — "Confirmar disparo →" gera `RUN-2026-07-02-<aleatório>` e afirma "O motor emitiu spec.recebida" **sem chamar nada** (não existe endpoint de despacho no painel.py). É o pior caso: simula sucesso de uma ação de produção.
- **Conexoes (linhas 15-17, 81-96)** — "Registrar Conexão →" só muda state; o texto "guardadas em ~/.claude/secrets/" é **falso** (nada é persistido). Convida o usuário a colar API key numa UI que mente sobre armazenamento.
- **Grafo3D (`rawGraphData`, linhas 72-95)** — grafo "AO VIVO" quase todo hardcoded (Logisti-Kit, clientes.db, "86% 1ª aprovação"…); `fetchDados` é buscado e **ignorado**; só contagem de runs e custo total são reais.
- **Home** — chat do Orquestrador é um `<span>` decorativo (não é input); KPI "Mês" = `custo*12.5+18.2` e "Projeção" = `custo*25` (por isso projeção < mês); roster de agentes com personas fictícias.
- **Custos** — filtros "hoje/7d" são fatias fabricadas (25%/60% do dataset, comentário no código admite); gráfico "Tendência" é senóide determinística; "anomalias" é heurística client-side.
- **Dashboard** — título fixo "csv→json · rota forja"; "Saúde dos provedores" hardcoded; fallbacks inventados (74%, 58/82/94%, 3.2s, 83%); gráfico "Custo 14 dias" renderiza vazio e o de tiers vaza do card (defeito visual).
- **Agentes** — galeria de personas (Órion, Vesta…) com métricas hardcoded; só `chamadas`/`falhas` vêm da API; chat "Falar →/Enviar" só ecoa localmente; link HF ↗ sem href.
- **Grafo2D** — núcleo REAL (nós/arestas/timeline/drawer por nó vêm de `/dados`; seleção de nó funciona), mas: pills "Edição"/"filtro: workflow"/chat do nó "Enfileirar/Direcionar/Perguntar" + input de prompt são MORTOS; "Replay" só congela o poll; metadados "kimi-k2.6", custos por nó com tabela de preço própria e "plano.md +64 −0" são fabricados; mistura nós de todas as runs sob o título de uma run só.
- **Skills / Runners / CatalogoWorkflows (fallback)** — catálogos hardcoded vestidos com contagens reais.
- **Configuracoes** — Tema/modo REAIS (`applyTheme`); Densidade, Animações e Limite de streaming gravam chaves que **nenhum código lê** (0 consumidores).

## Tema

- `index.css` é 100% `var(--token)`; claro (stark) e escuro (paperclip) trocam corretamente em Home, Grafo 2D, tabelas etc. (verificado no navegador). Persistência via localStorage ok.
- **Quebra: Grafo3D.jsx** — dezenas de hexes/`0x…`/rgba hardcoded (`#060708`, `#E8E6E1`, luzes three.js) → canvas permanentemente escuro no tema claro (verificado visualmente). `Agentes.jsx:11` tem 1 hex (`#0B0C0E`).

## O que está saudável (sem ressalva relevante)

- Contrato de dados: todos os fetches ↔ endpoints reais; sem 404; sem erro de console em nenhuma tela testada.
- **Runs & Histórico + detalhe** — 100% fiel à API (estados, custos, contagens, gates, stream de eventos).
- **Caixa do Fundador** — POST `/dados/gates/<portão>` 200 verificado no navegador; gravou na tabela `caixa` e edita a nota `PENDENTE — <portão>.md` que o motor (`--caixa`) polla. Aprovação em lote usa o mesmo caminho. Ressalvas: painel procura a nota só em 4 pastas fixas (se `--caixa` apontar pro vault, não acha); sem feedback visível pós-decisão e o card segue "pendente" até o motor emitir `decisao.fundador`.
- **Logs** (salvo timestamp), **Datahouse** (salvo o nome do evento), **Workflows** (catálogo real de `exemplos/registro`), **Mapa geral** (salvo bugs 2/3/8), **Curador** (estrutura real).
- Estado vazio (8378, log vazio): honesto — "Nenhuma missão ainda", US$ 0.00, sem erro.

## Onde isto pode dar errado

- A auditoria dinâmica usou **log sintético** (3 runs, eventos canônicos do schema); um log real do motor pode ter campos extras/formas que mudem agrupamento por run (`agrupar_eventos_por_run` divide por `t` decrescente — logs concorrentes intercalados quebrariam a divisão).
- Cliques verificados por amostragem; a classificação exaustiva REAL/MORTO vem de leitura estática (subagente + minhas confirmações pontuais). Um handler adicionado por efeito indireto poderia escapar.
- Não testei o painel com o **motor vivo** rodando (gate fechando o ciclo via `--caixa`); a fiação foi verificada em cada ponta separadamente.
