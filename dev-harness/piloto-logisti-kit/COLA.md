# COLA — passo a passo literal do piloto (primeira vez com spec-kit)

> Siga de cima para baixo. Cada bloco diz: o que digitar, o que vai acontecer,
> e o que VOCÊ precisa fazer. Não pule as PARADAS.

---

## PASSO 1 — Terminal (sem IA ainda)

```bash
mkdir -p ~/Desktop/Projects/logisti && cd ~/Desktop/Projects/logisti && git init

uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
specify init . --integration claude

# copia o kit preenchido (este diretório) para o repo
cp ~/Desktop/Projects/Orquestrador/dev-harness/piloto-logisti-kit/AGENTS.md .
echo "@AGENTS.md" > CLAUDE.md
mkdir -p docs
cp ~/Desktop/Projects/Orquestrador/dev-harness/piloto-logisti-kit/discovery.md docs/
cp ~/Desktop/Projects/Orquestrador/dev-harness/piloto-logisti-kit/telemetria.md docs/
cp ~/Desktop/Projects/Orquestrador/dev-harness/piloto-logisti-kit/ROADMAP.md .
cp ~/Desktop/Projects/Orquestrador/dev-harness/docs/security-DoD.md docs/

git add -A && git commit -m "chore: bootstrap piloto — spec-kit + harness (AGENTS, discovery, roadmap)"
```

O que acontece: `specify init` cria a pasta `.specify/` e os comandos `/speckit.*`
dentro do Claude Code. O resto é o seu harness entrando no repo.

**Leia o `docs/discovery.md` antes de seguir.** Eu preenchi — se discordar de algo
(dor, hipótese, fora-de-escopo), edite AGORA. É o seu único documento de decisão.

## PASSO 2 — Abrir o Claude Code no Kimi

```bash
export ANTHROPIC_BASE_URL=<url-do-seu-proxy-kimi>
export ANTHROPIC_API_KEY=<chave-do-proxy>
claude
```

Digite: `que modelo você é?` → tem que responder como Kimi/proxy. Se responder
"Claude", o proxy não pegou — feche e confira as env vars. NÃO siga gastando seu limite.

## PASSO 3 — Constitution (você NÃO precisa responder nada criativo)

Digite `/speckit.constitution` e cole o bloco abaixo na mesma mensagem.
O agente vai ESCREVER o arquivo de constitution sozinho — seu papel é só conferir
no fim que os 6 princípios estão lá.

```text
Crie a constitution com estes princípios e seções, governando spec, plan, tasks e implement:

PRINCÍPIO I — Ambiente sobre modelo (NÃO-NEGOCIÁVEL). O agente é um otimizador local sem
estado. Qualidade vem do contexto, não de "esforço" do modelo. Specs e planos são a fonte da
verdade; quando o requisito muda, edita-se a spec, nunca se improvisa no código.

PRINCÍPIO II — Escopo é lei. Toda spec declara escopo dentro E fora explícitos. O agente não
infla a tarefa. Over-engineering é violação: a abstração que ninguém pediu não entra.

PRINCÍPIO III — Tier define o rigor. T0 (spike): sem gate. T1 (MVP): segurança inegociável +
teste no caminho crítico. T2 (produção): gate completo. Este projeto é T1.

PRINCÍPIO IV — Teste pragmático (NÃO-NEGOCIÁVEL em T1+). Teste no caminho crítico é
obrigatório; test-first para lógica de negócio, test-after para UI/cola. O agente NUNCA
apaga ou edita teste para fazê-lo passar. Cobertura é sinal, não meta.

PRINCÍPIO V — Ceticismo ancorado. Toda proposta termina com "Onde isto pode dar errado",
avaliado contra a spec e a verdade externa — nunca contra o que o usuário quer ouvir.

PRINCÍPIO VI — Spec à prova de executor barato. Toda tarefa declara o tier do executor.
Executor barato: interfaces fixadas, arquivos a tocar listados, critérios de aceitação
executáveis (testes), proibido editar testes, ambiguidade escala ao planner — nunca se decide
design por conta própria. Tarefa de design aberto sobe de tier, não desce.

SEÇÃO — Security Requirements: validar todo input; autorização (não só autenticação) em cada
rota; zero segredo no código; erro não vaza interno; queries parametrizadas. Supabase/Postgres:
RLS ligada em toda tabela com dado de usuário; policies testadas (transportadora A não lê dados
da B); service_role só no servidor.

GOVERNANCE: a constitution supera qualquer preferência. Todo plano e revisão verificam
conformidade. Complexidade precisa ser justificada. O orquestrador (humano) revisa o plano e o
diff; validação não é delegável.
```

