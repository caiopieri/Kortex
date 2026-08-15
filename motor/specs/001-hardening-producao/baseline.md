# Baseline H00

- Commit auditado: `25b38d77b3055ee2fffbc822495ee9dda674c7a7`
- Ambiente de referencia: CPython `3.11.15`, pytest `9.1.1`, macOS.
- Corpus: `reproducer-corpus-00bbc07deca063f5.tar`
- SHA-256 do corpus: `00bbc07deca063f5d96f9639e94f72f4a6b3aab428689f621f6c0fd0369b3542`

| Estado | Comando | Resultado |
|---|---|---|
| Checkout rastreado | pytest nos 25 `motor/tests/test_*.py` retornados por `git ls-files` | `333 passed` |
| Overlay GPT5 | pytest em `test_auditoria_gpt5_[a-g].py` | `78 failed, 11 passed` |
| Pack Codex anterior | pytest em `test_auditoria_codex.py` | `22 failed` |
| Worktree completo derivado | checkout + ambos os packs | `100 failed, 344 passed` |

Os 111 casos ficam congelados no corpus fora de `motor/tests`, portanto H00 nao muda a
coleta do pytest. O manifest define quando cada caso pousa; os dois casos Codex que tratam
`plano` e `cobertura` como sensiveis foram rejeitados porque contradizem a classificacao
explicitamente aprovada em `clarifications.md`.

## Onde isto pode dar errado

- O baseline local nao substitui CI Linux/Python 3.11; ele apenas prova a mesma contagem no
  ambiente auditado. O gate de cada PR ainda precisa executar no runner oficial.
