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

## Rodar o motor (rápido)

```bash
cd motor
python -m pip install -e ".[dev]"
pytest -q                                       # suíte sem rede; mesmo alvo funcional do CI
python -m motor "pesquise oportunidades de aumento de receita"   # requer um provedor de modelo
```

## Estado

O motor v0.5 está em **hardening T2; ainda não está certificado para produção**. O programa H00–H13
fechou a maior parte das falhas encontradas pela auditoria defensiva, e a extensão H12b já avançou até
H12b2c1. O estado comprovado hoje é:

- kernel/spec/grafo, reconciliação bounded e validação de capabilities hardened;
- executor de comando com identidade e `argv` validados, mas **default-deny em produção**;
- schema de eventos v2, ledger append-only/recovery, projeção read-only e superfície MCP hardened;
- curador com sombra read-only, certificação anti-Goodhart e promoção apenas como intenção humana
  (ADR-003), nunca aplicação automática;
- Caixa do Fundador e livro-razão de orçamento com transações, replay, reserva exclusiva, outbox e
  protocolo de `claim/lease/ack` até H12b2c1.

Duas fronteiras impedem declarar o gate global fechado:

1. **H05b bloqueado externamente:** falta um backend real de sandbox, com imagem por digest e policy
   versionada, para provar isolamento de filesystem/rede/ambiente, limite de output e TERM/KILL da
   árvore de processos. Sem isso, C2/C3 permanecem indisponíveis.
2. **H12b2c2 é o próximo landing:** o relay/publicador ainda precisa transportar `event_id` ao
   consumidor. H12b2c1 não publica; portanto a janela entre publicação e `ack` ainda exige a semântica
   at-least-once/deduplicação que será fechada nessa fatia.

O estado verificável e os bloqueios estão em
[verification.md](motor/specs/001-hardening-producao/verification.md). O sequenciamento operacional
continua em [docs/ROADMAP.md](docs/ROADMAP.md).

## Contribuir e segurança

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para configurar o ambiente e executar os gates. Falhas de
segurança devem seguir [SECURITY.md](SECURITY.md), sem exposição antecipada em issue pública.

## Licença

MIT — ver [LICENSE](LICENSE).
