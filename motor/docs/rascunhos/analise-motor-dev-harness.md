# Analise: motor, dev-harness e entrega de software real

Data: 2026-06-26

## Conclusao curta

O rascunho `motor-entrega-profissional.md` faz mais sentido dentro do `dev-harness` do que dentro do `motor`.

Motivo: o `motor` e o kernel/orquestrador generico. Ele deve executar workflows, rotear modelos, registrar eventos, persistir estado, pausar em gates, retomar execucoes e carregar ferramentas. Quem define o que significa "fazer software direito" e o harness de dominio.

No caso de software, esse papel e do `dev-harness`.

Arquitetura mental correta:

```text
motor
  kernel/orquestrador generico

dev-harness
  processo de engenharia de software

packs de dominio
  SaaS
  LGPD/compliance
  pentest
  fornecedores
  Stack Lab
  governanca de IA
  incidentes juridico-operacionais
```

## O que o dev-harness ja cobre bem

O `dev-harness` ja tem uma base forte para desenvolvimento profissional com IA:

- Discovery antes de especificar.
- Roadmap `Now / Next / Later`.
- Spec-kit como funil por fatia.
- Tiers T0/T1/T2.
- Revisao humana do plano.
- PR pequeno como unidade de trabalho.
- CI/gate externo como bloqueio.
- Security DoD multi-stack.
- Fluxo brownfield/retrofit.
- Regra de consolidar antes de avancar.
- Anti-bajulacao e bloco "Onde isto pode dar errado".

Isso ja e coerente com a tese:

> IA executa; processo e gates seguram qualidade.

## O que ainda nao esta coberto o suficiente

O `dev-harness` cobre bem engenharia de software, mas ainda nao cobre completamente a empresa real que existe ao redor de um SaaS em producao.

As lacunas principais:

1. **LGPD/compliance como gate executavel**
   - mapa de dados pessoais;
   - base legal;
   - finalidade;
   - direitos do titular;
   - retencao;
   - RIPD/DPIA quando alto risco;
   - incidente com dados pessoais;
   - evidencias de atendimento.

2. **Pentest como fluxo proprio**
   - regras de engajamento;
   - escopo;
   - severidade;
   - SLA;
   - reteste;
   - achado virando regressao automatizada;
   - bloqueio de release para risco alto/critico.

3. **Fornecedores e contratos**
   - DPA;
   - subfornecedores;
   - regiao de processamento;
   - SLA;
   - notificacao de incidente;
   - exclusao/devolucao de dados;
   - custo de saida.

4. **Governanca de IA e propriedade intelectual**
   - dados permitidos em prompts;
   - retencao de logs de fornecedores de IA;
   - segredo comercial;
   - licencas;
   - SBOM/dependency inventory;
   - trilha de auditoria de geracao/revisao/aprovacao.

5. **Stack Lab**
   - escolher stack/modelo/ferramenta por evidencia;
   - tech radar interno;
   - imposto de complexidade para stack nova;
   - benchmark de construcao, manutencao, seguranca e operacao;
   - portfolio controlado para evitar fragmentacao.

6. **Resposta juridico-operacional a incidentes**
   - comunicacao;
   - preservacao de evidencias;
   - legal hold;
   - notificacao a titulares/reguladores quando aplicavel;
   - postmortem;
   - remediacao.

## Separacao de responsabilidades recomendada

### Motor

O `motor` deve continuar pequeno e generico:

- interpretar `WorkflowSpec`;
- executar subagentes e ferramentas;
- suportar `fan_out_sintese` e `grafo_dependencias`;
- persistir estado;
- registrar eventos/evidencias;
- pausar e retomar gates;
- rotear modelos;
- permitir execucao por registry;
- oferecer APIs/MCP para harnesses chamarem.

O motor nao deve conter regras especificas de SaaS, LGPD, pentest ou Stack Lab como codigo duro.

### Dev-harness

O `dev-harness` deve ser o dono das regras de software:

- discovery;
- roadmap;
- spec-kit;
- T0/T1/T2;
- CI;
- security-DoD;
- PR/diff review;
- observabilidade;
- retrofit;
- packs de SaaS, compliance, pentest, vendors e incidentes.

### Packs

Os packs devem ser templates/gates reutilizaveis, acionados por risco.

Exemplos:

```text
saas-launch-pack
lgpd-pack
pentest-pack
vendor-pack
ai-governance-pack
stack-lab-pack
incident-response-pack
```

Cada pack deve declarar:

- quando aciona;
- quais artefatos exige;
- quais evidencias aceitas;
- quem aprova;
- o que bloqueia release;
- como registrar excecao/aceite de risco.

## Tese refinada

Antes:

> O motor entrega software profissional.

Melhor:

> O motor executa workflows. O dev-harness define o processo de software. Packs de dominio definem os gates especificos. Juntos, eles permitem produzir software de ponta a ponta com evidencias, controles e responsaveis.

Essa formulacao evita prometer que o kernel sabe tudo. Ela deixa claro que "qualquer coisa" depende de harnesses de dominio.

## O que "qualquer coisa" deveria significar

"Qualquer coisa" nao deve significar que o motor improvisa qualquer dominio.

Deve significar:

> Qualquer dominio que tenha um harness capaz de definir processo, ferramentas, gates, evidencias e criterio de pronto.

Exemplos:

- software SaaS: `dev-harness`;
- hardware: `Harness Hardware`;
- mecanica: `Harness Mecanico`;
- legal/compliance: pack especifico;
- marketing/site: harness proprio;
- produto/PM: harness proprio.

Sem harness, o motor pode fazer pesquisa/sintese/spike. Com harness, pode operar processo.

## Proximo passo recomendado

Nao colocar isso em producao agora.

Primeiro consolidar em documento e depois transformar em backlog:

1. Mover o rascunho para `dev-harness/docs/`.
2. Criar um roadmap de packs faltantes.
3. Escolher um pack inicial de alto valor:
   - recomendacao: `lgpd-pack` ou `saas-launch-pack`.
4. Definir formato minimo de gate:
   - trigger;
   - artefatos;
   - evidencias;
   - bloqueios;
   - aprovadores.
5. Integrar depois ao motor via registry/ferramentas, sem acoplar regra de negocio ao kernel.

## Decisao sugerida

Mover:

```text
motor/rascunhos/motor-entrega-profissional.md
```

Para:

```text
dev-harness/docs/motor-entrega-profissional.md
```

E manter este relatorio no `motor`, porque ele documenta a fronteira arquitetural do kernel:

```text
motor/rascunhos/analise-motor-dev-harness.md
```

## Onde isto pode dar errado

O risco principal e transformar `dev-harness` em um cemiterio de Markdown. Para evitar isso, cada nova camada precisa virar pack executavel: com trigger, evidencia, bloqueio e responsavel. Outro risco e acoplar regras de SaaS diretamente no `motor`, inchando o kernel e tornando outros dominios piores. O motor deve continuar generico; o rigor de dominio deve viver nos harnesses.
