# HANDOFF — Motor R3: superfície de serviço + extensões de ferramenta (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR. Spec travada. **Não relitigar.**
> Interface FIXADA, testes a montante como DoD, ambiguidade ESCALA (`## DÚVIDAS`).
> Pré-requisito: suíte atual VERDE. Rode `python3 -m pytest -q` antes de começar e anote o número de testes.
> **Ordem é obrigatória:** as fases dependem umas das outras (F1→F2→F3→F4→F5→F6). Faça na ordem.

---

## De onde veio este handoff

Dois agentes deixaram requisitos ao motor, validados contra o **código real**:

- **Harness mecânico** → `Orquestrador/Harness Mecânico/02-REQUISITOS-AO-MOTOR.md` (MR-1..MR-5).
- **Jarvis** → `Orquestrador/Jarvis/docs/REQUISITOS-METAFABRICA-para-jarvis.md` (REQ-1..REQ-7).

Claude revisou cada pedido contra `motor/grafo.py`, `__main__.py`, `caixa.py`, `spec.py`,
`politica.py`, `registro.py`, `modelos.py` e decidiu o que muda, o que é novo e o que fica
**fora do escopo do motor**. Este doc é o resultado executável.

### Fronteira de escopo (decisão do Caio — travada)

> O motor é a **meta-fábrica**, nada além. **Não se mexe no motor em nada que não seja
> concern da meta-fábrica.** Em particular, a classificação de gate em
> `dinheiro`/`identidade` e a regra de cláusula pétrea (REQ-3) **NÃO entram no código do
> motor** — moram no **orquestrador/porteiro** do Jarvis e num **MCP de finanças** futuro.
> O motor apenas **expõe o gate fielmente** (já estruturado) para quem o consome decidir.

O que o motor faz por causa do REQ-3 é só **deixar o gate chegar ao chamador como evento
estruturado e aceitar a decisão de volta** (isso cai naturalmente das fases 4 e 6). A
classe de risco e a recusa-de-auto ficam descritas em `ARQUITETURA-MCP-e-orquestrador.md`,
não aqui.

### Princípio do gate humano (travado — NÃO remover a dependência do fundador)

> **Não-bloqueante ≠ autônomo.** Toda esta rodada **preserva** a validação humana do motor.
> O objetivo do MCP é só **mudar o canal** pelo qual o Caio responde o gate — de "abrir o
> motor e editar markdown no vault" para "o Jarvis traz o gate e leva a resposta de volta".
> O motor **continua dependendo do Caio**.

Concretamente, isto é lei para todas as fases:
- O gate **sempre espera** a decisão humana. Sem decisão, a missão fica parada de forma
  **durável** (SQLite) por tempo indefinido — não anda sozinha.
- O `--auto` do motor (gates auto-resolvem) **fica desligado por default** e **não é usado**
  pelo caminho de serviço/MCP. O `GerenciadorJobs` (F4) **nunca** auto-resolve gate.
- "Não-bloqueante" quer dizer: o processo do chamador não trava num `input()`; o motor
  **estaciona** no gate e devolve o controle. A decisão ainda é 100% do fundador.

Cenário-alvo (é exatamente o que F4+F6 entregam):
`status_missao` → `gate_pendente {pergunta, opcoes}` → Jarvis verbaliza → Caio decide em
linguagem natural → Jarvis chama `responder_gate(job_id, decisao)` → motor retoma do ponto.

**O caminho MANUAL continua existindo (aditivo, não substituto):** a CLI
(`python -m motor "..."` + `input()`) e a Caixa do fundador (`--caixa`, editar a nota no
vault) **permanecem intactas e funcionais**. O MCP é um **canal a mais** de responder o
gate, não uma troca. O Caio pode decidir na mão (CLI/vault) OU pelo Jarvis — as duas
superfícies leem/retomam o **mesmo** estado durável (`motor.db`). Nenhuma fase pode quebrar
ou depreciar o caminho manual; os testes de `caixa.py`/CLI ficam verdes.

### Duas trilhas independentes (pedido do Caio)

Os pedidos têm origens diferentes e **não dependem entre si**. Execute na trilha que
interessa primeiro:

- **Trilha JARVIS** (a que importa pra conversar com a meta-fábrica): **F3 → F4 → F5 → F6 → F7**
  (e **F8** opcional). É a camada de borda (job durável + MCP + digest); o núcleo do motor
  fica intacto.
