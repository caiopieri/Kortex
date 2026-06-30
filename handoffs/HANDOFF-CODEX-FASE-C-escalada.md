# HANDOFF-CODEX-FASE-C-escalada — auto-correção com escalada na escada

**Para:** Codex (executor) — produz na pasta `motor/`, 1 commit.
**Quem verifica:** Claude (Cowork) revisa diff + roda a suíte + sondagem independente.
**Regra de ouro:** divergiu do que está aqui → PARE e escreva **DÚVIDAS**. Não improvise.

## Contexto (por que isto existe)
Run real (CSV→JSON spec, regime free: executor llama-70b, juízo Kimi-k2.6) depois de calibrar
planner+verifier: 3 de 6 subagentes convergiram; os outros 3 reprovaram por TETO do executor barato
(faltou 'cast', exemplos, params de saída — lacunas reais, não pedantismo). Hoje o `subagente`
(grafo.py L319-330) re-tenta SEMPRE no mesmo `tier` → mesmo modelo fraco → não converge.
**Fase C (este corte) = quando o verifier reprova, a próxima tentativa SOBE um degrau da escada**
(tier mais forte), levando o nó difícil pro modelo mais capaz só quando precisa. É o north star do
Caio (tamanho certo de modelo por tarefa, descoberto em runtime, custo mínimo).

## Escopo TRAVADO (só isto)
Escalada de TIER na retentativa do `subagente`, **inerte por default** (flag desligada = comportamento
de hoje, byte-idêntico, 193 verdes). Reusa 100% o roteamento por tier que já existe (tier "complexa"
→ modelo forte do catálogo). NÃO mexe no roteador, no verifier, nem na spec.

## Mudanças (em `motor/grafo.py` + `tests/test_grafo.py` ou arquivo de teste equivalente)

### 1. Helper de escalada (nível de módulo, perto dos prompts)
```python
ORDEM_TIER = ["simples", "media", "complexa"]

def _proximo_tier(t: str | None) -> str:
    """Próximo degrau acima na escada de dificuldade. Teto = 'complexa'.
    tier None/desconhecido → escala direto pro mais forte ('complexa')."""
    if t in ORDEM_TIER and ORDEM_TIER.index(t) < len(ORDEM_TIER) - 1:
        return ORDEM_TIER[ORDEM_TIER.index(t) + 1]
    return "complexa"
```

### 2. Flag de run em `construir_grafo` (igual ao padrão de `politica`/`rota`)
- Assinatura: `construir_grafo(..., escalar_em_retry: bool = False)`. Default False = inerte.
- A closure `subagente` lê essa flag do escopo.

### 3. `subagente` — escalar o tier a cada reprovação (L318-352)
Hoje o `tier` passado a `cliente.chamar` é fixo (`tier=sub.get("tier")`). Troque por uma variável
`tier_atual` que começa em `sub.get("tier")` e, **só quando `escalar_em_retry` está ligada**, sobe
um degrau APÓS cada reprovação do verifier (antes da próxima tentativa):
```python
    tier_atual = sub.get("tier")
    feedback, ultima = payload.get("feedback", ""), None
    for tentativa in range(1, max_t + 1):
        log.evento("executor.chamado", executor=sub["id"], papel=sub["papel"],
                   tier=tier_atual, tentativa=tentativa)
        ultima = cliente.chamar(sub["papel"], PROMPT_SUBAGENTE.format(...),
            ferramentas=sub.get("ferramentas"), tier=tier_atual,
            capacidades=sub.get("capacidades_requeridas"))
        # ... (sem resposta / respondeu / verifier IGUAL a hoje) ...
        # APÓS reprovação (depois de setar feedback e logar portao.reprovado):
        if escalar_em_retry:
            novo = _proximo_tier(tier_atual)
            if novo != tier_atual:
                log.evento("executor.escalado", executor=sub["id"],
                           de=tier_atual, para=novo, tentativa=tentativa)
            tier_atual = novo
```
- **tentativa 1 usa o tier DECLARADO** (inalterado, mesmo com flag on) — só as retentativas escalam.
- A escala é capada em "complexa" (`_proximo_tier` já garante; em "complexa" o evento não dispara pois `novo == tier_atual`).
- Aprovação em qualquer tentativa retorna IGUAL a hoje (para a escalada).
- O guard de independência do verifier (`kw_verifier`/`prov_exec`) fica COMO ESTÁ — calculado 1× no início pelo tier declarado. NÃO recalcular por tentativa neste corte (anotado como FUTURO; ver abaixo).

### 4. CLI (`motor/__main__.py`) — flag `--escalar`
- `--escalar` no args → passa `escalar_em_retry=True` ao `construir_grafo` (nos DOIS caminhos de construção, igual ao `--auto`/`politica`). Sem a flag = False.

## DoD (testes)
1. **Inerte (regressão)**: sem a flag, `tier` passado a `cliente.chamar` é o DECLARADO em toda tentativa; suíte inteira **193 passed**, mypy limpo.
2. **`_proximo_tier`**: simples→media, media→complexa, complexa→complexa, None→complexa, "xpto"→complexa.
3. **Escalada e2e**: com um cliente fake que registra `(papel, tier)` por chamada e REPROVA no verifier nas 2 primeiras e aprova na 3ª, rodando `subagente` com `escalar_em_retry=True` e um sub tier "simples", max_tentativas=3 → tiers do EXECUTOR observados = ["simples","media","complexa"]; evento `executor.escalado` emitido 2× (simples→media, media→complexa).
4. **Aprovação para a escalada**: aprovou na tentativa 1 → nenhum `executor.escalado`, tier permanece o declarado.
5. **Flag via CLI**: `--escalar` liga; ausência mantém o default inerte.

## FORA DE ESCOPO (FUTURO, não fazer agora)
- **Loop upstream bounded** (validador reprova → re-dispara um nó upstream DIFERENTE, ex.: volta ao design quando a implementação falha) = o que o harness MECÂNICO (MR-3) e HARDWARE (REQ-2) pediram, para `grafo_dependencias`. É OUTRO handoff, com dados de falha de grafo_dependencias.
- Escalada por CAPACIDADE/custo_ordem (em vez de tier) — refinamento quando houver perfis de aptidão.
- Recalcular o guard de independência do verifier quando o executor escala pro provedor do verifier (perde cross-model nas retentativas escaladas; hoje pin vence o guard). Anotar, não consertar.
- Salvar síntese parcial / cooldown (v2 resiliência).

## Commit
Mensagem: `Fase C: escalada de tier na retentativa do subagente (inerte por default)`.
Traga `git log -1` + saída do `pytest` (ou DÚVIDAS).
