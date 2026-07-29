# ACHADOS UNIFICADOS — cadeado Anthropic (Fase A → B)

> Consolidação dos 4 relatórios da Fase A do [charter](../AUDITORIA-FINAL.md), rodados em
> 2026-07-25 por auditores Anthropic em contextos independentes, fatiados por grupo de
> invariante. Reprodutores em `tests/test_auditoria_anthropic_*.py` — **24 testes, todos
> vermelhos** contra o código atual. Nenhum arquivo de produção foi alterado pela auditoria.
>
> **Veredito: o cadeado Anthropic NÃO fecha.** 8 achados de severidade alta.

## Ressalva de independência (leia antes de confiar nisto)

Os quatro auditores são Anthropic, e o orquestrador que os despachou **modificou este código no
mesmo dia** — integrou 47 commits e reescreveu 9 testes de auditoria decidindo quais estavam
obsoletos. Mitigação aplicada: cada auditor rodou em contexto fresco, sem nenhum acesso a essas
decisões. Ainda assim:

- **Erro correlacionado não é coberto.** Se existe classe de defeito que modelos Anthropic não
  enxergam, ela passou pelos quatro. É exatamente por isso que o charter exige dois vendors.
- **O cadeado GPT-5/Codex está desatualizado.** As reproduções em `test_auditoria_gpt5_*.py` e
  `test_auditoria_codex.py` foram escritas contra o código anterior à integração do h12b3.
  Produção exige reauditá-lo sobre o estado atual.

## O padrão que atravessa os quatro relatórios

**A suíte segue verde — 972 passed — com todos estes defeitos presentes.** Ela não mede as
promessas do `INVARIANTES.md`. Três relatórios apontaram, de forma independente, testes citados
como prova de invariante que passam por **acidente de cenário**: montam o caso fácil e nunca
entram no ramo quebrado. O gate de CI verde (lint, tipos, SAST, segredos, build) continua
válido pelo que é, mas nunca foi evidência de que os invariantes se sustentam.

## Convergência independente

O achado **U-05** foi encontrado separadamente pelo auditor de kernel (A1) e pelo de grafo (B1),
sem contato entre eles. Dois olhares independentes na mesma linha — o sinal mais forte do lote.

---

## 🔴 Severidade alta (8)

| # | Achado | Onde | Invariante |
|---|---|---|---|
| **U-01** | **Gate humano vaza entre jobs.** A nota se chama `PENDENTE — {portao}.md`, sem o job; `_decisao_arquivada` faz glob global no vault compartilhado. A aprovação dada para o job A é consumida pelo job B, sem interação humana. Só no caminho CLI (`--caixa`); o serviço responde gates por API. | `caixa.py:475`, `607`, `676` | F2 |
| **U-02** | **Spec do usuário escapa do teto de custo.** A confrontação com `teto_bootstrap` existe só no ramo gerado pelo planner (`grafo.py:539`). Spec vinda da CLI/serviço — o entrypoint de produção — valida e segue direto, com `teto_custo` sem limite superior. É a única contenção monetária do sistema. | `grafo.py:497-500` vs `539`; `spec.py:78` | S4/S5 |
| **U-03** | **Falha parcial derruba o motor.** Tudo após o veredito do verifier está fora de guarda: `KeyError` em artefato sem `nome`, `OSError` em nome com separador, `command_runner.run` sem `try`. Como é o planner (LLM) que gera a spec e `produz_artefatos` é `list[dict[str, Any]]`, a validação não protege. Sem evento, sem resultado reprovado. | `grafo.py:772-773`, `875`, `1110` | G4 |
| **U-04** ✅ RESOLVIDO 2026-07-29 (ADR-004) | **O curador nunca executava o titular.** `rodar_sombra` roda só o candidato; qualidade e custo do titular saem de `caso["titular"]`, um dict do chamador. Quem monta os casos controla os dois lados da comparação. O `_LedgerCusto` — única fonte de custo medido — nunca é consultado. | `curador.py:254-259`, `560-563` | U2 |
| **U-05** | **Reconciliação descarta o nó culpado.** O veredito é reconstruído sem `nos_a_refazer` quando há reprovado, e a linha seguinte lê do dict mutilado. Com A→B, B reprovado e evaluator apontando A, refaz-se só o sintoma B — e queima uma rodada do teto. O loop de auto-correção corrige o lugar errado. **Achado por dois auditores independentes.** | `grafo.py:1147-1154` | G2 |
| **U-06** ✅ RESOLVIDO (U-06a fase C; U-06b 2026-07-29, ADR-004) | **Selo não provava autoria + a CLI fabrica evidência.** `evidencia_sha256` é sha256 público recomputável: detecta corrupção, não origem — evidência inventada passa na certificação. E `_runner_cli_read_only`, o runner de `--sombra`, ecoa `caso["candidato"]` do arquivo de entrada e sela como `sombra_concluida`, sem nenhuma chamada de modelo. | `curador.py:480-491`, `1293-1302` | U2/U3 |
| **U-07** ✅ RESOLVIDO 2026-07-29 (ADR-004) | **`min_casos` era autodeclarado pelo proponente**, sem piso e sem teste de significância — única validação é `>= 1`. Auditor certificou troca de modelo com **n=1**. Comparação `>` estrita entre proporções arredondadas; com n=2 (valor da própria suíte) é ruído com aparência de rigor. | `curador.py:514-520` | U2 |
| **U-08** | **`rodar_com_caixa` nunca renova o lease.** As duas chamadas de `ledger.consumir` omitem `lease_s`, e a thread de renovação só sobe se ele for passado. Retomada longa aplica o efeito e falha no ACK, deixando a outbox reelegível → redelivery e dois consumers no mesmo job. **Correção: uma linha em cada chamada.** | `caixa.py:647`, `715`, `366` | F1 |