- **Trilha HARNESS** (independente, veio do agente de mecânica): **F1, F2**. São extensões
  de `executar_ferramenta`. Podem entrar antes, depois, ou nem entrar agora se o foco for o Jarvis.

---

## Matriz de rastreabilidade (pedido → veredito → fase)

| Req | Pedido | Veredito | Onde |
|-----|--------|----------|------|
| **MR-1** | Timeout configurável por ferramenta | **Muda** (pequeno) | **F1** |
| **MR-2** | `interpreta_saida: "json"` (métricas, não só exit_code) | **Muda** (médio) | **F2** |
| MR-3 | Loop de revisão bounded | Futuro (v0.3) — o próprio harness diferiu | — |
| MR-4 | Input multimodal (imagem) | Futuro — não especificar agora | — |
| MR-5 | Gate posicional antes de nó irreversível | Futuro (nice) | — |
| **REQ-4** | Falha de provedor como erro tratável | **Muda** | **F3** |
| **REQ-2** | Missão como job durável e não-bloqueante | **Novo** (lib) | **F4** |
| **REQ-6** | Artefatos como referências, não blobs | **Muda** (shaping) | **F5** |
| **REQ-1** | Superfície MCP estável | **Novo** (servidor MCP) | **F6** |
| **REQ-5** | Descrições de ferramenta MCP | **Novo** (contrato do roteador) | **F6** |
| **(Caio)** | Digest compacto da missão (orquestrador não lê milhares de linhas) | **Novo** (essencial p/ conversar) | **F7** |
| **(Caio)** | RAG semântico sobre histórico de missões | **Novo** (opcional, depois) | **F8** |
| REQ-3 | Handshake de gate → porteiro | **Parcial no motor**: só expor o gate (F4/F6). Classe `dinheiro`/`identidade` e recusa-de-auto → **fora do motor** (orquestrador). | F4/F6 + arquitetura |
| REQ-7 | Envelope de segurança (Keychain, sem cred solta) | **Parcial no motor**: chaves vêm do env injetado pelo host. Resto é Jarvis-side. | F6 (nota) |

**Conclusão:** 2 extensões de ferramenta (F1, F2) + 4 fases que constroem a superfície de
serviço (F3→F6). MR-3/4/5 ficam fora. Toda a semântica de risco/permissão fica fora do motor.

---

## Leis (não quebrar)

1. **1 fase = 1 commit** pequeno. Commitar ao fim de cada fase.
2. **Nunca apagar nem afrouxar teste existente.** `python3 -m pytest -q` VERDE ao fim de
   cada fase. As fases F1–F5 são **aditivas e inertes por default**: sem os novos campos/
   chamadas, o comportamento é byte-idêntico ao de hoje.
3. **Não mudar a semântica testada** de roteamento, gates `plano`/`cobertura`, `ref_artefato`,
   ou Caixa. Você ADICIONA caminhos novos; não reescreve os existentes.
4. **Ambiguidade não se chuta — para e anota** em `## DÚVIDAS` no fim deste arquivo.
5. Python 3.14, **stdlib + deps do `pyproject.toml`**. A F6 introduz UMA dep nova (SDK MCP) —
   já está anotada e autorizada abaixo; nenhuma outra dep sem anotar.
6. Português nos comentários, como o resto do repo.
7. **Não toque em concern que não é da meta-fábrica** (ver fronteira de escopo). Se uma fase
   parecer exigir lógica de dinheiro/identidade/permissão dentro do motor, **pare** — está
   errado, isso é do orquestrador.

---

## Estado verificado do código (não mexer no que já funciona)

- **Nó-ferramenta:** `executar_ferramenta` (`grafo.py` ~L283–364). Roda `comando` via
  `subprocess.run(..., timeout=300, ...)` (**L332, hard-coded**), gateia por
  `exit_code == 0` **só** quando `interpreta_saida == "exit_code"` (**L334**), senão reprova
  sempre. `saida` junta stdout+stderr (**L333**).
- **Dois gates vivos** via `interrupt()`: `plano` (`grafo.py` ~L191) e `cobertura` (~L436).
  Payload já estruturado (`portao`, `pergunta`, `opcoes`, `lacunas`/`plano`). `spec.gates`
  (`GateFundador`) está **declarado mas NÃO ligado** ao grafo; `restricoes.teto_custo` é
  **hook, nunca medido**. → o motor **não** sabe de “dinheiro”; e está certo assim.
