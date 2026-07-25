# Rascunho: motor para entrega profissional de software

Data: 2026-06-26

## Tese

O motor nao deve ser vendido como "IA que garante software sem erro". Essa promessa e tecnicamente falsa e perigosa.

A tese forte e defensavel e outra:

> O motor transforma desenvolvimento com IA em uma linha de producao auditavel, com specs pequenas, execucao controlada, evidencias objetivas, gates de engenharia e responsabilidade de producao antes de qualquer deploy.

Ou seja: a qualidade nao vem de acreditar que a IA virou senior. A qualidade vem de forcar a IA a operar dentro de um processo senior.

## Intuicao central

Na engenharia tradicional, a diferenca entre software amador e software profissional raramente e "o senior digita codigo magico". A diferenca esta no processo:

- escopo pequeno;
- arquitetura explicita;
- criterio de aceite;
- revisao;
- testes;
- seguranca;
- observabilidade;
- rollback;
- deploy gradual;
- accountability.

O motor deve codificar esse processo.

O papel da IA e executar rapido. O papel do workflow e impedir que velocidade vire irresponsabilidade.

## O que o motor deve ser

O motor deve funcionar como uma fabrica de mudancas pequenas e verificaveis.

Fluxo ideal:

```text
problema real
-> discovery
-> spec curta
-> fatia pequena
-> plano tecnico
-> threat model quando aplicavel
-> implementacao
-> testes obrigatorios
-> review adversarial
-> checks de seguranca
-> staging
-> observabilidade
-> deploy controlado
-> monitoramento pos-deploy
```

O motor pode coordenar agentes, ferramentas e modelos, mas a aprovacao precisa depender de evidencias objetivas.

Regra de ouro:

> Nada critico e aprovado por opiniao. Tudo que importa precisa deixar evidencia: teste, diff, log, checklist, scanner, review, ambiente ou metrica.

## O que o motor nao deve prometer

Nao prometer:

- "sem risco de vazamento";
- "sem bugs";
- "100% seguro";
- "software production-grade so por prompt";
- "substitui time senior";
- "deploy autonomo sem supervisao".

Prometer:

- desenvolvimento assistido por IA com QA estruturado;
- processo auditavel;
- gates de seguranca e qualidade;
- rastreabilidade de decisoes;
- reducao de risco;
- velocidade com controle;
- capacidade de produzir PRs pequenos e revisaveis.

## Modelo mental correto

Uma IA solta se parece com um junior muito rapido: produz muito, mas pode errar com confianca.

Um workflow bom se parece com um senior operacionalizado: define limites, criterios, riscos e bloqueios.

CI, testes, scanners, staging e logs sao a realidade objetiva: eles nao se impressionam com texto bonito.

O motor deve juntar essas tres coisas:

```text
IA rapida
+ workflow senior
+ validacao objetiva
= entrega profissional possivel
```

## Modos de operacao

O motor nao precisa escolher entre "one-shot" e "engenharia seria". Ele deve ter modos explicitos, com expectativas, permissoes e gates diferentes.

### Modo 1: one-shot / spike

Objetivo: ver algo funcionando rapido.

Uso correto:

- sentir o produto;
- validar direcao;
- gerar demo navegavel;
- descobrir escopo escondido;
- produzir material bruto para lapidar depois.

Promessa: velocidade e aprendizado.

Nao promete: qualidade final, seguranca de producao, cobertura completa, arquitetura definitiva.

Regras:

- pode gerar sistema inteiro;
- pode deixar divida tecnica;
- pode conter bugs;
- nao pode tocar producao real;
- nao pode usar dados reais sensiveis;
- nao pode ter permissao de deploy;
- nao pode ser vendido como release final;
- saida vira insumo para refino, nao produto governado.

Este modo e util. Ele so fica perigoso quando o prototipo e confundido com produto.

### Modo 2: iterativo / pair programming

Objetivo: construir de verdade em ciclos curtos.

Fluxo:

```text
story pequena
-> teste
-> implementacao
-> CI
-> review
-> refactor
-> commit ou PR
```

Este e o modo mais proximo de XP com IA:

- small releases;
- TDD quando aplicavel;
- CI em cada mudanca;
- refactoring continuo;
- documentacao viva;
- humano como navegador;
- agente como piloto rapido.

Promessa: progresso real com controle.

### Modo 3: producao / governado

Objetivo: mexer em sistema serio, com usuarios e dados reais.

Fluxo:

```text
spec
-> PR pequeno
-> testes
-> security gate
-> CI
-> staging
-> aprovacao
-> deploy controlado
-> monitoramento
```

Promessa: reducao forte de risco, auditoria e operacao responsavel.

Aqui o motor nao deve apenas entregar. Ele deve provar.

## Transicao entre modos

O caminho saudavel pode ser:

```text
one-shot gera versao bruta
-> humano usa e aponta erro de escopo
-> motor converte feedback em backlog
-> fatias pequenas corrigem rumo
-> testes e gates endurecem o que virou real
-> producao so entra no modo governado
```

