# ACHADOS — auditoria independente: grafo/reconciliação (G) e validador `comando` (C)

Escopo: `motor/grafo.py`, `motor/registro.py`, `motor/runner.py`, contra G1–G4 e C1–C4
de `docs/INVARIANTES.md`. Suíte baseline: **972 passed, 7 skipped** — nenhum achado
abaixo é detectado por ela.

Reprodutores: `tests/test_auditoria_anthropic_gc.py` (5 testes, **todos falham** no
código atual). Nada foi corrigido — só evidenciado.

```
.venv/bin/python3 -m pytest tests/test_auditoria_anthropic_gc.py -q
# 5 failed
```

---

## 🔴 Alta

### A1 — Falha parcial no grafo derruba o motor inteiro, sem evento e sem resultado reprovado (G4)

`subagente` protege as chamadas de modelo com `try/except Exception` (grafo.py:715, 752),
mas **tudo o que vem depois do veredito do verifier está fora de qualquer guarda**.
Campos da spec — que em produção é *gerada pelo planner LLM* — chegam crus:

- `grafo.py:772` — `nome = f"{sub['id']}__{artefato['nome']}"` → `KeyError` se o LLM
  emitir `produz_artefatos: [{"tipo": "texto"}]`.
- `grafo.py:773` / `registrar_artefato` em `grafo.py:342-349` — só faz `mkdir` da raiz;
  qualquer `nome` com separador (`"sub/dir/x.md"`) levanta `FileNotFoundError`.
- `grafo.py:1110` — `resolver_refs_artefato` levanta `RuntimeError` quando o artefato
  referenciado não existe em runtime.
- `grafo.py:875` — `command_runner.run(...)` **sem `try`**: qualquer exceção do adapter
  atravessa `executar_validador` → `subagente` → `executar_grafo_dep` → o run.

`Subagente.produz_artefatos` é `list[dict[str, Any]]` (spec.py:110) — a spec **não valida
nada** desse dicionário, então a validação da `WorkflowSpec` não é barreira aqui.

O invariante G4 promete “vira evento e resultado reprovado, não crash silencioso”.
Nesses caminhos não há evento (`executor.erro`/`tarefa.abortada`), não há resultado
reprovado, e o `LogEventos` fica sem registro do motivo — exatamente o modo de falha
que G4 nomeia.

Sobre travessia de caminho: `nome = "../../x"` **não** vaza hoje, mas só porque o
prefixo `{id}__` cola em `..` e vira um diretório inexistente. É acidente de
formatação, não validação — não conte com isso.

Testes que falham:
`tests/test_auditoria_anthropic_gc.py::test_g4_artefato_sem_campo_nome_derruba_o_motor`
`tests/test_auditoria_anthropic_gc.py::test_g4_nome_de_artefato_com_separador_derruba_o_motor`
`tests/test_auditoria_anthropic_gc.py::test_c1_excecao_do_runner_nao_e_contida_pela_fronteira`

---

## 🟡 Média

### B1 — Reconciliação descarta o nó culpado a montante sempre que há reprovado (G2)

`grafo.py:1147-1153`:

```python
if reprovados:
    veredito = {"aprovado": False,
                "lacunas": list(veredito.get("lacunas", [])) + [...]}   # 1147-1149
nomes = veredito.get("nos_a_refazer", [])                               # 1150
```

O ramo `if reprovados:` **reconstrói o dicionário do zero, sem a chave
`nos_a_refazer`**, e a linha seguinte lê essa chave do dicionário já reconstruído.
Resultado: a atribuição de causa produzida pelo evaluator é jogada fora, e
`nos_a_refazer` fica reduzido a `refazer_reprovados` — só os nós que falharam.

Isso anula, na prática, a instrução central de `PROMPT_EVALUATOR` (grafo.py:189-192:
“prefira o nó MAIS A MONTANTE responsável […] pois refazê-lo re-deriva os que
dependem dele”) **justamente no cenário em que ela importa**: quando algo reprovou.
Com A→B, B reprovado e evaluator apontando A, a reconciliação refaz apenas B — o
sintoma —, gasta uma rodada do teto G3 e converge para o mesmo erro.

Quando *nada* reprova (lacuna só de cobertura), o caminho funciona; por isso o teste
`test_grafo.py::test_gate_cobertura_preencher_refaz_fonte_e_dependentes_em_ordem`
passa e não cobre o caso. A suíte mede o ramo fácil.

