**Especificação da Etapa de Gravação de Saída**

**Formatação de Saída JSON:**

*   O arquivo de saída será formatado em JSON, com indentação para melhor legibilidade.
*   Cada linha do arquivo CSV de entrada corresponderá a um objeto JSON no arquivo de saída.
*   Os nomes das colunas do arquivo CSV serão usados como chaves nos objetos JSON.

**Opções de Destino:**

*   **Arquivo:** O arquivo de saída JSON poderá ser gravado em um arquivo físico no sistema de arquivos.
*   **Stream:** O arquivo de saída JSON também poderá ser enviado para um stream de saída, como um socket de rede ou um pipeline de processamento.

**Controle de Sobrescrita:**

*   Para evitar a perda de dados, a etapa de gravação verificará se o arquivo de destino já existe antes de gravar a saída.
*   Se o arquivo existir, a etapa de gravação poderá ser configurada para:
    *   Sobrescrever o arquivo existente.
    *   Anexar a saída ao arquivo existente.
    *   Gerar um novo nome de arquivo para evitar a sobrescrita.

**Validação Pós-Gravação:**

*   Após a gravação da saída, a etapa de gravação realizará uma validação para garantir que o arquivo de saída foi gerado corretamente.
*   A validação incluirá:
    *   Verificação da existência do arquivo de saída.
    *   Verificação do tamanho do arquivo de saída.
    *   Verificação da integridade do arquivo de saída por meio de um checksum.

**Parâmetros de Configuração:**

*   `output_file`: Caminho do arquivo de saída JSON.
*   `output_stream`: Stream de saída para enviar o arquivo JSON.
*   `overwrite`: Flag para controlar a sobrescrita do arquivo de destino (true/false).
*   `append`: Flag para controlar a anexação da saída ao arquivo existente (true/false).
*   `validation`: Flag para habilitar ou desabilitar a validação pós-gravação (true/false).

**Exemplo de Configuração:**

```json
{
  "output_file": "saida.json",
  "output_stream": null,
  "overwrite": true,
  "append": false,
  "validation": true
}
```

Essa especificação detalha a etapa de gravação de saída do pipeline de conversão CSV→JSON, abordando formatação de saída, opções de destino, controle de sobrescrita e validação pós-gravação. Além disso, fornece parâmetros de configuração para personalizar o comportamento da etapa de gravação de acordo com as necessidades do usuário.