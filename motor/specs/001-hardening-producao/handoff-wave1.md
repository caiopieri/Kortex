# Handoff — proxima conversa, onda 1

Carregar somente:

1. `plan.md`, `tasks.md` e `verification-wave0.md`;
2. `reproducer-manifest.jsonl`, filtrando pelo owner da fatia;
3. os arquivos de producao explicitamente listados abaixo.

Nao reler o repo inteiro nem os oito fontes do corpus. `tests/audit_corpus.py` executa os
nodeids congelados sem duplicar o codigo da auditoria.

## Estado De Entrada

- H00/H01/H02 concluidos; gate Python 3.11: `375 passed`.
- Ruff, mypy, Bandit high/high, compileall, Gitleaks, build e install passam.
- Overlay residual: 54 falhas GPT5 e 17 Codex.
- H01/H02 alteraram `politica.py`, `spec.py` e `grafo.py`; nao reverter.

## Ordem

1. H03: `grafo.py`; excecoes tipadas, resultado reprovado e bloqueio de dependentes.
2. H06a: `eventos_schema.py`, `eventos.py`; envelope v2 e validacao antes do write.
3. H10a: `caixa.py`; IDs, paths, opcoes, nota parcial e deadline.

No maximo duas frentes. H03 e H06a podem ser analisados em paralelo porque nao compartilham
arquivo; H10a inicia quando uma delas fechar. Cada PR executa somente os casos do seu owner
mais a suite rastreada e permanece abaixo de aproximadamente 300 linhas.

## Riscos A Triar Antes De H13

- traversal em nome de artefato antes de `registrar_artefato`;
- caminho host arbitrario em `fonte_rag` (RAG estava fora da spec aprovada);
- whitespace em campos estruturais e booleanos aceitos nos limites inteiros da spec.

Nao encaixar esses itens silenciosamente em H03/H06a/H10a. Criar reprodutor e owner ou
formalizar uma fatia adicional antes de alterar producao.

## Onde isto pode dar errado

- H03 pode crescer e absorver sandbox H04/H05; limitar-se a falha parcial e dependencias.
- H06a nao deve adicionar todos os payloads `curador.*`; isso pertence a H06b.
- H10a nao deve antecipar ledger/outbox SQLite, reservados a H10b/H11.
