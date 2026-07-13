# Arquitetura — superfície MCP da meta-fábrica e a fronteira com o orquestrador/porteiro

> **Para:** Caio + agente do Jarvis + Codex. **De:** Claude (revisão do motor).
> **O que é:** o desenho de como a meta-fábrica vira um **MCP** que o Jarvis consome, e onde
> exatamente fica a linha entre **o que o motor faz** e **o que o orquestrador/porteiro faz**.
> Companheiro de `../handoffs/HANDOFF-CODEX-MOTOR-R3-roadmap.md` (esse é o "como programar"; este é o
> "por que essa forma e onde a fronteira corta").

---

## Princípio que decide tudo

**O motor é a meta-fábrica, e nada além.** Ele fabrica resultado complexo (fan-out,
verificação, síntese) e **expõe seu estado**. Ele mede uso/custo e aplica suas próprias
restrições de spec, mas não concede permissão externa nem fala no nome do dono. Autoridade
organizacional mora **fora** dele — no porteiro do Jarvis e em MCPs especializados (ex.:
finanças). Essa é a tradução fiel de duas
constituições:

- **Jarvis:** "a tranca nunca é o modelo"; dinheiro e identidade são **cláusulas pétreas**;
  o porteiro determinístico é a única tranca.
- **Caio (decisão desta rodada):** classificação dinheiro/identidade **não é concern da
  meta-fábrica** → não entra no código do motor; fica para o orquestrador e o MCP de finanças.

Logo, a meta-fábrica é "músculo, não autoridade". O desenho abaixo mantém **uma única
tranca** (o porteiro) com o motor como executor.

---

## Topologia

```
            ┌─────────────────────────────────────────────────────────────┐
            │                         JARVIS (cérebro pequeno, local)      │
            │  entende intenção → Meta-MCP acha a ferramenta → despacha     │
            │                                                               │
            │   ┌───────────────┐         ┌──────────────────────────────┐ │
            │   │  PORTEIRO      │  decide │  Orquestrador / Roteador     │ │
            │   │  (escada de    │◀────────│  (function-calling)          │ │
            │   │   risco, livro │  gate   └──────────────┬───────────────┘ │
            │   │   de confiança)│                        │  MCP (stdio)     │
            │   └───────┬────────┘                        │                  │
            └───────────┼─────────────────────────────────┼──────────────────┘
                        │ responder_gate (decisão)         │ despachar / status
                        ▼                                  ▼
            ┌──────────────────────────────────────────────────────────────┐
            │                  META-FÁBRICA (motor) — MCP                    │
            │  metafabrica.despachar_missao / status_missao / responder_gate │
            │        └── GerenciadorJobs (durável, SQLite, thread_id) ──┐    │
            │                 └── grafo LangGraph (planner→…→síntese) ───┘    │
            │  expõe gate cru {portao,pergunta,opcoes,lacunas/plano}; não decide │
            └──────────────────────────────────────────────────────────────┘
                        │ (se a missão tocar dinheiro/identidade, é o PORTEIRO
                        │  que roteia — possivelmente a um MCP de FINANÇAS — antes
                        ▼  de devolver a decisão ao motor via responder_gate)
            ┌──────────────────────────────────────────────────────────────┐
            │   MCP de FINANÇAS (futuro, fora do motor) · outros MCPs         │
            └──────────────────────────────────────────────────────────────┘
```

O Jarvis **não** importa o motor nem conhece o LangGraph. Ele vê **só ferramentas MCP**. O
servidor MCP fino (F6 do roadmap) é a fronteira física: do lado de dentro, o `GerenciadorJobs`
e o grafo; do lado de fora, três ferramentas com retorno tipado.

---

## Contrato MCP (a superfície que o Jarvis consome)

O núcleo mutável tem três ferramentas (`despachar`, `status`, `responder_gate`); projeções
read-only podem acrescentar `resumo` e, futuramente, `buscar`. Descrições são **artefato
versionado** — a precisão do roteador depende delas. (As descrições canônicas estão no
roadmap, F6; aqui o contrato de dados.)

### `metafabrica.despachar_missao(objetivo, contexto?, restricoes?) → {job_id, estado}`
Escopo de roteamento: **só** tarefa complexa (multi-passo, verificação adversarial, síntese)
que excede uma resposta direta. Não para pergunta simples nem ação de sistema. Retorna na
hora; execução assíncrona.

