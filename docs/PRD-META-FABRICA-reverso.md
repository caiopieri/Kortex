# PRD (reverso) — Meta-fábrica

> **Modo reverso / auditoria.** Este PRD foi reconstruído a partir do código + docs canônicos
> atuais (não escrito top-down). Onde os docs divergem do código, o **código é a verdade** e a
> divergência vira item da seção "Lacunas". Serve de estrela-guia para fatiar em specs/handoffs
> e de base para red-team.
> Fonte: `docs/LEIA-PRIMEIRO.md`, `docs/ROADMAP.md`, `motor/docs/EVOLUCAO.md`, `LOG-VERIFICACAO.md`.
> Data do retrato: 2026-07-03.
>
> ⚠️ **Retrato datado — não é o estado atual.** Este documento é um instantâneo de auditoria e
> **não foi reescrito**: seus números (48 eventos, suíte ~292) e sua leitura de maturidade valiam
> naquela data e hoje são falsos. Mantido como registro, não como estrela-guia. Para o estado
> corrente use `LEIA-PRIMEIRO.md` §5, `../motor/specs/001-hardening-producao/verification.md` e
> `../motor/docs/INVARIANTES.md`. Decisões posteriores que mudam este PRD:
> `DECISAO-conhecimento-e-julgamento.md` (2026-08-07) e `DECISAO-provedores-e-computacao.md`
> (2026-08-07). Antes de fatiar spec a partir daqui, reconstrua o retrato.

## Problema
Construir artefatos intelectuais complexos com IA (software, specs, design, pesquisa, patente)
hoje é: (a) **inconsistente** — um chat único alucina, perde contexto, não prova o que entrega;
(b) **caro e opaco** — sem medir custo/qualidade por papel não dá pra alocar bem nem baratear;
(c) **não cumulativo** — cada tarefa recomeça do zero, nada vira especialista reutilizável.
A meta-fábrica ataca os três: fabrica **com maestria** (qualidade verificada) e fica **cada vez
mais barata e segura** (eficiência medida). Função-objetivo do sistema: **minimizar
tempo-até-decisão do humano e retrabalho.**

## Quem usa
O dono (Caio) como fundador/operador de uma "fábrica" de agentes; e, no futuro, produtos
externos (Jarvis, Flint) que consomem a meta-fábrica via MCP. A primeira vertical é **software**
— não por acaso: é onde a evidência é mais barata de verificar (compila, testa, lint, SAST),
o melhor terreno pra provar as primitivas antes de generalizar.

## O produto — capacidades, em ordem de importância

1. **Motor (kernel).** Roda UM processo (UM artefato) com maestria: grafo LangGraph **fixo** que
   interpreta uma **WorkflowSpec dinâmica** (a spec é o dado; o grafo não muda por feature).
   Padrão `fan_out_sintese` + rota `grafo_dependencias`. Verificação adversarial por subagente,
   avaliador de cobertura, **gate do fundador** (`interrupt()`), jobs duráveis (SQLite
   checkpointer), telemetria JSONL event-sourced.
2. **Loop de auto-correção (Fase C).** Três pilares juntos: **prevenção** (rota de dependência em
   ondas — cada etapa vê a anterior), **escalada de tier** (subtarefa difícil reprovada sobe de
   degrau e converge), **reconciliação na fonte** (o avaliador nomeia o nó culpado; o motor
   re-dispara ele + dependentes até o gate aprovar ou bater o teto).
3. **Validadores determinísticos (V1).** Gates verificáveis por máquina (`schema_json`, `contem`,
   `test`) — passa/falha por algoritmo, não por opinião de LLM. **É o diferencial "Enforced
   Outcomes":** a fábrica *impõe* resultado, não só opina. Reprovação re-dispara o alvo via
   reconciliação.
4. **Roteamento provider-agnóstico + resiliência.** `ClienteOpenAICompat` (NVIDIA/Ollama/
   OpenRouter/Together/Groq — só muda `base_url`), `ClienteCodex`, `ClienteOpenCode`,
   `ClienteClaudeCLI`. Roteamento por papel/tier/pin/capacidade; **failover por custo**
   (`auto_esgotar`). Trocar de provedor = editar JSON, não reescrever código. Catálogo em escada
   (free → Codex → Claude no topo).
5. **Curador / flywheel (fundação completa, read-only).** Observador (telemetria → perfil),
   telemetria por modelo, **propositor por slot** (ranqueia modelo por papel/tier, com piso de
   qualidade, ciente de travas/timeouts), e **livro-razão de custo** (tokens + tempo + $ real).
   É o cérebro de medição e alocação — torna "vale a pena?" uma conta de ROI.