O objetivo nao e fingir que o one-shot e seguro. O objetivo e usar o one-shot como ferramenta de descoberta e depois promover apenas o que passou por endurecimento.

### Como resolver o risco do spike virar producao

O motor precisa marcar cada artefato com um estado:

```text
spike
candidate
production-ready
```

Regra:

- `spike`: pode existir sem testes completos, mas nao pode deployar com dados reais;
- `candidate`: escopo validado, precisa ser quebrado em fatias e ganhar testes;
- `production-ready`: passou por DoD, CI, review, security gate quando aplicavel, staging e plano de rollback.

Permissao deve seguir o estado:

- artefato `spike` nao recebe segredo de producao;
- artefato `spike` nao acessa banco real;
- artefato `spike` nao publica deploy publico sem aviso explicito;
- somente `production-ready` pode chegar ao caminho de release.

Tambem precisa existir um gate de promocao:

```text
promover spike para candidate:
  exige escopo revisado e backlog de lacunas

promover candidate para production-ready:
  exige testes, CI, security review quando aplicavel, staging e rollback
```

Assim o modo rapido continua existindo, mas nao contamina o modo serio.

## Unidade de trabalho

A unidade de trabalho nao deve ser "construir um sistema".

Deve ser uma fatia pequena:

- uma tela;
- uma rota;
- uma regra de negocio;
- uma migracao;
- um fluxo critico;
- um bug;
- uma melhoria de seguranca;
- uma integracao especifica.

Cada fatia precisa caber em revisao humana e idealmente gerar PR pequeno. Regra pratica: se passar de aproximadamente 300 linhas uteis, quebrar em mais fatias.

## Gates minimos por fatia

Toda fatia deve ter:

- objetivo;
- fora de escopo;
- criterios de aceite;
- plano de implementacao;
- arquivos afetados esperados;
- riscos;
- testes obrigatorios;
- rollback ou estrategia de recuperacao quando tocar producao;
- definicao clara de pronto.

Definition of Done minimo:

- testes do caminho feliz;
- testes de edge case relevante;
- teste negativo quando houver permissao, input externo ou regra critica;
- lint limpo;
- type-check limpo;
- review de seguranca se tocar banco, auth, input externo, pagamento, dados sensiveis ou mobile;
- diff dentro do escopo;
- nenhuma alteracao oportunista sem justificativa.

## Como impedir que gate vire teatro

Checklist em Markdown nao pode aprovar entrega sozinho.

O motor precisa separar tres coisas:

```text
intencao declarada
evidencia coletada
permissao liberada
```

Uma fatia so deve avancar quando a evidencia existe e foi validada por uma regra objetiva.

Exemplo ruim:

```text
agente marca "testes ok" no Markdown
```

Exemplo bom:

```text
CI executou npm test
CI executou type-check
CI executou lint
artefato de saida foi salvo
gate leu o resultado
branch protection bloqueou merge se falhou
```

O motor deve produzir checklist, mas quem bloqueia precisa ser sistema:

- CI bloqueia merge;
- branch protection exige checks verdes;
- deploy exige ambiente aprovado;
- segredo de producao nao fica disponivel para agente de implementacao;
- permissao de deploy fica separada da permissao de escrever codigo;
- areas criticas exigem aprovacao humana ou reviewer independente;
- evidencias da run ficam anexadas ao PR ou ao pacote de release.

Modelo de controle:

```text
motor planeja
executor implementa
CI verifica
reviewer critica
policy decide
permissao libera ou bloqueia
```

O motor nao deve ter permissao direta para pular a policy. Se ele puder alterar o codigo, alterar o teste, aprovar o proprio PR e fazer deploy, o processo perde valor.

### Contrato de evidencias

Cada gate precisa declarar exatamente qual evidencia aceita.

Exemplos:

- `lint_passou`: log do comando de lint com exit code 0;
- `typecheck_passou`: log do type-check com exit code 0;
- `teste_permissao_cross_tenant`: nome do teste e resultado no CI;
- `sem_secrets_no_diff`: scanner ou review dedicado;
- `migration_revisada`: aprovacao especifica em arquivo de migracao;
- `rollback_definido`: arquivo ou secao de release plan;
- `staging_validado`: URL/ambiente, smoke test e horario da validacao;
- `alertas_configurados`: link ou identificador dos alertas.

Sem contrato de evidencia, o agente pode responder bonito e o sistema pode acreditar.

### Politica por risco

Nem toda mudanca precisa do mesmo rigor.

Mudancas de baixo risco podem ser automatizadas:

- texto;
- docs;
- copy;
- testes adicionais;
- ajustes pequenos de UI sem dado sensivel;
- refactor mecanico com testes fortes.

Mudancas de medio risco exigem PR e CI:

- feature comum;
- endpoint novo;
- formulario;
- integracao sem dado sensivel;
- mudanca em regra de negocio local.

