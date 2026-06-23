# HANDOFF — Biblioteca de Rotas B2: planner ESCOLHE a rota do catálogo (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR. Spec travada. **Não relitigar.**
> 1 commit. `python3 -m pytest -q` VERDE ao fim (hoje **184 passed**). Ambiguidade → `## DÚVIDAS`.
> Pré-requisito: B1 commitado (eef596a). Rode `pytest -q` antes e confirme 184.

## Contexto (o que B2 faz e o que NÃO faz)

B1 deu ao planner a CAPACIDADE de ser parametrizado por uma rota (padrao+gabarito), mas a rota
era escolhida **explicitamente** (`--rota`). B2 faz o **planner ESCOLHER a rota** do catálogo a
partir da missão — é o que destrava "prompt qualquer → formato certo de decomposição".

A escolha é **fuzzy (um passo de classificação por modelo)**, por decisão estratégica: escolher
rota é julgamento semântico sobre o texto cru da missão (no momento da escolha ainda não há tags;
as `capacidades_requeridas` do R2a/R2b nascem depois, na decomposição). A segurança vem da rede
determinística que JÁ existe: a rota só decide o FORMATO, e tudo passa por verifier + cobertura +
**gate de revisão do plano** (o humano/Jarvis vê o `padrao` escolhido e pode abortar/editar). Com
fallback pra rota default, B2 é **inerte e seguro** quando não há catálogo ou a escolha falha.

**B2 NÃO faz:** calibração (afinar o prompt de seleção é RUN REAL do Caio, depois — igual R2b);
não cria rota nova; não toca roteamento de modelo (`modelos.py`), verifier, evaluator.

**Inércia (guarda-corpo):** sem catálogo de rotas passado, o comportamento é **byte-idêntico** ao
de hoje (usa `ROTA_DEFAULT`). Os **184 testes seguem verdes**.

## Leis (não quebrar)

1. 1 commit pequeno. `pytest -q` VERDE (184; inerte por default).
2. Nunca apagar/afrouxar teste existente.
3. **Precedência:** rota explícita (`--rota` / `rota=`) VENCE a escolha automática. Catálogo
   presente + sem rota explícita → planner escolhe. Sem catálogo → `ROTA_DEFAULT` (inércia).
4. Escolha inválida/vazia (modelo não devolve um nome do catálogo) → **fallback `ROTA_DEFAULT`**,
   nunca erro, nunca rota inventada. Loga o fallback.
5. Não tocar `modelos.py`/verifier/evaluator. A chamada de seleção usa um papel já roteável
   (use o papel `"planner"` — barato/forte conforme a tabela do Caio decide; NÃO criar provedor novo).
6. Python 3.14, stdlib + deps do `pyproject.toml`. Sem dep nova.
7. Português nos comentários. Ambiguidade → `## DÚVIDAS`.

## Mapa do código (pontos de integração)

```
motor/grafo.py     montar_prompt_planner(...rota) e ROTA_DEFAULT (B1) — INTACTOS.
                   construir_grafo(..., rota=None) (B1).
                   >>> ADICIONA: param `rotas: dict[str,dict] | None = None` (o CATÁLOGO);
                       PROMPT_SELETOR_ROTA; passo de seleção no planner; evento rota.escolhida.
motor/__main__.py  --rota carrega 1 rota (B1).
                   >>> ADICIONA: quando há --registro e NÃO há --rota, carrega o catálogo
                       (rotas_de_registro) e passa como `rotas=` (liga a escolha automática).
motor/servico.py   GerenciadorJobs monta construir_grafo (R3).
                   >>> ADICIONA: se dir_registro setado, carrega o catálogo e passa `rotas=`
                       (o caminho MCP/Jarvis também ganha escolha automática).
tests/             ADICIONA casos em tests/test_rotas.py (stub de seleção).
```

## Passos (FIXADOS)

