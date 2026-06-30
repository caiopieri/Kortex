# AGENTS.md — [NOME DO PROJETO]

> Vai na **raiz deste repo** como `AGENTS.md` (fonte da verdade, portável p/ Codex/Cursor).
> Crie também um `CLAUDE.md` de uma linha com `@AGENTS.md` — o Claude Code não lê AGENTS.md sozinho.
> O núcleo universal (comportamento, fluxo, DoD, alocação) vem do `~/.claude/CLAUDE.md` — **não repita aqui.**
> Aqui mora só o que é específico deste projeto. Mantenha enxuto.

## [QUENTE] O que é

[Uma a três frases: o que o software faz, pra quem. É produção? (Quase sempre sim — trate como tal.)]

## [QUENTE] Stack

- Frontend: [...]
- Backend: [...]
- Banco: [...]
- Infra / deploy: [...]
- Integrações: [...]

## [QUENTE] Restrições duras (não negociar sem aprovação)

- [O que NÃO pode mudar dentro de uma tarefa: estrutura de pastas, camadas, contratos de API.]
- [Mudança de arquitetura é tarefa própria, com spec.]

## [QUENTE] Convenções deste projeto

- [Ex.: "TypeScript strict, nunca `any` sem justificativa."]
- [Ex.: "Componentes funcionais, sem classe."]
- [Ex.: "Rode `npm run lint && npm test` ao terminar."]

## [MORNO] Segurança específica

Quais seções de `docs/security-DoD.md` se aplicam aqui:
- [ ] Banco / Postgres / Supabase
- [ ] Web / e-commerce / pagamentos
- [ ] Mobile / iOS
- [ ] Bot / entrada de LLM

## [FRIO] Memória recuperável

- `docs/specs/` — specs por feature (use `docs/spec-template.md`).
- `docs/openapi.yaml` — se houver API; é contexto de alta alavancagem, mantenha atualizado.
- [um doc por subsistema conforme o projeto cresce, registrando decisões e modos de falha conhecidos.]
