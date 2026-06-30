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
Consumidores externos (opcionais, via MCP):  Jarvis (assistente/porteiro) · Flint (app de notas) · …
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
**núcleo** (motor + harnesses de domínio + interface própria + documentação). **Jarvis** e **Flint** são
**projetos separados** (repos próprios) que *podem* consumir a meta-fábrica como clientes — ela funciona
sozinha sem eles.

## Estrutura do repositório

```
docs/                  visão, roadmap e specs do sistema (comece por docs/LEIA-PRIMEIRO.md)
  design/              briefing da interface viva
motor/                 o kernel (pacote Python autocontido)
  motor/ tests/ exemplos/ scripts/ motor_painel/
  docs/                EVOLUCAO, ARQUITETURA-MCP, runbooks
  handoffs/            histórico de handoffs de implementação (rationale)
dev-harness/           a softwarehouse: metodologia de engenharia (a 1ª casa)
harness-hardware/      semente da vertical de hardware
harness-mecanico/      semente da vertical mecânica
```

## Começar a entender

1. **[docs/LEIA-PRIMEIRO.md](docs/LEIA-PRIMEIRO.md)** — a visão, as camadas, os princípios e o estado atual. **Leia primeiro.**
2. [docs/ROADMAP.md](docs/ROADMAP.md) — o mapa operacional Now/Next/Later.
3. [motor/README.md](motor/README.md) — como rodar e testar o motor.
4. [motor/docs/EVOLUCAO.md](motor/docs/EVOLUCAO.md) e [motor/docs/ARQUITETURA-MCP.md](motor/docs/ARQUITETURA-MCP.md) — o norte e a fronteira do motor.

## Rodar o motor (rápido)

```bash
cd motor
pip install -e ".[dev]"
pytest -q                                       # suíte sem rede (ClienteStub)
python -m motor "pesquise oportunidades de aumento de receita"   # requer um provedor de modelo
```

## Estado

Motor-core fechado e validado em run real. Fase C completa (prevenção + escalada de tier + reconciliação
na fonte em loop). Curador (auto-melhora) com fundação completa: observa, perfila por modelo, propõe por
slot e mede custo. Próximo: esquema de eventos motor→superfície e validadores determinísticos. Detalhe em
[docs/ROADMAP.md](docs/ROADMAP.md).

## Licença

MIT — ver [LICENSE](LICENSE).
