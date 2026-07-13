# Verificacao - H08/H09 curador anti-Goodhart

Status: **CONCLUIDA NA FRONTEIRA; REPOSITORIO REAL NAO FORNECIDO**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Discovery E Contrato

A fatia fresh usou Graphify e leu integralmente `motor/motor/curador.py`. H08, H09a,
H09b e H09c foram mantidos como landings independentes, cada um abaixo de 300 linhas.

- H08 entrega copia profunda na entrada e saida do runner. Mutacao, alias e excecao de um
  caso nao alteram held-out nem abortam os casos seguintes (`motor/motor/curador.py:228`).
- H09a produz evidencia v2 deterministica e selada sobre policy, identidades e resultados
  por caso. Certificacao verifica o selo e recomputa agregados; campos agregados fornecidos
  pelo chamador nao decidem (`motor/motor/curador.py:287`).
- `min_casos`, IDs unicos, split held-out, proveniencia, booleanos estritos e custos
  completos/finitos sao hard gates. Qualidade e avaliada antes de custo.
- H09c impede overflow da media de custos finitos e revalida dominio/finitude das metricas;
  identidade e proveniencia somente whitespace sao vetadas
  (`motor/motor/curador.py:508`, `motor/motor/curador.py:549`).
- H09b exige `certification_id` resolvido por `RepositorioCertificacoes`. Sem repositorio,
  dict, hash isolado, JSON e CLI falham fechado (`motor/motor/curador.py:19`,
  `motor/motor/curador.py:354`).
- O registro e copiado, sua evidencia e recomputada e a decisao persistida precisa ser
  exatamente igual a recomputada. Sucesso gera somente `promocao_pendente` com
  `requer_gate=True`; nao existe apply nem evento `curador.promoveu`.

## Governanca Dos Oraculos

O controle congelado
`test_promocao_valida_permanece_intencao_gateada_sem_evento_de_apply` usava um dict como
autoridade e contradizia a clarificacao H09b. O corpus e hash foram preservados; o manifest
registra `oracle_migrated/replacement_test` e aponta para
`test_repo_valido_gera_somente_intencao_gateada_sem_aliases`. Nenhum adapter oculto
reinterpreta o dict legado.

## Evidencia Causal

| Fatia | Garantia | Teste |
|---|---|---|
| H08 | read-only profundo e erro isolado por caso | `motor/tests/test_hardening_h08.py` |
| H09a | evidencia v2, policy, held-out e recomputacao | `motor/tests/test_hardening_h09a.py` |
| H09b | repo default-deny, vinculo e somente intencao | `motor/tests/test_hardening_h09b.py` |
| H09c | overflow e identidades whitespace | `motor/tests/test_hardening_h09c.py` |
| Integracao | eventos publicos continuam schema v2 | `motor/tests/test_hardening_h06b.py` |

## Gate Da Fatia

| Checagem | Resultado |
|---|---|
| H06b + H08 + H09a-H09c + curador/schema + manifest | `90 passed` |
| Ruff | limpo |
| mypy | limpo |
| Bandit high/high | limpo |
| compileall | limpo |
| H08 | aproximadamente 162 linhas |
| H09a | aproximadamente 289 linhas |
| H09b | aproximadamente 235 linhas |
| H09c | aproximadamente 91 linhas |

O Gate CI e o build/install do snapshot final ainda serao repetidos em H13.

## Security DoD

- Runner recebe copia profunda e a evidencia nao compartilha aliases com input/resultado.
- Evidencia corrompida, incompleta, nao selada ou numericamente invalida e rejeitada.
- Custo menor nunca compensa qualidade igual ou pior.
- Repositorio ausente e o default. Fake existe somente nos testes e nao qualifica autoridade
  de producao.
- CLI/export sao consulta e nao criam intencao autoritativa.

## Onde isto pode dar errado

- SHA-256 prova integridade, nao autenticidade. Policy, dataset e provenance so ganham
  autoridade quando um repositorio confiavel do deployment os registra imutavelmente.
- O protocolo nao fornece esse backend. Enquanto ele nao existir, promocao operacional deve
  permanecer indisponivel, embora K4 continue seguro.
- Callback de sombra e codigo Python injetado; copia profunda impede aliases, nao sandboxa
  filesystem, rede ou efeitos externos do callback.
- Excecoes preservam tipo e mensagem para compatibilidade do oracle; mensagens de excecao
  produzidas por bibliotecas podem variar entre ambientes.