## 🟡 Severidade média (15, resumidas)

- **Curador:** held-out puramente declarativo (`meta.origem` serve de split *e* proveniência);
  `de` nunca conferido contra catálogo vigente; U1 furável por `__deepcopy__` que devolve `self`;
  score de `propor` ignora `taxa_incompletas` e subtrai taxas de denominadores diferentes.
- **Kernel/Spec:** rubrica e `criterios_cobertura` em branco passam (`list[str]`, não `NonBlank`)
  — K3 vale sintaticamente e falha semanticamente; `validador`/`valida` em nó tipo `modelo` valida
  e nunca executa; `jsonschema` não declarado em `pyproject.toml` e o fallback ignora
  `enum`/`minimum`/`pattern` devolvendo a mesma mensagem de aprovação.
- **Grafo/Comando:** allowlist valida binário do **host**, mas o `DockerSandboxRunner` usa esse
  path como entrypoint **dentro da imagem** — C2 não é operável assim; entradas não resolvíveis
  descartadas em silêncio (`continue`, sem evento); byte nulo em entrada derruba o motor.
- **Eventos/Caixa:** split-brain de writer via remoção do sidecar `.lock` (revalidação por inode
  a cada escrita, mas do lock só na abertura); guard anti-drift cego a tipo não literal e sem
  checar campos.

## Onde os auditores NÃO acharam problema (dito explicitamente)

Isto importa tanto quanto a lista acima — silêncio não é aprovação, mas declaração é.

- **K4/ADR-003 se sustenta:** nenhuma escrita de catálogo, nenhum `curador.promoveu`, fail-closed
  sem repositório. O portão é real; o problema é o dado que chega nele.
- **Fronteira default-deny de C1 é sólida:** nenhum entrypoint de produção compõe
  `command_runner`, e a allowlist é checada *antes* do runner — nem runner permissivo injetado
  a contorna.
- **C4 estrutural correto:** `shlex.split` antes de `format_map` é a decisão certa; metacaractere
  e whitespace ficam contidos num elemento de `argv`.
- **G1 e G3:** ordem topológica, injeção de dependências e teto de reconciliação se sustentam.
- **Protocolo do `LedgerCaixa`:** WAL+FULL, CAS em claim/renovar/ack, serialização por job,
  revalidação do claim antes do efeito — "o ponto mais forte da fatia", sem achado.
- **E1 se mantém de fato** (verificado por AST de campos, não só de tipos).
- **Aritmética do curador é sólida:** ordem qualidade→custo, `>` estrito, custo nunca compensa.
  Não há caminho pelo qual custo aprove regressão de qualidade **dada evidência confiável**.

---

## Ordem sugerida para a Fase C

Ranqueada por consequência, não por esforço. Cada item exige, pelo charter: teste que falha
(já existe — os 24 reprodutores) → fix → gate de CI → **revisão do vendor oposto**.

1. **U-01** (gate vaza entre jobs) — autoridade humana é a fronteira mais cara de furar.
2. **U-02** (teto de custo) — única contenção monetária.
3. **U-08** (lease) — uma linha, consequência desproporcional ao esforço.
4. **U-03** (motor cai em falha parcial) — disponibilidade.
5. **U-05** (reconciliação) — o loop de auto-correção corrige o nó errado.
6. ~~**U-04, U-06, U-07** (curador)~~ — fechados em 2026-07-29; ver `ADR-004-curador-rigor.md`.
   U-04 era mesmo o mais profundo: exigiu medir o titular de verdade, e foi isso que tornou o
   desenho pareado e habilitou o teste de significância de U-07.

**U-02 e U-05 podem ser decisão de design, não bug.** Se "a spec do usuário é soberana" for
intencional, o `INVARIANTES.md` está redigido de forma enganosa e o texto de S5 precisa mudar —
mas nenhum dos dois auditores tratou isso como aceitável antes de produção.
