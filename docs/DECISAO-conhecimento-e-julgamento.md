# DECISÃO — Conhecimento e julgamento

> Onde entra dado, onde entra humano, e por que os dois têm papel assimétrico.
> Registrado em 2026-08-07. Complementa `LEIA-PRIMEIRO.md` §4 (princípios 5 e 8) e
> `motor/docs/ADR-003` (promoção como intenção gated). **Isto é direção, não estado:
> nada aqui está implementado além do que já estava.**

---

## 1. O problema que motivou

Duas perguntas voltaram ao mesmo tempo:

1. **Precisamos de um "Kortex Data"?** — uma infraestrutura de aquisição (SQL/NoSQL/vetorial,
   embeddings, pipelines de ingestão, dataset management) para alimentar os agentes e,
   eventualmente, treinar especialistas.
2. **O gate humano é confiável?** — o motor pausa e pergunta ao fundador; na prática o fundador
   frequentemente carimba sem ler, e o motor registra isso como evidência.

As duas têm a mesma resposta de fundo: **necessário não é o mesmo que escasso, e escasso não é o
mesmo que "vale construir aqui".**

---

## 2. Decisão A — Conhecimento: comprar o gerador, construir o seletor

### O enquadramento

Conhecimento e experiência não são dois estoques da mesma substância. Ocupam posições diferentes
no ciclo:

- **Conhecimento é o gerador de hipótese.** Estreita o espaço de busca. Sem ele, tentar é
  aleatório.
- **Experiência é o seletor.** Decide qual hipótese sobrevive.

Ambos são necessários. As economias são opostas:

| | Gerador (conhecimento) | Seletor (experiência) |
|---|---|---|
| Se compra? | **Sim** — é commodity | Não. Ninguém vende |
| Retorno de mais investimento | decrescente | crescente |
| Melhora sozinho? | sim, a cada release de modelo | só se rodarmos missão |

Documentação pública raspada é commodity de treino: todo modelo de fronteira já treinou nela e vai
treinar de novo. Nosso **traço de execução com veredito** — esta tentativa passou no verificador
independente, aquela reprovou, e por quê — não está no dataset de ninguém.

### O que isto decide

1. **Não construir armazém de conhecimento externo.** Confirma e afia o princípio 8
   ("catálogo federado, não armazém") e o 5 ("conhecimento antes de peso").
2. **Ordem de custo/benefício para "o agente não sabe a API atual"**, do mais barato ao mais caro:
   1. **executar / typecheck** — pega o erro inclusive de biblioteca que ninguém ingeriu
      *(bloqueado hoje: sandbox não certificado — ver dívida 1 de `INVARIANTES.md`)*;
   2. **ler o que está instalado no projeto** — lockfile, `.d.ts`, fonte da dependência. Fresco por
      construção, proveniência perfeita, custo de ingestão zero;
   3. **buscar doc ao vivo na hora da tarefa** — escopo da missão, sem estoque;
   4. **cache de pesquisa verificada** — só depois de medir que 1–3 não fecham a lacuna.
3. **Se o cache do item 4 for construído, a forma é esta** (e não um índice do mundo):
   - chave: pergunta normalizada + **pin de versão do pacote** (do lockfile);
   - valor: resposta + fonte + **qual verificador a validou e com que cobertura**;
   - invalidação: pin mudou → entrada morre (não expira por TTL chutado: morre);
   - vazio → cai no caminho de hoje (busca ao vivo). O cache só pode acelerar, nunca degradar.
4. **Dado externo estocado é passivo, não ativo.** Cada fonte ingerida é obrigação de frescor
   perpétua. RAG vencido é pior que RAG nenhum: troca "não sei" por "sei errado". O padrão correto
   já existe no motor para pricing/FX (`composicao_orcamento.py`, snapshot vencido falha fechado);
   o custo de estender isso a N bibliotecas é a razão de não fazê-lo por precaução.