### 1. PROMPT_SELETOR_ROTA
Prompt curto que recebe a missão + a lista `{nome, quando}` das rotas do catálogo e devolve
**apenas** o nome escolhido (string simples ou JSON `{"rota": "<nome>"}` — escolha um e teste-o).
Instrução-chave: "escolha a rota cujo `quando` melhor descreve a missão; se nenhuma servir
claramente, responda `pesquisa-sintese`". Mantém o modelo num veredito objetivo, não-criativo.

### 2. Passo de seleção no planner (grafo.py)
No nó `planner`, antes de montar o prompt:
```
rota_ativa = rota                                   # rota explícita vence (B1)
if rota_ativa is None and rotas:                    # catálogo presente → escolher
    nome = _escolher_rota(cliente, state["missao_texto"], rotas, log)
    rota_ativa = rotas.get(nome) or ROTA_DEFAULT
# rota_ativa is None e sem catálogo → montar_prompt_planner usa ROTA_DEFAULT (inércia)
```
`_escolher_rota`: chama `cliente.chamar("planner", PROMPT_SELETOR_ROTA.format(...))`, faz parse
do nome, valida que está em `rotas`; inválido/vazio → devolve nome da default (`pesquisa-sintese`
se existir no catálogo, senão sinaliza usar `ROTA_DEFAULT`). **Sempre** loga
`log.evento("rota.escolhida", rota=<nome>, padrao=<padrao>, fallback=<bool>)` — é o que torna a
calibração observável depois.
Passe `rota=rota_ativa` ao `montar_prompt_planner`.

### 3. Ligar o catálogo nas duas superfícies
- `__main__.py`: com `--registro` e **sem** `--rota`, carregue `rotas_de_registro(dir_registro)`
  e passe `rotas=` a `construir_grafo`. Com `--rota`, mantém o comportamento B1 (rota explícita).
- `servico.py` (GerenciadorJobs): se `self.dir_registro`, carregue o catálogo uma vez e passe
  `rotas=` ao `construir_grafo`. (Assim o caminho MCP/Jarvis também escolhe rota.)

### 4. Inércia preservada
Sem catálogo (`rotas=None`) e sem `rota` → `montar_prompt_planner` cai em `ROTA_DEFAULT`, prompt
byte-idêntico ao de hoje. Nenhum dos 184 muda.

## DoD (tests/test_rotas.py + checagens)

1. **Inércia:** sem `rotas` e sem `rota` → prompt byte-idêntico (já coberto no B1); suíte **184 verde**.
2. **Escolha automática:** `construir_grafo(..., rotas=<catálogo 2 rotas>)` com um `ClienteStub`
   cujo seletor devolve `"construcao"` → o spec gerado sai com `padrao: grafo_dependencias` e o
   evento `rota.escolhida` (rota=construcao) é logado.
3. **Fallback seguro:** stub de seleção devolve lixo / nome fora do catálogo → usa `ROTA_DEFAULT`
   (fan_out), `rota.escolhida` com `fallback=true`, **sem erro**.
4. **Precedência:** `rota=` explícita + `rotas=` catálogo → usa a explícita, **não** chama o seletor.
5. **e2e:** com seleção → `grafo_dependencias` → roda pelo nó `executar_grafo_dep` sem erro
   (stub devolve spec com `depende_de` válido, shape de `exemplos/grafo-dep-minimo.json`).

## Fronteira / FUTURO (não fazer em B2)

- **Calibração** (afinar PROMPT_SELETOR_ROTA observando escolhas reais) = RUN do Caio, depois.
  B2 só entrega o mecanismo + a observabilidade (`rota.escolhida`).
- Não criar rota nova, não mexer em roteamento de modelo/verifier/evaluator.
- Custo por rota / certificação por rota / `capacidades_tipicas`: futuros (fases D+).

## Nota de calibração (pro Caio, pós-merge)
Depois do merge, rode uma missão de TEXTO aberto com `--registro <dir com rotas+modelos>` (sem
`--rota`) e observe `rota.escolhida` no `log.jsonl`: confira se a rota batente com o tipo de
missão. Se errar, é só afinar o PROMPT_SELETOR_ROTA (texto), não o mecanismo. Traga o log que eu reviso.

## DÚVIDAS
- (vazio)
