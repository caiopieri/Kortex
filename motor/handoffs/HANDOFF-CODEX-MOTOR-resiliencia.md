# HANDOFF — Motor: resiliência de provedor (cadeia de failover + auto-esgotamento) — Codex executa, Claude verifica

> 1 commit. `python3 -m pytest -q` VERDE ao fim (hoje **189 passed**). **INERTE por default**
> (ligado só por config) → os 189 não mudam. Ambiguidade → `## DÚVIDAS`. Não relitigar.

## Por que (validado em 5 runs reais)
Hoje, quando o modelo resolvido falha (rate-limit, crédito, SSL, lentidão, erro), o
`ClienteRoteador.chamar` (modelos.py) **só tenta o `padrao` UMA vez** e **não marca o provedor
como esgotado**. Resultado real observado: um provedor estoura no meio da missão → cada nó
seguinte re-bate no mesmo provedor morto → cascata → missão perdida inteira (`synthesizer não
respondeu`). O Caio precisa que o motor **desça/suba a escada de provedores sozinho**: tenta o
mais barato; se falha, vai pro próximo da cadeia (ordenada por custo); marca o que falhou como
esgotado pra não re-tentar no resto da missão; e só sobe pro caro se nada barato responder.

Isto é o **viabilizador do modo barato**: sem ele, não dá pra confiar em modelos free/baratos
(eles falham e matam a missão). Com ele, free→barato→caro vira uma cadeia auto-curável.

## Decisão de design (TRAVADA)
- **Inerte por default (guarda-corpo igual R1/R2a/B1):** novo flag `auto_esgotar: bool = False`
  no `ClienteRoteador`. `False` → comportamento de hoje BYTE-idêntico (resolve → tenta → se None
  e ≠ padrao, tenta padrao uma vez, evento `modelo.fallback`). Os 189 testes ficam verdes.
- `True` → liga o **failover em cadeia** + **auto-esgotamento**.
- A cadeia é **ordenada por custo** (mais barato primeiro). Quem constrói a cadeia
  (`cliente_de_config`/`cliente_de_registro`) deve ordená-la por `custo_ordem` crescente.
- **Não** mexer em: `_resolver` (pin>tier>capacidade>papel>padrao), guard do juiz, pins,
  `selecionar_por_capacidade`. Só o comportamento de FALHA do `chamar`.

## Mudança (modelos.py, só `ClienteRoteador`)

### 1. Flag + construtor
`__init__` ganha `auto_esgotar: bool = False` (guardar em `self.auto_esgotar`).

### 2. `chamar` — failover em cadeia quando `auto_esgotar` ligado
Mantém a resolução + guard do juiz como está. Troca SÓ o trecho pós-`cliente.chamar`:

```python
resposta = cliente.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                          timeout=timeout, capacidades=capacidades)
if resposta is not None:
    return resposta

if not self.auto_esgotar:
    # comportamento ATUAL (inalterado): tenta padrao uma vez
    if cliente is not self.padrao:
        alvo = self._disponivel(self.padrao, papel)
        if alvo is not cliente:
            self._evento("modelo.fallback", papel=papel)
            resposta = alvo.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                                   timeout=timeout, capacidades=capacidades)
    return resposta

# auto_esgotar ON: marca o que falhou e caminha a cadeia ordenada por custo
self._auto_esgotar(cliente, papel, motivo="sem resposta")
ja_tentados = {id(cliente)}
for alt in self._cadeia_failover():        # cost-ordered, não-esgotado, exclui já-tentados
    if id(alt) in ja_tentados:
        continue
    ja_tentados.add(id(alt))
    self._evento("modelo.fallback", papel=papel, para=getattr(alt, "provedor", None))
    resposta = alt.chamar(papel, prompt, ferramentas=ferramentas, tier=tier,
                          timeout=timeout, capacidades=capacidades)
    if resposta is not None:
        return resposta
    self._auto_esgotar(alt, papel, motivo="sem resposta")
return None
```

### 3. Helpers novos
```python
def _auto_esgotar(self, cliente, papel, motivo: str) -> None:
    prov = getattr(cliente, "provedor", None)
    if prov and prov not in self.esgotados:
        self.esgotados.add(prov)                      # sticky NO RESTO da missão
        self._evento("provedor.auto_esgotado", provedor=prov, papel=papel, motivo=motivo)

def _cadeia_failover(self) -> list["ClienteModelo"]:
    # cadeia (já ordenada por custo na construção) + padrao, só não-esgotados
    vistos, saida = set(), []
    for alt in [*self.cadeia, self.padrao]:
        prov = getattr(alt, "provedor", None)
        if prov in self.esgotados or prov in vistos:
            continue
        vistos.add(prov); saida.append(alt)
    return saida
```

### 4. Ligar por config (cliente_de_config e cliente_de_registro)
- Ler `auto_esgotar` da config (`cfg.get("auto_esgotar", False)`) e passar ao `ClienteRoteador`.
  No registro, aceitar um campo equivalente (ex.: entidade especial ou parâmetro) — ou só por
  `cliente_de_config`; se for trabalho a mais no registro, anote em DÚVIDAS e faça só no config.
- **Ordenar a `cadeia` por `custo_ordem` crescente** ao montá-la (cliente mais barato primeiro).
  Se `custo_ordem` não existir pra um cliente, manda pro fim.

## Racional do auto-esgotamento (por que marcar no 1º None)
Os clientes (Codex/OpenCode/OpenAICompat/Claude) JÁ retentam falha transiente internamente
(`tentativas=3`, backoff linear). Logo, um `None` que chega ao roteador = falha **persistente**
(não um soluço). Marcar o provedor como esgotado pro resto da missão evita re-bater num provedor
morto a cada nó — que foi exatamente a cascata observada. (v2 futuro: cooldown/retry-later pra
distinguir rate-limit que reseta de crédito que acabou — NÃO fazer agora.)

## Critério de aceite (DoD)
1. **Inércia:** `auto_esgotar=False` (default) → `chamar` byte-idêntico ao de hoje; **189 verdes**.
2. **Failover em cadeia:** com `auto_esgotar=True` e `ClienteStub`s cadeia=[A(sempre None),
   B(sempre None), C(ok)] (custo A<B<C) → `chamar` retorna a saída de **C**; eventos
   `provedor.auto_esgotado` pra A e B; A e B entram em `self.esgotados`.
3. **Sticky:** uma 2ª chamada no mesmo roteador **pula A e B** (vai direto ao 1º não-esgotado).
4. **Tudo falha:** todos None → `chamar` devolve **None** sem crash; todos os provedores marcados.
5. **Ordem por custo:** a cadeia é percorrida do mais barato pro mais caro (testar com custo_ordem).
6. **Preservado:** pin, guard do juiz, tier/capacidade, e o `modelo.fallback` do modo default
   continuam funcionando (testes existentes intactos).
Novos testes em `tests/test_modelos.py` (sufixo dedicado), `ClienteStub` com flag de “sempre None”.

## Fronteira / FUTURO (não fazer agora)
- **Cooldown/retry-later** (rate-limit que reseta vs crédito que acaba) = v2.
- **Salvar síntese parcial** quando tudo esgota (hoje a missão devolve None) = item separado
  (toca o grafo/cobertura, não o roteador) — anotar como próximo, não fazer aqui.
- **Catálogo em escada** (free→barato→caro com custo_ordem real) = conteúdo de Registry/config,
  outro passo (o Caio decide a escada).

## DÚVIDAS
- (vazio)
