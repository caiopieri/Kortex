# DECISÃO — Manutenção e custódia

> Entrega não é o fim. O que acontece quando o software do cliente cai às 3 da manhã, e como isso
> torna a fábrica mais barata e mais segura a cada produto.
> Registrado em 2026-08-10. **Isto é direção, não estado.**

---

## 1. O problema

Hoje o ciclo termina na entrega. Semanas depois o cliente liga dizendo que caiu, e o contexto do que
foi construído já se perdeu — vive numa run encerrada. Manutenção recomeça do zero toda vez.

A tensão operacional é real e não se resolve escolhendo um lado: **cuidado extremo para não derrubar o
cliente, e pressa extrema quando ele já está no chão.**

---

## 2. A entidade que falta: dossiê

A unidade do Kortex hoje é a **run** — efêmera, com começo e fim (`runs/<run_id>/`). Manutenção exige
uma unidade com **vida**.

**Dossiê = contexto durável sobre um sujeito, versionado e com proveniência.** O sujeito pode ser um
produto sob custódia, um cliente, um repositório, um corpus de domínio, uma peça de hardware. Não é
conceito de manutenção: é o mecanismo geral de **dar contexto a agente sobre qualquer coisa**.

Para um produto sob custódia, o dossiê carrega:

- spec e arquitetura que o geraram, e a versão do template usado
- topologia de deploy: onde roda, o que expõe, o que é reversível
- **inventário de dependências com versão** — que é a mesma chave de invalidação do cache de pesquisa
  (`DECISAO-conhecimento-e-julgamento.md` §2)
- histórico de incidentes: o que caiu, quando, o que mitigou, o que corrigiu
- hardening aplicado, cada regra com sua origem
- superfície de ataque conhecida e o que já foi testado contra ela

### A trava que impede o dossiê de virar folclore

Um dossiê é exatamente o lugar onde afirmação não verificada acumularia autoridade por repetição.
Portanto:

> **Toda entrada de dossiê carrega o mesmo carimbo de evidência do resto do sistema.**

Incidente que aconteceu é `execucao`. Nota de arquitetura que alguém escreveu é `opiniao`. Um dossiê
não é wiki; é **montagem de projeções com veredito**, e o que não tem origem não entra.

### Isto é o "Kortex Data" que sobrevive à crítica

O dossiê é conhecimento **produzido pela fábrica**, com escopo de sujeito e com veredito — não
ingestão do mundo por precaução. É a forma que passou no crivo de
`DECISAO-conhecimento-e-julgamento.md`: o ativo composto é o que a fábrica gera, não o que ela estoca.

---

## 3. Manutenção inverte o gatilho

| | Construção | Manutenção |
|---|---|---|
| Disparo | objetivo humano | **evento do mundo**: caiu, CVE publicado, ataque passou, certificado vencendo, dependência deprecada |
| Contexto | briefing | **dossiê** |
| Sucesso | artefato entregue | serviço de pé **e** regra nova no catálogo |

O monitor que observa o produto é processo longevo. **Não é o motor** (músculo, não autoridade) e não
é uma run: mora na camada das casas. Ele detecta e **compõe a spec** — que já é decisão tomada,
"autoria de workflow é uma run do motor" (`EVOLUCAO.md` V7).

---

## 4. Resposta a incidente: mitigar → corrigir → causa raiz

Três etapas com donos, prazos e níveis de autonomia **diferentes**. Confundi-las é o que faz sistema de
manutenção quebrar cliente.

### 4.1 Mitigar — minutos, automático

Restaurar o serviço por qualquer meio **reversível**. Não conserta nada; para a hemorragia.

Rollback para o último bom conhecido · failover · desligar feature flag · escalar · circuit breaker ·
página de manutenção honesta.

Toda ação aqui é reversível **por construção** — é exatamente por isso que pode ser automática. E a
página de degradação declara o estado real: **degradação honesta, nunca saúde simulada.** É o princípio
de honestidade operacional do painel aplicado ao produto do cliente.

### 4.2 Corrigir — o conserto de verdade, com portão

Pode ser duas linhas; pode ser refatoração. **Se a correção for demorar, a mitigação tem que segurar** —
por isso ela é etapa própria, com seu próprio objetivo de tempo, e não um preâmbulo da correção.

Correção é código novo em produção. **Sempre gated.**

### 4.3 Causa raiz — depois, e é onde a fábrica aprende

Vira regra no catálogo, validador determinístico ou restrição de template. Sem esta etapa, manutenção
é só apagar incêndio e o custo por produto nunca cai.

### 4.4 A tabela de autonomia

**Automatize o reversível, portone o irreversível.**

| Ação | Reversível | Autonomia |
|---|---|---|
| Reiniciar, escalar, failover, rollback para o último bom | sim — volta a estado já verificado | **automática** |
| Desligar feature flag, página de manutenção | sim | automática |
| Rotacionar credencial, bloquear IP | sim | automática, com registro |
| Aplicar patch de código em produção | não de fato | **gate humano** |
| Mudar schema, migrar dado | não | **gate humano, sempre** |

**Classificação de severidade é decisão de autoridade**, não de motor: depende de impacto no negócio.
Mora na casa e no portão.

---

## 5. O flywheel de segurança