### `metafabrica.status_missao(job_id) → {estado, ...}`
`estado ∈ {em_execucao, gate_pendente, concluido, erro}`. Não bloqueia.
- `gate_pendente` → `gate: {portao, pergunta, opcoes, lacunas?, plano?}` **cru**, como saiu do
  `interrupt()`. `gates` expõe todos os interrupts com `decision_id`; `gate` permanece alias
  do primeiro para compatibilidade. O motor não anota classe de risco (ver fronteira).
- `concluido` → `resposta_final` (texto-produto) + `artefatos` (**referências**: nome/tipo/
  caminho/subagente) + `run: {job_id, workspace, log}`. **Sem blobs.**
- `erro` → `{tipo, mensagem}` tratável; o servidor não cai.

### `metafabrica.responder_gate(job_id, decisao, decision_id?) → {estado, ...}`
**Uso interno do porteiro**, não do modelo. Retoma com `Command(resume=decisao)`. A decisão
vem da escada de risco, nunca do julgamento de um modelo (nem do motor, nem do Jarvis).
Quando há múltiplos interrupts, `decision_id` é obrigatório; reenvio idêntico é idempotente e
conteúdo/ID divergente falha fechado.

### `metafabrica.resumo_missao(job_id) → <digest>` (F7 — o "RAG" de conversa)
O orquestrador é pequeno e **não pode ler o `log.jsonl` cru nem os artefatos**. Esta
ferramenta devolve um **digest do tamanho de um modelo**: progresso, marcos selecionados,
gate pendente, 1–3 frases de resposta e **refs** de artefato. É o que responde "como está a
missão X" sem despejar milhares de linhas. **Determinístico, sem banco vetorial** — deriva de
state + log. É a peça que torna a conversa Jarvis↔meta-fábrica viável.

### `metafabrica.buscar(consulta, k?) → [{run_id, trecho, ref, score}]` (F8 — opcional)
Busca **semântica** sobre o histórico de missões concluídas (índice local). Para perguntas
retrospectivas ("já produzimos algo sobre X?"). Indexa só **o que o motor produziu** — não é
a memória pessoal do Jarvis. Construir só quando houver histórico que justifique.

---

## A fronteira do gate (REQ-3, traduzido para a decisão do Caio)

Este é o ponto de maior alavancagem — e onde a linha de escopo corta com mais nitidez.

**O que o MOTOR faz (dentro do escopo):**
1. Quando a cobertura reprova (ou o plano precisa de revisão), o grafo chama `interrupt()`
   com um payload **estruturado** (`portao`, `pergunta`, `opcoes`, `lacunas`/`plano`).
2. O `GerenciadorJobs` **transporta** esse payload para `status_missao = gate_pendente`.
3. Aceita a decisão de volta em `responder_gate` e retoma. Fim. **O motor não interpreta o
   gate.**

**O que o motor NÃO faz (fora do escopo — orquestrador/porteiro + finanças):**
- **Classificar** o gate em `rotina` / `dinheiro` / `identidade`. Quem mapeia
  `portao → classe de risco` é o **porteiro** do Jarvis, usando sua escada de risco e seu
  livro de confiança. O motor conserva uma defesa local mínima: `promocao` é gate sensível
  e nunca é auto-respondido; `plano` e `cobertura` não são sensíveis no contrato atual.
- **Aplicar a cláusula pétrea** (dinheiro/identidade nunca autônomos). Isso é regra do
  porteiro: ele simplesmente **nunca** chama `responder_gate` automaticamente para uma classe
  pétrea — exige confirmação do dono e, se for dinheiro, pode consultar o **MCP de finanças**
  antes. O motor não precisa "saber" disso.
- **Substituir o hard-stop de `teto_custo`.** O motor já mede `modelo.uso`/`custo.tick`, mas
  S4 ainda não é sustentado: não há reserva/hard-stop antes de chamada, retry ou failover.
  H12b pertence ao motor porque `teto_custo` é contrato da spec; porteiro/finanças podem
  impor limites adicionais, não substituir esse enforcement. Ver
  `../specs/001-hardening-producao/plan-h12b.md`.

**Por que essa divisão é segura:** o motor expõe **tudo** que um gate carrega (o payload já é
estruturado), então o porteiro tem o que precisa para classificar e decidir. Nenhuma decisão
de permissão "vaza" para dentro do motor. Mantém-se **uma única tranca**.

**Consequência para o `--auto` do motor:** auto-resposta só vale para gates não sensíveis.
`promocao` falha fechado mesmo com `auto_mode`, override ou default. Quando o chamador é o
Jarvis, o porteiro continua responsável por classes organizacionais adicionais e por nunca
automatizar dinheiro/identidade.

