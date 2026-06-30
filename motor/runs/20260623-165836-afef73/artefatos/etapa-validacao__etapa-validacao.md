**Especificação da Etapa de Validação de Colunas**

**Resumo:** 
A etapa de validação de colunas é crucial no pipeline de conversão CSV→JSON, garantindo que os dados sejam consistentes e conformem às regras de negócio estabelecidas. Esta especificação detalha as regras de coluna, tipos de dados, validadores disponíveis e mensagens de erro para essa etapa.

**Regras de Coluna:**

1. **Cabeçalho:** O arquivo CSV deve ter um cabeçalho na primeira linha, contendo os nomes das colunas. Esses nomes devem ser únicos e não vazios.
2. **Tipos de Dados:** Cada coluna deve ter um tipo de dado específico (e.g., inteiro, float, string, data). A validação verificará se cada valor na coluna corresponde ao tipo de dado esperado.
3. **Regras de Negócio:** 
   - **Coluna "ID":** Deve ser um número inteiro positivo.
   - **Coluna "Nome":** Deve ser uma string não vazia com no máximo 50 caracteres.
   - **Coluna "Data de Nascimento":** Deve ser uma data no formato "DD/MM/AAAA" e não pode ser posterior à data atual.

**Tipos de Dados Suportados:**

- Inteiro
- Float
- String
- Data (no formato "DD/MM/AAAA")

**Validadores Disponíveis:**

1. **Validador de Tipo:** Verifica se o valor corresponde ao tipo de dado esperado para a coluna.
2. **Validador de Cabeçalho:** Verifica a existência e a unicidade dos nomes das colunas no cabeçalho.
3. **Validador de Regras de Negócio:** Aplica as regras de negócio específicas para cada coluna.

**Mensagens de Erro:**

1. **Erro de Cabeçalho:** "Cabeçalho inválido: {mensagem_especifica}"
2. **Erro de Tipo de Dado:** "Valor '{valor}' na coluna '{coluna}' não é do tipo '{tipo}'"
3. **Erro de Regra de Negócio:** "Valor '{valor}' na coluna '{coluna}' viola a regra de negócio: {regra}"

**Exemplo de Configuração:**

```json
{
  "colunas": [
    {
      "nome": "ID",
      "tipo": "inteiro",
      "regras": ["positivo"]
    },
    {
      "nome": "Nome",
      "tipo": "string",
      "regras": ["max_50_caracteres"]
    },
    {
      "nome": "Data de Nascimento",
      "tipo": "data",
      "regras": ["data_valida"]
    }
  ]
}
```

**Conclusão:**
A etapa de validação de colunas é essencial para garantir a qualidade e a consistência dos dados durante o processo de conversão CSV→JSON. Com as regras de coluna, tipos de dados, validadores e mensagens de erro especificados, é possível automatizar a detecção de erros e anomalias, melhorando a robustez do pipeline e a confiabilidade dos dados resultantes.