- **Provedor:** `__main__.py` **L91–93**: `if not ClienteClaudeCLI.disponivel(): print(...); return 1`.
  Pré-condição rígida + `print` + exit. É interface de humano (CLI).
- **Durabilidade:** com `--caixa`, `SqliteSaver` em `motor.db` + `thread_id` fixo `"cli"`
  (`__main__.py` L144, L167–169). `rodar_com_caixa` (`caixa.py` L121–144) faz loop sobre
  `__interrupt__` **bloqueando** num humano (nota no vault).
- **Artefatos:** `referenciar_artefato` resolve caminho+hash; resultado de nó carrega
  `artefatos: [{nome, tipo, caminho}]`; `resposta_final` é o texto da síntese.

---

## FASE 1 — MR-1: timeout configurável por ferramenta 🔴 (bloqueante pequeno)

**Por quê:** `timeout=300` mata qualquer solver FEA/CFD real (CalculiX/OpenFOAM) com falso
“timeout”. O harness não roda M2 sem isso.

**Arquivo / ponto:** `motor/grafo.py`, dentro de `executar_ferramenta`, **L332**.

**Mudança (FIXADA):**
```python
# antes
proc = subprocess.run(partes, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
# depois
timeout_s = int(ferramenta.get("timeout", 300))   # entidade de ferramenta manda; 300 = fallback
proc = subprocess.run(partes, capture_output=True, text=True, timeout=timeout_s, stdin=subprocess.DEVNULL)
```
Nada mais muda. A entidade `tipo: ferramenta` do Registry ganha um campo **opcional**
`timeout: <segundos>`; ausência → 300 (comportamento de hoje). `ferramentas_de_registro`
já carrega o frontmatter inteiro como dict, então **nenhuma mudança em `registro.py`**.

**Critério de aceite:**
- Ferramenta com `timeout: 3600` cujo `comando` dorme 310 s **conclui com sucesso**
  (hoje morreria aos 300). Use stub determinístico (script que dorme e sai 0).
- Ferramenta sem `timeout` continua com teto 300 s.
- Suíte existente sem regressão.

**Teste a adicionar** (`tests/test_ferramenta.py`): script stub que dorme N s e sai 0;
um caso com `timeout` curto que estoura (reprova com `motivo` de timeout), um com `timeout`
folgado que conclui. Mantenha rápido (dormir 1–2 s, não 310, e validar a leitura do campo
com um caso de timeout curto vs. folgado).

---

## FASE 2 — MR-2: `interpreta_saida: "json"` (métricas estruturadas) 🟡

**Por quê:** hoje só existe o modo `exit_code`; qualquer outro valor reprova sempre. Solvers
imprimem números (FS, tensão, massa, Δ de convergência) que precisam virar **dado**
estruturado para reconciliação/síntese, não prosa re-parseada por modelo.

**Arquivo / ponto:** `motor/grafo.py`, `executar_ferramenta`, **L333–334** e a montagem do
`resultado` logo abaixo.

**Contrato (FIXADO):** novo modo `interpreta_saida: "json"`. O executável imprime no
**stdout** (só stdout, não stderr):
```json
{"aprovado": true, "metricas": {"fs_escoamento": 2.1, "tensao_max_mpa": 112,
                                "convergencia_delta": 0.018, "massa_g": 84.3}, "motivo": ""}
```
- `aprovado` (bool) **gateia** o nó.
- `metricas` (dict) entra no `resultado` do nó como `resultado["metricas"]` → disponível
  para nós a jusante (`deps`), evaluator, síntese e `log.jsonl`.
- `motivo` (str) preenche o motivo da reprovação quando `aprovado=false`.
- **Falha de parse** (stdout não-JSON, ou JSON sem chave `aprovado`) → `aprovado=false`
  + evento `ferramenta.saida_invalida` (`ferramenta`, `subagente`, `motivo`). **Nunca**
  aprovação silenciosa.
- **`exit_code` continua intacto.** Qualquer `interpreta_saida` ≠ `"exit_code"` e
  ≠ `"json"` mantém o comportamento atual (reprova).

