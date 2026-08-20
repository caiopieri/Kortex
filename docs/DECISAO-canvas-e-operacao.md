# DECISÃO — Canvas e superfície de operação

> A fábrica vista como fábrica: tela infinita, andares, e o cordão que puxa você até o defeito.
> Registrado em 2026-08-10. Normativo junto com `../motor/specs/002-painel-operacional/spec.md`,
> que continua valendo integralmente. **Isto é direção, não estado.**

---

## 1. O que se decidiu construir

Uma superfície de operação em canvas infinito, organizada em **andares**, onde se vê a fábrica
rodando em tempo real e — o ponto central — **se é levado até o defeito**.

O modelo não é "visualização de grafo". É **andon**: o sinal aparece, aponta a estação exata, o
operador vai até lá com um supervisor do lado, acha a raiz, e a correção volta para o processo para
não repetir. Isso é a operação de uma fábrica renderizada, e é a razão de a interface própria existir
("VÊ a fábrica rodando e **intercepta**").

O supervisor que aprende é o curador. O canvas é onde o humano encontra o defeito; o curador é o que
impede a reincidência.

---

## 2. A regra que protege tudo

> **Nada existe por estar no canvas. Existe por estar no ledger ou numa spec.**

O canvas é projeção e editor — nunca segunda fonte de verdade. Toda invariante do painel
(`002-painel-operacional`) continua valendo: nada de progresso, custo ou saúde simulados; controle ou
faz a ação documentada ou fica visivelmente desabilitado.

### Corolário: rigidez de spec não é rigidez de interface

`WorkflowSpec` estrito é qualidade do sistema. Experiência engessada é defeito de UI, não requisito
de disciplina — as duas coisas vivem em camadas diferentes e não se pagam mutuamente. O canvas pode
ser inteiramente fluido e emitir uma spec rigorosamente validada, como um editor gráfico fluido emite
um formato estrito. Onde a criatividade do operador estiver morrendo, o defeito é da superfície, não
do contrato.

---

> **Complemento (2026-08-19):** os cortes aprovados na interface e o desenho da estante
> de artefatos estão em `DECISAO-interface-cortes-e-estante.md`.
>
> **Complemento (2026-08-19):** o colapso visual de uma fase e o terceiro modo (aplicação)
> estão em `DECISAO-modos-do-produto-e-colapso.md`. Lá também fica registrado que "Kortex
> Studio" e "Kortex Enterprise", como o fundador os chama, são **rótulos** para as zonas de
> rascunho e roteiro definidas nesta seção — não conceitos novos.

## 3. Duas zonas com regras diferentes

| Zona | Regras | Autoridade |
|---|---|---|
| **Rascunho** | livre: nota, desenho, ligação solta, hipótese, "verifica isso pra mim" | **nenhuma.** Nada aqui é fato; nada alimenta o curador |
| **Roteiro** | só a gramática válida; emite `WorkflowSpec` | produz evidência |

A passagem de rascunho para roteiro é **explícita e unidirecional**: hipótese vira roteiro passando
por validação, nunca por estar bem desenhada. Mesma forma de "promoção é intenção sujeita a gate" —
desenho bonito não promove nada.

Isso resolve a tensão entre disciplina e criatividade: o rascunho é o operador **gerando hipótese**
(onde o humano é bom), o roteiro executado é o **seletor** (onde o humano não é autoridade). Ver
`DECISAO-conhecimento-e-julgamento.md` §3.

**O rascunho que gerou um roteiro bom vira proveniência, não evidência.** Fica anexado à versão da
spec como *origem* — recuperável, auditável, e sem veredito nenhum. Não conta como prova de nada e
não entra no corpus do curador. Rascunho descartado pode ser apagado sem consequência.

**Autoria só oferece a gramática válida** — decisão já tomada em `../motor/docs/EVOLUCAO.md` V7. O
canvas é uma forma boa de escrever a spec, não um editor de programa. Padrão topológico novo continua
exigindo versão de spec certificada.

---

## 4. Andares

Andar = **casa / harness** (softwarehouse, hardware, mecânica, treinamento). Não é metáfora nova: é a
camada que já existe acima do motor.

