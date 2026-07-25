# Handoff — Interface da Meta-fábrica

## Visão geral
Painel de controle de uma "meta-fábrica" de agentes de IA: o operador acompanha, intercepta e
aprova runs de orquestração (planner → subagentes paralelos → portões adversariais → gate humano →
síntese). O conjunto cobre ~24 telas: home, caixa do fundador (fila de decisão), grafo do pipeline
(2D/3D/edição), mapa geral, datahouse, agentes, skills, runs/replay, logs, custos, dashboard,
configurações e o laboratório de temas.

## Sobre os arquivos deste pacote
Os `.dc.html` deste bundle são **referências de design em HTML** — protótipos de alta fidelidade
que mostram a aparência e o comportamento pretendidos. **Não são código de produção para copiar
direto.** A tarefa é **recriar estas telas no ambiente do codebase de destino** (React/Vue/etc.),
usando os padrões e a biblioteca de componentes que já existirem lá — ou, se ainda não houver
ambiente, escolher o framework mais adequado e implementar a partir destas referências.

Cada arquivo é um "Design Component" (DC): abre direto no navegador. O runtime é `support.js`
(não recriar — é só o motor de preview). O que importa recriar é a **UI, o sistema de tokens e o
comportamento** descritos abaixo.

## Fidelidade
**Alta fidelidade (hifi).** Cores, tipografia, espaçamento, estados e interações são finais.
Recrie pixel-perfect usando as bibliotecas do codebase de destino. As telas em `Canvas.dc.html`
são a exceção: são os wireframes lo-fi da fase de exploração (referência de fluxo, não de estilo).

---

## ⚠ CAPÍTULO CENTRAL — SISTEMA DE TEMAS (leia antes de tudo)

Esta é a principal preocupação do dono. **Nada de cor hardcoded. Toda cor, em toda tela, sai de
uma única camada de tokens (CSS custom properties) que precisa ser trocável globalmente.**

### Como funciona hoje
1. **Camada de tokens** — cada tela declara o mesmo bloco de variáveis num wrapper `.mf-root`.
   Existem **dois temas base por CSS var**, no mesmo bloco:
   - **escuro (default, "paperclip")** → `.mf-root { --bg:#0B0C0E; … }`
   - **claro ("stark")** → `.mf-root[data-theme="stark"] { --bg:#E4E9F2; … }`
   Um toggle `◐` no topbar comuta `data-theme`. **Todo componente lê `var(--token)`** — nunca um
   hex literal.

2. **Registro global de temas** — `mf-themes.js` é carregado no `<head>` de TODAS as telas. Ele lê
   o tema ativo de `localStorage['mf-theme-active']` e injeta um `<style id="mf-theme-active-style">`
   que **sobrescreve** o bloco `.mf-root` / `[data-theme=stark]`. Temas custom ficam em
   `localStorage['mf-themes-custom']`. Como escuta o evento `storage`, **trocar o tema numa aba
   troca em todas ao vivo**. Builtins: `metafabrica`, `gemini`, `framer` (cada um com var-set
   escuro + claro). API pública: `window.MFThemes`.

3. **É isto que garante o "tudo em variáveis trocáveis facilmente"** que o dono pediu. No codebase
   real, isto vira: **um único theme provider / arquivo de tokens** (ex.: CSS vars em `:root` +
   `[data-theme]`, ou ThemeProvider do styled-system/Tailwind config). Um componente novo SÓ pode
   consumir tokens; trocar o objeto de tema deve repintar o app inteiro sem tocar em componente.

### ⚠ Não confundir: "tweaks" do CuradorAnalise ≠ tema do sistema
`CuradorAnalise.dc.html` tem um **laboratório de estilo local** (props/tweaks: `fonte`, `estilo`,
`contraste`, `skinEscura`, `acento`, `tags`) que muda SÓ aquela tela e **não persiste / não
propaga** — é banco de provas de direção visual, não o tema do sistema. Se ao abrir outra tela
você vê o tema base e não o "tema do curador", **isso é o comportamento correto**: aqueles tweaks
nunca foram feitos pra sair dali. O tema real e global é o do item 1–2 acima. Ao portar, **NÃO
transforme esses tweaks locais em configuração global** — eles são ferramenta de design, podem
ficar de fora do produto ou virar um "playground" isolado.

