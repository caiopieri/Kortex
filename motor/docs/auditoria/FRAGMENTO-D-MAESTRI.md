# Fragmento D — auditoria independente C1–C4

## Registro pré-teste do julgamento independente

> Registro feito em 2026-07-10 depois das consultas ao grafo e da leitura integral
> de `docs/INVARIANTES.md`, `motor/grafo.py` e `motor/registro.py`, e antes de abrir
> qualquer teste ou relatório de outro auditor.

### Veredito preliminar

| Critério | Veredito defensivo | Fundamento independente |
|---|---|---|
| C1 | **REPROVADO** | A allowlist é opcional e fail-open; quando existe, compara apenas o basename fornecido, não a identidade nem o caminho canônico do executável. |
| C2 | **PARCIAL** | O validador passa literalmente `cwd=workspace`, mas `cwd` não é sandbox: caminhos absolutos/`..`, ambiente e `PATH` continuam herdados, e a origem do workspace não é confinada aqui. |
| C3 | **REPROVADO defensivamente** | O timeout do filho direto retorna motivo determinístico, mas não cria nem encerra um grupo de processos; descendentes podem sobreviver. A captura integral de stdout/stderr também deixa o motor sem limite de memória. |
| C4 | **REPROVADO** | `shell=False` e split antes da interpolação impedem que espaços, aspas, `;`, `&&` ou newline criem novos argumentos/comandos, mas não impedem injeção de opções, escolha de executável por placeholder, acesso a caminhos fora do workspace nem erros do mini-language de `format_map`. |

### Achados preliminares por severidade

#### Alta

1. **C1 — allowlist não autentica o executável e pode ser omitida.**
   `motor/grafo.py:351-355` reduz entradas autorizadas a `Path(...).name` e
   `motor/grafo.py:611-625` compara o mesmo basename, testa `shutil.which`, mas
   executa depois o token original. Um caminho absoluto, symlink ou resolução por
   `PATH` com o mesmo nome passa sem estar preso ao arquivo autorizado. Com
   `None`/`[]`, o teste condicional da linha 612 não roda e qualquer executável
   encontrado é aceito.

2. **C2 — diretório de trabalho não é confinamento.**
   `motor/grafo.py:360-361` deriva o workspace de `run_id` sem validar nesta
   fronteira traversal, caminho absoluto ou symlink; `motor/grafo.py:759-763`
   cria o diretório e o fornece como `cwd`. `motor/grafo.py:627-634` não restringe
   filesystem, não troca usuário e herda o ambiente e o `PATH`. O processo pode
   ler/escrever fora do workspace. Além disso, ferramentas chamam a mesma função
   sem `cwd` em `motor/grafo.py:656-674`.

3. **C3 — timeout não cobre a árvore de processos.**
   `motor/grafo.py:627-643` usa `subprocess.run(timeout=...)` sem nova sessão ou
   grupo e trata apenas `TimeoutExpired` do filho direto. Não há encerramento dos
   descendentes; efeitos colaterais podem ocorrer depois de o motor reportar
   timeout.

4. **C3/C4 — stdout e stderr são ilimitados.**
   `motor/grafo.py:627-645` usa `capture_output=True` e concatena toda a saída sem
   teto, streaming ou truncamento. Um comando autorizado pode exaurir memória
   antes de o timeout proteger o motor.

#### Média

5. **C4 — isolamento de argv não é política de argumentos.**
   `motor/grafo.py:600-608` preserva cada expansão como um único argumento, o que
   bloqueia word splitting e shell metacharacters, mas aceita valores iniciados
   por `-`/`--` sem inserir `--` nem validar por posição. Em utilitários e
   interpretadores permitidos, um operando controlado pode virar opção e mudar
   completamente a operação.

6. **C1 — o Registry pode ampliar a lista a partir de qualquer entidade.**
   `motor/registro.py:192-204` coleta `ferramentas_permitidas` de todo `*.md`, sem
   filtrar `tipo`, canonicalizar caminho ou rejeitar arquivo symlink. Isso amplia
   a base de confiança e torna a proveniência da permissão indistinguível.

#### Baixa

7. **C4 — falhas de formatação não são totalmente normalizadas.**
   `motor/grafo.py:604-608` captura apenas `KeyError`; templates com chaves
   desbalanceadas ou formatos inválidos podem levantar `ValueError` e escapar do
   resultado determinístico do validador.

### Controles que de fato existem

- `subprocess.run` recebe lista e não recebe `shell=True` (`motor/grafo.py:600-606`,
  `motor/grafo.py:627-634`): metacaracteres vindos de valores não abrem um shell.
- Placeholder ausente vira reprovação estruturada (`motor/grafo.py:604-608`).
- Lista vazia de argv é rejeitada (`motor/grafo.py:609-610`).
- O timeout do processo direto vira `erro="timeout"` e motivo fixo
  (`motor/grafo.py:642-643`).
- O validador de comando fornece literalmente o workspace como `cwd`
  (`motor/grafo.py:759-763`).

