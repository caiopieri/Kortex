# HANDOFF — Biblioteca de Rotas B1: rota como entidade + planner parametrizável (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR. Spec travada. **Não relitigar.**
> 1 commit. `python3 -m pytest -q` VERDE ao fim (hoje **173 passed**). Ambiguidade → `## DÚVIDAS`.
> Pré-requisito: rode `python3 -m pytest -q` antes e confirme 173.

## Contexto (o que B1 faz e o que NÃO faz)

Hoje o planner (`PROMPT_PLANNER`, grafo.py ~L52) **crava `padrao = "fan_out_sintese"`** e
"depende_de sempre []". Ele só sabe UMA estratégia de decomposição. O padrão
`grafo_dependencias` existe no schema e no grafo (`rota_pos_plano` L219–222 roteia pra
`executar_grafo_dep`), mas o planner **nunca o emite** — só se obtém escrevendo a spec à mão.

B1 introduz **rota** como uma estratégia de decomposição nomeada, carregada do Registry
(igual executores e ferramentas já são entidades). O planner passa a ser **parametrizável por
rota** (padrão + gabarito injetados no prompt). 

**B1 NÃO faz o planner ESCOLHER a rota** — isso é B2 (fuzzy, exige calibração, fica com o
Claude a montante). Em B1 a rota é selecionada explicitamente (`--rota <nome>`); sem rota, o
comportamento é **byte-idêntico ao de hoje**.

**Filosofia de segurança (igual R1/R2a):** ADITIVO e **inerte sem rota**. A rota default
reproduz o prompt atual ao caractere → os **173 testes seguem verdes**. Esse é o guarda-corpo.

## Leis (não quebrar)

1. 1 commit pequeno. `pytest -q` VERDE ao fim (173, não podem mudar de resultado — B1 inerte por default).
2. Nunca apagar/afrouxar teste existente.
3. **A rota default DEVE reproduzir o `PROMPT_PLANNER` de hoje ao caractere** (mesma string
   montada quando nenhuma rota é passada). Se o texto montado divergir, os testes do planner
   quebram — esse é o sinal de que você errou.
4. **Não** mexer em roteamento de modelo (`modelos.py`), verifier, evaluator, nem nos padrões
   de execução (`fan_out_sintese`/`grafo_dependencias` já existem — você só deixa o planner
   EMITIR um deles, não cria padrão novo).
5. Python 3.14, stdlib + deps do `pyproject.toml`. Sem dep nova.
6. Português nos comentários.
7. Ambiguidade → `## DÚVIDAS`, não chutar.

## Mapa do código (pontos de integração)

```
motor/registro.py   ferramentas_de_registro(pasta) (L167–183) lê entidades tipo:ferramenta.
                    >>> ADICIONA rotas_de_registro(pasta) ANÁLOGO: lê tipo:rota.
motor/spec.py       padrao: Literal["fan_out_sintese","grafo_dependencias"] (L62-ish) — INTACTO.
                    >>> (opcional) modelo Rota pydantic p/ validar a entidade; ou validar no loader.
motor/grafo.py      PROMPT_PLANNER (L52) crava padrao+depende_de[]; planner() (L142) formata e
                    chama; construir_grafo(...) assinatura.
                    >>> PARAMETRIZA o prompt por rota (padrao+gabarito); construir_grafo ganha
                        kwarg `rota=None` (default = rota fan_out embutida = texto de hoje).
motor/__main__.py   parsing de flags (--modelos/--registro/--workspace...).
                    >>> ADICIONA --rota <nome> (carrega do dir de --registro; sem --registro e
                        com --rota = erro claro). Sem --rota → rota default.
tests/              NÃO apagar. ADICIONA tests/test_rotas.py.
```

## Passos (FIXADOS)

### 1. Entidade `tipo: rota` + loader
`rotas_de_registro(pasta) -> dict[str, dict]` (espelha `ferramentas_de_registro`): lê `*.md`
com `tipo: rota`, indexa por `nome`. Campos da entidade:
- `nome` (str, obrigatório; duplicado → ValueError, igual ferramenta).
- `padrao` (`fan_out_sintese` | `grafo_dependencias`; obrigatório; outro valor → ValueError).
- `quando` (str; descrição de quando a rota se aplica — **usado só em B2**, mas já carregado).
- `gabarito` (str; instruções de decomposição injetadas no PROMPT_PLANNER).