Mudancas de alto risco exigem gate forte:

- auth;
- pagamento;
- permissao;
- multi-tenant;
- banco e migracao destrutiva;
- dados sensiveis;
- upload;
- webhook;
- deploy de infraestrutura;
- alteracao de logging;
- mudanca em backup/restore.

Para alto risco, o motor pode preparar, implementar e testar, mas nao deve aprovar sozinho.

## QA que nao vira teatro

QA fraco testa apenas o caminho feliz.

QA profissional exige matriz por fluxo:

```text
happy path
edge case
erro esperado
permissao negada
input malicioso
estado vazio
estado com muitos dados
concorrencia quando relevante
falha de dependencia externa
```

O motor deve bloquear a conclusao da fatia se a matriz aplicavel nao estiver coberta.

Exemplo: login nao esta testado se apenas "usuario correto entra" passa.

Tambem precisa testar:

- senha errada;
- usuario inexistente;
- sessao expirada;
- rota protegida;
- logout;
- rate limit ou protecao contra brute force quando aplicavel;
- comportamento com provider de auth indisponivel.

## Rubricas verificaveis

Rubrica ruim:

```text
"codigo limpo"
"boa UX"
"seguro"
"bem arquitetado"
```

Rubrica boa:

```text
"usuario sem permissao recebe 403"
"usuario do tenant A nao consegue ler recurso do tenant B"
"payload invalido retorna 400 com erro estruturado"
"teste cobre tentativa de acesso cruzado entre tenants"
"logs nao incluem token, senha, email completo ou payload sensivel"
"migration tem estrategia de rollback ou plano de recuperacao"
```

O motor deve rejeitar rubricas subjetivas em gates criticos. Se nao da para verificar, nao deve aprovar sozinho.

## Seguranca como etapa obrigatoria

Todo input externo e hostil ate validado.

Entram como input externo:

- forms;
- query params;
- uploads;
- webhooks;
- APIs de terceiros;
- mensagens de bot;
- CSV/planilhas importadas;
- callbacks OAuth;
- dados vindos do cliente;
- eventos assincronos.

Checklist minimo para input externo:

- schema validation;
- tamanho maximo;
- rate limit;
- sanitizacao/normalizacao;
- tratamento de erro sem vazar detalhe interno;
- logs sem segredo ou PII desnecessaria;
- testes negativos;
- monitoramento de falha.

## Banco, multi-tenant e dados sensiveis

Para sistemas com muitos usuarios e muitos dados, o motor precisa tratar banco e autorizacao como zona vermelha.

Gates obrigatorios:

- modelo de dados revisado;
- migracao revisada;
- indices para consultas criticas;
- testes de permissao;
- teste de isolamento entre tenants;
- politica de backup;
- estrategia de restore testada;
- logs sem dados sensiveis;
- dados sensiveis criptografados quando necessario;
- principio do menor privilegio;
- secrets fora do repo.

Em Supabase/Postgres com RLS, por exemplo, nao basta "ativar RLS". Precisa de teste provando que:

- usuario sem login nao acessa dado privado;
- usuario A nao acessa dado de usuario B;
- tenant A nao acessa tenant B;
- service role nao aparece no client;
- policies cobrem select, insert, update e delete conforme o caso.

## Auth, pagamento e permissoes

Essas areas nao devem ser autonomas por padrao.

Elas exigem gate mais forte:

- spec explicita;
- threat model;
- review adversarial;
- testes negativos;
- revisao humana ou agente revisor forte;
- staging;
- rollback;
- logs e alertas.

Exemplos de falha que o motor deve procurar:

- rota protegida so no frontend;
- permissao checada depois da query;
- IDOR;
- webhook sem assinatura;
- checkout confiando em preco vindo do cliente;
- token em log;
- permissao admin inferida por campo manipulavel;
- reset de senha sem expiracao;
- upload aceitando tipo/tamanho arbitrario.

## Pentest e validacao adversarial externa

Security checklist, scanner e review de codigo nao substituem pentest.

O pentest entra quando o sistema tem risco real:

- usuarios externos;
- dados sensiveis;
- multi-tenant;
- pagamento;
- auth complexa;
- uploads;
- webhooks;
- APIs publicas;
- integracoes criticas;
- grande mudanca de infraestrutura;
- lancamento publico relevante.

O motor pode preparar e coordenar pentest, mas nao deve fingir que ele mesmo substitui um atacante qualificado.

### Camadas de validacao

```text
secure design
-> testes negativos
-> scanners automatizados
-> review adversarial de codigo
-> pentest interno em staging
-> pentest externo quando risco justificar
-> correcao
-> reteste
-> regressao automatizada
```

Pentest bom nao e "rodar ferramenta e colar relatorio". Pentest bom tenta quebrar o sistema dentro de um escopo autorizado e transforma achado em melhoria permanente.

### Regras de engajamento