### Limite do grafo

As quatro consultas `graphify query "C1"` até `"C4"` encerraram com código zero,
mas retornaram `No matching nodes found.`. Nenhuma conclusão acima dependeu do
grafo.

## Veredito final após a validação independente dos testes

| Critério | Veredito final | Evidência decisiva |
|---|---|---|
| C1 | **REPROVADO** | Os três caminhos para um binário malicioso de mesmo basename — `PATH`, absoluto e symlink — foram executados apesar da allowlist apontar para outro arquivo (`tests/test_auditoria_gpt5_d.py:53-78`). A ausência de lista também executou, confirmando o default fail-open (`tests/test_auditoria_gpt5_d.py:81-91`). |
| C2 | **PARCIAL** | A chamada usa `cwd=workspace` (`motor/grafo.py:759-763`), portanto a parte literal passa. Não existe, porém, isolamento: caminho absoluto e traversal leram arquivo externo (`tests/test_auditoria_gpt5_d.py:94-108`) e o filho recebeu segredo do ambiente (`tests/test_auditoria_gpt5_d.py:111-122`). |
| C3 | **REPROVADO defensivamente** | O timeout direto reprovou com o motivo determinístico esperado, mas o descendente escreveu após a reprovação (`tests/test_auditoria_gpt5_d.py:133-156`). Configurações malformadas escaparam como exceção (`tests/test_auditoria_gpt5_d.py:125-130`) e 512.000 bytes de stdout foram preservados integralmente (`tests/test_auditoria_gpt5_d.py:159-170`). |
| C4 | **REPROVADO** | O placeholder `-c` mudou a semântica do Python permitido e executou código (`tests/test_auditoria_gpt5_d.py:173-182`). Em contraste, cinco casos com espaço, aspas, `;`, `&&` e newline passaram como um único argv, sem criar marcador (`tests/test_auditoria_gpt5_d.py:185-202`); logo a quebra é option/argument injection, não shell injection. |

## Correlação entre produção e testes

### C1 — allowlist

- **Produção:** `motor/grafo.py:351-355` perde identidade/caminho ao transformar
  cada entrada em basename. `motor/grafo.py:611-625` compara somente esse nome,
  consulta `shutil.which(partes[0])`, mas entrega `partes[0]` — ainda não fixado —
  ao subprocesso. O `if executaveis_permitidos` da linha 612 torna `None` e `[]`
  equivalentes a nenhuma checagem. `motor/registro.py:192-204` agrega permissões
  de qualquer arquivo `*.md` e não rejeita symlink.
- **Teste de identidade:** `tests/test_auditoria_gpt5_d.py:53-78` usa dois
  executáveis diferentes com nome `audit-runner`; o autorizado é confiável e o
  candidato malicioso chega por `PATH`, caminho absoluto ou symlink. Os três
  casos aprovaram e executaram o candidato.
- **Teste de ausência:** `tests/test_auditoria_gpt5_d.py:81-91` prova que `None`
  executa um binário arbitrário. Este é um requisito de fail-closed defensivo,
  mais forte que a redação estritamente condicional de C1; C1 já está reprovado,
  independentemente dele, pelos três bypasses com allowlist configurada.

### C2 — cwd versus isolamento

- **Produção:** `motor/grafo.py:759-763` comprova o `cwd` literal. Entretanto,
  `motor/grafo.py:627-634` não fornece `env`, sandbox, namespace, usuário restrito
  ou política de filesystem. `motor/grafo.py:360-361` também não confina aqui o
  `run_id`/workspace por caminho canônico. A variante de ferramenta nem sequer
  passa `cwd` (`motor/grafo.py:656-674`).
- **Teste de filesystem:** `tests/test_auditoria_gpt5_d.py:94-108` leu o mesmo
  segredo por caminho absoluto e por `..`, em ambos os casos com retorno zero e
  resultado aprovado.
- **Teste de ambiente:** `tests/test_auditoria_gpt5_d.py:111-122` recebeu e
  imprimiu `AUDITORIA_SEGREDO` herdado do processo host.
- **Leitura correta:** esses testes não negam que o diretório corrente seja o
  workspace; provam que chamar esse workspace de “isolado” excede o controle
  implementado.

### C3 — timeout, descendentes e recursos

- **Produção:** `motor/grafo.py:627-643` limita somente o `subprocess.run` direto,
  sem nova sessão/process group e sem kill da árvore. `motor/grafo.py:627-645`
  captura stdout/stderr integralmente. As conversões de timeout em
  `motor/grafo.py:673` e `motor/grafo.py:760` não normalizam `TypeError` ou
  `ValueError` nesta fronteira.
- **Teste de configuração:** `tests/test_auditoria_gpt5_d.py:125-130` obteve
  `TypeError` para `None`/lista e `ValueError` para `"0.25"`, em vez de resultado
  reprovado. É evidência do nó executor; sua admissibilidade pela spec não foi
  afirmada, pois esse teste invoca o nó diretamente.
