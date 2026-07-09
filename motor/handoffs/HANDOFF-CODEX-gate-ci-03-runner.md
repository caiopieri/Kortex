# HANDOFF CODEX — Gate de CI: Runner do Validador de Comando (Fase 4, Passo 3)

## Por quê (EVOLUCAO V1)
Para fazer o validador de `comando` funcionar em tempo de execução, precisamos estender a lógica do grafo LangGraph em `motor/grafo.py`. Quando o motor encontrar um nó de `tipo: "validador"` com `kind: "comando"`, ele deve rodar o processo determinístico em um subprocesso seguro e coletar o resultado (exit code == 0).
Como é um nó validador, se o comando falhar, ele apontará a lacuna ao nó alvo original (`refazer: alvo`), ativando o loop de auto-correção para que o modelo reescreva o código baseado na saída de erro.

## O que fazer
Modifique a função `construir_grafo` no arquivo `/Users/caioamaraldepieri/Desktop/Projects/Orquestrador/motor/motor/grafo.py`:

1. **Passar `workspace` para `executar_validador`:**
   Altere a assinatura de `executar_validador` e sua chamada dentro de `subagente`:
   ```python
   # No nó subagente:
   if sub.get("tipo", "modelo") == "validador":
       return executar_validador(sub, deps, payload["workspace"])
   
   # Na declaração de executar_validador:
   def executar_validador(sub: dict[str, Any], deps: dict[str, str], workspace: Path) -> dict:
   ```

2. **Implementar a lógica de `kind == "comando"`:**
   Dentro de `executar_validador`, adicione o suporte ao tipo `"comando"`:
   - Recupere a string `"comando"` de `config`.
   - Formate a string do comando substituindo placeholders pelas entradas do subagente resolvidas (que já contêm referências aos caminhos de artefatos resolvidos por `resolver_refs_artefato`).
   - Faça o parse do comando usando `shlex.split`.
   - **Validação de Segurança:** Obtenha o nome do executável (`Path(partes[0]).name`). Se `executaveis_permitidos` estiver definido e o executável não estiver contido nele, retorne `aprovado = False` e `motivo = "executável não permitido: <nome>"`.
   - **Subprocesso:** Execute o comando via `subprocess.run`, capturando `stdout` e `stderr` com um timeout definido (configurável em `config` ou default de 30s).
   - O validador será **aprovado** se o `exit_code` for `0` (`proc.returncode == 0`). Caso contrário, será **reprovado**.
   - O `motivo` da falha deve conter o `stdout` e `stderr` gerados pelo processo (para que o programador saiba o que corrigir).
   - Registre o evento `"validador.rodou"` no log utilizando a chave `log.evento(...)` com os mesmos campos das outras validações.
   - Retorne o dicionário de resultado no formato:
     ```python
     resultado = {
         "id": sub["id"],
         "saida": saida,
         "tentativas": 1,
         "aprovado": aprovado,
         "motivo": motivo,
         "alvo": alvo
     }
     if not aprovado and alvo:
         resultado["refazer"] = alvo
     ```

## DoD (Falsificável)
1. Modificações em `motor/grafo.py` preservando a estrutura original de LangGraph e as checagens das outras rotas (V1 intacto).
2. Validador `comando` executa comandos CLI em subprocessos, respeitando a allowlist de executáveis.
3. Se o comando retornar código `0`, o nó é aprovado. Se retornar diferente de `0` (ex: pytest falhou, ruff falhou), o nó é reprovado e adiciona o ID do alvo a `refazer`.
4. Evento `"validador.rodou"` é disparado com as informações corretas e sem causar drift de schema.
5. Todos os testes existentes passam.
