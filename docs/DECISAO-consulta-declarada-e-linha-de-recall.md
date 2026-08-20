# DECISÃO — Consulta declarada e linha de recall

> **Canônico** sobre duas coisas que a analogia da fábrica expôs: (1) quando um agente pode
> falar com outro; (2) o que acontece com artefato já entregue que precisa de ajuste.
> Registrado em 2026-08-19, a partir de decisão do fundador.
>
> Complementa `DECISAO-ciclo-de-vida-workflow.md` (canônico sobre workflow). Se conflitar
> com ele no tema "workflow", aquele vence.

---

## 1. O princípio que decide as duas

> *"A linha de produção pode ser melhorada — mas só depois que analisaram, subiu para P&D e
> foi comprovada. Senão os carros da Toyota seriam diferentes a cada unidade."*

Uma run não pode entregar qualidade diferente porque dependeu de uma conversa. **Depender de
conversa entre agentes é depender de agente** — e é exatamente o que o Kortex existe para
não fazer. Melhoria é bem-vinda; **melhoria não-provada em produção não é.**

## 2. Consulta entre agentes: declarada antes, nunca espontânea

**Um agente só fala com outro se isso foi declarado antes de o workflow subir para
produção.** Se não foi declarado, não fala. Não há canal aberto por conveniência em tempo
de execução.

### Por que não pode ser fio livre

Uma aresta de consulta que sai de qualquer nó para qualquer nó transforma o DAG certificado
em grafo sem limite — o *"não é n8n de fios livres"* de
`DECISAO-ciclo-de-vida-workflow.md` §10. E cria o pior modo de falha possível: **contexto
indevido injetado num agente muda o que ele produz**, e a mesma spec passa a render
resultados diferentes por caminho não-determinístico. Isso destrói previsibilidade sem
disparar nenhum portão, porque nada tecnicamente falhou.

### A forma permitida

Consulta é **capacidade declarada do nó**, não fio de tempo de execução:

- a spec declara que o nó X pode consultar a casa/nó Y — e só ela;
- cada consulta real é **evento logado**, com proveniência;
- cada consulta consome **teto de orçamento declarado**;
- consulta não declarada **reprova fechado**, como qualquer capacidade não coberta.

Na tela pode parecer espontânea — uma linha que aparece e some. No registro é declarada,
contida e auditável. **Parecer vivo não é o mesmo que ser livre.**

### Handoff não é consulta

Não confundir, porque a topologia é outra:

| | o que é | avança o artefato? |
|---|---|---|
| **handoff** | artefato tipado com proveniência atravessando fronteira de casa | **sim** — é a linha de produção |
| **consulta** | pergunta com resposta voltando | **não** — o artefato fica onde estava |

Handoff já está decidido (`DECISAO-canvas-e-operacao.md` §4). Consulta é o que este
documento decide.

## 3. Evolução do workflow: já decidido, e reafirmado

O fundador reafirmou o que `DECISAO-ciclo-de-vida-workflow.md` §5 e §6 já decidiram, e a
implementação existe:

- versão nova carrega **evidência de como performou**; versão sem evidência é **candidata,
  não titular**;
- *"a palavra final é do dado, não do agente"* — run em sombra ou telemetria histórica;
- `motor/motor/curador.py` implementa: `rodar_sombra`, `certificar_sombra`, **teste de
  McNemar** sobre discordâncias, **piso de 30 casos held-out**, **α = 0.05**, selo HMAC na
  evidência, e promoção como **intenção sujeita a portão humano** — nunca mutação automática
  do catálogo.

O medo do fundador — *"melhorar aqui e piorar três outras"* — **é exatamente o que o McNemar
pareado mede**: ele conta os casos em que só o candidato acertou contra aqueles em que só o
titular acertou, olhando apenas onde os dois divergem. O instrumento certo já está lá.

## 4. Linha de recall (decisão nova)

**Artefato já entregue que precisa de ajuste não volta pela linha de produção inteira.** Ele
entra numa **linha de recall**: um workflow próprio, mais curto, que opera sobre um artefato
que já tem proveniência e evidência.

É o mesmo princípio que o motor já aplica **dentro do nó** — `motor/motor/grafo.py:1024`
entrega ao executor a tentativa anterior com *"o conteúdo já está bom — NÃO reescreva do
zero; corrija APENAS o que foi apontado"* — **elevado do nó para a linha**. Não se joga fora
trabalho bom, e não se refaz o que não foi apontado.

Regras:

- o recall **é um workflow**, com spec, portões e evidência próprios. Não é modo especial nem
  atalho;
- o artefato corrigido carrega **link para o original + o que mudou + por quê**. Sem isso a
  proveniência quebra e a evidência do original passa a mentir sobre o que está em campo;
- **o recall também é gated.** Correção pode regredir — é o mesmo risco do "melhora aqui,
  piora três outras", agora sobre um artefato específico;
- recall **não** promove workflow. Consertar uma unidade não é o mesmo que mudar a linha; se
  o defeito for da linha, isso vira candidatura de versão nova, pelo §3.

## 5. Onde isto pode dar errado

- **"Declarada antes" mata a espontaneidade que a analogia da fábrica sugere.** Na Toyota o
  gerente atravessa o corredor e pergunta. Aqui ele precisa que o corredor tenha sido
  desenhado. É troca consciente: previsibilidade acima de flexibilidade — mas é troca, e vai
  incomodar no dia em que faltar um canal óbvio.
- **Declarar consulta demais recria o fio livre pela porta dos fundos.** Se toda spec
  declarar "pode consultar todo mundo", a restrição vira formalidade. Vale medir densidade
  de consulta declarada e desconfiar de spec que abre canal que nunca usa.
- **O McNemar mede a dimensão que se mediu.** Ele pega "melhora aqui, piora ali" **dentro do
  conjunto held-out**; regressão numa dimensão que ninguém pôs no conjunto passa invisível.
  O piso de 30 casos limita ruído, não cegueira.
- **Linha de recall pode virar a linha principal.** Se corrigir for sempre mais barato que
  produzir certo, a pressão é entregar cru e consertar depois — e aí a linha de produção
  degrada enquanto a métrica de recall parece saudável. Vale vigiar a razão recall/produção.
- **Nada disto está construído.** Consulta declarada não existe no `WorkflowSpec`; linha de
  recall não existe. É decisão registrada, não funcionalidade. O `ESTADO.md` diz o que existe.
