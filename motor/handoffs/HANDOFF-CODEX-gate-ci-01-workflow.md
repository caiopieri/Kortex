# HANDOFF CODEX — Gate de CI: Criação do Workflow do GitHub Actions (Fase 4, Passo 1)

## Por quê (ROADMAP Alvo 1)
Atualmente, o monorepo do Orquestrador não possui um gate automático de CI para validar as entregas do agente nos PRs antes do merge. Isso faz com que a qualidade seja "auto-reportada", o que viola o princípio de que o julgamento deve ser mecânico e neutro ("a máquina decide, o agente propõe").
Este handoff cria o arquivo `.github/workflows/ci.yml` na raiz do monorepo para rodar validações em máquina neutra a cada Pull Request e push na branch `main`.

## O que fazer
Crie o arquivo `.github/workflows/ci.yml` na raiz do monorepo `/Users/caioamaraldepieri/Desktop/Projects/Orquestrador/` com a seguinte configuração:

1. **Trigger:** Executar a cada `push` ou `pull_request` direcionado para a branch `main`.
2. **Ambiente:** Executar em `ubuntu-latest`.
3. **Passos do Pipeline (Jobs):**
   - **Checkout:** Fazer o checkout do repositório.
   - **Setup Python:** Configurar o Python usando `actions/setup-python` (versão 3.10 ou 3.11 para estabilidade).
   - **Cache de Dependências:** Configurar cache do `pip` ou usar `uv` para instalação rápida.
   - **Instalação:** Instalar dependências de desenvolvimento do motor (`pip install -e "motor/[dev]"` ou `uv pip install -e "motor/[dev]"`).
   - **Job 1: Lint:** Rodar `ruff check motor/` (ou linter equivalente).
   - **Job 2: Type-check:** Rodar `mypy motor/` para validação de tipos.
   - **Job 3: Test:** Rodar `pytest motor/` para executar a suíte de testes.
   - **Job 4: Build Check:** Garantir que o pacote python do motor pode ser construído e instalado sem erros.
   
*Observação:* Para manter o tempo de CI `< 5 min` (restrição dura), utilize ferramentas modernas rápidas (como `ruff` ou cache agressivo de dependências).

## DoD (Falsificável)
1. O arquivo `.github/workflows/ci.yml` existe na raiz do repositório.
2. A sintaxe do YAML é válida.
3. O pipeline executa lint, type-check, tests, e build de forma sequencial ou paralela.
4. O tempo total de execução simulado ou esperado é `< 5 min`.
