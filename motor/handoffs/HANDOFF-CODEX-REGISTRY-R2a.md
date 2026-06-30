# HANDOFF — Registry-cérebro, Corte R2a (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR. Spec travada. **Não relitigar.**
> Interface FIXADA, testes a montante como DoD, ambiguidade ESCALA (`## DÚVIDAS`).
> Pré-requisito: R1 commitado (`cliente_de_registro`, 124 passed). Confira com
> `python3 -m pytest -q` antes de começar.

## Contexto (o que R2a faz e o que NÃO faz)

R1 trocou a FONTE do roteamento (JSON → entidades `.md`), mas o binding continua
MANUAL: a entidade declara `papeis`/`tiers`. R2a adiciona o **cérebro**: seleção
automática do **executor mais barato cujas capacidades cobrem o requisito da tarefa**.

R2a é só o MECANISMO de seleção, dirigível por uma spec escrita à mão (subagente com
`capacidades_requeridas`). **R2a NÃO mexe no prompt do planner** — fazer o planner
EMITIR capacidades sozinho é o R2b (outro corte, com o Claude). Não faça R2b aqui.

**Filosofia de segurança (igual ao R1):** o mecanismo é ADITIVO e **inerte sem
catálogo**. Sem `catalogo` e sem `capacidades_requeridas`, o roteamento é byte-idêntico
ao de hoje → os 124 testes têm que ficar VERDES. Esse é o guarda-corpo.

## Leis (não quebrar)

1. **1 corte = 1 commit** pequeno. Commitar ao fim.
2. **Nunca apagar nem afrouxar teste existente.** `python3 -m pytest -q` VERDE ao fim
   (hoje **124 passed**). Os 124 NÃO PODEM mudar de resultado — R2a é inerte por default.
3. **Não mudar a SEMÂNTICA testada** de pin/tier/papel/esgotado/guard-do-juiz. Você VAI
   adicionar uma rung nova e um kwarg novo, mas só ATIVOS quando há catálogo+capacidades.
4. **Ambiguidade não se chuta — para e anota** em `## DÚVIDAS`.
5. Python 3.14, **só stdlib** + deps do `pyproject.toml`. Sem dep nova sem anotar.
6. Português nos comentários, como o resto do repo.

## Mapa do código (pontos de integração exatos)

```
motor/spec.py     class Subagente (linha ~22): papel, objetivo, rubrica, tier(opcional).
                  >>> ADICIONA: capacidades_requeridas: list[str] = [] (opcional).
motor/modelos.py  ClienteModelo(Protocol).chamar(papel, prompt, ferramentas, tier, timeout)
                  ClienteStub.chamar(...) / ClienteCodex / ClienteClaudeCLI /
                  ClienteOpenCode / ClienteOpenAICompat.chamar(...)
                  ClienteRoteador: _resolver(papel,tier,ferramentas,emitir),
                  provedor_de(papel,tier,ferramentas), chamar(...,evitar), _disponivel,
                  _outro_provedor, _eh_pin.
                  >>> ADICIONA: kwarg `capacidades` uniforme + `catalogo` no roteador +
                      selecionar_por_capacidade + rung nova em _resolver.
motor/registro.py cliente_de_registro(pasta, log) — monta o ClienteRoteador.
                  >>> ADICIONA: construir o `catalogo` das entidades e passá-lo ao roteador.
motor/grafo.py    L133/190: cliente.provedor_de(sub["papel"], sub.get("tier"), sub.get("ferramentas"))
                  L197-203: cliente.chamar(sub["papel"], ..., ferramentas=..., tier=sub.get("tier"))
                  L209-212: cliente.chamar("verifier", ..., **kw_verifier)  # kw_verifier={"evitar":prov_exec}
                  >>> ADICIONA: passar capacidades=sub.get("capacidades_requeridas") nas
                      chamadas do EXECUTOR (provedor_de + attempt). O verifier NÃO recebe
                      capacidades (ele roteia por papel "verifier" + evitar).
tests/            pytest, ClienteStub. NÃO apagar.
```

---

## R2a — passos (FIXADOS)

