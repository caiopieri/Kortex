# HANDOFF CODEX — Fase C / corte 2: loop de reconciliação com TETO + auto-mode

## Por quê (dado do run real 2026-06-25, corte 1)
Com `--rota construcao --modelos modelos-free-escalada.json --escalar --gate cobertura=preencher`:
o corte 1 disparou a reconciliação na fonte, re-rodou os nós em ordem de dependência e RESOLVEU as 3
lacunas grossas da rodada 1 (linha vazia, trim em --headers, --output ambíguo). MAS na 2ª avaliação
surgiram lacunas FINAS novas (plano de testes com fixture inconsistente T-13/T-14; falta erro de uso
da CLI com exit 1). O corte 1 faz UMA rodada e segue (`prosseguir`) — então o resíduo fino fica.
Conclusão empírica: uma rodada resolve o grosso; falta o LOOP com teto pra convergir o fino (uma 2ª
rodada, provavelmente nomeando só o plano de testes, fecharia barato).

## Objetivo (corte 2)
Transformar a rodada única de `preencher` num LOOP bounded por um teto `max_rodadas_reconciliacao`, e
integrar com o auto-mode (sob override/auto "preencher", reconcilia enquanto houver orçamento, depois
"prosseguir"). DEFAULT preserva o corte 1 (1 rodada) → todos os testes atuais continuam verdes.

## Mudanças (só motor/grafo.py + motor/__main__.py)

### M1 — novo parâmetro com DEFAULT que não muda nada
`construir_grafo(...)`: adicionar após `escalar_em_retry: bool = False`:
```python
                    max_rodadas_reconciliacao: int = 1):
```
Default 1 = comportamento do corte 1 (uma rodada de preencher). Documentar no docstring.

### M2 — `avaliar` (~611) vira LOOP bounded
Substituir o corpo por um laço que reavalia após cada rodada de `preencher_lacunas`, até aprovar ou
esgotar o teto. Esboço (manter nomes/funções existentes: `avaliar_cobertura`, `decidir_cobertura`,
`preencher_lacunas`, `finalizar_cobertura`, `workspace_de`, `mesclar_resultados`):
```python
def avaliar(state: EstadoMotor) -> dict:
    spec, resultados = state["spec"], state["resultados"]
    log.evento("paralelo.concluido", commitados=len(resultados))
    veredito = avaliar_cobertura(spec, resultados)
    acumulados: list[dict[str, Any]] = []
    rodada = 0
    while not veredito.get("aprovado"):
        log.evento("portao.reprovado", portao="cobertura", lacunas=veredito.get("lacunas", []))
        permitir = rodada < max_rodadas_reconciliacao
        decisao = decidir_cobertura(veredito, permitir_preencher=permitir)
        if not (permitir and str(decisao).strip().lower().startswith("preench")):
            base = {"resultados": acumulados} if acumulados else {}
            return {**base, "avaliacao": finalizar_cobertura(veredito, decisao)}
        resultados, novos = preencher_lacunas(spec, resultados, workspace_de(state), veredito)
        if not novos:  # nada a refazer → não adianta repetir
            decisao = decidir_cobertura(veredito, permitir_preencher=False)
            base = {"resultados": acumulados} if acumulados else {}
            return {**base, "avaliacao": finalizar_cobertura(veredito, decisao)}
        acumulados = mesclar_resultados(acumulados, novos)
        rodada += 1
        veredito = avaliar_cobertura(spec, resultados)
    if rodada >= max_rodadas_reconciliacao and not veredito.get("aprovado"):
        log.evento("reconciliacao.esgotada", rodadas=rodada)  # (só por clareza; o laço já saiu se aprovou)
    log.evento("portao.aprovado", portao="cobertura")
    return ({"resultados": acumulados, "avaliacao": veredito} if acumulados else {"avaliacao": veredito})
```
IMPORTANTE: emitir `reconciliacao.esgotada` (rodadas=teto) quando o teto for atingido E ainda reprovado
ANTES de cair no `finalizar_cobertura` via `prosseguir` (ajuste a posição do evento para o ponto certo:
quando `permitir` for False por causa do teto e o veredito seguir reprovado). Não emitir quando aprovou.

