# Requisitos do Motor para o Harness Mecânico

> **Para:** agente responsável pelo motor (`Orquestrador/motor`).
> **Origem:** harness mecânico.
> **Método:** cada item foi validado contra o **código real** (`motor/spec.py`, `motor/grafo.py`, `motor/registro.py`), com linha citada — não contra memória. Onde já funciona, está marcado **atende**. Onde falta, vem com contrato + critério de aceite.
> **Instrução:** respeite as decisões travadas do motor (LangGraph puro; nós = funções puras que só falam `cliente.chamar`; a spec é a dinâmica; eventos JSONL próprios). **Nenhum requisito abaixo relitiga isso** — todos estendem a *spec* ou a execução de nó-ferramenta. Ambiguidades exigem decisão explícita do mantenedor.

---

## Resumo executivo

Diferente do harness de hardware (que pediu 5 capacidades ausentes), o motor de **hoje já hospeda o degrau de design+simulação estática (M2)**. A cadeia `grafo_dependencias` + nós-`ferramenta` + `ref_artefato` é exatamente o pipeline `CAD → malha → solver → reconciliação → docs`. Por isso esta lista é **curta**: **1 bloqueante pequeno (MR-1)**, **1 útil de médio porte (MR-2)**, e **3 itens futuros (MR-3..5)** que não travam M2.

| Req | O quê | Severidade | Habilita |
|---|---|---|---|
| **MR-1** | Timeout configurável por ferramenta | 🔴 Bloqueante (pequeno) | qualquer solver FEA/CFD (M2+) |
| **MR-2** | `interpreta_saida` estruturado (métricas, não só exit_code) | 🟡 Útil (médio) | reconciliação limpa + transparência (Artigo 10) |
| **MR-3** | Loop de revisão bounded (FEA-falha → modelador) | ⚪ Futuro (v0.3) | auto-correção; **humano fecha o loop por ora** |
| **MR-4** | Canal de input multimodal (imagem) | ⚪ Futuro | feedback do loop físico (foto de fratura → malha) |
| **MR-5** | Gate humano posicional antes de nó irreversível | ⚪ Futuro (nice) | Artigo 7 dentro do grafo (hoje o gate é externo) |

---

## O que JÁ funciona (verificado — não mexer)

- **Cadeia em ondas topológicas.** `padrao: "grafo_dependencias"` honra `depende_de`; `executar_grafo_dep` (grafo.py L366–392) roda em ondas, ciclo é erro de validação (spec.py L113–133). → o pipeline `analítico → CAD → malha → solver → check → docs` executa na ordem.
- **Nó-ferramenta determinístico.** `executar_ferramenta` (grafo.py L283–364): roda `comando` via `subprocess`, preenche placeholders a partir de `entradas`, declara saídas via `produz[].de_placeholder`, gateia por `exit_code == 0` (L334), emite `ferramenta.executada` / `ferramenta.indisponivel`. Executável ausente → falha explícita (L324–329). → os solvers (CalculiX/Gmsh) e os checadores (reconciliação/DFM/clash) são nós-ferramenta.
- **Passagem de artefato.** `ref_artefato` resolvido em runtime para o **caminho real** (`resolver_refs_artefato`, grafo.py L394–408); validação rejeita ref a não-ancestral ou artefato não declarado (spec.py L148–165). Suporta **múltiplos** inputs-artefato (ex.: o checador de reconciliação lê `results.json` **e** `analytical.json`). → o STEP/malha/resultado passa adiante.
- **Modelo a jusante lê o stdout da ferramenta.** Em `grafo_dependencias`, um nó-modelo recebe `deps = {id: saida}` no prompt (grafo.py L385, L231–235). → um **validador-modelo** consegue interpretar os números que o solver imprimir no stdout (FS, tensão máx, massa). Isto é o que torna a reconciliação por modelo viável **sem mudança de motor**, desde que os escalares estejam no stdout.
- **Workspace por execução** `runs/<run_id>/artefatos/` (grafo.py L139–140, `workspace_base` configurável L127). Artefato por caminho+hash (L109–122).
- **Três gates** já existem: verifier-modelo (L263–266), evaluator de cobertura (L410–421), gate do fundador via `interrupt()` (L436–441).
- **Registry de ferramentas** como entidades `.md` (`ferramentas_de_registro`, registro.py L167–183).

