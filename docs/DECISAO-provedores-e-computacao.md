# DECISÃO — Provedores e computação

> Quem serve o poder de processamento, e o que o Kortex é dono de saber sobre isso.
> Registrado em 2026-08-07. Complementa `DECISAO-conhecimento-e-julgamento.md` e a regra pétrea
> "músculo, não autoridade". **Isto é direção, não estado.**

---

## 1. A pergunta

O dono tem várias assinaturas e créditos ao mesmo tempo — Claude, OpenAI, Gemini, OpenRouter,
NVIDIA, Modal, AWS, Azure, Oracle. A pergunta foi: o Kortex deve **orquestrar todos** por conta
própria, ou deve ter **uma entrada de provedor padrão** e deixar quem quiser plugar um agregador
externo (OmniRoute) nessa entrada?

A resposta depende de separar duas coisas que a pergunta juntava.

---

## 2. Inferência e computação não são o mesmo problema

| | **Inferência** | **Computação** |
|---|---|---|
| O que é | token entra, token sai | "roda este container, me dá exit code + artefatos" |
| Estado | sem estado, fungível | filesystem, rede, GPU, tempo |
| Padrão de fato | **existe** (`/v1/chat/completions`) | **não existe** |
| Quem já agrega bem | OmniRoute, OpenRouter, LiteLLM | ninguém, para o requisito do Kortex |
| Exemplos do dono | Claude, OpenAI, Gemini, NVIDIA | Modal, AWS, Azure, Oracle |

**Decisão: alugar a inferência, ser dono da computação.**

### 2.1 Inferência — não construir gateway

Existe padrão de fato e o motor **já tem o plugue**: `ClienteOpenAICompat` alcança NVIDIA, Ollama,
OpenRouter, Together e Groq mudando só `base_url`; OmniRoute entra pelo mesmo buraco. Não há o que
construir — há o que configurar.

Construir cliente para N provedores é manutenção infinita de quirks de API, OAuth, quota e rate
limit; é commodity; e é literalmente o risco "reinventar o control-plane" do `LEIA-PRIMEIRO` §9.

### 2.2 Computação — construir, porque ninguém resolveu

O requisito do Kortex para executar comando não é "rode barato". É **"rode de um jeito que eu
consiga atestar"**: isolamento real, imagem pinada por digest, limite de output, timeout, cleanup
determinístico de árvore de processos (`motor/specs/001-hardening-producao/sandbox-conformance.md`).
Nenhum broker genérico de computação entrega isso pronto.

A costura já existe e é de uma linha:

```python
class CommandRunner(Protocol):
    def run(self, request: CommandRequest) -> CommandResult: ...
```

`DenyCommandRunner` (default) e `DockerSandboxRunner` são implementações. **`ModalSandboxRunner`
seria a terceira**, e o kernel não precisa saber a diferença. Não é refatoração: é preencher um
plugue desenhado para isso.

**Modal como candidato ao bloqueio nº 1:** container isolado, imagem por digest, cobrança por
segundo, efêmero por construção, GPU sob demanda, e não é a máquina do dono. É a lista da
conformance. Se passar, C2/C3 saem de ⚠️ e **o motor passa a rodar o que escreve** — o que destrava
a alça experiência→conhecimento inteira. **Pré-requisito inegociável:** ler `sandbox-conformance.md`
contra a documentação do Modal *antes* de escrever código. Egress controlável, limite de output por
streaming e cleanup determinístico são os pontos que decidem.

**A mesma camada serve à fábrica de especialistas.** Fine-tuning, destilação e eval de held-out são
consumidores de computação com GPU. O runner que certifica execução de comando é a mesma primitiva
que torna V6 (`EVOLUCAO.md`) operável sem infra nova. Isso não antecipa V6 — só evita construir
duas camadas de computação.

---

## 2.3 Topologia: o Kortex não é um container — o trabalho é

- **Motor** — processo longevo com estado durável (`motor.db`, `log.jsonl`, livro-razão) e as
  credenciais. Roda no host ou como serviço.
- **Runner** — container **efêmero por comando**, sem rede, rootfs read-only, não-root, imagem por
  digest, workspace montado.

O motor **não pode** ser o sandbox: ele guarda credencial e estado durável, e um sandbox com os
privilégios do motor não isola nada. Empacotar o motor em container para *distribuição* é legítimo,
mas então ele fala com o daemon do host para criar containers irmãos — caminho conhecido de
escalonamento de privilégio, a decidir explicitamente e não por acidente.

### Duas restrições que o código já impõe

**`--network none`.** Dependência não se instala em runtime; tudo vem da imagem. Cada dependência é
decisão no momento de construir a imagem. Isso é rigidez proposital e é o que torna o resultado
reprodutível — mas **não cobre teste de integração nem chamada de API**, que são parte de "entregar
software".

**Decisão:** a conformance passa a admitir **duas classes de isolamento**, não uma:

| Classe | Rede | Uso | Evidência |
|---|---|---|---|
| **Selada** | `none` | build, teste unitário, lint, type-check | `execucao` plena |
| **Egress restrito** | allowlist explícita de destino | teste de integração, chamada de API | `execucao` **com ressalva de rede na proveniência** |

