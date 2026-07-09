# Runbook: Curador Sombra e Certificacao

Este caminho e read-only. Ele gera evidencia para gate posterior; nao muda catalogo, config ou
roteamento.

## Casos held-out

Arquivo para `--sombra`:

```json
{
  "proposta": {"slot": "executor/simples", "titular": "modelo-atual", "candidato": "modelo-novo"},
  "casos": [
    {
      "id": "caso-1",
      "slot": "executor/simples",
      "entrada": {"prompt": "..."},
      "titular": {"modelo": "modelo-atual", "aprovado": true, "custo_usd": 0.02},
      "candidato": {"aprovado": true, "custo_usd": 0.01, "motivo": "ok"}
    }
  ]
}
```

`candidato` e usado apenas pelo runner stub da CLI para evitar chamada real de LLM. Adaptadores reais
devem continuar injetados por codigo/teste ate existir contrato de replay fiel.

## Comandos

```bash
python3 -m motor.curador --sombra casos.json --json evidencia-sombra.json
python3 -m motor.curador --certificar evidencia-sombra.json --json certificacao.json
python3 -m motor.curador --promocao certificacao.json --json promocao.json
```

`python3 -m motor.curador <logs.jsonl>` continua sendo o caminho existente de perfil read-only.

## Invariantes

- `motivo_certificacao` e texto opaco para auditoria/display; nao use regex nele como contrato.
- `requer_gate=True` deve ser honrado por qualquer camada que aplique mudanca real.
- `curador.promoveu` nao e emitido por estes comandos; ele pertence ao gate externo que aplicar a
  promocao.
- Custo ausente (`null`/`None`) nao e zero.
