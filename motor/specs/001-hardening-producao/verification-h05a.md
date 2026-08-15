# Verificacao - H05a fronteira de comando default-deny

Status: **CONCLUIDA NO ESCOPO H05a; H05b NAO IMPLEMENTADA**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Contrato Entregue

Graphify foi consultado antes da leitura integral de `motor/motor/grafo.py` e
`motor/motor/registro.py`. A fatia separou validacao H04 de execucao H05:

- `CommandRequest` transporta `argv`, workspace e timeout de forma tipada; os limites de
  conformidade ficam publicos em `motor/motor/runner.py:8`.
- `CommandRunner` e uma fronteira de composicao, nao uma certificacao de sandbox
  (`motor/motor/runner.py:32`).
- Sem runner injetado, `construir_grafo` usa `DenyCommandRunner` e nenhum subprocesso local
  e iniciado (`motor/motor/grafo.py:376`, `motor/motor/grafo.py:385`).
- A validacao H04 ocorre antes da delegacao ao runner (`motor/motor/grafo.py:744`).
- Execucao local existe apenas em `motor/tests/runner_fake.py` e precisa ser injetada
  explicitamente. Ela nao qualifica producao e nao integra wheel de runtime.

## Evidencia Causal

| Garantia | Evidencia |
|---|---|
| Quatro reprodutores H05a | `motor/tests/test_hardening_h05a.py:12` |
| Resultado expoe timeout e truncamento tipados | `motor/tests/test_hardening_h05a.py:17` |
| H04 preserva argv sem shell | `motor/tests/test_hardening_h04.py` |
| Runner ausente falha fechado | reprodutores H05a sem plugin |
| Runner local e exclusivamente test-only | `motor/tests/runner_fake.py` |

## Gate Da Fatia

| Checagem | Resultado |
|---|---|
| H05a | `5 passed` |
| H01/H04/H05a wrappers | `38 passed` |
| H04/H05a + grafo/ferramenta/validadores | `85 passed` |
| Ruff | limpo |
| mypy | limpo |
| Bandit high/high | limpo |
| compileall | limpo |
| Diff H05a | aproximadamente 154 linhas; abaixo de 300 |

O Gate CI global e o build/install do snapshot final ainda nao foram executados. H05b
continua sem backend real no repositorio; portanto C3 e a capacidade de comando em producao
nao estao declarados concluidos.

## Security DoD

- Input externo nao escolhe shell nem cria fallback local.
- O default e negar, inclusive quando a composicao esquece o runner.
- O fake fica fora da fronteira de runtime e deve continuar ausente da configuracao de
  deployment.
- Nao existe alegacao de isolamento por `cwd`, validacao de string ou protocolo Python.

H13 restaurou o checklist canonico em `motor/docs/security-DoD.md`. Esta verificacao foi
executada antes da restauracao e usou as regras universais do AGENTS; ela nao retroage uma
certificacao de sandbox.

## Onde isto pode dar errado

- O protocolo nao limita filesystem, ambiente, rede, output ou arvore de processos por si
  so. Somente um backend real aprovado pela suite H05b pode habilitar comandos em producao.
- `CommandRequest.argv` usa identidade absoluta do host; um adapter de container precisa
  mapear essa identidade de forma explicita, sem voltar a confiar em basename.
- Carregar deliberadamente `tests.runner_fake` fora dos testes executa no host e viola o
  contrato de producao.
