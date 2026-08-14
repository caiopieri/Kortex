# PLANO DE CAMPANHA — fechar as dívidas do motor

> Plano de execução das dívidas registradas em `INVARIANTES.md`. Este documento é o
> **estado da campanha**: quem faz, qual é o critério empírico de pronto, e o que já caiu.
> Ler ANTES de `INVARIANTES.md` — lá está o que é verdade sobre o motor, aqui está o que
> vamos fazer a respeito e em que ordem.
>
> Se você é uma sessão nova: comece pela seção "Como operar", depois vá para a primeira
> caixa não marcada. Não confie na sua memória de conversa; confie nas caixas.

---

## Como operar

**Divisão de trabalho, decidida pelo fundador em 2026-08-13:**
Claude **planeja, despacha, verifica e revisa**; o agente de codificação (`Codex #2` no
canvas do Maestri) **escreve o código**. Claude só encosta em código quando (a) é perigoso,
ou (b) o agente produziu código ruim. Ciclo: planejar → despachar → verificar → `/clear` no
agente → repetir.

**Despacho:** `maestri ask "Codex #2" '<briefing>'`. Briefing que funciona traz contexto,
restrições inegociáveis e **critério de sucesso empírico**. Quando há mais de uma leitura
razoável, pedir o JULGAMENTO ANTES do código e exigir que ele apresente as leituras em vez
de escolher em silêncio — é o que rende as melhores contribuições dele.

**Verificação — nunca aceitar "green" auto-reportado, de agente nenhum:**
1. Reproduzir o comando eu mesmo, em estado limpo.
2. Provar que o teste novo não é vazio: `git stash push -- <fontes>` revertendo SÓ o
   código-fonte e mantendo os testes; o teste tem que reprovar.
3. Comparar artefato por AST, não por impressão.
4. Conferir a premissa dele ANTES de contestar (já quase reverti decisão correta por
   premissa minha errada).
5. Exigir que ele JULGUE o veredito que recebe, não só reporte — ele já passou adiante
   falso positivo de evaluator sem marcar como tal.

**Regra de medição (custou um dia inteiro para ser descoberta):** rodar a suíte completa
**UM DE CADA VEZ por checkout**. `motor/__main__.py` abre o `log.jsonl` da raiz sob flock
exclusivo; duas suítes — ou dois agentes no mesmo repositório — se contaminam e produzem
conjuntos de falha diferentes. Handshake herdado, literal: *"antes de rodar a suíte
completa, me avise e espere. Eu faço o mesmo."* Se o gate der 7 falhas, desconfiar disso
ANTES de desconfiar de regressão.

**Gate completo, de `motor/`:**
```bash
python3 -m pytest -q
python3 -m ruff check motor tests
python3 -m mypy motor
python3 -m bandit -r motor -q --severity-level high --confidence-level high
python3 -m compileall -q motor tests
```

**Baseline em 2026-08-14 (commit `4883203`, Onda 1 fechada):** 1152–1153 passam, **3 falham
fixas** (E-01/E-02/E-03), 35 pulados, **mais até UMA falha rotativa da família de
concorrência**. As 3 fixas caem conforme a campanha avança, e cada onda declara o número
novo esperado.

**O baseline não é um número exato, e isso é medido, não desculpa.** Duas suítes completas
consecutivas no mesmo checkout deram uma falha de concorrência cada, em teste DIFERENTE, as
duas verdes isoladas — `test_hardening_h11::...persiste_decision_id_e_ack` e
`test_servico::...renova_claim_sem_segundo_writer`. Causa raiz é a dívida 12 (o caminho de
resposta escreve, então corrida legítima devolve `ServicoOcupado`/`transitorio`), e os
testes aceitam menos desfechos do que a corrida produz. **Regressão é:** uma 4ª falha fora
dessa família, uma 5ª qualquer, ou qualquer falha determinística (que reprova isolada).
Antes de chamar de regressão, RODE O TESTE ISOLADO — se passar sozinho e for de
`servico`/`hardening_h11`, é a família, não o seu diff.

