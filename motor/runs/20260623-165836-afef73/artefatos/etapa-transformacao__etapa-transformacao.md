**Especificação da Etapa de Transformação**

**Introdução**

A etapa de transformação é um componente crítico do pipeline de conversão CSV→JSON, responsável por converter os dados do formato CSV para um formato JSON estruturado e normalizado. Esta etapa é fundamentada na arquitetura definida para o projeto, que inclui a leitura de arquivos, validação de colunas, transformação e gravação de saída.

**Mapeamento de Tipos**

Para garantir a consistência e a precisão dos dados, é necessário mapear os tipos de dados dos campos no arquivo CSV para os tipos de dados correspondentes em JSON. Abaixo, está um exemplo de mapeamento de tipos que pode ser utilizado:

| Campo CSV | Tipo CSV | Tipo JSON |
| --- | --- | --- |
| id | Integer | Number |
| nome | String | String |
| data_nascimento | Date | String (formato ISO 8601) |
| valor | Float | Number |

**Regras de Normalização**

As regras de normalização são aplicadas para garantir que os dados sejam consistentes e fáceis de processar. As seguintes regras de normalização serão aplicadas:

1. **Tratamento de Dados Faltantes**: Os campos com dados faltantes serão representados como `null` em JSON.
2. **Formatação de Datas**: As datas serão formatadas de acordo com o padrão ISO 8601 (YYYY-MM-DDTHH:MM:SSZ).
3. **Remoção de Espaços em Branco**: Os espaços em branco no início e no fim dos campos de texto serão removidos.
4. **Conversão de Maiúsculas e Minúsculas**: Os campos de texto serão convertidos para minúsculas, a menos que especificado de outra forma.

**Estrutura do JSON de Saída**

A estrutura do JSON de saída será a seguinte:

```json
{
  "id": Number,
  "nome": String,
  "data_nascimento": String (formato ISO 8601),
  "valor": Number
}
```

**Exemplo de Transformação**

Abaixo, está um exemplo de como um registro CSV pode ser transformado em JSON:

Registro CSV:
```csv
id,nome,data_nascimento,valor
1,João,1990-01-01,10.50
```

Registro JSON:
```json
{
  "id": 1,
  "nome": "joão",
  "data_nascimento": "1990-01-01T00:00:00Z",
  "valor": 10.50
}
```

**Conclusão**

A etapa de transformação é um componente fundamental do pipeline de conversão CSV→JSON, responsável por converter os dados do formato CSV para um formato JSON estruturado e normalizado. Com o mapeamento de tipos, regras de normalização e estrutura do JSON de saída definidos, é possível garantir que os dados sejam consistentes e fáceis de processar.