Nunca egress livre. A classe usada entra no carimbo — o operador vê em que isolamento a prova foi
obtida.

**`--mount type=bind,src={workspace}`.** Bind mount é local: `CommandRequest.workspace: Path` assume
filesystem da mesma máquina. **Um runner remoto não monta o diretório do host.**

**Decisão para backend remoto:** volume persistente no provedor, sincronizado por run — não
upload/download por comando. Sobe/desce a cada `pytest` transforma a alça de verificação em algo lento
demais para ser usado, e sandbox lento é sandbox desligado. **Medir o tamanho real do workspace antes
de escolher** é pré-requisito, e se o sync por run também for proibitivo, o backend remoto não serve
para a alça de teste — serve só para trabalho pesado (§2.4).

## 2.4 Três formas de computação — só uma existe

| Forma | Contrato | Para quê | Evidência que gera | Estado |
|---|---|---|---|---|
| **Comando** | `argv` → exit code, timeout curto | build, teste, lint | `execucao` **de graça** — o exit code é o veredito | `CommandRunner`, não certificado |
| **Trabalho** | submeter → poll → artefatos; horas, GPU | fine-tuning, destilação, render | só com grader (eval em held-out) | não existe |
| **Sessão** | processo vivo, comandos e observação contínua | FreeCAD, ComfyUI, browser, simulador | **nenhuma naturalmente** | não existe |

**Trabalho não passa por `run()` síncrono** — travaria o grafo por horas. **Decisão:** modelar como
submeter → checkpoint → retomar, a mesma mecânica do gate do fundador aplicada a um job. A retomada é
idempotente por identificador de job, sob o mesmo contrato de durabilidade do outbox monetário
(claim/lease/ack, entrega ao menos uma vez, deduplicada). Isso **não** é "só usar o `interrupt()`":
provedor que cai no meio, job órfão e reconciliação são a mesma classe de problema que o H11 levou
meses para fechar, e o custo deve ser orçado assim.

**Sessão é classe de isolamento própria e mais fraca** — display, rede, GPU, filesystem gravável. Sua
evidência nasce mais fraca e **isso vai no carimbo**, nunca escondido. Sessão não produz `execucao`
por si só.

## 3. O cérebro de roteamento já existe; falta a classe de capacidade

"O Kortex identifica que precisa de algo, vê que tem provedor que roda aquilo, e vai" **já é** o
invariante S3: `capacidades_requeridas` não vazia é requisito estrito, e o roteador escolhe o
executor **mais barato que cobre todas** as capacidades. Falha fechada sem cobertura. O fallback é
o `auto_esgotar` (failover por custo), já implementado.

O que falta: hoje capacidade descreve só **habilidade de modelo** — nos exemplos versionados,
`redacao`, `codigo`, `analise`, `raciocinio-longo`. Não há vocabulário para `gpu`, `container`,
`armazenamento`, `rede-egress`. Um nó não consegue declarar "preciso de uma GPU por 40 segundos" e
deixar o roteador achar o Modal.

**Decisão:** estender capacidade de "o que o modelo sabe" para "**o que a rota consegue
executar**", mantendo o requisito estrito e o fail-closed. É aditivo e respeita "a spec é a
dinâmica, o grafo é fixo".

**Guarda:** capacidade de modelo é declarativa e barata de checar. Capacidade de computação tem
quota, região, cold start e disponibilidade de GPU. Se o roteador precisar **consultar
disponibilidade em tempo real** para decidir, ele deixa de ser função pura sobre config e vira
orquestrador de recurso — inchaço de kernel proibido pela regra pétrea. A consulta viva, se for
necessária, mora na casa/control-plane, acima do motor.

---

## 4. Atestação de rota: agnóstico sobre quem serve, nunca sobre saber quem serviu

O instinto de "não se apegar a nenhum provedor" está certo, com um ajuste de uma palavra. A
liberdade é sobre **quem serve**; a evidência depende de **saber quem serviu**.

### O problema concreto, hoje

`exemplos/cfg-omniroute.json` roteia **todos os papéis** — executor, verifier, evaluator,
synthesizer, planner — pelo mesmo proxy. `validar_independencia_orcada` aprova porque `vendor`
(code-owned) e `route_id` diferem na config.

O `vendor` code-owned fecha um buraco real: o mesmo Opus servido por duas assinaturas (`claude/` e
`agy/`) não conta como dois julgamentos. O que ele **não** fecha, e o docstring de
`omniroute_orcado.py` já diz com todas as letras, é o proxy reescrever o roteamento por baixo.

E a feature de vitrine do agregador é *auto-fallback entre centenas de provedores em milissegundos*.
Ou seja: **o comportamento que dá valor ao gateway é exatamente o que quebraria a independência
executor↔verifier em silêncio.** Não é defeito dele; é o propósito dele colidindo com o invariante
central do Kortex. Hoje o teste prova que a config **declara** independência; nada prova que ela
**acontece**.

### A decisão

