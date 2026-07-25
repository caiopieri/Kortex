# HANDOFF CODEX — Curador fatia 2.1: incompletas (anti-timeout-cego) + piso de qualidade

## Por quê (dado real 2026-06-29 expôs 2 pontos cegos)
Rodando o propositor sobre runs reais (inclusive Ollama local como "modelo novo"):
1. **Cegueira a timeout**: logs de timeout do Ollama têm só `executor.chamado`+`modelo.pin` (o processo
   travou e foi morto externamente). No perfil isso vira `chamadas 1, respostas 0, erros 0` — parece
   LIMPO, quando é o PIOR resultado (nunca terminou). Como decidimos NÃO ter timeout de chamada (não
   cortar raciocínio), não há evento de timeout. Mas o curador PODE inferir: `executor.chamado` sem
   `executor.respondeu`/`executor.erro` correspondente no run = INCOMPLETA.
2. **Sem piso de qualidade**: o propositor "recomendou" codex/gpt-5.4 a 33% de aprovação só porque era o
   único candidato do slot. "Melhor disponível" ≠ "bom". Precisa de piso + sinal de candidato único.

Ambos os consertos são SÓ no curador (read-only, sem mexer no motor/telemetria).

## Mudanças (motor/curador.py + tests/test_curador.py)

### M1 — métrica `incompletas` (inferida)
No `_Agregador`, ao fim de cada run, toda `executor.chamado` (por chave executor+tentativa) que NÃO teve
`executor.respondeu` nem `executor.erro` correspondente conta como `incompletas` no bucket daquele
executor (papel/tier E papel/tier/modelo E por_modelo). Adicionar aos dicts de métrica:
`incompletas` (int) e `taxa_incompletas` = incompletas/chamadas (0 se chamadas==0). Mostrar no markdown
do perfil (por_modelo e por_papel_tier) e incluir nas métricas de `por_slot_modelo`.
NOTA: hoje `executor.respondeu/erro` órfão cai em "desconhecido"; aqui é o inverso — `chamado` SEM
resposta. Implementar pareando chamado↔(respondeu|erro) por (executor, tentativa); o que sobrar de
chamado sem par = incompleta.

### M2 — `propor(...)`: piso de qualidade + evitar por não-completar/erro
- **Evitar** passa a disparar também quando, sobre `chamadas >= min_amostras` (tentativas, não só
  julgamentos), o modelo tem `taxa_incompletas + taxa_erro >= limiar_falha` (default 0.5). Ou seja: um
  modelo que trava/erra muito num slot vai pra "evitar" MESMO sem julgamentos do verifier (é o caso
  Ollama-timeout, hoje invisível).
- **Piso de qualidade**: parâmetro `piso_aprovacao` (default 0.6). Se o `recomendado` tiver
  `taxa_aprovacao_primeira < piso_aprovacao`, NÃO marcar como recomendação limpa: usar
  `"status": "melhor_disponivel_abaixo_do_piso"` + campo `aviso` ("aprovação X% < piso Y%; não confie
  sem mais evidência"). Acima do piso → `"status": "proposto"` como hoje.
- **Candidato único**: quando o slot tem só 1 modelo com evidência suficiente, incluir
  `"unico_candidato": true` (não é comparação real, é o único que rodou).
- Manter tudo read-only; nunca aplicar.

### M3 — CLI/markdown
A saída de `--propor` mostra o `status` (proposto / melhor_disponivel_abaixo_do_piso /
evidencia_insuficiente), o `aviso` quando houver, `unico_candidato`, e a coluna `incompletas` (ou
taxa_incompletas) na tabela de ranking. Flags novas opcionais: `--piso <float>` e `--limiar-falha <float>`.

## Restrições
- READ-ONLY, stdlib puro, sem chamar modelo, sem mexer no motor.
- Aditivo: métricas novas com default; sem `--propor` a saída do perfil só GANHA a coluna incompletas.
- Defaults: min_amostras=3, piso_aprovacao=0.6, limiar_falha=0.5.

## DoD (todos precisam passar)
1. **Incompleta inferida**: fixture com `executor.chamado` (modelo M) e NENHUM respondeu/erro no run →
   `incompletas`==1 p/ M em por_modelo e no slot; `taxa_incompletas` correta. Um chamado COM respondeu
   no mesmo run não conta incompleta.
2. **Evitar por não-completar**: fixture com modelo que tem `chamadas>=3` e `taxa_incompletas>=0.5`
   (sem julgamentos) → aparece em `evitar` do slot.
3. **Piso**: recomendado com aprov_1a 0.33 (>=min_amostras) → `status=="melhor_disponivel_abaixo_do_piso"`
   + `aviso`; recomendado com 0.8 → `status=="proposto"`.
4. **Candidato único**: slot com 1 modelo elegível → `unico_candidato==true`.
5. Suíte verde (236+); compileall ok; (mypy se disponível). Saída atual de `--propor`/perfil sem flags
   continua coerente.

## Validação do Caio (depois do commit) — NÃO é código
`python3 -m motor.curador logs/curador-*.jsonl --propor` → conferir: Ollama 9b/4b (timeouts) agora
aparecem com `incompletas` e/ou em `evitar`; pesquisador/complexa (codex 33%) vem como
`melhor_disponivel_abaixo_do_piso`, não recomendação limpa; especificador/media (Kimi 66.7%) segue
`proposto`. Aí o propositor reflete o julgamento manual ("não use ollama-3b como default; codex@33% não
é confiável") — e fica pronto pra fundamentar a fatia 3 (sombra+certificação).