*Baseline anterior, para histórico:* 1150/6 em 2026-08-13 (`81831fc`).

---

## Fatos operacionais vivos

- **FX RECAPTURADO em 2026-08-14T13:17Z** (`ask` = 5.21128, versão
  `awesomeapi-usdbrl-2026-08-14`), nos quatro `cfg-*.json`. **VENCE 2026-08-15T13:17Z** —
  janela de 24h, e vence todo dia. Se a data de hoje passou disso, recapture ANTES de
  qualquer coisa; nenhuma missão real roda com FX vencido.
  Comando: `curl -s https://economia.awesomeapi.com.br/json/last/USD-BRL` → `cotacao_venda`
  = campo **`USDBRL.ask`** (venda = ask; `bid` é compra e SUBFATURA). Use o
  **`timestamp` da própria API** como `capturado_em`, não o relógio local: é quando a
  cotação valeu, e snapshot no futuro é recusado pelo motor.
  *Como verificar que funcionou, porque "o JSON é válido" não prova nada:* compor com
  relógio real (`compor_orcamento_omniroute(cfg, workspace)`, com `OMNIROUTE_API_KEY`
  qualquer no ambiente, pois o check de credencial vem ANTES do de FX e curto-circuita) e
  rodar o **controle negativo** — o FX antigo tem que continuar sendo recusado. Sem o
  controle negativo, um gate quebrado dá o mesmo "aceitou" que um snapshot fresco.
- **PRICING VENCE 2026-08-17T00:00Z.** `PRICING_CAPTURADO_EM = 1786320000`, janela de 7
  dias. Vencido, o motor **recusa arrancar**. Ninguém vivo no projeto reconferiu esses 19
  preços — vieram de antes da sessão anterior. Reconferir é manual contra
  `openrouter.ai/models`, e o campo `vendor` é code-owned junto.
- **Custo em BRL é PREÇO-SOMBRA.** As rotas atuais são OAuth de assinatura e não vão na
  fatura. O teto existe para pegar loop, não para controlar dinheiro real. Rotas
  `auth_type: apikey` (nvidia, gemini, groq, cerebras, alibaba, openrouter...) **são**
  dinheiro real se houver cobrança.
- **Nada foi enviado ao GitHub**, por decisão do fundador. Branch `refatoracao-painel`.

---

## ONDA 0 — tempo-crítico (antes de 2026-08-17)

- [x] **Dívida 7 — fixture de pricing com bomba-relógio.** FECHADA em 2026-08-13, commit
      `e4d28d6`. Medida antes de corrigir: a +10 dias eram 16 falhas (as 6 da auditoria +
      10 de pricing). Corrigida injetando `relogio=lambda: PRICING_CAPTURADO_EM` nos dez
      chamadores afetados, com o FX congelado junto (snapshot no futuro é recusado pelo
      motor). Verificado com plugin próprio, não com o do executor: revertendo só o diff
      dele a bomba volta; suíte a +1 ano dá 1150/6.
- [ ] **Reconferir os 19 preços de `PRECOS`** contra os catálogos, ou aceitar
      conscientemente que o motor para em 17/ago. *Dono:* fundador decide; pesquisa manual.

## ONDA 1 — portões que não porteiam (spec/kernel)

**ONDA FECHADA em 2026-08-14.** Melhor retorno por linha do repositório: cada um deixava
passar coisa que o contrato diz que não passa.
*Esperado ao fim:* 6 falhas → 3. *Obtido:* 3 fixas + até 1 rotativa de concorrência — ver
a nota de baseline abaixo, que é o resultado mais importante desta onda depois dos três
consertos.

- [x] **A-03** — FECHADO 2026-08-14, commit `102f95c`. `NonBlank` em `rubrica` e
      `criterios_cobertura`, escopo estreito de propósito.
- [x] **A-04** — FECHADO 2026-08-14, commit `5ee8c76`. A leitura estreita (exigir que
      `valida` aponte para id existente) **já estava no código** desde sempre em
      `spec.py:177` — só não rodava fora do `tipo: validador`. O que faltava era recusar
      `valida`/`validador` em nó que não é validador.
