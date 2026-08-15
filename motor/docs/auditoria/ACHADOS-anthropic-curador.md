# ACHADOS — Curador anti-Goodhart (grupo U)

Auditoria defensiva de `motor/motor/curador.py` (1630 linhas) contra os invariantes
U1/U2/U3 de `docs/INVARIANTES.md`.

**Estado da suíte antes da auditoria:** 81 testes verdes em
`test_hardening_h08/h09a/h09b/h09c` + `test_curador`. Nenhum deles falha.
Isso **não** significa que os invariantes se sustentam — significa que a suíte
mede o interior do contrato e nunca a fronteira dele.

**Probes escritos:** `motor/tests/test_auditoria_anthropic_curador.py` — 8 testes,
**8 falham**, um por achado. Nenhuma linha de `curador.py` foi alterada.

```
.venv/bin/python3 -m pytest -q tests/test_auditoria_anthropic_curador.py
8 failed in 0.54s
```

---

## Sumário

| Sev | # | Achado |
|---|---|---|
| 🔴 | 1 | O selo não é chaveado e a CLI `--sombra` fabrica evidência selada sem executar nada |
| 🔴 | 2 | O titular nunca é executado: os dois lados da comparação vêm do mesmo input |
| 🔴 | 3 | `min_casos` é autodeclarado pelo proponente; n=1 certifica; nenhum teste estatístico |
| 🟡 | 4 | "held-out" é puramente declarativo; `meta.origem` faz duplo dever; zero defesa contra contaminação |
| 🟡 | 5 | `de` (titular) nunca é conferido contra o catálogo vigente — o curador não lê catálogo nenhum |
| 🟡 | 6 | U1 é literalmente falso: `deepcopy` é furável por `__deepcopy__` que devolve `self` |
| 🟡 | 7 | O score de `propor` ignora `incompletas` e subtrai taxas de denominadores diferentes |
| 🟢 | 8 | `BaseException` no runner aborta a sombra inteira |
| 🟢 | 9 | `casos_ignorados` fica fora do selo — viés de seleção é invisível ao certificador |
| 🟢 | 10 | `min_amostras=3` default em `propor` |

---

## 🔴 1 — O selo não é chaveado, e a própria CLI produz evidência selada sem execução

`curador.py:480-491` — `_selo_sombra` é `sha256(json.dumps(...))` sobre campos
públicos da própria evidência. `curador.py:505-507` valida recomputando o mesmo
hash. Isso detecta **corrupção acidental**, não autoria. Qualquer produtor de
JSON monta uma evidência inteira e assina corretamente.

Pior: `curador.py:1293-1302`, `_runner_cli_read_only`, é o runner usado por
`python3 -m motor.curador --sombra` (`curador.py:839`). Ele **devolve
`caso["candidato"]` do próprio arquivo de entrada**. Ou seja, o comando que
deveria "rodar o candidato em sombra" na verdade ecoa o resultado que o autor do
arquivo escreveu, sela isso como `versao: 2 / sombra_concluida`, e o resultado
passa em `certificar_sombra` sem ressalva. Nenhuma chamada de modelo acontece,
e nada na evidência registra esse fato.

Probe: `test_U2_selo_nao_e_chaveado_evidencia_100pct_forjada_certifica` — evidência
inventada do zero (3 casos que nunca existiram) → `status == "certificado"`.

O que salva hoje é só U3 (a promoção exige repositório). Mas a evidência selada é
o artefato que circula, é o que o markdown de `formatar_sombra_markdown` apresenta
ao humano, e é o que o repositório vai guardar. Selo sem chave é um convite a
confundir "íntegro" com "autêntico".

**Correção mínima:** HMAC com segredo do motor, ou — melhor — o selo deixar de ser
o critério e a evidência passar a referenciar `event_id`/`run_id` do ledger v2
(que já é append-only e tem writer único, per E2). E `--sombra` sem runner real
deve produzir `status: "sombra_invalida"`, nunca `sombra_concluida`.

## 🔴 2 — O titular nunca é executado; qualidade e custo dele são declarados pelo chamador

`curador.py:254-259` executa o runner **só para o candidato**. O lado do titular
sai de `caso["titular"]` via `_resumo_caso` (`curador.py:560-563`), que apenas
faz `deepcopy` de um dict arbitrário. `_ContadorSombra.registrar`
(`curador.py:573-584`) tira dali tanto `aprovado` quanto `custo_usd`.

Consequência: **quem monta os casos controla os dois lados da comparação.**
Basta declarar o titular como reprovado e caro. Não há nenhum cruzamento com o
`_LedgerCusto` (`curador.py:1064`), que é a única fonte de custo *medido* do
módulo e nunca é consultada pela sombra nem pela certificação.

Probe: `test_U2_titular_e_fabricado_pelo_proponente_e_nunca_reexecutado` — 5 casos,
titular declarado `aprovado: False, custo_usd: 1000.0`, candidato aprovado a
`0.001` → `certificado`.

