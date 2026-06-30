# HANDOFF CODEX — Desacoplar `--registro` (rotas+ferramentas) de `--modelos` (cliente)

## Por quê (contexto travado pela arquiteta)
Run real 2026-06-25 (CSV→JSON, modelos-free-escalada.json --auto --escalar): A+B+revisão
funcionaram (3 subagentes aprovados de 1ª, síntese cheia). MAS o gate `cobertura` reprovou por
**inconsistência REAL entre os 3 artefatos** (arquitetura=array simples vs spec=envelope meta+data vs
testes=array; tipagem string vs --strict; escopo inflado; política de linha malformada divergente).
CAUSA: a missão é CADEIA DE DEPENDÊNCIA ("spec baseada na arquitetura; testes contra o design") mas
rodou como `fan_out_sintese` PARALELO → cada subagente inventou seu contrato sem ver o do outro.

O conserto estratégico é PREVENÇÃO: rodar a rota `grafo_dependencias` (já existe; passa `deps_txt` da
etapa de cima pra de baixo → consistente por construção). Essa rota só liga via `--registro`, que HOJE
é mutuamente exclusivo com `--modelos` (os modelos baratos). Os dois eixos — TOPOLOGIA (rotas) e
CLIENTE (modelos) — são ortogonais; o acoplamento é só uma conflação de implementação no CLI.

## Objetivo
Permitir `--registro <dir>` JUNTO com `--modelos <cfg>`: o CLIENTE vem da config de `--modelos`
(roteamento por custo/tier), e o `--registro` passa a servir SÓ para rotas (`rotas_de_registro`) e
ferramentas (`ferramentas_de_registro`). Backward-compat total: cada flag sozinha mantém o
comportamento atual.

## Mudança (cirúrgica, só em `motor/__main__.py`)
Arquivo: `motor/__main__.py`, função `main()`.

1. **Remover o erro de exclusividade mútua** (hoje linhas ~108-110):
   ```python
   if cfg_modelos is not None and dir_registro is not None:
       print("erro: use --registro OU --modelos, não os dois.")
       return 2
   ```
   Apagar esse bloco inteiro.

2. **Gatear a fonte do cliente** no ponto onde `construir_cliente` é chamado (hoje ~linha 194).
   Definir, ANTES da chamada, um booleano que decide se o cliente vem da config (e não do registro):
   ```python
   cliente_por_config = bool(
       cfg_modelos and ("provedores" in cfg_modelos or "base_url" in cfg_modelos)
   )
   ```
   E chamar `construir_cliente` mandando `dir_registro=None` quando o cliente vem da config — assim o
   cliente é o `cliente_de_config` (tier/pins/esgotados), mas `rotas` e `ferramentas` (que já são
   lidas separadamente de `dir_registro` mais acima) continuam valendo:
   ```python
   cliente = construir_cliente(
       cfg_modelos,
       None if cliente_por_config else dir_registro,
       log=log,
   )
   ```
   NÃO alterar a função `construir_cliente` em si (a fronteira programática que levanta
   `ProvedorIndisponivel` fica intacta). NÃO mexer em `rotas` (linha ~122-124) nem em `ferramentas`
   (linha ~188) — elas já dependem só de `dir_registro` e devem seguir carregando quando `--registro`
   é passado, mesmo com `--modelos` presente.

## Por que `cliente_por_config` (e não `cfg_modelos is not None`)
Existe merge de config GLOBAL `~/.motor/pins.json` (`_merge_cfg`) que pode preencher `cfg_modelos` só
com `pins` (sem `provedores`) mesmo quando o usuário passou só `--registro`. Gatear por
`is not None` quebraria o `--registro` sozinho nesse caso. Gatear por presença de
`provedores`/`base_url` preserva: registro sozinho (sem provedores explícitos) → cliente do registro.

## Restrições (inerte onde deve ser)
- `--registro` sozinho: idêntico a hoje (cliente do registro).
- `--modelos` sozinho: idêntico a hoje (cliente da config).
- Não introduzir flag nova. Não tocar em `grafo.py`, `modelos.py`, `registro.py`.
- Não editar testes existentes (só ADICIONAR). Suíte atual = 202 passed deve continuar 202+.

## DoD (critérios de falsificação — todos precisam passar)
1. **Combinado monta cliente da config + rotas do registro**: teste novo que chama `cli.main()` (ou a
   montagem equivalente) com `--registro <dir-de-rotas> --modelos <cfg-com-provedores>` e verifica:
   (a) não retorna 2 / não imprime "use --registro OU --modelos"; (b) o cliente resultante é o de
   config (ex.: `cliente_de_config`/roteador, NÃO `cliente_de_registro`); (c) `rotas` foi carregada
   do registro (catálogo com as rotas esperadas).
2. **Backward-compat**: `--registro` sozinho continua usando o cliente do registro; `--modelos`
   sozinho continua usando o cliente da config (2 testes, ou parametrizado).
3. **Global pins-only não sequestra `--registro` sozinho**: com um `~/.motor/pins.json` simulado
   contendo só `pins` (sem `provedores`), `--registro` sozinho ainda usa o cliente do registro.
   (Se for difícil simular o caminho global no teste, documentar e cobrir ao menos via o booleano
   `cliente_por_config` num teste unitário direto.)
4. Suíte completa verde (`python3 -m pytest -q`), 202+ passed.

## Depois (NÃO faz parte deste handoff — é o run de validação do Caio)
`python3 -m motor "<missão CSV→JSON>" --registro exemplos/registro --modelos exemplos/modelos-free-escalada.json --auto --escalar`
→ o planner deve selecionar a rota de dependência (construcao/grafo_dependencias) e os artefatos
saírem consistentes (gate `cobertura` aprova, ou lacunas deixam de ser "arquitetura/spec/testes
discordam"). Se `exemplos/registro` não tiver as rotas, usar o dir que tem (`exemplos/registro-rotas`).
