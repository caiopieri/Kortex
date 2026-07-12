# HANDOFF REFAT-D — Despacho real de missão pela UI (aprovado pelo Fundador)

> Executor: Codex. Contexto: `motor/docs/auditoria/AUDITORIA-PAINEL-TELAS.md`.
> Pré-requisito: itens 13–22 do HANDOFF-REFAT-C já aplicados (NovaMissao honesta).
> Arquivos permitidos: `motor/motor_painel/painel.py`, `motor/motor_painel/app/src/api.js`,
> `motor/motor_painel/app/src/pages/NovaMissao.jsx`, `motor/tests/test_painel_despacho.py` (novo).
> Nada além disso. Não mexer no motor/ core.

## Objetivo
Um clique em "Confirmar disparo" na Nova Missão passa a **executar o motor de verdade**
(`python3 -m motor --spec <arquivo> --caixa runs/caixa [--auto] [--escalar]`), com salvaguardas.
Isto gasta dinheiro real: as salvaguardas são parte do contrato, não opcionais.

## Backend — `painel.py`
1. Novo endpoint `POST /dados/missoes`:
   - Mesma validação de Origin do POST de gates (reusar o padrão existente).
   - Body: `{"spec": <objeto WorkflowSpec>, "opcoes": {"auto": bool, "escalar": bool}}`.
     Body >64KB ou JSON inválido → 400. `spec` deve ser dict não-vazio → 400.
   - **Lock de despacho único**: arquivo `BASE.parent/runs/despachos/.lock` contendo o pid.
     Se existir e o pid estiver vivo (`os.kill(pid, 0)`) → 409 "já existe despacho em curso".
     Pid morto → sobrescrever.
   - Gravar a spec em `BASE.parent/runs/despachos/spec-<YYYYmmdd-HHMMSS>.json`.
   - `subprocess.Popen([sys.executable, "-m", "motor", "--spec", str(spec_path),
     "--caixa", "runs/caixa"] + (["--auto"] se auto) + (["--escalar"] se escalar),
     cwd=BASE.parent, stdout/stderr → `runs/despachos/run-<ts>.log`,
     start_new_session=True)`. Sem shell. Nenhum campo do body vira argumento além
     da spec gravada em arquivo (imune a injeção de flag).
   - Escrever o pid no lock. Resposta 200: `{"ok": true, "pid": ..., "spec": "<path>", "log": "<path>"}`.
2. Novo endpoint `GET /dados/missoes/ativa`: lê o lock; responde
   `{"ativa": bool, "pid": ...}` (pid vivo) — para a UI saber se há run em curso.

## Frontend
3. `api.js`: `postMissao = (spec, opcoes) => post('/missoes', {spec, opcoes})` e
   `getMissaoAtiva = () => get('/missoes/ativa')`.
4. `NovaMissao.jsx`:
   - Montar a WorkflowSpec real do formulário (mesmo objeto que o painel "Despacho manual"
     do REFAT-C exibe — uma única fonte).
   - Checkbox obrigatório: "entendo que isto executa o motor e consome créditos" —
     botão "Confirmar disparo →" desabilitado sem ele.
   - Se `getMissaoAtiva().ativa` → botão desabilitado com "já há uma missão em curso".
   - Sucesso: tela mostra pid + caminho do log reais (da resposta) + link "Abrir Grafo 2D";
     REMOVER qualquer resquício de id fake. Erro (409/400/500): mostrar a mensagem crua.
   - Manter o painel "comando CLI copiável" como alternativa (vem do REFAT-C).

## Testes — `motor/tests/test_painel_despacho.py` (novo, obrigatório)
Seguir o padrão dos testes de endpoint existentes (`test_auditoria_*`/testes do painel:
Handler com log_path/db_path fake em tmp_path). Com `subprocess.Popen` espionado (monkeypatch):
- POST válido → 200, Popen chamado 1x com argv exato esperado, spec gravada, lock criado.
- Lock com pid vivo → 409 e Popen NÃO chamado.
- JSON inválido / spec vazia / body gigante → 400, sem Popen.
- Origin estranha → 403, sem Popen.
- GET /dados/missoes/ativa reflete lock vivo/morto.

## DoD (falsificável)
- `python3 -m pytest motor/tests/test_painel_despacho.py -q` verde e suíte inteira verde.
- `cd motor/motor_painel/app && npm run build` verde.
- `grep -n "shell=True" motor/motor_painel/painel.py` → 0.
- Relato em `motor/motor_painel/handoffs/RELATO-REFAT-D.md`.

## Onde isto pode dar errado
- O motor default usa `claude` CLI como executor — custo real por clique; por isso lock único +
  checkbox. Teto de custo por run ainda NÃO é enforced pelo motor (dívida em INVARIANTES.md) —
  não prometer teto na UI.
- Processo detached órfão: o lock com pid + `GET ativa` mitiga; matar processo não é escopo daqui.
