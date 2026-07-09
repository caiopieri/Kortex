# HANDOFF OPENCODE — Curador Fatia 3.3: Intencao de Promocao Gated

## Objetivo
Gerar um artefato serializavel de intencao de promocao a partir de uma certificacao aprovada, sem aplicar
mudanca de catalogo/config.

## Mudanca esperada
Adicionar funcao em `motor/motor/curador.py`:

```python
def preparar_promocao_gated(
    certificacao: dict[str, Any],
    emitir_evento: Callable[[str, Any], None] | None = None,
) -> dict[str, Any]:
    ...
```

Retorno minimo:

- `status: "promocao_pendente"`
- `slot`
- `de`
- `para`
- `evidencia`
- `requer_gate: True`

Se a certificacao nao estiver aprovada, retornar/rejeitar deterministicamente sem promocao.

## Eventos
Emitir `curador.promocao_pendente` via callback opcional. Nao emitir `curador.promoveu` nesta fatia.

## Testes obrigatorios
- Certificacao aprovada gera intencao de promocao pendente.
- Certificacao rejeitada nao gera promocao.
- Artefato inclui evidencia suficiente para auditoria.

## Onde isto pode dar errado
- Escrever catalogo diretamente nesta fatia quebra a lei da run gated.
- Esconder evidencia impede revisao adversarial.