Todo pentest precisa declarar:

- escopo;
- ambiente;
- janela de teste;
- dados permitidos;
- tecnicas permitidas;
- tecnicas proibidas;
- limite de carga;
- contatos de emergencia;
- criterio de parada;
- formato de relatorio;
- severidade;
- SLA de correcao;
- necessidade de reteste.

Sem regras de engajamento, pentest vira risco operacional.

### Evidencias obrigatorias

Cada achado deve conter:

- descricao;
- impacto;
- severidade;
- passos de reproducao;
- evidencias;
- recurso afetado;
- causa provavel;
- recomendacao;
- owner;
- prazo;
- status;
- reteste;
- teste de regressao criado quando aplicavel.

Achado fechado sem reteste e fraco. Achado corrigido sem regressao pode voltar.

### Como resolver o risco de pentest virar teatro

Controle:

- pentest nao aprova producao sozinho; ele alimenta backlog de risco;
- achado critico ou alto bloqueia release ate correcao ou aceite formal de risco;
- aceite de risco precisa ter dono, prazo e justificativa;
- todo achado reproduzivel deve virar teste automatizado quando tecnicamente possivel;
- reteste e obrigatorio para severidade alta/critica;
- pentest externo deve ser independente do executor principal;
- ambiente de teste deve representar producao sem expor dados reais desnecessarios;
- relatorio deve mapear impacto de negocio, nao apenas CVE ou ferramenta.

### Papel da IA no pentest

A IA pode ajudar a:

- montar threat model;
- gerar checklist por superficie;
- sugerir casos de teste adversariais;
- revisar logs de scanner;
- correlacionar achados;
- criar testes de regressao;
- priorizar correcoes;
- explicar impacto e mitigacao.

A IA nao deve:

- atacar sistemas sem autorizacao explicita;
- rodar carga agressiva fora de ambiente permitido;
- exfiltrar dados reais;
- decidir sozinha aceitar risco alto;
- substituir pentester externo em sistemas de alta responsabilidade.

## Governanca legal, LGPD e compliance

Seguranca tecnica nao cobre responsabilidade legal.

Para sistemas com usuarios reais, dados pessoais, pagamentos, contratos ou operacao publica, o motor precisa acionar uma camada de compliance. Essa camada nao substitui advogado, mas impede que o time trate requisito juridico como detalhe de implementacao.

### LGPD e privacidade

Todo produto que trata dados pessoais precisa declarar:

- quais dados coleta;
- por que coleta;
- base legal;
- finalidade;
- controlador;
- operadores;
- encarregado/DPO quando aplicavel;
- fornecedores e suboperadores;
- onde os dados ficam;
- quem acessa;
- por quanto tempo retém;
- como apaga;
- como exporta;
- como atende direitos do titular;
- como comunica incidente;
- quais dados entram em logs, analytics e ferramentas de suporte;
- quais dados entram em prompts, modelos ou ferramentas de IA.

O motor deve bloquear features com dados pessoais se nao existir pelo menos um mapa minimo de tratamento.

### Direitos dos titulares

Precisa existir processo para:

- confirmar identidade do solicitante;
- localizar dados do titular;
- exportar dados;
- corrigir dados;
- anonimizar ou excluir quando aplicavel;
- registrar excecoes legais de retencao;
- responder dentro do prazo aplicavel;
- manter evidencia da resposta.

Sem isso, "temos LGPD" vira frase, nao processo.

### Retencao e descarte

Todo dado precisa ter destino.

Perguntas obrigatorias:

- esse dado e necessario?
- por quanto tempo?
- existe obrigacao legal de guardar?
- existe motivo para apagar antes?
- backup respeita politica de retencao?
- logs expiram?
- ambiente de staging contem dado real?
- dados de suporte e analytics expiram?

Dado sem politica de retencao vira passivo.

### RIPD / DPIA

Quando o tratamento puder gerar alto risco aos titulares, o motor deve exigir avaliacao de impacto.

Sinais de alto risco:

- grande escala;
- dados sensiveis;
- criancas/adolescentes;
- geolocalizacao;
- scoring/perfilamento;
- biometria;
- decisoes automatizadas;
- monitoramento sistematico;
- cruzamento de bases;
- dados financeiros ou de saude;
- compartilhamento relevante com terceiros.

Saida minima:

- descricao do tratamento;
- necessidade e proporcionalidade;
- riscos aos titulares;
- medidas de mitigacao;
- responsavel;
- aprovacao;
- plano de revisao.

### Como resolver o risco de compliance virar teatro

Controle:

- compliance gate nao aprova por texto generico;
- exige inventario de dados e finalidade;
- exige owner para cada base/processamento;
- exige politica de retencao;
- exige canal para direitos do titular;
- exige evidencias de atendimento;
- exige revisao juridica para alto risco;
- exige aceite formal de risco quando a decisao for seguir mesmo com pendencia.

