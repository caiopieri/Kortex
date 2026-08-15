# Meta-fábrica

> Um **simulador de organização**: recebe um objetivo, instancia o time de papéis especialistas que ele
> exige (planner, arquiteto, engenheiros, QA, jurídico, designer…) e roda o processo inteiro dentro de um
> motor + IA, com **gates e evidências**. Entrega artefato intelectual (software, specs, docs, design) com
> qualidade — e busca um processo **cada vez mais seguro e barato**.

A função-objetivo do sistema é **minimizar o tempo-até-decisão do humano e o retrabalho**. Software é a
primeira vertical (onde a evidência é mais barata de verificar); o desenho é agnóstico para crescer a
outras (hardware, mecânica, jurídico, CAD).

## Arquitetura em camadas

A meta-fábrica é **autossuficiente** (motor + casas + **interface própria**). Produtos externos consomem
ela via MCP, mas ela **não depende de nenhum deles**.

```
Consumidores externos opcionais via MCP (assistentes, painéis e aplicações)
   ▲  MCP (despachar / status / stream de eventos)
┌ META-FÁBRICA (este repositório) ───────────────────────────────────────────────┐
│ Interface própria   ── a superfície de 1ª classe: VÊ a fábrica rodando e intercepta
│ Casas / harness     ── softwarehouse (dev-harness), hardware, mecânica… (método/control-plane)
│ Motor (kernel)      ── roda UM processo com maestria: grafo de papéis, verificação
│                        adversarial, gate de cobertura, contrato de evidência
└────────────────────────────────────────────────────────────────────────────────┘
```

**Regra pétrea:** o motor é *músculo, não autoridade* — fabrica e expõe estado; não decide permissão,
risco ou dinheiro (isso é do porteiro). A fronteira entre camadas é **MCP**. Este repositório é o
**núcleo** (motor + harnesses de domínio + interface própria + documentação). Clientes externos vivem
em projetos separados; a meta-fábrica funciona sem eles.

## Estrutura do repositório

```
docs/                  arquitetura, roadmap, decisões e design system
motor/                 o kernel (pacote Python autocontido)
  motor/ tests/ exemplos/ scripts/ motor_painel/
  docs/                ADRs, invariantes, segurança e runbooks
  specs/               contratos e verificação reproduzível
dev-harness/           a softwarehouse: metodologia de engenharia (a 1ª casa)
harness-hardware/      semente da vertical de hardware
harness-mecanico/      semente da vertical mecânica
```

## Começar a entender

1. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — camadas, fluxo e fronteiras de confiança.
2. [docs/ROADMAP.md](docs/ROADMAP.md) — o mapa operacional Now/Next/Later.
3. [motor/README.md](motor/README.md) — como rodar e testar o motor.
4. [motor/docs/EVOLUCAO.md](motor/docs/EVOLUCAO.md) e [motor/docs/ARQUITETURA-MCP.md](motor/docs/ARQUITETURA-MCP.md) — o norte e a fronteira do motor.
5. [motor/specs/](motor/specs/) — contratos públicos e evidências reproduzíveis.

## Verificar o motor e exercitar a composição

```bash
cd motor
python -m pip install -e ".[dev]"
pytest -q                                       # sem rede; ver "Estado da suíte" abaixo
python -m motor --modelos /caminho/modelos-orcados.json "pesquise oportunidades de aumento de receita"  # fail-closed
```

O último comando demonstra a composição e pode bloquear antes da rede: a configuração precisa conter
`orcamento_openai`, credencial por variável de ambiente, snapshot FX fresco e
`teto_bootstrap_brl` positivo. A rota OpenAI única ainda reprova o preflight de independência;
configurações legadas não autorizam efeitos.

## Estado

O motor v0.5 está em **hardening T2; ainda não está certificado para produção**. O programa H00–H13
fechou a maior parte das falhas encontradas pela auditoria defensiva, e a extensão H12b chegou à
integração fail-closed dos callsites de modelo. O estado comprovado hoje é:

- kernel/spec/grafo, reconciliação bounded e validação de capabilities hardened;
- executor de comando com identidade e `argv` validados, mas **default-deny em produção**;
- schema de eventos v2, ledger append-only/recovery, projeção read-only e superfície MCP tipada com
  input e resposta serializada limitados, identidade de gate e orçamento fail-closed;
- curador com sombra read-only, certificação anti-Goodhart e promoção apenas como intenção humana
  (ADR-003), nunca aplicação automática;
- Caixa do Fundador e livro-razão de orçamento com transações, replay, reserva exclusiva e relay
  `claim/lease/ack` para o ledger JSONL, preservando `event_id` e deduplicação após reabertura;
- planner, executor, verifier, evaluator, reconciliação e synthesizer reservam antes do efeito e
  bloqueiam custo desconhecido; a composição OpenAI exige pricing/FX versionados e frescos.

### Estado da suíte (branch `refatoracao-painel`, 2026-08-10)

`1129 passaram · 7 falharam · 35 pulados` (1171 coletados). **A branch não está verde.**