**Cuidado de implementação (importante):** hoje `saida = stdout+stderr` juntos (L333). No
modo `json`, faça o parse de **`proc.stdout`** isolado (stderr quebraria o JSON). Mantenha o
`saida` combinado para log/transparência, mas **parseie só stdout**. A checagem de artefatos
declarados em `produz[]` continua valendo após `aprovado=true` (igual ao modo exit_code).

**Esqueleto (orientação, ajuste ao estilo do arquivo):**
```python
modo = ferramenta.get("interpreta_saida")
if modo == "exit_code":
    aprovado = proc.returncode == 0
elif modo == "json":
    try:
        dados = json.loads(proc.stdout)
        if not isinstance(dados, dict) or "aprovado" not in dados:
            raise ValueError("json sem 'aprovado'")
        aprovado = bool(dados["aprovado"])
        metricas = dados.get("metricas") or {}
        motivo_json = str(dados.get("motivo") or "")
    except (json.JSONDecodeError, ValueError) as ex:
        aprovado = False
        metricas = {}
        motivo_json = f"saída inválida: {ex}"
        log.evento("ferramenta.saida_invalida", ferramenta=nome_ferramenta,
                   subagente=sub["id"], motivo=motivo_json)
else:
    aprovado = False
# ... ao montar `resultado`: se modo == "json" e há metricas → resultado["metricas"] = metricas
# ... se modo == "json" e não aprovado → usar motivo_json no `motivo`
```

**Critério de aceite (do harness):**
- Ferramenta `interpreta_saida: "json"` cujo script imprime o JSON acima → `aprovado`
  respeita o campo; `metricas` aparece em `resultado` e no `log.jsonl`; um nó a jusante
  recebe as métricas via `deps`.
- Script que imprime JSON **sem** `aprovado` → reprova + evento `ferramenta.saida_invalida`.
- Script com stdout não-JSON → reprova + mesmo evento.
- Modo `exit_code` inalterado (`tests/test_ferramenta.py` passa sem mudança).

**Fronteira:** extensão de `executar_ferramenta`. Não toca roteamento, verifier, nem
`ref_artefato`.

---

## FASE 3 — REQ-4: falha de provedor como erro tratável (não `print` + exit 1)

**Por quê:** `__main__.py` L91–93 aborta o processo com `print` + `return 1` se `claude` CLI
não está no PATH. Isso é interface de humano; um chamador programático (o job manager da F4)
precisa de **erro tipado**, não de processo que morre com código 1.

**Mudança (FIXADA):**
1. Em `motor/modelos.py` (ou um `erros.py` novo se preferir isolar), defina uma exceção:
   ```python
   class ProvedorIndisponivel(RuntimeError):
       """Nenhum provedor de modelo utilizável (ex.: `claude` CLI fora do PATH e sem config)."""
   ```
2. A **construção do cliente** para o caminho de serviço deve **levantar `ProvedorIndisponivel`**
   em vez de imprimir/sair. Extraia a lógica de “qual cliente montar” de `main()` para uma
   função reutilizável, por ex. `construir_cliente(cfg_modelos, dir_registro, log) -> ClienteModelo`,
   que:
   - monta `cliente_de_registro` / `cliente_de_config` / `ClienteClaudeCLI` como hoje;
   - se cair no `ClienteClaudeCLI` e `ClienteClaudeCLI.disponivel()` for falso → `raise ProvedorIndisponivel(...)`.
3. **A CLI mantém o comportamento de humano:** `main()` chama `construir_cliente` dentro de
   `try/except ProvedorIndisponivel` e aí sim faz `print(...)` + `return 1`. Ou seja, **o
   texto e o exit-code da CLI não mudam** — só o caminho programático ganha o erro tipado.

**Critério de aceite:**
- `main()` sem `claude` no PATH e sem `--modelos`/`--registro` → mesma mensagem e `return 1`
  de hoje (sem regressão de comportamento da CLI).
- `construir_cliente(...)` chamado direto, mesma condição → levanta `ProvedorIndisponivel`,
  **não** imprime, **não** chama `sys.exit`.
- Suíte verde. Adicionar teste unitário de `construir_cliente` nos dois ramos (com stub no
  lugar de `claude`).

**Fronteira:** nenhuma mudança de roteamento. Só refatorar a montagem do cliente para ser
chamável e falhar como exceção.