Isto é o buraco central anti-Goodhart. U2 promete "recomputa a evidência selada";
recomputar significa apenas *reagregar os números que o chamador escreveu*. O
teste que a suíte usa para provar U2 —
`test_hardening_h09a.py::test_certificacao_recomputa_casos_e_ignora_agregados_recebidos`
— só demonstra que os campos de topo `evidencia["titular"]`/`["candidato"]` são
ignorados em favor de `evidencia["casos"]`. Ele não toca no fato de que
`evidencia["casos"][i]["titular"]` é igualmente input do chamador. **É um teste
que prova menos do que o invariante afirma.**

**Correção mínima:** o custo do titular tem que vir do ledger (`por_slot_modelo`,
`curador.py:1166`) para o mesmo slot e janela; e a aprovação do titular tem que vir
de eventos `portao.aprovado/reprovado` reais, referenciados por `event_id`.

## 🔴 3 — `min_casos` é autodeclarado, sem piso, e não há teste de significância

`curador.py:514-520`: o piso amostral vem de `evidencia["politica"]["min_casos"]`,
que por sua vez vem de `proposta["politica"]` copiada em `curador.py:267`. Quem
propõe a troca escolhe quantos casos bastam. A única validação é `min_casos >= 1`.

`test_U2_min_casos_autodeclarado_certifica_com_um_unico_caso` certifica uma troca
de modelo de produção com **um caso**. Não é hipotético: a própria suíte usa
`min_casos: 1` em `test_hardening_h09c.py:56`.

Além do piso, não existe nenhum teste de significância. `certificar_sombra`
(`curador.py:311`) compara duas proporções amostrais com `>` estrito sobre valores
arredondados a 4 casas. Com n=2 (o valor usado em h09a/h09b), 1/2 vs 0/2 é ruído
puro e certifica. "Estritamente maior" dá aparência de rigor a uma comparação sem
nenhum poder estatístico — é exatamente o formato de métrica que Goodhart come.

**Correção mínima:** piso duro no código (não na política do chamador), e
substituir `>` por um limite inferior de intervalo de confiança / teste exato
sobre pares casados. Sem isso, U2 é teatro de precisão.

## 🟡 4 — "held-out" é uma string do próprio input; nenhuma defesa contra contaminação

`curador.py:530-534` exige `caso["split"] == "held-out"` e `proveniencia` string
não-vazia. Ambos vêm de `_evidencia_caso` (`curador.py:444-453`), que os lê de
`caso["meta"]`. E o fallback é `meta["origem"]` para **os dois campos**: um caso
com `meta = {"origem": "held-out"}` recebe automaticamente
`split="held-out"` e `proveniencia="held-out"`.

Ou seja: a checagem de proveniência é vacuamente satisfeita por qualquer string,
e a de split é satisfeita escrevendo a palavra certa. Nada liga esses casos a um
conjunto que tenha sido segregado *antes* de `propor` ranquear — os mesmos runs
que geraram a recomendação podem estar no "held-out".

Probe: `test_U2_proveniencia_held_out_e_puramente_declarativa`.

`test_hardening_h09c.py::test_identidade_e_proveniencia_whitespace_sao_vetadas`
prova apenas que `"   "` é rejeitado. Rejeitar whitespace não é validar proveniência.

## 🟡 5 — Nada confere que `de` é o titular vigente do slot

`preparar_promocao_gated` (`curador.py:383-402`) monta `de`/`para` a partir de
`recomputada["titular"]["modelo"]` / `["candidato"]["modelo"]`, que vêm de
`proposta["titular"]`/`["candidato"]` — strings livres em `curador.py:238-240`.
`grep -n "catalogo" motor/curador.py` retorna só um comentário de docstring: o
módulo **não lê catálogo nenhum**.

A intenção apresentada ao gate humano pode portanto dizer "de: modelo-X" quando o
titular real do slot é outro, ou apontar para um slot que não existe. O gate humano
é a última defesa e recebe um par não verificado.

Probe: `test_U3_repositorio_e_a_unica_autoridade_mas_nao_valida_nada` — um
repositório arbitrário com `.obter()` devolvendo evidência sintética e decisão
consistente gera `promocao_pendente` para o slot `executor/t1` com titular
`gpt-caro`, sem que nada confirme que esse é o titular vigente.

Observação de contexto: não existe hoje nenhuma `RepositorioCertificacoes` de
produção — `grep` não encontra chamador de `preparar_promocao_gated` fora dos
testes. Isso já consta como dívida 3 do `INVARIANTES.md`; o achado aqui é que,
quando esse repositório existir, ele herda **toda** a autoridade sem que o curador
faça qualquer verificação cruzada.

## 🟡 6 — U1 é literalmente falso: `deepcopy` não garante isolamento

U1 promete "isolada por cópia profunda: mutação/alias do runner não altera casos".
`_executar_runner` (`curador.py:424`) faz `runner(deepcopy(caso), modelo)`.
`deepcopy` respeita `__deepcopy__`; um valor aninhado que devolve `self` entrega
ao runner um **alias vivo** do caso original.

Probe: `test_U1_deepcopy_e_furavel_por_objeto_que_se_devolve` — o runner muta o
objeto e o caso held-out original muda em memória.