---

## Modelo de execução (por que job durável e não-bloqueante)

- Uma missão leva minutos e pode pausar num gate por tempo indefinido. O loop do Jarvis não
  pode ficar preso num `input()` nem segurar a thread → **despachar retorna na hora**, o
  acompanhamento é por `status`.
- Durabilidade: `thread_id` do **chamador** é a chave; `SqliteSaver` em `motor.db` é o default
  do caminho de serviço. Outbox SQLite com claim/lease/ack reconcilia decisões depois de
  restart. A entrega é **at-least-once** e efeitos externos precisam deduplicar por
  `decision_id`; não há promessa de exactly-once entre stores.
- O LangGraph já devolve controle no `interrupt()`; o `GerenciadorJobs` roda `invoke()` em
  thread de fundo e lê `__interrupt__` para saber se é `gate_pendente` ou `concluido`. Sem
  Caixa, sem `input()`.

---

## Memória e dados (REQ-6) — a fronteira da fronteira

- A saída entra na memória do Jarvis como **dado de trabalho**, no **cofre difuso** (busca),
  nunca no cofre exato de segurança. Isso é decisão do Jarvis; o motor só **devolve referências**
  (`artefatos` + `run.job_id`), não despeja blobs.
- **Conteúdo produzido pelo motor é dado, nunca instrução** ao modelo do Jarvis. O orquestrador
  trata `resposta_final`/artefatos como payload, não como comando. (Defesa de prompt-injection.)
- Correlação: `job_id` == `thread_id` casa a memória do Jarvis com `runs/<run_id>` + `log.jsonl`
  do motor.

---

## Segurança da chamada (REQ-7) — o que toca o motor e o que não

| Item | Onde mora | Ação no motor |
|------|-----------|---------------|
| Chaves de provedor (se nuvem) | Keychain do macOS → injetadas como env pelo host MCP | Motor só lê `os.environ`. **Não** hardcode, **não** acessa Keychain. |
| Prompt injection | Porteiro/orquestrador | Motor trata missão e retornos como dados (já é assim). |
| Cláusulas pétreas (dinheiro/identidade) | Porteiro + MCP de finanças | **Nada** no motor. |
| Rodar sem credencial de produção solta | Host/deploy do MCP | Motor não guarda credencial; recebe env por invocação. |
| Comando autônomo | Runner externo certificado | Default `DenyCommandRunner`; C2/C3 indisponíveis sem H05b real. |

---

## Decisões travadas (não relitigar)

1. **Forma da superfície:** servidor MCP **fino** embrulhando o `GerenciadorJobs` + grafo
   (não um "agente orquestrador" pesado dentro da meta-fábrica). O agente orquestrador é o
   **do Jarvis**, do lado de fora. Espaço deixado para evoluir, mas a rodada R3 entrega o
   servidor fino.
2. **Gate sempre sobe cru ao chamador;** classificação e cláusula pétrea ficam no porteiro.
   O motor não conhece `dinheiro`/`identidade`.
3. **Escopo do motor = meta-fábrica.** Finanças, permissão, memória de segurança, escada de
   risco: tudo fora.
4. **A validação humana é preservada, não removida.** O MCP só troca o *canal* da resposta
   ao gate (de "editar markdown no vault" para "Jarvis traz e leva"). O motor continua
   dependendo do fundador: o gate sempre espera (parado de forma durável), `--auto` fica
   desligado no caminho de serviço, o `GerenciadorJobs` nunca auto-resolve. "Não-bloqueante"
   = o motor estaciona e devolve o controle, **não** = anda sozinho.
5. **Retomada é at-least-once.** O reconciliador fecha perda após crash, mas não transforma
   efeitos em stores distintos em exactly-once; consumidores deduplicam por `decision_id` e
   callers fecham explicitamente o `GerenciadorJobs`.

## Em aberto para o Caio (se quiser decidir antes de o Codex chegar na F6)

- **Nome do servidor/entrypoint:** sugiro `python -m motor.mcp_servidor` e prefixo de
  ferramenta `metafabrica.*`. Confirmar o prefixo (o roteador do Jarvis versiona a descrição,
  então o nome importa).
- **`thread_id`: quem gera?** Sugiro: o **Jarvis** fornece e reusa (dá a ele a chave de
  correlação de memória); o servidor gera um `uuid4` só se vier vazio. Confirmar.