O motor pode preparar a analise. Decisao juridica de alto impacto deve ter responsavel humano qualificado.

## Contratos, fornecedores e cadeia de terceiros

Fornecedor e parte do sistema.

Se o produto usa auth provider, cloud, analytics, gateway de pagamento, email, CRM, observabilidade, suporte, IA externa ou storage, isso entra na superficie de risco.

Gate minimo para fornecedor:

- que dados recebe;
- finalidade;
- pais/regiao de processamento;
- subfornecedores;
- SLA;
- suporte;
- seguranca;
- DPA quando tratar dados pessoais;
- notificacao de incidente;
- direito de auditoria ou relatorio independente;
- exclusao/devolucao de dados no encerramento;
- custo de saida;
- plano B se o fornecedor falhar.

### Contratos do produto

Produto serio precisa de artefatos juridicos coerentes com o que o sistema faz:

- termos de uso;
- politica de privacidade;
- politica de cookies quando aplicavel;
- DPA para clientes B2B quando aplicavel;
- SLA;
- politica de suporte;
- politica de reembolso/cancelamento quando aplicavel;
- limites de responsabilidade;
- regras de uso aceitavel;
- aviso sobre IA quando o produto usar IA de forma relevante.

O motor nao deve gerar esses documentos como decisao final. Ele pode gerar rascunhos e checklist, mas revisao juridica deve fechar.

## Governanca de IA, propriedade intelectual e licencas

Se o motor usa IA para construir software, existe uma camada propria de risco.

Perguntas obrigatorias:

- prompts podem conter dados pessoais?
- prompts podem conter segredo comercial?
- outputs ficam armazenados por fornecedor?
- fornecedor usa dados para treino?
- logs de prompts expiram?
- quem pode acessar conversas e artefatos?
- codigo gerado tem dependencia/licenca compativel?
- agentes podem copiar trechos de codigo externo sem origem clara?
- modelos diferentes tem politicas diferentes de retencao?
- existe trilha de auditoria de quem gerou, revisou e aprovou?

Controle minimo:

- politica de uso de IA;
- classificacao de dados permitidos em prompts;
- fornecedores aprovados;
- redacao/mascara de dados sensiveis;
- revisao de licencas;
- SBOM/dependency inventory quando aplicavel;
- audit log das decisoes;
- regra de que output de IA nao entra em producao sem review e testes.

## Resposta a incidentes, judicial e comunicacao

Incidente nao e so tecnico.

Quando ha vazamento, indisponibilidade grave, fraude, abuso, perda de dados, sequestro de dados ou falha em fornecedor, entram tambem:

- juridico;
- suporte;
- comunicacao;
- lideranca;
- seguranca;
- engenharia;
- cliente;
- regulador quando aplicavel;
- seguradora quando existir cyber insurance.

O motor precisa ter runbook de incidente com:

- classificacao de severidade;
- sala de guerra;
- responsaveis;
- preservacao de evidencias;
- timeline;
- decisao de comunicacao;
- comunicacao a titulares quando aplicavel;
- comunicacao a regulador quando aplicavel;
- comunicacao a clientes;
- postmortem;
- plano de remediacao;
- testes de regressao;
- revisao de contrato/fornecedor quando aplicavel.

### Legal hold e evidencias

Em incidente serio ou disputa judicial, nem todo dado pode ser apagado imediatamente.

O motor precisa distinguir:

- retencao normal;
- pedido de exclusao;
- obrigacao legal;
- investigacao;
- legal hold;
- auditoria.

Sem isso, o sistema pode apagar prova necessaria ou reter dado indevido.

## Produção de verdade

Para dizer que algo esta pronto para usuarios reais, o motor precisa exigir mais que testes locais.

Checklist de producao:

- ambiente de staging;
- variaveis de ambiente separadas;
- seed de dados realista;
- smoke test;
- teste de carga basico nos fluxos criticos;
- pentest ou validacao adversarial quando risco justificar;
- feature flag quando o risco justificar;
- deploy gradual;
- rollback testado;
- logs estruturados;
- metricas;
- alertas;
- runbook de incidente;
- ownership claro.

Sistema profissional nao e apenas codigo correto. E tambem operacao.

## Stack Lab: decisao tecnica por evidencia

Uma empresa profissional nao so entrega software. Ela melhora continuamente a forma como entrega software.

O motor deve ter uma funcao de laboratorio para avaliar stacks, modelos, ferramentas e processos antes de promover qualquer coisa para o jogo real.

Objetivo:

> Encontrar a menor stack que entrega confiabilidade, seguranca, velocidade e operacao suficientes para cada dominio, sem fragmentar a empresa em tecnologias demais.

Nao e laboratorio de moda. E laboratorio de decisao tecnica.

### Portfolio controlado de stacks

O caminho saudavel nao e uma stack perfeita para tudo, nem uma stack diferente para cada microproblema.

O motor deve manter um portfolio controlado:

