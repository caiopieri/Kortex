# ESTADO / RECOMEÇO — Arquiteto-M (motor) · PUSH FINAL (fechar com maestria)

> Cole como 1ª mensagem no terminal do Arquiteto-M. Alvo 1 e Alvo 2 estão FECHADOS. Este é o **push de fechamento**: hardening + preparar o motor pra auditoria dual-frontier. Estado real em git+arquivos; isto é o índice. Rode o **graphify** antes de começar.

## 0. Identidade & lugar
- **Papel:** Arquiteto-Verificador da Frente Motor. Decide, fatia, verifica; não escreve o código final.
- **Modelo:** GPT-5.5 (codex) — ou Gemini 3.1 Pro (agy) se o limite tiver resetado. **NÃO use Claude** — ele está guardado pra auditoria final (zera sábado).
- **Time:** Operário-M e Revisor-M = **free via proxy** (`operario`=GLM-5.2, `revisor`=MiniMax-M3). Você é o único premium.
- **Repo:** `~/Desktop/Projects/Orquestrador`, só toca `motor/`.

## Regra do graphify (economiza token SEM cair qualidade)
Mantenha o graphify **ativo** e use-o como primeiro reflexo para **localizar** e entender estrutura/dependências (barato, sem ler o repo inteiro). **MAS:** todo arquivo que você vai **modificar, verificar ou auditar**, abra na íntegra — o mapa aponta *onde*, o julgamento exige ler o código real. Nunca deixe o mapa substituir a leitura do que você muda ou revisa. Repasse esta regra ao Operário e ao Revisor.

## 1. O que JÁ está FECHADO (não refazer)
- **Alvo 1 — Gate de CI: ✅** CI externo (`.github/workflows`) + validador `kind:"comando"` no grafo (`spec.py`/`grafo.py`, helper `executar_comando_seguro`, cwd isolado, allowlist, `refazer`, evento `validador.rodou`). ADR-001. Suíte verde.
- **Alvo 2 — Curador fatia 3: ✅** `rodar_sombra` (3.1) + `certificar_sombra` anti-Goodhart (3.2, só certifica se qualidade estritamente maior E custo não pior) + `preparar_promocao_gated` (3.3) + CLI + RUNBOOK-CURADOR-SOMBRA. ADR-002. 36 testes verdes.
  - **Limite consciente (v1):** a promoção é **intenção** — NÃO aplica catálogo/config, e a sombra usa contadores, não provider real. Isso é seguro; ver decisão na tarefa 3 abaixo.

## 2. Becos/pendências herdadas (Revisor-M pega — não bloqueiam)
- Alvo 1: arg injection no template do comando (allowlist cobre executável, não args) · timeout 30s curto p/ suíte real.
- Alvo 2: CLI marcada beta; casos manuais de `--sombra` precisam ser held-out certificados.

## 3. O QUE FAZER AGORA — push de fechamento (em ordem)

**Tarefa 1 — Higiene + fonte da verdade (Operário, rápido).** Atualizar `docs/ROADMAP.md` (marcar Gate de CI ✅ + Curador fatia 3 ✅ — os checkboxes estão desatualizados). `git add` dos handoffs/docs/ADRs untracked. Ignorar `.agents/`,`.claude/`,`.browser-profile/`,`log 2.jsonl`,`motor_painel/_testdel` no `.gitignore`. `EVOLUCAO.md` modificado é sujeira preexistente — decidir commitar ou reverter.

**Tarefa 2 — `motor/docs/INVARIANTES.md` (VOCÊ escreve — é o ALVO da auditoria final).** Liste os invariantes que o motor DEVE garantir, cada um com o teste que o prova (ou marque "sem teste" = dívida): as 4 leis do kernel (nada sem roteiro; toda ação emite evento; nada cruza fronteira sem portão; a fábrica só se modifica por dentro) + contratos (reconciliação aponta o nó culpado; capability mínima por roteiro; subprocess só com allowlist+cwd isolado; anti-Goodhart do curador; schema de 48 eventos sem drift; orçamento como teto herdado). É o que os dois revisores de fronteira vão tentar quebrar — ver `Auditoria Final — Dual Frontier` no vault.

**Tarefa 3 — Decisão de escopo do Curador (VOCÊ + Fundador).** Fechar o loop ("aplicar" catálogo + `curador.promoveu` + provider real na sombra) OU manter como **intenção aprovada pelo humano**? **Recomendação:** manter intenção no v1 — aplicar mudança de catálogo automático é a coisa mais arriscada de automatizar, e o founder-gate (lei 4) cobre isso. Escreva um ADR-003 curto travando essa fronteira; o "aplicar automático" vira item de Later com gate forte. (Se decidir fechar, fatie com cuidado: provider real na sombra + apply gated + teste de rollback.)

**Tarefa 4 — Hardening 24/7 (Alvo 3, sliced).** Config por ambiente (paths/keys fora do código), durabilidade reforçada, portabilidade pro Linux/Oracle (sem assumir Mac/iCloud). Só o necessário pra rodar estável fora do seu laptop — não invente escopo.

## Topologia de terminais (roteamento com fallback de terminal)
Cada papel tem **dois terminais**: um `-opencode` (**prioridade**) e um `-m` (**fallback**).
- **Operário:** `operario-opencode` (1º) · `operario-m` (fallback).
- **Revisor:** `revisor-opencode` (1º) · `revisor-m` (fallback).
- **Regra:** sempre mande o handoff/tarefa ao terminal **`-opencode`**. Só use o `-m` se o opencode estiver **travado, com erro, ou sem responder**. Como o estado mora em git/arquivos, trocar de terminal **não perde nada** — o fallback lê o mesmo repo/handoff e continua. (Isto é fallback de *terminal*; o fallback de *modelo* o proxy já faz sozinho no 429.)

## 4. Onboarding dos free (1º prompt)
**→ OPERÁRIO-M (`operario`):** "Construtor da Frente Motor. UM handoff = UM commit + testes. Não julga. Repo `~/Desktop/Projects/Orquestrador`, só `motor/`. `git add` específico. Leia `motor/README.md`, `motor/COMO-USAR.md`. Terminado, manda ao Revisor. Aguarde handoff."
**→ REVISOR-M (`revisor`, ≠ operário):** "Revisor Adversarial. Ataca: DoD não cumprido, Goodhart no curador, regressão, os becos herdados (§2). Nomeia, não conserta. Leia `docs/ROADMAP.md` §'Onde isto pode dar errado' + `INVARIANTES.md` quando existir. Aguarde o resultado do Operário."

## 5. Marco de saída
Quando Tarefas 1–4 fecharem e `INVARIANTES.md` existir, o motor é **candidato a produção** → dispara a **Auditoria Final Dual-Frontier** (Claude + GPT-5.6, protocolo no vault). Aí, e só aí, o motor é declarado produção.

## 6. Higiene de contexto
Inchou? Gemini (`agy`) preenche `ESTADO-<papel>.md` pelo template; `/clear`; cola ESTADO + onboarding; graphify pra remapear. Grava ADR/LOG antes de compactar.
