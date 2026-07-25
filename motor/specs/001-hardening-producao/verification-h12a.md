# Verificacao - H12a roteamento runtime por capacidade

Status: **CONCLUIDA NO ESCOPO H12a**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Discovery E Leitura

Graphify foi executado antes do julgamento do codigo:

```text
graphify query "Onde ocorre o roteamento runtime de modelos por capacidades declaradas
entre spec.py, modelos.py e grafo.py?" --budget 1800
```

Foram lidos integralmente `motor/docs/INVARIANTES.md`, `plan.md`,
`clarifications.md`, `handoff-wave2.md` e exatamente estes tres arquivos de producao:

- `motor/motor/spec.py`
- `motor/motor/modelos.py`
- `motor/motor/grafo.py`

O defeito causal estava em `ClienteRoteador._resolver/chamar`: pin, tier, desvio de
ferramenta, esgotamento e fallback podiam selecionar um cliente sem provar que sua entrada
de catalogo cobria todas as capacidades. Na ausencia de cobertura, o codigo caia em
papel/padrao. Um cliente concreto passado diretamente ao grafo tambem contornava o catalogo.

## Contrato Implementado

- `None` e `[]` em `capacidades_requeridas` preservam a rota legada por tier/papel, como
  documentado em `Subagente`.
- Lista nao vazia ativa obrigatoriamente o caminho capability-aware.
- A requisicao e o catalogo sao revalidados em runtime; string vazia, whitespace, tipo
  errado, provedor hostil, custo de ordem invalido, cliente duplicado ou entrada ambigua
  invalidam o catalogo inteiro para aquela chamada.
- O cliente selecionado precisa cobrir o conjunto completo, estar disponivel, respeitar
  `evitar` e suportar ferramentas quando requeridas.
- Pin e tier continuam com precedencia, mas nao podem sobrepor a capacidade minima.
- Retry/fallback nunca usa cliente incapaz; sem alternativa capaz, retorna `None` e nao
  chama backend.
- O grafo bloqueia tarefas com capacidades nao vazias quando o cliente injetado nao declara
  `roteamento_capacidades_runtime=True`.
- `ClienteStub` e `ClienteTierFake` carregam o marker somente como test doubles explicitos.

O marker e um contrato de composicao confiavel, nao validacao de input externo. A prova
real continua em `ClienteRoteador`, que resolve e valida novamente na chamada efetiva.

## Evidencia Causal

`motor/tests/test_hardening_h12a.py` cobre:

| Garantia | Teste |
|---|---|
| Capacidade hostil nao executa | `test_h12a_capacidade_ausente_ou_hostil_nao_executa` |
| Catalogo ausente/malformado nao executa | `test_h12a_catalogo_ausente_ou_hostil_falha_fechado` |
| Provedor hostil invalida catalogo | `test_h12a_provedor_hostil_invalida_catalogo` |
| Rota nao-hashable falha fechada | `test_h12a_rota_hostil_nao_chega_ao_catalogo` |
| Lista vazia preserva legado | `test_h12a_lista_vazia_preserva_rota_legada` |
| Pin/tier incapaz nao contorna catalogo | `test_h12a_pin_ou_tier_incapaz_nao_contorna_catalogo` |
| Fallback preserva todas as capacidades | `test_h12a_fallback_mantem_todas_as_capacidades` |
| Grafo aceita rota completa e rejeita incompleta | `test_h12a_grafo_executa_somente_rota_que_cobre_todas_capacidades` |
| Cliente direto sem enforcement nao executa | `test_h12a_grafo_bloqueia_cliente_direto_sem_enforcement` |

Controles anteriores de S3 foram atualizados sem remover testes: ausencia de cobertura e
independencia sem alternativa agora falham fechadas; tier valido foi incluido no catalogo.

## Gate

Gate H12a repetido pela raiz:

```text
pytest -q tests/test_hardening_h12a.py tests/test_capacidade.py \
  tests/test_modelos.py tests/test_grafo.py tests/test_spec.py
150 passed
```

Conjunto ampliado do agente:

```text
pytest -q tests/test_spec.py tests/test_capacidade.py tests/test_hardening_h12a.py \
  tests/test_modelos.py tests/test_grafo.py tests/test_registro.py tests/test_main.py \
  tests/test_grafo_dep.py tests/test_validadores_deterministicos.py \
  tests/test_ferramenta.py tests/test_experimento_rag.py \
  tests/test_experimento_especialista.py
208 passed
```

- Ruff dos arquivos H12a: limpo.
- mypy de `motor/modelos.py` e `motor/grafo.py`: limpo.
- Bandit high/high: limpo.
- compileall: limpo.
- diff-check: limpo.
- mypy de `tests/test_hardening_h12a.py`: limpo, sem relaxar assertions.
- A suite consolidada, build/install e Gate CI global pertencem ao gate da raiz; este
  documento nao declara o motor pronto para producao.

## Landings

O working tree contem as landings juntas, mas elas devem ser revisadas e pousadas separadas:

- **H12a1a (~200 linhas fisicas):** validacao de requisicao/catalogo e testes hostis.
- **H12a1b (~175 linhas fisicas):** selecao, pin/tier, fallback capability-aware e controles.
- **H12a2 (~130 linhas fisicas):** guard do grafo, propagacao no fluxo real e integracao.

As contagens sao por hunks incrementais sobre o working tree compartilhado; o `numstat`
contra HEAD inclui hardening anterior em `grafo.py` e nao representa uma landing H12a.

## Dividas Delimitadas

- H12a nao implementa teto de custo. Catalogo de tres campos ainda declara ordem, nao custo
  maximo monetario; o desenho esta em `plan-h12b.md` e aguarda revisao humana.
- H13 alinhou `INVARIANTES.md` ao fail-closed de S3 e restaurou o checklist detalhado em
  `motor/docs/security-DoD.md`.

## Onde isto pode dar errado

- O marker pode ser declarado por uma implementacao defeituosa. Apenas composicao confiavel
  pode habilita-lo; input de workflow nunca controla o atributo.
- O catalogo e mutavel por compatibilidade. A revalidacao por chamada evita uso silencioso,
  mas uma mutacao concorrente pode fazer uma chamada falhar fechada entre preview e execucao.
- Entradas duplicadas para o mesmo objeto-cliente invalidam o catalogo. Uma configuracao que
  queira duas rotas logicas deve criar identidades de rota distintas.
- Chamadas legadas com `None|[]` nao possuem prova de capacidade; essa compatibilidade e
  deliberada e nao pode ser usada como rota certificada para specs que declaram requisitos.
- H12a prova selecao, nao custo. Sem H12b, S4 continua aberto.