Rota passa a ter **nível de atestação**, e o painel já tem a metade difícil disso: `Conexoes.jsx`
modela `tem_credencial` com três estados e se recusa a colapsar "não" com *"não verificável —
transporte desconhecido"*.

| Rota | Atestação | Pode ser |
|---|---|---|
| Vendor direto, credencial própria | verificável | **verifier** · alimenta o curador · promoção |
| Agregador opaco (OmniRoute e afins) | declarada | **executor** · volume barato · evidência carimbada mais fraca |

**Não bloquear — carimbar.** É o mesmo padrão de `cobertura_de_evidencia`
(`execucao`/`estrutural`/`opiniao`): a máquina já sabe dizer "esta prova é mais fraca". Um sistema
que não roda por excesso de rigor não gera evidência nenhuma.

Duas ações que convertem promessa em evidência:

1. **Atestação por resposta.** Se o agregador expõe qual provedor de fato atendeu, registrar no
   evento e comparar com o `provider_id` declarado; divergência falha fechada. Se ele **não** expõe,
   isso é a informação decisiva: a independência é estruturalmente inverificável enquanto os dois
   papéis passarem por lá.
2. **Tirar ao menos um papel do proxy.** Verifier falando direto com um vendor, credencial própria.
   Custa uma credencial e fecha o bloqueio nº 2 de verdade, não no papel.

### O que não trazer do agregador

- **Compressão de prompt** (engines de compressão com perda). Quebra reprodutibilidade — o
  `reproducer-manifest.jsonl` e o corpus endereçado por conteúdo assumem replay, e o ledger
  registraria "executor recebeu P" quando o modelo recebeu `comprime(P)`. Pior: U4 exige titular e
  candidato sobre os **mesmos** casos; compressão adaptativa faria o selo MAC (U5) carimbar uma
  comparação que não foi maçã com maçã.
- **A contabilidade de custo do agregador** — já rejeitada e corretamente: o header observado vinha
  `0.0000000000`. Custo sai do `usage` do corpo contra tabela code-owned.
- **Catálogos grandes de ferramentas MCP em bloco.** Ferramenta é superfície de autoridade. Se
  entrar, entra na camada das casas, uma de cada vez, com allowlist — nunca dentro do motor.

---

## 5. Resumo da posição

**O Kortex é dono da identidade, do custo e do roteamento por capacidade. Não é dono do
transporte.** Uma conexão declara: capacidades (o que consegue executar), identidade/vendor
code-owned, modelo de custo conservador e nível de atestação. Uma das implementações é "endpoint
OpenAI-compatível" — e por ela entram OmniRoute, OpenRouter, NVIDIA, Ollama e assinaturas próprias
sem código novo.

A opção "plugar um agregador externo como um provedor" **é** a arquitetura certa, desde que ele
entre como uma conexão de tier baixo entre várias, e não como *a* porta de entrada.

## 6. Sequência

1. `ModalSandboxRunner` contra `sandbox-conformance.md` — bloqueio nº 1, plugue existente.
2. Tirar um papel do proxy — bloqueio nº 2 de verdade.
3. Capacidade estendida para computação.
4. Tier de atestação por rota, alimentando o carimbo de evidência.
5. Só então a tela de conectar provedores (OAuth, quota, saúde). É a parte visível e a menos urgente.

Itens 1–3 aproveitam tudo que o dono já paga, aplicado onde ninguém resolveu por ele — em vez de
reimplementar o que já está resolvido.

## 7. Onde isto pode dar errado

- **Modal pode não passar na conformance.** Egress controlável, limite de output por streaming,
  cleanup determinístico e imagem por digest são requisitos específicos; se faltar um, o item 1
  morre e volta a ser problema de runner Linux dedicado. Ler a spec contra a doc do Modal é uma hora
  de trabalho que decide o trimestre — e é pré-requisito, não etapa.
- **Sandbox em nuvem de terceiro é outra fronteira de confiança.** O código gerado passa a rodar em
  infra alheia com credenciais no ambiente. Para código autoral do dono, aceitável; no dia em que o
  Kortex rodar código de cliente, vira decisão de compliance.
- **Crédito promocional não é fundação.** Construir dependência estrutural sobre crédito que expira
  é hipoteca. A abstração precisa aguentar o provedor sair — argumento a favor de fazer a camada de
  conexão direito e contra otimizá-la para um provedor específico.
- **Capacidade de computação pode não ser aditiva** como o §3 supõe, pelo motivo do próprio guarda:
  se exigir consulta viva de disponibilidade, muda de natureza e não cabe no kernel.
- **Carimbar em vez de bloquear pode virar porta dos fundos.** Se todo mundo escolher a rota barata
  não-atestada porque "é só um carimbo mais fraco", o sistema converge para evidência fraca em todo
  lugar e o tier vira decorativo. O carimbo precisa ter consequência — no mínimo, veto de promoção
  e de alimentação do curador.
- **Nada disto ataca o gargalo real**, que continua sendo rodar uma missão de ponta a ponta. Há uma
  leitura honesta em que o certo é fazer só o item 1, rodar uma missão, e deixar 2–5 esperarem o que
  a missão ensinar.
