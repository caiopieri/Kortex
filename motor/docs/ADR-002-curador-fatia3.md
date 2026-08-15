# ADR-002: Curador Fatia 3 — Sombra, Certificacao e Promocao Gated

## Status
Implementado na fronteira H08/H09. Promoção operacional indisponível sem repositório
autoritativo do deployment.

## Contexto
O curador ja observa logs e propoe ranking read-only por slot/modelo:

- `analisar(...)` carrega runs certificados, agrega qualidade, latencia, resiliencia e custo.
- `_Agregador` produz metricas por papel/tier/modelo.
- `_LedgerCusto` calcula tokens, tempo e custo por modelo/slot/run.
- `propor(...)` gera recomendacoes `status="proposto"` sem alterar catalogo.

Falta a fatia 3: transformar uma proposta em evidencia de promocao sem Goodhart. O curador nao pode
promover apenas porque o candidato e mais barato; ele precisa vencer o titular em qualidade e custo, em
teste de sombra, antes de qualquer aplicacao.

Ha uma restricao pratica importante: os logs JSONL atuais nao carregam prompt, saida completa nem
artefatos suficientes para replay fiel de uma chamada de modelo. Portanto, a primeira versao da sombra
nao deve fingir replay a partir de log bruto. Ela deve consumir casos held-out explicitos, com runner
injetado, e deixar o adaptador "log/artifact replay" para uma fatia posterior quando houver contrato de
evidencia suficiente.

## Decisao
Adicionar ao `motor.curador` uma trilha aditiva, deterministica e testavel:

1. **Sombra read-only**
   - Entrada: proposta de slot/modelo, casos de referencia e runner injetado.
   - O titular vem dos dados do caso; o candidato roda em sombra pelo runner.
   - Nao muda roteamento, catalogo, config ou resultado de uma run real.
   - Emite evento `curador.sombra` via callback/`LogEventos` opcional.

2. **Certificacao**
   - Compara titular vs candidato por taxa de aprovacao e custo medio.
   - Promove somente se o candidato tiver qualidade estritamente maior e custo estritamente menor.
   - Rejeita regressao de qualidade mesmo com custo menor.
   - Recalcula a decisao a partir de evidencia v2 selada; agregados fornecidos pelo chamador
     nao sao autoridade.
   - Emite `curador.certificou` quando passa e `curador.rejeitou` quando falha.

3. **Promocao gated**
   - A aplicacao da mudanca nao acontece dentro do comparador.
   - O curador aceita somente `certification_id` recuperado de `RepositorioCertificacoes`;
     dict, hash ou JSON isolado falham fechado.
   - A promocao vira uma run gated do motor: o curador prepara uma intencao de mudanca com
     evidencia autoritativa, e outra camada executa/aprova a alteracao de catalogo.
   - Evento final esperado: `curador.promoveu` apenas depois do gate.

4. **Formato dos casos**
   - Um caso de sombra e um dict simples, serializavel, com `id`, `slot`, `entrada` e resultado do
     titular (`modelo`, `aprovado`, `custo_usd`).
   - O runner do candidato recebe `(caso, modelo_candidato)` e devolve `aprovado`, `custo_usd`, `saida`
     e `motivo`.
   - Artefatos da CLI sao diagnosticos/read-only e nao ingressam automaticamente no
     repositorio autoritativo.

## Plano de Handoffs

1. **Fatia 3.1 — Shadow runner read-only**
   - Adicionar `rodar_sombra(...)` em `motor.curador`.
   - Usar runner injetado e emitir `curador.sombra`.
   - Testes: agregacao, excecao do runner, nenhum efeito colateral.

2. **Fatia 3.2 — Certificador/comparador**
   - Adicionar `certificar_sombra(...)`.
   - Critério: candidato vence titular em qualidade e custo.
   - Testes: promove quando vence nos dois eixos; rejeita regressao de qualidade mesmo com custo menor.
   - Emitir `curador.certificou` / `curador.rejeitou`.

3. **Fatia 3.3 — Intencao de promocao gated**
   - Adicionar geracao de artefato/intencao de promocao a partir de certificacao aprovada.
   - Nao escrever catalogo diretamente; exigir certificacao recuperada por ID e emitir
     evento pendente com evidencia.

4. **Fatia 3.4 — CLI e docs de operacao**
   - Expor caminho read-only para rodar sombra/certificacao em arquivo JSON.
   - Documentar formato de casos held-out.
   - Atualizar verificacao e runbook.

## Invariantes

- Runs `rascunho` nao entram como evidencia de promocao.
- Custo e qualidade sao dados, nao opiniao.
- Qualidade regressiva veta promocao, mesmo com economia.
- Nenhuma promocao sem evento e evidencia serializavel.
- Nenhuma intencao autoritativa a partir de JSON/CLI; sem repositorio confiavel, promocao e
  default-deny.

## Onde isto pode dar errado

- **Replay falso:** tentar reconstruir prompt/saida de logs incompletos pode gerar sombra ilusoria.
- **Runner generico demais:** se o runner virar mini-orquestrador, duplica o motor e aumenta o risco.
- **Custo incomparavel:** custo `None` nao deve ser tratado como zero; sem custo comparavel, nao certifica.
- **Qualidade frouxa:** taxa de aprovacao herdada de validador fraco promove modelo ruim.
- **Promocao escondida:** aplicar config/catalogo dentro do curador violaria a lei da run gated.
- **Repositorio cenografico:** um fake ou store mutavel prova protocolo, nao autoridade de
  producao. O deployment precisa fornecer imutabilidade, autenticidade e controle de acesso.