### Tokens do tema base (`metafabrica`) — fonte da verdade
Nomes de var sem o prefixo `--` por brevidade.

**Escuro (default):**
`bg #0B0C0E` · `surface #121417` · `surface2 #17191D` · `border #26292E` · `focus #3E434A` ·
`text #E8E6E1` · `text2 #8A8F98` · `text3 #5A5F66` · `accent #E8A33D` ·
`red #E5484D` · `amber #E8A33D` · `green #30A46C` · `blue #3E63DD` ·
`inv-bg #E8E6E1` · `inv-text #0B0C0E` · `grap1 #2A2D33` · `grap2 #3A3E46` · `rim #55596200`

**Claro (`data-theme="stark"`, compartilhado por todos os builtins — "azul profundidade"):**
`bg #E4E9F2` · `surface #FAFBFD` · `surface2 #EDF0F6` · `border #D2DAE7` · `focus #9AA8BF` ·
`text #26324B` · `text2 #4D5B76` · `text3 #7E8AA1` · `accent #54718D` ·
`red #B0413E` · `amber #9A6A1A` · `green #3B7D5D` · `blue #3F62A8` ·
`inv-bg #26324B` · `inv-text #FAFBFD` · `grap1 #C9D1DE` · `grap2 #AEB9CB` · `rim #8F9DB5` ·
`card-shadow 0 1px 2px rgba(38,50,75,.06),0 4px 14px rgba(38,50,75,.07)`

Os outros builtins (`gemini`, `framer`) e os defaults exatos estão em `mf-themes.js` (array
`BUILTINS`) — use-o como especificação literal da estrutura de temas.

**Semântica dos tokens:** `bg/surface/surface2` = fundo → cartão → cartão elevado. `border`
= hairline. `text/text2/text3` = principal → secundário → terciário. `accent` = cor de marca/ação.
`red/amber/green/blue` = status. `inv-bg/inv-text` = botão primário (inverte fundo/texto).
`grap1/grap2/rim` = grafite dos retratos de agente.

### Regra de ouro para o dev
> Qualquer componente novo deve nascer consumindo os tokens acima e ser testado nos **dois temas**
> (escuro e claro) + pelo menos um builtin alternativo (`gemini`/`framer`). Se aparecer um hex
> literal fora do arquivo de tokens, é bug.

---

## Sistema visual (kit compartilhado — repetido inline em cada tela)
- **Tipografia:** Space Grotesk (títulos, `.title`), IBM Plex Mono (dados/labels/IDs/custo —
  `.mono`, `.eyebrow`, `.num`), Inter (corpo). Base 14px.
- **Formas de status (4, não só cor — § brief):** `.sh.blue` = círculo executando ·
  `.sh.green` = círculo concluído · `.sh.amber` = triângulo aguardando · `.sh.red` = losango/erro ·
  `.sh.idle` = cinza. Recriar como componente `<StatusShape kind size>`.
- **Chrome "grau-defesa":** `.eyebrow` = micro-label mono caixa-alta com tracking largo; numerais
  como leitura de instrumento; hairlines `1px var(--border)`; cantos de registro `.bk` (L-shapes)
  nos modais/overlays.
- **Layout padrão:** `.mf-top` (topbar 52px: logo · seletor de Projeto · toggle tema `◐` ·
  "+ Nova missão" · sino com badge) + `.mf-body` = `.mf-side` (sidebar 238px em 4 zonas:
  Fixas / Projeto / Biblioteca / Sistema) + área principal. **A sidebar é praticamente idêntica
  entre telas** — no codebase é UM componente de layout compartilhado; muda só o item ativo (`.ni.on`).
- **Componentes reutilizáveis** (candidatos a virar componentes reais): topbar, sidebar,
  StatusShape, card (`.card`), pill/chip (`.pill`), nó-cartão do grafo, drawer do nó, KPI, tabela
  ordenável, botão (`.btn` primário usa `--inv-bg/--inv-text`).
- **Grids:** sempre `min-width:0` nas células (senão overflow).

## Grafos (React Flow)
`Grafo2D.dc.html` e `GrafoEdicao.dc.html` usam **React Flow 11**. Wrappers: `GrafoFlow.jsx`,
`GrafoEditFlow.jsx`. Detalhe crítico de implementação já resolvido: **as arestas são desenhadas
numa camada SVG própria** (`EdgeLayer`, lendo `transform` + `nodeInternals` do store), não pelas
arestas nativas do RF — o passe de medição de handles não roda de forma confiável no ambiente de
preview. No codebase real (RF instalado via npm) isso pode não ser necessário; avaliar. Nós são
cartões retangulares verticais (forma de status no topo → status mono → nome → agente/modelo →
badge → custo). Grafo3D é ilustrativo (P2).

