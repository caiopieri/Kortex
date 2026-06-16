# HANDOFF — Cortes do motor para o Codex (gpt-5.5 high) produzir

> **Papéis:** Codex = EXECUTOR (produz o código). Claude = VERIFICADOR (revisa depois,
> arruma erros). Este doc é a spec travada. **Não relitigar as decisões.**
> Modelo do executor: gpt-5.5 high. Spec à prova de executor potente: interface
> FIXADA, testes a montante como DoD, ambiguidade ESCALA (ver Leis).

## Leis (não quebrar)

1. **1 corte = 1 commit** pequeno (~≤300 linhas). Commitar entre cortes.
2. **Nunca apagar nem afrouxar teste existente** sem autorização. A suíte
   `python3 -m pytest -q` tem que ficar VERDE ao fim de cada corte (hoje: 110 passed).
3. **Ambiguidade não se chuta — para e anota** num bloco `## DÚVIDAS` no fim deste
   arquivo, e segue pro próximo corte independente. O Claude resolve na revisão.
4. **Não tocar** na fronteira `cliente.chamar(papel, prompt, ...)` (o grafo é cego a
   modelos) nem na semântica já testada de tier/esgotado/pin/guard-do-juiz.
5. Python 3.14, só stdlib + o que já está no `pyproject.toml` (langgraph, pydantic,
   langgraph-checkpoint-sqlite). Sem dependência nova sem anotar em DÚVIDAS.
6. Estilo: português nos comentários/docstrings, como o resto do repo.

## Mapa do código (contexto)

```
motor/spec.py       WorkflowSpec (pydantic): Subagente tem id, papel, objetivo,
                    entradas, resultado_esperado, rubrica, ferramentas, tier, depende_de.
motor/modelos.py    ClienteModelo (Protocol) + ClienteStub + ClienteRoteador
                    (resolução: pin > tier > papel > padrão; esgotados+cadeia;
                    provedor_de(); guard de juiz via `evitar`) + ClienteClaudeCLI +
                    ClienteCodex + ClienteOpenCode + ClienteOpenAICompat + cliente_de_config.
motor/politica.py   PoliticaGates(auto_mode, overrides) + decisao_auto(gate_id, default)
                    + politica_de_config. Precedência override>auto_mode>manual.
motor/grafo.py      construir_grafo(cliente, log, checkpointer=None, politica=None).
                    Topologia: START→planner→[fan-out subagente×N: attempt→verifier]
                    →avaliar(gate "cobertura")→sintetizar→END.
motor/eventos.py    LogEventos: evento(tipo, **dados) → JSONL {"t","evento",...}.
motor/caixa.py      CaixaFundador + rodar_com_caixa (gate via nota no vault + resume).
motor/__main__.py   CLI: --spec, --modelos, --esgotado, --auto, --gate, --pin, --caixa.
tests/              pytest; ClienteStub determinístico. NÃO apagar.
```

Eventos já emitidos (padrão do painel): `spec.criada/recebida`, `paralelo.iniciado`,
`executor.chamado` (com papel, tier), `executor.respondeu/erro`, `portao.aprovado/reprovado`,
`modelo.roteado_tier`, `modelo.pin`, `modelo.reroteado_esgotado`, `juiz.independencia`,
`gate.auto`, `escalado`, `decisao.fundador`, `tarefa.concluida/abortada`.

---

## CORTE 1 — Plan-review gate (revisão do plano antes do fan-out)

**Por quê:** o Caio quer ver o plano (qual modelo cada subtarefa vai usar) e poder
editar/aprovar ANTES de executar. Governado pela MESMA `PoliticaGates` (auto-mode
pula o gate; manual pausa).

**Interface FIXADA:**
- Novo nó `revisar_plano` no grafo, ENTRE `planner` e o fan-out (`despachar`).
- Ele monta o "plano": para cada subagente, `{"id","papel","tier","modelo": <provedor>}`
  onde `<provedor>` vem de `cliente.provedor_de(papel, tier, ferramentas)` quando o
  cliente tem esse método (senão `null`).
- Consulta `politica.decisao_auto("plano", default="prosseguir")`:
  - retorno != None (auto) → emite `gate.auto`(portao="plano", decisao=...) e segue
    direto pro fan-out, SEM pausar.
  - retorno None (manual) → emite `escalado`(para="plano") e `interrupt({"portao":
    "plano", "plano": [...], "pergunta": "Revise o plano. prosseguir / editar / abortar",
    "opcoes": "prosseguir · editar · abortar"})`.
- Resume (valor do `Command(resume=...)`):
  - `"prosseguir"` (ou começa com "prossegu") → roda o plano como está.
  - `"abortar"` (ou começa com "abort") → encerra (sem fan-out, sem resposta_final);
    estado `{"avaliacao": {"abortada": True, "motivo": "plano rejeitado"}}` e roteia pro END.
  - um **dict** `{subagente_id: novo_tier}` → aplica o override de tier nos subagentes
    correspondentes da spec ANTES do fan-out (muda `sub["tier"]`), emite
    `decisao.plano`(edicoes=<dict>), e roda.
- Emitir `decisao.plano`(decisao=str|edicoes) sempre que houver decisão manual.

