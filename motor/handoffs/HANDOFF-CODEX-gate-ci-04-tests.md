# HANDOFF CODEX — Gate de CI: Testes Unitários do Validador de Comando (Fase 4, Passo 4)

## Por quê (EVOLUCAO V1)
Para garantir que a implementação do validador de `comando` seja robusta, precisamos adicionar testes automáticos na suíte de testes. Os testes devem cobrir o fluxo de aprovação (sucesso do comando), reprovação (falha do comando), a integração com o loop de reconciliação para re-executar o alvo e o bloqueio de segurança por allowlist.

## O que fazer
Modifique o arquivo `/Users/caioamaraldepieri/Desktop/Projects/Orquestrador/motor/tests/test_validadores_deterministicos.py` e adicione os seguintes testes unitários:

1. **`test_validador_comando_sucesso(tmp_path)`:**
   - Crie uma WorkflowSpec onde um subagente modelo produz uma saída (ex: `"hello"`).
   - Defina um validador de tipo `validador` e `kind: "comando"` que roda um comando que retorna exit code `0` (ex: `echo "passou"` ou `python3 -c "print('ok')"`).
   - O comando deve passar pela allowlist se houver.
   - Execute o grafo e valide que o resultado final é `aprovado` e que o evento `validador.rodou` foi emitido com `aprovado: True`.

2. **`test_validador_comando_falha_re-dispara_alvo(tmp_path)`:**
   - Crie uma WorkflowSpec semelhante.
   - O validador roda um comando que retorna código de saída `1` (ex: `python3 -c "import sys; sys.exit(1)"`).
   - Execute o grafo com a reconciliação habilitada (`cobertura="preencher"`).
   - Configure o roteador do stub de modelo para retornar uma resposta inválida no primeiro turno, mas uma resposta que passa em uma checagem simulada no segundo turno (ou configure o comando para passar no segundo turno com base em arquivo escrito no workspace).
   - Valide que o alvo foi re-executado pelo loop de reconciliação (o número de chamadas ao executor deve ser `2`).
   - Valide que o validador foi reprovado no primeiro ciclo e aprovado no segundo.

3. **`test_validador_comando_bloqueado_por_allowlist(tmp_path)`:**
   - Configure o grafo com uma allowlist de executáveis permitidos que exclui o comando configurado no validador (ex: allowlist contém apenas `python3` e o comando tenta rodar `bash` ou `sh`).
   - Execute o grafo.
   - Valide que o validador é reprovado com motivo de segurança ("executável não permitido") e sem executar de fato o processo no sistema operacional.

## DoD (Falsificável)
1. Modificações em `tests/test_validadores_deterministicos.py` adicionam os 3 novos testes estruturados sem alterar ou quebrar as coberturas de `schema_json` e `contem`.
2. Todos os testes passam (pytest -q verde para este arquivo).
3. Nenhuma exceção de concorrência ou imports ausentes.
4. Cobertura de tipos mypy ok.
