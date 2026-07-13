# Auditoria independente — Fragmento F (K4/U1–U3)

Data: 2026-07-10

Escopo de produção: somente `motor/curador.py`

Specs: `docs/INVARIANTES.md` e `docs/ADR-003-curador-promocao-intencao-v1.md`

## Método e independência

O julgamento abaixo foi registrado antes da abertura de
`tests/test_auditoria_gpt5_f.py`. Nenhum outro teste, fragmento ou relatório foi
lido. `graphify query "K4 U1 U2 U3" --budget 3000` respondeu
`No matching nodes found`; portanto nenhuma conclusão depende do grafo. Para o
teste cross-slice, `tipos()` foi chamado pela API pública, sem abrir
`eventos_schema.py`.

## Veredito

| Invariante | Veredito | Fundamento |
|---|---|---|
| K4 | **APROVADO no escopo estreito** | A função de promoção retorna intenção com `requer_gate=True`, emite apenas `curador.promocao_pendente` e não contém apply de catálogo/config/roteamento nem `curador.promoveu` (`motor/curador.py:358-376`; teste positivo em `tests/test_auditoria_gpt5_f.py:228-246`). |
| U1 | **REPROVADO — alta** | O runner recebe o caso original e as cópias são rasas; mutação e aliases quebram o read-only profundo (`motor/curador.py:245-253,381-401`; testes `:63-93`). |
| U2 | **REPROVADO — crítica** | Held-out não tem integridade, agregação aceita valores hostis/parciais e a certificação confia em resumos fornecidos sem recomputar casos (`motor/curador.py:229-314,411-432`; testes `:119-215`). |
| U3 | **REPROVADO — alta** | `status="certificado"` é a única condição de entrada; certificação vazia/forjada vira intenção pendente (`motor/curador.py:345-369`; teste `:218-225`). |

K4 atende à decisão de não aplicar automaticamente (`docs/INVARIANTES.md:14`;
`docs/ADR-003-curador-promocao-intencao-v1.md:19-29`). Isso não compensa a
cadeia de evidência falsificável em U1–U3 (`docs/INVARIANTES.md:54-56`).

## Achados priorizados

### P0 — certificação e intenção podem ser inteiramente forjadas

`certificar_sombra` lê diretamente taxas e custos do chamador e não exige
`status="sombra_concluida"`, casos, total positivo, contagens consistentes ou
proveniência (`motor/curador.py:287-314`). Um agregado sem `casos` certificou no
teste `tests/test_auditoria_gpt5_f.py:185-189`.

Em seguida, `preparar_promocao_gated` testa somente
`status_cert != "certificado"` (`motor/curador.py:345-350`). O valor
`{"status": "certificado"}` produziu `promocao_pendente`, evento de pendência e
campos `slot/de/para=None`; o gate está presente, mas a evidência é inexistente
(`motor/curador.py:352-376`; teste `tests/test_auditoria_gpt5_f.py:218-225`).

### P1 — sombra não é read-only diante do runner nem de aliases

O caso original é entregue ao runner (`motor/curador.py:245-248`). Mesmo quando
o runner muta o caso e depois lança, a exceção é contida mas a mutação permanece.
Além disso, `dict(resultado)` e `dict(titular)` são cópias rasas
(`motor/curador.py:390-401`), então mutar a evidência retornada altera estruturas
aninhadas dos casos. Ambos os vetores falharam em
`tests/test_auditoria_gpt5_f.py:63-93`.

Exceções ordinárias sem mutação são corretamente convertidas em reprovação e a
sombra continua (`motor/curador.py:386-395`; teste aprovado em
`tests/test_auditoria_gpt5_f.py:96-116`). Não há rollback de efeitos anteriores
nem evento específico de erro do runner.

### P1 — held-out vazio, duplicado ou sem proveniência é aceito

O único filtro é igualdade de `slot` após coerção para string
(`motor/curador.py:229-239`). Não há mínimo, ID único, split/fonte/hash ou
congelamento. Lista vazia recebe `sombra_concluida`; caso declarado como treino e
IDs duplicados podem certificar (`motor/curador.py:245-262`; testes
`tests/test_auditoria_gpt5_f.py:119-135,174-182`). Duplicatas também reponderam
qualidade e custo.

### P1 — tipos e agregação violam o veto anti-Goodhart

- `aprovado` usa truthiness, portanto a string `"false"` contou como aprovação
  (`motor/curador.py:411-419`; teste `tests/test_auditoria_gpt5_f.py:138-146`).