6. **Camada de conhecimento (RAG).** Nó consome `fonte_rag`, recebe bloco "CONTEXTO RECUPERADO"
   antes de produzir. **Lift de RECUPERAÇÃO provado com régua honesta (medidor v3, 2026-07-04)**:
   a evidência v2 caiu (tautologia + baseline ruído), a régua foi refeita — fatos não-adivinháveis,
   3 braços, execução isolada em tempdir — e bateu o critério pré-registrado (SEM RAG 1/5 ·
   irrelevante 0/5 · relevante 5/5; codex/gpt-5.4-mini). **Síntese: não medida.** Ver `LOG-VERIFICACAO.md`.
7. **Superfície MCP + eventos tipados.** `metafabrica.despachar_missao / status_missao /
   responder_gate / resumo_missao / eventos`. Esquema de 48 eventos tipados (`eventos_schema.py`,
   guard anti-drift) que instrumenta tudo e destrava a interface viva.
8. **Interface própria (aspiracional, em design).** A superfície de 1ª classe que **vê** a fábrica
   rodando e intercepta. Brief v2 travado em `docs/design/`.

## Arquitetura em camadas (a decisão que organiza tudo)
Fractal, da mais profunda à mais externa: **Motor** (kernel: roda um artefato) < **Casas/harness**
(control-plane: org-chart, orçamento, coordenação; a softwarehouse = dev-harness) < **Interface
própria** (vê e opera). Consumidores externos (Jarvis, Flint) usam via MCP — relação unilateral.
**Regra pétrea: o motor é músculo, não autoridade** — não decide permissão, risco, dinheiro nem
identidade; isso mora fora (porteiro/Jarvis + MCPs). A meta-fábrica é **autossuficiente**: não
depende de nenhum produto externo.

## Anti-escopo (o que NÃO é)
- **O motor não é autoridade.** Não classifica risco, não move dinheiro, não fala pelo dono.
- **Não inchar o kernel.** Orçamento/org-chart/permissão moram nas casas (reusar Paperclip lá),
  nunca dentro do motor.
- **Não é o Paperclip 2.** Compra-se a commodity (control-plane) e constrói-se a diferenciação
  (motor + curador/flywheel).
- **Jarvis e Flint são projetos separados**, não dependências.
- **Não cobre largura sobre profundidade.** Casas novas (hardware, mecânica) e especialistas de
  CAD são Later — fé, não engenharia, até o flywheel provar UM especialista ponta a ponta.
- **Não dá checklist/to-do a um nó** — o grafo já é o organizador; melhorar entrega = retrieval,
  não auto-organização.

## Sucesso (critérios falsificáveis)
- Uma missão real fecha com `cobertura` indo de **reprovado → aprovado** sem intervenção humana
  além dos gates. ✅ atingido.
- Validador determinístico distingue saída boa de ruim de forma reproduzível (não satura). ✅.
- RAG dá **lift de recuperação medível** sobre corpus que o base ignora. ✅ **provado (medidor v3, 2026-07-04)** — a evidência v2 caiu, a régua v3 (fatos não-adivinháveis, 3 braços, tempdir isolado) bateu o critério pré-registrado numa config. Síntese: ❌ não testada.
- Trocar de provedor sem tocar em código (só JSON). ✅.
- Livro-razão atribui **$ estimado por modelo/papel** (tabela de preço manual, sem reconciliação vs fatura → tendência, não valor exato — item 15 red-team), permitindo comparação de alocação. ✅ (com ressalva).
- **Meta ainda aberta:** UM especialista pequeno bate o generalista em custo **e** passa no gate
  em tarefa real, com o loop treina→avalia→aloca→monitora fechado e gate-seguro. ❌ não atingido
  (é o norte de longo prazo).

## Restrições
- **Gate antes de flywheel**: sem avaliador objetivo não se treina nem se afirma "pequeno ≈
  grande". A régua é o gargalo.
- **Só dado gate-verificado treina** (anti-collapse); âncoras de ouro pra detectar deriva.
- **Conhecimento antes de peso**: RAG + ferramentas primeiro; fine-tune é o último 10%.
- **Imposto de complexidade**: toda peça nova paga com ganho real em qualidade, custo ou
  segurança, senão fica no Later.
- **Inerte-por-default / falsificável-primeiro**: extensão entra atrás de flag/registro sem
  quebrar a suíte; cada passo tem critério de falha barato antes de virar fundação.