```text
default stack
  cobre 70-80% dos casos
  simples, conhecida, barata de operar

stacks aprovadas por dominio
  mobile
  SaaS CRUD
  realtime
  data/ML
  automacao interna
  baixa latencia/performance

stacks experimentais
  apenas laboratorio ou spike

stacks em hold
  evitar ate nova evidencia
```

A regra:

> Stack nova paga imposto de complexidade.

Esse imposto inclui:

- mais conhecimento para o time;
- mais superficie de seguranca;
- mais CI/CD;
- mais observabilidade;
- mais deploy;
- mais documentacao;
- mais debug;
- mais contratacao;
- mais risco de integracao;
- mais manutencao.

Uma stack nova nao entra porque e elegante. Ela entra se pagar esse imposto com ganho real em confiabilidade, custo, velocidade, seguranca, performance ou simplicidade operacional.

### Fluxo do laboratorio

O Stack Lab deve operar por hipoteses:

```text
hipotese tecnica
-> matriz de criterios
-> prototipo comparavel
-> benchmark
-> analise de riscos
-> custo operacional
-> decisao
-> prazo para reavaliar
```

Exemplo:

```text
Hipotese:
  Phoenix entrega realtime multi-tenant com menos risco operacional que Next.js + WebSocket custom.

Experimento:
  implementar login, tenant isolation, CRUD, canal realtime, teste negativo, deploy e observabilidade basica nas duas stacks.

Metricas:
  tempo de implementacao, linhas relevantes, dependencias, build, deploy, latencia, facilidade de debug, cobertura de teste, risco de permissao, clareza de operacao.

Decisao:
  Adopt, Trial, Assess ou Hold.
```

### Tech Radar interno

Saida do laboratorio:

```text
Adopt: usar em producao sem medo relevante
Trial: usar em projeto pequeno/controlado
Assess: estudar mais, ainda sem producao
Hold: evitar por enquanto
```

Cada decisao precisa guardar:

- problema avaliado;
- stacks comparadas;
- criterio de sucesso;
- evidencias;
- custos;
- riscos;
- decisao;
- prazo de reavaliacao;
- responsavel.

### Como resolver os riscos do Stack Lab

#### Risco: virar laboratorio de moda

Controle:

- todo experimento precisa estar ligado a problema real;
- todo experimento tem timebox;
- toda hipotese tem metrica e criterio de decisao;
- se nao melhora entrega, seguranca, custo, confiabilidade ou velocidade, nao entra.

#### Risco: virar burocracia e matar velocidade

Controle:

- default stack continua sendo o caminho rapido;
- laboratorio so e exigido para excecoes relevantes;
- experimento pequeno, prazo curto e decisao explicita;
- ausencia de evidencia favorece a stack padrao.

#### Risco: fragmentar a empresa

Controle:

- limitar numero de stacks em `Adopt`;
- exigir dono claro para cada stack aprovada;
- exigir template de projeto, CI, deploy, logs, metricas, secrets e runbook;
- stack sem dono volta para `Hold`;
- excecao precisa justificar o imposto de complexidade.

#### Risco: benchmark mentir

Controle:

- testar nao so construir, mas tambem manter:
  - alterar requisito;
  - corrigir bug;
  - debugar erro;
  - fazer deploy;
  - observar logs;
  - atualizar dependencia;
  - proteger rota;
  - migrar banco;
  - rollback.
- usar cenario minimo realista:
  - auth;
  - tenant isolation;
  - CRUD;
  - job assincrono;
  - upload ou webhook quando aplicavel;
  - migration;
  - erro de API externa;
  - logs e metricas;
  - teste negativo;
  - deploy.

#### Risco: agente favorecer a stack que conhece melhor

Controle:

- usar criterios fixos;
- separar executor de reviewer;
- rodar avaliacao adversarial;
- quando possivel, usar agentes diferentes por stack;
- CI mede o que puder ser medido;
- humano revisa trade-offs antes de `Adopt`.

#### Risco: metricas falsas

Controle:

- nao decidir so por LOC ou tempo de prototipo;
- medir clareza, debug, dependencias, qualidade dos erros, seguranca, maturidade, observabilidade e upgrade path;
- incluir custo total de 12 meses, nao so velocidade inicial.

### Plataforma comum acima das stacks

Mesmo com stacks diferentes, a experiencia operacional deve ser unificada.

Contrato minimo:

- CI padrao;
- logs padrao;
- metricas padrao;
- deploy padrao;
- secrets padrao;
- testes minimos;
- security checklist;
- estrutura de docs;
- runbook;
- ownership.

Esse e o caminho pragmatico para chegar perto de uma "superstack": talvez nao uma unica linguagem para tudo, mas uma experiencia operacional comum, confiavel e eficiente.

## Como o motor deveria organizar agentes

Um workflow serio pode ter papeis assim:

