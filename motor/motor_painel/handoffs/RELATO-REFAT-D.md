# RELATO REFAT-D — Despacho real de missão pela UI (+ item 14 do REFAT-C)

Executor: Claude (Fable). Arquivos tocados: exatamente os 4 permitidos.

## Mudanças por arquivo

### `motor/motor_painel/painel.py`
- Imports novos: `os`, `subprocess`.
- Helpers de módulo: `_pid_vivo(pid)` (os.kill(pid, 0); `PermissionError` conta como vivo)
  e `_ler_pid_lock(lock)` (pid do lock ou None se ausente/ilegível).
- `Handler.despachos_dir` — atributo de classe (`BASE.parent/runs/despachos`), substituível em testes,
  como `log_path`/`db_path`.
- `Handler._origem_permitida()` — a validação de Origin do POST de gates foi extraída para este helper
  (código idêntico) e é reusada pelos dois POSTs. `Handler._erro(status, msg)` — resposta de erro curta.
- **`POST /dados/missoes`** (`_post_missao`): body ≤64KB (senão 400, com drenagem), JSON válido (senão 400),
  `spec` dict não-vazio (senão 400), Origin validada (403). Lock `despachos_dir/.lock`: pid vivo → 409
  "ja existe despacho em curso"; pid morto/ilegível → sobrescreve. Spec gravada em
  `spec-<YYYYmmdd-HHMMSS>.json`; `subprocess.Popen` SEM shell, argv fixo
  `[sys.executable, -m, motor, --spec, <arquivo>, --caixa, runs/caixa]` + `--auto`/`--escalar`
  (só se `opcoes.auto/escalar is True` — nenhum campo do body vira argumento), `cwd=BASE.parent`,
  stdout/stderr → `run-<ts>.log`, `start_new_session=True`. Pid gravado no lock.
  Resposta: `{"ok": true, "pid", "spec", "log"}`.
  Nota: o corpo é lido (limitado a 64KB) ANTES de responder 403/400 — responder antes de drenar
  causava RST no cliente (flake observado no teste de Origin; corrigido).
- **`GET /dados/missoes/ativa`**: lê o lock → `{"ativa": bool, "pid": <pid vivo ou null>}`.

### `motor/motor_painel/app/src/api.js`
- `getMissaoAtiva = () => get('/missoes/ativa')`.
- `postMissao(spec, opcoes)` — fetch próprio: em erro lança `HTTP <status>: <corpo cru do servidor>`
  (o `post()` genérico descartava a mensagem do corpo, e o handoff exige erro cru na UI).

### `motor/motor_painel/app/src/pages/NovaMissao.jsx`
- **Item 14 (REFAT-C)**: removidos o run id fake (`RUN-2026-07-02-***`) e a frase
  "O motor emitiu spec.recebida". `montarSpec()` monta a WorkflowSpec real do formulário
  (objetivo=descrição, rota/preset no contexto, papel por rota, teto→max_tentativas) — schema
  válido de `motor/spec.py` (missao/criterios_cobertura/subagentes/sintese). Painel
  "Despacho manual · alternativa" na coluna direita: JSON da spec + botão "copiar comando"
  (navigator.clipboard) com o mesmo par spec+opções do botão de despacho.
- **REFAT-D**: checkbox obrigatório "entendo que isto executa o motor e consome créditos"
  (botão desabilitado sem ele); `usePoll(getMissaoAtiva)` — se ativa, botão desabilitado com
  "já há uma missão em curso"; `handleConfirm` chama `postMissao(spec, {auto, escalar})`;
  tela de sucesso mostra pid/spec/log REAIS da resposta + "Abrir Grafo 2D"; erros 400/409/403/500
  exibidos crus.

### `motor/tests/test_painel_despacho.py` (novo, 11 testes)
Padrão de `test_painel.py` (módulo via importlib, `_TCPServerTeste` efêmero, `Handler.log_path/db_path/
despachos_dir` monkeypatched para tmp_path). `subprocess.Popen` SEMPRE monkeypatched (fixture
`popen_espiao`) — nenhum Popen real do motor roda. Os 5 casos do handoff:
1. POST válido → 200, Popen 1x com argv exato (com e sem `--auto/--escalar`), spec gravada, lock com pid.
2. Lock com pid vivo → 409, Popen NÃO chamado; lock com pid morto → sobrescreve e despacha.
3. JSON inválido / spec vazia (`{}`, não-dict, ausente) / body >64KB → 400, sem Popen.
4. Origin estranha → 403, sem Popen.
5. GET /dados/missoes/ativa: sem lock → false; lock vivo → true+pid; lock morto → false.

## Desvio declarado (comando CLI do item 14)
O handoff pedia o comando `python3 -m motor --spec '<json>' --caixa runs/caixa`, mas
`motor/__main__.py:204` lê `--spec` como **caminho de arquivo** (`Path(args[1]).read_text()`) —
JSON inline falharia com FileNotFoundError. O comando copiável gerado é
`python3 -m motor --spec <(printf '%s' '<json>') --caixa runs/caixa` (+`--auto`/`--escalar` conforme
opções): mesmo comando, com o JSON entregue via process substitution (funciona em zsh/bash).
Alternativa se preferir literal: mudar `__main__.py` para aceitar JSON inline (fora dos arquivos permitidos).

## DoD

### pytest — suíte inteira
```
$ python3 -m pytest motor/tests/ -q
63 failed, 444 passed, 1 warning in 67.08s
```
**Os 63 fails são TODOS pré-existentes e alheios a este handoff**: estão exclusivamente em
`test_auditoria_codex.py` / `test_auditoria_gpt5_{a,c,d,e,f,g}.py` (motor core: caixa/resume/interrupts),
arquivos não-rastreados de outra frente. Verificação falsificável: com `git stash` do meu `painel.py`,
os mesmos testes falham identicamente (26/26 nos dois arquivos amostrados). Nenhuma falha em
`test_painel*.py` ou em qualquer teste que toque os 4 arquivos deste handoff:
```
$ python3 -m pytest motor/tests/ -q | grep FAILED | grep -v test_auditoria
(vazio)
$ python3 -m pytest motor/tests/test_painel.py motor/tests/test_painel_despacho.py -q  (3x)
38 passed / 38 passed / 38 passed
```

### npm run build
```
$ cd motor/motor_painel/app && npm run build
dist/index.html                   0.73 kB │ gzip:   0.40 kB
dist/assets/index-BED-XArp.css   11.49 kB │ gzip:   2.57 kB
dist/assets/index-CkW7nbQR.js   531.52 kB │ gzip: 149.60 kB
✓ built in 203ms
```
(Aviso de chunk >500kB é pré-existente, não bloqueante.)

### shell=True
```
$ grep -n "shell=True" motor/motor_painel/painel.py
(0 ocorrências — exit 1)
```

## Onde isto pode dar errado
- O lock é por diretório, não atômico (TOCTOU entre check e write) — dois POSTs no mesmo
  milissegundo poderiam ambos passar. Painel local single-founder: risco aceito.
- Processo detached órfão se o painel morrer: mitigado pelo lock+`GET ativa`; matar processo
  não é escopo (conforme handoff).
- Teto de custo por run NÃO é enforced pelo motor (dívida em INVARIANTES.md) — a UI não promete teto.
- O comando manual com process substitution não funciona em `sh` puro (só zsh/bash).
