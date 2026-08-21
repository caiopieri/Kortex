# DECISÃO — Cortes na interface e a estante de artefatos

> **Aprovado pelo fundador em 2026-08-19.** Deixa de ser proposta.
>
> Origem: inventário medido pelo agente do canvas sobre `motor_painel/app/src`.
> Companheiro de `DECISAO-canvas-e-operacao.md` (a superfície) e
> `DECISAO-modos-do-produto-e-colapso.md` (zonas e colapso).

---

## 1. O que foi medido

21 páginas mais o canvas, **7204 linhas** de JSX/JS.

**Quatro telas desenham o mesmo grafo.** A issue #15 reconciliou o painel com o canvas;
sobraram quatro projeções ao todo:

| tela | linhas | |
|---|---|---|
| `Grafo2D` | 840 | projeção própria |
| `Grafo3D` | 512 | consome `/dados` |
| `canvas/ledger/Grafo` | 166 | a projeção canônica |
| `MapaGeral` | 163 | inventa "projeto" agrupando por `objetivo` |

A #15 não era defeito isolado — era o **sintoma de uma regra ausente**: quem projeta o
log. Ela reconciliou duas; as outras duas sobram.

**Quatro telas renderizam o mesmo estado de run** — `Home`, `Dashboard`, `Board`,
`MapaGeral`. Só o `Board` tem trabalho próprio (kanban de gate humano); as outras são a
mesma consulta com outro layout.

**Sete páginas fazem poll do `/dados` inteiro a cada 2s** — `Curador`, `Datahouse`,
`MapaGeral`, `Board`, `Dashboard`, `Logs`, `Grafo3D`. É exatamente o gargalo que
`DECISAO-canvas-e-operacao.md` §6.1 previu: *"o gargalo será a camada de dados, não os
pixels"*.

## 2. O modelo do que está certo

`Runners.jsx`, com 36 linhas, é a melhor tela do painel. Ela não tem fonte, e **declara
que não tem**:

> *"o motor não registra host, IP nem capacidade, então o painel não tem o que mostrar
> aqui — e não vai inventar"*

**Toda tela sem contrato deve ter essa forma.** `Skills.jsx` e `Conexoes.jsx` também a
seguem. Foi essa forma que substituiu os dados fabricados removidos na issue #23.

## 3. Os cortes aprovados

Por gravidade, não por tamanho. **Nenhuma informação que o ledger emite se perde** — é
redundância, não conteúdo.

