# Brief de Design — Painel Meta-fábrica (v2)

**Para:** Claude Design
**De:** Caio (dono do projeto)
**Versão:** 2 — substitui integralmente a v1 e o `interface-briefing.md` de 29/06 (02/07/2026). O que mudou: navegação passa a ser **por projeto** (seletor global); a Home vira cockpit de triagem; entram **Datahouse**, grafos **2D/3D**, **agentes personificados**, **skills** e as personas **Orquestrador/Curador**; a direção visual agora é explícita (STARK Minerva + Paperclip), em **dois temas**. Do briefing de 29/06 ficam preservados: **zoom semântico** (§7.3), **motor headless / fronteira MCP** (§2) e **camadas atividade×conhecimento** (§8.8). O modelo de dados e eventos da v1 permanece (§5).

---

## 0. O produto em uma frase

Um **C2 (comando e controle)** de uma fábrica de software autônoma: um humano audita múltiplos projetos executados por agentes de IA, decide só o que o motor lhe delega, e observa a execução em grafos vivos — com a calma e a confiança de um sistema de defesa, não a ansiedade de um feed.

---

## 1. Contexto do domínio (o que o painel controla)

A Meta-fábrica é um **motor que orquestra agentes de IA para fabricar artefatos** (specs, planos, código, pesquisa). Em vez de um chat único, ela monta um **grafo de trabalho**: um *planejador* quebra a missão em subtarefas, subtarefas rodam **em paralelo** (cada uma com um *executor* = um modelo num papel), cada saída passa por um **verificador**, e **gates** decidem se o conjunto avança. Reprovou → o motor **escala** para um modelo mais capaz ou **reconcilia** (refaz na fonte do problema). Tudo **barato por design**: modelos gratuitos primeiro, sobe de tier só quando necessário. **Provider-agnóstico**: modelos entram por configuração.

Duas personas de IA têm presença na interface:

- **Orquestrador** — o maestro. Recebe missões, monta e dirige os workflows, reporta o que está acontecendo. É a **persona principal do painel**, com avatar humanoide próprio, chat e feed de atividade na Home.
- **Curador** — o analista. Lê a telemetria, perfila *qual modelo é bom em quê*, propõe melhorias de catálogo e roteamento. Também personificável. As propostas dele não moram num feed próprio: **viram pendências na Caixa do Fundador** (§8.2).

**Quem usa:** uma pessoa (Caio). Objetivo declarado: **deixar de ser operador e virar auditor** — acompanhar 2–3 fábricas em paralelo, intervir só quando um gate pede decisão humana, e usar dados para melhorar o catálogo. O painel é o cockpit dessa transição, e precisa dar conta de *muita coisa ao mesmo tempo* sem perder a sensação de controle.

---

## 2. Plataforma e restrições (decididas)

- **Web, na rede pessoal.** Abre em qualquer máquina, zero instalação. Empacotar como app desktop (ex.: Tauri) é opção de fase P2 — mesma base de código; não muda nada neste brief.
- **O motor é headless; a fronteira é MCP.** A interface **renderiza o stream de eventos** que o motor emite e devolve intervenções (decisões, chats, disparos) pela mesma fronteira — ela não calcula nem decide nada do processo. Consequência de design: toda tela deve ser desenhável a partir dos eventos do §5.2 + estado consultável; se uma tela precisa de dado que o motor não emite, isso é requisito ao motor, não gambiarra na UI. (Clientes externos, como o Flint, podem consumir o mesmo stream — ver §12.)
- **Usuário único, sem autenticação pesada.** Nada de login/signup, billing, planos, convites, onboarding de SaaS.
- **Tempo real importa.** O motor emite fluxo de eventos JSONL (§5.2); desenhe para atualização contínua com indicador explícito de AO VIVO / ENCERRADO / REPLAY.
- **Desktop-first, densidade alta.** Ferramenta de poder para usuário técnico: layouts densos e escaneáveis, tabelas e timelines, não interface "arejada" de marketing.

---

## 3. Direção visual

Referências: **STARK Minerva** (stark-defence.com/en/systems/stark-c2-minerva) e **Paperclip** (github.com/paperclipai/paperclip — "control plane" open-source para gerenciar agentes de IA).

O que extrair da Minerva (conceito, não cópia literal):

- **Sensação-alvo: tudo sob controle.** Calma, precisão, confiança consolidada. Um C2 militar moderno, não um dashboard SaaS colorido. A UI acelera o loop observar→orientar→decidir→agir.
- **Human-in-the-loop como valor central da marca:** o operador decide; o sistema prepara a decisão.
- **Linguagem visual:** títulos curtos em caixa alta, labels de seção pequenos e técnicos, numeração de blocos (01/02/03), setas e marcações de precisão, imagens escuras.

### 3.1 Design tokens (ponto de partida concreto — Caio pode trocar valores, não a lógica)

**Um design system, dois temas.** Os tokens são semânticos e todo componente é desenhado uma vez, funcionando nos dois:

- **Tema claro — "STARK":** o ar do site da Stark. Off-white de papel, tipografia quase-preta em caps, hairlines, muito rigor. Clima: sala de briefing.
- **Tema escuro — "PAPERCLIP":** o ar de dev tool do Paperclip. Grafite quase-preto, texto off-white, telemetria brilhando. Clima: sala de operações à noite.

