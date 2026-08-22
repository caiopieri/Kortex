# HANDOFF — R3: servidor MCP configurável por env (Codex executa, Claude verifica)

> Corte pequeno, 1 commit. `python3 -m pytest -q` VERDE ao fim (hoje 173 passed). Não relitigar.
> Preserva tudo do R3: gate sempre espera, sem auto-resolve, fronteiras intactas.

## Contexto / problema
`motor/mcp_servidor.py` hoje faz `jobs = gerenciador or GerenciadorJobs()` — sem `cfg_modelos`
nem `dir_registro`. Logo `construir_cliente` cai no `ClienteClaudeCLI` (exige `claude` no PATH).
O Caio roteia pelo Codex/registry barato (`exemplos/modelos-codex.json` ou um dir de Registry),
então o servidor MCP precisa **aceitar essa config** — senão a meta-fábrica via MCP só fala Claude.

## Mudança (FIXADA) — só `motor/mcp_servidor.py`
`criar_app` (e `main`) leem config de **variáveis de ambiente** (injetadas pelo host MCP) e
montam o `GerenciadorJobs` com elas. Nada de credenciais hardcoded; chaves de provedor continuam
vindo do env (REQ-7).

Env lidas (todas opcionais; ausência = comportamento de hoje):
- `MOTOR_MODELOS` — caminho de um JSON de `--modelos` (ex.: `exemplos/modelos-codex.json`).
- `MOTOR_REGISTRO` — diretório do Registry (alternativa a `MOTOR_MODELOS`; **erro se ambos**).
- `MOTOR_DB` — caminho do `motor.db` (default `motor.db`).
- `MOTOR_WORKSPACE` — base dos artefatos (obrigatório; não há default relativo).

Esqueleto:
```python
import os, json
from pathlib import Path

def _gerenciador_de_env() -> GerenciadorJobs:
    modelos = os.environ.get("MOTOR_MODELOS")
    registro = os.environ.get("MOTOR_REGISTRO")
    if modelos and registro:
        raise ValueError("use MOTOR_MODELOS OU MOTOR_REGISTRO, não os dois")
    cfg_modelos = json.loads(Path(modelos).read_text(encoding="utf-8")) if modelos else None
    return GerenciadorJobs(
        db_path=os.environ.get("MOTOR_DB", "motor.db"),
        workspace_base=os.environ["MOTOR_WORKSPACE"],
        cfg_modelos=cfg_modelos,
        dir_registro=registro,
    )

def criar_app(gerenciador: GerenciadorJobs | None = None) -> FastMCP:
    app = FastMCP("metafabrica")
    jobs = gerenciador or _gerenciador_de_env()
    ...  # tools inalteradas
```
- **Não** ligue `--auto`/auto-mode: a política do serviço continua all-manual (gate espera o
  humano). Não toque em `servico.py`, grafo, spec, nem nas 4 tools ou suas descrições.
- O parâmetro `gerenciador` injetável continua (os testes passam um stub) — só o **fallback**
  passa a ler env em vez de `GerenciadorJobs()` cru.

## Critério de aceite
- Sem env setada → `_gerenciador_de_env()` monta igual a hoje (claude CLI), comportamento intacto.
- `MOTOR_MODELOS=exemplos/modelos-codex.json python -m motor.mcp_servidor` → o gerenciador usa
  o roteador da config (Codex/registry), **sem** exigir `claude` no PATH se a config não usar claude.
- `MOTOR_MODELOS` e `MOTOR_REGISTRO` juntos → `ValueError` claro.
- Teste novo em `tests/test_mcp_servidor.py`: setar `MOTOR_MODELOS` (tmp file) e checar que
  `_gerenciador_de_env()` devolve um `GerenciadorJobs` com `cfg_modelos` preenchido; e o caso de
  conflito levantar erro. (Use `monkeypatch.setenv`.) Suíte inteira verde.

## DÚVIDAS
- (vazio)