1. **`Grafo3D`** (512) — **não some: vira modo de vista do canvas.** A página e a rota
   saem; a capacidade fica. Decidido pelo fundador em 2026-08-19, sobre a própria
   ressalva do autor da proposta.

   **A formulação que vale: uma projeção, N renderizadores.** O defeito da issue #15
   nunca foi *renderizar* — foi *projetar*. Duas projeções divergem, e divergiram (8
   nós/0 arestas contra 5/4). **Dois renderizadores sobre uma projeção não têm como
   divergir**, porque recebem o mesmo dado.

   Isso não abre exceção: `DECISAO-canvas-e-operacao.md` §6.3 já decide que *"o
   renderizador de massa fica atrás de uma interface fina para que a escolha não seja
   porta de mão única"*. 3D é escolha de renderizador sobre a projeção canônica, e
   implementar isso **é** construir aquela interface fina.

   **A posição, porém, não pode ser inventada — e isso quase passou.** `canvas/ledger/Grafo.jsx`
   posiciona nó por **onda declarada** (coluna = onda), e o comentário diz: *"não há
   coordenada no ledger e a superfície não finge que há"*. Um grafo *force-directed*
   **inventa posição**: a coordenada vira função da física, não de nada declarado. "3D e
   2D desenham o mesmo grafo" seria verdade na **topologia** e falso na **posição** — e
   inventar lugar é a mesma regra que matou o `MapaGeral` no corte 3.

   **Decisão: a onda declarada define o eixo Z; a física só espalha DENTRO da onda.** O
   eixo que carrega significado continua declarado, e a física fica confinada ao que já
   era arbitrário (a ordem dentro da onda, que o 2D também arbitra, em linha). Isso torna
   o 3D **melhor que a tela antiga, não um porte dela**: profundidade de onda legível de
   relance é leitura que o 2D não dá — e é o que justifica a capacidade existir depois de
   tudo que foi cortado.

   **A CDN sai.** O `Grafo3D` buscava `three` e `3d-force-graph` no unpkg.com **em tempo
   de execução** — as únicas dependências do painel fora do `package.json`. **Sem rede, a
   tela não abre**, e o painel roda na LAN, num runner que existe para funcionar sozinho.
   Vira `import()` dinâmico com pacotes instalados: chunk sob demanda, bundle base
   intacto.

   Critérios de aceite: topologia idêntica ao 2D para a mesma run (irmão do teste da #15);
   **Z derivado da onda declarada** — dois nós de ondas diferentes nunca com o mesmo Z,
   dois da mesma onda sempre; a segunda projeção de estado do `Grafo3D` **apaga** e passa
   a ler `no.estado`, `no.falhas` e `run.terminal` do `projetarRun`; e a tela **abre sem
   rede**.

   **O custo real, medido e honesto:** das 512 linhas, ~230 sobrevivem, e a maioria é
   boilerplate de three.js que um rewrite produziria igual. O que é caro de redescobrir
   são três coisas — o merge de nós persistentes (evita jitter), `setPixelRatio(1)` +
   `shadowMap` desligado, e o recolorir no evento de tema. **O porte economiza um dia,
   não uma semana.** A decisão, portanto, não é econômica: é de conteúdo.

   **Se o porte custar mais que reescrever depois, a capacidade sai** e a decisão fica
   registrada — a medição do autor foi que ela é *"a tela mais divertida e a menos
   informativa"*, e se ela só ficar divertida depois de trabalho grande, isso é
   informação.
2. **`Grafo2D`** (840) — depois da #15, é a projeção que o canvas substituiu, e o canvas
   tem o andon que ela não tem. Uma projeção do log, uma só.
3. **`MapaGeral`** (163) — inventa "projeto" a partir de `objetivo`. Projeto **não
   existe no modelo**: cada run é um `runs/<id>` que esquece tudo (§G do `ESTADO.md`).
4. **`Home`** (408) — duplicação pura. **Correção de 2026-08-20:** o texto original dizia
   "duas das três" entre `Home`, `Dashboard` e `Board`; era taquigrafia da proposta e
   estava errado. A substância é **remover redundância, preservar trabalho próprio** — e
   `Dashboard` tem cálculo próprio que mais nada faz: **% de 1ª tentativa, latência
   mediana e p90, escaladas com convergência, saúde de provedor**. O curador **coleta
   `latencias` e nunca as desenha**; cortar o `Dashboard` apagaria as quatro medidas do
   painel inteiro. `Board` sobrevive por trabalho próprio (gate humano).

   Achado incidental do corte: a seção "Mapa geral vivo" da `Home` era **SVG hardcoded** —
   `planner`, `pesquisa-alfa`, `pesquisa-beta`, `global_evaluator` desenhados à mão, com
   animação de fluxo, sob o rótulo **"tempo real"**. Nenhum vinha do ledger. É o sétimo
   irmão do defeito da issue #23, agora em SVG.
5. **`Skills`** (99) — projeção do campo `papel` que o `Inventario` já mostra.
6. **Três dos quatro temas.** São 4 temas + 2 peles do canvas = **seis linguagens
   visuais** para um produto de um usuário. Cada uma é caminho de código que quebra
   sozinho, e o `App.jsx` já carrega comentário sobre a tela ficar "metade clara, metade
   escura" quando os dois estados dessincronizam.
7. **O rótulo "Projeto: Todos"** na sidebar — promete um seletor que não existe.

Ordem de grandeza: **~2500 das 7204 linhas**.

**A decisão de remover vem antes da de construir**, porque construir a aba de aplicações
sobre 21 telas é fazer a 22ª.

## 4. A estante de artefatos (a "aba de aplicações")

### O que a medição mostrou

47 eventos `artefato.atualizou` no ledger de produção, com **`tipo` = "python" em 47 de
47**, e três nomes de arquivo no total.

A fábrica nunca produziu um site nem um objeto 3D. **A aba não está bloqueada por falta
de contrato — está bloqueada por falta de corpus.** Se o contrato tipado ficasse pronto
hoje, a estante mostraria 40 cartões escritos "python".

*(Ressalva medida depois: 9 de 49 artefatos não têm evento — issue #22. Parte é registro
perdido, não só corpus.)*

### A forma

Não é vitrine de janelas vivas. É **estante**, e cada cartão tem o que o evento declara
mais **um slot vazio nomeado**:

```
[ nome ] [ tipo ]                    <- do evento, hoje
[ produzido por: <subagente> ]       <- do evento, hoje
[ na run: <link> ]                   <- so depois da issue #24
[ revisoes: N ]                      <- so com hash; hoje seria mentira
+-----------------------------------+
|  sem pre-visualizacao             |
|  o motor nao declara como abrir   |
|  um artefato "python"             |
+-----------------------------------+
```

**O slot vazio é o ponto.** Ele torna o contrato que falta visível toda vez que a aba
abre — o que funciona melhor que um documento que ninguém relê. É a mesma forma do
`Runners.jsx`.

### A cadeia até a janelinha viva

Em ordem de custo, e **são quatro contratos, não um ajuste de tela**:

1. **`hash` no evento** (issue #24, em curso). Sem ele a identidade é *caminho*, que é
   localização: dois artefatos com o mesmo caminho em runs diferentes são coisas
   diferentes, e o mesmo conteúdo em dois lugares parece duas coisas. Com hash,
   "revisões" vira verdade.
2. **`tipo` virar enum/registry.** Hoje é string livre validada só como não-vazia, e é o
   `tipo` que decide se existe visualizador. Sem enum, o slot **nunca** sai de vazio.
3. **Proveniência (V5+V7).** Responde "a partir de que este artefato nasceu" e permite
   mostrar linhagem em vez de lista.
4. **A forma "sessão"** (`DECISAO-canvas-e-operacao.md` §5.1). Só ela entrega a janelinha
   viva: *"não se observa um processo vivo num contrato argv → exit code"*. E §5.1 já
   decide a regra — visualizador é read-only por padrão, e se virar interativo a ação vai
   ao ledger **com autor**.

### O que NÃO entra

**Agrupamento por "projeto".** Projeto não existe no modelo. Agrupa-se por run e, quando
o hash chegar, por identidade de conteúdo — e a tela **declara** que projeto não existe,
em vez de fabricar um a partir de `objetivo` como o `MapaGeral` faz.

**Métricas por projeto.** Não é só overengineering: **a métrica não teria sujeito.**

## 5. Onde isto pode dar errado

- **A lista de cortes é por redundância medida, não por uso observado.** O autor não
  sabia quais telas o fundador abre todo dia; o fundador aprovou sabendo disso. Uso
  observado venceria a medição, e ainda vence se alguém sentir falta.
- **Remover `Grafo3D` é politicamente caro e tecnicamente barato** — a pior combinação.
  É a tela que dá prazer. Se ela voltar, que volte como modo de vista, não como tela.
- **A estante com slot vazio pode virar monumento à falta.** Uma aba onde tudo diz "sem
  pré-visualização" é honesta e desanimadora. Se o corpus não mudar em algumas semanas,
  ela vira prova diária de que a fábrica não produz aplicação — o que é achado
  verdadeiro, mas transforma uma funcionalidade pedida em acusação.
- **Cortar antes de construir concentra risco num diff grande.** Vale fazer em etapas
  revisáveis, não num commit só.
- **A medição de artefatos é comprovadamente incompleta** (issue #22), e o autor só
  descobriu o quanto ao cruzar com o disco. Pode haver mais buraco: a contagem assume que
  todo artefato mora em `runs/*/artefatos/`.
