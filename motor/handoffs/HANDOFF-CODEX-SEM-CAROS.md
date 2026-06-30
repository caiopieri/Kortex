# HANDOFF-CODEX-SEM-CAROS — último recurso configurável (perfil "sem caros")

**Para:** Codex (executor) — produz na pasta `motor/`, 1 commit.
**Quem verifica:** Claude (Cowork) revisa o diff + roda a suíte + sondagem independente.
**Regra de ouro:** se algo divergir do que está aqui, NÃO improvise — pare e escreva **DÚVIDAS**.

## Problema
Hoje o `padrao` do `ClienteRoteador` é **cravado** como `ClienteClaudeCLI` (modelos.py L645).
Ele é o ÚLTIMO recurso: em falha, o roteador cai no `padrao` 1× (sem `auto_esgotar`) ou o coloca no
fim da cadeia de failover (com `auto_esgotar`). Resultado: um run "free-only" que sofra rate-limit
pode **vazar uma chamada pro claude** (gasta a assinatura do Caio). O Caio quer um perfil **"sem caros"**:
roda só free/barato e, se tudo falhar, **falha limpo** — nunca claude, nunca codex.

## Solução (mínima, inerte por default)
Um sentinela de config: `"padrao": "nenhum"` no topo do JSON de `--modelos` → o `padrao` vira um
**`ClienteNulo`** que sempre devolve `None` (falha vira evento, não crash — lei do motor).
Sem o campo `"padrao"` → comportamento de hoje (claude), byte-idêntico. **193 verdes intactos.**

## Mudanças (SÓ em `motor/modelos.py` + `tests/test_modelos.py`)

### 1. Classe nova `ClienteNulo` (perto dos outros clientes, ex.: após `ClienteClaudeCLI`)
Contrato uniforme, igual aos outros `chamar`:
```python
class ClienteNulo:
    """Último recurso do perfil 'sem caros': NUNCA chama modelo pago.
    Sempre devolve None (falha vira evento, não crash). Usado como `padrao`
    quando a config declara `"padrao": "nenhum"`."""
    suporta_ferramentas = True   # nunca desvia "pro padrao por falta de ferramenta"
    provedor = "nenhum"          # rótulo p/ esgotamento/cadeia

    def __init__(self, log: Optional[Any] = None) -> None:
        self.log = log

    def chamar(self, papel: str, prompt: str, ferramentas: Optional[str] = None,
               tier: Optional[str] = None, timeout: int = 300,
               evitar: Optional[str] = None,
               capacidades: Optional[list[str]] = None) -> Optional[str]:
        if self.log is not None:
            self.log.evento("modelo.sem_recurso", papel=papel)
        return None
```
- A assinatura de `chamar` deve bater EXATAMENTE com o Protocol `ClienteModelo` (mesmos kwargs uniformes — `evitar`, `capacidades`, `tier`, `timeout`). Se o Protocol mudou desde este doc, alinhe a ele e anote em DÚVIDAS.

### 2. `cliente_de_config` — ligar o sentinela (1 linha, logo após `padrao = ClienteClaudeCLI(log=log)`, L645)
```python
    padrao = ClienteClaudeCLI(log=log)
    if cfg.get("padrao") == "nenhum":
        padrao = ClienteNulo(log=log)
```
- Fica ANTES das duas ramificações de formato (multi-plataforma e v1), então vale pros dois.
- `"padrao"` é OPCIONAL. Qualquer valor diferente de `"nenhum"` (inclusive ausente) → segue claude.
  NÃO tratar `provedor/modelo` como padrao neste corte (fora de escopo; se aparecer, é DÚVIDA).
- O `_cliente_destino("padrao", ...)` já existente continua retornando `self.padrao` — agora pode ser
  o `ClienteNulo`. Confirme que tiers/pins que referenciam `"padrao"` apontam pro sentinela (esperado).

## DoD (em `tests/test_modelos.py`)
1. **ClienteNulo devolve None**: `ClienteNulo().chamar("planner","x") is None`; com log fake, emite `modelo.sem_recurso`; tem `provedor == "nenhum"` e `suporta_ferramentas is True`.
2. **Sentinela liga**: `cliente_de_config({"padrao":"nenhum","provedores":{...},"tiers":{...}})` → `roteador.padrao` é `ClienteNulo`.
3. **Sem vazamento em falha**: monte uma config "sem caros" com `auto_esgotar: true` e UM provedor cujo cliente FALHA (stub que retorna None). Force uma chamada que normalmente cairia no padrao → resultado `None` e **o claude nunca é instanciado/chamado** (use um monkeypatch em `ClienteClaudeCLI.chamar` que faça `raise AssertionError` se tocado — o teste passa só se NÃO for tocado).
4. **Inerte (regressão)**: config SEM `"padrao"` → `roteador.padrao` é `ClienteClaudeCLI`. Suíte inteira **193 passed**.
5. **mypy limpo** nos arquivos tocados.

## FORA DE ESCOPO (não fazer agora)
- `padrao = "provedor/modelo"` (ex.: ollama como último recurso em vez de "nada"). Candidato a v2.
- Mesma feature em `cliente_de_registro` (caminho `--registro`). Este corte cobre só `--modelos`.
  Se quiser simetria, é OUTRO commit/handoff — não misture aqui.
- Salvar síntese parcial / cooldown-retry (v2 da resiliência).

## Commit
Mensagem sugerida: `Adiciona ClienteNulo + perfil sem-caros (padrao:nenhum)`.
Traga `git log -1` + saída do `pytest` (ou DÚVIDAS).
