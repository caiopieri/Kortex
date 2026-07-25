# Tasks — onda 0 do hardening

Status: **CONCLUIDA — H00/H01/H02**  
Escopo autorizado: somente `H00 -> H01 -> H02`, nessa ordem.

## Regras de aterrissagem

- Conforme o plano aprovado, `H00` e um gate de rastreabilidade sem correcao causal: nao
  coleta os reprodutores vermelhos. Cada reprodutor so entra no PR da correcao causal.
- `H01` so inicia depois do gate H00; `H02` so inicia depois do gate H01.
- Nenhum `xfail`, `skip`, exclusao de coleta, relaxamento de assercao ou mudanca de H03+.
- O gate usa arquivos rastreados em checkout limpo; o worktree de auditoria e medido a parte.
- Producao + testes de cada PR deve ficar em aproximadamente 300 linhas ou menos.

## H00 — inventario verificavel

- [x] **T001 — Capturar baseline duplo**
  - Arquivos: `reproducer-manifest.jsonl`, `baseline.md`.
  - Fixar `HEAD 25b38d7`, Python 3.11 e resultados esperados: checkout rastreado `333 passed`;
    overlay GPT5 `78 failed, 344 passed`; worktree completo `100 failed, 344 passed`.
  - Orcamento: 25 linhas documentais.
- [x] **T002 — Manifest 1:1**
  - Arquivos: `reproducer-corpus.tar`, `reproducer-manifest.jsonl`.
  - Congelar os oito fontes fora da coleta pytest em corpus content-addressed, sem links ou
    paths absolutos/traversal; cada membro deve reproduzir o hash registrado.
  - Exatamente 100 falhas e 11 controles, cada qual com `nodeid`, SHA-256 do arquivo,
    origem, causa, invariante, owner Hxx e disposicao. Os 22 casos Codex exigem disposicao
    humana explicita, aprovador e fundamento, inclusive os que excedem o contrato aprovado.
    T004 fica bloqueada enquanto qualquer disposicao estiver pendente.
  - Orcamento: 111 linhas JSONL.
- [x] **T003 — Validador do manifest e matriz K1-F3**
  - Arquivos: `motor/tools/validar_manifest_reprodutores.py`,
    `motor/tests/test_manifest_reprodutores.py`.
  - Falhar por contagem, hash divergente, campo ausente, `nodeid` duplicado, owner invalido,
    membro ausente/inseguro, disposicao pendente ou qualquer um dos 24 invariantes sem owner.
  - Orcamento: 100 linhas de codigo/teste.
- [x] **T004 — Gate H00**
  - Rodar validador, teste causal do manifest e suite original rastreada.
  - Security-DoD: Universal. JSONL e corpus sao hostis; paths ficam presos ao corpus, sem
    symlink/traversal. Autorizacao/endpoint/segredos sao `N/A`; SAST continua obrigatorio.
  - PR H00 estimado: 236 linhas + corpus binario; natureza sem teste causal consta do plano
    aprovado (`H00: Nenhum; somente rastreabilidade`).

## H01 — decisoes e vereditos fail-closed

- [x] **T005 — Tipar politica e decisoes**
  - Arquivos: `motor/politica.py`, `tests/test_hardening_h01.py`.
  - Aceitar apenas `auto_mode: bool`, mapa `str -> decisao` e decisoes conhecidas por gate.
    Gate desconhecido e decisao desconhecida ficam manuais/fail-closed. `promocao`,
    `autorizacao`, `risco` e `dinheiro` ignoram master switch e overrides.
  - Controles: `plano:prosseguir`, `cobertura:prosseguir|preencher|abortar` continuam validos.
  - Aterrissar os `nodeid`s do manifest com owner H01 e preservar corpo/hash, salvo apenas
    imports/harness necessarios para separa-los de casos H03+; equivalencia fica registrada.
  - Orcamento: 75 linhas de producao + 80 de teste.
