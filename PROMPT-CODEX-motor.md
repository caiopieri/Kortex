# Prompt para o Codex — implementar o Motor R3 (meta-fábrica)

Cole isto como instrução inicial do Codex que trabalha no **motor**.

---

Você é o EXECUTOR do motor da meta-fábrica (`Orquestrador/motor`). Sua tarefa é implementar o
roadmap **R3** já especificado. Não relitigue decisões: a spec está travada.

## Leia primeiro (nesta ordem)
1. `Orquestrador/motor/HANDOFF-CODEX-MOTOR-R3-roadmap.md` — seu plano de trabalho. Fases F1–F8,
   cada uma com contrato FIXADO, critério de aceite, arquivos e linhas exatas.
2. `Orquestrador/motor/ARQUITETURA-MCP-e-orquestrador.md` — por que essa forma e onde a
   fronteira corta (o que NÃO é do motor).
3. O código real que vai tocar: `motor/grafo.py`, `motor/__main__.py`, `motor/modelos.py`,
   `motor/caixa.py`, `motor/spec.py`, `motor/registro.py`, `motor/politica.py`.

## Regras (não quebrar)
- **1 fase = 1 commit** pequeno, na ordem do roadmap. `python3 -m pytest -q` VERDE ao fim de
  cada fase (rode antes de começar e anote o número atual de testes — é seu baseline).
- **Nunca apague nem afrouxe teste existente.** F1–F5 e F7 são aditivas e **inertes por
  default**: sem os campos/chamadas novos, o comportamento é byte-idêntico ao de hoje.
- **Preserve a validação humana e o caminho manual.** O gate sempre espera o fundador;
  `--auto` fica desligado no caminho de serviço; o `GerenciadorJobs` nunca auto-resolve. A
  CLI (`python -m motor` + `input()`) e a Caixa (`--caixa`, nota no vault) continuam
  intactas — o MCP é canal ADICIONAL, não substituto. Ambas leem o mesmo `motor.db`.
- **Escopo = meta-fábrica.** NÃO escreva no motor nenhuma lógica de permissão, classe de risco
  de gate (`dinheiro`/`identidade`), medição de custo, ou memória de segurança. Isso é do
  orquestrador/porteiro do Jarvis e de um MCP de finanças futuro. O motor só **expõe** o gate
  cru e aceita a decisão de volta. Se uma fase parecer pedir isso dentro do motor, **pare** —
  está errado.
- Python 3.14, stdlib + deps do `pyproject.toml`. Deps novas só as já autorizadas no roadmap:
  o SDK MCP (F6) e, se construir F8, um índice local (Chroma/sqlite-vec). Nenhuma outra sem anotar.
- Português nos comentários, como o resto do repo.
- **Ambiguidade não se chuta:** pare e registre em `## DÚVIDAS` no fim do roadmap; não invente.

## Ordem e prioridade
- **Trilha JARVIS (prioridade — é o que conecta a meta-fábrica ao Jarvis):**
  F3 → F4 → F5 → F6 → F7. F8 (RAG semântico) é opcional/depois — só com histórico.
- **Trilha HARNESS (independente):** F1 e F2 (extensões de `executar_ferramenta`). Pode fazer
  antes, depois, ou pular se o foco agora for o Jarvis. **Comece pela trilha Jarvis salvo
  instrução em contrário do Caio.**

## Definition of Done
Cada fase entregue conforme o "Critério de aceite" do roadmap, com os testes novos pedidos e a
suíte inteira verde. Ao terminar a trilha Jarvis, o resultado é: um servidor MCP
(`python -m motor.mcp_servidor`) que expõe `despachar_missao`, `status_missao`,
`responder_gate` e `resumo_missao`, rodando missões de forma durável e não-bloqueante, com o
gate sempre esperando decisão humana — sem ter tocado no núcleo do grafo.
