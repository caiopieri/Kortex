# Guia de piloto: primeiro projeto com XP/TDD Lite Seguro

Data: 2026-06-26

## Objetivo

Usar um projeto pequeno para testar se o processo `XP/TDD Lite Seguro` funciona na pratica antes de virar parte oficial do `dev-harness`.

Este guia tem duas partes:

1. Instrucao para voce, como operador do piloto.
2. Prompt para colar no outro Codex/agente.

## Parte 1: instrucao para o operador

### O que criar

Crie um projeto pequeno, simples e testavel.

Sugestoes boas:

- lista de tarefas com status e filtro;
- controle simples de gastos;
- mini CRM de contatos;
- API de notas com tags;
- catalogo simples de produtos sem pagamento.

Evite no primeiro piloto:

- auth real;
- pagamento;
- multi-tenant;
- LGPD pesada;
- upload;
- webhooks;
- infra complexa;
- deploy em producao.

O objetivo nao e fazer um produto ambicioso. O objetivo e testar o processo.

### Stack recomendada para o piloto

Escolha uma stack que voce e o agente consigam testar rapido.

Exemplos:

- Python + FastAPI + pytest;
- Node/TypeScript + Express/Fastify + Vitest;
- Next.js simples + Vitest/Playwright, se quiser UI;
- Rails, se quiser seguir mais perto do estilo XP/TDD do Akita.

Regra: a stack precisa ter teste rapido e comando de verificacao claro.

### Como medir o piloto

Crie um arquivo no projeto:

```text
PILOTO-XP-TDD-LITE.md
```

Registre por tarefa:

```text
Tarefa:
Tempo ate primeiro teste:
Tempo ate teste verde:
Arquivos tocados:
Linhas alteradas:
Testes adicionados:
Comandos rodados:
Saiu do escopo? sim/nao
Precisou subir de modo? sim/nao
Retrabalho necessario:
Observacoes:
```

### Sequencia sugerida de tarefas

Faca 3 a 5 tarefas.

Exemplo para um app de tarefas:

1. Criar tarefa com titulo obrigatorio.
2. Listar tarefas por status.
3. Marcar tarefa como concluida.
4. Corrigir bug: titulo com espacos nao pode ser aceito.
5. Pequena refatoracao mantendo testes verdes.

Cada tarefa deve caber em um diff pequeno.

### Regra de parada

Pare o modo XP/TDD Lite e suba para processo mais pesado se a tarefa tocar:

- auth;
- pagamento;
- permissao;
- multi-tenant;
- dados sensiveis;
- migracao destrutiva;
- arquitetura;
- decisao de stack;
- deploy publico.

### Criterio de sucesso

O piloto foi bom se:

- as tarefas ficaram pequenas;
- o agente escreveu testes antes;
- os testes falharam antes da implementacao;
- houve pelo menos um teste negativo quando aplicavel;
- os comandos de verificacao rodaram;
- o diff nao inflou;
- voce entendeu o que mudou;
- o retrabalho ficou baixo.

### Criterio de falha

O piloto falhou se:

- os testes foram cosmeticos;
- o agente saiu do escopo;
- o agente fez refactor oportunista;
- voce precisou corrigir muita coisa depois;
- explicar a tarefa ficou tao pesado quanto spec-kit;
- o processo mediu velocidade, mas nao reduziu erro.

## Parte 2: prompt para colar no agente

Cole isto no outro Codex no inicio do projeto:

```text
Estamos testando um processo chamado XP/TDD Lite Seguro.

Objetivo do piloto:
Validar se conseguimos entregar tarefas pequenas com IA usando exemplos concretos, teste primeiro, implementacao minima, CI local e mini-review, sem usar spec-kit completo.

Regras globais:
- Nao comece codando sem contrato da tarefa.
- Para cada tarefa, escreva testes de comportamento primeiro.
- Rode os testes e confirme que falham pelo motivo esperado antes da implementacao.
- Implemente o minimo para passar.
- Refatore apenas se reduzir complexidade real da tarefa atual.
- Nao faca refactor oportunista.
- Nao altere escopo sem pedir.
- Nao apague ou desabilite teste sem autorizacao explicita.
- Se tocar auth, pagamento, multi-tenant, permissao, dados sensiveis, LGPD, migracao destrutiva, infraestrutura ou arquitetura, pare e recomende subir para processo mais pesado.
- Toda resposta final deve listar comandos rodados, arquivos tocados, testes adicionados, riscos e "Onde isto pode dar errado".

Fluxo por tarefa:
1. Confirmar entendimento em ate 5 bullets.
2. Identificar se a tarefa cabe em XP/TDD Lite ou deve subir de modo.
3. Escrever testes de comportamento.
4. Rodar testes e verificar falha esperada.
5. Implementar o minimo.
6. Rodar testes/lint/type-check disponiveis.
7. Refatorar apenas se necessario.
8. Rodar verificacoes novamente.
9. Atualizar PILOTO-XP-TDD-LITE.md com metricas da tarefa.
10. Entregar resumo final.

Formato da tarefa que vou te passar:

Modo: XP/TDD Lite

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

Risco:
  baixo | medio

Se qualquer item estiver ambiguo, pergunte antes de codar.
```

## Template de tarefa

Use este template para cada tarefa do piloto:

```text
Modo: XP/TDD Lite

Objetivo:
  [descreva o comportamento pequeno]

Porque:
  [por que isso importa]

Exemplos:
  - dado [...], quando [...], entao [...]
  - dado [... invalido], quando [...], entao [...]

Fora de escopo:
  - [...]

Limites:
  - toque preferencialmente: [...]
  - nao mexa em: [...]

Risco:
  baixo | medio
```

## Exemplo pronto de primeira tarefa

```text
Modo: XP/TDD Lite

Objetivo:
  Permitir criar uma tarefa com titulo obrigatorio.

Porque:
  O app precisa registrar tarefas validas antes de listar ou filtrar.

Exemplos:
  - dado titulo "Comprar leite", quando criar tarefa, entao a tarefa e salva com status "pendente"
  - dado titulo vazio ou so espacos, quando criar tarefa, entao retorna erro de validacao

Fora de escopo:
  - login
  - banco real
  - UI
  - edicao de tarefa
  - exclusao de tarefa

Limites:
  - toque preferencialmente no modulo de dominio e nos testes
  - nao mexa em configuracao de deploy

Risco:
  baixo
```

## Como avaliar depois

Depois de 3 a 5 tarefas, responda:

- O processo foi mais rapido que spec-kit completo?
- Os testes pegaram erro real?
- O agente saiu do escopo?
- O mini-review pegou algo util?
- O arquivo `PILOTO-XP-TDD-LITE.md` ajudou ou virou burocracia?
- Que tipo de tarefa precisou subir de modo?
- Voce confiaria nesse processo para T1 comum?

Se a resposta for boa, o proximo passo e adaptar isto para `dev-harness` como modo experimental.

## Onde isto pode dar errado

O piloto pode ser facil demais e dar falsa confianca. Inclua pelo menos uma tarefa com input invalido e um bugfix real. Tambem pode virar burocracia se voce preencher detalhes demais; mantenha o contrato curto. O agente pode escrever teste superficial, entao olhe se o teste valida comportamento observavel e se falhou antes da implementacao.
