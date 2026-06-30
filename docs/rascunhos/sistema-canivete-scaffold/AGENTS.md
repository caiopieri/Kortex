# AGENTS.md — sistema-canivete

## Objetivo do projeto

Este projeto e um piloto para validar um processo de desenvolvimento com IA chamado **Projeto Publicavel com XP/TDD Lite**.

O objetivo nao e apenas gerar codigo funcionando. O objetivo e criar um projeto pequeno que uma pessoa externa conseguiria entender, instalar, testar, contribuir e confiar minimamente.

## Processo obrigatorio

Antes de codar, o agente deve produzir uma proposta curta com:

1. problema que resolve;
2. usuario-alvo;
3. exemplo de uso;
4. superficie de instalacao desejada;
5. stack sugerida, com justificativa curta;
6. fora de escopo;
7. primeira fatia XP/TDD.

Depois disso, trabalhar em ciclos pequenos:

```text
exemplo concreto
-> teste primeiro
-> falha esperada
-> implementacao minima
-> verificacoes
-> mini-review
```

## Regras globais

- Nao comece codando sem contrato da tarefa.
- Nao faca spec-kit completo neste piloto.
- Nao faca refactor oportunista.
- Nao altere escopo sem pedir.
- Nao apague ou desabilite teste sem autorizacao explicita.
- README deve explicar primeiro o problema e o uso, nao a stack.
- Comandos importantes devem virar scripts padronizados quando a stack for escolhida.
- Se a tarefa tocar auth, pagamento, multi-tenant, permissao, dados sensiveis, LGPD, migracao destrutiva, infraestrutura publica ou arquitetura relevante, pare e recomende subir de modo.

## Definition of Done por tarefa

- [ ] Teste de comportamento escrito antes da implementacao.
- [ ] Teste falhou pelo motivo esperado antes da implementacao.
- [ ] Implementacao minima para passar.
- [ ] Pelo menos um teste negativo quando aplicavel.
- [ ] Verificacoes disponiveis rodadas.
- [ ] Diff pequeno e dentro do escopo.
- [ ] `PILOTO-XP-TDD-LITE.md` atualizado.
- [ ] Resumo final com comandos, arquivos, riscos e "Onde isto pode dar errado".

## Formato de resposta final do agente

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

## Onde isto pode dar errado

O piloto pode virar projeto grande demais. Mantenha pequeno. Tambem pode virar codigo funcionando sem superficie de projeto real. Instalar, testar, entender e contribuir importam tanto quanto a funcionalidade inicial.

