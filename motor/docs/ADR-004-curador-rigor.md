# ADR-004: Rigor da Certificação de Sombra (U-04, U-06b, U-07)

## Status
Aprovado e implementado em 2026-07-29. Fecha os três achados do curador que
bloqueavam o flywheel. Decisão delegada pelo fundador ("resolve o curador e o u4
e u6 e u7"), então o raciocínio e o preço de cada escolha ficam registrados aqui.

## Contexto
O ADR-003 fechou a **autoridade** da promoção: o curador não aplica catálogo, só
gera intenção gateada. Isso protege contra o curador agir sozinho — mas não
protege contra ele estar **errado**. A auditoria dupla achou três buracos, e os
três produzem o mesmo desfecho: uma certificação que parece rigorosa e cujo
resultado reescreve o catálogo de modelos do motor.

| Achado | O buraco |
|---|---|
| U-04 | `rodar_sombra` executava só o candidato. O desempenho do titular vinha de `caso["titular"]`, um dict do chamador. |
| U-06b | `evidencia_sha256` era sha256 público: qualquer um recomputava o hash do próprio invento. |
| U-07 | `min_casos` era autodeclarado pelo proponente, checado apenas contra `>= 1`. Um auditor certificou troca de modelo com **n=1**. |

Compostos, eram piores que a soma: quem montava o arquivo escolhia os dois lados
do placar, selava o resultado e declarava que uma amostra de tamanho 1 bastava.

## Decisão

### U-04 — os dois lados são medidos
`rodar_sombra` executa titular **e** candidato pelo mesmo runner, sobre os mesmos
casos, na mesma rodada. Resultado de titular declarado no arquivo é ignorado.

**Preço: a sombra custa o dobro de chamadas.** Aceito. Assinatura é custo fixo
mensal e teto é freio de disparada, não orçamento apertado — e a alternativa é
uma comparação que mede a honestidade de quem escreveu o arquivo.

**Efeito colateral que virou o principal ganho:** rodar os dois nos mesmos casos
torna o desenho **pareado**, e é isso que autoriza o teste de U-07. U-04 e U-07
se resolveram um ao outro.

### U-06b — selo é MAC com chave
`evidencia_sha256` → `evidencia_mac`, HMAC-SHA256. O nome mudou de propósito:
mantê-lo faria evidência v2 antiga ser lida como MAC válido. A chave vem de um
arquivo apontado por `KORTEX_CURADOR_CHAVE` — o caminho na variável, nunca a
chave, porque ambiente vaza em `ps`, dump de crash e log de subprocesso. Arquivo
legível por grupo/outros, ou com menos de 32 bytes, é recusado como inexistente.
Sem chave, nada certifica.

**Onde este fix é honesto e onde não é.** Ele contém evidência que chega **de
fora**: outra máquina, diretório de runs compartilhado, arquivo que um modelo
escreveu. Esse é o caminho real do flywheel e era o que passava. Ele **não**
contém quem já executa como o dono da máquina — essa pessoa lê a chave. Fechar
isso exigiria separar o processo que produz evidência do que a assina, e essa
separação não existe hoje. Registrado aqui para não ser vendido como mais do que
é: HMAC autentica origem no transporte, não contra o dono da máquina.

### U-07 — piso de amostra no código + significância
Duas mudanças, porque uma sem a outra não resolve:

1. **`PISO_CASOS = 30`, no código.** Exigir amostra maior *na política* seria
   inútil: a política é escrita pelo proponente. O rigor não pode ser um campo
   que o interessado preenche.
2. **McNemar exato unilateral, `ALFA = 0.05`**, no lugar do `>` estrito entre
   proporções arredondadas. Exato (binomial), não a aproximação qui-quadrado:
   com poucas discordâncias a aproximação mente para o lado otimista, e é
   exatamente nesse regime — sombra pequena, cara de rodar — que este teste vive.

Consequência deliberada: **com menos de 5 discordâncias, nenhum placar certifica,
nem o perfeito.** 4 a 0 sai de moeda honesta uma vez a cada 16. Isso não é uma
limitação a contornar; é a resposta certa, e está fixada em teste para não
"melhorar" por acidente.

**Custo continua `<` estrito**, sem teste. Os eixos são diferentes: qualidade é
proporção medida em amostra pequena; custo por caso vem de tabela de preço por
token e é determinista.

## Consequências
- 5 reprodutores de auditoria viraram verdes; nenhum teste foi apagado ou
  silenciado. Onde o contrato mudou, o teste foi reescrito para o contrato novo
  com o porquê no lugar.
- `tests/test_curador_rigor.py` fixa os dois desfechos de cada portão — aprovar
  e reprovar — porque um portão que aprova tudo é indistinguível de um que
  funciona quando o normal é aprovar.
- **Nenhuma certificação existente sobrevive:** todas usam o campo antigo e
  amostras abaixo do piso. Isso é intencional; nenhuma delas foi produzida sob
  condições que mereçam confiança.
- O flywheel destrava tecnicamente, mas fica **mais caro e mais lento** de
  alimentar: 30 casos held-out por proposta, com os dois modelos rodando todos.
  Essa é a troca aceita — dado ruim treinando o catálogo é pior que catálogo
  parado.

### Onde isto pode dar errado
- **O piso de 30 é um número escolhido, não derivado.** É o menor n em que o
  teste distingue sinal de moeda com folga e ainda cabe numa rodada pagável. Para
  slots de baixa variância pode ser desperdício; para slots com muitos empates
  (poucas discordâncias) pode ser insuficiente na prática, porque a amostra passa
  no piso e mesmo assim nunca acumula discordância bastante para certificar. O
  sintoma será "nada certifica nunca", que é seguro mas frustrante — e o conserto
  certo aí é amostrar casos mais discriminativos, não baixar o piso.
- **McNemar pareado assume que o mesmo caso é comparável entre os dois modelos.**
  Se o runner tiver estado (cache, rate limit, ordem), o segundo modelo a rodar
  pode ser sistematicamente favorecido ou prejudicado. Hoje o titular sempre roda
  primeiro. Não há aleatorização de ordem, e isso é dívida conhecida.
- **A significância é sobre a amostra, não sobre a produção.** `held-out`
  continua sendo em boa parte declarativo (achado 🟡 ainda aberto): o teste prova
  que o candidato é melhor *nesses casos*, e a garantia de que esses casos
  representam a produção continua vindo de quem os montou.
- **HMAC pode dar falsa sensação de segurança.** Ver a seção de U-06b: contra o
  dono da máquina ele não vale nada. O risco real é alguém ler "evidência
  autenticada" e parar de desconfiar.
- **A chave é um novo modo de falha operacional.** Perder o arquivo invalida toda
  evidência selada com ela — sem rotação, sem key id no selo. Para um sistema de
  uma máquina isso é aceitável; se a evidência passar a ser compartilhada entre
  máquinas, faltará versionamento de chave e a migração vai doer.