→ Anote a linha "constitution" na `docs/telemetria.md`.

## PASSO 4 — Specify (cole exatamente isto)

```text
/speckit.specify Fatia "Central de documentos da frota" do Logisti, conforme
docs/discovery.md e ROADMAP.md (item Now). O quê: dono de transportadora de caminhões
cadastra seus caminhões (placa, modelo, ano; campo modal fixo em "caminhao") e seus
motoristas (nome, CNH, validade da CNH); caminhões têm documentos com data de vencimento
(licenciamento, seguro); um painel lista tudo que vence nos próximos 30 e 60 dias com
status ok/vencendo/vencido (incluindo CNHs). Inclui autenticação simples (1 conta =
1 empresa) porque o isolamento por RLS depende disso. Por quê: o usuário 0 (3 caminhões,
controle manual) é pego de surpresa por vencimentos — validar que ele adota e MANTÉM o
sistema atualizado (hipótese do discovery). Tier T1. Fora do escopo: tudo listado na
seção 5 do docs/discovery.md — em especial outros modais, custos e viagens.
Esta sessão tem executor de tier barato: siga o PRINCÍPIO VI da constitution — não
tome decisões de design implícitas; em ambiguidade, pergunte antes.
```

O que acontece: ele cria um branch e um `spec.md`. Leia o spec por alto: o escopo
bate com o discovery? Inflou? Se inflou, responda apontando o corte.

## PASSO 5 — Clarify (aqui ELE te faz perguntas — é normal)

Digite: `/speckit.clarify`

O agente faz até ~5 perguntas de múltipla escolha sobre vãos da spec. Como responder:
- A resposta estiver no discovery → responda de lá (ele deveria ter lido; aponte).
- For detalhe de produto que você sabe → responda direto. Sugestões prontas:
  campos do caminhão: placa, modelo, ano (capacidade/eixos só se o tio pedir — YAGNI);
  motorista: nome, CNH, validade; documentos: licenciamento e seguro, cada um com data
  de vencimento; status: vencido (< hoje), vencendo (≤ 30 dias), atenção (≤ 60), ok;
  pode perguntar pro seu tio o que ele anota hoje — resposta dele > nossa suposição.
- Você não souber e parecer importante → me cole a pergunta aqui no Cowork que eu respondo.
- Parecer fora de escopo → "fora do escopo desta fatia, registre como assunção".

## PASSO 6 — Plan + ⛔ PARADA OBRIGATÓRIA

Digite: `/speckit.plan`

Quando terminar, NÃO digite o próximo comando. Abra o `plan.md` gerado e:
1. Confira contra o AGENTS.md (stack certa? domínio puro em src/domain? RLS no schema?).
2. Confira escopo (só a fatia? nada de roteirização/financeiro?).
3. **Me cole o plano aqui no Cowork** — review premium custa minutos de token e é o
   ponto de maior alavancagem. Eu devolvo aprovado-ou-corrija.
Só depois de aprovado: siga.

## PASSO 7 — Tasks → Analyze → Checklist (sequência direta)

```
/speckit.tasks
/speckit.analyze
/speckit.checklist
```

`analyze` apontando inconsistência P1 = volta ao plan (não "deixa pra depois").
Anote cada fase na telemetria.

## PASSO 8 — Implement

Digite: `/speckit.implement`

Regras durante: ele NÃO edita testes para passar; tarefa que ele errar 2-3x você anota
na telemetria (seção Escalações) e deixa para Sonnet depois — siga com as outras.
Ao final: `npm run lint && npm test` têm que passar.

## PASSO 9 — ⛔ PARADA: seu diff review + fim

```bash
git add -A && git diff --staged   # leia de verdade, com o AGENTS.md do lado
git commit -m "feat: cadastro de frota (fatia 1) — piloto Rota Forja regime barato"
```

Preencha o fim da `docs/telemetria.md` (kill criteria + veredito) e me traga o
resultado — eu fecho a auditoria e atualizo o status da rota (L0 → L1 ou diagnóstico).

---

## Se algo travar

- Comando `/speckit.*` não existe → o `specify init` não rodou nesta pasta; repita o Passo 1.
- Kimi se perder/alucinar comandos → `/clear` e recomece a fase atual (artefatos ficam salvos em arquivos; você não perde nada commitado).
- Dúvida em qualquer parada → me cole aqui. Perguntar custa quase nada; retrabalho custa caro.