Teste que falha:
`tests/test_auditoria_anthropic_gc.py::test_g2_atribuicao_a_montante_do_evaluator_e_descartada_quando_ha_reprovado`
(`AssertionError: ... nos_a_refazer=['B']`, esperado conter `'A'`)

### B2 — Argumentos não são validados em conteúdo; byte nulo derruba o motor (C4)

`executar_comando_seguro` (grafo.py:795-883) valida bem a *estrutura*: `shlex.split`
antes da substituição (então whitespace e metacaractere ficam contidos em um elemento
de argv — C4 se sustenta nesse ponto), placeholder não pode selecionar o executável
(827) nem fabricar opção (835-845). Mas **não valida o conteúdo do valor**. Um `\x00`
vindo de `entradas` da spec chega ao backend e faz o `subprocess` levantar
`ValueError: embedded null byte`, que:

- `DockerSandboxRunner.run` não captura — `runner.py:252` só trata `OSError`, e o
  `finally` de cleanup deixa a `ValueError` seguir;
- `executar_comando_seguro` não captura (grafo.py:875).

Mesma classe de A1, mas alcançável por dado da spec e não por adapter defeituoso.

Teste que falha:
`tests/test_auditoria_anthropic_gc.py::test_c4_byte_nulo_em_entrada_derruba_o_motor`

### B3 — A allowlist checa uma identidade no host que não é a que o sandbox executa (C1/C2)

`construir_grafo` resolve os executáveis **no host** com `resolve(strict=True)` +
`is_file()` + `os.access(X_OK)` (grafo.py:388-398) e repete a checagem por chamada
(grafo.py:846-874), enviando ao runner o *realpath do host* (grafo.py:874).

`DockerSandboxRunner` usa esse valor como `--entrypoint` **dentro da imagem**
(runner.py:144). Logo:

1. o binário verificado (host) não é o binário executado (imagem) — a “identidade
   absoluta resolvida” de C1 não descreve o que roda;
2. o host precisa conter, no mesmo path e executável, cada binário da imagem, senão a
   entrada é **silenciosamente descartada** (`continue` em grafo.py:392/396, sem evento
   nem erro) e o `comando` passa a negar tudo;
3. há duas allowlists independentes — a do grafo (resolvida) e a de
   `DockerSandboxRunner.__init__` (strings cruas, runner.py:80/130). Se `/usr/bin/python3`
   resolve para `/usr/bin/python3.11`, o runner rejeita o que o grafo aprovou.

Tudo isso falha *fechado*, então não é brecha — é motivo de C2 não ser operável como
está, e o descarte silencioso da allowlist é um modo de falha difícil de diagnosticar
em produção. Vale registrar em `sandbox-conformance.md` antes de certificar.

### B4 — Qualquer `.md` do Registry pode ampliar a allowlist global de executáveis (C1)

`ferramentas_permitidas_de_registro` (registro.py:192-204) varre `*.md` e coleta
`ferramentas_permitidas` **sem filtrar `tipo`** — ao contrário de
`ferramentas_de_registro` (:180), `rotas_de_registro` (:214) e `cliente_de_registro`
(:122), que todas filtram. Um arquivo de nota, uma entidade `tipo: rota` ou um
rascunho com esse campo no frontmatter entra na união silenciosamente; não há entidade
designada de política, nem erro por duplicidade/conflito (só dedupe).

Além disso, `servico.py:137-139` e `__main__.py:250-252` dão precedência ao JSON de
config sobre o Registry — a allowlist de subprocesso é decidida por JSON, o mesmo tipo
de fonte que K4 recusa como autoridade para promoção.

Sem reprodutor: é fraqueza de superfície de autoridade, não bug de execução.

---

## 🟢 Baixa

### C1 — `fonte_rag` é caminho arbitrário lido sem limite

`Subagente.fonte_rag` (spec.py:98) é string livre da spec gerada pelo LLM, e
`carregar_dataset` (rag.py:24) faz `read_text()` de um caminho arbitrário sem raiz
permitida e sem teto de tamanho, com o conteúdo indo para o prompt do subagente
(grafo.py:661-671). O impacto real é pequeno — só linhas JSON com chave `conteudo`
sobrevivem, e `OSError` devolve `[]` (fail-soft) —, mas `/dev/zero` ou um arquivo
enorme travam/estouram memória do run.