---

## FASE 4 — REQ-2: job durável e não-bloqueante (biblioteca `servico.py`)

**Por quê:** `invoke()` é síncrono e a missão é longa e pode pausar num gate por tempo
indefinido. `rodar_com_caixa` resolve durabilidade mas **bloqueia** num humano. O chamador
programático precisa **iniciar → receber id na hora → consultar → responder gate** sem
travar.

**Insight-chave (não reinventar):** o LangGraph **já** devolve o controle no gate — quando o
grafo bate em `interrupt()`, `invoke()` retorna com `__interrupt__` no resultado. Então:
um job = rodar `invoke()` numa thread de fundo; quando ela retorna, inspecionar:
`__interrupt__` presente → `gate_pendente`; senão → `concluido`. `responder_gate` retoma com
`Command(resume=...)` em nova thread de fundo. **Não usa Caixa nem `input()`.**

**Arquivo novo:** `motor/servico.py`. Reusa `construir_grafo` (F3), `SqliteSaver` durável e o
`construir_cliente` (F3).

**API (FIXADA — capacidade, não framework):**
```python
class GerenciadorJobs:
    def __init__(self, *, db_path="motor.db", workspace_base="runs",
                 cfg_modelos=None, dir_registro=None, politica=None, log=None): ...

    def iniciar(self, *, missao_texto=None, spec=None, thread_id: str) -> dict:
        """Dispara a execução em background e RETORNA IMEDIATAMENTE.
        thread_id é a chave de durabilidade — FORNECIDA PELO CHAMADOR e reusada.
        Retorna: {"job_id": thread_id, "estado": "em_execucao"}.
        Exige missao_texto XOR spec. Provedor ausente → ProvedorIndisponivel (F3)."""

    def status(self, job_id: str) -> dict:
        """Estado atual SEM bloquear:
          - {"estado": "em_execucao"}
          - {"estado": "gate_pendente", "gate": {portao, pergunta, opcoes, lacunas?, plano?}}
          - {"estado": "concluido", "resposta_final": str, "artefatos": [<refs>]}   # ver F5
          - {"estado": "erro", "erro": {"tipo": str, "mensagem": str}}"""

    def responder_gate(self, job_id: str, decisao) -> dict:
        """Retoma o job com Command(resume=decisao) em background. Retorna o novo estado
        (mesmo formato do status). Erro se o job não está em gate_pendente."""
```

**Contrato de durabilidade:**
- `thread_id` vem do chamador e é a chave (substitui o `"cli"` fixo). `config = {"configurable": {"thread_id": job_id}}`.
- **Checkpointer SQLite durável é o default** deste caminho (não o `InMemorySaver`). Religar
  o processo + `status(job_id)` retoma do gate pendente (mesma garantia que o `--caixa` dá ao
  humano, agora para o chamador programático).
- Execução em background: use `threading.Thread` (simples, suficiente — o grafo é I/O-bound
  em subprocessos/CLI). Guarde o estado do job num dict em memória `{job_id: registro}` +
  o checkpointer como verdade durável. Após crash, `status` reconstrói “gate_pendente” lendo
  o checkpoint (há `__interrupt__` pendente) — documente isso; se reconstruir do checkpoint
  for custoso, no mínimo persista o último payload de gate junto ao `motor.db`.
- **Erro tratável:** exceções da execução (inclusive `ProvedorIndisponivel`) viram
  `{"estado": "erro", ...}`, nunca derrubam o processo do gerenciador.

**Gates expostos, não decididos:** `status` devolve o payload de gate **como veio do
`interrupt()`** (`plano` e `cobertura` hoje). O gerenciador **não** classifica nem decide —
só transporta. Quem decide é o chamador (orquestrador) via `responder_gate`. **Não adicione
classe `dinheiro`/`identidade` aqui** (fora de escopo — ver arquitetura).

**Critério de aceite (com `ClienteStub`, sem rede):**
- `iniciar(missao_texto=..., thread_id="t1")` retorna na hora com `em_execucao`; após a
  execução, `status("t1")` chega a `gate_pendente` (gate `plano` ou `cobertura`) com payload
  estruturado.
- `responder_gate("t1", "prosseguir")` retoma e leva a `concluido` com `resposta_final`.
- Novo `GerenciadorJobs` apontando para o **mesmo** `motor.db` + `status("t1")` de um job
  pausado retoma do gate (durabilidade entre instâncias).