| Token | Claro (STARK) | Escuro (PAPERCLIP) | Uso |
|---|---|---|---|
| `bg/base` | `#F4F3F0` | `#0B0C0E` | Fundo geral (sempre com temperatura quente) |
| `bg/surface` | `#FFFFFF` | `#121417` | Cards, painéis, sidebar |
| `bg/surface-2` | `#EDEBE6` | `#17191D` | Elevação: drawers, popups, hover de card |
| `border/default` | `#D8D6D0` | `#26292E` | Toda borda é **1px sólida** — elevação por borda+superfície, nunca por sombra difusa |
| `border/focus` | `#A9A69E` | `#3E434A` | Hover/foco de contêiner |
| `text/primary` | `#111213` | `#E8E6E1` | Texto principal |
| `text/secondary` | `#5D6167` | `#8A8F98` | Labels, metadados |
| `text/tertiary` | `#8B8E93` | `#5A5F66` | Ids técnicos, timestamps |
| `accent` | `#B87514` | `#E8A33D` | Âmbar tático. **Regra de ouro: o acento É a cor de "precisa de você"** (§4). Marca, badge da fila e pendências usam a mesma família — atenção humana = identidade do produto. |

**Regras dos temas:**

- **Canvases de grafo (2D, 3D, Mapa geral, Datahouse) permanecem escuros nos DOIS temas.** Pulso, brilho de conexão e sinal luminoso só funcionam sobre fundo escuro. No tema claro, o canvas escuro fica emoldurado pela UI clara — exatamente como as interfaces mostradas no próprio site da Stark: moldura limpa, teatro de operações escuro.
- Troca de tema em Configurações (§8.15), com atalho no topbar. Persistida. Nenhum componente pode existir "só num tema".
- **Lógica de cor (vale nos dois):** fora do âmbar, as únicas cores da interface são as 4 de status (§4). Botões primários = alto contraste invertido (claro: texto branco sobre quase-preto; escuro: texto escuro sobre off-white), nunca coloridos. Zero cor decorativa.

**Tipografia:**

- Títulos/labels de seção: **Space Grotesk** (ou Archivo) — CAIXA ALTA, tracking +6–8%, pesos 500–600.
- Telemetria e dados: **IBM Plex Mono** (ou JetBrains Mono) — ids, eventos, latências, custos, caminhos de arquivo, timestamps, números em tabelas. *Se é dado do motor, é mono.*
- Corpo/UI: **Inter** — parágrafos, chats, descrições.
- Escala enxuta: 11 (labels mono) / 13 (corpo denso) / 14 (corpo) / 16 (subtítulo) / 20–24 (título de página) / 32+ (héroi, raro).

**Geometria e densidade:**

- Cantos **retos**: radius 0–2px em tudo (4px máximo em popups). Nada de pílulas ou cantos 12px+.
- Grid de 8px; linhas de tabela de 32px; padding de card 16px. Denso, escaneável.
- Divisores hairline (1px, `border/default`); grades finas de fundo em áreas de mapa.

**Micro-detalhes de assinatura (o "nível STARK"):**

- Ids técnicos visíveis em mono: `WF-042`, `RUN-2026-07-02-013`, `NODE/qa-engineer-02`.
- Labels de seção pequenos em caps com numeração: `01 — CUSTOS`, `02 — FILA DE DECISÃO`.
- Marcações de canto (crosshair/bracket) nos contêineres-herói (mapa, card do Orquestrador).
- Setas e indicadores direcionais finos (↑ escalada, → fluxo).

**Movimento:** discreto e físico — 200–400ms ease-out longo, sem bounce/spring exagerado. Pulso de status em ciclo ~2s. Animação comunica estado (pulso = atividade), nunca enfeita. Toggle global "animações on/off" (§8.15).

**Anti-padrões (proibido — é isso que mataria a estética):** gradientes coloridos, glassmorphism, sombras difusas/coloridas, cantos muito arredondados, emojis na UI, ilustrações "friendly" de SaaS, confete, cores decorativas em gráficos (usar acento + neutros + as 4 de status).
- **Nota sobre HyperFrames** (github.com/heygen-com/hyperframes): é um framework de render **HTML→MP4 offline e determinístico** — não serve para animação de UI ao vivo. Uso correto aqui: **exportar o replay de um run como vídeo** (P2, ver §8.12). Para UI ao vivo: CSS/WAAPI/GSAP; para personagens: Rive/Lottie.

---

## 4. Sistema de status (token global)

A mesma semântica em **todo** o painel — card de projeto, nó de grafo, item de log, agente, provedor:

| Cor | Escuro (PAPERCLIP) | Claro (STARK) | Forma/ícone (nunca só cor) | Significado |
|---|---|---|---|---|
| **Vermelho** | `#E5484D` | `#C62A30` | octógono / ! | Erro, reprovado, esgotado — algo quebrou |
| **Âmbar** | `#E8A33D` (= acento) | `#B87514` (= acento) | triângulo / mão | **Aguardando VOCÊ** — decisão humana pendente |
| **Verde** | `#30A46C` | `#1E7F50` | círculo / check | Concluído/aprovado e parado |
| **Azul** | `#3E63DD` | `#2F4FC4` | círculo pulsante | Executando, tudo nos conformes |

Nos canvases de grafo (sempre escuros, §3.1) valem os hex do tema escuro, independente do tema ativo.

Regras:

- Cor sempre acompanhada de forma (acessibilidade + leitura periférica).
- Estados compostos de execução = **azul + badge próprio**: ↑ escalando, ⟳ em reconciliação, ⚖ em verificação.
- Junto da bolinha, uma **palavra de atividade**: "planejando", "codificando", "pesquisando", "verificando", "sintetizando", "aguardando".

---

## 5. Vocabulário do domínio (a verdade dos dados — usar estes termos na UI)

### 5.1 Conceitos centrais