## Comportamento & estado
- **Liveness = sinal real:** nada anima sem um evento do motor por trás. Em `Grafo2D`/`Runs`, o
  estado de cada nó vem de `deriveState(idx)` = **fold puro** sobre a lista de eventos → permite
  scrubbing/replay recalculando qualquer índice sem estado incremental. Replicar essa arquitetura
  (reducer puro sobre event log) no backend/frontend real.
- **Gate humano** = o único ponto que PARA a run (herói da tela). O replay/step pausa
  automaticamente quando o evento revelado é `escalado`.
- **Interceptação on-demand, 4 níveis:** observar / sugerir / parar / assumir. Só "parar" e
  "assumir" bloqueiam a run.
- **Custo** = cidadão de 1ª classe, sempre visível no HUD, nunca escondido.
- **Modo maquete vs. ao-vivo** explícito: partes sem dado real do motor se distinguem
  visualmente e "acendem" quando o evento real chega.
- **Segurança:** nunca exibir chave de API — só o fato "tem credencial: sim/não".

## Dados
Eventos e catálogo reais vêm do motor em `Orquestrador/motor/` (log em
`exemplos/log-amostra.jsonl`, `modelos-*.json`). Já estão transcritos dentro do JS de cada DC
(funções `events()`, `graph()`, `deriveState()`). Use-os como contrato de dados / fixtures.

## Índice de telas
- **Home** — 6 blocos (custos, fila condicional, mapa vivo, projetos, orquestrador, agentes).
- **CaixaFundador** — fila única de decisão + pendência aberta (contexto × artefato; opções
  destravam o run). Porta de decisão única do sistema.
- **NovaMissao** — modal: descrição, rota, insumos + upload, preset, resumo "o que vai acontecer"
  ao vivo com custo estimado; estado pós-disparo.
- **Grafo2D / Grafo3D / GrafoEdicao** — pipeline fan-out→síntese; nó-cartão (7 estados, incl.
  escalada e gate pausado), drawer do nó (janela ao vivo, alterações, chat 3 modos), timeline.
- **Dashboard** — 6 KPIs, custo 14d, aprovação 1ª tentativa por tier, saúde de provedores, digests.
- **CuradorAnalise** — comparativa papel×tier×modelo (10 col ordenáveis), motivos de reprovação
  agregados, chat do Curador → proposta pra Caixa. (Também o laboratório de tweaks de estilo.)
- **Custos** — drill-down projeto→rota→provedor→modelo→run com breadcrumb; períodos; anomalias.
- **MapaGeral** — macro "teatro de operações": clusters de projeto, camadas Atividade/Conhecimento,
  entidade-ponte, filtros, toggle 2D/3D.
- **Datahouse** — sub-abas Dashboard | Grafo (fontes db/dataset/MD, hosts, leituras/escritas).
- **Agentes** — Galeria (bustos procedurais = modelos personificados) | Escada & Rotas + página do
  agente (retrato, fazendo-agora, chat, ficha, telemetria do Curador).
- **Skills** — galeria de skills ensináveis; popup com prompt copiável + corpo da SKILL.md.
- **Runs** — Runs & Histórico + replay (HUD grau-instrumento, transporte, scrubber; fold puro).
- **Logs** — 3 colunas (Normal/Erros/Interação); Interação = atalhos → Caixa do Fundador.
- **Configuracoes / Temas** — galeria de temas + laboratório de calibração dos 2 temas ao vivo.
- **Board / CatalogoWorkflows / Inventario / Runners** — telas de apoio.
- **Canvas** — wireframes lo-fi da fase A (referência de fluxo).

## Arquivos deste pacote
Todos os `.dc.html` acima + `mf-themes.js` (registro de temas — **especificação do sistema de
temas**), `support.js` (runtime de preview, não recriar), `GrafoFlow.jsx` / `GrafoEditFlow.jsx`
(wrappers React Flow), e `BRIEF-DESIGN-interface-meta-fabrica.md` (brief completo com todos os
requisitos § por § das telas).
