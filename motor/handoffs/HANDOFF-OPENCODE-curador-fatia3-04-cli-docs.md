# HANDOFF OPENCODE — Curador Fatia 3.4: CLI/Docs de Sombra e Certificacao

## Objetivo
Expor caminho operacional read-only para rodar sombra/certificacao a partir de JSON de casos held-out,
sem chamada real de LLM e sem aplicar promocao.

## Mudanca esperada
- Documentar formato de casos held-out em `motor/docs/`.
- Documentar que `motivo_certificacao` e texto opaco para auditoria/display, nao contrato para parse.
- Documentar que `requer_gate=True` deve ser honrado por qualquer camada que aplique mudanca real.
- Documentar que `curador.promoveu` nao deve ser emitido nesta trilha read-only.
- Adicionar CLI opcional em `python3 -m motor.curador` para ler evidencia/casos se o desenho das fatias
  anteriores estiver estavel.
- Atualizar `LOG-VERIFICACAO.md` com a verificacao da fatia.

## Restrições
- Nao mudar catalogo.
- Nao chamar provider real.
- Nao quebrar o comportamento atual de `python3 -m motor.curador <logs>`.

## Onde isto pode dar errado
- CLI virar interface definitiva antes do contrato estabilizar.
- Misturar dados de rascunho com evidencia certificada.
- Painel/auditoria depender de regex sobre `motivo_certificacao`.
- Camada futura aplicar catalogo apesar de `requer_gate=True`.