| Termo | O que é | Como aparece na UI |
|---|---|---|
| **Projeto** | O contêiner de tudo: workflows, datahouse, runs, custos. | Eixo primário de navegação (seletor global). |
| **Missão** | O pedido de alto nível ("spec de pipeline CSV→JSON"). | Título de um run. |
| **WorkflowSpec** | Especificação tipada da missão: subtarefas, rubricas, gates, restrições. | "Receita" do run; inspecionável. |
| **Rota** | Tipo de fluxo (`forja`/software, `construcao`, `pesquisa`, `hardware`). | Seletor ao disparar; etiqueta no run. |
| **Nó** | Unidade de trabalho no grafo (planejador, executor, verificador, gate, síntese). | Nó-cartão no grafo 2D; ícone no 3D. |
| **Papel** | Função do nó (`planner`, `pesquisador`, `redator`, `arquiteto`, `qa_engineer`, `transformador`, `evaluator`, `synthesizer`, `verifier`…). | Rótulo do nó; eixo de análise. |
| **Executor** | Instância concreta que roda um papel (ex.: `pesquisa-alfa`). | Nome do nó de trabalho. |
| **Tier** | Dificuldade exigida: `simples`, `media`, `complexa` (e `sem-tier` legado). | Badge no nó; eixo de análise. |
| **Modelo / Provedor** | O modelo concreto da chamada (llama via NVIDIA, Kimi, Codex, Claude…) e seu provedor. | Dado de primeira classe por chamada (ver §5.3). |
| **Agente** | Um modelo personificado no painel: retrato, chat, ficha, telemetria. | Galeria + página própria (§8.9). |
| **Gate / Portão** | Controle de qualidade que decide avançar/reprovar. **Automático** ou **humano**. | Nó especial + pendência na Caixa do Fundador. |
| **Caixa do Fundador** | Fila única de decisões humanas pendentes. | Aba fixa com badge (§8.2). |
| **Escalada** | Subir tier/modelo após reprovação (llama → Kimi → Codex…). | Badge ↑ no nó; evento na timeline. |
| **Reconciliação** | Reabrir os nós-raiz do problema (closure estreito), refazer em ordem de dependência, re-sintetizar. | Badge ⟳ + sub-grafo destacado na timeline. |
| **Datahouse** | O conjunto de fontes de dados do projeto: databases (Google, locais…), datasets (HF), notas MD. | Aba própria com dashboard + grafo (§8.7). |
| **Telemetria** | Event-sourcing JSONL, fonte auditável da verdade. | Alimenta tudo que é "ao vivo" e o Curador. |
| **Curador** | Módulo/persona que perfila aptidão de modelos. | Página de análise (§8.11) + propostas na fila. |
| **Orquestrador** | Persona-maestro da execução. | Card central da Home (§8.1) + chat. |
| **Skill** | Instrução reutilizável ensinável a agentes. | Galeria com prompt copiável (§8.10). |
| **Digest** | Resumo final legível de um run. | Cartão de fechamento; lista em Runs (§8.12). |

### 5.2 Eventos reais emitidos (o vocabulário do "ao vivo")

Cada evento tem carimbo relativo `t` (segundos) e campo `evento`. A timeline e os grafos devem saber representar cada um:

- `spec.recebida` / `spec.criada` — missão entrou; traz `missao` e nº de `subagentes`.
- `paralelo.iniciado` — abriu fan-out; traz lista de `subagentes`.
- `modelo.pin` / `modelo.roteado_tier` — papel fixado/roteado para um `tier`.
- `executor.chamado` — executor começou; traz `executor`, `papel`, `tier`, `tentativa`.
- `executor.respondeu` — entregou; traz `executor`, `tentativa`.
- `executor.erro` — falhou com `motivo` e `tentativa`.
- `modelo.falha` — chamada de modelo falhou (`motivo`, `papel`, `tentativa`).
- `portao.aprovado` / `portao.reprovado` — gate decidiu; traz `portao`, `ciclo` e, se reprovou, `motivo` (**texto longo e técnico — o conteúdo mais valioso**; truncar com expandir, ou painel lateral).
- `escalado` — subiu de tier/modelo.
- `gate.auto` — gate automático decidiu; traz `portao` e `decisao`.
- `decisao.fundador` — o humano decidiu um gate.
- `paralelo.concluido` — fan-out terminou; quantos `commitados`.
- `provedor.esgotado` / `provedor.auto_esgotado` — provedor estourou cota (`provedor`, `motivo`).
- `modelo.fallback` / `modelo.reroteado_esgotado` — trocou de modelo por esgotamento (`de`/`para`).
- `ferramenta.indisponivel` — ferramenta exigida ausente.
- `tarefa.concluida` — missão fechada.

### 5.3 Lacuna conhecida a acomodar

A telemetria registra `papel` e `tier`, mas nem sempre o **modelo/provedor concreto** por chamada. Isso será adicionado. **Desenhe assumindo `modelo` + `provedor` por chamada**, com fallback gracioso "modelo: desconhecido" para telemetria antiga. Dado de primeira classe, não escondido.

---

## 6. Vocabulário visual de entidades (a "ponte" entre vistas)

Cada tipo de entidade tem **um ícone canônico** com versão 2D (flat) e 3D (mesma silhueta, mesmo reconhecimento):

agente/executor · planejador · verificador · gate · artefato · database · nota MD · dataset · workflow · projeto · skill · ferramenta/MCP.

Regra central: **o mesmo ícone em qualquer vista**. O database que aparece conectado num grafo de workflow é o mesmo ícone, com o mesmo nome, do grafo do Datahouse e do Mapa geral. Entidades compartilhadas são **âncoras de navegação**: clicar nelas em qualquer mapa abre a mesma ficha lateral. É isso que faz os mapas parecerem um sistema só, e não três telas separadas.

---

## 7. Navegação

### 7.1 Topbar (persistente)