- **Catálogo federado, não armazém**: dados = ponteiros + metadados com proveniência/licença.

## Estado atual (retrato honesto — 2026-07-03)
**Já funciona (validado, não aspiracional):** motor v0.5 + Fase C completa; validadores
determinísticos V1; roteamento provider-agnóstico + failover por custo; curador (observador +
propositor com custo real + livro-razão); RAG (encanamento + lift de recuperação provado no
medidor v3, 2026-07-04; síntese não medida); 48 eventos tipados + superfície MCP. Suíte ~292 verde.
(Ver `LOG-VERIFICACAO.md`.)
**Aspiracional (desenhado, não construído):** interface viva própria; curador que **age** (fatia
3 — sombra + certificação antes de mudar catálogo); fábrica de especialistas (fine-tune/destilação
governados); casas além da softwarehouse; data-house (aquisição de dataset, repo separado —
**despausada 2026-07-04**, no Next como semente); ponte física.

## Capacidades-alvo validadas manualmente hoje (o protótipo "Maestri")
O dono opera hoje, **à mão**, um arranjo (Maestri + monitor Python + Antigravity) que prototipa o
alvo da meta-fábrica. Vale mapear, porque valida a tese e mostra o que o motor já cobre vs. o que
falta:
- **Terminais que se comunicam sozinhos** (Claude Code ↔ Codex, um comanda o outro) → é o
  **control-plane / coordenação entre agentes** que na meta-fábrica é o grafo + as casas.
- **Monitor reagenda quando um agente bate o limite** (continua no reset) → mapeia para
  **resiliência / `auto_esgotar` / failover** do motor (hoje troca de modelo; a versão "esperar o
  reset" é uma política de retry a mais).
- **Um terminal dá qualquer comando em outro** (de `clear` pós-spec a trocar de modelo) → é
  **roteamento/controle de execução** — na meta-fábrica, decisão da casa/orquestrador, não do
  kernel.
- **Delegar tarefa aos free via opencode** → já é **`ClienteOpenCode` + roteamento por custo**.
- **Antigravity gera áudio/vídeo/imagem (Google) com limites altos via prompt certo** → é uma
  **capacidade multimodal por trás de um cliente/ferramenta** — na meta-fábrica entraria como um
  `ClienteX`/ferramenta MCP roteável por capacidade (`modelo.roteado_ferramentas`), com o prompt
  correto como parte do papel.
Este arranjo é **momentâneo** e faz um subconjunto do que a meta-fábrica fará — mas já entrega
muito e serve de banco de provas do caso de uso. A meta-fábrica generaliza: grafo tipado +
verificação + curador + evidência, em vez de orquestração manual.

## Lacunas / inconsistências (achados de auditoria)
- **Docs vs. estado:** o `LEIA-PRIMEIRO.md` (dado 2026-06-29) lista como "em curso/aspiracional"
  coisas **já entregues** depois: validadores determinísticos V1, eventos de superfície, RAG com
  lift, propositor com custo real. → atualizar o §5/§6 do LEIA-PRIMEIRO (o retrato mente se ficar
  velho). *(Este PRD já reflete o estado novo.)*
- **Interface:** o brief de design (v2) referencia eventos que o motor emite; o próprio brief teve
  o contrato de eventos corrigido em 2026-07-03. Manter o brief e `eventos_schema.py` sincronizados
  (a fonte-da-verdade é o schema).
- **Antigravity/multimodal:** capacidade real usada à mão, **sem** cliente/rota correspondente no
  motor ainda. Se vira alvo, precisa de um `Cliente`/ferramenta + roteamento por capacidade.
- **Política "esperar reset de limite":** o monitor do Maestri faz; o motor hoje faz failover por
  troca de modelo, não espera-e-retoma. Gap pequeno, aditivo, se for desejado.
- **Curador só observa:** propõe mas não age (fatia 3 pendente) — a alocação ainda é decisão
  humana no gate.

## Suposições (a validar)
- Software é mesmo a vertical de grader mais barato pra provar o flywheel primeiro. (Alta
  confiança.)
- O RAG dá lift real em corpus que o base ignora — **recuperação provada numa config** (medidor
  v3, 2026-07-04). Segue suposição: generalizar pra outros modelos/corpora externos (data-house)
  e a claim de **síntese** (combinar conhecimento, não só recuperar).
- Um especialista pequeno **pode** bater o generalista em custo+qualidade numa tarefa estreita —
  hipótese central do longo prazo, ainda **não** provada.