### 1. `spec.py` — Subagente ganha capacidades_requeridas
```python
capacidades_requeridas: list[str] = Field(
    default_factory=list,
    description="capacidades que a tarefa exige (ex.: codigo, redacao, calculo). "
                "Vazio → roteia por tier/papel como antes. O cliente escolhe o "
                "executor mais barato que cobre TODAS estas capacidades.")
```
Vazio por default → specs existentes inalteradas.

### 2. `modelos.py` — kwarg `capacidades` uniforme (igual ao que foi feito com `tier`)
Adicione `capacidades: Optional[list[str]] = None` à assinatura `chamar` do **Protocol**
e de **todos** os clientes (Stub, ClaudeCLI, Codex, OpenCode, OpenAICompat). Os
transportes **ignoram** `capacidades` (como já ignoram `tier`) — é sinal de roteamento,
consumido só pelo ClienteRoteador. Isso mantém a fronteira: o grafo segue cego a modelos.

### 3. `modelos.py` — ClienteRoteador ganha `catalogo` + seleção

Construtor: novo param `catalogo: Optional[list[tuple]] = None`, guardado como
`self.catalogo`. Cada entrada = `(cliente, frozenset[str] capacidades, int custo_ordem)`.
Default vazio → rung inerte.

```python
def selecionar_por_capacidade(self, capacidades, evitar=None, emitir=True):
    """Mais barato (menor custo_ordem) cujas capacidades ⊇ `capacidades`, com
    provedor NÃO esgotado e (se `evitar`) provedor != `evitar`. Nenhum → None.

    Regra do juiz (FIXADA): com `evitar` setado, NUNCA devolve cliente no provedor
    `evitar`. Se os únicos capazes estão todos em `evitar`, devolve None — a chamada
    cai no padrão (claude, o juiz confiável), nunca num modelo incapaz e nunca
    quebrando a independência cross-model."""
    req = set(capacidades or ())
    candidatos = [
        (ordem, i, cli) for i, (cli, caps, ordem) in enumerate(self.catalogo)
        if req <= caps
        and getattr(cli, "provedor", None) not in self.esgotados
        and (evitar is None or getattr(cli, "provedor", None) != evitar)
    ]
    if not candidatos:
        return None
    candidatos.sort()                      # menor custo_ordem; empate → ordem estável (i)
    return candidatos[0][2]
```

### 4. `modelos.py` — rung nova em `_resolver` (PRECEDÊNCIA TRAVADA)

Precedência final: **pin > tier > capacidade > papel > padrão**. Racional: pin e tier
são sinais EXPLÍCITOS (humano/planner); a capacidade é o cérebro AUTOMÁTICO — explícito
vence automático (menor surpresa; consistente com pin>tier de hoje). A rung de
capacidade só dispara quando NÃO há pin, NÃO há tier-na-tabela, HÁ `capacidades` e o
catálogo cobre.

`_resolver` ganha os params `capacidades=None` e `evitar=None`:
```python
def _resolver(self, papel, tier, ferramentas, capacidades=None, evitar=None, emitir=True):
    pin = ...
    if pin is not None:
        cliente = pin; (evento modelo.pin se emitir)
    elif tier and tier in self.tiers:
        cliente = self.tiers[tier]; (evento modelo.roteado_tier se emitir)
    elif capacidades and self.catalogo:
        cli = self.selecionar_por_capacidade(capacidades, evitar=evitar, emitir=emitir)
        if cli is not None:
            cliente = cli
            if emitir: self._evento("modelo.roteado_capacidade", papel=papel,
                                    capacidades=list(capacidades),
                                    provedor=getattr(cli, "provedor", None))
        else:
            if emitir: self._evento("registro.sem_executor", papel=papel,
                                    capacidades=list(capacidades))
            cliente = self.mapa.get(papel, self.padrao)   # cai no papel/padrão
    else:
        cliente = self.mapa.get(papel, self.padrao)
    cliente = self._disponivel(cliente, papel, emitir=emitir)   # esgotamento, como hoje
    # ... desvio de ferramentas EXATAMENTE como hoje ...
    return cliente
```
> A rung de capacidade já honra `evitar` internamente (devolve provedor != evitar).
> Logo o guard genérico em `chamar` continua igual e fica INERTE pra esse caminho
> (o cliente já é != evitar). Não toque na lógica do guard genérico.