`[Logo Meta-fábrica] [Projeto: Todos ▾]` … `[+ Nova missão] [🔔 pendências (badge)]`

- O **seletor de projeto** re-escopa tudo que está na zona PROJETO da sidebar, os custos e as visões. Opção **"Todos"** habilita as visões agregadas (Home e Mapa geral mostram tudo).
- **+ Nova missão** é global (§8.3). O sino abre a Caixa do Fundador.

### 7.2 Sidebar (4 zonas; grupos colapsáveis estilo Notion)

```
FIXAS (não encolhem — o coração do painel)
  Home
  Caixa do Fundador          ← fila única de decisão (badge com nº)
  Mapa geral                 ← tudo conectado, tempo real

PROJETO: {selecionado}
  Dashboard
  Grafos ▾                   ← grupo colapsável
    Workflows                (sub-abas: Dashboard | Grafo 2D | Grafo 3D)
    Datahouse                (sub-abas: Dashboard | Grafo)
  Runs & Histórico           ← digests + replay

BIBLIOTECA ▾                 ← colapsável
  Agentes                    (galeria + página por agente + aba Escada & Rotas)
  Skills                     (galeria, filtros, popup de prompt)
  Curador                    (análise/telemetria histórica + chat do Curador)
  Logs                       (página completa)
  Custos                     (drill-down)

SISTEMA ▾                    ← colapsável
  Conexões                   (provedores, MCPs, databases — nunca exibe chave)
  Configurações
```

Comportamento Notion: clicar no título do grupo encolhe/expande; estado persistido. As três abas FIXAS nunca encolhem.

### 7.3 Zoom semântico (a interação central dos mapas)

"Entrar nas salas" = trocar de **nível de detalhe**, não dar zoom de pixel. Três níveis, sempre os mesmos:

- **MACRO** — a fábrica inteira: Mapa geral (§8.8), projetos como regiões, conexões pulsando.
- **MESO** — o pipeline de um projeto/workflow: grafo 2D/3D (§8.5/8.6), papéis, dependências, handoffs, gates.
- **MICRO** — um agente trabalhando: o drawer do nó (§8.5) — ação atual, chamadas de ferramenta, artefato sendo editado ao vivo, chat de direcionamento.

Regras: descer de nível preserva contexto (breadcrumb macro→meso→micro); subir de volta mantém onde você estava; a transição é contínua (o nó cresce e vira a sala), não um redirect seco. É a metáfora do cérebro→sala→funcionário: assistir em macro, entrar, dar palpite, sair e seguir vendo em macro.

---

## 8. Telas

### 8.1 Home (P0) — triagem em 10 segundos

Pergunta que a tela responde, nesta ordem: **"algo precisa de mim? algo quebrou? quanto estou gastando? o que está rodando?"**

Blocos, de cima para baixo:

1. **Linha de custos** — cards compactos lado a lado: custo de hoje, do mês, por provedor, projeção; deltas vs período anterior. Cada card clica para Custos (§8.13) já filtrado.
2. **Fila de decisão (condicional)** — só existe quando há pendências; lista os primeiros N itens da Caixa do Fundador, **decidíveis inline, um a um**; "ver todas" → §8.2. Vazia = o bloco some (ausência de pendência não vira ruído).
3. **Mapa geral vivo** — o hero visual: a mesma engine do Mapa geral (§8.8) em escopo "Todos", pulsando com a atividade real. Hover destaca sub-grafos; clique expande para a página.
4. **Projetos** — grid de cards: nome, **grafo decorativo de fundo** (representação estética, não funcional), métricas em hover (runs ativos, custo do dia, pendências), e **linha inferior de status**: último acontecimento (mesma string do último evento/digest — uma fonte de verdade) + bolinha do §4. Clique = seletor muda para o projeto e abre seu Dashboard.
5. **Orquestrador** — o card grande, a presença da casa: **chat à esquerda** (conversar, pedir status, **disparar missão por linguagem natural** — ver §8.3), **feed de processos em tempo real ao centro** (últimas ações do motor; quando ele propõe algo, o item traz `Aprovar | Ver mais` — Ver mais abre o chat com a proposta anexada para discutir e alterar juntos), **avatar humanoide à direita**, com sensação de presença na página (slot desde P0; ilustração estática em P0/P1, 3D animado em P2).
6. **Agentes** — fileira compacta de avatares (busto circular pequeno + anel na cor de status); hover = nome + o que está fazendo agora; clique = página do agente; "ver todos" → galeria (§8.9).

Fora da Home (decisão de arquitetura): carrossel de skills → §8.10; logs em 3 colunas → §8.14; previews de grafos de workflow/datahouse → redundantes com o bloco 3.

### 8.2 Caixa do Fundador (P0) — fila única de decisão

Tudo que espera um humano, num lugar só: gates humanos de runs, propostas do Curador, propostas do Orquestrador, pedidos de interação de nós.

- **Item da fila:** origem (ícone da entidade + projeto), missão/nó, a **pergunta**, as **opções** (prosseguir / revisar / abortar / inserir valor), e o **contexto que embasa** lado a lado: o plano proposto, o `motivo` longo de reprovação, o diff, o artefato em revisão.
- **Decisão é individual por pendência.** Nunca approve em massa por padrão; ações em lote existem apenas atrás de seleção explícita de itens.
- Decidir **destrava o run na hora** e registra `decisao.fundador` — histórico de decisões auditável por run.
- Badge na sidebar/topbar com contagem em tempo real.
- **Fronteira mantida da v1:** gates de **dinheiro/identidade** não moram aqui (pertencem ao "Jarvis", outro projeto). Aqui só o gate cru: portão + pergunta + opções + contexto.

### 8.3 Nova missão (P0)

