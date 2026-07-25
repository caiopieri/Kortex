# Experimento: XP/TDD Lite Seguro com IA

Data: 2026-06-26

## Objetivo

Testar um processo mais leve que spec-kit completo, inspirado em XP/TDD, para tarefas pequenas e medias, sem virar vibe coding nem burocracia.

O experimento deve responder:

> Consigo usar IA para entregar fatias pequenas com velocidade, testes reais, CI e baixo erro de direcao, sem precisar gerar spec/plan/tasks formais para tudo?

Este documento e um piloto. Nao altera o `dev-harness` nem o `motor` ainda.

## Tese

Spec-kit completo nao deve ser o padrao universal.

Para muita tarefa, o fluxo ideal pode ser:

```text
intencao curta
-> exemplos concretos
-> teste primeiro
-> implementacao minima
-> refactor pequeno
-> CI
-> mini-review
```

Isso e mais leve, mas ainda seguro se tiver guardrails.

## Quando usar este modo

Use `XP/TDD Lite` quando:

- a tarefa cabe em 1 commit ou PR pequeno;
- a regra de negocio e clara;
- o risco e baixo/medio;
- o feedback por teste e rapido;
- nao exige decisao arquitetural aberta;
- nao toca area critica sem gate adicional.

Nao use sozinho quando tocar:

- auth;
- pagamento;
- multi-tenant;
- permissao;
- dados sensiveis;
- migracao destrutiva;
- infraestrutura;
- compliance/LGPD;
- arquitetura de longo prazo.

Nesses casos, subir para spec-kit ou processo governado.

## Entrada minima

Toda tarefa precisa comecar com este contrato:

```text
Modo: XP/TDD Lite

Objetivo:
  [o comportamento que quero]

Porque:
  [resultado esperado / dor]

Exemplos:
  - dado X, quando Y, entao Z
  - dado A invalido, quando B, entao erro C

Fora de escopo:
  - [...]

Limites:
  - arquivos provaveis a tocar: [...]
  - nao mexer em: [...]

Risco:
  baixo | medio
```

Se nao da para preencher isso em poucos minutos, a tarefa provavelmente precisa de spec maior.

## Fluxo do agente

O agente deve seguir:

```text
1. confirmar entendimento em ate 5 bullets
2. escrever testes de comportamento primeiro
3. rodar testes e confirmar que falham pelo motivo esperado
4. implementar o minimo para passar
5. rodar testes/lint/type-check
6. refatorar so se reduzir complexidade real
7. rodar testes novamente
8. entregar resumo do diff, comandos e riscos
```

Regra:

> Refactor oportunista e proibido. Se nao ajuda a tarefa atual, fica fora.

## Qualidade dos testes

O teste deve validar comportamento, nao implementacao interna.

Checklist minimo:

- [ ] cobre caminho feliz;
- [ ] cobre pelo menos um erro/negativo relevante;
- [ ] falha antes da implementacao;
- [ ] nao depende de detalhes internos desnecessarios;
- [ ] nome do teste descreve comportamento;
- [ ] nao apaga teste existente;
- [ ] se tocar permissao/input externo, inclui teste de acesso negado ou input invalido.

Teste ruim:

```text
verifica que a funcao privada X foi chamada
```

Teste bom:

```text
usuario sem permissao recebe 403 ao acessar pedido de outro usuario
```

## Mini-review obrigatorio

Antes de considerar pronto, revisar:

- arquivos tocados;
- diff total;
- se saiu do escopo;
- se teste cobre comportamento real;
- se existe teste negativo;
- se comando de verificacao rodou;
- se houve refactor sem necessidade;
- se a tarefa deveria ter subido de modo.

Saida esperada do agente:

```text
Resumo:
  [...]

Testes adicionados:
  [...]

Comandos rodados:
  [...]

Arquivos tocados:
  [...]

Fora de escopo respeitado:
  sim/nao

Riscos:
  [...]

Onde isto pode dar errado:
  [...]
```

## Como resolver os riscos do XP/TDD Lite

### Risco: imitar o formato do Akita sem o julgamento dele

Controle:

- entrada minima obrigatoria;
- exemplos concretos antes do codigo;
- limite de arquivos;
- mini-review;
- regra de subida para spec-kit quando tocar area critica;
- checkpoints de arquitetura a cada 3-5 PRs ou quando o diff revelar padrao novo.

### Risco: TDD virar teste superficial

Controle:

- pelo menos um teste negativo;
- teste precisa falhar antes;
- teste deve falar em comportamento;
- revisar nomes dos testes;
- se o teste apenas confirma implementacao interna, reescrever.

### Risco: CI verde sem seguranca

Controle:

- scanner por risco;
- security checklist se tocar input externo, banco, auth, pagamento ou dados pessoais;
- teste de permissao quando houver dado de usuario;
- logs nao podem conter dado sensivel;
- segredo nunca entra no diff.

### Risco: commits pequenos acumularem direcao errada

Controle:

- checkpoint de direcao depois de cada bloco de 3-5 tarefas;
- atualizar mini-ARCHITECTURE.md se surgiu padrao novo;
- revisar duplicacao e acoplamento;
- se aparecer decisao arquitetural, parar e subir para spec/plan.

### Risco: agente satisfazer teste sem entender dominio

Controle:

- exemplos devem vir do usuario ou de regra de negocio real;
- teste negativo obrigatorio;
- revisar se nomes e mensagens fazem sentido para usuario;
- para regra critica, pedir explicacao curta do comportamento antes do codigo.

## Protocolo de piloto

Rodar em um projeto descartavel ou modulo pequeno, nunca direto em producao.

### Duracao

3 a 5 tarefas pequenas.

### Tipos de tarefa para testar

Escolher uma mistura:

1. regra de negocio simples;
2. endpoint/API pequeno;
3. UI com comportamento testavel;
4. bugfix com regressao;
5. pequena refatoracao com teste existente.

Evitar no piloto inicial:

- pagamento;
- auth complexa;
- LGPD;
- multi-tenant;
- migracao destrutiva.

### Metricas

Registrar por tarefa:

- tempo ate primeiro teste;
- tempo ate testes verdes;
- numero de arquivos tocados;
- linhas alteradas;
- bugs encontrados pelo teste;
- vezes que saiu do escopo;
- vezes que precisou subir para spec-kit;
- qualidade subjetiva do diff;
- retrabalho necessario depois.

### Criterio de sucesso

O processo passa no piloto se:

- 80%+ das tarefas terminam com diff pequeno e escopo respeitado;
- toda tarefa tem teste de comportamento;
- toda tarefa tem pelo menos um teste negativo quando aplicavel;
- comandos de verificacao rodam;
- nenhum refactor oportunista grande entra;
- nenhuma tarefa critica foi tratada como leve;
- o tempo total parece menor que spec-kit completo para tarefas equivalentes.

### Criterio de falha

O processo falha se:

- testes sao cosmeticos;
- agente frequentemente sai do escopo;
- mini-review vira burocracia sem pegar erro;
- tarefas medias escondem decisao arquitetural;
- o usuario precisa corrigir muito depois;
- a falta de spec gera retrabalho maior que o tempo economizado.

## Template de prompt

```text
Modo: XP/TDD Lite.

Objetivo:
  [...]

Porque:
  [...]

Exemplos:
  - dado [...], quando [...], entao [...]
  - dado [... invalido], quando [...], entao [...]

Fora de escopo:
  - [...]

Limites:
  - toque preferencialmente: [...]
  - nao mexa em: [...]

Fluxo:
  1. confirme entendimento em ate 5 bullets
  2. escreva testes de comportamento primeiro
  3. rode os testes e confirme falha esperada
  4. implemente o minimo
  5. rode testes/lint/type-check
  6. refatore apenas se reduzir complexidade real
  7. entregue resumo do diff, comandos, riscos e "Onde isto pode dar errado"

Se a tarefa tocar auth, pagamento, multi-tenant, dados sensiveis, LGPD, migracao destrutiva ou arquitetura, pare e recomende subir de modo.
```

## Decisao depois do piloto

Se funcionar, transformar em um modo oficial do `dev-harness`:

```text
T0: spike
T1-XP-Lite: tarefa pequena com teste primeiro
T1-Spec-Lite: issue/spec curta
T2-Spec-Kit: risco alto/producao/compliance
```

Se nao funcionar, manter apenas como tecnica manual para tarefas muito simples.

## Onde isto pode dar errado

O piloto pode ser escolhido facil demais e parecer melhor do que e. Para evitar isso, incluir pelo menos um bugfix real e uma tarefa com input invalido/permissao simples. Outro risco e medir so velocidade; o objetivo e velocidade com menos retrabalho, nao velocidade bruta. Se o processo exigir tanta explicacao que vira spec-kit disfarçado, ele perdeu a razao de existir.
