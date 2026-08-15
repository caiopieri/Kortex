# COMO USAR o motor (uso real, hoje)

> Este guia é o mínimo pra rodar uma missão sem esperar o resto ser construído.
> Visão: `../docs/ARCHITECTURE.md`. Como funciona por dentro: `docs/EVOLUCAO.md`.
> Estado verificável e bloqueios: `specs/001-hardening-producao/verification.md`.

## Antes de rodar: renovar o câmbio

O snapshot de FX **vence em 24 horas** e o pricing em 7 dias. Vencidos, o motor **recusa arrancar** —
por desenho: câmbio velho é teto monetário velho. Se a última missão foi ontem, comece por aqui:

```bash
cd motor
python3 scripts/recapturar_fx.py            # busca a cotação real e grava nas configs custeadas
python3 scripts/recapturar_fx.py --conferir # só mostra, não grava
```

O script busca o número de verdade. **Adiantar a data à mão não funciona e não deve funcionar** —
manteria o valor velho, que é exatamente o que o erro de snapshot vencido recusa.

O **pricing não é automatizado de propósito**: renová-lo exige reconferir a tabela pública de cada
vendor contra `PRICING_SOURCE` e confirmar que a tabela code-owned continua sendo teto conservador.
Isso é julgamento, não coleta. Quando vencer, o erro diz o que fazer; a data e o registro da
reconferência ficam em `PRICING_CAPTURADO_EM`, em `motor/composicao_orcamento.py`.

## Rodar uma missão

```bash
export OMNIROUTE_API_KEY=...        # só a variável que a config exige; nunca chave no JSON
python3 -m motor "SEU OBJETIVO AQUI" --modelos exemplos/cfg-omniroute.json
```

**A configuração precisa ser custeada.** Configuração legada (sem bloco de orçamento) falha antes de
qualquer efeito com `orçamento indisponível: configuracao orcada ausente ou invalida`. Isso é o
fail-closed funcionando, não um defeito: nenhuma chamada de modelo acontece sem reserva prévia.

Opções que importam:

- **Sem `--auto`** (recomendado pra trabalho real): o motor **pausa** e mostra o **plano** antes de
  executar (`prosseguir` / `editar` / `abortar`) e pausa de novo no gate de **cobertura** se algo
  ficar inconsistente. É o anti-retrabalho — aprova-se o de cima antes de comprometer o de baixo.
- **`--auto`**: corre sozinho. O gate de cobertura **não** vira "prosseguir": vira `escalar`, que sobe
  para um modelo independente fazer o papel do fundador. Portão que reprova e deixa passar não é
  portão.
- **`--caixa <dir>`**: decisão do gate vai para uma nota na Caixa do Fundador e o estado do grafo é
  persistido — religar o processo retoma do gate pendente. Sem isso, o checkpointer é em memória.
- **`--rota construcao --registro exemplos/registro`**: construção em etapas com dependência
  (arquitetura → spec → testes).
- **`--gate cobertura=preencher --reconciliar 3`**: reconciliação automática, conserta a inconsistência
  na fonte.
- **`--spec exemplos/missao-pesquisa.json`**: roda uma `WorkflowSpec` pronta em vez de deixar o planner
  gerar.

## O que você recebe

- **Resposta final** (a síntese) impressa no fim, com o **carimbo de evidência**: que tipo de prova
  cobriu cada artefato (`execucao`, `estrutural` ou `opiniao`).
- **Artefatos** em `runs/<run_id>/artefatos/`, gravados **antes** da síntese. Se a síntese falhar, os
  artefatos já estão lá.
- **Log** de eventos em `log.jsonl` — é o que o painel e o curador leem.

## O que funciona hoje, e o que não

Funciona bem: **pesquisa, síntese, spec, análise, arquitetura, documentação** — o padrão
`fan_out_sintese` (default) e a rota `construcao`.

**Não funciona: entregar software com teste rodado.** A execução de comando é **default-deny** porque
nenhum backend de sandbox foi certificado (`specs/001-hardening-producao/sandbox-conformance.md`). O
motor escreve o código e **não consegue executá-lo**, então o carimbo sai `opiniao` ou `estrutural`,
nunca `execucao`. Isso é honesto e é suficiente para aprender onde o processo vaza — mas não é
"entrega verificada".

## Ver a fábrica rodando

```bash
python3 -m motor_painel.painel      # projeções do ledger em /dados/*
```

## Limitações atuais

- **Lento.** Uma missão leva minutos (latência por chamada de provedor). É normal.
- **Planner às vezes erra o JSON na 1ª tentativa** e recupera na 2ª — ele reinjeta o erro.
- **Independência executor↔verifier é declarada, não observada** quando todos os papéis passam pelo
  mesmo proxy. Ver dívida 8 em `docs/INVARIANTES.md`.

## Trocar de modelo/provedor

Trocar `--modelos <arquivo>`. As configurações custeadas vivem em `exemplos/`
(`cfg-omniroute.json`, `cfg-omniroute-gemini.json`, `cfg-omniroute-sem-codex.json`,
`cfg-orcada-multi.json`). O motor é provider-agnóstico: mudar de provedor é editar JSON, não código.

## Onde pedir mais

Falta o quê e o que vem depois: `../docs/ROADMAP.md`. Como o motor evolui: `docs/EVOLUCAO.md`.