Botão global no topbar; abre modal/página:

- Descrição da missão; **rota**; insumos (arquivo, caminho, spec); **preset de catálogo** (ex.: `free-escalada`, `codex`, `claude`); opções: `--auto` vs supervisionado, escalada on/off, reconciliação + teto de rodadas, gate de cobertura.
- **Resumo "o que vai acontecer"** antes de confirmar (rota + catálogo + opções) — escolhas custam tempo e dinheiro.
- Caminho alternativo: **pedir ao Orquestrador por chat** (Home). Ele preenche o mesmo formulário e devolve o mesmo resumo para confirmação — uma só mecânica de disparo, duas portas.

### 8.4 Dashboard do projeto (P1)

KPIs do projeto selecionado: runs ativos/concluídos, custo (dia/mês) com tendência, aprovação de 1ª tentativa, latência mediana/p90, escaladas e convergência, pendências abertas; últimos digests; saúde dos provedores usados pelo projeto; atalhos para os grafos.

### 8.5 Workflows — Grafo 2D (P0; a tela de trabalho)

Canvas de **nós-cartão** (estilo Paperclip / React Flow), topologia planejador → fan-out → verificadores → gate → síntese.

**Anatomia do nó-cartão:**

- Linha de status no topo: bolinha+forma (§4) + palavra de atividade + tier + tentativa.
- Nome do executor + papel; modelo/provedor atual (§5.3).
- **Mini-janela: preview do último artefato produzido/associado** — código, markdown renderizado, tabela, objeto 3D. Atualiza **por evento** (novo artefato, arquivo salvo), não frame a frame. É a resposta ao "quero ver como ficou o que o agente fez" sem streamar tudo.
- Linha inferior: **último arquivo tocado** em tempo real (`modificando planner.md`, `editando test.py`).

**Regra de atenção (importante):** só o nó em **hover/foco** liga stream ao vivo (terminal/execução contínua); os demais ficam em preview + última linha. Doze terminais simultâneos matam o navegador e ninguém lê doze de uma vez — a sensação de "vivo" vem do pulso, da última linha mudando e dos previews trocando.

**Clique no nó → painel lateral (drawer):**

- Topo: a mesma linha de status.
- **Janela grande ao vivo** (terminal / artefato / visual 3D — o que o nó estiver produzindo).
- Bloco **Alterações**: últimos 5 arquivos tocados com ±linhas; expandir = auditoria completa (todos os arquivos, diffs completos de tudo que ele editou e está editando).
- **Chat do nó** com 3 modos, iguais ao Claude Code: **Enfileirar** (executa assim que possível), **Direcionar agora** (injeta o prompt no próximo turno), **Perguntar** (canal paralelo que não interrompe — o "btw"). Aceita anexos.

**Timeline de eventos** do run em painel inferior recolhível: todos os eventos de §5.2 em ordem, filtro por tipo, `motivo` longo truncado com expandir.

**Filtro de workflow** (ex.: só o da software house) — vale **simultaneamente para 2D e 3D**. Sem filtro = todos os workflows do projeto.

**Momentos críticos com destaque:** gate reprovado, escalada, reconciliação (mostrar o sub-grafo reaberto e a ordem de dependência do refazimento). Pendência humana = impossível de ignorar, com atalho para a Caixa do Fundador.

### 8.6 Workflows — Grafo 3D (P2)

O mesmo grafo, metáfora de rede neural, usando os **ícones 3D canônicos** (§6).

- Conexões **acendem quando trafegam**; caminhos ociosos ficam estáticos.
- **Progresso por gates, não % contínuo:** o sinal luminoso avança um trecho do caminho quando uma etapa/gate fecha. (Percentual contínuo de tarefa de LLM não é mensurável com honestidade; se um dia houver métrica real — testes passando, tokens — pluga-se aqui.)
- Hover: pulsa o nó + **apenas os caminhos ativos associados**.
- Navegação orbital livre; clicar num nó abre **o mesmo drawer do 2D** (um único componente de detalhe para as duas vistas).
- Entidades de outros domínios (ex.: um database do Datahouse) aparecem com o ícone canônico + nome — clicáveis (a ponte do §6).

### 8.7 Datahouse (P1)

- **Dashboard:** volumes, leituras/escritas por workflow, hosts (Google, datasets do Hugging Face, locais…), notas MD indexadas, últimos acessos.
- **Grafo:** nós = databases / notas MD / datasets com o ícone canônico; arestas = quem lê/escreve em quê; **piscam quando estão sendo usados**; **só aparecem entidades usadas por algum workflow** do escopo (o não-usado não polui). Escopo segue o seletor de projeto; "Todos" = tudo.

### 8.8 Mapa geral (P1)

O teatro de operações: **todos os workflows + datahouses de todos os projetos num mapa só**, com conexões sendo feitas e desfeitas em tempo real. Filtros: projeto, tipo de entidade, só-ativos. Modos 2D e 3D (mesmas engines das §8.5/8.6). É a vista referenciada no bloco 3 da Home e o nível MACRO do zoom semântico (§7.3). Com vários projetos rodando, é aqui que a fábrica "pulsa que nem louca" — e o §9 garante que isso não vire caos visual.

**Duas camadas sobreponíveis** (toggle no próprio mapa): **Atividade** (workflows executando — quem está fazendo o quê agora) e **Conhecimento** (datahouse — o que existe e quem lê/escreve). Ver uma, outra, ou as duas sobrepostas; entidades-ponte (§6) aparecem nas duas.

### 8.9 Agentes (P1; retratos gerados por IA em P2)