`test_hardening_h08.py::test_falha_ao_copiar_caso_intermediario_nao_aborta_sombra`
testa o caso oposto (um `__deepcopy__` que **levanta**) e conclui robustez a partir
dele. O caso que quebra o invariante — `__deepcopy__` que devolve `self` — não é
testado.

Severidade média e não alta porque casos normalmente vêm de JSON, onde todos os
tipos são deepcopiáveis por valor. Mas o invariante como escrito ("mutação ou
alias do runner não altera casos") está falso, e a defesa correta é validar que o
caso é JSON-serializável na entrada, não confiar em `deepcopy`.

## 🟡 7 — O score de `propor` ignora incompletas e mistura denominadores

`_item_ranking`, `curador.py:1356-1357`:

```python
score = round(metricas["taxa_aprovacao_primeira"] - metricas["taxa_erro"] - (1.0 - convergencia), 4)
```

Dois problemas:

1. `taxa_incompletas` **não entra no score**. Um modelo cujas chamadas simplesmente
   nunca terminam (`curador.py:982-984`) não é penalizado. `_modelos_a_evitar`
   (`curador.py:1375-1388`) só barra a partir de `limiar_falha=0.5`; com 49% de
   incompletas o modelo é recomendado limpo.
2. `taxa_aprovacao_primeira` tem denominador `verifier_julgados`; `taxa_erro` tem
   denominador `chamadas` (`curador.py:1480-1482`). Subtrair uma da outra é
   aritmética entre populações diferentes.

Probe: `test_propor_score_ignora_incompletas_e_mistura_denominadores` — modelo com
40% de incompletas é o `recomendado`.

Impacto: `propor` é o que escolhe o candidato que vai à sombra. Um filtro de
entrada enviesado alimenta todo o resto do funil.

## 🟢 8 — `BaseException` no runner aborta a sombra inteira

`curador.py:423-426` captura `Exception`. Um runner que levante `SystemExit` —
e o próprio módulo usa `raise SystemExit` em `_ler_json_path`/`_parse_custo`
(`curador.py:1257`, `1281`) — propaga e mata os casos seguintes, contrariando o
"falha de um caso não aborta os seguintes" de U1.

Probe: `test_U1_baseexception_no_runner_aborta_a_sombra_inteira`.

## 🟢 9 — `casos_ignorados` fica fora do selo

`_selo_sombra` (`curador.py:481-484`) cobre `versao, status, slot, modelos,
politica, casos` — **não** `casos_ignorados` (`curador.py:270`). O certificador não
vê quantos casos foram descartados pelo filtro de slot de `curador.py:244-248`,
então não consegue detectar cherry-picking pela contagem. Baixo apenas porque o
achado 2 já torna o cherry-picking desnecessário.

## 🟢 10 — `min_amostras=3` default em `propor`

`curador.py:159`. Três julgamentos de verifier não distinguem modelos. É um default
de ferramenta exploratória, e a proposta é read-only, mas alimenta a sombra.

---

## Onde NÃO encontrei nada ≥ média

Áreas que auditei e considerei sólidas:

- **A ordem de decisão de `certificar_sombra`** (`curador.py:305-332`) está correta:
  qualidade é avaliada **antes** de custo e com `>` estrito; custo nunca entra como
  crédito compensatório. Dado uma evidência confiável, **não achei caminho pelo qual
  o custo aprove uma regressão de qualidade**. Empate de qualidade rejeita.
- **Validação de tipos numéricos**: `_custo_sombra_valido` / `_taxa_sombra_valida`
  (`curador.py:545-550`) usam `type(v) in (int, float)`, o que corretamente exclui
  `bool`, e checam `isfinite`. `_selo_sombra` usa `allow_nan=False`, então NaN
  quebra o selo antes de virar métrica. `_media_custos` (`curador.py:553-557`) é
  média incremental e resiste a overflow (comprovado em h09c).
- **Custo parcial**: `_ContadorSombra.resumo` (`curador.py:586-598`) exige custo
  válido em **todos** os casos, senão devolve `None` → "custo incomparável". Fecha
  a porta de diluir custo omitindo casos.
- **A fronteira "intenção, não aplicação"**: `preparar_promocao_gated` só devolve
  `status: "promocao_pendente"` com `requer_gate: True` e emite
  `curador.promocao_pendente`. Não há escrita de catálogo, evento `curador.promoveu`
  ou side effect em lugar nenhum do módulo — confirmado por grep. **K4 se sustenta.**
- **Fail-closed sem repositório**: `curador.py:364-369` e o caminho da CLI
  (`curador.py:856-858`, que nunca passa repositório) vetam por default. Correto.
- **`carregar_runs`** tolera JSON malformado sem crash e contabiliza (`curador.py:35-39`).

O padrão dos achados é consistente: **o curador é rigoroso na aritmética e frouxo
na proveniência.** Toda validação forte incide sobre números que o próprio chamador
forneceu. A camada que falta não é mais checagem de tipo — é amarrar cada número da
evidência a um evento do ledger v2.
