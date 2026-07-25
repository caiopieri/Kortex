# HANDOFF ARQUITETO-M — escrever `motor/docs/INVARIANTES.md`

> **Você (Arquiteto) escreve este doc — é julgamento, não é tarefa de operário.** Ele é o **alvo da Auditoria Final Dual-Frontier**: a lista do que o motor DEVE garantir, cada invariante com o teste que o prova (ou marcado como dívida). Os dois revisores de fronteira (Claude + GPT-5.6) vão tentar quebrar cada linha. Um invariante sem teste é uma porta aberta — nomeie-a como tal.

## Por quê
"Nível absurdo" só é verificável contra invariantes explícitos. Sem esta lista, a auditoria vira vibe-check. Com ela, cada revisor tem um checklist executável pra atacar. Também vira a espinha do que o Gate de CI protege.

## O que fazer
Crie `motor/docs/INVARIANTES.md`. Para CADA invariante abaixo, preencha: **enunciado** · **onde é enforçado** (`arquivo::função`) · **teste que prova** (nome do teste existente, ou "⚠️ SEM TESTE — dívida"). Confirme cada um lendo o código real (não confie nesta lista de cabeça — ela é o rascunho do Arquiteto; valide).

**Regra do graphify (economiza token SEM cair qualidade):** use o graphify pra **localizar** cada `arquivo::função` barato — mas **abra e leia o código real** de cada um antes de afirmar o invariante. Aqui o mapa nunca substitui a leitura: você está *verificando*, e verificação exige o código, não o mapa. Rode `pytest` também.

### Rascunho dos invariantes (valide e complete)

**A. Kernel — as 4 leis**
1. **Nada roda sem roteiro.** Toda execução parte de uma WorkflowSpec válida. Enforço: `spec.py` (validação). Teste: `tests/test_spec.py`.
2. **Toda ação emite evento.** Passos, portões, custos, erros → log append-only. Enforço: `eventos.py`/`grafo.py`. Teste: `tests/test_eventos_schema.py` (+ guard anti-drift dos 48 eventos).
3. **Nada cruza fronteira de workflow sem portão.** Artefato só avança por validador/portão. Enforço: `grafo.py::executar_validador`. Teste: `tests/test_validadores_deterministicos.py`.
4. **A fábrica só se modifica por dentro (gated).** Mudança de catálogo/modelo passa por certificação; promoção NÃO é automática (é intenção aprovada pelo fundador — v1). Enforço: `curador.py::preparar_promocao_gated`. Teste: `tests/test_curador.py`.

**B. Spec & capabilities**
5. Validador só aceita `kind ∈ {schema_json, contem, comando}`; config inválida é rejeitada na validação. Enforço: `spec.py` (l.113+). Teste: `tests/test_spec.py`.
6. Executor recebe só as capacidades que o roteiro declara (capability mínima). Enforço: `spec.py`/`politica.py`. Teste: `tests/test_capacidade.py` / `test_politica.py`.
7. Orçamento é teto herdado do roteiro-pai; custo por passo emitido. Enforço: `politica.py`. Teste: `tests/test_politica.py` — ⚠️ confirmar que existe teste do estouro de teto.

**C. Grafo / reconciliação**
8. **Reconciliação aponta o nó CULPADO** (`refazer: alvo`), re-dispara ele + dependentes, com teto de rodadas (loop bounded). Enforço: `grafo.py` (reconciliação, `max_rodadas_reconciliacao`). Teste: `tests/test_grafo_dep.py`.
9. Erro de passo vira evento, não crash (executor indisponível degrada). Enforço: `grafo.py`. Teste: confirmar.

**D. Segurança do validador `comando` (superfície nova do Alvo 1)**
10. Subprocess só roda executável na **allowlist** do Registry. Enforço: `grafo.py::executar_comando_seguro` + `registro.py::ferramentas_permitidas_de_registro`. Teste: `tests/test_validadores_deterministicos.py`.
11. Comando roda em **`cwd=workspace` isolado**, não na raiz do repo. Enforço: idem (l.762). Teste: ⚠️ confirmar que há teste provando o cwd.
12. **Args do comando não são superfície de injeção** — a allowlist cobre o executável; validar que placeholders/paths substituídos não permitem escape. Enforço: `executar_comando_seguro`. Teste: ⚠️ **provável dívida — escrever teste adversarial de arg com espaço/aspas/`;`.**
13. Timeout sempre aplicado; timeout → reprovação, não travamento. Enforço: idem. Teste: confirmar.

**E. Eventos**
14. Os 48 tipos de evento são fechados; evento fora do schema é bloqueado (guard anti-drift). Enforço: `eventos_schema.py`. Teste: `tests/test_eventos_schema.py`.
15. O log é a única fonte de verdade; projeções (painel, curador) só leem. Enforço: arquitetura. Teste: `tests/test_painel.py` (parse read-only).

**F. Curador (Alvo 2) — anti-Goodhart**
16. `certificar_sombra` só certifica se candidato tem **qualidade estritamente maior E custo não pior**; empate não certifica; custo incomparável veta. Enforço: `curador.py::certificar_sombra`. Teste: `tests/test_curador.py` — **confirmar que há caso NEGATIVO (regressão de qualidade veta mesmo com custo menor).**
17. Sombra é **read-only**: não altera a saída da run real nem o catálogo. Enforço: `curador.py::rodar_sombra`. Teste: `tests/test_curador.py`.
18. Promoção sem certificação aprovada → `promocao_vetada`. Enforço: `preparar_promocao_gated`. Teste: `tests/test_curador.py`.

**G. Fundador / Caixa**
19. Escalação sobrevive a crash (kill -9): decisão pendente é retomada, não perdida. Enforço: `caixa.py`. Teste: `tests/test_caixa.py`.
20. Gate de classe sensível nunca é auto-respondido pelo modelo (é do fundador). Enforço: `caixa.py`/política. Teste: confirmar.

## DoD (falsificável)
1. `motor/docs/INVARIANTES.md` existe, com **todos** os invariantes acima validados contra o código (nomes de arquivo/função conferidos), cada um com teste nomeado OU marcado `⚠️ SEM TESTE`.
2. Para cada `⚠️ SEM TESTE`, você abre um item no `LOG-VERIFICACAO` (ou um handoff ao Operário) para escrever o teste — priorizando os de **segurança** (12) e o **caso negativo do curador** (16).
3. O doc termina com uma seção "Dívidas conhecidas" (os invariantes sem teste) — honestidade explícita é o que o auditor respeita.

## O que isto prova e o que NÃO prova
Prova que existe um alvo auditável e honesto. NÃO prova que os invariantes se sustentam — isso é a Auditoria Final (Claude + GPT-5.6) tentando quebrá-los. Este doc é a munição que a torna devastadora.
