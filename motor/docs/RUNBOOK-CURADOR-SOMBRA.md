# Runbook: Curador Sombra e Certificacao

Este caminho e read-only. Ele gera evidencia diagnostica; nao muda catalogo, config ou
roteamento e nao cria intencao autoritativa de promocao.

O formato da CLI ainda e beta: artefatos JSON sao contrato interno de inspecao, nao API
publica, registro autoritativo ou entrada confiavel para apply.

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

Os casos fornecidos a `--sombra` devem ser held-out e certificados. O filtro de `rascunho` vale para o
caminho de logs (`python3 -m motor.curador <logs.jsonl>`), mas nao consegue inferir a procedencia de um
JSON manual.

## Comandos

```bash
python3 -m motor.curador --sombra casos.json --json evidencia-sombra.json
python3 -m motor.curador --certificar evidencia-sombra.json --json certificacao.json
```

`python3 -m motor.curador <logs.jsonl>` continua sendo o caminho existente de perfil read-only.

`--certificar` recomputa e sela a evidencia, mas o arquivo exportado continua nao
autoritativo. Nao promova copiando `status`, hash ou conteudo desse JSON.

O comando legado abaixo exercita somente o default-deny da CLI:

```bash
python3 -m motor.curador --promocao certificacao.json --json veto.json
```

Sem `RepositorioCertificacoes`, ele nao pode criar `promocao_pendente`. A trilha
operacional exige uma integracao de deployment que:

1. registre a certificacao validada em repositório imutavel/autenticado;
2. passe somente o `certification_id` a `preparar_promocao_gated(...)`;
3. confira que o retorno e `promocao_pendente` e `requer_gate=True`;
4. encaminhe a intencao ao gate humano; o curador nao aplica catalogo.

Este repositorio define o protocolo, mas nao fornece hoje esse backend. Portanto, promocao
operacional esta indisponivel por default; um fake de teste nao remove essa restricao.

## Invariantes

- `motivo_certificacao` e texto opaco para auditoria/display; nao use regex nele como contrato.
- `requer_gate=True` deve ser honrado por qualquer camada que aplique mudanca real.
- `curador.promoveu` nao e emitido por estes comandos; ele pertence ao gate externo que aplicar a
  promocao.
- Custo ausente (`null`/`None`) nao e zero.
- JSON/CLI, dict, hash e `status="certificado"` fornecidos pelo chamador nao sao autoridade.
- Custo menor nunca compensa qualidade igual ou pior; ambos os eixos precisam melhorar de
  forma estrita.

## Falhas operacionais

- Repositorio ausente, ID desconhecido ou registro divergente: veto; nao contornar pela CLI.
- Evidencia selada invalida, caso duplicado, proveniencia vazia ou custo nao finito: rejeicao;
  corrigir a origem, nao o agregado.
- Runner falha em um caso: o caso registra falha e os demais continuam; revisar antes de
  certificar.