- `responder_gate` em job não-pausado → erro tratável.
- Suíte existente verde (este módulo é novo e não toca a CLI).

**Testes a adicionar:** `tests/test_servico.py` cobrindo os 4 itens acima com `ClienteStub`
e uma spec mínima que force gate (`politica` toda-manual).

---

## FASE 5 — REQ-6: resultado como referências de artefato, não blobs

**Por quê:** a saída da missão vira **dado de trabalho** na memória do Jarvis. O contrato
devolve **referências** (caminho/ids dos artefatos), não despeja blobs no estado. `job_id`/
`thread_id` é a chave de correlação com `runs/` + `log.jsonl`.

**Mudança (FIXADA):** no `status(...)=="concluido"` do `GerenciadorJobs` (F4), montar a saída
assim:
```python
{
  "estado": "concluido",
  "resposta_final": <str da síntese>,          # o texto-produto da missão
  "artefatos": [                               # REFERÊNCIAS, não conteúdo
    {"nome": ..., "tipo": ..., "caminho": ..., "subagente": <id>}
    # agregar de todos os resultados aprovados que têm `artefatos`
  ],
  "metricas": { <id_subagente>: {...} },       # se houver (F2), por nó — opcional
  "run": {"job_id": job_id, "workspace": "runs/<run_id>", "log": "log.jsonl"}
}
```
- **Não** inclua o conteúdo dos arquivos. Quem quiser o blob lê pelo `caminho`.
- `resposta_final` continua sendo texto (é o produto da síntese, não um artefato de arquivo).
- Correlação: o `job_id` aparece no envelope `run` para o chamador casar com `runs/` e os
  eventos do `log.jsonl`.

**Critério de aceite:** job concluído cujos nós produziram artefatos → `status` traz a lista
de refs (com `caminho` resolvido e existente) e **não** traz bytes de arquivo; `run.job_id`
== `thread_id`. Teste em `tests/test_servico.py`.

**Fronteira:** shaping da resposta do gerenciador. Não muda `referenciar_artefato` nem o
formato em disco.

---

## FASE 6 — REQ-1 + REQ-5: servidor MCP fino (superfície estável da meta-fábrica)

**Por quê:** o Jarvis só fala **MCP**: chama uma ferramenta e recebe **estado tipado**, nunca
faz parsing de `stdout`. Esta fase embrulha o `GerenciadorJobs` (F4/F5) num servidor MCP.
É a superfície da meta-fábrica → **dentro do escopo do motor**.

**Dep nova (autorizada):** o SDK MCP de Python (`mcp` / FastMCP). Anote no `pyproject.toml`.
Transporte: **stdio** (o host injeta env/chaves). É a única dep nova deste handoff.

**Arquivo novo:** `motor/mcp_servidor.py` (e um entrypoint, ex. `python -m motor.mcp_servidor`).
Ele instancia **um** `GerenciadorJobs` e expõe 3 ferramentas. As **descrições são contrato**
(REQ-5) — escreva-as EXATAMENTE assim (o roteador do Jarvis depende delas):

```
metafabrica.despachar_missao(objetivo: str, contexto?: str, restricoes?: object) -> {job_id, estado}
  """Entrega uma missão complexa à meta-fábrica: pesquisa multi-fonte, produção
  verificada e síntese. Use quando a tarefa exige vários passos/verificação
  adversarial e excede uma resposta direta do assistente. Não use para perguntas
  simples nem ações de sistema. Retorna um job_id para acompanhar; a execução é
  assíncrona (consulte status_missao)."""

metafabrica.status_missao(job_id: str) -> {estado, ...}
  """Consulta o estado de uma missão: em_execucao | gate_pendente | concluido | erro.
  Se gate_pendente, traz o payload do gate (decisão humana necessária). Se concluido,
  traz resposta_final e referências de artefato. Não bloqueia."""

metafabrica.responder_gate(job_id: str, decisao: str) -> {estado, ...}
  """Responde um gate pendente de uma missão e retoma a execução. USO INTERNO do
  fluxo de autorização do chamador (porteiro), não é ferramenta de uso livre do
  modelo. A decisão vem da escada de risco do Jarvis, nunca do julgamento de um modelo."""
```

