# HANDOFF CODEX — Curador, fatia 1: OBSERVADOR (telemetria → perfil de aptidão, read-only)

## Por quê (contexto travado pela arquiteta)
O Curador é o norte "auto-melhora": observar telemetria → testar em sombra → propor melhorias via
certificação+auditoria, alimentando perfis de aptidão por TAGS (decisão travada: aptidão entra por
tags, NÃO inverte a precedência tier>capacidade). A gente JÁ faz a parte de observação NA MÃO (ler os
logs JSONL e concluir "llama tem teto em tarefa difícil", "escalada converte", "planner lento/flaky no
Codex", "Kimi pedante + 429 no free"). A fatia 1 AUTOMATIZA só essa observação, de forma
DETERMINÍSTICA e READ-ONLY. Sem chamada de modelo, sem mutar roteamento/catálogo, sem custo. As fatias
seguintes (teste em sombra, propor mudanças) vêm depois e dependem deste perfil como fundação.

## Objetivo (fatia 1)
Um módulo novo `motor/curador.py` que LÊ um ou mais logs de eventos JSONL (os que o motor já produz) e
EMITE um perfil estruturado de aptidão/latência/resiliência por (papel, tier) e por run. Puro stdlib
(json, statistics, pathlib, collections). CLI: `python3 -m motor.curador <log-ou-dir> [<mais>...]`.

## O que os logs já contêm (não inventar campos — usar estes eventos)
- `executor.chamado` {executor, papel, tier, tentativa}; `executor.respondeu` {executor, tentativa};
  `executor.erro` {executor, motivo, tentativa}; `modelo.falha` {papel, tentativa, motivo}
- `modelo.roteado_tier` {papel, tier}; `modelo.pin`; `modelo.fallback` {papel, para};
  `modelo.reroteado_esgotado` {papel, de, para}; `provedor.auto_esgotado` {provedor, papel, motivo}
- `portao.aprovado` {portao:"verifier:<id>"|"cobertura", ciclo}; `portao.reprovado` {portao, ciclo, motivo|lacunas}
- `executor.escalado` {executor, de, para, tentativa}
- `spec.criada`/`spec.recebida`; `reconciliacao.iniciada`/`concluida` {nos}; `lacuna.preenchida` {subagente}
- `gate.auto` {portao, decisao}; `tarefa.concluida`
- cada evento tem `t` (segundos desde o início do run) → latência = delta entre `executor.chamado` e o
  `executor.respondeu`/`executor.erro` correspondente do mesmo executor.

## Métricas a agregar (determinístico)
Por **(papel, tier)** ao longo de todos os logs dados:
- nº de chamadas, nº de respostas, nº de erros (`executor.erro`/`modelo.falha`) e taxa de erro;
- aprovação na 1ª tentativa do verifier (portao.aprovado verifier:* com ciclo==1) sobre o total julgado;
- nº de reprovações (portao.reprovado verifier:*) + AMOSTRA de motivos (até ~3);
- escaladas: nº de `executor.escalado` partindo deste tier, e taxa de CONVERGÊNCIA pós-escalada
  (o executor foi aprovado depois do `executor.escalado`?);
- latência por chamada: mediana e p90 (via deltas chamado→respondeu).
Por **run** (cada arquivo de log é um run; detectar reinício por `t` decrescente se houver concatenação):
- planner: nº de tentativas até `spec.criada` (sinal de fragilidade de JSON) e latência;
- cobertura: foi reprovado→APROVADO via reconciliação? quantas rodadas (`reconciliacao.iniciada`)?
  tamanho do closure por rodada (len(nos));
- resiliência observada: ocorrências de `provedor.auto_esgotado`/`modelo.reroteado_esgotado`/`modelo.fallback`
  por provedor/papel; motivos de 429 etc. (substring "429" no motivo).

## Saída
- Um dict estruturado (JSON) — perfil legível por máquina (fundação das próximas fatias).
- Um resumo Markdown legível — o tipo de conclusão que hoje é escrita na mão ("tier simples (executor)
  aprova X% de 1ª, escala Y%, converge Z% após escalar; planner: N tentativas/run; cobertura converge
  via reconciliação em R rodadas").
- Por default imprime o Markdown no stdout; com `--json <caminho>` grava o dict. (Não criar pasta nova
  obrigatória; se for gravar arquivo, usar o caminho dado.)

## Restrições (inerte / seguro)
- READ-ONLY: NÃO chama modelo, NÃO importa nem altera grafo.py/modelos.py/roteamento/catálogo, NÃO
  escreve em logs existentes. Só lê JSONL e emite perfil.
- Puro stdlib. Robusto a linha malformada (ignora linha que não parseia, não quebra).
- Módulo e testes NOVOS; não tocar em nada existente.

## DoD (todos precisam passar)
1. **Fixtures sintéticos**: testes com JSONL montado à mão exercitando cada métrica — (a) um executor que
   aprova de 1ª; (b) um que reprova→escala→aprova (convergência pós-escalada=verdadeira); (c) um run com
   `provedor.auto_esgotado`+`modelo.reroteado_esgotado` (resiliência); (d) cobertura reprovado→reconciliação
   →aprovado (R rodadas, closure por rodada); (e) planner com 2 tentativas até spec.criada. Asserções sobre
   os números do perfil.
2. **Robustez**: log com uma linha corrompida no meio não quebra (é ignorada).
3. **CLI**: `python3 -m motor.curador <arquivo>` imprime o resumo; `--json <caminho>` grava o dict.
4. Suíte completa verde (`python3 -m pytest -q`), 224+ passed. `compileall` ok.

## Validação do Caio (depois do commit) — NÃO é código
`python3 -m motor.curador logs/` (e/ou nos logs reais que ele tem) → conferir se o perfil REPRODUZ as
conclusões que a gente tirou na mão: executor barato (llama/tier simples) com baixa aprovação de 1ª em
tarefa difícil e alta escalada que converge; planner lento/flaky; verifier Codex sem 429 (e, nos logs
free, Kimi com 429/esgotado); cobertura convergindo via reconciliação. Se bate → o Observador é uma lente
fiel e vira a fundação das próximas fatias do Curador (teste em sombra, então propor via certificação).

## FATIAS SEGUINTES (NÃO agora — só pra orientar o desenho)
2: o Curador propõe ajustes de roteamento/tags de aptidão a partir do perfil (ainda sem aplicar — gera
proposta + justificativa). 3: teste em SOMBRA (rodar candidato em paralelo sem afetar produção) +
certificação/auditoria antes de qualquer mudança no catálogo. A decisão travada vale: aptidão entra por
TAGS granulares (codigo-simples/codigo-complexo/...), sem inverter a precedência tier>capacidade.
