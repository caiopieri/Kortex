# Runbook — subir o Kortex em produção

> O que separa o motor de rodar um projeto real, o que já foi resolvido e o que
> ainda depende de decisão. Escrito em 2026-07-28.

## O arranjo de provedores

| papel do motor | provedor | modelo | por quê |
|---|---|---|---|
| `planner` | Anthropic | `claude-sonnet-5` | planeja a ideia inteira |
| `executor` | Google | `gemini-2.5-pro` | produz (padrão) |
| `executor` (alta complexidade) | OpenAI | `gpt-5.6-terra` | assume quando o roteamento evita o Gemini |
| `verifier` | OpenAI | `gpt-5.6-terra` | julga o que o Gemini produziu |
| `verifier` (quando OpenAI executou) | Anthropic | `claude-sonnet-5` | produtor nunca julga a própria obra |
| `evaluator` | Anthropic | `claude-sonnet-5` | revisa a cobertura e aprova ou não |
| `synthesizer` | OpenAI | `gpt-5.6-terra` | fecha |

A preferência é **ordenada** e o motor passa `evitar_provedor`. É isso que faz a
independência produtor↔juiz valer nos dois caminhos, e não só no caso fácil.

## Snapshot de câmbio vencido

Sintoma, agora explícito na saída da CLI:

```
erro: orçamento indisponível: snapshot FX vencido: capturado ha 25.9h,
limite 24.0h (versao awesomeapi-usdbrl-2026-07-29). Recapture a cotacao real
e atualize o bloco `fx` da config -- adiantar so a data mantem o numero velho.
```

O motor recusa arrancar, e está certo: precificar em BRL com câmbio velho torna
o teto ficção. Conserto:

```sh
curl -s "https://economia.awesomeapi.com.br/json/last/USD-BRL"
```

Use o `ask` como `cotacao_venda`, o `timestamp` como `capturado_em`, e a data em
`versao`. **Aproveite para reconferir a tabela de preço dos modelos em uso** —
preço de modelo é perecível, e adiantar só a data mantém números velhos com cara
de novos.

O frescor é conferido duas vezes: na composição (antes de planejar ou gastar) e
a cada chamada (uma run longa pode vencer no meio dela).

## Bloqueio 1 — config de orçamento · RESOLVIDO

`exemplos/cfg-orcada-multi.json`. Uso:

```sh
export GEMINI_API_KEY=... OPENAI_API_KEY=... ANTHROPIC_API_KEY=...
python -m motor --modelos exemplos/cfg-orcada-multi.json "sua missão"
```

A config **escolhe** o arranjo, sem default silencioso: bloco `orcamento_openai`
→ compositor de um provedor; blocos `gemini`/`openai`/`anthropic` → multi.

## Bloqueio 2 — dois provedores certificados · RESOLVIDO

`validar_independencia_orcada` exige `provider(executor) != provider(verifier)`.
O único compositor que existia (`compor_orcamento_openai`) devolvia **uma** rota,
com `openai` cobrindo os dois papéis — ou seja, **nunca passava na própria
validação**. Não era bug dela: era o contrato dizendo que produzir e julgar com o
mesmo provedor não vale.

Resolvido com `compor_orcamento_multi` + dois adaptadores custeados novos
(`gemini_orcado.py`, `anthropic_orcado.py`), espelhando a forma do de OpenAI.

## Bloqueio 3 — validador default-deny · ABERTO, DEPENDE DE DECISÃO

**Nenhum entrypoint de produção compõe `command_runner`** — `__main__.py` e
`servico.py` deixam o default `DenyCommandRunner()`. A vertical de software não
consegue compilar nem testar o próprio output. Os auditores confirmaram que a
fronteira fail-closed é intencional e sólida; ligar um runner é decisão de
segurança, não conserto.

O que existe: `DockerSandboxRunner`, que exige **imagem fixada por digest
sha256**. Pendências para operá-lo:

1. **Docker não está rodando** na máquina (binário presente, daemon fora).
2. **Falta a imagem** com o toolchain (python, pytest, ruff, git) e seu digest.
3. **🟡 aberto que atrapalha:** a allowlist valida o binário no **host**, mas o
   `DockerSandboxRunner` usa esse path como entrypoint **dentro da imagem**. Os
   caminhos precisam existir nos dois lados, ou C2 não é operável como está.

## Preços — dado perecível, e estavam errados

`PRICING_MAX_AGE_S` = 7 dias. Vencido, o motor recusa arrancar. **Isso é desenho:
preço velho é contenção monetária velha.** Renovar exige *reconferir*, não
carimbar a data.

Reconferido em 2026-07-28 contra a fonte de cada provedor:

| provedor | estava | está | efeito |
|---|---|---|---|
| OpenAI | `gpt-5` a $1.25/$10 | `gpt-5.6-terra` a $2.50/$15 | **subfaturava ~4x na entrada, ~3x na saída** |
| Gemini | — | $1.25/$10, cache $0.125 | novo |
| Anthropic | — | $3/$15, cache r/w $0.30/$3.75 | novo |

O achado da OpenAI é sério: o preço fixado era o de **lançamento de agosto/2025**,
e aquela geração de modelo nem existe mais na tabela. O motor subfaturava na
única contenção monetária que tem.

**Sobre o Sonnet 5:** está em promoção de $2/$10 até 2026-08-31, e vai a $3/$15 em
01/09. A tabela usa o preço **pós-promoção**. Superfatura ~50% até agosto e fica
exata depois — errar para cima aperta o teto, errar para baixo furaria a contenção
no dia da virada sem ninguém perceber.

**Limites de faixa:** Gemini e Anthropic cobram mais acima de 200k tokens de
prompt, então `MAX_INPUT_TOKENS` fica **em 200k** nos dois. Elevar esse teto sem
trocar a tabela faz o custo ser subestimado.

## O que ainda não está pronto

- **Bloqueio 3** acima — sem ele o Kortex escreve software mas não o executa.
- **Fase C incompleta:** U-04, U-06 e U-07 (curador) seguem abertos. Consequência
  prática: **o flywheel de auto-melhoria não é confiável ainda.** O Kortex pode
  trabalhar; não deve promover modelo sozinho.
- **Critério 3 do charter aberto:** nada disto foi revisto pelo cadeado
  GPT-5/Codex.

### Onde isto pode dar errado

- **Nenhum dos três adaptadores foi exercitado contra a API real.** Os testes usam
  transporte injetado. O formato de `usage` do Gemini e da Anthropic está
  implementado a partir da documentação, não de resposta observada — o primeiro
  run real pode revelar campo divergente, e o adapter falha fechado (bom), mas
  falha.
- **`gpt-5.6-terra`, `gemini-2.5-pro` e `claude-sonnet-5` não foram chamados**
  para confirmar que os identificadores resolvem. Um id errado derruba no
  primeiro uso.
- **A cotação de câmbio no exemplo é de 2026-07-28 e vale 24h.** Depois disso o
  motor recusa até alguém atualizar `fx`.
- **`teto_bootstrap_brl` está em R$ 5,00** no exemplo — escolha minha, não sua.
  Com a spec do usuário agora confrontada contra o teto (U-02), missão que peça
  mais que isso é **recusada no arranque**.