**Conclusão falsificável:** o 1º passo do harness é escrever uma **WorkflowSpec M2 real** (ex.: bracket sob carga) e validá-la contra o schema — exatamente como o hardware fez com `exemplos/hardware-diagnostico.json`. Rodar isso revela o atrito real antes de qualquer extensão de motor.

---

## MR-1 — Timeout configurável por ferramenta 🔴

**Estado hoje (grafo.py L332):** `subprocess.run(partes, ..., timeout=300, ...)` — **300 s fixos, hard-coded**. Qualquer solve de FEA/CFD não-trivial (CalculiX em malha fina, OpenFOAM) ultrapassa 5 min e é morto com falso `"timeout ao executar ferramenta"` (L359–364).

**Necessário:** o timeout do `subprocess` vem da **entidade de ferramenta** do Registry (campo `timeout` em segundos), com fallback ao default atual (300 s) quando ausente. Sem teto artificial baixo para solvers.

**Contrato:** entidade `tipo: ferramenta` ganha campo opcional `timeout: <segundos>`. `executar_ferramenta` lê `ferramenta.get("timeout", 300)` e passa ao `subprocess.run`. Nenhuma outra mudança de fronteira.

**Critério de aceite:** uma ferramenta com `timeout: 3600` roda um script que dorme 310 s e **conclui com sucesso** (hoje morreria aos 300). Teste com stub determinístico (script que dorme e sai 0). Suíte existente sem regressão.

---

## MR-2 — `interpreta_saida` estruturado (métricas, não só pass/fail) 🟡

**Estado hoje (grafo.py L334):** `aprovado = proc.returncode == 0 if ferramenta.get("interpreta_saida") == "exit_code" else False`. Ou seja, **só existe o modo `exit_code`**; qualquer outro valor de `interpreta_saida` reprova **sempre**. O stdout vira texto livre em `saida` (L333) e flui adiante, mas **sem estrutura** — o motor não captura métricas (FS, tensão máx, Δ de convergência, massa) como dado.

**Por quê (mecânica):** a reconciliação (Artigo 2) e a transparência (Artigo 10) ficam muito mais limpas se o nó-ferramenta puder devolver **métricas estruturadas** que entram no `resultado` e, portanto, no evaluator/síntese/deps como dado — não como prosa a ser re-parseada por um modelo.

**Necessário:** um modo adicional `interpreta_saida: "json"` em que o motor lê o **stdout como JSON** no formato `{"aprovado": bool, "metricas": {...}, "motivo": str}`. `aprovado` gateia; `metricas` entra no `resultado` do nó (ex.: `resultado["metricas"]`), disponível para nós a jusante e para o log. O modo `exit_code` **continua intacto** (não quebrar os testes atuais).

**Contrato sugerido:**
```
# entidade ferramenta
interpreta_saida: json      # alternativa a exit_code
# o executável imprime no stdout, p.ex.:
# {"aprovado": true, "metricas": {"fs_escoamento": 2.1, "tensao_max_mpa": 112,
#                                 "convergencia_delta": 0.018, "massa_g": 84.3}, "motivo": ""}
```
Falha de parse (stdout não-JSON ou sem `aprovado`) → `aprovado=false` + evento `ferramenta.saida_invalida`, nunca aprovação silenciosa.

**Critério de aceite:** ferramenta com `interpreta_saida: "json"` cujo script imprime o JSON acima → `aprovado` respeita o campo, `metricas` aparece no `resultado` e no `log.jsonl`; um nó a jusante recebe as métricas. Script que imprime JSON sem `aprovado` → reprova com evento próprio. Modo `exit_code` inalterado (testes de `test_ferramenta.py` passam sem mudança).

