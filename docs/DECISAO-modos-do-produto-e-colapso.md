# DECISÃO — Modos do produto e colapso visual

> **Canônico** sobre duas coisas: (1) a caixa que esconde um processo é **apresentação, nunca
> semântica de execução**; (2) o terceiro modo do produto — a aplicação que cobre a
> complexidade. Registrado em 2026-08-19, a partir de decisão verbal do fundador.
>
> Companheiro de `DECISAO-canvas-e-operacao.md` (a superfície) e
> `DECISAO-ciclo-de-vida-workflow.md` (o objeto workflow). **Não cria vocabulário novo para o
> que já tem nome** — ver §1.

---

## 1. O que já estava decidido (e fica como está)

O fundador descreveu três modos: *Studio* (criativo, livre), *Enterprise* (produção) e
*Apps* (interface que cobre a complexidade). Dois deles **já existiam com outro nome**, e os
nomes existentes são melhores porque dizem a regra em vez do público:

| nome falado | nome canônico | onde |
|---|---|---|
| Kortex Studio / modo criativo | **zona de rascunho** | `DECISAO-canvas-e-operacao.md` §3 |
| Kortex Enterprise | **zona de roteiro** | idem |

Fica valendo o vocabulário existente: **rascunho** e **roteiro**. "Studio" e "Enterprise"
podem ser rótulos de interface para o usuário final; **não** são conceitos novos na
arquitetura, e não devem aparecer em código ou spec como se fossem.

Também já estava decidido, e é reafirmado aqui: **o canvas é uma forma de escrever a spec**
(`DECISAO-canvas-e-operacao.md` §3, corolário; `EVOLUCAO.md` V7). Autoria interativa não é
ideia nova a aprovar — é construção pendente.

**Por que ainda não foi construída:** `EVOLUCAO.md` §"Sequência sugerida" põe o V8 (backend
de execução) como *"o desbloqueador"*, que *"vem antes de qualquer coisa nova, **inclusive de
tela**"*. O V8 foi certificado em 2026-08-18. A tela deixou de estar atrás de dependência.

### 1.1 Zonas, não aplicativos — e nem modo global

Registrado em 2026-08-19, depois de o fundador propor separar em **dois aplicativos**
(Studio e Enterprise) e de o agente do canvas contrapor com argumento melhor que o meu.

**Dois aplicativos: não.** Os dois falariam com o **mesmo motor** e o **mesmo ledger**,
então o risco de rodar spec não certificada seria idêntico — *"só que com a sensação de
estar protegido"*. E duas superfícies que fazem a mesma coisa divergem: a issue #15,
fechada no mesmo dia, mediu o painel desenhando **8 nós e 0 arestas** enquanto o canvas
desenhava 5 e 4, sem que ninguém quisesse divergir. Dois apps é essa mesma falha com
uma fronteira de deploy no meio para ninguém perceber.

**Eu propus "um app, dois modos, com o modo imposto". Também está errado**, e a razão é
mais forte que a minha proposta:

> **Modo global é estado, e estado pode estar errado.** Se existe "estou em Studio",
> existe "achei que estava em Enterprise". A pergunta *"em que modo eu estou?"* não
> deveria ter como ser feita.

**A decisão: o regime vem do objeto, não do aplicativo nem de um modo.**

- Você não "entra no Studio" — você **abre um rascunho**. Rascunho tem afordância de
  autoria porque é isso que rascunho é.
- Você não "entra no Enterprise" — você **abre um roteiro certificado**. Ele não tem
  afordância de autoria em build nenhum, nunca, porque roteiro certificado não se edita:
  edita-se a próxima versão, que nasce rascunho. Isso já **é** a passagem "explícita e
  unidirecional" do `DECISAO-canvas-e-operacao.md` §3.
- Os dois convivem na mesma tela, visualmente inconfundíveis, sem trocar de janela. O
  operador olha o roteiro rodando e rascunha a hipótese ao lado — que é o gesto real.

**Sobra exatamente uma pergunta global:** *"esta instalação pode ter rascunho?"* — e essa
é **flag de build**, não estado de runtime: em build sem autoria, os módulos de autoria
**não são importados**. Não é botão desabilitado nem feature flag; não está no bundle.
Uma pergunta, uma resposta, sem estado que possa mentir.

O "subir de branch para main" que o fundador descreveu **já tem nome e já tem regra**: é
a promoção rascunho → roteiro. Não é deploy entre produtos — é gate. Chamar de "dois
aplicativos" transfere a segurança do gate (que é real) para a separação de janelas (que
não contém nada).

**Onde isto pode estar errado, registrado pelo próprio autor:** algumas afordâncias são
genuinamente globais — "criar novo", "importar", "abrir editor". Elas não têm objeto que
carregue regime e vão acabar num flag de qualquer jeito. Se forem muitas, este desenho
colapsa de volta em "modo global", com mais passos.

---

## 2. Decisão nova — colapso é apresentação, não execução

