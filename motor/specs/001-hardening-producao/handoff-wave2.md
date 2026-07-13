# Handoff - onda 2 do hardening

Status: **SUPERADO PELO SNAPSHOT H13 DE 2026-07-12**. Para o estado atual, consulte
`verification-h13.md`, `verification-h12a.md` e `plan-h12b.md`. O restante deste arquivo
preserva o handoff historico da onda 2.

Base: H00-H04, H06a-H06b, H10a-H10b e H11a-H11d concluidos no gate
consolidado (`490 passed`). Bloqueio global: overlay completo ainda tem `38 failed`.

## Fatias Frescas

1. H05a - contrato de sandbox externo.
   - Iniciar em contexto proprio, sem reabrir a policy H04.
   - Tratar ambiente, filesystem e rede como isolamento real; `cwd` nao satisfaz o contrato.
2. H07 - append, lock, seq e recovery do JSONL.
   - Iniciar depois de uma das duas frentes acima fechar.
   - Ler integralmente apenas `motor/motor/eventos.py` e `motor/motor/eventos_schema.py`.
3. H08/H09 - curador anti-Goodhart, evidencia e promocao vinculada.
   - Iniciar somente depois de H07; ler integralmente apenas `motor/motor/curador.py`.

No maximo duas frentes simultaneas. Cada fatia deve ocorrer em conversa/contexto novo e usar
`tests.audit_corpus.casos(owner)`; nenhum pack inteiro deve ser carregado como contexto.

## Limites

- H04 esta fechado em identidade/default-deny, mas nao e sandbox; confinamento, ambiente
  limpo, limites e kill de descendentes pertencem a H05a/H05b. A allowlist operacional
  agora exige caminho absoluto canonico, nao basename.
- H06b esta fechado nos quatro contratos/eventos `curador.*`; evidencia/certificacao
  anti-Goodhart continuam H08-H09.
- H10b deve pousar como H10b1/H10b2; H11 deve pousar como H11a-H11d. O working tree
  consolidado nao e um PR revisavel.
- H11 entrega at-least-once com dedupe por `decision_id`, reconcilia depois de restart e
  serializa interrupts do mesmo job. Efeito externo continua exigindo idempotencia propria.
- Reexecutar graphify no inicio da nova conversa; o mapa localiza, o codigo integral decide.

## Onde isto pode dar errado

- H05a pode mascarar TOCTOU se adicionar apenas mais checks de path; o backend precisa
  fornecer confinamento real e identidade imutavel na execucao.
- Adicionar eventos do curador sem tipos completos reabre E1 sob outro namespace.
- Um heartbeat futuro pode reduzir redelivery em callbacks longos, mas nunca deve ser vendido
  como exactly-once entre o checkpoint e efeitos externos.
