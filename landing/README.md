# landing — página do Kortex

Landing page build-in-public do **Kortex** (sistema agêntico open source).
Vive dentro do próprio repo do projeto (`Kortex/landing/`) — coerente com o
discurso "100% open source · construído com a própria fábrica".
Estático, sem build step, sem dependências. Dark-first com modo claro espelhado,
monocromático estilo Linear.

## Rodar

```bash
# a partir da raiz do repo Kortex
python3 -m http.server 4180 --directory landing
# → http://localhost:4180
```

## Estrutura

- `index.html` — página única: hero (globo-grafo interativo) → diferenciais
  (3 destaques + bento + 4 leis) → filosofia → prova (stats reais + replay de
  terminal) → peças do ecossistema → CTA waitlist → footer.
  A marca (símbolo + wordmark) vive em `<defs>` SVG, geometria oficial do
  kortex-brand-system.
- `styles.css` — tokens dark/light monocromáticos (`--bg/--surface/--text/...`);
  Archivo (variável, wdth) + IBM Plex Mono. A única cor permitida é o
  verde/vermelho semântico dentro do terminal e do demo de portão (como diff).
- `app.js` — vanilla JS: globo-grafo em canvas 2D (esfera de fibonacci ~4k
  partículas, nós+arestas, rotação lenta, repulsão ao cursor com mola), tema
  com localStorage, reveals por IntersectionObserver, demos (portão, roteiro
  digitado, replay de terminal), contadores. Pausa fora do viewport e respeita
  `prefers-reduced-motion`.

Sem assets locais: logo é SVG inline, favicon é data-URI, fontes são CDN.

## Deploy

Produção na **Vercel** — https://kortex-site.vercel.app.
Estático puro, então basta servir esta pasta como raiz. Para deploy por Git,
apontar o `rootDirectory` do projeto Vercel para `landing/`; assim cada push
vira deploy (com preview por PR).

## Copy — âncoras de honestidade

Selos: **já roda** · **em construção** · **visão** — nunca apresentar visão
como pronto. Números da seção Prova vêm do estado real do repo (2026-07):
333 testes verdes, 46 eventos tipados (`eventos_schema.py`), motor v0.5 fase C,
retomada 5/5 vs 1/5 pós `kill -9`. Se o estado mudar, atualizar aqui, no hero
(eyebrow) e em `#prova`.

## Integrações

- Waitlist: Formspree (`https://formspree.io/f/xykrgqjg`), POST JSON com `{email}`.
- Repo público: links apontam para `github.com/caiopieri/Kortex`.
