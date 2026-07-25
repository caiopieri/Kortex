# Plano do Painel — 20 telas sem quebrar o escopo (nem o bolso)

> Estado: `painel.py` v0.5 + `painel.html` (mapa orbital vivo lendo `log.jsonl`) + `grafo3d.html` já funcionam. O Claude Design gerou **20 telas** (.dc.html). Este plano diz **em que ordem implementar, e com qual modelo** — sem cair na armadilha de "implementar as 20" nem queimar Claude à toa.

## A decisão que salva tudo: contrato de dados + shell, ANTES das telas

Não implemente 20 HTMLs independentes. Isso é 20× o trabalho e 20 fontes de bug. Faça como o motor já pensa (núcleo que conecta tudo; rota é texto sobre o núcleo):

1. **Um contrato de API** — `painel.py` expõe projeções do `log.jsonl` + do `motor.db`: `/dados/runs`, `/dados/agentes`, `/dados/custos`, `/dados/gates`, `/dados/catalogo`, `/dados/curador`. Toda tela é uma **view fina** sobre esse contrato. O log é a fonte da verdade; a tela só lê.
2. **Um app shell** — nav + roteador + tema (o `Temas.dc.html`) + o cliente que busca o contrato. Uma vez só.
3. **Cada tela = uma rota** que consome o contrato. Trocar/adicionar tela não mexe no núcleo.

Faça o **contrato + shell com um modelo bom, uma vez**. Depois as 20 telas são preenchimento barato contra um contrato estável. Isso é o análogo do "roteiro-como-texto": a API é o núcleo, as telas são rotas nele.

## As 20 telas em 3 tiers (implementar nesta ordem)

### 🟢 Tier 1 — OPERAR a fábrica (o MVP real do painel — só isto destrava o uso)
Sem estas 4 você não usa a fábrica com conforto; com elas, usa. **Pare aqui e comece a operar.**

- **Home** — entrada: missões ativas, atalho pra nova, últimos eventos.
- **Runs** — assistir uma missão acontecendo (você já tem 80% no `painel.html`: o mapa vivo).
- **CaixaFundador** — **a peça mais importante:** aprovar/reprovar gates pela tela em vez do terminal. É o que torna a operação assíncrona (você decide do celular, a fábrica segue). Sem isso você fica preso no terminal.
- **Grafo2D** — o mapa (≈ o `painel.html` atual; adaptar ao shell).

### 🟡 Tier 2 — ENTENDER e economizar (observabilidade de profundidade)
Leem projeções do log; agregam valor mas não bloqueiam operar.

- **Custos** — livro-razão por run/modelo (o curador já gera o dado).
- **CuradorAnalise** — o que o curador propõe (modelo por papel/tier).
- **Agentes** — executores do registry, capacidades, saúde.
- **CatalogoWorkflows** — roteiros disponíveis.
- **Inventario** — entidades do registry.
- **Dashboard** — visão macro agregada.

### 🔵 Tier 3 — AUTORAR e enfeitar (por último; vários são luxo)
- **NovaMissao** — o CLI já despacha; a tela é conveniência.
- **GrafoEdicao / Board** — autoria visual de roteiro (é o "grafo de workflows" — Futuro, depende do resto).
- **Skills, Runners, Datahouse, MapaGeral** — views específicas, sob demanda.
- **Grafo3D** — vistoso, custa caro em esforço, entrega o que o 2D já dá. **Último de todos.**
- **Temas** — vira parte do shell (Tier 1), não tela isolada.

**Regra:** só sobe de tier quando o de baixo está no ar e usado. Metade das 20 telas talvez nunca precise existir — e tudo bem.

## Qual modelo para quê (a resposta direta)

**O ponto que te queimou:** o `claude_design` MCP roda em endpoint da Anthropic (`/design-login`) — **implementar as 20 telas por ele consome seu Claude semanal.** Foi o que esgotou. Mas o trabalho criativo (o design) **já foi feito** — os `.dc.html` já existem. Você não precisa re-rodar o Claude Design.

Implementar = pegar o HTML/CSS estático do `.dc.html` e **ligar ao `/dados` do painel.py + log.jsonl**. Isso é frontend limitado, visual e testável (renderizou? mostra o dado do log?) — **o caso PERFEITO para modelos free**. Divisão:

| Trabalho | Modelo | Por quê |
|---|---|---|
| **Contrato de API + app shell + tema** (uma vez) | 1 modelo bom: Sonnet, GLM 5.2 topo, ou Opus se sobrar quota | decisão de arquitetura, feita certa uma vez |
| **Implementar cada tela** contra o contrato | **Operário free**: DeepSeek V4 / Kimi K2.6 / GLM 5.2 (NVIDIA free, via gateway) | frontend-de-spec é bounded e visual — modelo free faz bem |
| **Revisar o pacote** (marco) | modelo ≠ operário; **Fable/Opus finalzão** 1×/fase | pega o que o free deixou passar |

**Não** gaste Claude/Opus preenchendo tela — só no contrato/shell e na revisão de marco.

## Como proceder — passo a passo

1. **Não re-importe pelo Claude Design.** Exporte/salve os 20 `.dc.html` como estáticos no repo (`motor_painel/telas/`).
2. **Missão 1 (modelo bom, 1 vez):** definir o contrato `/dados/*` no `painel.py` + o app shell com roteador e tema. DoD: shell carrega, troca de rota, tema aplica, um endpoint real responde.
3. **Missões Tier 1 (Operário free, via gateway):** Home, Runs, CaixaFundador, Grafo2D — cada tela ligada a um endpoint real. DoD por tela: renderiza + mostra dado vivo do log + (CaixaFundador) grava a decisão que o motor lê.
4. **PARE e opere a fábrica.** Rode missões reais de verdade. Só volte pro Tier 2 quando sentir falta de uma tela específica.
5. Marco → **Fable/Opus** revisa o pacote e aponta o que melhorar.

Pode rodar isso no loop do Maestri (Arquiteto define contrato → Operário free preenche telas → Revisor valida) **ou** despachar como missão do próprio motor (dogfood: a fábrica constrói o próprio painel). Os dois usam modelo free; nenhum queima seu Claude.

## Missão cumprida quando
As 4 telas do Tier 1 rodam sobre o contrato, lendo o log real, e você aprova um gate pela CaixaFundador sem tocar no terminal — construídas por modelo free. Aí o painel deixou de ser bloqueio e virou a janela por onde você opera a fábrica. As outras 16 entram só quando forem sentidas como falta.

---
*Plano criado em 2026-07-04. Alinha com [[3. Arsenal]] (frota free), [[5. Gateway de Fallback]] (como servir os modelos) e a Doutrina Local-First. O design já está pronto; falta só o fiação barato.*
