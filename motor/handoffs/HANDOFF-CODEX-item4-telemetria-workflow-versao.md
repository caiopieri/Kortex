# HANDOFF CODEX — telemetria por template@versão (eixo de workflow no curador)

> Red-team item 4 (verificado): `curador.py` agrega por papel×tier×modelo, por_modelo,
> por_slot_modelo e por_run — **não há eixo template/versão**. A telemetria carrega `missao`, não
> `template@versao`. Consequência dupla: (a) "versão carrega evidência" (DECISÃO §5) não tem de
> onde derivar; (b) **erro de atribuição** — um template mal desenhado gera reprovações que o
> curador debita do MODELO → propõe modelo mais caro → a causa real (o template) fica invisível.

## Por quê (amarra à arquitetura)
O ciclo de vida do workflow (DECISÃO) exige que cada **versão de template** acumule evidência
(certificação). E o curador precisa distinguir "modelo fraco" de "template fraco" — senão a
seleção do orquestrador (item 7) erra em silêncio e a conta vai sempre pros modelos.

## O que fazer (2 PRs em ordem, 2 commits)
**PR1 — a spec carrega template/versão e os eventos emitem:**
- `motor/spec.py`: em `Missao` (ou top-level da `WorkflowSpec`), campos **opcionais**
  `template: Optional[str]` e `versao_template: Optional[str]` (não confundir com `versao` do
  schema). Sem eles = comportamento de hoje.
- `motor/grafo.py`: incluir `template`/`versao_template` (quando presentes) nos eventos de
  execução (`executor.chamado`) — junto de papel/tier/modelo. Declarar os campos no
  `eventos_schema.py` (sem tipo novo; campos opcionais no evento existente).

**PR2 — o curador agrega o eixo:**
- `motor/curador.py`: nova agregação `por_template_versao` (chave `template@versao`) com as mesmas
  métricas de `_finalizar_metricas` (aprovação-1ª, erros, latência…). Ausente/None → bucket
  `"desconhecido"`. Expor na saída JSON e numa seção do Markdown.

## Restrições
- Aditivo/inerte: spec sem template/versão → tudo como hoje (legado vira "desconhecido").
- stdlib; sem chamar modelo. Não alterar precedência de roteamento nem o propositor.
- Higiene de git: add específicos; nunca `git add -A`.

## DoD (falsificável)
1. Spec com `template`/`versao_template` valida; sem eles, valida igual (regressão).
2. `executor.chamado` carrega os campos quando presentes; guarda anti-drift passa.
3. `curador` mostra `por_template_versao`; 2 versões do mesmo template aparecem como buckets
   distintos; runs sem template caem em "desconhecido".
4. Suíte verde; mypy ok.

## O que isto prova e o que NÃO prova
Dá o **eixo** pra medir versão e separar template de modelo. NÃO decide sozinho "v3 > v2" — isso
é o guardrail de sombra (item 6, desenho estatístico pendente) usando este eixo.