- planner: transforma problema em spec pequena;
- arquiteto: define desenho tecnico e trade-offs;
- implementador: faz mudanca minima;
- testador: cria testes obrigatorios;
- security reviewer: procura vazamento, permissao quebrada, input hostil;
- code reviewer: procura bug, acoplamento, regressao e escopo;
- operator: valida deploy, logs, metricas e rollback;
- sintetizador: consolida evidencias e decisao.

Importante: o reviewer nao pode ser o mesmo executor, quando possivel. Revisao precisa ser adversarial.

## Evidencias que o motor deve guardar

Cada execucao deveria produzir um pacote de evidencias:

- spec da fatia;
- plano tecnico;
- diff;
- comandos rodados;
- saida de testes;
- saida de lint/type-check;
- checklist de seguranca aplicavel;
- relatorio de pentest ou validacao adversarial quando aplicavel;
- decisoes e trade-offs;
- riscos aceitos;
- resultado do review;
- link do PR;
- status do deploy;
- metricas pos-deploy quando houver.

Sem evidencia, a aprovacao e fraca.

## Maturidade por niveis

### Nivel 0: assistente de texto

O motor gera plano, spec e analise.

Serve para pensar melhor, mas nao deve ser vendido como entrega de software.

### Nivel 1: gerador de PR pequeno

O motor implementa fatias pequenas com executor de codigo, roda testes e abre PR.

Ainda exige review humano para areas criticas.

### Nivel 2: pipeline com gates reais

O motor so aprova mudanca com testes, lint, type-check, security checklist e evidencias.

Pode entregar software profissional em escopo controlado.

### Nivel 3: operacao assistida

O motor acompanha staging, deploy gradual, metricas, alertas e rollback.

Aqui ele comeca a funcionar como parte de uma organizacao de engenharia real.

### Nivel 4: autonomia limitada

O motor pode fazer mudancas de baixo risco sozinho dentro de limites formais.

Exemplos:

- texto;
- docs;
- ajustes pequenos de UI;
- testes adicionais;
- refactors mecanicos;
- correcoes com rollback simples.

Nao deve ter autonomia total sobre auth, pagamento, banco multi-tenant, dados sensiveis ou deploy amplo.

## Produto vendavel

Mensagem defensavel:

> Criamos software com IA dentro de um processo profissional de engenharia: specs pequenas, revisao, testes automatizados, controles de seguranca, CI/CD, staging, observabilidade e auditoria.

Mensagem perigosa:

> Nossa IA cria sistemas sem bugs e sem risco de vazamento.

O valor comercial nao e "IA infalivel". O valor e velocidade com governanca.

## Primeiras evolucoes praticas para este motor

1. Implementar modos explicitos de operacao:
   - `one-shot/spike`;
   - `iterativo/pair`;
   - `producao/governado`.

2. Marcar artefatos/runs por estado:
   - `spike`;
   - `candidate`;
   - `production-ready`.

3. Criar gates de promocao entre estados, impedindo spike de acessar caminho de release.

4. Criar templates de WorkflowSpec por tipo de tarefa:
   - feature web;
   - bugfix;
   - migracao de banco;
   - auth/permissao;
   - integracao externa;
   - mobile;
   - pagamento;
   - observabilidade.

5. Criar um gate de DoD que leia a spec e exija evidencias.

6. Integrar executor de codigo com permissao limitada e workspace isolado.

7. Fazer o motor produzir PR, nao deploy direto.

8. Criar security checklists executaveis por categoria de risco.

9. Criar rubrica validator: reprovar criterio subjetivo em area critica.

10. Guardar pacote de evidencias por run.

11. Adicionar staging/deploy gate apenas depois que PR pequeno estiver confiavel.

12. Criar o Stack Lab:
   - portfolio controlado de stacks;
   - tech radar interno;
   - experimentos por hipotese;
   - benchmark de construcao, manutencao, seguranca e operacao;
   - regra de imposto de complexidade para stack nova;
   - plataforma comum de CI, logs, deploy, secrets, docs e runbook.

13. Criar o fluxo de pentest:
   - regras de engajamento;
   - escopo e ambiente;
   - severidade e SLA;
   - triagem de achados;
   - bloqueio de release para risco alto/critico;
   - reteste;
   - conversao de achados em testes de regressao.

14. Criar compliance gates:
   - mapa de dados pessoais;
   - base legal/finalidade;
   - direitos do titular;
   - retencao e descarte;
   - RIPD/DPIA quando alto risco;
   - aceite formal de risco juridico quando aplicavel.

15. Criar vendor gates:
   - DPA;
   - subfornecedores;
   - regiao de processamento;
   - SLA;
   - notificacao de incidente;
   - exclusao/devolucao de dados;
   - custo de saida.

16. Criar governanca de IA e licencas:
   - politica de dados em prompts;
   - fornecedores de IA aprovados;
   - retencao de logs;
   - revisao de licencas;
   - SBOM/dependency inventory;
   - audit log de geracao, revisao e aprovacao.

