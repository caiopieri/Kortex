# Verificacao - onda H03/H06a/H10a

Status: **CONCLUIDA NO ESCOPO DA ONDA**  
Data: 2026-07-11  
Ambiente de teste: CPython 3.11.15

## Resultado

- H03 converte excecoes externas do executor/verifier em evento sanitizado e resultado
  reprovado, preserva retry e bloqueia dependentes tanto no DAG inicial quanto na reconciliacao.
- H06a publica schema de eventos v2, valida envelope/payload/tipos antes do primeiro byte e
  reserva `evento`, `t` e `seq` ao writer.
- H10a valida nota, portao, opcoes, symlink e `job_id`; usa deadline monotonico, preserva a
  nota no timeout e evita colisao de nomes arquivados no mesmo segundo.

## Oraculos Migrados

O corpus content-addressed nao foi alterado. Dois casos permanecem coletaveis no inventario,
mas nao representam o contrato aprovado:

- K2 antigo exigia que `RuntimeError` escapasse; foi substituido por
  `tests/test_auditoria_codex.py::test_g4_excecao_do_executor_vira_resultado_e_evento_de_erro`.
- E1 Codex aceitava sobrescrever o envelope; foi substituido por
  `tests/test_hardening_h06a.py::test_e1_colisao_com_envelope_falha_antes_do_write`.

As linhas usam `disposition=oracle_migrated`, `landing=replacement_test` e
`replacement_nodeid`. O validador H00 confirma que a regressao substituta existe e que o
corpus original continua com os hashes congelados.

## Gate

| Checagem | Resultado |
|---|---|
| Suite rastreada, sem packs futuros | `432 passed` |
| Pack completo como overlay | `491 passed, 52 failed` |
| Manifest/corpus/matriz | valido; `100 failures, 11 controls, 24 invariantes` |
| Ruff | limpo |
| mypy | limpo, 68 arquivos |
| Bandit high/high | limpo |
| compileall | limpo |
| Gitleaks dir (`motor/`) | limpo, 16.25 MB |
| build sdist/wheel | passou |
| install e import do wheel isolado | passou; schema v2 |

O job de testes do CI global continua vermelho de forma esperada: as 52 falhas incluem H04+
e os oraculos congelados que foram formalmente migrados. Logo, esta verificacao nao declara o
motor pronto para producao nem o Gate CI global aprovado.

## Security DoD

- Universal/input: atendido nas fronteiras alteradas; tipos, IDs, paths, nota e decisoes
  falham fechados.
- Erros: H03 nao registra mensagem, prompt ou stack de excecao externa.
- Injecao/path: H10a rejeita separadores, controles, IDs ocultos e symlinks de nota.
- Segredos/SAST: Gitleaks e Bandit high/high limpos.
- Autorizacao/banco: N/A para H03/H06a; H10b ainda e dono do ledger/outbox.
- Ambiente/autonomia: **nao atendido nesta sessao**. Os comandos rodaram no host com acesso
  amplo, nao em dev container. H04-H05 continuam bloqueados para producao ate sandbox real.

## Escopo E Tamanho

- H03 ficou em aproximadamente 299 linhas entre producao e teste causal.
- H06a ficou em aproximadamente 200 linhas.
- H10a ficou abaixo de 170 linhas, incluindo controles adicionais.
- H04/H05, H06b/H07 e H10b/H11 nao foram antecipados.

O build e apenas verificacao local: como o checkout contem fontes de auditoria nao rastreadas,
o sdist tambem as inclui. Um artefato de release deve ser reconstruido de checkout limpo apos
H13.

## Onde isto pode dar errado

- `except Exception` esta limitado a chamadas de modelo, mas um cliente composto pode ainda
  classificar bug interno do provider como falha externa; observabilidade deve continuar
  sanitizada sem esconder contagem/tipo operacional.
- H06a valida o evento individual, nao oferece append atomico, lock, `seq`, recovery ou JSON
  finito; essas garantias pertencem a H07.
- H10a fecha o arquivo Markdown, mas nao torna consumo/arquivamento transacional ou idempotente;
  concorrencia, crash e replay pertencem a H10b/H11.
- Os 52 casos vermelhos e a ausencia de sandbox impedem qualquer declaracao de producao.
