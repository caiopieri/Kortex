# Harness Mecânico

Workflow agêntico que **recebe um pedido e entrega uma peça mecânica desenhada, simulada em toda a física aplicável, com tolerâncias e com o pacote completo de manufatura** — sob uma diretiva primária: nunca liberar peça com erro silencioso.

Roda **sobre o motor** (`../motor`). Não espelha o dev-harness (software) nem o harness hardware — tem workflow próprio. No futuro conversa com eles por contrato de fronteira para montar projetos inteiros.

> **Norte:** peça simples → submontagem → **CNC 5-eixos de precisão** (BOM + medidas + manual) → **armadura Homem de Ferro** (santo graal: integra hardware+software+mecânica).

---

## Por onde ler (ordem)

1. **[[00-BLUEPRINT]]** — a arquitetura: diretiva primária, mapa de estados (pedido → pacote), os três eixos (geometria/intenção/física), reconciliação V&V, trajetória de maturidade M0–M∞, toolchain, fronteira inter-harness.
2. **[[01-CONSTITUICAO-MECANICA]]** — a lei: 11 artigos não-negociáveis que todo run obedece.
3. **[[02-REQUISITOS-AO-MOTOR]]** — o que o motor precisa ganhar (curto: 1 bloqueante + 1 útil + 3 futuros). **Para o agente do motor.**

## Estrutura da pasta (mapa de construção)

```
harness-mecanico/
├── README.md                     ← você está aqui
├── 00-BLUEPRINT.md               ← arquitetura (o como e o porquê)
├── 01-CONSTITUICAO-MECANICA.md   ← a lei (o que nunca violar)
├── 02-REQUISITOS-AO-MOTOR.md     ← o que pedir ao motor (verificado no código)
├── corpus/                       ← [A construir] conhecimento consultável (materiais, peças-padrão, fornecedores, processos)
├── ferramentas/                  ← [A construir] entidades de ferramenta do Registry (.md) — os nós determinísticos
└── specs/                        ← [A construir] WorkflowSpecs por degrau (M2 bracket primeiro)
```

Cada subpasta tem um `README.md` que especifica, **com precisão, o que o agente construtor deve produzir** — porque o desenvolvimento é feito por outros agentes que precisam conhecer o alvo sem ambiguidade.

## Status (v0 — arquitetura travada, construção a iniciar)

| Item | Status |
|---|---|
| Arquitetura (blueprint, constituição) | ✅ definida |
| Requisitos ao motor (verificados) | ✅ escritos — `MR-1` é o bloqueante a passar ao agente do motor |
| Toolchain (build123d · Gmsh · CalculiX · OpenFOAM · analítico · FreeCAD-TechDraw) | ✅ decidido (direção) |
| Corpus / ferramentas / specs | ⬜ a construir (ver READMEs das subpastas) |
| 1ª WorkflowSpec M2 validada contra o schema | ⬜ próximo passo concreto e falsificável |

## Ordem de construção recomendada

1. **Passar `02-REQUISITOS-AO-MOTOR.md` ao agente do motor** — implementar **MR-1** (timeout configurável) destrava qualquer solver real.
2. **`specs/M2-bracket.json`** — a 1ª WorkflowSpec real (bracket sob carga), validada contra o schema do motor **sem rodar física**. Prova a premissa "M2 roda hoje".
3. **`ferramentas/`** — as entidades que a spec M2 referencia: `cadquery-runner`, `gmsh-mesher`, `calculix-solver`, `reconciliation-checker`, `dfm-linter`, `mass-props`, `clash-detector`.
4. **`corpus/`** — material library + perfil de fornecedor JLC (entidade versionada) + peças-padrão.
5. **Rodar M2 ponta-a-ponta** em ambiente isolado → anotar atrito real → MR-2.

## Convenções

- **Idioma:** docs em PT-BR; nomes de artefato/ferramenta/arquivo em inglês (atravessam a fronteira com o hardware).
- **Padrão de engenharia:** ISO (1101 / 2768 / 286) por default; ASME Y14.5 quando o destino exigir (Artigo 11).
- **Fornecedor de referência:** JLC, como entidade versionada e datada (Artigo 5).