17. Criar runbook juridico-operacional de incidentes:
   - severidade;
   - comunicacao;
   - preservacao de evidencias;
   - notificacao a titulares/regulador quando aplicavel;
   - legal hold;
   - postmortem;
   - remediacao.

## Principio final

O motor pode entregar trabalho de equipe de verdade se ele agir menos como "prompt gigante" e mais como "sistema operacional de engenharia".

Ele precisa transformar ambicao em fatias, fatias em PRs, PRs em evidencias, evidencias em aprovacao, aprovacao em deploy controlado e deploy em operacao observavel.

Essa e a diferenca entre automacao amadora e engenharia profissional assistida por IA.

### Onde isto pode dar errado

O processo pode virar teatro se os gates forem apenas Markdown sem bloqueio real. Testes ruins continuam passando codigo ruim. Scanners nao entendem regra de negocio. Agentes podem concordar entre si e aprovar uma solucao errada. Ferramentas com permissao demais aumentam o risco operacional. Para sistemas com milhoes de dados e responsabilidade alta, o motor precisa ser uma camada de controle dentro de uma pratica de engenharia madura, nao a unica fonte de verdade.

---

# Revisão e decisão (2026-06-29)

> Este rascunho foi escrito pelo Codex. Avaliado contra o contexto real (motor v0.5, solo, sem
> produção ainda) seguindo o princípio de que opinião externa é possibilidade a estudar, não ordem a
> acatar. Veredito: **aprovado como visão e como fonte de primitivas; reprovado como roadmap.** O
> roadmap operacional consolidado vive em `../../docs/ROADMAP.md`.

## O que muda o enquadramento

A largura deste documento (jurídico, fornecedor, compliance, pentest, vários papéis de engenharia)
**não é inchaço** — é o destino da meta-fábrica como simulador de organização. O desacordo com o
rascunho é de **escopo e sequenciamento**, não de filosofia. A tese central dele ("a qualidade vem de
forçar a IA a operar dentro de um processo senior") é a própria tese do dev-harness.

## Aprovado — primitivas universais (servem agora e o destino)

- **`intenção declarada / evidência coletada / permissão liberada`** + "quem bloqueia é sistema, não
  Markdown". Converge com a Fase 4, passo 1 (gate de CI). É o primeiro tijolo.
- **Contrato de evidências** — cada gate declara exatamente o que aceita (log de lint exit 0, nome do
  teste no CI, scanner de secrets). Implementável no WorkflowSpec.
- **Modos (spike/iterativo/produção) + estado do artefato (spike/candidate/production-ready) + gate de
  promoção.** Aprovado **com ressalva**: reconciliar com os tiers T0/T1/T2 já existentes — não criar um
  terceiro vocabulário paralelo. O repo já tem confusão de nomenclatura (Fase 1-4 vs E1-E6).
- **Rubricas verificáveis** (rejeitar critério subjetivo em gate crítico) + **executor ≠ reviewer**.

## Adiado — instâncias de verticais futuras, não bloat a deletar

Stack Lab/Tech Radar, regras de engajamento de pentest, LGPD/DPIA, vendor/DPA gates, legal hold,
runbook de incidente com regulador/seguradora. São reais **quando houver SaaS com usuários e dados
reais**. Hoje são preocupações de Nível 3-4 num sistema de Nível 1. Abstrair o padrão (um "gate", um
"papel"); não colar a instância. Vão pro Later do roadmap.

## Crítica estrutural

O documento confunde *motor* (a engine) com *governança da organização inteira*. Compliance, jurídico,
fornecedor e pentest são **processo organizacional que o motor no máximo rastreia, não é**. O motor
força os gates **técnicos** (CI, testes, evidência, permissão separada, máquina de estados); o resto
vive como checklists/templates no dev-harness, disparado por tags de risco — não codificado na engine.

## Pilares novos que surgiram no planejamento (não estavam no rascunho)

Detalhados no `../../docs/ROADMAP.md`; resumo das decisões:

- **Flywheel de especialistas (curador).** Modelos pequenos task-tuned (distill/SFT/LoRA), 1 base local
  + adapters. Aprovado como destino; colher dado agora, treinar quando o volume justificar. **Trava
  anti-collapse: só dado gate-verificado vira sinal de treino.** Fundação já em construção (curador
  fatias 1-2 read-only).
- **Camada de dados / conhecimento.** Grafo federado (catálogo de ponteiros, não armazém); uma camada,
  três projeções (humano / agentes / treino); proveniência + confiança + licença obrigatórias por nó.
- **Medição de custo.** Livro-razão por run/modelo/projeto — o instrumento que falta pra missão "cada
  vez mais barato". Deriva da telemetria-por-modelo.
- **Interface viva.** Flint como superfície/cliente do motor headless. Vivacidade = projeção de
  telemetria real (sem mentira decorativa). Gancho barato de hoje: o esquema de eventos motor→superfície.
  Briefing em `../../docs/design/interface-briefing.md`.
