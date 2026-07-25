# Auditoria Final — Dual-Frontier (chefão de 2 cadeados)

> Charter da auditoria de produção do motor. Dois auditores de **fronteira, de vendors diferentes** — **Claude (Fable-5/Opus-tier)** e **GPT-5.6** — auditam o motor de forma **independente**, cruzam achados, corrigem sob gate, e re-auditam até **os dois assinarem**. O motor só é declarado produção quando os dois cadeados fecham. Alvo: `motor/docs/INVARIANTES.md`.
>
> Pré-requisitos (todos ✅): Alvo 1 (Gate de CI) · Alvo 2 (Curador fatia 3) · hardening/portabilidade · `INVARIANTES.md` · 333 testes verdes.

## Definição de "produção" (operacional — senão é infinito)
Declara-se produção quando, ao mesmo tempo:
1. **Gate de máquina verde** (lint · mypy · pytest · SAST · secrets · build), <5 min, determinístico.
2. **Todo invariante do `INVARIANTES.md` tem teste que o prova** (as dívidas `⚠️ SEM TESTE` viraram testes verdes).
3. **Dois cadeados:** Claude E GPT-5.6, em auditorias independentes, não produzem nenhum achado novo de severidade ≥ **média**.
4. **Zero dívida silenciosa:** todo "frágil mas deixei" está escrito em ADR/LOG, não escondido.

## Protocolo — 4 fases

### Fase A — Auditorias independentes e paralelas, FATIADAS por subsistema
O auditor Anthropic (Opus 4.8/Fable) e o GPT-5.6 Sol auditam **sem ver o trabalho um do outro** (independência preserva a diversidade de erro).

> ⚠️ **NÃO audite o motor inteiro numa janela só — não cabe no contexto de nenhum modelo, nem frontier, e degrada a qualidade.** Fatie por grupo de invariante do `INVARIANTES.md` (A–G), **cada fatia numa conversa NOVA/fresh**, carregando o **mapa do graphify + apenas os 1–3 arquivos da fatia** (nunca o repo todo). Auditor lê na íntegra só esses arquivos. Fatias:
> 1. Leis do kernel (A) → `spec.py`, `grafo.py` (alto nível)
> 2. Spec & capabilities (B) → `spec.py`, `politica.py`
> 3. Grafo/reconciliação (C) → `grafo.py`
> 4. Segurança do validador `comando` (D) → `grafo.py::executar_comando_seguro` + `registro.py`
> 5. Eventos (E) → `eventos_schema.py`, `eventos.py`
> 6. Curador anti-Goodhart (F) → `curador.py`
> 7. Fundador/Caixa (G) → `caixa.py`

Cada fatia entrega `motor/docs/auditoria/ACHADOS-<vendor>-<fatia>.md` — ranqueado por severidade (🔴/🟡/🟢), cada achado com **evidência** (`arquivo:linha` + teste que falha, quando aplicável). Depois agregam-se os ACHADOS por vendor.
Fatiar cabe no contexto, foca a atenção (auditor em 3 arquivos > auditor folheando 30) e reduz a superfície de falso-positivo dos safeguards (mensagens menores e defensivas).

### Fase B — Cross-examination
Cada auditor lê os achados do outro e os critica: marca falso-positivo, funde duplicata, resolve discordância. Sai `motor/docs/auditoria/ACHADOS-UNIFICADOS.md` — lista única, priorizada, sem ruído.

### Fase C — Correção gated
Cada achado vira, nesta ordem: (1) um **teste/cheque que FALHA** demonstrando o defeito; (2) o **fix**; (3) passa pelo **Gate de CI** + **revisão do vendor OPOSTO** ao que corrigiu (Claude corrigiu → GPT revisa, e vice-versa). Registrar no `LOG-VERIFICACAO.md` com SHA. Quem corrige pode ser o próprio par de fronteira (ambos resetaram) ou o free/GPT-5.5 no mecânico — mas a revisão cruzada é sempre do vendor oposto.

### Fase D — Re-auditoria até limpo
Repete A→C até nenhum dos dois achar novo defeito ≥ médio. Aí o motor é **declarado produção** (registrar o veredito duplo no LOG + tag git `motor-v1.0`).

## O prompt de cada auditor (Fase A) — colar no auditor Anthropic (Opus 4.8/Fable) e no GPT-5.6
> **Enquadramento defensivo (é hardening do próprio sistema — não segurança ofensiva).** "Você é auditor de qualidade e robustez do **motor** (backend Python) da minha própria meta-fábrica — uma revisão de engenharia **defensiva** antes de declarar produção. Objetivo: confirmar que cada invariante em `motor/docs/INVARIANTES.md` se sustenta e identificar defeitos de correção, robustez e segurança **para corrigir** (hardening do meu sistema). NÃO conserte — verifique e evidencie. Rode o graphify pro mapa, LEIA na íntegra todo arquivo que for auditar (o mapa localiza; o julgamento exige o código real), rode a suíte (`pytest`) e o Gate de CI. Para CADA invariante, verifique se ele realmente se mantém; se encontrar um caso onde não se mantém, escreva um teste que demonstre a falha para corrigirmos. Áreas de atenção: correção sob concorrência, tratamento de erro parcial, o loop de reconciliação, robustez do curador (evitar que uma métrica de custo aprove uma regressão de qualidade), validação de entrada no executor de comando (garantir que só executáveis permitidos rodem e que argumentos sejam tratados com segurança), consistência do schema de eventos, dívida silenciosa, testes que não provam nada, e a fronteira 'promoção é intenção, não aplicação automática' (ADR-003). Entregue `motor/docs/auditoria/ACHADOS-<seu-nome>.md` priorizado por severidade com evidência (`arquivo:linha` + teste). Trabalhe de forma independente — não assuma o que outro auditor achou."
>
> *Nota: o auditor Anthropic pode ser Fable-5 ou Opus 4.8 (mesmo vendor). Se o safeguard do Fable marcar falso-positivo em trabalho defensivo, use Opus 4.8 — é frontier de topo e serve igual como o cadeado Anthropic. O 2º cadeado (GPT-5.6) preserva a diversidade de vendor. E dê feedback do falso-positivo via `/feedback`.*

## Timing & disciplina
- **Roda antes de sábado** (Claude zera sábado), na janela com Claude (resetado) + GPT-5.6 disponíveis.
- **Um passe caro, cirúrgico, com alvo pronto.** Não gaste os frontier no mecânico — free/GPT-5.5 fazem correção de baixo risco; os frontier fazem o **julgamento** (auditar + revisar cruzado).
- Dispara **só quando o motor é candidato a produção** — que já é o caso agora.

## Saída
Motor declarado produção = gate verde + invariantes testados + os dois vendors assinando, sem achado novo ≥ médio. De brinde: os `ACHADOS-*` viram dataset de "o que os melhores acham defeito" — combustível do curador (Alvo 2) pra evoluir a fábrica.

---
*Charter criada 2026-07-04. Base estratégica: vault `2. Roadmap Estratégico/9. Auditoria Final — Dual Frontier`. Alvo: `INVARIANTES.md`. Executores: Claude + GPT-5.6, vendors distintos.*
