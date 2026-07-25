# Verificacao — onda H00/H01/H02

Status: **CONCLUIDA**  
Data: 2026-07-11  
Base: `25b38d77b3055ee2fffbc822495ee9dda674c7a7`  
Ambiente: CPython 3.11.15

## Resultado

- H00 congelou oito fontes em corpus content-addressed e validou a particao exata
  `78 failures GPT5 + 11 controls GPT5 + 22 failures Codex`.
- H01 tornou politica, decisoes, verifier, evaluator e ferramenta JSON fail-closed.
  Os 15 casos H01 do corpus passam sem tornar `plano`/`cobertura` sensiveis.
- H02 adicionou union discriminada para os tres validadores, custo finito estrito,
  capacidade nao vazia, tier fechado e revalidacao integral de edicao do plano.
  Os 14 casos H02 passam; testes independentes evitam o falso positivo do fixture antigo.
- As 11 specs JSON persistidas em `motor/exemplos` continuam validas.

## Gate

| Checagem | Resultado |
|---|---|
| Suite rastreada + H00/H01/H02 | `375 passed` |
| Manifest/corpus/matriz | `100 failures, 11 controls, 24 invariantes` validos |
| Ruff | limpo |
| mypy | limpo, 64 arquivos |
| Bandit high/high | limpo |
| compileall | limpo |
| Gitleaks dir (`motor/`) | limpo, ~15.7 MB |
| build sdist/wheel | passou |
| install wheel isolado | passou |

O overlay de auditoria ainda mede `54 failed, 35 passed` no pack GPT5 e
`17 failed, 5 passed` no pack Codex. As 71 falhas remanescentes pertencem a H03+ ou,
em dois casos Codex (`plano`/`cobertura` sensiveis), contradizem o contrato aprovado.
Portanto, o worktree completo ainda nao e gate de producao.

## Riscos Novos Fora Da Onda

A revisao adversarial externa apontou superficies anteriores que nao pertencem a H00-H02:

- nome de artefato pode conter traversal antes de `registrar_artefato`;
- `fonte_rag` aceita caminho do host e RAG foi explicitamente excluido desta spec;
- strings estruturais apenas com whitespace e inteiros booleanos ainda merecem contrato global.

Esses itens nao foram corrigidos silenciosamente. Precisam de reprodutor, owner e aprovacao de
escopo antes de entrar numa onda; ate la, impedem declarar o motor inteiro pronto para producao.
O build local tambem nao e artefato de release: o checkout contem fontes de auditoria nao
rastreadas; release deve ser reconstruido de checkout limpo.

## Onde isto pode dar errado

- Rodar somente `pytest motor/` neste worktree mistura casos futuros deliberadamente vermelhos
  com o gate rastreado da onda.
- O schema estrutural de `schema_json` nao valida o meta-schema completo; isso permanece risco
  residual ate `jsonschema` virar dependencia/contrato explicito.