**Galeria:** cards com **retrato do agente** — busto humanoide único que personifica aquele modelo. Assinatura visual: o recorte do peito para cima fica dentro do card e **a cabeça ultrapassa a borda superior**, como se ele estivesse presente na página. Anel/linha de status (§4). Hover: o agente "acorda" (micro-animação idle, P2) + botão **Falar**. Fallback até os retratos existirem: **avatar procedural** (silhueta + paleta derivada do hash do nome) — nada do MVP depende de geração de imagem. **A especificação completa dos personagens para o pipeline de geração de imagens está no Apêndice C.**

**Página do agente** (minimalista, ar de calma, completa de informação):

- Retrato grande + **chat** com o agente.
- O que está fazendo agora (nós ativos em quais workflows/projetos).
- Ficha técnica: modelo, provedor, **link do Hugging Face**, **fine-tunings em andamento**.
- Telemetria do Curador: aprovação de 1ª tentativa, latência mediana/p90, taxa de erro, convergência pós-escalada.
- Posição na escada e **status de certificação**: em sombra / certificado / reprovado.

**Aba "Escada & Rotas"** (o catálogo de modelos, fundido aqui):

- A **escada** de custo/capacidade visualizada: degraus free (NVIDIA: llama/qwen/Kimi/DeepSeek) → Codex → Claude no topo/verificador.
- **Presets nomeados** (`free-escalada`, `codex`, `claude`, `construcao`, `pesquisa-sintese`): o que cada um mapeia (papel → provedor/modelo) e quando usar.
- **Roteamento** papel → tier → modelo e fallbacks por esgotamento.
- **Status operacional por provedor:** disponível / throttled (429) / esgotado / sem-chave. A UI mostra apenas "credencial configurada: sim/não" — **nunca a chave**.
- Fluxo de modelo novo: entra **em sombra** → Curador acumula evidência → promover a certificado ou reprovar (link para a evidência em §8.11).

### 8.10 Skills (P1)

- **Galeria de cards:** nome da skill + **arte de fundo representando a categoria** (backend, database, design…) + tag da categoria. Onde embutida (ex.: página de agente), aparece como carrossel com setas ← → e "ver mais".
- **Página completa:** filtro por categoria, busca, ordenação.
- **Clique no card → popup:** o prompt pronto para copiar ("use a skill X que está em `<caminho>`") + botão copiar + metadados (origem, versão, última edição).

### 8.11 Curador — Análise (P1)

A casa analítica do Curador (com o chat dele): dashboards comparáveis — tabelas ordenáveis + gráficos, não texto cru.

- Aptidão por **papel × tier × modelo**: chamadas, respostas, erros e taxa de erro; **aprovação de 1ª tentativa** (métrica-chave); reprovações; escaladas e **convergência pós-escalada**; latência mediana e p90; tentativas do planejador; reprovado→aprovado via reconciliação (rodadas, closure estreito?); 429/esgotado por provedor.
- **Motivos de reprovação agregados** por papel/tier — parágrafos longos, legíveis e filtráveis: é o que explica o teto de cada modelo.
- Visão **por run** e **agregada** ("8 fontes / 14 runs").
- **Ruídos de dado sinalizados, não escondidos:** taxa de erro >100% (mistura de tipos), entradas `sem-tier` legadas — aviso honesto.
- Propostas geradas aqui (ex.: "promover Kimi a certificado em `codigo-medio`") **entram na Caixa do Fundador**.

Cenários a facilitar: "qual modelo aprova de primeira em código-complexo?" · "onde está minha latência?" · "o free está estourando 429 demais?" · "a escalada converge ou só queima tempo?"

### 8.12 Runs & Histórico (P1)

- Lista de runs do escopo: digest, custo, duração, ciclos, escaladas, resultado (bolinha §4).
- Abrir um run = **replay do grafo com scrubber de tempo** (arrastar no `t`) — o mesmo componente do ao-vivo em modo REPLAY, inequivocamente marcado.
- P2: **exportar o replay como vídeo** (HyperFrames, §3) para compartilhar/arquivar.

### 8.13 Custos (P1)

Drill-down: projeto → rota → provedor → modelo → run; períodos; anomalias destacadas; projeção do mês. Os cards da Home clicam para cá já filtrados.

### 8.14 Logs (P1)

Página completa: **3 colunas — normal / erros / interação** + filtros (projeto, tipo de evento, período, busca). Itens de "interação" são **atalhos para a Caixa do Fundador** — não se decide aqui; porta de decisão é uma só.

### 8.15 Conexões e Configurações (P2)

- **Conexões:** provedores (status + credencial sim/não), MCPs/ferramentas, databases do Datahouse, Hugging Face.
- **Configurações:** **tema claro (STARK) / escuro (PAPERCLIP)** — com atalho no topbar, persistido; densidade; **animações on/off** (performance); limites de stream; retenção de logs.

---

## 9. Regras de tempo real (orçamento de atenção)

1. Pulso/brilho **apenas em entidades ativas**; ocioso é estático.
2. Mini-janelas atualizam **por evento** (artefato novo, arquivo salvo), não frame a frame.
3. **No máximo 1 stream contínuo** ao vivo por vez: o nó em hover/foco, ou o drawer aberto.
4. Badges (fila, erros) em tempo real; toast só para vermelho.
5. Toda vista viva exibe **AO VIVO / ENCERRADO / REPLAY**.
6. Conexões feitas/desfeitas em runtime refletem nos grafos imediatamente.

---

## 10. Estados a desenhar (todas as telas)