- [x] **T006 — Validar vereditos externos antes de controlar fluxo**
  - Arquivos: `motor/grafo.py`, `tests/test_hardening_h01.py`.
  - `aprovado` aceita somente booleano real em verifier, evaluator e ferramenta JSON.
    Parse/campo/tipo invalido reprova e emite a saida invalida existente; decisao interativa
    invalida nao prossegue nem sintetiza.
  - Nao capturar excecoes de executor nem alterar propagacao de dependentes (H03).
  - Orcamento: 70 linhas de producao + 60 de teste; PR H01 alvo: 285 linhas.
- [x] **T007 — Gate H01**
  - Rodar testes causais H01, controles da fatia e suite original rastreada.
  - Security-DoD: Universal + Bot/LLM. Saida de LLM e tipada; gates sensiveis permanecem
    fora do canal; rate limit/identidade sao `N/A` (sem endpoint novo).

## H02 — spec estrita e revalidacao pos-gate

- [x] **T008 — Modelos discriminados de validador**
  - Arquivos: `motor/spec.py`, `tests/test_hardening_h02.py`.
  - Modelar `schema_json`, `contem` e `comando` por `kind`; exigir configuracao executavel;
    rejeitar comando vazio e timeout booleano/fora de 1..300.
  - Aterrissar os `nodeid`s do manifest com owner H02 sob a mesma regra de equivalencia H01.
  - Orcamento: 90 linhas de producao + 65 de teste.
- [x] **T009 — Dominios finitos da spec**
  - Arquivos: `motor/spec.py`, `tests/test_hardening_h02.py`.
  - Rejeitar capacidade vazia, tier desconhecido, teto booleano, `NaN`, infinito ou <= 0;
    preservar specs validas v0.1.
  - Nao implementar roteamento runtime ou reserva de orcamento (H12a/H12b).
  - Orcamento: 35 linhas de producao + 40 de teste.
- [x] **T010 — Revalidar edicao externa integralmente**
  - Arquivos: `motor/grafo.py`, `tests/test_hardening_h02.py`.
  - Toda edicao devolvida pelo gate de plano passa novamente por `WorkflowSpec` antes de log,
    fan-out ou chamada externa; erro impede execucao.
  - Orcamento: 15 linhas de producao + 30 de teste; PR H02 alvo: 275 linhas.
- [x] **T011 — Gate H02 e gate completo da onda**
  - Rodar testes causais H02, H01, controles e suite original rastreada.
  - Security-DoD: Universal + Bot/LLM. Validacao ocorre na fronteira; sem banco/endpoint/comando
    novo. Ambiente/Autonomia permanece fora desta onda.
  - Medir adicoes de producao + testes por `git diff --numstat <base>`; acima de ~300 linhas
    bloqueia a aterrissagem e retorna para revisao humana.

## Comandos de gate

Executar da raiz do repositorio, em ambiente de desenvolvimento sem credenciais de producao:

```bash
python3 motor/tools/validar_manifest_reprodutores.py
pytest --strict-markers -rA motor/tests/test_manifest_reprodutores.py
pytest --strict-markers -rA motor/
ruff check motor/
mypy motor/
bandit -r motor/motor -q --severity-level high --confidence-level high
python3 -m compileall -q motor/motor motor/tests
python3 -m build motor/
python3 -m pip install --force-reinstall motor/dist/*.whl
gitleaks detect --source . --no-banner
```

## Onde isto pode dar errado

- O worktree contem reprodutores de ondas futuras; `pytest motor/` local seguira vermelho ate
  H13; o gate de checkout rastreado deve usar um worktree temporario, nunca interpretar o
  resultado local como CI.
- Discriminar config sem validar seu conteudo apenas deslocaria a falha para runtime.
- Tornar `plano` ou `cobertura` sempre manuais mudaria comportamento alem da decisao aprovada;
  somente os quatro gates sensiveis definidos sao manual-only nesta onda.