**Não fazer:** não mexer no gate "cobertura" (já existe). Não criar UI. Edição = só
override de `tier` por subagente (override de modelo cru fica pra depois).

**DoD (escreva estes testes em tests/test_grafo.py, devem passar):**
1. `auto_mode=True` → roda sem interrupt; evento `gate.auto` com portao="plano";
   `resposta_final` presente.
2. Política manual (default) → `invoke` retorna `__interrupt__` com `value["portao"]=="plano"`
   e `value["plano"]` é lista com um dict por subagente contendo as chaves id/papel/tier/modelo.
3. Resume `"abortar"` → sem `resposta_final`, `avaliacao["abortada"] is True`, fan-out NÃO rodou
   (nenhum `executor.chamado` com papel de subagente no log).
4. Resume com dict `{"pesquisa-alfa": "complexa"}` → o subagente pesquisa-alfa roda com
   tier "complexa" (verifique via `executor.chamado` tier no log), evento `decisao.plano`.
5. Os 110 testes anteriores continuam verdes.

Use o padrão de `tests/test_grafo.py` (ClienteStub + faz_roteador + InMemorySaver).
O `provedor_de` no ClienteStub não existe → no teste, use ClienteRoteador (que tem)
ou aceite `modelo: null` no payload do plano.

---

## CORTE 2 — Telemetria (medir antes de otimizar)

**Por quê:** base pro Curador e pra certificação; e pra ENXERGAR o custo. "Não se
otimiza o que não se mede."

**Interface FIXADA:**
- Novo módulo `motor/telemetria.py` com:
  - `resumir(eventos: list[dict]) -> dict` — recebe a lista de eventos parseados do
    log e devolve um resumo com EXATAMENTE estas chaves:
    ```
    {
      "missao": <id ou None>,
      "subagentes": <int>,                 # de spec.criada/recebida
      "chamadas_por_papel": {papel: int},  # conta executor.chamado por papel
      "reprovacoes_verifier": <int>,       # portao.reprovado com portao começando "verifier:"
      "reroteamentos": {"esgotado": int, "juiz": int, "ferramentas": int},
      "gates": {"auto": int, "manual": int},   # gate.auto vs escalado
      "falhas_modelo": <int>,              # eventos modelo.falha
      "concluida": <bool>                  # houve tarefa.concluida
    }
    ```
  - `carregar(log_path) -> list[dict]` — lê o JSONL (reusar a lógica de parse; pode
    importar de motor_painel/painel.py:parse_eventos se existir, senão ler linha a linha).
- CLI: `python3 -m motor.telemetria <caminho/log.jsonl>` imprime o resumo legível
  (uma chave por linha; dicts indentados). Sem libs novas.

**Não fazer:** não medir custo em $/tokens ainda (o log não tem usage; isso é outro
corte — anote em DÚVIDAS se quiser propor o evento `modelo.uso`).

**DoD (tests/test_telemetria.py):**
1. Dado um log de exemplo (monte uma lista de eventos no teste cobrindo spec.criada,
   2× executor.chamado papel "pesquisador", 1 portao.reprovado "verifier:x", 1 gate.auto,
   1 modelo.reroteado_esgotado, tarefa.concluida), `resumir` devolve os contadores certos.
2. `resumir([])` não quebra (devolve zeros/None/False).
3. Suíte verde.

---

## CORTE 3 — 3ª opção do gate "cobertura": preencher a lacuna

**Por quê:** hoje o gate de cobertura só oferece prosseguir/abortar. O Caio quer a
opção de FECHAR a lacuna (re-fan-out) em vez de aceitar parcial.

**Interface FIXADA (mínima, sem re-planejamento geral):**
- No nó `avaliar`, quando reprovado e a decisão (manual OU auto via
  `politica.decisao_auto("cobertura")`) for `"preencher"`:
  - para cada lacuna que cite um subagente reprovado (string contém o id de um
    subagente), reexecutar SÓ aquele(s) subagente(s) uma vez (chamar a mesma lógica
    de `subagente`), com o feedback da lacuna no prompt; recommitar resultados.
  - emitir `lacuna.preenchida`(subagente=<id>) por reexecução.
  - depois, reavaliar UMA vez; se ainda reprovar, cai no comportamento atual
    (interrupt/auto prosseguir). Limite: no máx. 1 rodada de preenchimento (anti-loop).
- `politica`: aceitar a decisão "preencher" como override de gate válido.

**Se isto ficar ambíguo/grande, PARE e anote em DÚVIDAS — não improvise re-planejamento.**

**DoD:** teste em test_grafo: subagente reprovado + decisão "preencher" → evento
`lacuna.preenchida` e o subagente é reexecutado; com no máx. 1 rodada. Suíte verde.

---

## FUTURO (NÃO fazer agora — design pendente com o Claude)

Registry como cérebro do roteamento; biblioteca de rotas multi-domínio; o Curador
(loop de melhoria contínua); input-enxuto profundo (contrato compacto da fundação);
hosting 24/7. Esses exigem decisão de arquitetura — não são pra este handoff.

---

## DÚVIDAS
(Codex: escreva aqui o que travou, em vez de chutar.)
