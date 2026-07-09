# HANDOFF CODEX — Gate de CI: Validação de Spec com kind 'comando' (Fase 4, Passo 2)

## Por quê (EVOLUCAO V1)
Para suportar o validador de `comando` na `WorkflowSpec`, a estrutura de validação da spec deve reconhecer a string `"comando"` como um tipo válido de validador determinístico (V1), além de `schema_json` e `contem`.
Este handoff atualiza as regras do Pydantic em `motor/spec.py` para permitir e validar essa nova primitiva de spec.

## O que fazer
Modifique o arquivo `/Users/caioamaraldepieri/Desktop/Projects/Orquestrador/motor/motor/spec.py`:

1. **Adicionar "comando" à lista de tipos permitidos:**
   No método `_consistencia` (ou validação interna de `Subagente`):
   ```python
   kind = s.validador.get("kind")
   if kind not in {"schema_json", "contem", "comando"}:
       raise ValueError(f"subagente '{s.id}' usa validador kind inválido: {kind}")
   ```
2. **Definir regras de validação para `kind == "comando"`:**
   - Exigir que `s.valida` esteja definido.
   - Exigir que `s.valida` esteja contido em `s.depende_de`.
   - Exigir que `s.validador` contenha a chave `"config"` e que `"config"` contenha a chave `"comando"` (string).
   - Opcionalmente, permitir a chave `"timeout"` (inteiro) na configuração.
   - Garantir que o validador `comando` não exija `papel` ou `rubrica` (visto que ele é executado por algoritmo, não por LLM).

## DoD (Falsificável)
1. Modificações em `motor/spec.py` preservando a compatibilidade retroativa (specs antigas sem o validador `comando` continuam válidas e verdes).
2. Validação Pydantic lança `ValueError` apropriado se a spec declarar `kind: "comando"` sem a chave `"comando"` em `config`.
3. Validação Pydantic lança `ValueError` se o validador `comando` não declarar `valida` ou se `valida` não estiver em `depende_de`.
4. Todos os testes existentes em `tests/test_spec.py` continuam passando. Mypy limpo.