- **Vazio/primeiro uso** (sem runs, sem logs) — com orientação do que fazer.
- **Carregando / aguardando eventos.**
- **Ao vivo vs replay** — inequívoco.
- **Degradado:** provedor esgotado, 429, fallback de modelo, ferramenta indisponível — comunicar *o que* degradou e *o que o motor fez* ("sem o modelo X, caímos para Y").
- **Pausado esperando humano** — o estado mais acionável; impossível de ignorar.
- **Falha dura:** run abortado, crash/retomada (o motor sobrevive e retoma — a UI reflete), "N linhas de log ignoradas".
- **Dados incompletos:** modelo "desconhecido" em telemetria antiga; "n/d" sem amostra.

---

## 11. Fluxos-chave (jornadas a validar)

1. **Triagem matinal:** Home → fila de decisão → decidir 2 pendências inline → olhar custos → seguir o dia.
2. **Disparar e assistir:** + Nova missão (form ou chat com o Orquestrador) → Grafo 2D → nós acendendo → digest.
3. **Ser convocado:** badge no sino → Caixa do Fundador → contexto lado a lado → decidir → run destrava.
4. **Entender uma reprovação:** timeline `portao.reprovado` → motivo longo → reconciliação reabrindo o sub-grafo → APROVADO.
5. **Direcionar um nó ao vivo:** 2D → clique no nó → chat (enfileirar / direcionar / perguntar) → resposta no canal paralelo.
6. **Investigar custo/qualidade:** Curador → comparar modelos → Escada & Rotas → ajustar preset.
7. **Certificar um modelo novo:** adicionar → em sombra → evidência acumula → promover/reprovar (via pendência na fila).
8. **Re-assistir um run:** Runs & Histórico → replay com scrubber → (P2) exportar vídeo.
9. **Conhecer um agente:** Home (fileira) → página do agente → conversar → ver fine-tunings/HF.
10. **Reusar uma skill:** Skills → filtrar categoria → popup → copiar prompt → colar num agente.

---

## 12. Anti-escopo (o que esta interface NÃO é)

- **Não é SaaS:** sem login/signup, billing, planos, multiusuário, marketing.
- **Não decide dinheiro nem identidade:** esses gates moram no "Jarvis" (outro projeto). Aqui só o gate cru.
- **Não é IDE:** mostra artefatos e diffs para *decisão e auditoria*, não para edição livre.
- **Chats são canais de direcionamento contextuais** (Orquestrador, agente, nó) — a metáfora central continua sendo grafo + timeline + dashboards, não conversa.
- **Não inventa métricas:** só o que existe na telemetria/Curador ou está marcado como futuro (modelo-por-chamada, teste em sombra, % real de progresso).
- **Não é o Flint:** o Flint (app de notas) é projeto separado que *pode* consumir o mesmo stream MCP como cliente externo opcional — a meta-fábrica não depende dele e esta superfície não o desenha.

---

## 13. Fases

- **P0 — cockpit mínimo:** navegação completa (topbar+sidebar), Home, Grafo 2D com drawer e chat de nó, Caixa do Fundador, Nova missão. Dados mock aceitáveis; slots de avatar com fallback procedural.
- **P1 — profundidade:** Dashboard do projeto, Curador/Análise, Custos, Datahouse, Mapa geral 2D, Agentes/Skills, Runs+replay, Logs, tempo real de verdade.
- **P2 — presença:** Grafo 3D com ícones canônicos e sinais por gate, retratos IA dos agentes, avatar humanoide do Orquestrador (animado), micro-animações (Rive/Lottie), export de replay em vídeo (HyperFrames), empacote desktop (Tauri) se desejado.

---

## 14. Pedidos ao Claude Design (processo em duas etapas)

### Etapa A — Wireframes (baixa fidelidade, rápido de iterar)

Objetivo: validar **estrutura e hierarquia** antes de gastar em acabamento. Cinza + tipografia + as 4 cores de status; sem retratos, sem 3D, sem polish.

1. **Arquitetura de informação + navegação** — validar/criticar §7 (sidebar, topbar, seletor de projeto).
2. **Wireframe da Home** — os 6 blocos do §8.1, com a fila condicional aparecendo/sumindo.
3. **Wireframe do Grafo 2D** — canvas + anatomia do nó-cartão + drawer aberto.
4. **Wireframe da Caixa do Fundador** — fila + pendência aberta com contexto lado a lado.

*Gate humano: Caio aprova os wireframes antes da Etapa B.*

### Etapa B — Alta fidelidade (aplicando §3 na íntegra)

5. **Home em alta fidelidade** nos estados: saudável, com pendências, com erro, vazia — **nos dois temas** (claro STARK e escuro PAPERCLIP); as demais telas podem ser entregues num tema só, desde que usem apenas tokens semânticos do §3.1.
6. **Grafo 2D em alta fidelidade**: nó-cartão em todos os estados (§4 + §10) + drawer do nó.
7. **Caixa do Fundador em alta fidelidade.**
8. **Inventário de componentes reutilizáveis:** nó-cartão, item de timeline por tipo de evento, cartão de pendência, card de projeto, card/retrato de agente, card de skill, badges (status/tier/certificação), tabela comparativa do Curador, indicador AO VIVO/REPLAY.
9. Demais telas na ordem de P1.

**Critério de aceite da Home:** em 10 segundos, sem clicar, dá para responder — o que precisa de mim, o que quebrou, quanto custou hoje, o que está rodando.

**Critério de aceite da estética:** colocada ao lado do site da STARK, a tela parece da mesma família de produto (calma, precisão, controle) — e nada nela viola os anti-padrões do §3.1.

---

### Apêndice A — Prompt de abertura para o Claude Design (colar junto com este brief)

