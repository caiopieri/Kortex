# ADR-003: Curador v1 Promove Intenção, Não Aplica Catálogo

## Status
Aprovado para v1; hardening H09 aplicado. Promoção operacional permanece default-deny
enquanto o deployment não fornecer `RepositorioCertificacoes` autoritativo.

## Contexto
O Alvo 2 fechou a fatia 3 do curador:

- `rodar_sombra(...)` compara titular e candidato em casos held-out, sem alterar run real.
- `certificar_sombra(...)` aplica o guard anti-Goodhart.
- `preparar_promocao_gated(...)` só gera intenção a partir de certificação recuperada por
  `certification_id` de um `RepositorioCertificacoes`.
- CLI e artefatos JSON operam essa trilha como diagnóstico read-only; não são autoridade.

A fronteira aberta é se o motor deve fechar o loop aplicando automaticamente a mudança no catálogo de
modelos/configuração e emitindo `curador.promoveu`, ou se deve parar em uma intenção aprovada por
humano.

## Decisão
No v1, o curador **não aplica catálogo automaticamente**.

O comportamento aprovado é:

1. Rodar sombra sobre casos held-out explícitos.
2. Certificar apenas quando o candidato vence o titular nos eixos objetivos definidos,
   recomputando a evidência v2 selada em vez de confiar em agregados do chamador.
3. Recuperar a certificação exata por ID em repositório autoritativo do deployment. Sem
   repositório, ID ou correspondência, vetar.
4. Gerar `status="promocao_pendente"` com `requer_gate=True` e evidência serializável.
5. Deixar a aplicação real de catálogo/config para um gate humano externo ao curador.

Um arquivo JSON, o output da CLI, um dict com `status="certificado"` ou um hash isolado não
pode criar intenção autoritativa. O repositório obrigatório fecha essa fronteira; o repo não
fornece hoje um backend de produção e, portanto, a operação permanece indisponível por
default.

`curador.promoveu` fica reservado para uma etapa futura que aplique a alteração depois do gate. A fatia
atual emite `curador.promocao_pendente`, não `curador.promoveu`.

## Critério atual de certificação
O código atual é mais estrito que a frase "custo não pior": `certificar_sombra(...)` certifica somente
quando a qualidade do candidato é estritamente maior **e** o custo médio é estritamente menor.

Esta ADR não relaxa esse critério para `<=`. Se o produto quiser aceitar "qualidade maior e custo igual",
isso deve ser uma mudança separada com teste explícito e revisão anti-Goodhart.

## Por quê
Aplicar catálogo automaticamente é a parte mais arriscada do flywheel:

- muda o executor usado por runs futuras;
- pode degradar qualidade de forma silenciosa se o grader for fraco;
- acopla medição, decisão e mutação numa mesma função;
- viola a lei de que a fábrica só se modifica por dentro, com gate.

Parar em intenção preserva o aprendizado do curador sem entregar autoridade operacional ao comparador.

## Consequências
Positivas:

- Mantém o curador determinístico, testável e read-only na fronteira de risco.
- Dá à auditoria um ponto claro para atacar: evidência da sombra e motivo da certificação.
- Evita mutação de catálogo por métrica insuficiente ou casos held-out fracos.
- Impede que estado externo auto-declarado ou JSON transportável ganhe autoridade de
  promoção.

Negativas:

- O loop ainda exige humano ou camada externa para aplicar a promoção.
- O deployment precisa fornecer repositório confiável; sem ele, nem a intenção é criada.
- Não há rollback automático porque não há apply automático.
- `curador.promoveu` permanece evento reservado, não emitido pela trilha v1.

## Later
Aplicação automática só deve entrar quando houver:

1. contrato versionado de catálogo;
2. repositório de certificações imutável, autenticado e com controle de acesso;
3. gate humano/organizacional explícito;
4. rollback testado;
5. histórico de promoção com before/after;
6. casos held-out certificados e congelados por slot;
7. evento `curador.promoveu` emitido somente após apply bem-sucedido.

## Onde isto pode dar errado
- O humano pode virar rubber-stamp e aprovar promoção sem olhar a evidência.
- A intenção pendente pode acumular backlog e atrasar economia real.
- O critério "custo estritamente menor" pode rejeitar candidato de mesma qualidade/custo com outras vantagens operacionais; isso é aceitável no v1, mas deve ser reavaliado com dados.
- O evento reservado `curador.promoveu` pode ser usado por outra camada sem contrato de rollback; isso deve bloquear auditoria.
- Um fake em memória pode provar o protocolo, mas não autenticidade ou imutabilidade. Tratá-lo
  como backend de deployment reabre U3/K4.
