# HANDOFF CODEX — Telemetria POR MODELO (2 PRs em ordem) — fundação p/ o Curador comparar modelos

## Por quê (visão do Caio, travado pela arquiteta)
O Caio vai trocar de provedor com o tempo (Codex → Cursor/Ollama cloud/OpenRouter; futuro talvez só
open-source grande Kimi/DeepSeek; fluxo "NVIDIA grátis 1º, sobe se falhar"). Quer que o CURADOR teste e
COMPARE modelos pra operação ficar mais segura+barata+boa. O motor já é provider-agnóstico (fronteira
ClienteModelo). GAP: a telemetria loga (papel, tier), NÃO o MODELO concreto por chamada → o Curador não
consegue comparar "Kimi vs DeepSeek vs llama em código-complexo". Este handoff fecha esse gap.

Fazer os 2 PRs NA ORDEM, cada um seu commit + testes. São sequenciais e seguros (inerte/aditivo).

---

## PR 1 — emitir o modelo/provedor concreto nos eventos (motor/modelos.py + motor/grafo.py)

### 1a. `ClienteRoteador.descricao_de(...)` (modelos.py)
Espelhar `provedor_de` (resolve com `emitir=False`, sem efeito), mas retornar a IDENTIDADE concreta:
```python
def descricao_de(self, papel, tier=None, ferramentas=None, capacidades=None) -> Optional[str]:
    c = self._resolver(papel, tier, ferramentas, capacidades=capacidades, emitir=False)
    prov = getattr(c, "provedor", None)
    modelo = getattr(c, "modelo", None)
    if prov and modelo:
        return f"{prov}/{modelo}"
    return prov or (str(modelo) if modelo else None)
```

### 1b. helper no grafo p/ funcionar com QUALQUER cliente (não só roteador)
No grafo, calcular a descrição de forma defensiva (clientes single — claude/codex/openai-compat — não têm
`descricao_de`):
```python
def _descricao_modelo(papel, tier=None, ferramentas=None, capacidades=None):
    if hasattr(cliente, "descricao_de"):
        return cliente.descricao_de(papel, tier, ferramentas, capacidades=capacidades)
    prov = getattr(cliente, "provedor", None); modelo = getattr(cliente, "modelo", None)
    return f"{prov}/{modelo}" if prov and modelo else (prov or (str(modelo) if modelo else None))
```

### 1c. logar `modelo=` em CADA `executor.chamado`
Adicionar o campo `modelo` (string ou None) nos 4 pontos:
- planner (~245): `modelo=_descricao_modelo("planner")`
- subagente (~361): já há `prov_exec` via `provedor_de`; adicionar `modelo=_descricao_modelo(sub["papel"], tier_atual, sub.get("ferramentas"), sub.get("capacidades_requeridas"))`
- global_evaluator (~564): `modelo=_descricao_modelo("evaluator")`
- synthesizer (~705): `modelo=_descricao_modelo("synthesizer")`
NÃO mudar mais nada do fluxo. Campo aditivo; ausência = None (compat com logs antigos).

### PR1 DoD
- Teste: com `ClienteRoteador` configurado (tiers/pins), um run stub emite `executor.chamado` com `modelo`
  resolvido correto (ex.: tier simples → "nv-llama/meta/llama-3.3-70b-instruct"; pin → o pinado).
- Teste: com cliente single (ClienteStub/sem provedor), `modelo` vira None e NADA quebra.
- Suíte verde (227+); compileall ok. NÃO tocar PROMPT_PLANNER (snapshot).

---

## PR 2 — Curador perfila POR MODELO + limpa 2 ruídos de métrica (motor/curador.py + tests)

### 2a. nova agregação `por_modelo`
Além de `por_papel_tier`, agregar as MESMAS métricas keyed pelo `modelo` lido do `executor.chamado`
(quando ausente → bucket "desconhecido"). A info do executor passa a carregar `modelo`; ao parear
`executor.respondeu`/julgamento do verifier, atribuir as métricas TAMBÉM ao modelo daquela chamada.
Adicionar `"por_modelo": {...}` no dict de `analisar(...)` e uma seção no markdown
("## Aptidao por modelo") — é o ranking que o Caio vai usar pra comparar modelos.

### 2b. consertar `taxa_erro > 100%`
Hoje `erros` mistura `executor.erro` (a chamada não produziu resultado) com `modelo.falha` (retentativa
INTERNA do cliente dentro de uma chamada) → erros pode passar de chamadas (visto 247%). Separar:
- `erros` = só `executor.erro` (resultado nulo após retries). `taxa_erro = erros/chamadas` (≤100%).
- `falhas_internas` = contagem de `modelo.falha` (reportar à parte, NÃO entra em taxa_erro).

### 2c. reduzir entries órfãs `sem-tier`
Quando `executor.respondeu`/`erro` ou julgamento `verifier:<id>` não acha a `executor.chamado`
correspondente no segmento de run, NÃO inventar um papel=`<id>` com tier `sem-tier`. Em vez disso:
atribuir a um bucket único e rotulado `("desconhecido","sem-tier")`. (Logs antigos de formato diferente
geram esse ruído; agrupar em "desconhecido" mantém o perfil limpo sem perder a contagem.)

### PR2 DoD
- Fixtures sintéticos: (a) 2 modelos diferentes no mesmo papel/tier → `por_modelo` separa e ranqueia
  corretamente (aprovação-1ª, latência, escalada+convergência por modelo); (b) um run com `modelo.falha`
  → `falhas_internas` conta, `taxa_erro` fica ≤100%; (c) respondeu/julgamento órfão → cai em
  "desconhecido", não cria papel-fantasma.
- `python3 -m motor.curador logs/` roda sem erro e mostra a seção "Aptidao por modelo".
- Suíte verde; compileall ok. Curador continua READ-ONLY (sem chamar modelo, sem mutar nada).

---

## Validação do Caio (depois dos 2 commits) — NÃO é código
1. Rodar QUALQUER missão (a config atual basta) e confirmar no `log.jsonl` que `executor.chamado` agora
   traz `modelo`.
2. `python3 -m motor.curador logs/ log.jsonl` → conferir a seção "Aptidao por modelo" e que `taxa_erro`
   não passa de 100% nem há mais papéis-fantasma. Trazer a saída.

## DEPOIS (NÃO agora — só fatia quando o perfil-por-modelo estiver limpo e real)
Fatia 2 do Curador = PROPOR roteamento/pins a partir do `por_modelo` (ranquear modelo por papel/tier/tag
por qualidade→latência→custo, emitir PROPOSTA + evidência, SEM aplicar). Eu escrevo esse handoff depois
de ver a saída real do `por_modelo` — não quero construir o propositor sobre métrica ainda não validada.
Fatia 3 = teste em SOMBRA de modelo novo + certificação antes de mudar o catálogo (= "testar modelo
quando eu adiciono um").