**Um bloco pode esconder um processo inteiro na tela. O grafo executado continua plano.**

Colapsar e expandir uma fase é operação de **vista**. Na hora de rodar, o grafo é achatado e
cada nó continua sendo um nó, com seu portão, sua rubrica e seu evento no ledger.

### Por que assim, e não aninhando de verdade

`DECISAO-ciclo-de-vida-workflow.md` §10 recusa topologia livre — *"não é n8n de fios livres"* —
e a razão é que uma estrutura de controle nova é uma que **o motor não sabe verificar**.
Aninhar workflow dentro de workflow tem o mesmo defeito e um pior: **esconde o portão**. A
caixa vira preta e a evidência de dentro dela some do lugar onde alguém audita.

Colapso visual entrega a legibilidade que o aninhamento prometia **sem** pagar esse preço. É
a mesma escolha que o ComfyUI faz com subgrafos: agrupa na tela, achata na execução.

### A regra que impede o colapso de virar mentira

> **Uma caixa colapsada nunca é mais verde que o pior nó dentro dela.**

Se um portão reprovou lá dentro, a caixa mostra reprovado. Se um nó está pendente de gate
humano, a caixa mostra pendente. Colapsar reduz **detalhe**, nunca **severidade**. Isto é o
mesmo princípio do andon em `DECISAO-canvas-e-operacao.md` §5 — a superfície não inventa
lugar, e agora também não inventa saúde.

### O que isto exige

- O estado agregado da caixa é **derivado**, nunca armazenado: recalculado dos nós contidos.
  Estado agregado guardado é a forma clássica de ele mentir depois.
- Colapsar/expandir **não** altera a `WorkflowSpec`. Se alterar, virou semântica — e aí é
  padrão topológico novo, que exige versão de spec certificada (`DECISAO-ciclo-de-vida-workflow.md` §4).
- O agrupamento é metadado de apresentação e pode ser versionado junto da spec, mas o motor
  ignora esse campo por contrato.

---

## 3. Decisão nova — o terceiro modo: aplicação

Um workflow certificado pode ganhar **uma interface própria que cobre a complexidade**: o
usuário vê campos e um botão, não blocos e fios. Por trás, é o mesmo roteiro versionado, com
os mesmos portões e a mesma evidência.

Isto **não** é um quarto ambiente nem um motor diferente. É uma **projeção** do roteiro:

- só workflow **certificado** vira aplicação — o que está em rascunho não tem interface;
- a aplicação **não pode** relaxar portão, pular gate humano nem alterar a spec. Se ela
  precisar de um caminho que o roteiro não tem, o caminho entra no roteiro, é aprovado, e só
  então a aplicação o expõe;
- a evidência produzida por uma run disparada pela aplicação é evidência igual: mesmo ledger,
  mesmo curador, mesma proveniência. **Interface simples não produz prova mais fraca.**

Nome de trabalho: **aplicação**. Fica registrado que o fundador a chama de "Kortex Apps".

---

## 4. O que isto NÃO decide

- **Não decide o vocabulário de tipos** das arestas. Ligação entre nós é artefato tipado com
  proveniência (`DECISAO-canvas-e-operacao.md` §4), e definir esse vocabulário é o trabalho
  aberto de V5+V7 — a maior peça pendente do projeto.
- **Não decide como o orquestrador desenha o workflow** a pedido do usuário. Que ele possa
  fazê-lo já está em `DECISAO-ciclo-de-vida-workflow.md` §3 (autoria é uma run do motor); ver
  o desenho aparecendo ao vivo na tela é consequência de interface, não decisão nova.
- **Não decide renderizador, LOD nem desempenho** — isso é `DECISAO-canvas-e-operacao.md` §6.

---

## 5. Onde isto pode dar errado

- **A regra do "nunca mais verde" é fácil de escrever e fácil de furar.** Basta um agregado
  cacheado, um estado otimista enquanto carrega, ou um ícone neutro que o olho lê como bom.
  Se for implementada, precisa de teste causal: nó reprovado dentro, caixa fechada, a caixa
  tem que aparecer reprovada.
- **Colapso pode virar aninhamento pela porta dos fundos.** No dia em que alguém quiser
  "reusar aquela caixa em outro workflow", a pressão para transformá-la em unidade de
  execução volta — e aí é padrão novo, com o rigor que padrão novo exige, não um atalho de UI.
- **A aplicação é a superfície mais fácil de mentir do sistema inteiro**, porque foi feita
  para esconder. Um formulário bonito sobre um roteiro reprovado é indistinguível de um sobre
  um roteiro aprovado, para quem olha só a frente.
- **Rótulos "Studio" e "Enterprise" podem vazar para o código** e criar um segundo vocabulário
  concorrendo com rascunho/roteiro. Se isso acontecer, dois times passam a falar línguas
  diferentes sobre a mesma zona.
- **Nada disto está construído.** É decisão registrada, não funcionalidade. O `ESTADO.md`
  continua sendo quem diz o que existe.