**Mapeamento (FIXADO):**
- `despachar_missao` → `GerenciadorJobs.iniciar`. O servidor **gera o `thread_id`/`job_id`**
  (ex.: `uuid4`) se o chamador não passar um, e o devolve. `objetivo`→`missao_texto`;
  `contexto`/`restricoes` entram na missão/spec conforme o planner aceitar.
- `status_missao` → `GerenciadorJobs.status`.
- `responder_gate` → `GerenciadorJobs.responder_gate`.
- Todo erro vira retorno tipado/erro MCP, **nunca** `print`+exit (graças à F3/F4).

**REQ-7 (nota, sem lógica de permissão no motor):** chaves de provedor (se nuvem) vêm do
**env injetado pelo host MCP** (que lê do Keychain do macOS) — **não** hardcode, **não** leia
Keychain dentro do motor. O motor só consome `os.environ`. A escada de risco, o porteiro e a
recusa de auto para `dinheiro`/`identidade` **não moram aqui** — ver `ARQUITETURA-MCP-e-orquestrador.md`.

**Critério de aceite:**
- Subir o servidor e, via cliente MCP de teste, `despachar_missao` retorna `job_id`+`estado`;
  `status_missao` evolui `em_execucao`→(`gate_pendente`)→`concluido`; `responder_gate` retoma.
- Falha de provedor → erro MCP estruturado, processo do servidor **não** cai.
- As 3 descrições batem **palavra por palavra** com o contrato acima.
- Suíte existente verde; teste de fumaça do servidor em `tests/` (pode usar `ClienteStub`).

---

## FASE 7 — Digest da missão (resumo compacto pro orquestrador) 🟢 (essencial da trilha Jarvis)

**Por quê:** o orquestrador do Jarvis é um modelo **pequeno** — não pode ingerir o
`log.jsonl` inteiro nem os artefatos crus pra responder "como está a missão lá". Ele precisa
de um **resumo do tamanho de um modelo**. Este é o verdadeiro "RAG" que o Caio pediu pro
caminho de conversa — e ele **não precisa de banco vetorial**, só derivar do estado + log.

**Arquivo / ponto:** método novo no `GerenciadorJobs` (`motor/servico.py`, F4) + ferramenta
no servidor MCP (F6).

**API (FIXADA):**
```python
def resumo(self, job_id: str) -> dict:
    """Digest compacto, derivado de state + log.jsonl. NUNCA devolve log cru nem blobs."""
```
Formato de retorno (do tamanho de um modelo — alvo: caber em < ~400 tokens):
```python
{
  "estado": "em_execucao | gate_pendente | concluido | erro",
  "progresso": "3/5 subagentes concluídos; onda atual: [id, id]",   # derivado dos eventos onda.*
  "gate": {"portao": ..., "pergunta": ..., "opcoes": ...} | None,   # só se gate_pendente
  "marcos": [                                                        # eventos-CHAVE, não o log inteiro
    "planner: spec com 5 subagentes",
    "cobertura: reprovada — 1 lacuna",
    ...
  ],
  "resumo_resposta": "1–3 frases" | None,    # se concluído; do synthesizer, truncado/resumido
  "artefatos": [ {nome, tipo, caminho, subagente} ],   # refs (igual F5), nunca conteúdo
  "run": {"job_id": ..., "workspace": ..., "log": "log.jsonl"}
}
```

**Como derivar (orientação):**
- `progresso` e `marcos`: filtrar o `log.jsonl` da run por eventos de marco
  (`grafo_dep.iniciado`, `onda.iniciada/concluida`, `portao.aprovado/reprovado`, `gate.*`,
  `tarefa.concluida/abortada`, `ferramenta.executada` com aprovado=false) e formatar 1 linha
  cada. **Não** despejar o log; é um sumário de eventos selecionados.
- `resumo_resposta`: se a `resposta_final` for curta, use-a; se for longa, trunque para as
  primeiras frases (não chame modelo aqui — mantenha determinístico e barato; sumarização por
  modelo, se quiser, é decisão do orquestrador, não do motor).
- Tudo o mais reusa o que F4/F5 já têm.

