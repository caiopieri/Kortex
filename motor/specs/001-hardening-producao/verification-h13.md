# Verificacao H13 - snapshot consolidado

Status: **NAO APROVADO PARA PRODUCAO**
Data: 2026-07-12
Ambiente: macOS, CPython 3.11.15

## Resultado Executivo

O hardening corrigiu e provou H00-H04, H05a, H06a-H06b, H07a-H07e, H08,
H09a-H09c, H10a-H10b, H11 e H12a. O snapshot nao satisfaz ainda o criterio global:

1. H05b nao possui backend real de sandbox; C2/C3 continuam indisponiveis.
2. S4 nao possui reserva/hard-stop runtime; H12b aguarda revisao humana em
   `plan-h12b.md`.

Default-deny impede que essas lacunas virem execucao silenciosa, mas nao prova as
capacidades ausentes.

## Gate De Testes

| Checagem | Resultado |
|---|---|
| Suite autoritativa: rastreados + `test_hardening_*` + manifest + empacotamento | `625 passed` |
| `pytest motor/` literal no working tree compartilhado | `721 passed, 15 failed` |
| Overlay bruto dos oito arquivos de auditoria | `96 passed, 15 failed` |
| Manifest H00 | integro; corpus, hashes, dispositions e replacements validos |

As 15 falhas literais sao totalmente classificadas:

- 6 controles de comando precisam do plugin/fake test-only explicito e nao podem ativar
  runner host por default;
- 7 oraculos estao registrados como `oracle_migrated` ou `rejected_contract`;
- 2 reprodutores H05b exigem backend real para output limitado e TERM/KILL de descendentes.

Nenhuma falha inesperada permaneceu fora dessas classes. Os arquivos soltos
`test_auditoria_*.py` sao copias de trabalho do corpus congelado e nao pertencem ao landing;
os wrappers materializam o tar content-addressed e executam somente dispositions autorizadas.

## Gates Estaticos E Artefatos

| Checagem | Resultado |
|---|---|
| Ruff `motor/` | limpo |
| mypy autoritativo, producao + testes que pousam | limpo, 69 arquivos |
| mypy literal `motor/` | 6 erros no controle H09 congelado/migrado |
| Bandit high/high | limpo |
| compileall | limpo |
| `git diff --check` | limpo |
| Gitleaks sem historico em `motor/` | limpo, 18.94 MB |
| build sdist/wheel | passou |
| fechamento de dependencias do sdist | passou |
| install isolado + smoke do wheel | passou |

Build: `/tmp/orquestrador-final2-build.C2uZ60`.
Install: `/tmp/orquestrador-final2-install.y3px4s`.

`MANIFEST.in` inclui helpers, validador, matriz, manifest e corpus exigidos pelos packs que
o sdist distribui. O wheel continua contendo somente runtime. Como o checkout esta sujo, o
sdist de verificacao tambem enxerga copias soltas de testes; artefato de release precisa ser
reconstruido de checkout limpo.

## Estado Por Fronteira

| Fronteira | Estado |
|---|---|
| Kernel/spec/grafo | sustentado no escopo H01-H03 |
| Comando C1/C4 | sustentado; identidade/argv/default-deny |
| Comando C2/C3 | **indisponivel** sem H05b real |
| Eventos E1/E2 | sustentado por H06-H07 |
| Curador U1/U2 | sustentado por H08/H09a/H09c |
| Curador U3/K4 | fail-closed; protocolo sustentado, repo real nao fornecido |
| Caixa F1/F2 | sustentado como at-least-once + dedupe por `decision_id` |
| Gates F3 | `promocao` manual-only; plano/cobertura nao sensiveis no contrato atual |
| Capacidades S3 | sustentado por H12a; `None|[]` preservam legado |
| Orcamento S4 | **nao sustentado**; H12b pendente |

## Security DoD

O checklist foi restaurado em `motor/docs/security-DoD.md`, com ponteiro em
`docs/security-DoD.md`. No snapshot:

- input, schemas, paths, IDs, eventos e decisoes possuem testes hostis;
- concorrencia/crash foi exercitada em JSONL, Caixa/outbox e servico;
- runner ausente, repo ausente e rota incapaz falham fechado;
- secrets/SAST/lint/types/build do conjunto autoritativo estao limpos;
- sandbox H05b e hard-stop H12b permanecem `bloqueado`, nunca `N/A`.

## Proxima Decisao

`plan-h12b.md` termina no ponto de parada humano exigido pelo spec-kit. Antes de editar
H12b0-H12b4, decidir entre:

1. arquitetura completa com SQLite por run, tentativa unica custeada, pricing versionado e
   adaptadores reais;
2. default-deny total de clientes sem contrato de custo, aceitando indisponibilidade.

H05b exige tambem engine, imagem por digest, policy e job de conformidade reais. Docker CLI
existia no host, mas o daemon estava inacessivel e nenhuma imagem/policy confiavel podia ser
enumerada.

## Onde isto pode dar errado

- `625 passed` nao substitui `pytest motor/` em checkout limpo; a selecao so e valida se o
  landing excluir as copias soltas e preservar corpus/manifest/wrappers.
- Um daemon Docker iniciado depois nao certifica H05b sem imagem, policy e conformidade.
- Opcao B de H12b evita overshoot, mas torna o motor inutil para workflows com modelo; nao
  deve ser vendida como orcamento funcional.
- O repo fake do curador prova protocolo, nao autenticidade ou imutabilidade de deployment.
- Build de checkout sujo nao e artefato de release, mesmo com smoke verde.
