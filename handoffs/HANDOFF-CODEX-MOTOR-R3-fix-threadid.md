# HANDOFF — R3 ajuste: `thread_id` fornecido pelo chamador em `despachar_missao` (Codex executa, Claude verifica)

> Corte mínimo. 1 commit. `python3 -m pytest -q` VERDE ao fim (hoje 171 passed). Não relitigar.

## Contexto
No R3, `metafabrica.despachar_missao` (em `motor/mcp_servidor.py`) **sempre** gera o `job_id`
via `uuid4()`. O contrato do Jarvis (REQ-2) diz que o **chamador fornece e reusa** o
`thread_id` — é a chave de correlação com a memória dele. O `GerenciadorJobs.iniciar` já
aceita `thread_id`; falta só expor isso na ferramenta MCP, mantendo o uuid4 como fallback.

## Mudança (FIXADA) — só `motor/mcp_servidor.py`
Na tool `metafabrica.despachar_missao`, adicione um parâmetro **opcional** `thread_id`:

```python
@app.tool(name="metafabrica.despachar_missao", description=DESCRICAO_DESPACHAR)
def despachar_missao(objetivo: str, contexto: str | None = None,
                     restricoes: dict[str, Any] | None = None,
                     thread_id: str | None = None) -> dict:
    try:
        partes = [objetivo]
        if contexto:
            partes.append(f"\n\nContexto:\n{contexto}")
        if restricoes:
            partes.append("\n\nRestrições:\n" + json.dumps(restricoes, ensure_ascii=False))
        return jobs.iniciar(missao_texto="".join(partes), thread_id=thread_id or uuid4().hex)
    except Exception as ex:
        return {"estado": "erro", "erro": {"tipo": type(ex).__name__, "mensagem": str(ex)}}
```

Atualize a descrição `DESCRICAO_DESPACHAR` acrescentando UMA frase ao final:
> "Passe `thread_id` para reusar/correlacionar uma missão; se omitido, um id é gerado."

Nada mais muda. `GerenciadorJobs.iniciar` já valida `thread_id` não-vazio e já reusa o
mesmo `motor.db` (durável). Não toque em `servico.py`, grafo, spec nem nos outros tools.

## Critério de aceite
- `despachar_missao(objetivo="x", thread_id="abc")` → `{"job_id": "abc", "estado": "em_execucao"}`.
- `despachar_missao(objetivo="x")` (sem thread_id) → `job_id` gerado (uuid4), como antes.
- Dois despachos com o **mesmo** `thread_id` apontam para a mesma missão durável (reusa o
  estado no `motor.db`) — comportamento herdado do `GerenciadorJobs`, não reimplementar.
- Teste novo em `tests/test_mcp_servidor.py`: um caso com `thread_id` explícito (id volta
  igual) e um sem (id não-vazio gerado). Suíte inteira verde.

## DÚVIDAS
- (vazio)