As 8 falhas por snapshot vencido foram resolvidas em 2026-08-10 recapturando FX e reconferindo as
quatro tabelas de pricing contra os `PRICING_SOURCE` (nenhum preço subiu; toda entrada verificável
está igual ou acima do mercado, então a tabela segue sendo teto conservador). Renovação de FX agora
tem ferramenta: `python3 scripts/recapturar_fx.py`.

As **7 falhas restantes são achados ABERTOS da auditoria Anthropic**, não reprodutores obsoletos.
Cada uma tem referência de arquivo:linha na docstring e todas descrevem **portão que não porteia**:

| Achado | Defeito |
|---|---|
| A-03 | `spec.py` usa `list[str]` e não `list[NonBlank]`: rubrica `["   "]` passa na validação e o verifier julga contra critério vazio |
| A-04 | validador declarado em nó de modelo é silenciosamente ignorado |
| A-05 | `grafo.py` faz `max(0, min(minimo, len(requer)))`: `min: 0` — proibido por `ConfigContem` — vira aprovação incondicional no runtime |
| A-06 | sem `jsonschema` instalado o mesmo payload é aprovado; o portão depende de dependência não declarada |
| E-01 | removido o sidecar `.<nome>.lock`, um segundo writer abre no mesmo inode e a `seq` deixa de ser contígua |
| E-02 | linha corrompida no meio do log não é quarentenada |
| E-03 | guard anti-drift é cego para tipo de evento não literal |

Estes contradizem parcialmente o parágrafo "Auditoria dual-frontier" abaixo, escrito quando a triagem
concluiu que não havia defeito aberto. A conclusão não vale para estes sete: eles reprovam hoje, em
isolamento, contra o código atual.

Contagem é evidência daquela revisão apenas. Um release deve rerodar todo gate de um checkout limpo.

As fronteiras abaixo impedem declarar o gate global fechado:

1. **H05b depende do ambiente, não de código faltando:** o backend Docker fail-closed existe
   (`motor/motor/runner.py`), com identidade OCI selada, limite de output e limpeza de execução. O que
   falta é *rodá-lo e certificá-lo*: o default composto continua sendo `DenyCommandRunner`, e o harness
   de conformance é Linux. `CommandRunner` é um `Protocol` — o caminho mais curto até a certificação
   pode ser um backend de nuvem com container isolado, imagem por digest e cobrança por segundo, e não
   um runner Linux dedicado. Ver `docs/DECISAO-provedores-e-computacao.md` §2.2. Fora de um ambiente certificado, C2/C3 permanecem indisponíveis — por
   desenho, não por omissão. Os testes de auditoria que exigem execução real ficam explicitamente
   pulados (`MOTOR_RUNNER_CERTIFICADO=1` os liga); a segurança de `argv` que eles cobriam é provada
   sem execução em `test_auditoria_gpt5_d.py::test_c4_metacaractere_vira_exatamente_um_argv`.
2. **Composição real ainda não é operacional:** uma única rota OpenAI não satisfaz a independência
   entre executor e verifier. A composição via OmniRoute alcança vários vendors com uma credencial,
   mas roteia **todos os papéis pelo mesmo proxy**: `vendor` code-owned impede contar o mesmo modelo
   duas vezes sob assinaturas diferentes, e nada observa qual upstream de fato atendeu. Isso é
   independência **declarada**, não observada — ver dívida 8 em `motor/docs/INVARIANTES.md` e
   `docs/DECISAO-provedores-e-computacao.md`. O teto bootstrap agora é governado por configuração e limita a spec
   gerada, mas o deployment deve dimensioná-lo para a reserva conservadora. Studio e experimentos
   reais falham fechados até receberem composição custeada durável.
3. **Autoridade do curador é externa:** sem `RepositorioCertificacoes` autoritativo, promoção continua
   indisponível; o motor produz no máximo uma intenção sujeita a gate humano.

### Auditoria dual-frontier

O charter está em [AUDITORIA-FINAL.md](motor/docs/AUDITORIA-FINAL.md) e as reproduções dos auditores
são versionadas em `motor/tests/test_auditoria_*.py` (111 testes, fatiados por grupo de invariante).

A triagem dos 15 vermelhos que elas produziam **não encontrou nenhum defeito aberto**: 7 eram a mesma
causa raiz (o default fail-closed do executor, item 1 acima) e 8 eram reproduções obsoletas — o
hardening já tinha landado e o teste ainda codificava a expectativa antiga. Todas foram reescritas
preservando a intenção do auditor, com docstring dizendo o que a auditoria pedia e por que a fronteira
real é outra. Isso fecha o critério 2 de produção (invariante sem teste virou teste verde), **não** o
critério 3: o cadeado Anthropic da Fase A ainda não rodou, e "dois vendors assinando" continua aberto.

O estado verificável e os bloqueios estão em
[verification.md](motor/specs/001-hardening-producao/verification.md). O sequenciamento operacional
continua em [docs/ROADMAP.md](docs/ROADMAP.md).

## Contribuir e segurança

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para configurar o ambiente e executar os gates. Falhas de
segurança devem seguir [SECURITY.md](SECURITY.md), sem exposição antecipada em issue pública.

## Licença

MIT — ver [LICENSE](LICENSE).