### Onde conhecimento próprio ainda se justifica

Quatro casos onde o gerador comprado é cego e nenhuma busca resolve — aqui dado é nosso ou não
existe:

- **corpus proprietário de domínio** (ex.: `harness-mecanico/corpus/`);
- **contexto de cliente/projeto**, que nunca esteve na web;
- **pós-cutoff que mudou o jogo** — o caso da biblioteca recém-lançada;
- **nossos processos certificados** — que não existem fora do Kortex.

Regra: **construir conhecimento exatamente onde a cegueira do gerador foi medida, em nenhum lugar
a mais.**

### Como decidir sem achismo

Antes de construir o cache: **logar toda consulta de pesquisa com a versão do pacote alvo e medir a
taxa de repetição.** Repetição alta → o cache se paga. Repetição baixa → cada missão pesquisa coisa
diferente e o cache seria infra parada. Uma linha de log responde uma pergunta de arquitetura.

### O `rag.py` de 61 linhas não é dívida

Sobreposição crua de tokens, sem embedding, é a **linha de base honesta**. Não dá para saber se
busca vetorial é necessária antes de medir onde a busca burra falha. Trocar por embeddings agora é
otimizar sem baseline.

---

## 3. Decisão B — Julgamento: o gate é tipado pela pergunta, não só pelo risco

### O achado

`politica.py` já classifica gates por **sensibilidade** (`GATES_SENSIVEIS` nunca é auto-respondido)
e a taxonomia implícita está substancialmente certa:

| gate | o que pergunta | humano é o quê |
|---|---|---|
| `dinheiro`, `autorizacao`, `risco` | **autoridade** | o **responsável** — não o juiz |
| `plano` | **fim / intenção** | a **verdade**. Ninguém mais sabe |
| `cobertura` | **correção** | não deveria ser o juiz — e já não é |

`cobertura` merece nota: o default automático é `escalar`, não `prosseguir`, com o comentário
"um portão que reprova e deixa passar não é portão". Ou seja, o gate de correção **já** foi movido
da mesa do humano para um juiz independente, e o humano só é chamado quando a escalada se esgota.
Isso é a decisão certa, já implementada.

### O que falta

1. **A distinção não está nomeada.** `GateFundador` tem `pergunta: str` e `opcoes: str` em texto
   livre; nada no tipo diz qual das quatro classes acima está sendo perguntada. Gate desconhecido
   cai em manual (fail-safe, correto), mas a classe epistêmica não é dado.
2. **Ninguém mede se o gate carrega informação.** Se o humano aprovou N itens e a taxa de falha
   posterior dos aprovados é igual à dos não-olhados, o gate tem **poder discriminante zero** — e
   isso é mensurável, não uma suspeita. É o detector empírico do risco "gate cerimonial" que o
   `ROADMAP.md` já nomeia e que hoje ninguém consegue observar.

### As regras que ficam decididas

1. **Humano é input externo.** O `CLAUDE.md` global já diz "todo input externo é hostil até
   validado"; a regra vale para o fundador também. Achado de sênior, relatório de pentest e
   observação do dono entram como **hipótese com prior alto, não como veredito**. Prior alto
   significa "testar primeiro", nunca "pular o teste".
2. **Carimbo rápido em gate de autoridade é legítimo.** Gate de dinheiro não existe porque o humano
   julga melhor que a máquina — existe porque alguém tem que ser **responsável** pela consequência.
   Autoridade não requer expertise; requer dono.
3. **Gate de correção sem verificador é sintoma, não solução.** Se o motor precisa perguntar a um
   humano se o algoritmo está certo, falta um verificador. A resposta certa é construir o
   verificador ou falhar fechado — nunca coletar opinião e registrá-la como evidência.
