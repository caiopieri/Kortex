# AGENTS.md — Logisti  (EXEMPLO preenchido)

> Exemplo de como instanciar `project-template/AGENTS.md` para um projeto real.
> Note: comportamento, fluxo, DoD e alocação NÃO aparecem aqui — vêm do `~/.claude/CLAUDE.md`.

## [QUENTE] O que é
Gestão de frota para uma transportadora de pequeno porte (Brasil). Dados reais de operação. Produção.

## [QUENTE] Stack
- Frontend: React
- Backend: Node.js / Express
- Banco: SQLite → em migração para Supabase (Postgres) + deploy Vercel
- Integrações: bot Telegram + Gemini 2.5 Flash (parsing de foto de despesa)

## [QUENTE] Restrições duras
- Sem dependência nova sem justificar custo/benefício e alternativa nativa.
- Sem mudança de arquitetura dentro de tarefa de implementação — é tarefa própria, com spec.

## [QUENTE] Convenções deste projeto
- [preencher conforme o padrão real do repo: estilo, lint, scripts de verificação]

## [MORNO] Segurança específica
Seções aplicáveis de `docs/security-DoD.md`:
- [x] Banco / Postgres / Supabase  ← crítico na migração (RLS em toda tabela)
- [ ] Web / e-commerce / pagamentos
- [ ] Mobile / iOS
- [x] Bot / entrada de LLM  ← foto/texto do motorista é input hostil

## [FRIO] Memória recuperável
- `docs/specs/` — specs por feature.
- `docs/openapi.yaml` — API de frota (manter atualizada; alto valor como contexto).
