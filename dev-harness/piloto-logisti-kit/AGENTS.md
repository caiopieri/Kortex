# AGENTS.md — Logisti

> Fonte da verdade deste repo (portável p/ Codex/Cursor). O `CLAUDE.md` de uma linha importa este arquivo.
> O núcleo universal (comportamento, fluxo, DoD, alocação) vem do `~/.claude/CLAUDE.md` — não repetir aqui.

## [QUENTE] O que é

Sistema web de gestão para transportadora pequena de CAMINHÕES — usuário 0 é uma empresa
real com 3 caminhões e motoristas contratados, que hoje controla tudo manualmente. Fatia
atual: central de documentos da frota (vencimentos de licenciamento/seguro/CNH). Visão
futura: logística multi-modal (van, carro, moto) — por isso o domínio tem o campo `modal`,
mas SÓ caminhão tem regras e UI nesta fase. É produção — trate como tal.

## [QUENTE] Stack

- Frontend: Next.js (App Router) + TypeScript strict + Tailwind
- Backend: Next.js (server actions / route handlers) — sem serviço separado nesta fase
- Banco: Supabase (Postgres) com RLS ligada em TODA tabela de dado de usuário
- Infra / deploy: Vercel
- Testes: Vitest (unidade/lógica de negócio) — caminho crítico apenas (Tier T1)
- Integrações: nenhuma nesta fase

## [QUENTE] Restrições duras (não negociar sem aprovação)

- Estrutura de pastas e contratos definidos no plano da fatia não mudam dentro de uma tarefa.
- Lógica de domínio (vencimentos, status, regras de caminhão) vive em UM módulo puro
  (`src/domain/`), separado de UI e banco — testável sem mock de rede. Mudança de
  arquitetura é tarefa própria, com spec.
- NÃO construir abstrações multi-modal agora (sem strategy/factory por modal): o campo
  `modal` existe como enum com valor `caminhao`; o resto é YAGNI até a fatia de outros modais.
- NUNCA editar testes para fazê-los passar. Teste que parece errado = parar e reportar.
- Executor de tier barato: em ambiguidade, perguntar — não decidir design por conta própria.

## [QUENTE] Convenções deste projeto

- TypeScript strict; `any` proibido sem justificativa em comentário.
- Componentes funcionais; lógica de negócio fora de componentes.
- Validação com zod nas fronteiras (formulários e entrada de API).
- Rode `npm run lint && npm test` ao terminar qualquer tarefa.
- Nomes de domínio em português (Veiculo, Modal, Documento) — o usuário é brasileiro.

## [MORNO] Segurança específica

Seções de `docs/security-DoD.md` que se aplicam:
- [x] Banco / Postgres / Supabase — RLS em toda tabela; policies testadas (transportadora A não lê frota da B); service_role só no servidor; zero segredo no código.
- [x] Web — validar todo input; autorização em cada rota; erro não vaza interno.
- [ ] Mobile / iOS
- [ ] Bot / entrada de LLM

## [FRIO] Memória recuperável

- `docs/discovery.md` — por que este projeto existe e a fatia atual.
- `ROADMAP.md` — Now/Next/Later.
- `docs/specs/` — specs por feature (geradas pelo spec-kit em `.specify/`).
- `docs/telemetria.md` — registro por fase (modelo usado, tempo, retrabalho) — OBRIGATÓRIO no piloto.
