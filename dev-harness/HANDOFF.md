# HANDOFF — Continuar este trabalho

> Para um agente novo (Claude Code, sessão limpa). Leia este arquivo + os referenciados abaixo.
> Você está continuando um projeto de **metodologia/harness de desenvolvimento com IA**.
> A continuidade está aqui e nos artefatos — não em nenhum histórico de chat. Isso é proposital (FIC).

> **⚠️ ATUALIZAÇÃO (Fase 4).** O motor do fluxo migrou para o **github/spec-kit** (decisão travada).
> A teoria da Fase 2, o `security-DoD` e os tiers continuam — agora como **constitution** do spec-kit.
> Novos documentos canônicos: `fase4-roadmap-ciclo-de-vida.md`, `spec-kit-adocao.md` (mapeamento +
> constitution pronta), `COMO-FUNCIONA-passo-a-passo.md`, e os templates `docs/discovery-template.md`
> + `docs/ROADMAP-template.md`. **Aposentados:** `.claude/skills/fic-*` e `docs/spec-template.md`.
> Próximo passo real: piloto no Logisti (`specify init` + constitution + 1ª fatia).

## Objetivo
Estabelecer boas práticas de desenvolvimento com IA para **todos os projetos** do dono (portfólio: **Logisti**, **Flint**, **e-commerces com apps iOS e sistemas web**). Meta: software coerente, seguro e no escopo; eficiência de token como subproduto, não como alvo.

## O que já existe — leia nesta ordem
1. `fase2-teoria-framework.md` — a teoria (o porquê).
2. `dev-harness/PLAYBOOK.md` — o processo, para o humano administrador.
3. `dev-harness/global/CLAUDE.md` — núcleo universal (vai em `~/.claude/CLAUDE.md`).
4. `dev-harness/project-template/AGENTS.md` (+ shim `CLAUDE.md`) — instruções por projeto.
5. `dev-harness/docs/` — `security-DoD.md` (multi-stack) e `spec-template.md`.
6. `dev-harness/.claude/skills/fic-*` — fluxo Research → Plan → Implement.
7. `dev-harness/examples/logisti.AGENTS.md` — exemplo preenchido.

Ignore: `logisti-harness/` (rascunho, **substituído** pelo `dev-harness/`). `escopo-pesquisa-...md` é o escopo inicial (Fase 0), opcional.

## Decisões travadas (não relitigar)
- **Tese central:** os cinco problemas (incoerência macro, insegurança, sycophancy, over-engineering, ineficiência) têm **uma causa** — o modelo é sem estado, otimiza local e é treinado pra agradar/adicionar. A alavanca é o **ambiente/harness**, não o modelo. Scaffolding > capacidade.
- **Arquitetura:** o orquestrador supre as faculdades que o modelo não tem (memória, escopo, autocontenção, consciência, ceticismo, economia).
- **Eficiência de token é derivada** da qualidade de contexto. Não perseguir direto.
- **Fluxo FIC:** Research → Plan → Implement; cada fase compacta num artefato (~200 linhas) salvo em `docs/specs/<feature>/`. Humano revisa o **plano** (alavancagem máxima) e o **diff**.
- **Sessão:** `/clear` entre specs e antes do implement. Continuidade vive nos arquivos.
- **Arquivos:** `AGENTS.md` é a fonte da verdade (portável p/ Codex); `CLAUDE.md` é shim `@AGENTS.md` (Claude Code não lê AGENTS.md nativamente). Núcleo universal fica em `~/.claude/CLAUDE.md`.
- **Unidade:** 1 spec ≈ 1 PR ≤ ~300 linhas. Spec/PRD proporcional ao risco; trivial pula.
- **TDD pragmático;** nunca apagar teste sem autorização.
- **Orquestrador = o humano.** Não construir swarm autônomo. Máx 2-3 agentes em paralelo. Validação não é delegável (gate automático + revisão humana do plano e do diff).
- **Enforcement de ferramenta:** `allowed-tools` no skill **não é imposto** — usar **dev container/sandbox** para autonomia.
- **Registro profissional:** commitar spec + ADR para decisões grandes; gitignore de `research.md`/`progress.md` (rascunho); o registro real é git/PR.
- **Ferramentas externas** (claude-mem, graphify, code-review-graph, ruflo, etc.): adotar só quando a **escala** justificar — hoje seria over-engineering. `rtk` é o único barato/sem-risco de experimentar já.

## Como se comportar (reforço do núcleo)
- Anti-bajulação: propor o melhor mesmo contrariando o pedido; terminar propostas com `### Onde isto pode dar errado`; calibrar (não ser contrário por esporte).
- **Verificar detalhes de produto na doc oficial antes de afirmar** — ferramentas mudam.
- Conversa longa ≠ acordo (sycophancy cresce ao longo dos turnos).

## Estado atual
- Pesquisa → teoria → implementação → playbook: **completos.**
- **Nada validado em projeto real ainda.** É hipótese bem-fundamentada.
- **Próximo passo que destrava tudo:** primeiro uso real. Candidatos: migração de uma tabela do Logisti para Supabase (exercita RLS + escopo + gate), ou o sistema de marketplace do zero (exercita o ciclo de arquitetura).

## Threads abertas / honestidade
- Seções de segurança de e-commerce e iOS são genéricas-sólidas, **não auditadas** para o Flint nem para os e-commerces reais — afinar quando os stacks forem conhecidos.
- O harness tem overhead; aplicar com proporção (não em tarefa descartável).
- Se o contexto (AGENTS.md/docs) não for mantido vivo, ele mente — pior que não ter.

## Instrução para o humano usar este handoff
Na sessão nova, com o `dev-harness/` acessível, diga:
> "Leia `dev-harness/HANDOFF.md` e os arquivos que ele referencia. Você está continuando este trabalho. Comece confirmando o estado e o próximo passo."