- [x] **A-05** — FECHADO 2026-08-14, commit `4883203`. Runtime reexecuta `ConfigContem`
      em vez de fazer clamp. Fechou três buracos, não um: `min: 0`, `min > len(requer)`
      (o clamp por cima) e `requer: []`, que também era aprovação incondicional.

*Onda 1 fechada.* Medição que a fechou: com o diff **1152 passam / 4 falham**; revertendo
SÓ `spec.py` e `grafo.py` com `git stash push` seletivo e mantendo os reprodutores,
**1149 / 7** — os três voltam a reprovar, então o diff é o que os segura.

**A quarta falha não é regressão, e virou achado próprio.** Uma falha de concorrência por
rodada, em teste DIFERENTE a cada rodada (`test_hardening_h11::...decision_id_e_ack` com o
diff, `test_servico::...sem_segundo_writer` sem ele), sempre verde isolado. O traceback que
faltava para a dívida 14d foi capturado: `ServicoOcupado` / `transitorio: True` onde o teste
só aceita `EstadoInvalido` — **fail-closed**, motor certo, teste enumerando menos desfechos
do que a corrida produz. Ver dívida 14d reclassificada e dívida 12 (causa raiz).
**Consequência para o baseline:** "1150/6" nunca mais é número exato. O baseline é
1152–1153 passando com 3 falhas fixas (E-01/E-02/E-03) **mais até uma falha rotativa da
família de concorrência**. Uma 5ª falha, ou uma 4ª fora dessa família, é que é regressão.

## ONDA 2 — ledger e eventos

Mais arriscada que a Onda 1: mexe no caminho append-only que sustenta E2, o invariante do
qual toda auditoria depende. Onda separada de propósito.
**ONDA FECHADA em 2026-08-14, com E-02 recusado por decisão do fundador.**
*Esperado ao fim:* 3 falhas fixas → 0. *Obtido:* **1160 passam, 1 falha — só o E-02**, que
não é defeito e sim contrato mantido de propósito. Nesta rodada a rotativa de concorrência
não apareceu; ela continua prevista pelo baseline. **São TRÊS itens, não quatro** — o A-06
já estava fechado, ver abaixo.

⚠️ **A ARMADILHA DESTA ONDA:** "quarentenar" é sinônimo de "tirar do log". O conserto
estreito do E-02 — quarentenar o arquivo inteiro, ou truncar na última linha válida — deixa
o teste verde APAGANDO auditoria: no primeiro caso tudo, no segundo todas as linhas boas
*depois* da corrompida. Qualquer proposta aqui tem que dizer o que acontece com as linhas
boas anteriores, as posteriores, a continuidade de `seq`, e como se distingue linha
corrompida de linha escrita por versão mais nova do schema.

- [x] **E-01** — FECHADO 2026-08-14, commit `364ae50`. Lock duplo: sidecar (identidade
      lógica do path através de `replace`) **e** flock no inode do log (identidade física),
      ordem fixa, ambas revalidadas antes de cada escrita. O conserto óbvio — trocar sidecar
      por flock-no-log — derrubaria `h07c::test_sidecar_impede_split_brain_apos_replace`,
      porque inode não é identidade estável. Três testes novos para o risco real, que era
      inicialização parcial vazando lock e trocando split-brain por deadlock de processo.
- [x] **E-03** — FECHADO 2026-08-14, commit `544d11a`. O buraco era maior que o enunciado:
      `self._evento(...)` é `ast.Attribute` e o ramo de Attribute só aceitava
      `attr == "evento"`, então **15 callsites** de `modelos.py` eram invisíveis, inclusive
      os com string constante. Agora resolve domínio finito e mantém coleção de
      não-resolvidos que a asserção exige vazia. 56 tipos fixados.