### 2. PROMPT_PLANNER parametrizável
Hoje o trecho fixo é (L60 e a regra de depende_de):
```
Regras: entre 2 e {max_sub} subagentes focados e INDEPENDENTES (depende_de sempre []);
...
padrao = "fan_out_sintese".
```
Troque o que é específico de rota por placeholders `{padrao}` e `{gabarito}`. O resto do prompt
(tier, capacidades_requeridas, rubricas mecânicas) **fica idêntico**. O `gabarito` da rota
default deve conter EXATAMENTE o texto de hoje (subagentes INDEPENDENTES, depende_de []), de
modo que, sem rota, a string montada seja byte-idêntica. Para `grafo_dependencias`, o gabarito
instrui o planner a emitir `depende_de` formando o grafo (ex.: "decomponha em etapas
dependentes; cada subagente declara `depende_de` com os ids dos quais consome a saída").

### 3. Rota default embutida (inércia)
`construir_grafo(..., rota=None)`. Quando `rota is None`, use uma rota default embutida no
código com `padrao="fan_out_sintese"` e `gabarito` == texto atual. **Critério-chave:** a string
final do PROMPT_PLANNER com `rota=None` == a de hoje (teste compara, ver DoD).

### 4. CLI `--rota <nome>`
Em `__main__.py`: `--rota <nome>` carrega `rotas_de_registro(dir_registro)[nome]` e passa a
`construir_grafo(rota=...)`. `--rota` sem `--registro` → erro claro (`return 2`). Nome
inexistente no catálogo → erro claro. Sem `--rota` → `rota=None` (default).

### 5. Catálogo-semente (demonstra o mecanismo)
`exemplos/registro-rotas/` com 2 entidades:
- `pesquisa-sintese.md` (`padrao: fan_out_sintese`, gabarito = comportamento default; `quando`:
  "perguntas, levantamentos, comparações — subagentes independentes + síntese").
- `construcao.md` (`padrao: grafo_dependencias`, gabarito = decomposição em etapas dependentes;
  `quando`: "produzir/implementar algo em etapas que dependem umas das outras (design→build→validação)").

## DoD (tests/test_rotas.py + checagens)

1. **Inércia:** `construir_grafo(...)` sem rota → o PROMPT_PLANNER montado é **byte-idêntico** ao
   de hoje (teste compara a string formatada; ou um teste de regressão do texto). Suíte = **173 verdes**.
2. **Loader:** `rotas_de_registro(exemplos/registro-rotas)` devolve as 2 rotas com `padrao`
   corretos; entidade sem `padrao` → ValueError; `padrao` inválido → ValueError; nome duplicado → ValueError.
3. **Parametrização:** com a rota `construcao` (grafo_dependencias) passada, a string do
   PROMPT_PLANNER contém o gabarito de dependências e NÃO a frase "depende_de sempre []".
4. **CLI:** `--rota` sem `--registro` → erro/return 2; `--rota nome-inexistente` → erro claro.
5. **e2e com stub:** um `ClienteStub` cujo planner devolve uma spec `grafo_dependencias` válida
   (com `depende_de`) roda pelo nó `executar_grafo_dep` (já existe) sem erro — confirma que a
   rota não-default flui ponta-a-ponta. (Use o shape de `exemplos/grafo-dep-minimo.json`.)

## Fronteira / FUTURO (não fazer em B1)

- **B2 (planner escolhe a rota):** o planner casar missão→`quando` e selecionar a rota sozinho.
  Fuzzy, exige calibração em run real. Fica com o Claude a montante. NÃO fazer aqui.
- Não criar padrão de execução novo; não tocar roteamento de modelo/verifier/evaluator.
- `capacidades_tipicas` / custo por rota / certificação por rota: futuros.

## DÚVIDAS
- (vazio)