- **Teste de árvore:** em `tests/test_auditoria_gpt5_d.py:133-156`, as asserções
  de reprovação e motivo determinístico passaram, mas o neto gravou
  `filho-sobreviveu` depois do timeout.
- **Teste de volume:** `tests/test_auditoria_gpt5_d.py:159-170` gerou 512.000
  bytes; os 512.000 reapareceram na evidência, sem truncamento.

### C4 — placeholders, metacaracteres e opções

- **Produção:** `motor/grafo.py:600-608` divide o template antes de interpolar e
  mantém cada expansão em um único elemento da lista. Isso é um controle real
  contra word splitting e shell metacharacters. Não existe, porém, schema de argv
  por posição, separador `--` ou proibição de placeholder no executável/opções.
- **Teste de opção:** `tests/test_auditoria_gpt5_d.py:173-182` injeta `-c` numa
  posição tratada como dado; o Python passa a interpretar o próximo argumento
  como código, cria o marcador e termina com sucesso.
- **Controles negativos:** os cinco casos em
  `tests/test_auditoria_gpt5_d.py:185-202` passaram e reproduziram cada valor
  exatamente em um argv. Portanto não há base para reportar execução de `;` ou
  `&&` por shell.

## Comandos e resultados

| Comando (cwd `motor`) | Resultado |
|---|---|
| `graphify query "C1"` (idem C2, C3 e C4) | Quatro execuções com exit 0; todas: `No matching nodes found.` |
| `uv run pytest -q --tb=short tests/test_auditoria_gpt5_d.py` | Exit 1 antes da coleta: resolução impossível porque o projeto aceita Python 3.10 e `langgraph-api==0.10.0` exige Python >=3.11. |
| `.venv/bin/pytest -q --tb=short tests/test_auditoria_gpt5_d.py` | Exit 2 na coleta: `ModuleNotFoundError: No module named 'langgraph'`. |
| `pytest -q --tb=short tests/test_auditoria_gpt5_d.py` | Exit 1; **13 failed, 5 passed, 1 warning in 4.41s**. Os cinco passes são as variantes de metacaracteres; as 13 falhas correspondem aos achados acima. Ambiente global Python 3.14 emitiu aviso de compatibilidade Pydantic V1. |
| `uv run ruff check tests/test_auditoria_gpt5_d.py` | Não iniciou o lint pela mesma falha de resolução do `uv`. |
| `ruff check tests/test_auditoria_gpt5_d.py` | Exit 0: `All checks passed!` |

## Escopo e limites

- Foram lidos integralmente apenas `docs/INVARIANTES.md`, `motor/grafo.py`,
  `motor/registro.py` e, depois do registro pré-teste acima,
  `tests/test_auditoria_gpt5_d.py`.
- Nenhum outro arquivo de produção ou teste e nenhum relatório/fragmento de
  auditor anterior foi aberto. Produção e testes alheios não foram modificados.
- O teste chama diretamente o nó compilado `subagente` para isolar a fronteira.
  Isso prova o comportamento de `executar_validador`, mas não prova que todos os
  formatos inválidos de timeout atravessam `WorkflowSpec.model_validate`.
- O teste de 512.000 bytes demonstra ausência de truncamento nesse volume; a
  inexistência de qualquer limite é também evidência estática de
  `motor/grafo.py:627-645`, não uma tentativa de exaurir memória de verdade.
- O teste de descendentes prova efeito colateral pós-timeout no macOS/POSIX; não
  mede hang indefinido nem comportamento específico do Windows.
- Não foi executada a suíte geral, type-check ou revisão de outros módulos, por
  restrição explícita de escopo. As falhas vermelhas são testes adversariais de
  segurança deliberadamente não corrigidos em produção.

### Onde isto pode dar errado

- A ameaça real depende de quem controla a WorkflowSpec, o Registry, o template
  e os arquivos executáveis. O recorte permitido não estabelece essas ACLs; se
  todos forem conteúdo imutável e confiável, a explorabilidade cai, embora os
  bypasses continuem presentes.
- Fixar apenas `resolve()` ainda teria TOCTOU/symlink swap; fixar basename ainda
  deixaria `PATH` vulnerável; e permitir interpretadores genéricos (`python`,
  `sh`, equivalentes) continuaria oferecendo execução arbitrária por argumentos.
- Trocar `cwd` por validação de caminhos não cria sandbox. Confinamento exige uma
  fronteira de processo/FS/ambiente coerente com o `docs/security-DoD.md`, que não
  foi aberto nesta auditoria por proibição de ler outros documentos.
- Encerrar process group pode matar processos compartilhados se a sessão não for
  criada e identificada pelo próprio motor. Limitar saída exige também drenar os
  pipes sem deadlock e preservar diagnóstico suficiente.
- Os resultados funcionais vieram do Python global 3.14, não do ambiente
  declarado do projeto; a falha de resolução do `uv` deve ser corrigida antes de
  transformar esta matriz em gate regular de CI.