- Custos ausentes parciais são removidos do denominador, em vez de tornar o lado
  incomparável (`motor/curador.py:419-432`; teste `:149-160`).
- Custo string vindo do runner causa `TypeError` em `sum(...)` (`:422-432`;
  teste `:163-171`).
- O certificador valida tipos numéricos apenas com `isinstance(int, float)` e
  só veta custo `None` (`motor/curador.py:296-314`). Taxa bool, custos string
  lexicográficos, bool, negativo e infinito, além de taxas fora de `[0,1]`,
  certificaram (`tests/test_auditoria_gpt5_f.py:192-215`).
- `NaN` e custo totalmente ausente foram rejeitados nos casos exercitados, mas
  `NaN` falha apenas incidentalmente na comparação; não há validação explícita
  de finitude/domínio.

### P1 — eventos do curador estão fora do schema público

O teste cross-slice coletou os quatro eventos efetivamente emitidos e
`set(eventos) <= tipos()` falhou; todos ficaram fora do conjunto público
(`tests/test_auditoria_gpt5_f.py:249-265`). Isso quebra a promessa de eventos
fechados/auditáveis quando o callback estiver ligado ao log tipado.

## Eventos `curador.*` emitidos

| Evento | Linha de emissão |
|---|---:|
| `curador.sombra` | `motor/curador.py:265` (payload `:266-271`) |
| `curador.certificou` | seleção/emissão `motor/curador.py:325-331` |
| `curador.rejeitou` | seleção/emissão `motor/curador.py:325-331` |
| `curador.promocao_pendente` | `motor/curador.py:372` (payload `:373-375`) |

Não há emissão de `curador.promoveu`, `curador.promocao_vetada` nem evento de
erro do runner. O veto existe apenas como retorno em `motor/curador.py:346-350`.

## Resultados executados

- `.venv/bin/pytest -q tests/test_auditoria_gpt5_f.py`: **17 falhas, 6 passes em
  0,33 s**. Os passes confirmam contenção de `RuntimeError`, veto nos casos
  exercitados de `NaN`/custo totalmente ausente e a intenção positiva gateada
  sem `curador.promoveu`. As 17 falhas reproduzem os achados acima, incluindo um
  `TypeError` para custo string e o drift dos quatro eventos.
- `ruff check tests/test_auditoria_gpt5_f.py`: **passou**.
- `ruff format --check tests/test_auditoria_gpt5_f.py`: **passou**.
- A tentativa inicial com `uv run` não executou teste nem Ruff: o resolver
  encontrou conflito preexistente entre `requires-python >=3.10` e
  `langgraph-api==0.10.0` (que exige Python >=3.11). Os binários instalados foram
  usados para obter os resultados acima, sem alterar dependências.

Produção não foi modificada. Os testes permanecem vermelhos de propósito: não
foram apagados, desabilitados ou convertidos em `xfail` para maquiar as falhas.

## Limites

- A auditoria de produção foi deliberadamente restrita a `motor/curador.py`;
  callers ou camadas externas podem impor controles que esta unidade não impõe.
- `eventos_schema.py` não foi aberto; o drift foi observado apenas pelo retorno
  público de `tipos()`.
- A spec diz “held-out explícito”, mas não define schema de proveniência. O teste
  usa `meta.origem` para tornar treino versus held-out observável; o contrato
  definitivo ainda precisa ser especificado.
- `BaseException` (`SystemExit`, `KeyboardInterrupt`) não foi exigida como erro
  recuperável; o teste cobre `Exception` operacional comum.
- Não foi rodada a suíte completa, type-check ou qualquer teste alheio, conforme
  a restrição da tarefa.
- A CLI escreve no caminho fornecido por `--json` (`motor/curador.py:675-692,
  1121-1122`). Isso é saída explicitamente solicitada, não apply automático, mas
  permite sobrescrever o próprio input se os caminhos coincidirem.

### Onde isto pode dar errado

- A ausência de aplicação automática está provada apenas no arquivo autorizado;
  não prova que um consumidor externo respeite o gate.
- Um runner arbitrário ainda pode produzir efeitos por closures, rede ou disco;
  cópia profunda protege os inputs, mas não transforma callable hostil em sandbox.
- Regras de proveniência, domínio numérico e amostra mínima ainda são parcialmente
  implícitas. Corrigir código sem fechar primeiro esses contratos pode trocar uma
  falsificação por outra ou gerar falsos positivos de auditoria.
- Os testes vermelhos bloqueiam “pronto”; o fragmento é diagnóstico, não aceite
  para ship.
