# HANDOFF — v0.2 Hardware, REQ-1: padrão `grafo_dependencias` (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR. Spec travada. **Não relitigar.**
> Origem: `../Harness Hardware/REQUISITOS-MOTOR-harness-hardware.md` (REQ-1) + a resposta
> do motor (`RESPOSTA-MOTOR-aos-requisitos.md`). Pré-req: suíte verde (hoje **134 passed**).

## Contexto

Hoje o motor só executa **paralelo puro** (`padrao: "fan_out_sintese"`): o validador em
`spec.py` REJEITA qualquer `depende_de`, e `despachar` no grafo faz um único `Send` pra
todos os subagentes. REQ-1 adiciona um padrão NOVO — `grafo_dependencias` — em que
`depende_de` é honrado: os subagentes rodam em **ordem topológica** (ondas), e cada um
recebe os **resultados das suas dependências** como entrada.

**Escopo deste corte = SÓ REQ-1.** Os resultados passados entre nós são **TEXTO** (a
saída do subagente, como hoje). Artefatos-arquivo (REQ-3) e a passagem por referência de
artefato (REQ-5) são cortes FUTUROS — **não** os faça aqui. Nó-ferramenta determinístico
(REQ-4) e loop de auto-correção (REQ-2, que vai pra v0.3) também não são deste corte.

**Decisão de arquitetura TRAVADA (risco baixo):** **não rerotear o caminho
`fan_out_sintese`.** Ele fica intocado (os 134 testes dele continuam idênticos). O
`grafo_dependencias` entra como um **nó dedicado** com o loop de ondas POR DENTRO (Python
puro), **reusando a função `subagente()` que já existe** — exatamente como
`preencher_lacunas` já a chama. Nada de mexer no `Send`/superstep do fan-out.

## Leis (não quebrar)

1. **1 corte = 1 commit** pequeno. Commitar ao fim.
2. **Nunca apagar nem afrouxar teste existente.** `python3 -m pytest -q` VERDE ao fim
   (134 + os novos). O caminho `fan_out_sintese` é **byte-idêntico** ao de hoje.
3. **Não tocar:** o nó `subagente` no que diz respeito ao fan-out, o `despachar`/`Send`,
   a fronteira `cliente.chamar(...)`, o `ClienteRoteador`/Registry, os gates
   (verifier/cobertura/fundador). A ÚNICA mudança em `subagente` é OPCIONAL e aditiva
   (injetar resultados de dependência no prompt — ver passo 3).
4. **Ambiguidade não se chuta — para e anota** em `## DÚVIDAS`. Se a semântica de
   superstep do LangGraph atrapalhar, NÃO improvise no core — anote o que achou.
5. Python 3.14, só stdlib + deps do `pyproject.toml`. Sem dep nova.
6. Português, como o resto do repo.

## Mapa do código

```
motor/spec.py    WorkflowSpec.padrao = Literal["fan_out_sintese"]; _consistencia()
                 REJEITA depende_de. Subagente.depende_de: list[str] já existe.
motor/grafo.py   planner → revisar_plano → rota_pos_plano → (despachar: Send×N) →
                 subagente → avaliar → sintetizar. `subagente(payload)` é função pura
                 {"sub","spec","feedback"?} -> {"resultados":[1]}. `preencher_lacunas`
                 já chama subagente(...) direto (reuso comprovado).
```

---

## REQ-1 — passos (FIXADOS)

### 1. `spec.py` — habilitar o padrão e validar o DAG

- `padrao: Literal["fan_out_sintese", "grafo_dependencias"]` (adicionar o valor).
- `versao` segue `"0.1"` (NÃO bumpar agora; v0.2 completa = quando REQ-1..5 fecharem).
- No `_consistencia`:
  - Se `padrao == "fan_out_sintese"`: manter a rejeição de `depende_de` EXATAMENTE como hoje.
  - Se `padrao == "grafo_dependencias"`: para cada subagente, validar `depende_de`:
    - cada id referenciado **existe** entre os subagentes (senão `ValueError` citando o id);
    - **sem auto-dependência** (`id` em seu próprio `depende_de` → `ValueError`);
    - o grafo de dependências é **acíclico** (ordenação topológica conclui; ciclo →
      `ValueError` listando os ids no ciclo). Use Kahn ou DFS, stdlib.

### 2. `grafo.py` — nó dedicado `executar_grafo_dep`

Adicione um nó que roda as ondas por dentro, reusando `subagente(...)`:

```python
def executar_grafo_dep(state):
    spec = state["spec"]
    subs = {s["id"]: s for s in spec["subagentes"]}
    concluidos: dict[str, dict] = {}     # id -> result dict (saída do subagente)
    resultados: list[dict] = []
    restantes = set(subs)
    log.evento("grafo_dep.iniciado", subagentes=list(subs))
    while restantes:
        onda = sorted(sid for sid in restantes
                      if set(subs[sid].get("depende_de", [])) <= set(concluidos))
        if not onda:                      # impossível se validado acíclico; trava de segurança
            log.evento("grafo_dep.travado", restantes=sorted(restantes))
            break
        log.evento("onda.iniciada", ids=onda)
        for sid in onda:                  # sequencial dentro da onda é OK neste corte
            sub = subs[sid]
            deps = {d: concluidos[d]["saida"] for d in sub.get("depende_de", [])}
            r = subagente({"sub": sub, "spec": spec, "deps": deps})["resultados"][0]
            concluidos[sid] = r
            resultados.append(r)
            restantes.discard(sid)
        log.evento("onda.concluida", ids=onda)
    return {"resultados": resultados}
```

> **Paralelismo intra-onda fica de fora deste corte** (sequencial é suficiente p/ o
> contrato de ORDEM; threads são otimização futura — anote em DÚVIDAS se quiser propor).

### 3. `grafo.py` — `subagente` injeta resultados de dependência (aditivo)

No `subagente(payload)`, leia `deps = payload.get("deps", {})` e, se houver, injete no
prompt do executor uma seção com os resultados das dependências (id → saída). Sugestão:
um novo campo opcional no `PROMPT_SUBAGENTE` (ex.: `{deps_txt}`) preenchido com
`"\nResultados das dependências:\n- <id>: <saída>\n..."` quando `deps` não for vazio, e
`""` quando vazio. **Quando `deps` é vazio (todo o caminho fan_out), o prompt fica
idêntico ao de hoje** — é isto que preserva os 134 testes. Não mude mais nada do nó.

### 4. `grafo.py` — wiring (sem tocar o fan-out)

- Registrar o nó: `g.add_node("executar_grafo_dep", executar_grafo_dep)`.
- `rota_pos_plano(state)`: se `avaliacao.abortada` → END (como hoje); **elif
  `spec["padrao"] == "grafo_dependencias"`** → `"executar_grafo_dep"`; **else** →
  `despachar(state)` (Sends pro `subagente`, caminho fan_out INTOCADO).
- Aresta: `g.add_edge("executar_grafo_dep", "avaliar")`.
- Inclua `"executar_grafo_dep"` na lista de destinos do conditional edge de
  `revisar_plano` junto de `["subagente", END]`.
- `subagente → avaliar` e tudo a jusante: inalterado.

### DoD (tests/test_grafo_dep.py — com ClienteStub determinístico)

1. **Cadeia A→B→C→D:** a ordem de execução é A,B,C,D; o prompt de B contém a saída de A
   (injeção de dep). Use um stub que registra a ordem das chamadas e ecoa o id.
2. **Diamante A→{B,C}→D:** A antes de B e C; D depois de B e C (B/C em qualquer ordem
   entre si).
3. **Ciclo A→B→A:** `WorkflowSpec.model_validate` levanta `ValueError`.
4. **Dep inexistente:** `depende_de: ["zzz"]` (id que não existe) → `ValueError`.
5. **fan_out intocado:** uma spec `fan_out_sintese` roda como antes; **os 134 seguem
   verdes**; `depende_de` sob `fan_out_sintese` continua REJEITADO.
6. **Passagem de resultado:** num A→B, o resultado de A chega no payload de B
   (`deps={"A": <saída de A>}`) e aparece no prompt de B.

### Exemplo (crie p/ documentar o padrão)

`exemplos/grafo-dep-minimo.json`: 3 subagentes em cadeia (`arquiteto → codificador →
validador`, papéis quaisquer, sem ferramentas/artefatos — texto puro), `padrao:
"grafo_dependencias"`, pra servir de smoke manual e de fixture.

---

## FUTURO (NÃO fazer aqui)

REQ-3 (artefatos-arquivo + workspace por run; resultado estruturado
`{resumo_texto, artefatos:[...]}`; estado carrega referência, não conteúdo) → REQ-4
(nó-ferramenta determinístico, resolvendo o executável pelo **Registry**) → REQ-5
(`entradas` com `ref_artefato`, a forma-arquivo da passagem que aqui é texto) → (v0.3)
REQ-2 (loop de revisão bounded). Cada um é um corte próprio.

---

## DÚVIDAS
(Codex: escreva aqui o que travou, em vez de chutar.)
