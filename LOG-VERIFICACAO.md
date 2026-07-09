# Log de Verificação — meta-fábrica (Orquestrador)

> O veredito auditável, fora da cabeça de qualquer agente. Uma linha por handoff, preenchida
> pelo Arquiteto **depois de verificar** (leu o diff + rodou testes + sonda independente no
> sandbox + checou higiene de git). Ao trocar de sessão/agente, leia isto pra saber o estado
> real. Processo: `kit-processo/METODO-DE-TRABALHO.md`.

| Data | Handoff | O que verifiquei | Resultado | Evidência |
|---|---|---|---|---|
| 2026-07-01 | V1-validadores-deterministicos | li o diff; rodei a suíte; sondei os kinds `schema_json`/`contem` no sandbox; confirmei que reprovação re-dispara o alvo por reconciliação | ✅ passou | suíte verde; validador `contem` reprova/aprova conforme termos; re-fire observado |
| 2026-07-01 | propositor-custo-real | li o diff; rodei pytest; sondei o desempate com 2 perfis fabricados (mesma qualidade/latência, `custo_usd` diferentes) | ✅ passou | 262+ testes verdes; casos 1/2/3 do DoD reproduzidos; regressão sem `custo_usd` intacta |
| 2026-07-01 | eventos-superficie | li o diff; conferi contra `eventos_schema.py` (guard anti-drift); sondei emissão de `aresta.fluxo`/`custo.tick`/`artefato.atualizou`/`validador.rodou` | ✅ passou | schema declara os 48 tipos; nenhum evento não-declarado; log emite os de superfície |
| 2026-07-02 | rag-consumo-e-lift (v2) | rodei o experimento com `--somente-metrica-deterministica`; comparei COM vs SEM RAG sobre corpus que o base ignora (nossos docs); métrica = validador `contem` | ✅ passou | SEM RAG 0/3, COM RAG 3/3 no validador determinístico → lift real (flywheel provado) |

## Legenda
- ✅ **passou** — DoD satisfeito, sonda independente confirmou.
- ❌ **reprovou** — gerou handoff de correção nomeando o defeito.
- ⏸️ **parcial** — entregue, aguardando gate humano.

## Pendências abertas (a verificar quando voltarem do Codex/Mac)
- Commit no Mac de V1 + lift-v2 (worktree do Codex) seguindo higiene de git.
- Juiz Codex pendura no fim de runs completas — usar juiz free ou tratar (problema de
  provedor, não do motor).