### C2 — `DockerSandboxRunner` sem limite de memória/CPU

`_argv` (runner.py:138-145) fixa `--network none`, `--read-only`, `--cap-drop ALL`,
`--no-new-privileges` e `--pids-limit 64`, mas não `--memory`, `--memory-swap` nem
`--cpus`. C3 só promete timeout, output e árvore de processos, então não é violação
declarada; é lacuna a fechar antes de certificar C2 (“ambiente confinado”).

### C3 — Cleanup falho apaga o `returncode` do resultado

`runner.py:264-269`: se `docker rm -f` falha, o `CommandResult` devolvido perde o
`returncode` de uma execução que pode ter sido bem-sucedida, e `executar_validador`
(grafo.py:1007) reprova. Fail-closed e defensável, mas o motivo reportado
(`cleanup_falhou`) esconde o exit code real na depuração.

---

## Onde NÃO encontrei nada de severidade ≥ média

- **G1 (ordem topológica + injeção de dependências).** `executar_grafo_dep`
  (grafo.py:1051-1092) só libera uma onda quando `set(depende_de) <= set(concluidos)`,
  a spec já proíbe ciclo (spec.py:206-207) e `deps_txt` (grafo.py:631-634) injeta as
  saídas das dependências. Não achei caminho que viole a ordem. Nota: nós cuja
  dependência reprovou entram em `concluidos` e são **bloqueados** (`resultado_bloqueado`,
  grafo.py:1031-1049) — comportamento correto e coberto.
- **G3 (teto de reconciliação).** `decidir_cobertura_node` (grafo.py:1286-1301) marca
  `limite_esgotado` por `rodada >= max_rodadas_reconciliacao`, e o contador só avança
  quando `preencher_lacunas` produz nós novos (grafo.py:1308-1319); preenchimento vazio
  vira `preenchimento_vazio=True`, que também retira a opção `preencher`. Percorri
  auto-mode, override e gate manual: não achei ciclo não-limitado.
- **C1 fronteira default-deny.** Nenhum entrypoint de produção compõe `command_runner`:
  `grep` em `motor/`, `motor_painel/`, `scripts/`, `tools/` mostra o parâmetro só em
  `grafo.py`; `DockerSandboxRunner` só é instanciado em
  `scripts/h05b_linux_conformance.py`. Em produção o validador `comando` é
  inexecutável por construção, e a checagem de allowlist acontece **antes** do runner
  (grafo.py:846-874), então nem um runner permissivo injetado contornaria a allowlist.
  Não achei caminho que contorne o `DenyCommandRunner`.
- **C4 estrutura de argv.** `shlex.split` **antes** de `format_map` é a decisão certa:
  o valor nunca reabre parsing, então `;`, `|`, `$(...)`, aspas e whitespace ficam
  dentro de um único elemento de argv. Testei separadamente template com placeholder
  no argv[0] (bloqueado, :827), placeholder virando opção (bloqueado, :839),
  placeholder expandindo para `--` (bloqueado pelo mesmo teste) e `--` literal
  liberando posicionais (comportamento intencional). O buraco de C4 é de conteúdo
  (B2), não de estrutura.

## Sobre “testes que não provam nada”

Auditei os fakes do slice e **não** encontrei teste tautológico ou que passe por
acidente nessa área:

- `tests/runner_fake.py::RunnerFake` roda `subprocess` local sem confinamento algum,
  mas os testes que o usam (`test_hardening_h04.py`, `test_ferramenta.py`,
  `test_validadores_deterministicos.py`) só asseveram construção de argv e allowlist —
  coisas do lado do grafo. Nenhum deles alega C2/C3.
- `tests/test_auditoria_gpt5_d.py:16-28` documenta explicitamente que os casos que
  exigem execução real ficam `skipif` sem `MOTOR_RUNNER_CERTIFICADO=1`, em vez de
  serem silenciados — e o `_RunnerCaptura` (:63-70) declara que prova o argv entregue,
  não o efeito. Honesto.
- O gap real não é teste falso, é **teste ausente**: nenhum caso exercita
  reconciliação com nó reprovado + atribuição a montante (B1), nem falha parcial fora
  da chamada de modelo (A1). Ambos passam despercebidos por 972 testes verdes.