> Você vai desenhar o painel da Meta-fábrica seguindo o brief anexo. Regras de trabalho:
> 1. Leia o brief inteiro antes de desenhar. Os §3 (design system), §4 (status) e §6 (ícones canônicos) são lei — não invente paleta, tipografia nem cantos arredondados. Respeite os anti-padrões do §3.1.
> 2. Comece pela **Etapa A do §14** (wireframes). Não pule para alta fidelidade sem eu aprovar a estrutura.
> 3. Use dados de exemplo realistas do domínio (§5): nomes de eventos reais (`portao.reprovado`), ids técnicos (`WF-042`), papéis (`qa_engineer`), custos em reais/dólares plausíveis. Nada de "Lorem ipsum" nem "Task 1".
> 4. A sensação-alvo é a de um C2 militar moderno (STARK Minerva): calma, precisão, tudo sob controle. Se uma tela parecer dashboard SaaS colorido, está errada.
> 5. Cada tela deve ser entregue nos estados do §10 que se aplicam (vazio, ao vivo, degradado, pausado-esperando-humano).
> 6. Quando tiver dúvida entre densidade e "respiro", escolha densidade escaneável (§2).

### Apêndice B — glossário (mesma linguagem em todo o produto)

Projeto · Missão · WorkflowSpec · Rota · Nó · Papel · Executor · Tier (simples/média/complexa) · Modelo/Provedor · Agente · Gate/Portão (auto/humano) · **Caixa do Fundador** · Escalada · Reconciliação (closure estreito) · **Datahouse** · Telemetria · **Curador** · **Orquestrador** · Skill · Digest · Fan-out (paralelo) · Verificador · Fallback/Esgotamento (429) · **Mapa geral** · **Escada & Rotas** · Ponte visual (§6).

---

### Apêndice C — Spec de personagens (para o pipeline de geração de imagens)

Objetivo: qualquer gerador de imagens, chamado automaticamente pelo motor, produz um retrato novo que **pertence à mesma família visual** dos existentes — sem curadoria manual imagem a imagem.

**C.1 Direção de arte fixa (a "família")**

- **O que são:** humanoides sintéticos (andróides de design industrial refinado) — nem pessoa fotorreal, nem cartoon, nem robô de brinquedo. Pense em engenharia de precisão com presença calma.
- **Materiais:** polímero grafite fosco, metal escovado escuro, tecido técnico; juntas e painéis visíveis mas discretos.
- **Luz:** estúdio dramática, key light superior-lateral, **fundo transparente (alfa)** com **rim light sutil** contornando a silhueta — o retrato precisa ler bem sobre superfície clara (tema STARK) e escura (tema PAPERCLIP); **detalhes luminosos no acento âmbar `#E8A33D`** (olhos/visor, traços finos de circuito) — é a única cor viva do personagem.
- **Postura/expressão:** calma, competente, "sob controle". Olhar frontal ou ¾ leve. Nunca agressivo, nunca fofo.
- **Proibido:** neon multicolorido, poses de ação, fundos cenográficos, logotipos, hiper-realismo humano (evita vale da estranheza e confusão com pessoa real).

**C.2 Identidade determinística (derivada de atributos reais do agente)**

Cada personagem é função dos dados do agente — mesmo input, mesmo personagem:

| Atributo do agente | Traço visual |
|---|---|
| **Papel** (`qa_engineer`, `arquiteto`, `pesquisador`, `redator`, `planner`…) | Equipamento/vestuário característico (ex.: qa = visor de inspeção; arquiteto = sobreposição estrutural nos ombros; pesquisador = lente/ocular adicional; planner = HUD projetado) |
| **Degrau na escada** (free → topo) | Robustez do chassi: free = esguio/leve; topo (Claude/verificador) = presença mais sólida e acabamento superior |
| **Provedor/família do modelo** | Emblema pequeno e padrão de painel próprios (marcação, não logotipo) |
| **Hash do nome** | Seed fixa + variações menores (formato de cabeça, textura) — reprodutibilidade |

Guardar na ficha do agente (§8.9): `seed`, prompt usado e versão do gerador — regenerar = mesmo personagem.

**C.3 Enquadramentos (gerar 1 master, cortar o resto)**

Gerar **uma imagem master** por personagem e derivar os crops dela — nunca 3 gerações separadas (quebraria a consistência):

| Uso | Recorte | Formato |
|---|---|---|
| **Master** | meio corpo, do umbigo para cima, espaço livre acima da cabeça | PNG com alfa, ≥2048px de altura |
| Card da galeria | peito para cima; **cabeça ultrapassa a borda superior do card** | crop do master |
| Fileira da Home | busto circular | crop 256px |
| Página do agente | o master inteiro | — |

**Orquestrador** (persona principal): mesma família, porém figura de ¾ de corpo, escala maior, postura de comando sereno — é o único personagem com presença de corpo na Home. **Curador**: variação analista (ocular/lente, postura observadora).

**C.4 Template de prompt (bloco fixo + bloco variável)**

Bloco fixo (todo personagem, sempre igual — em inglês, geradores respondem melhor):

> *Refined industrial android portrait, matte graphite polymer and dark brushed metal, subtle visible panel lines, calm competent presence, front-facing slight three-quarter view, dramatic studio key light from upper left, subtle rim light outlining the silhouette, isolated on transparent background (PNG alpha, readable on both light and dark surfaces), single amber accent (#E8A33D) glow in eyes/visor and thin circuit traces, waist-up framing with clear space above head, no neon colors, no action pose, no logos, not photorealistic human, not cartoon.*

Bloco variável (preenchido pelo motor a partir do §C.2):

> *Role: {equipamento do papel}. Build: {esguio|padrão|robusto conforme degrau}. Marking: {emblema do provedor}. Seed: {hash}.*

**C.5 Fases:** P0/P1 usa o avatar procedural (§8.9). O pipeline de geração entra em P2 — mas o slot, os crops e esta spec já valem desde o primeiro wireframe, para o layout nunca depender de refazer nada.
