# HANDOFF CODEX — Livro-razão de CUSTO (2 PRs em ordem) — ROADMAP Next #1

## Por quê (ROADMAP-META-FABRICA.md)
Missão tem 2 eixos: entregar bom (qualidade) + processo cada vez mais barato. Hoje **nada mede custo** —
"mais barato" é sensação, não fato (gap explícito no ROADMAP). O custo deriva DIRETO da telemetria-por-
modelo que já construímos. Fechar isso torna o Curador capaz de ranquear por custo REAL (hoje usa
`custo_ordem` como proxy grosseiro). Read-only, derivado da telemetria; sem mexer na orquestração.

Fazer os 2 PRs NA ORDEM, cada um seu commit + testes. Aditivos e seguros.

---

## PR 1 — capturar tokens na telemetria (motor/modelos.py)
O `ClienteOpenAICompat._post` já recebe o JSON completo da resposta, que inclui `usage`
(`prompt_tokens`, `completion_tokens`, `total_tokens`) no padrão OpenAI-compat. Hoje `chamar` extrai só
`choices[0].message.content` e descarta o resto.

Mudança: em `ClienteOpenAICompat.chamar`, ao obter `conteudo` válido (sucesso), se `resp.get("usage")`
existir, emitir um evento (quando `self.log` houver):
```python
uso = resp.get("usage") or {}
if self.log is not None and uso:
    self.log.evento("modelo.uso", papel=papel,
                    modelo=self.mapa_papeis.get(papel, self.modelo),
                    prompt_tokens=uso.get("prompt_tokens"),
                    completion_tokens=uso.get("completion_tokens"),
                    total_tokens=uso.get("total_tokens"))
```
- Só openai-compat (NVIDIA/Ollama/OpenRouter — provedores futuros do Caio; todos retornam `usage`).
- CLI (codex/claude/opencode) NÃO expõem tokens → não emitem `modelo.uso` → o ledger cai pro tempo nesses.
- NÃO mudar a assinatura de `chamar` nem o valor de retorno (segue string|None). Evento é efeito colateral.

### PR1 DoD
- Teste: stub de `_post` retornando `usage` → `chamar` emite `modelo.uso` com os tokens e o modelo certo.
- Teste: resposta SEM `usage` → nenhum `modelo.uso`, comportamento atual intacto.
- Suíte verde (239+); compileall ok.

---

## PR 2 — livro-razão de custo no Curador (motor/curador.py + tests)
Agregar custo a partir dos eventos, por RUN e por (papel, tier, modelo) e por modelo:
- **tokens**: somar `modelo.uso` (prompt/completion/total) atribuindo ao modelo/papel do evento.
- **tempo**: já temos latência por chamada (deltas chamado→respondeu); somar como `tempo_total_s` por
  agregado (proxy de custo, especialmente p/ local/CLI sem tokens).
- **$ estimado (opcional)**: parâmetro `precos` (dict `"<provedor/modelo>" -> {"in_por_1k": float,
  "out_por_1k": float}`); custo_usd = prompt/1000*in + completion/1000*out. Sem `precos` → custo_usd None
  (não inventar preço). Provedores locais (ex. ollama) sem preço = $0/None, só tempo.

Expor em `analisar(...)` uma seção `custo`:
```
"custo": {
  "por_run": [{"id", "fonte", "tokens_prompt", "tokens_completion", "tokens_total", "tempo_total_s", "custo_usd"}],
  "por_modelo": { "<provedor/modelo>": {tokens_*, tempo_total_s, chamadas_com_uso, custo_usd} },
  "total": {tokens_*, tempo_total_s, custo_usd}
}
```
CLI: `python3 -m motor.curador <logs> --custo [precos.json]` imprime o livro-razão em markdown
(tabela por modelo + por run + total). Sem `--custo`, saída atual intacta. `precos.json` opcional;
sem ele, mostra tokens+tempo e custo_usd vazio.

### PR2 DoD
- Fixtures: (a) run com 2 `modelo.uso` de modelos diferentes → `por_modelo` soma tokens certo;
  (b) com `precos`, custo_usd calculado certo (in/out × tabela); (c) sem `precos`, custo_usd None mas
  tokens/tempo presentes; (d) modelo só-CLI (sem `modelo.uso`) aparece no ledger com tempo e sem tokens.
- `python3 -m motor.curador logs/curador-*.jsonl --custo` roda sem erro e mostra o livro-razão.
- READ-ONLY; stdlib; suíte verde; compileall ok.

## Validação do Caio (depois dos 2 commits) — NÃO é código
1. Rodar uma missão com config openai-compat (ex. modelos-free-escalada com executores nv-*) e confirmar
   `modelo.uso` no log.jsonl.
2. `python3 -m motor.curador logs/ log.jsonl --custo precos.json` (montar um precos.json simples com os
   preços dos modelos pagos que usar) → ver tokens/tempo/$ por modelo e por run. Agora "mais barato"
   vira número.

## DEPOIS (não agora)
- Curador passa a considerar custo_usd real no desempate do propositor (hoje usa custo_ordem proxy).
- Fatia 3 do Curador (sombra+certificação) já entra olhando custo×qualidade real.