Ligação entre andares **não é fio solto**: é artefato tipado com proveniência atravessando a
fronteira, e quem encadeia é o orquestrador, não o motor
(`DECISAO-ciclo-de-vida-workflow.md`, decisão #5). Desenhar a ligação no canvas produz um handoff
tipado ou não produz nada.

Um andar de treinamento é uma casa cujo produto é especialista — o V6 de `EVOLUCAO.md`, que segue
gated pelo grader.

---

## 5. O andon

### Duas classes de defeito, e nunca inventar lugar

| Classe | Exemplos | Onde aparece |
|---|---|---|
| **Localizado** | nó reprovado, validador falhou, gate esperando, reconciliação estourou o teto | na estação: andar → run → nó |
| **Sistêmico** | composição falhou, FX/pricing vencido, credencial ausente, rota sem cobertura de capacidade, runner negado | **portaria** — estação fixa de pré-voo, antes de qualquer run existir |

A segunda classe é a que mais trava a operação hoje e é justamente a que não tem coordenada no grafo.
**O indicador nunca inventa localização.** Quando o defeito não tem nó, ele diz que não tem, e leva à
portaria — o mesmo princípio de `Conexoes.jsx`, que se recusa a colapsar "não" com "não verificável".

### O que o andon exige do motor

Cada evento de falha precisa carregar coordenada ou declarar ausência dela. Isso é extensão do schema
de eventos, não trabalho de UI. Sem coordenada, o canvas não tem para onde levar.

---

## 5.1 Visualizadores de ferramenta

Uma janela viva na tela mostrando o que o agente está fazendo — o modelo mudando no FreeCAD, o
navegador navegando, o simulador rodando. **Sim, e é especialmente valioso nas verticais onde
evidência é cara** (hardware, mecânica, design), porque ali a observação humana é o verificador
disponível.

Três regras:

1. **Visualizador é projeção, read-only por padrão.** No instante em que o operador pode clicar dentro
   da janela, surge a pergunta "quem agiu — agente ou humano?". Ação sem autor é vazamento de
   autoridade. Se for interativo, a ação vai ao ledger **com autor**, como qualquer outra.
2. **A janela de pensamento fica no registro de rascunho e nasce colapsada.** Raciocínio de modelo
   não é evidência — está abaixo de `opiniao`, porque nem output é. Ao lado de um resultado, ele
   convida a julgar pela narrativa: raciocínio eloquente faz trabalho ruim parecer cuidadoso. É útil
   para diagnosticar **por que** deu errado — que é o propósito do andon — e nunca é razão para
   aprovar. Separação visual não basta se for a janela mais interessante da tela: **colapsada por
   padrão, aberta sob demanda.**
3. **Visualizador exige a forma "sessão"** (`DECISAO-provedores-e-computacao.md` §2.4), que ainda não
   existe. Não se observa um processo vivo num contrato `argv` → exit code.

**Screenshot por passo, anexado ao ledger.** Converte "um humano olhou e pareceu certo" em **opinião
reproduzível**: continua `opiniao` no carimbo, mas passa a ser auditável e replayável — e é o caminho
honesto para um dia extrair dali um validador determinístico.

## 6. Desempenho — as três decisões, em ordem de impacto

### 6.1 O dado antes do render

O gargalo será a camada de dados, não os pixels. `usePoll` busca o estado inteiro periodicamente;
isso morre antes de qualquer otimização de canvas importar.

**Decisão:** streaming incremental sobre `seq`. O ledger é append-only com `seq` contígua (invariante
E2) — é exatamente o substrato que a maioria dos apps precisa inventar e que aqui já existe. Endpoint
`/dados/eventos?desde=<seq>`, cliente mantém o fold e aplica deltas.

**Correção obrigatória, mesmo contrato do relay monetário:** o cliente rastreia a última `seq`,
**detecta buraco** e refaz o fold quando houver descontinuidade. Enquanto a projeção estiver suspeita,
a tela diz que está suspeita — nunca mostra um estado que não existiu. Divergência é visível, não
silenciosa.

Isto vem **antes** de trocar de renderizador.

### 6.2 Nível de detalhe (LOD), com a fronteira decidida

Não é DOM *ou* WebGL. É híbrido, e o híbrido é onde projetos de canvas afundam — então a fronteira
fica decidida aqui:

- **Camada de massa** (zoom afastado): retângulos, arestas e rótulos em WebGL/Canvas2D. Milhares de
  nós, sem DOM. **Não é interativa** além de seleção e navegação.
- **Camada de foco** (zoom aproximado / nó selecionado): componente React real sobreposto, com log ao
  vivo, botões e formulário. **É a única camada interativa.**
- **Uma única fonte de coordenadas**, da camada de massa. A camada de foco se posiciona a partir dela,
  nunca o contrário.

Regra de execução: **não implementar LOD à mão.** Usar biblioteca que já resolveu hit-testing,
zoom/pan, seleção e undo.

### 6.3 Renderizador — escolha reversível

- **Mapa da fábrica** (tela infinita): biblioteca de canvas infinito. `tldraw` é a candidata mais
  forte; **verificar a licença comercial antes de acoplar**, não depois. `PixiJS` é a alternativa se
  quisermos controle total.
- **Grafo de uma run**: ReactFlow, que já está em uso e é ótimo em dezenas de nós. Não forçá-lo a ser
  a tela infinita — ele é DOM e o teto é de algumas centenas.
- **Nó em foco**: DOM/React, como hoje.

O renderizador de massa fica **atrás de uma interface fina** para que a escolha não seja porta de mão
única. Trocar de canvas no meio do caminho é caro; a interface é o seguro.

---

## 7. App ou navegador

**App — e a razão é o andon, não a estética.** Um indicador de problema é inútil se a aba não está
aberta. O andon exige notificação nativa, ícone com estado da operação e clique que traz a janela e
navega até a estação.

**Tauri**, pelo peso e porque a maior parte da superfície é DOM/SVG; o sidecar Python funciona. Com
uma condição de execução: **testar o caminho WebGL em WKWebView na primeira semana**, não na última —
é a divergência conhecida do webview nativo e é o único risco que pode derrubar a escolha.

O navegador continua sendo caminho de primeira classe. O app é uma casca sobre a mesma superfície, não
um segundo produto.

---

## 8. Sequência

1. **Streaming incremental sobre `seq`** com detecção de buraco. Vale para o painel atual; é o ganho
   maior e independe de canvas.
2. **Coordenada nos eventos de falha** + classe localizado/sistêmico. É o que torna o andon possível.
3. **Mapa da fábrica em canvas** com LOD, começando somente como **vista** (projeção).
4. **Zona de rascunho** — a superfície criativa, sem autoridade.
5. **Autoria** emitindo `WorkflowSpec` na gramática válida.
6. **Casca Tauri** com notificação nativa, quando o andon estiver de pé.

---

## 9. O que isto não resolve

Registrado para não haver ilusão: **canvas nenhum faz o motor rodar.** Hoje a composição custeada
falha por FX/pricing vencidos e execução de comando é default-deny. Uma superfície fluida sobre uma
fábrica parada mostra uma fábrica parada com mais fluidez.

A sensação de rigidez tem duas causas somadas — a superfície é dura *e* não há nada acontecendo para
ver. Esta decisão ataca a primeira. A segunda é `DECISAO-provedores-e-computacao.md` §6 e o item 1 do
Now no `ROADMAP.md`, e continua tendo precedência.

---

## 10. Onde isto pode dar errado

- **O canvas é a coisa mais divertida de construir no projeto e não move nenhum dos três bloqueios.**
  É o risco "largura sobre profundidade" na forma mais tentadora. A mitigação escrita aqui é a
  sequência: streaming e coordenada de falha (itens 1 e 2) melhoram o painel que já existe e são úteis
  mesmo se o canvas nunca for construído.
- **A classe "sistêmico" pode engolir a "localizado".** Se a maioria dos defeitos reais for de
  pré-voo, a portaria vira a tela principal e o mapa da fábrica vira decoração — o que seria um
  achado honesto sobre o estado do sistema, não uma falha do desenho, mas mudaria a prioridade.
- **Coordenada em evento de falha pode ser mais invasiva do que o §5 sugere.** Se exigir mudança no
  schema de eventos, entra no guard anti-drift e no corpus de reprodutores — não é trabalho de UI, é
  mudança de contrato do motor, com o custo que isso tem.
- **Duas zonas na mesma tela convidam a confusão que elas existem para evitar.** Se rascunho e roteiro
  não forem visualmente inconfundíveis, alguém vai olhar um desenho e achar que é o sistema. A
  distinção precisa ser óbvia à distância, não uma legenda.
- **"Uma interface fina sobre o renderizador" é fácil de escrever e difícil de manter.** Abstração
  sobre motor gráfico costuma vazar no primeiro requisito de performance, e aí o seguro não vale o
  prêmio pago.
