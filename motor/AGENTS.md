# AGENTS.md — motor (kernel da meta-fábrica)

> Convenções de trabalho neste pacote. Leia isto antes de mexer. A **visão** está em
> `../docs/LEIA-PRIMEIRO.md`; o **norte do motor** em `docs/EVOLUCAO.md`; a **fronteira MCP** em
> `docs/ARQUITETURA-MCP.md`. Este arquivo é só "como trabalhamos aqui".

## Como o trabalho chega
- As tarefas vêm como **HANDOFFs travados** (em `handoffs/`, ou passados na conversa). Cada handoff traz:
  objetivo, mudanças precisas, restrições, e **DoD (critérios de falsificação)**.
- **Execute UM handoff por commit.** Não relitigue decisões já travadas no handoff/docs — se discordar,
  pare e levante a questão; não mude o escopo por conta própria.
- Ao terminar: rode os testes, confira o diff, e relate (diff + resultado dos testes).

## Regras permanentes (valem em toda tarefa)
- **Inerte por default.** Toda extensão entra atrás de flag/registro/versão **sem quebrar a suíte**. O
  comportamento atual não muda a menos que explicitamente ligado.
- **A spec é a dinâmica; o grafo é fixo.** Feature nova = mudança na WorkflowSpec (dado), não nó novo no
  código. Padrão novo entra por versão de spec certificada, um de cada vez.
- **Nó é função pura** que chama uma capacidade (`cliente.chamar(papel, prompt)`). NÃO dê ao nó
  ferramentas de auto-organização (to-do/checklist) — o organizador é o grafo; progresso = eventos;
  workspace = `runs/<id>`; contexto = `deps_txt`. Estado mutável compartilhado entre nós é anti-padrão.
- **Músculo, não autoridade.** O motor não decide permissão/risco/dinheiro/identidade; o gate sobe cru.
- **Testes são o DoD — não edite teste pra passar.** Se um teste falha, conserte o código (ou o handoff
  está errado: pare e avise).
- Não criar parser mágico pra prosa de LLM; ajustar prompt, não topologia.

## Rodar e validar
```bash
pip install -e ".[dev]"
python3 -m pytest -q          # python3, NÃO python. Suíte sem rede (ClienteStub).
python3 -m compileall -q motor tests
```
- Rede/LLM real só nos exemplos/runbooks (`docs/RUNBOOK-*.md`); a suíte não precisa de rede.
- `python` não existe no Mac do dono — sempre `python3`.

## Git / higiene
- Um commit = uma mudança lógica, mensagem clara.
- Lock órfão recorrente: `rm -f .git/index.lock` antes de commitar.
- NÃO commitar runtime: `log.jsonl`, `motor.db*`, `runs/`, `__pycache__`, `*.egg-info`, `.DS_Store`
  (tudo no `.gitignore`).

## Onde as coisas estão
`motor/` (pacote) · `tests/` · `exemplos/` (specs + configs de modelo) · `scripts/` · `motor_painel/`
(painel que lê o JSONL) · `docs/` (norte, fronteira, runbooks) · `handoffs/` (histórico de handoffs).
