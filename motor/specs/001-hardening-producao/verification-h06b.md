# Verificacao - H06b eventos publicos do curador

Status: **CONCLUIDA NO ESCOPO H06b**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Contrato Entregue

- O schema v2 publica exatamente os quatro eventos emitidos pelo fluxo do curador:
  `curador.sombra`, `curador.certificou`, `curador.rejeitou` e
  `curador.promocao_pendente` (`motor/motor/eventos_schema.py:26`).
- Cada evento declara categoria e payload completo. `evento`, `t` e `seq` continuam
  reservados ao envelope do writer.
- Os campos do curador usam os tipos estritos ja aplicados por H06a: nomes/motivo sao
  strings e contadores sao inteiros reais, sem aceitar `bool` como `int`
  (`motor/motor/eventos_schema.py:292`).
- `motor/motor/curador.py` nao foi alterado. Seus quatro pontos de emissao existentes
  (`motor/motor/curador.py:264`, `:324` e `:371`) ja produziam o contrato publicado.

H06b apenas publica e prova o contrato dos eventos. Nao muda a decisao de certificacao,
nao fortalece evidencia e nao aplica promocao; esses limites pertencem a H08-H09.

## Evidencia Causal

| Garantia | Evidencia |
|---|---|
| Dois reprodutores congelados H06b | `motor/tests/test_hardening_h06b.py:28` |
| Conjunto publico exato e envelope reservado | `motor/tests/test_hardening_h06b.py:66` |
| Quatro caminhos reais produzem eventos validos | `motor/tests/test_hardening_h06b.py:76` |
| Campo ausente, extra ou com tipo errado falha fechado | `motor/tests/test_hardening_h06b.py:86` |

O subagent fresco leu integralmente apenas `eventos_schema.py` e `curador.py`, confirmou o
mapa Graphify e deixou o diff no workspace antes de atingir seu limite de uso. A revisao,
execucao integral dos gates e aceitacao foram refeitas no processo principal.

## Gate

| Checagem | Resultado |
|---|---|
| H06b + eventos + curador | `44 passed` |
| Suite rastreada, sem packs futuros | `453 passed` |
| Pack completo como overlay | `68 passed, 43 failed` |
| Ruff | limpo |
| mypy | limpo, 70 arquivos |
| Bandit high/high | limpo |
| compileall | limpo |
| Gitleaks dir (`motor/`) | limpo, 16.33 MB |
| build sdist/wheel | passou |
| install e smoke do wheel isolado | passou; schema v2 e quatro tipos `curador.*` |

Os dois reprodutores H06b deixaram de falhar. Nenhum caso H08-H09 foi absorvido: as falhas
anti-Goodhart continuam visiveis no overlay. Esta verificacao nao declara o motor pronto para
producao nem o Gate CI global aprovado.

## Security DoD

- Input externo: payload ausente, extra ou tipado incorretamente e rejeitado pelo schema.
- Envelope: payload do curador nao pode fornecer `evento`, `t` ou `seq`.
- Promocao: `curador.promocao_pendente` continua sendo intencao auditavel, nao aplicacao.
- Segredos/SAST: Gitleaks e Bandit high/high limpos.
- Concorrencia/persistencia: fora de H06b; H07 continua responsavel por append, lock, seq e
  recovery do JSONL.

O build foi feito do checkout sujo de auditoria. Um artefato de release deve ser reconstruido
de checkout limpo apos H13.

## Onde isto pode dar errado

- Schema valido prova formato, nao veracidade. Um evento pode ser bem tipado e carregar
  evidencia insuficiente; H08-H09 devem validar proveniencia, held-out e dominios numericos.
- `certificar_sombra` e `preparar_promocao_gated` ainda aceitam dicionarios externos pouco
  estruturados. Com writer estrito, payload invalido falha antes do append, mas a fronteira
  de negocio ainda precisa falhar antes de produzir uma certificacao.
- H06b nao torna JSONL atomico ou recuperavel. Reabertura, concorrencia e tail parcial
  permanecem defeitos conhecidos de H07.