O grader mais barato do sistema inteiro: **o exploit entrou ou não entrou.** Binário, reprodutível,
adversarial, automatizável. Não precisa de juiz LLM, rubrica, gosto nem significância — não existe
"provavelmente não houve SQL injection".

Consequência: **segurança é o primeiro domínio do catálogo certificado, não o último.** Provar "este
padrão resiste a esta classe de ataque" é barato e rende sempre; provar "este modelo é melhor no papel
X" é caro e rende pouco.

### Achado e regra são coisas diferentes

- **Achado** (este ataque entrou neste produto) — evidência `execucao` no sentido mais forte. Promove
  com cerimônia mínima: é fato observado.
- **Regra derivada** (portanto todo software deve fazer assim) — é **generalização**, e generalização a
  partir de um caso é indução em amostra de um. Continua exigindo julgamento, e **tem prazo**: a
  revogação de `DECISAO-conhecimento-e-julgamento.md` §4 se aplica inteira. Defesa de 2026 pode ser
  peso morto — ou dano — em 2028.

---

## 6. Monocultura: o risco que contradiz a tese

Se dez produtos saem do **mesmo padrão consolidado**, eles compartilham os mesmos pontos cegos. Um
ataque que falha nos dez não prova que o padrão é bom: pode significar que a classe que derruba todos
nunca foi testada.

**Quanto mais o padrão consolida — que é o objetivo — mais correlacionadas ficam as vulnerabilidades da
carteira.** Monocultura é o que transforma um exploit em catástrofe: uma brecha, dez clientes.

Duas defesas, nenhuma opcional:

1. O red team **gera ataque novo**, não só reproduz o corpus. Corpus fixo mede regressão, não segurança.
2. **Auditoria externa periódica** como âncora de ouro — o mesmo conceito já usado contra deriva de
   modelo. Alguém de fora do padrão precisa olhar, senão a frota só confirma o que já acredita.

---

## 7. Onde isto vive

"Como uma empresa de software faz" é **método**, e método é da casa: runbook, níveis de severidade,
plantão, postmortem, janela de mudança. Vai para o **`dev-harness/`** (a softwarehouse), como templates
de workflow versionados — não para dentro do motor. O motor não sabe o que é severidade; a casa sabe.

O monitor, o dossiê e a classificação de severidade são todos da camada das casas. O motor continua
rodando **uma** missão com maestria.

---

## 8. Riscos, resolvidos

- **Ataque simulado exige autorização.** Ambiente espelhado é o **default**; produção é exceção com
  autorização escrita por alvo, escopo e janela. Sem isso não é serviço. E ataque contra produção pode
  causar exatamente a queda que deveria prevenir.
- **O dossiê é um mapa da superfície de ataque da carteira inteira.** Vazamento dele é pior que
  vazamento de código. Portanto: **segmentado por cliente, cifrado em repouso, acesso por escopo,
  jamais agregado num índice único consultável.** Isso muda os requisitos de segurança do próprio
  Kortex — que hoje não foram desenhados para guardar isso.
- **Promoção rápida de achado** vale para o achado, não para a regra derivada (§5).
- **Manutenção é modelo de negócio diferente de entrega:** SLA, plantão, responsabilidade contratual
  por indisponibilidade. **Não se vende manutenção antes de o sandbox estar certificado** — seria
  prometer o que o sistema comprovadamente não faz.
- **Nada disto precede a fábrica rodar.** A sequência abaixo respeita isso.

---

## 9. Sequência

1. **Rodar missões** — o resto é hipótese até existir uma run que entregou algo.
2. **Dossiê como montagem de projeções** sobre o ledger, para um produto real. Começa read-only.
3. **Método de manutenção no `dev-harness/`**: severidade, runbook, escada mitigar→corrigir→causa raiz,
   como templates versionados.
4. **Monitor na camada das casas**, disparando missão a partir de evento — primeiro só notificando.
5. **Mitigação automática** restrita à tabela de reversíveis; correção sempre gated.
6. **Red team recorrente** em ambiente espelhado, alimentando achados ao catálogo.

## 10. Onde isto pode dar errado

- **A escada mitigar→corrigir pode induzir a parar na mitigação.** Serviço de pé com rollback aplicado
  parece resolvido, e a correção some do radar até o próximo incidente. A mitigação precisa **abrir**
  um item de correção com prazo, não fechar o incidente.
- **Rollback nem sempre é reversível de verdade.** Se houve migração de schema ou escrita de dado entre
  o deploy e a falha, voltar a versão pode corromper mais do que a falha original. A tabela do §4.4
  assume rollback limpo, e essa hipótese precisa ser verificada **por produto**, no dossiê — não
  assumida.
- **O dossiê pode virar o gargalo que ele deveria eliminar.** Contexto grande demais custa token em
  toda missão e degrada a atenção do modelo. Vai precisar de recuperação seletiva — e aí volta a
  pergunta de retrieval que decidimos adiar até medir.
- **"Segurança é o primeiro domínio do catálogo" pressupõe red team automatizado competente.** Um red
  team fraco gera falsa confiança medida com precisão: dez produtos "aprovados" contra ataques que não
  representam a ameaça real. O grader é barato; **construir o atacante não é.**
- **Custódia cria dependência assimétrica.** Cliente cujo software só o Kortex sabe manter fica preso —
  e você fica preso a ele. É bom comercialmente e é risco de reputação e de operação quando algo dá
  errado e não há segunda opinião possível.
