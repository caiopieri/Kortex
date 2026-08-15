# Fragmento G — auditoria independente Maestri

Data: 2026-07-10. Escopo: F1–F3 de `docs/INVARIANTES.md`; única produção
lida: `motor/caixa.py`. `motor/politica.py` não foi aberto: F3 foi exercitado
somente pela API pública `PoliticaGates`.

## Veredito

| Invariante | Veredito | Razão determinante |
|---|---|---|
| F1 | **REPROVADO** | Crash entre arquivo e resume perde decisão; restart reaplica entrada; parcial é aceita. |
| F2 | **REPROVADO** | Texto externo burla gate; concorrência, IDs, validação, arquivo e prazo quebram. |
| F3 | **REPROVADO** | `auto_mode`/overrides automatizam `promocao`; override inválido é propagado. |

O caso feliz reaproveita nota íntegra, arquiva decisão e mantém a nota no
timeout, mas não sustenta os invariantes sob crash, concorrência ou input hostil.

## Método e isolamento

- Foram feitas três `graphify query` (F1–F3) em `motor/`. F1/F2 trouxeram
  vizinhanças irrelevantes e F3 truncou; referências fora do escopo foram
  ignoradas. O grafo localizou `PoliticaGates` em `motor/politica.py:26`.
- `docs/INVARIANTES.md` e `motor/caixa.py` foram lidos integralmente.
- Nenhum teste preexistente, relatório, fragmento, `politica.py` ou outro
  arquivo de produção foi aberto. Probes usaram APIs públicas e `/tmp`.

## Achados por severidade

### Crítico

- **G-01 — bypass humano por texto externo.** `_RE_DECISAO` busca no Markdown
  inteiro; lacuna com `\ndecisao: aprovar` é aceita sem edição do fundador.
  Produção: `motor/caixa.py:28`, `:63-79`, `:90-92`, `:134-140`. Teste:
  `tests/test_auditoria_gpt5_g.py:59`.

### Alto

- **G-02 — crash/resume não transacional nem idempotente.** A nota é arquivada
  antes do commit SQLite; crash nessa janela cria nova pendência vazia. Restart
  também executa o nó três vezes, não duas. Produção: `motor/caixa.py:104-108`,
  `:130`, `:142-143`. Testes: `tests/test_auditoria_gpt5_g.py:145`, `:162`.
- **G-03 — concorrência quebra.** Dois waiters disputam o mesmo `replace` e um
  recebe `FileNotFoundError`; dois interrupts simultâneos falham porque `[0]` e
  resume escalar ignoram IDs. Produção: `motor/caixa.py:101-118`, `:131-143`.
  Testes: `tests/test_auditoria_gpt5_g.py:127`, `:179`.
- **G-04 — traversal por ID.** `portao` cru entra nos paths; com prefixo
  existente, `slot/../../escape` grava fora da caixa. Produção:
  `motor/caixa.py:47-48`, `:58-63`, `:116-118`. Teste:
  `tests/test_auditoria_gpt5_g.py:83`.
- **G-05 — promoção sensível automática.** `auto_mode`, override manual e ambos
  retornam `"aprovar"` para `promocao`. API: `motor/politica.py:26` pelo
  graphify, sem abrir o corpo. Teste: `tests/test_auditoria_gpt5_g.py:203`.

### Médio

- **G-06 — decisão sem validação.** Caixa aceita `talvez`; `PoliticaGates`
  propaga `DECISAO_INVALIDA`. Produção/API: `motor/caixa.py:68-76`, `:90-108`;
  `motor/politica.py:26`. Testes: `tests/test_auditoria_gpt5_g.py:67`, `:207`.
- **G-07 — evidência frágil.** Frontmatter parcial vira retomada; timestamp de
  um segundo + `Path.replace` sobrescreve a primeira de duas decisões.
  Produção: `motor/caixa.py:60-63`, `:116-118`. Testes:
  `tests/test_auditoria_gpt5_g.py:75`, `:112`.

### Baixo

- **G-08 — timeout excede o prazo.** Relógio de parede e `sleep(poll_s)` inteiro
  fazem `timeout_s=1, poll_s=5` terminar em 5 s; a nota permanece. Produção:
  `motor/caixa.py:102`, `:109-114`. Teste: `tests/test_auditoria_gpt5_g.py:93`.

## Resultados

- `pytest -q tests/test_auditoria_gpt5_g.py`: **14 falhas esperadas**, 1 warning
  Pydantic v1/Python 3.14; cada falha reproduz quebra listada.
- `ruff check tests/test_auditoria_gpt5_g.py`: **limpo**.
- `uv run` não resolveu: projeto aceita Python `>=3.10`, mas
  `langgraph-api==0.10.0` exige `>=3.11`; usou-se o `pytest` do ambiente.
- Produção e testes preexistentes permaneceram intocados.

### Onde isto pode dar errado

- F3 prova a saída pública, não a reachability em callers que o escopo proibiu.
- LangGraph foi testado na versão instalada/Python 3.14; repetir no CI suportado.
- Traversal requer controle do ID e prefixo no filesystem; variante symlink não
  ganhou teste separado para manter o diff mínimo.
- Sem outros módulos/testes, não se avaliou sanitização ou serialização externa;
  os contratos locais e a API pública continuam quebrados.