4. **Perguntar o irrespondível envenena o ativo.** Fora da sua faixa de competência o humano não
   devolve silêncio: devolve ruído com selo de aprovação. Numa fábrica cujo ativo composto é
   experiência verificada, uma reprovação legítima carimbada como "aprovado" entra no catálogo como
   processo que funciona. A obrigação de projeto é **tornar a pergunta respondível dentro da
   competência e do orçamento de atenção do humano** — "aprova gastar R$40 nesta correção que muda
   X para Y?" em vez de "revise estas 5000 linhas".
5. **Gosto é a exceção onde o humano é o instrumento** — e n=1 tem variância alta. Registrar a
   incerteza; não tratar como evidência forte. E migrar o que der para correção: contraste WCAG,
   área de toque, quebra em breakpoint e conformidade com os tokens de `docs/design/` são
   validadores determinísticos, não opinião. Isso não produz o bonito; elimina o objetivamente ruim
   antes de gastar a atenção humana.

**Direção geral:** a maturidade do Kortex se mede por **quantas perguntas saíram da mesa do
humano**. Toda pergunta migrada de gosto/correção para verificador é ganho permanente.

---

## 4. Decisão C — Certificação precisa de prazo

Conhecimento consolidado também fossiliza: prática que funcionou pelo motivo errado, regra cujo
contexto original evaporou. "Experiência é conhecimento comprovado" vale **enquanto o mundo que a
comprovou continuar o mesmo**.

Hoje o curador tem promoção (`preparar_promocao_gated`) e não tem **revogação**: não há prazo,
validade nem rebaixamento de certificação em `curador.py`. Um workflow certificado permanece
certificado indefinidamente.

Fica decidido que o catálogo precisa de revogação antes de ser tratado como autoridade — senão a
fábrica de processo vira burocracia por acumulação, que é o risco "gate cerimonial" um nível acima.
A forma (prazo fixo, re-certificação por amostragem, rebaixamento automático por queda de taxa de
aprovação) **não** está decidida: as três têm modos de falha diferentes e nenhuma foi medida.

---

## 5. Onde isto pode dar errado

- **"Comprar o gerador" pode estar barateando demais o problema.** O modelo de fronteira erra
  exatamente onde o Kortex opera: recente, proprietário, específico. Se a cegueira do gerador
  dominar as reprovações reais, a assimetria inverte e conhecimento próprio vira o investimento
  principal. Mensurável olhando *por que* as missões reprovam — não decidível por argumento.
- **A ordem "executar primeiro" depende da premissa bloqueada.** Enquanto o sandbox não estiver
  certificado, "o typecheck pega" é teoria. Se a certificação demorar, ficamos sem os dois
  mecanismos, e investir em retrieval passa a ser o único movimento disponível.
- **Existe classe de erro que verificador não pega e RAG pegaria:** API deprecada que ainda compila,
  padrão idiomático novo, brecha conhecida numa versão. Se essa classe dominar, o item 4 sobe de
  prioridade.
- **Cache de pesquisa envenenado é pior que armazém vencido**, porque carrega o selo "passou no
  verificador". Daí a exigência de registrar *qual* verificador e com que cobertura.
- **Medir o gate cria incentivo perverso.** Cronometrar o operador é Goodhart apontado para dentro
  de casa. Vale como diagnóstico do gate, nunca como avaliação da pessoa.
- **A taxonomia de gates é limpa demais.** "Esta arquitetura é a certa?" é fim, correção e gosto ao
  mesmo tempo; forçar numa classe só empurra decisão importante para a caixa errada. O campo
  provavelmente precisa admitir mais de uma classe.
- **Calibrar aprovação exige resultado posterior atribuível**, que só existe em missão que rodou até
  o fim com veredito. Na prática o instrumento só liga depois do sandbox.
- **Isto pode virar desculpa para tirar o humano do caminho.** "O humano é ruim julgando algoritmo"
  implica "construa o verificador", **não** "o motor decide". Sem verificador, o certo continua
  sendo falhar fechado. A regra pétrea (músculo, não autoridade) não é relitigada aqui.