- [ ] **E-02 — NÃO SERÁ FEITO. Decisão do fundador em 2026-08-14: manter o contrato H07.**
      Não é defeito isolado, é colisão de contrato. `h07b.py:93-113` exige que
      `[linha válida][linha completa não-JSON][sufixo parcial]` levante sem quarentena; o
      reprodutor exige que `[linha válida][linha completa não-JSON]` **não** levante e
      quarentene. Os dois primeiros elementos são idênticos — diferem só por um write
      interrompido no fim. Separar tecnicamente ("recupera se o lixo for exatamente uma
      linha completa e nada depois") foi **recusado**: aceitar o caso menos benigno e
      recusar o mais benigno é incoerente como propriedade de segurança.
      **Custo aceito e declarado:** log com linha corrompida fica permanentemente
      inemitível — o job morre para sempre, fail-closed.
      *Proposta arquivada, para quando houver motivo* (desenho do Codex #2, que também
      recomendou não implementar sem formalizar a exceção): quarentena durável com hash
      **antes** de qualquer escrita; evento de recuperação ocupando `seq` e registrando
      offset, tamanho, motivo e hash dos bytes retirados; troca atômica de inode;
      idempotência pós-crash pelo hash; toda linha boa preservada byte a byte, anterior
      **e** posterior; recuperação só para falha sintática de framing/UTF-8/JSON — JSON
      bem formado com schema desconhecido é versão futura, não corrupção, e não se toca.
- [x] **A-06 — JÁ ESTAVA FECHADO. Medido em 2026-08-14; a dívida 9 estava errada, e este
      plano repetiu o erro.** A leitura herdada era "o gate mostra 6 e a dívida lista 7
      porque o A-06 é invisível com `jsonschema` instalado — verde por acidente de
      ambiente". **Falso nos dois lados.** (i) O fallback fraco não existe mais:
      `grafo.py:492-499` reprova fechado com motivo próprio (`"schema_json indisponivel:
      jsonschema ausente no ambiente"`), e o comentário no lugar registra o raciocínio —
      portão que não consegue checar reprova, não aprova com menos rigor. (ii) A dependência
      **está declarada**, em `pyproject.toml:19`, com comentário citando o A-06 como motivo.
      *Como foi medido, já que "rodar a suíte" não responde:* plugin de `sys.meta_path` fora
      do repo bloqueando o import (mesmo princípio do plugin de relógio da dívida 7 — o
      motor não pode ganhar uma chave para fingir o próprio ambiente). Com o bloqueio ativo,
      6/6 passam e `grafo.JsonSchemaValidationError is None`, ou seja o motor estava
      genuinamente em modo fallback. **O instrumento foi conferido antes da leitura**: sem
      essa checagem, um plugin que não bloqueia nada produz exatamente o mesmo "6 passed".
      *Lição:* o gate mostrava 6 porque são 6. O número certo nunca precisou de explicação.

## ONDA 3 — Fase 1: moeda de contenção para rota grátis

Gargalo declarado pelo fundador. `PRECOS` tem 19 modelos code-owned e `modelo not in PRECOS`
reprova fechado, então NVIDIA/DeepSeek/GLM/Gemini-free/Alibaba não executam.
**Preço zero é PROIBIDO:** silencia a única contenção monetária e faz o ledger mentir. Para
rota grátis o escasso não é dinheiro — é cota e disponibilidade.

Desenho fechado (ver `kortex-fase1-moeda-de-contencao` na memória):
- moeda é **TOKEN**, não requisição (requisição por janela é taxa, e taxa é disponibilidade,
  que é do OmniRoute);
- **um arquivo de banco por moeda** (`orcamento.sqlite3` / `cota.sqlite3`), mesma classe e
  mesmo código durável — zero migração no caminho do dinheiro;
- tabela de rota grátis **code-owned e com `vendor`**, senão reabre em silêncio o buraco que
  impede executor e verifier "independentes" serem o mesmo modelo por dois prefixos;
- teto de token vem da config do **operador**, nunca da spec (o planner ecoa default de
  Pydantic — foi o defeito do S7);
- tabela de rota grátis tem **janela de frescor**: provedor cortar free tier é o espelho do
  snapshot de preço velho.

- [ ] **1-pré — medir o corpo HTTP de uma rota grátis por provedor.** A medição herdada veio
      do `call_logs` do OmniRoute, que prova que o PROXY contou token — não que o provedor
      devolve `usage` no formato que `omniroute_orcado._brl()` lê. **A moeda-token inteira
      depende disso.** Alibaba popula usage (deepseek-v3.2, glm-5.2, kimi-k2.7-code); NVIDIA
      é desconhecido para texto; 61 zeros da alibaba não estão explicados.
      *Bloqueado por:* FX vencido (Onda 0).
- [ ] **1a** — moeda paramétrica na criação do schema + arquivo separado, comportamento BRL
      idêntico. Inclui o **guard obrigatório que reprova entrada de `PRECOS` com preço zero**
      — sem ele a decisão vive só em prosa.
- [ ] **1b** — tabela code-owned de rota grátis (modelo → vendor + classe de cota), cotação
      em token, mesma checagem vendor × provider_id, fail-closed para modelo fora das duas
      tabelas.
- [ ] **1c** — `chamar_orcado` resolvendo sessão **por moeda** ao longo da cadeia de
      failover. É o nó real: hoje ele chama `sessao(...)` uma vez, antes da cadeia, com um
      teto só — e executor grátis com verifier pago é o caso NORMAL, não a borda.
      *Refutação a vigiar:* se aparecer código que assume "uma sessão por run" de um jeito
      que dois arquivos quebrem, o desenho muda para migração paramétrica.

## ONDA 4 — evidência que não se mantém

O motor sabe **produzir** evidência e não sabe **manter** evidência. Camada mais perigosa
porque aqui o sistema parece funcionar.

- [ ] **Dívida 5 — revogação de certificação.** Há promoção; não há prazo, re-certificação
      nem rebaixamento. U2 prova que a certificação NASCE honesta; nada prova que CONTINUA.
      A forma é indecidida (prazo fixo, re-certificação amostrada, rebaixamento automático
      por decaimento) e nenhuma foi medida — **exige spec minha antes de código**.
- [ ] **Dívida 6 — gate humano não é medido.** Aprovação carimbada sem leitura é
      indistinguível de aprovação deliberada no ledger, e entra na evidência com o mesmo
      peso. Tratar aprovação como predição e medir poder discriminante contra o resultado
      posterior. **Exige spec minha antes de código.**

## ONDA 5 — operação

- [ ] **Dívida 12 — `status()` escreve.** `_status_duravel` drena o outbox, e drenar é
      escrita. F4 consertou o contrato de erro, não o desenho. O dono do relay deveria ser
      quem já tem o writer do job. Não foi feito porque mover o relay sem redefinir ponto de
      recuperação e ordem de publicação pode dessincronizar estado e ledger.
- [ ] **Dívida 4 — saúde do reconciliador** exposta e lifecycle explícito.
- [ ] **Dívida 14a** — `provedor_de` não resolve no caminho orçado: a nota do gate de plano
      mostra `modelo: ?` e o humano aprova sem ver qual modelo roda cada subagente.
- [ ] **Dívida 14b** — fallback de papel não declarado em `compor_orcamento_omniroute` não
      emite evento: papel digitado errado roteia como executor **em silêncio**.
- [ ] **Dívida 14c** — o planner cria rotineiramente nó de fecho em `fan_out_sintese`, onde
      tudo roda em paralelo e o nó nunca vê a saída dos outros. Numa run ele inventou
      taxonomia e rebaixou um `NAO ATENDE` para `NAO SEI`.
- [ ] **Dívida 14d** — `test_retomada_longa_renova_claim_sem_segundo_writer` intermitente e
      **NÃO CLASSIFICADO**: 0/16 num diagnóstico dedicado, reprovou em duas verificações
      independentes. Sem o traceback não se afirma fail-open nem fail-closed. *Primeiro
      passo é capturar o traceback*, não consertar.
- [ ] **Aberto novo (2026-08-13)** — `responder_gate` chama `_gates_duraveis` ANTES do
      fallback de `status()`, e ela abre o log do job: log genuinamente corrompido levanta
      `ValueError` cru para o chamador, exceção nua na mesma API que o F4 garantiu devolver
      erro estruturado. Mesma família do F4, um degrau acima.
- [ ] **Dívida 15a (2026-08-14)** — `GateFundador` declarado e nunca executado. `spec.py:153`
      tem `gates: list[GateFundador]` e nenhum ponto de `motor/*.py` lê `spec.gates`. Uma
      spec pode declarar portão humano que o motor jamais abre, e validar. Mesma classe do
      A-04, um nível acima: lá o campo era do subagente, aqui é do workflow. **Decidir
      primeiro se o campo deve executar ou deve sumir** — não sair implementando.
- [ ] **Dívida 15b (2026-08-14)** — `Subagente` sem `model_config`, herdando `extra="ignore"`
      do pydantic, enquanto `ConfigContem`/`ConfigComando`/`Validador*` todos usam
      `extra="forbid"`. Campo digitado errado é descartado em silêncio. Raio de explosão real:
      pode reprovar spec que hoje passa, então **medir contra `exemplos/*.json` antes**.
- [ ] **Dívida 15c (2026-08-14)** — `ConfigContem` aceita `requer` com termos repetidos.
      Medido: `_validar_contem('so um X aqui', {'requer':['X','X'],'min':2})` → `True`.
      Sobrevive ao A-05, porque `len(requer)` não deduplica. Fecha igual
      `ConfigComando._modulos_sem_duplicatas`.
- [ ] **Dívida 15d (2026-08-14)** — `contem` é substring casefold sem fronteira de token:
      `'auth' in 'unauthorized'` aprova. O validador determinístico mais usado do motor
      confunde presença de conceito com presença de sequência de caracteres. **Não é
      conserto óbvio** — fronteira de token quebra termo com pontuação (`aresta.fluxo`,
      `custo.tick` aparecem em spec real). Precisa de decisão de contrato antes de código.
- [ ] **Dívida 15e (2026-08-14)** — o guard anti-drift **não enxerga emissor injetado**.
      `curador.py` recebe `emitir_evento: Callable[[str, Any], None]` e emite por ele em 3
      callsites; nenhum casa os padrões do guard. **`curador.py:404` emite de um `IfExp`** —
      domínio finito, resolvível, e o guard nunca chega lá. É a classe do E-03 viva em
      outro emissor, na forma mais perigosa: emissor não reconhecido é **invisível**, não
      "não-resolvido", então escapa da coleção que a asserção protege. Fechar exige decidir
      o que conta como fronteira de emissão, não só melhorar o resolvedor.
- [ ] **Dívida 15f (2026-08-14)** — o guard varre só `motor/motor/*.py`.
      `scripts/experimento_especialista.py:61` emite `modelo.uso` fora da varredura.
- [ ] **Dívida 15g (2026-08-14)** — a asserção é de uma direção só: prova
      `emitidos - declarados == ∅`, nunca o inverso. **8 dos 64 tipos declarados** não são
      emitidos por nada em `motor/motor/`. Quatro são os `curador.*` do item 15e; os quatro
      **`custo.*` (`reservado`, `reconciliado`, `bloqueado`, `contrato_violado`) não são
      emitidos por NADA em produção** — só por `test_hardening_h12b0.py`. Têm schema de
      payload completo e participam da lógica de `eventos_schema.py:565-566`. Ou o ledger
      durável deveria emiti-los e não emite, ou é superfície morta prometida a quem consome
      o log. As duas leituras são ruins; nenhuma foi verificada. **Medir antes de consertar.**

## TRILHA BLOQUEADA — não é trabalho de agente de codificação

- [ ] **Dívida 1 / C2 / C3 — sandbox real.** Precisa daemon Linux dedicado, imagem por
      digest, output por streaming e cleanup causal. **Toda evidência de `execucao` produzida
      até hoje carrega a ressalva de que Docker Desktop no macOS não é o runner que a spec
      exige.** *Bloqueado por:* Fase 0 (VPS ARM na Oracle; cadastro deu problema).
      Runbook pronto em `RUNBOOK-VPS-FASE-0.md`; ARM já foi provado antes de existir VPS.
- [ ] **Dívida 11 — CLI não roda duas missões.** Correção óbvia (log por run) quebra
      `motor_painel/painel.py`, que lê `BASE.parent / "log.jsonl"` hardcoded, e a branch
      atual é a da refatoração do painel. **Decisão do fundador, não refactor local.**
- [ ] **Dívida 3 — backend autoritativo do curador.** U3/K4 falham fechado sem
      `RepositorioCertificacoes` real. É infraestrutura, não protocolo.
- [ ] **Dívida 2 — duas rotas certificadas de verdade** e dimensionar o teto para a reserva
      conservadora.
- [ ] **Dívida 8 — independência declarada, não observada.** Fecha com atestação de upstream
      por resposta, ou **tirando um papel do proxy** (verifier falando direto com um vendor,
      credencial própria). Auto-fallback é a feature de vitrine do gateway, então a quebra
      seria silenciosa e por desenho.
- [ ] **Dívida 13 — auto-consistência ≠ conformidade.** A superfície pública ainda diverge
      entre runs. Fechar pinando nome a nome faria a spec virar a implementação e o motor
      deixar de gerar para transcrever; a linha certa não foi achada. *Precisa de runs, não
      de código.*
- [ ] **Validar que o portão de processo TRANSFERE.** 9 das 13 runs foram a mesma missão do
      eBay; contrato por chamada canônica, auto-consistência ≠ conformidade e "ambiguidade
      vira taxa de defeito" repousam num exemplo só. Uma missão de outro domínio confirma ou
      revela que é artefato daquele caso. *Bloqueado por:* FX vencido.

---

## Registro do que caiu

- [x] **Dívida 14e** — `responder_gate` preservando qualquer erro de `status()` estava sem
      teste. Fechada em 2026-08-13, commit `81831fc`:
      `test_responder_gate_preserva_erro_terminal_em_vez_de_estado_invalido`. Removida a
      preservação, o motor devolve `EstadoInvalido`/"job não está em gate_pendente" para um
      job que morreu com `ValueError` — afirmação falsa sobre o estado.
- [x] **Onda 1 inteira** — A-03 (`102f95c`), A-04 (`5ee8c76`), A-05 (`4883203`), fechadas em
      2026-08-14. Codex #2 escreveu, verificação independente aqui: diff lido linha a linha,
      suíte rodada neste checkout com o lock tomado, e prova de carga por reversão seletiva
      (1149/7 sem o diff → 1152/4 com ele). O commit de A-03 foi medido ISOLADO antes do de
      A-04, para provar que fechava o próprio achado sem fechar o vizinho por acidente.
- [x] **Onda 2** — E-03 (`544d11a`) e E-01 (`364ae50`) fechadas em 2026-08-14; E-02 recusado
      por decisão do fundador, com o custo declarado. Gate rodado aqui com o lock tomado:
      **1160 passam, 1 falha (só E-02)**. Painel e CLI conferidos por mim porque trava é
      território da dívida 11: `parse_eventos` lê normalmente sob flock exclusivo (advisory)
      e o segundo writer é recusado.
- [x] **A dívida 15e caiu da verificação, não do plano** — conferindo o commit do E-03,
      medi que 8 dos 64 tipos declarados não são emitidos em `motor/motor/` e fui atrás do
      porquê. O guard reportava "0 não resolvidos" enquanto `curador.py` emitia por um
      callback injetado que ele não reconhece — inclusive um `IfExp` em `curador.py:404`.
      Emissor não reconhecido é invisível, não não-resolvido: a métrica de completude do
      próprio guard não detecta o buraco dele.
- [x] **A dívida 14d saiu de "não classificado"** no mesmo trabalho, sem ter sido o alvo: o
      traceback que faltava apareceu na falha rotativa, e classifica como **fail-closed**.
      Não estava previsto no plano; caiu porque a suíte foi rodada duas vezes seguidas com
      e sem o diff, e a comparação mostrou o teste mudando de nome entre as rodadas.