> **Nota de fronteira:** isto é extensão de `executar_ferramenta`, não novo tipo de nó. Não toca roteamento, verifier-modelo, nem o formato de `ref_artefato`.

---

## MR-3 — Loop de revisão bounded (diferido para v0.3) ⚪

**Estado hoje:** `grafo_dependencias` executa as ondas **uma vez** (L374–392). O `preencher_lacunas` (L445–461) re-roda o **mesmo** nó reprovado com feedback — **não** roteia a saída de um validador de volta para um nó **upstream diferente** (ex.: FEA-falha → re-disparar o modelador CAD com as coordenadas do hotspot).

**Decisão (travada, alinhada ao Artigo 8 e à postura do hardware):** **humano fecha o loop por ora.** FEA reprova → o orquestrador relê o rationale e re-dispara o modelador manualmente. A auto-correção bounded (iteração com teto, estado "não-convergiu", anti-loop-infinito) entra **só depois** de observarmos os padrões reais de reprovação do FEA — senão se projeta o loop no escuro (e o auto-engrossar-no-hotspot é mecanicamente ingênuo: pode perseguir singularidade ou mover o caminho de carga). 

**Quando for a hora (v0.3):** construto de loop em que a saída estruturada (reprovação + `metricas` + coordenadas do hotspot, via MR-2) volta como **entrada** de um nó upstream nomeado, com `max_iteracoes` e estado explícito de não-convergência. Mesmo contrato sugerido no doc de hardware (`laco: {validador, retorna_para, max_iteracoes}`). **Não construir antes de M2 rodar e gerar dados de reprovação reais.**

---

## MR-4 — Canal de input multimodal (imagem) ⚪ Futuro

**Estado hoje:** `cliente.chamar(papel, prompt)` é texto puro (modelos.py — clientes CLI). Sem canal de imagem.

**Necessário (loop físico):** para o feedback de bancada (foto de peça fraturada → correlacionar com a malha → reiniciar a simulação no ponto da falha), um nó-modelo precisaria aceitar **imagem** como entrada. É a parte multimodal do Artigo 8.

**Postura:** **futuro, não-bloqueante.** Só relevante quando o loop físico estiver maduro (M4+). Registrar como direção; não especificar contrato agora (seria especular sem cliente). A correlação imagem→coordenada-de-malha é, ela mesma, trabalho de harness, não de motor.

---

## MR-5 — Gate humano posicional antes de nó irreversível ⚪ Futuro (nice)

**Estado hoje:** o gate do fundador (`interrupt`) está acoplado ao evaluator de **cobertura** (grafo.py L436–441), depois da execução. Não há um gate **posicionado antes de um nó específico** de alto custo/irreversível.

**Necessário (Artigo 7):** idealmente, um `interrupt()` **antes** do nó de fabricação/deploy, não só após cobertura. 

**Postura:** **não-bloqueante hoje** — a fabricação acontece **fora** do harness (o humano submete à JLC), então o gate já é naturalmente humano. Vira útil só quando/se o deploy à API entrar no grafo. Registrar; não construir agora.

---

## Fronteira: o que NÃO muda

Nada aqui toca roteamento por papel/tier/capacidade (`ClienteRoteador`), o `interrupt()` do fundador, o formato do `log.jsonl`, LangGraph puro, ou os testes existentes do stub. MR-1 e MR-2 são extensões de `executar_ferramenta`; MR-3..5 são futuros. A fatia de M2 **não precisa de MR-3/4/5** e precisa de **MR-1** (e se beneficia muito de **MR-2**).

**Ordem sugerida:** MR-1 (destrava qualquer solve real) → validar a 1ª WorkflowSpec M2 ponta-a-ponta → MR-2 (com os padrões de saída de solver já observados) → (v0.3) MR-3.

---

*Documento-irmão: [[00-BLUEPRINT]] (onde estes requisitos viram degraus) · [[01-CONSTITUICAO-MECANICA]] (a lei que os gates servem).*