### 5. `modelos.py` — threading de `capacidades`/`evitar`
- `provedor_de(papel, tier=None, ferramentas=None, capacidades=None)` → passa
  `capacidades` e `evitar=None` ao `_resolver(..., emitir=False)`.
- `chamar(papel, prompt, ferramentas=None, tier=None, timeout=300, evitar=None,
  capacidades=None)` → passa `capacidades` E `evitar` ao `_resolver`. (Hoje o `chamar`
  resolve com `_resolver(papel,tier,ferramentas)` e depois aplica o guard; agora o
  `_resolver` recebe `evitar` e `capacidades`; o guard genérico pós-resolução
  permanece para os caminhos pin/tier/papel.)

### 6. `registro.py` — construir o catálogo
Entidades cujo frontmatter tem `capacidades` (lista não-vazia) entram no catálogo:
`(cliente_da_entidade, frozenset(capacidades), int(custo_ordem or 0))`. Entidade sem
`capacidades` NÃO entra no catálogo (segue só no binding manual papel/tier). Passe
`catalogo=...` ao `ClienteRoteador`. (O `cliente_de_config` do JSON pode ficar sem
catálogo por enquanto — catálogo é feature do Registry; não force no JSON.)

### 7. `grafo.py` — passar capacidades nas chamadas do EXECUTOR
- L~133 e L~190 (`provedor_de`): adicionar `capacidades=sub.get("capacidades_requeridas")`.
- L~197-203 (attempt do subagente): adicionar `capacidades=sub.get("capacidades_requeridas")`.
- **NÃO** passar capacidades na chamada do verifier/evaluator/synthesizer/planner.

### DoD (tests/test_capacidade.py + 1 e2e em test_grafo.py)

Monte o catálogo com `ClienteStub`s rotulados por provedor (use `ClienteStub` com um
atributo `.provedor` setado à mão, ou pequenos fakes com `.provedor` e `.chamar`).
1. **Mais barato capaz:** catálogo `[(cheap caps{x,y} ordem1, prov A), (exp caps{x,y}
   ordem5, prov B)]`; `provedor_de("p", capacidades=["x"])` → A (menor ordem).
2. **Cobertura:** `capacidades=["x","z"]` sem entrada que cubra z → evento
   `registro.sem_executor` e cai no padrão (`provedor_de` → "claude").
3. **Independência do juiz:** dois capazes (A barato, B caro); `provedor_de("verifier",
   capacidades=["x"], )` chamado com `evitar="A"` (via `chamar(..., evitar="A",
   capacidades=["x"])`) → escolhe B; e se SÓ A é capaz e `evitar="A"` → cai no padrão
   (None), nunca A.
4. **Esgotado:** provedor do capaz mais barato em `esgotados` → escolhe o próximo capaz.
5. **Precedência:** subagente com `tier` na tabela E `capacidades` → vence o tier
   (rung de capacidade não consultada; nenhum evento `modelo.roteado_capacidade`).
6. **Compat:** catálogo vazio / sem capacidades → roteamento idêntico; **os 124 seguem
   verdes**.
7. **e2e (test_grafo):** spec com um subagente `capacidades_requeridas=["x"]` e catálogo
   stub → o subagente é executado pelo cliente do catálogo (evento
   `modelo.roteado_capacidade` no log).

---

## FUTURO — R2b (NÃO fazer; é com o Claude)

Fazer o **planner EMITIR `capacidades_requeridas`** sozinho, a partir de um VOCABULÁRIO
CONTROLADO de capacidades (ex.: `codigo`, `redacao`, `calculo`, `raciocinio-longo`,
`pesquisa`) — as MESMAS tags têm que estar nas entidades do Registry, senão nada casa.
Isso mexe no `PROMPT_PLANNER` + exige um run real pra calibrar (saída de LLM é fuzzy) +
a decisão do vocabulário. Fica pro Claude a montante. Também futuro: `custo_max` por
subagente (teto que FORÇA escalar em vez de pagar caro). **Não improvise R2b nem custo_max
aqui.**

---

## DÚVIDAS
(Codex: escreva aqui o que travou, em vez de chutar.)