### M3 — CLI `--reconciliar N` (motor/__main__.py)
Parsear como as outras flags (ex.: perto de `--escalar`), default 1:
```python
max_rodadas = 1
if "--reconciliar" in args:
    i = args.index("--reconciliar")
    max_rodadas = int(args[i + 1]); args = args[:i] + args[i + 2:]
```
E passar `max_rodadas_reconciliacao=max_rodadas` nas DUAS chamadas de `construir_grafo` (caminho com
`--caixa`/SqliteSaver e o caminho default/InMemorySaver), ao lado de `escalar_em_retry=...`.

## Como os gatilhos se comportam (contrato a preservar)
- `--auto` SOZINHO (sem override): `decisao_auto("cobertura")` segue default "prosseguir" → o laço entra,
  `decisao` != preencher → sai por `finalizar_cobertura(prosseguir)`. SEM reconciliação. (Mantém
  `test_gate_auto_mode_nao_interrompe` verde.)
- `--gate cobertura=preencher` (com ou sem `--auto`): reconcilia até `max_rodadas`, depois "prosseguir".
- manual (sem auto, sem override): interrompe; humano escolhe preencher → reconcilia até `max_rodadas`.
- DEFAULT `max_rodadas=1` → uma rodada (idêntico ao corte 1).

## Restrições (inerte / não-quebra)
- DEFAULT 1 obrigatório (preserva corte 1). NÃO mudar o default de decisão do auto-mode.
- Não tocar PROMPT_PLANNER (snapshot), modelos.py, registro.py, nem a lógica de `preencher_lacunas`
  (closure/deps já validada no corte 1) além do necessário.

## DoD (todos precisam passar)
1. **GUARD corte 1**: suíte atual continua verde com default 1 — em especial
   `test_gate_cobertura_preencher_reexecuta_reprovado_uma_vez` (1 rodada),
   `test_gate_cobertura_preencher_refaz_fonte_e_dependentes_em_ordem` (aprova após 1 rodada),
   `test_gate_auto_mode_nao_interrompe` (auto sozinho → prosseguir, sem reconciliação).
2. **NOVO — loop converge**: `max_rodadas_reconciliacao=2`, override cobertura=preencher; evaluator
   reprova nas avaliações 1 e 2 e APROVA na 3ª → exatamente 2 rodadas de preencher (2 blocos
   `reconciliacao.iniciada`/`lacuna.preenchida`), resultado final aprovado.
3. **NOVO — teto respeitado (sem loop infinito)**: `max_rodadas=2`, evaluator SEMPRE reprova → exatamente
   2 rodadas, depois `prosseguir` (`finalizar_cobertura` com `prosseguir_parcial`), evento
   `reconciliacao.esgotada` (rodadas=2), missão completa.
4. **NOVO — CLI**: `--reconciliar 3` chega como `max_rodadas_reconciliacao=3` em `construir_grafo`
   (testar via o mesmo padrão de monkeypatch de construir_grafo já usado em test_rotas.py).
5. Suíte completa verde (`python3 -m pytest -q`), 221+ passed. `python3 -m compileall -q motor tests` ok.

## Validação do Caio (depois do commit) — NÃO é código
`python3 -m motor "<missão CSV→JSON>" --registro exemplos/registro --rota construcao --modelos exemplos/modelos-free-escalada.json --escalar --gate cobertura=preencher --reconciliar 3`
Métrica: o `cobertura` passa a APROVAR dentro do teto (as lacunas finas — fixture T-13/T-14, erro de uso
da CLI — somem após a 2ª/3ª rodada)? Ou bate o teto e segue parcial (então o teto/uso precisa de ajuste)?
Trazer log.jsonl. NOTA conhecida: planner no Codex é lento (~80-160s) e às vezes falha a 1ª tentativa de
JSON (recupera) — eixo separado, não bloqueia.
```