**Ferramenta MCP (F6) correspondente:**
```
metafabrica.resumo_missao(job_id) -> <digest acima>
  """Resumo compacto de uma missão para acompanhamento conversacional: progresso,
  marcos, gate pendente e referências de artefato — sem despejar logs ou conteúdo.
  Use para responder 'como está a missão X'."""
```

**Critério de aceite:** missão em andamento → `resumo_missao` cabe em poucas linhas, traz
progresso e marcos sem o log cru; missão em gate → traz o `gate`; concluída → traz
`resumo_resposta` + refs. Determinístico (sem chamada de modelo). Teste em `tests/test_servico.py`.

---

## FASE 8 — RAG semântico sobre o histórico (opcional, depois) ⚪

**Por quê:** quando houver muitas missões concluídas, o Jarvis vai querer perguntas
retrospectivas — "já produzimos algo sobre X?", "como concluiu a missão Y?". Aí sim vale um
índice semântico. **Não construir antes de haver histórico** (senão é RAG no escuro). A F7
(digest) já cobre o caso de conversa ao vivo; a F8 é só o retrospectivo.

**Forma (FIXADA quando for a hora):**
- Índice **local-first** (Chroma ou sqlite-vec — sem nuvem; coerente com o resto). Corpus:
  por missão concluída, indexar `missao.objetivo` + `resposta_final` + artefatos **textuais**
  (lendo pelos `caminho`s de `runs/`). Chunking simples por artefato.
- Ferramenta MCP:
  ```
  metafabrica.buscar(consulta: str, k?: int) -> [ {run_id, trecho, ref, score} ]
    """Busca semântica no histórico de missões da meta-fábrica. Retorna trechos +
    referências de artefato, não documentos inteiros. Use para recuperar trabalho
    passado, não para acompanhar uma missão em andamento (use status/resumo)."""
  ```
- Indexação: um passo que roda ao concluir a missão (hook no `GerenciadorJobs`) ou um
  reindex batch sobre `runs/`. Decidir na hora; preferir incremental ao concluir.

**Critério de aceite (quando construída):** indexar 2–3 runs stub e `buscar("...")` retorna
o trecho certo com `ref` resolvível; nada de blobs inteiros; índice em disco local.

**Fronteira:** indexa as **saídas do próprio motor**. Não é a memória pessoal do Jarvis
(o cofre difuso/Chroma do Jarvis é Jarvis-side e indexa tudo que o Jarvis sabe). O motor só
expõe busca sobre o que **ele** produziu; o Jarvis decide o que guardar do retorno.

---

## O que fica FORA do motor (arquitetado, não codado aqui)

Detalhado em `ARQUITETURA-MCP-e-orquestrador.md`. Resumo para o Codex saber onde **não**
escrever código no motor:

- **Classe de risco do gate** (`rotina`/`dinheiro`/`identidade`) e a **cláusula pétrea**
  (dinheiro/identidade nunca auto): vivem no **orquestrador/porteiro** do Jarvis + **MCP de
  finanças** futuro. O motor só expõe o gate cru.
- **Porteiro, escada de risco, livro de confiança, dois cofres de memória:** Jarvis-side.
- **Medição de custo / enforcement de `teto_custo`:** sistema de finanças futuro, fora do motor.
- **MR-3/4/5** (loop bounded, multimodal, gate posicional): futuros, não nesta rodada.

---

## Ordem de execução e DoD global

```
Trilha JARVIS (a que conversa com a meta-fábrica):
  F3 (erro de provedor tratável) → F4 (GerenciadorJobs durável, gate espera) →
  F5 (refs de artefato) → F6 (servidor MCP) → F7 (digest/resumo)
  → F8 (RAG semântico)  [opcional, só com histórico]

Trilha HARNESS (independente):
  F1 (timeout)   F2 (interpreta_saida json)
```
Cada fase: commit próprio, `pytest -q` verde, sem regressão dos testes de hoje. F1–F5 e F7
são aditivas e inertes por default. F6 adiciona a dep MCP e o entrypoint; F8 (se construída)
adiciona a dep de índice local (Chroma/sqlite-vec).

**Lembrete travado:** nenhuma fase remove a validação humana. O gate sempre espera o
fundador; `--auto` fica desligado no caminho de serviço; o `GerenciadorJobs` nunca
auto-resolve. O MCP só muda o canal da resposta humana, não a dependência dela.

## DÚVIDAS (Codex preenche se travar; não chutar)

- (vazio)
