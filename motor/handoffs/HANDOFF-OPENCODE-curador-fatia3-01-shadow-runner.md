# HANDOFF OPENCODE — Curador Fatia 3.1: Shadow Runner Read-only

## Contexto
Leia antes:

- `motor/README.md`
- `motor/COMO-USAR.md`
- `motor/AGENTS.md`
- `motor/docs/EVOLUCAO.md`
- `motor/docs/ADR-002-curador-fatia3.md`
- `motor/motor/curador.py`
- `motor/tests/test_curador.py`

O curador ja tem observador/propositor/ledger read-only. Esta fatia inicia a parte "agir", mas ainda
sem aplicar nada: rodar candidato em sombra sobre casos held-out explicitos.

## Objetivo
Adicionar a `motor/motor/curador.py` uma funcao read-only `rodar_sombra(...)` que:

1. Recebe uma proposta de troca de modelo para um slot.
2. Recebe casos de referencia explicitos.
3. Executa o modelo candidato por runner injetado.
4. Retorna evidencia comparativa serializavel, sem alterar catalogo, config, roteamento ou logs originais.
5. Emite evento `curador.sombra` se receber callback/event logger opcional.

## Contrato sugerido
Use dicts simples e stdlib. Pode ajustar nomes se os testes ficarem mais claros, mas preserve a ideia:

```python
def rodar_sombra(
    proposta: dict[str, Any],
    casos: list[dict[str, Any]],
    runner: Callable[[dict[str, Any], str], dict[str, Any]],
    emitir_evento: Callable[[str, Any], None] | None = None,
) -> dict[str, Any]:
    ...
```

Formato minimo de `proposta`:

```python
{
    "slot": "executor/simples",
    "titular": "modelo-atual",
    "candidato": "modelo-novo",
}
```

Formato minimo de caso:

```python
{
    "id": "caso-1",
    "slot": "executor/simples",
    "entrada": {"prompt": "..."},
    "titular": {"modelo": "modelo-atual", "aprovado": True, "custo_usd": 0.02},
}
```

Formato minimo de retorno do runner:

```python
{"aprovado": True, "custo_usd": 0.01, "saida": "ok", "motivo": ""}
```

Formato esperado da evidencia:

```python
{
    "status": "sombra_concluida",
    "slot": "executor/simples",
    "titular": {"modelo": "modelo-atual", "aprovados": 1, "total": 1, "taxa_aprovacao": 1.0, "custo_medio_usd": 0.02},
    "candidato": {"modelo": "modelo-novo", "aprovados": 1, "total": 1, "taxa_aprovacao": 1.0, "custo_medio_usd": 0.01},
    "casos": [...]
}
```

## Regras
- Read-only: nao escrever catalogo, modelos, registro, config ou logs existentes.
- Sem chamada real de modelo nos testes.
- `custo_usd=None` deve permanecer `None`; nao converter para zero.
- Se um caso nao for do slot da proposta, ignore ou rejeite de forma deterministica. Escolha uma politica
  e teste. Preferencia: ignorar e registrar contagem `casos_ignorados`.
- Se o runner levantar excecao, o caso do candidato deve virar `aprovado=False` com `motivo` contendo a
  classe/erro. Nao deixe a sombra inteira quebrar por um caso.
- Evento `curador.sombra`: emita pelo callback opcional com campos suficientes (`slot`, `titular`,
  `candidato`, `casos`, `aprovados_candidato`, `aprovados_titular`).

## Testes obrigatorios
Adicionar em `motor/tests/test_curador.py`:

1. `test_rodar_sombra_agrega_titular_e_candidato`
   - Dois casos do mesmo slot.
   - Runner fake aprova 1/2 e retorna custos.
   - Assert de totais, taxa de aprovacao e custo medio.

2. `test_rodar_sombra_nao_quebra_com_excecao_do_runner`
   - Runner levanta em um caso.
   - Evidencia marca o caso como reprovado e preserva motivo.

3. `test_rodar_sombra_emite_evento_read_only`
   - Passar callback fake que captura eventos.
   - Assert que `curador.sombra` foi emitido.
   - Assert que a proposta/casos originais nao foram mutados.

## DoD
- `python3 -m pytest motor/tests/test_curador.py -q` verde.
- `ruff check motor/motor/curador.py motor/tests/test_curador.py` verde.
- `mypy motor/motor/curador.py motor/tests/test_curador.py` verde.
- Diff limitado a `motor/motor/curador.py` e `motor/tests/test_curador.py`.
- Um commit com mensagem clara. `git add` especifico, nunca `git add -A`.

## Onde isto pode dar errado
- Nao implemente certificacao/promocao nesta fatia.
- Nao trate custo ausente como custo zero.
- Nao use logs atuais como se fossem replay fiel; eles nao carregam prompt/saida completa.
- Nao chame LLM real no teste.
