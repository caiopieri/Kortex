# Guia de piloto: projeto publicavel com XP/TDD Lite

Data: 2026-06-26

## Objetivo

Testar um piloto mais ambicioso, inspirado no fluxo XP/TDD e nas boas praticas minimas de projeto aberto com LLM.

Este piloto nao e "fazer uma API de exemplo". E criar um projeto pequeno que uma pessoa externa conseguiria:

- entender;
- instalar;
- testar;
- contribuir;
- confiar minimamente.

Base conceitual:

- XP/TDD para construir em ciclos curtos;
- instalacao facil como superficie principal;
- CI automatizado como chao comum;
- documentacao orientada ao problema;
- release/deploy padronizado quando fizer sentido.

## Regra central

Codigo funcionando nao basta.

O projeto so conta como piloto valido se tiver:

```text
1. superficie de instalacao simples
2. testes + CI automatizado
3. README claro sobre o problema que resolve
4. docs/ com decisoes tecnicas basicas
5. comandos padronizados para agente rodar sem adivinhar
```

## Escopo recomendado

Escolha algo mais legal que uma TODO list, mas ainda pequeno.

Boas ideias:

- CLI que organiza arquivos por regras;
- CLI que analisa logs e gera resumo;
- mini servidor local para notas Markdown;
- ferramenta de auditoria de README/estrutura de repos;
- app web local para controlar gastos simples;
- MCP pequeno para buscar/anotar informacoes locais;
- gerador de changelog a partir de commits;
- dashboard local de tarefas em SQLite.

Evite no primeiro piloto:

- usuarios reais;
- auth real;
- pagamento;
- multi-tenant;
- dados pessoais sensiveis;
- deploy publico com dominio real;
- stack que voce nao consegue debugar.

## Definicao de pronto do piloto

O piloto termina quando existir:

- `README.md` com problema resolvido, instalacao, uso e exemplos;
- `docs/ARCHITECTURE.md` curto;
- `docs/DECISIONS.md` ou `docs/adr/` com decisoes relevantes;
- teste automatizado;
- CI no GitHub Actions ou equivalente;
- comando unico para testar localmente;
- comando unico para rodar localmente;
- `.env.example` se houver config;
- nenhum segredo real no repo;
- `CHANGELOG.md` se houver versao/release;
- script `bin/test` ou equivalente;
- script `bin/run` ou equivalente;
- script `bin/release` ou plano de release, se fizer sentido.

Para CLI/binario:

- instalacao por pelo menos um caminho simples;
- artefato de release ou plano claro de como gerar;
- checksums se gerar binarios.

Para web app local:

- `bin/setup`;
- `bin/dev`;
- `bin/test`;
- Docker opcional, se simplificar.

## Modos dentro do piloto

### Modo Produto/README

Antes do codigo:

```text
problema
usuario
caso de uso
comando de instalacao ideal
exemplo de uso
fora de escopo
```

Se nao da para explicar o projeto em uma frase, nao comece.

### Modo XP/TDD Lite

Para cada comportamento:

```text
exemplo concreto
-> teste primeiro
-> implementacao minima
-> refactor pequeno
-> CI/local checks
-> mini-review
```

### Modo OSS Hardening

Depois que a funcionalidade minima existe:

```text
README
-> instalacao
-> CI
-> docs
-> release/deploy
-> revisao LLM adversarial
```

## Prompt inicial para colar no agente

```text
Estamos testando um piloto chamado "Projeto Publicavel com XP/TDD Lite".

Objetivo:
Criar um projeto pequeno, mas com padrao minimo de projeto aberto real: instalacao simples, testes, CI, README orientado ao problema, docs tecnicas curtas e comandos padronizados.

Regras:
- Nao comece pela stack. Comece pelo problema e caso de uso.
- Antes de codar, produza uma proposta curta com:
  1. problema que resolve
  2. usuario-alvo
  3. exemplo de uso
  4. superficie de instalacao desejada
  5. fora de escopo
- Depois disso, trabalhe em XP/TDD Lite:
  1. teste de comportamento primeiro
  2. falha esperada
  3. implementacao minima
  4. verificacoes
  5. mini-review
- Nao faca spec-kit completo.
- Nao faca refactor oportunista.
- Nao adicione auth, pagamento, multi-tenant, dados sensiveis ou deploy publico.
- Todo comando importante deve virar script padronizado: bin/setup, bin/run, bin/test, bin/release quando fizer sentido.
- O README deve explicar primeiro o problema e o uso, nao a stack.
- CI deve rodar testes, lint/format quando aplicavel e scanner de dependencia quando disponivel.
- Se algo ficar grande demais, pare e recomende quebrar em tarefas.

Ao final de cada tarefa, entregue:
- resumo do diff;
- testes adicionados;
- comandos rodados;
- arquivos tocados;
- riscos;
- Onde isto pode dar errado.
```

## Primeira conversa com o agente

Use algo assim:

```text
Quero criar um projeto piloto publicavel, mas pequeno.

Ideia:
  [descreva sua ideia em 2-5 linhas]

Quero seguir o modo Projeto Publicavel com XP/TDD Lite.

Antes de codar, me devolva:
1. problema que isso resolve;
2. usuario-alvo;
3. exemplo de uso;
4. instalacao ideal em um comando;
5. stack sugerida, com justificativa curta;
6. fora de escopo;
7. primeira fatia XP/TDD.
```

## Tarefas sugeridas para um piloto OSS

### Tarefa 0: esqueleto publicavel

Objetivo:

- criar estrutura inicial;
- README inicial;
- scripts `bin/setup`, `bin/run`, `bin/test`;
- teste inicial simples;
- CI inicial.

Nao precisa implementar tudo ainda.

### Tarefa 1: comportamento central

Implementar o primeiro caso de uso real com teste primeiro.

Exemplo:

```text
dado um arquivo de log pequeno,
quando rodar o comando summarize,
entao exibe total de linhas, erros e warnings.
```

### Tarefa 2: caso negativo

Exemplo:

```text
dado caminho inexistente,
quando rodar o comando,
entao retorna erro claro e exit code diferente de zero.
```

### Tarefa 3: docs e UX de instalacao

- melhorar README;
- adicionar exemplos;
- documentar arquitetura;
- garantir que um usuario novo roda em poucos comandos.

### Tarefa 4: release/deploy minimo

Para CLI:

- versionamento;
- changelog;
- artefato local;
- plano de release por tag.

Para web/local app:

- script de build;
- Docker opcional;
- `.env.example`;
- instrucoes de deploy local simples.

## Checklist de avaliacao

Ao final, responda:

- Um estranho entenderia o problema pelo README?
- Da para instalar/rodar com um comando ou poucos comandos?
- Os testes cobrem o comportamento central?
- Existe teste negativo?
- O CI cria um chao comum?
- O agente conseguiu rodar scripts sem adivinhar comando?
- A documentacao tecnica explica o suficiente para contribuir?
- O projeto parece publicavel ou so "codigo que funciona"?

## Onde isto pode dar errado

O risco e tentar fazer um produto grande demais e perder o aprendizado do processo. Outro risco e gastar tempo demais em embalagem antes de validar o comportamento central. Resolva assim: primeiro README curto + script/teste/CI minimo; depois comportamento central; so entao hardening de instalacao, docs e release. O objetivo e projeto publicavel minimo, nao ecossistema completo no primeiro dia.
