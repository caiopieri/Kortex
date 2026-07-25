# Guia de piloto: projeto publicavel com XP/TDD Lite

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

## Modos dentro do piloto

### Produto/README

Antes do codigo:

```text
problema
usuario
caso de uso
comando de instalacao ideal
exemplo de uso
fora de escopo
```

### XP/TDD Lite

Para cada comportamento:

```text
exemplo concreto
-> teste primeiro
-> implementacao minima
-> refactor pequeno
-> CI/local checks
-> mini-review
```

### OSS Hardening

Depois que a funcionalidade minima existe:

```text
README
-> instalacao
-> CI
-> docs
-> release/deploy minimo
-> revisao LLM adversarial
```

## Definition of Done do piloto

- `README.md` explica problema, instalacao, uso e exemplos.
- `docs/ARCHITECTURE.md` curto existe.
- Teste automatizado existe.
- CI existe ou esta explicitamente planejado se ainda nao houver remote.
- Comando unico para testar localmente.
- Comando unico para rodar localmente.
- Nenhum segredo real no repo.
- Script `bin/test` ou equivalente.
- Script `bin/run` ou equivalente.

## Onde isto pode dar errado

O risco e tentar fazer produto grande demais e perder o aprendizado do processo. Primeiro README curto + script/teste minimo; depois comportamento central; so entao hardening de instalacao, docs e release.

