# Harness Mecânico — Blueprint v0

> **Base:** roda **sobre o motor** (`Orquestrador/motor` — grafo LangGraph fixo que interpreta uma WorkflowSpec dinâmica). Não importa o grafo de ninguém; fala por artefatos e contrato.
> **Não espelha** o dev-harness (software) nem o harness hardware. A mecânica tem workflow próprio porque sua verdade vem de resolver física, não de julgar texto nem de checar geometria de placa.
> **Documentos-irmãos:** [[01-CONSTITUICAO-MECANICA]] (a lei) · [[02-REQUISITOS-AO-MOTOR]] (o que o motor precisa ganhar).

---

## 0. Norte (por que isto existe)

A meta-fábrica tem um santo graal declarado: **um dia produzir uma armadura estilo Homem de Ferro** — porque integra hardware, software e, sobretudo, **mecânica** nos níveis mais altos. Antes dela, um degrau tangível: **projetar e entregar o pacote completo (BOM + medidas + manual de montagem) de uma CNC 5-eixos de precisão nível alemão**, montável por um humano seguindo o que o harness entrega.

Esses dois alvos definem a *trajetória*, não o ponto de partida. Começamos por **peça única simples** e endurecemos degrau a degrau (§5). Toda decisão de arquitetura é tomada apontando para a trajetória, mas validada no degrau atual.

**O que o harness faz, em uma frase:** recebe um pedido e entrega uma peça **desenhada, simulada em toda a física aplicável, com tolerâncias, e com o pacote de manufatura** — sem nunca liberar uma peça com erro silencioso ([[01-CONSTITUICAO-MECANICA|Artigo 1]]).

---

## 1. Por que a mecânica é estruturalmente diferente

- **O "verifier" é um solver de física, não uma rubrica nem um DRC.** A verdade de "essa peça aguenta?" vem de resolver estática/fadiga/térmica/modal/fluido — não de julgamento de modelo.
- **O erro mais caro é silencioso e mora nas condições de contorno, não na geometria.** O FEA quase sempre *roda* e devolve um número plausível; o perigo é a singularidade num canto vivo, o apoio errado, o caso de carga faltando. "FEA passou, FS>2" é a ilusão que fabrica peça que quebra na bancada.
- **Existe um degrau analítico que vira a melhor arma.** Resolver por fórmula fechada *antes* do FEA dá uma estimativa independente — o **oráculo** que valida (ou condena) o modelo numérico. É o diferencial técnico do harness.
- **Manufatura é intrínseca à geometria, não um porte a jusante.** Parede, saída, acesso de ferramenta e tolerância moldam a própria peça. E o destino é um fornecedor concreto (JLC), cuja capacidade vira gate determinístico.
- **A peça é uma distribuição, não uma geometria.** Tolerância e cadeia de tolerâncias são primeira classe desde o início.

---

## 2. Diretiva primária

**Nunca liberar para fabricação uma peça com erro silencioso.** Confiança na mecânica é inegociável, mesmo que custe mais simplicidade *ou* mais complexidade. Simplicidade e complexidade são preços aceitáveis da confiança; confiança nunca é a variável de ajuste. Detalhada em [[01-CONSTITUICAO-MECANICA]].

---

## 3. Os três eixos que parametrizam cada peça

O intake guiado infere o máximo e só pergunta o indecidível. Três eixos dirigem todo o resto:

### 3.1 Classe de geometria (roteador explícito, cedo)
`prismática/usinável` · `chapa` · `fundida/injetada` · `orgânica/otimizada`.
Essa única escolha dirige: modo do modelador (paramétrico vs. topológico), tier de reconciliação (§4), regras de DFM e processo de fabricação.

### 3.2 Perfil de intenção (eixo de prioridade)
- **Econômico / Fabricabilidade** — folga máxima, processo simples, muitos fornecedores. Barato e fácil.
- **Balanceado / Confiável** — o modo "indústria automotiva": qualidade alta sem complexidade cara. Confiável e simples de produzir.
- **Alta-Performance / Precisão** — "engenharia alienígena": otimização topológica, física no limite, tolerância apertada só onde precisa. Melhor dos mundos.

O perfil dirige **alocação de tolerância** (a mais folgada que a função permite por padrão; apertada só onde o cálculo prova necessidade) e **quão agressiva** fica a otimização. A Diretiva Primária vale igual nos três — muda só *como se compra a confiança*: no Econômico, com simplicidade e margem; no Alta-Performance, com física e verificação pesada.

### 3.3 Escopo de física (a decisão que nenhum solver pega)
Quais físicas importam: carga cíclica → fadiga; temperatura → térmica/fluência; esbelto → flambagem; rotativo/excitado → modal; fluido → CFD. **Decidido por um modelo-validador por padrão, com gate humano opcional.** O escopo inferido é tratado como *hipótese a falsificar*, não como verdade; escala ao humano quando a confiança é baixa.

---

## 4. O mapa de estados (do pedido ao pacote)

```
PEDIDO
  │
  ▼
INTAKE GUIADO ─── infere tudo que dá; pergunta só o indecidível (perfil de intenção,
  │                função-objetivo se não for "mínima massa sob FS+envelope", restrições)
  ▼
CLASSIFICAÇÃO + ESCOPO ─── classe de geometria + quais físicas importam
  │                         ← VALIDADOR-MODELO (gate humano opcional)
  ▼
DIMENSIONAMENTO ANALÍTICO ─── fórmula fechada → 1ª geometria + valor ESPERADO
  │                            (o oráculo que vai validar o FEA)
  ▼
MODELAGEM ─── paramétrica (build123d)  OU  topológica/generativa (se Alta-Performance)
  │            → reconstrução em sólido manufaturável, se orgânica
  ▼
CHECAGENS BARATAS ─── massa/CG, estanqueidade, interferência no envelope (clash detection),
  │   (ferramentas)     DFM contra o fornecedor (JLC) → RATING DE MANUFATURABILIDADE preliminar
  ▼
TOLERÂNCIAS ─── alocação dirigida pela intenção (folgada↔apertada) + cadeia de tolerâncias
  │              → simula a peça REAL (distribuição), não a nominal
  ▼
SIMULAÇÃO ─── malha (+gate de qualidade) → solvers por física escopada
  │   (ferramentas)   (estática/modal/térmica/fadiga/CFD)
  ▼
RECONCILIAÇÃO V&V ─── O GATE NATIVO DA MECÂNICA (§4.1)
  │
  ▼
GATE DO ENGENHEIRO (humano) ─── antes de comprometer doc / fabricação
  │
  ▼
PACOTE DE MANUFATURA ─── desenho GD&T + tolerâncias + spec de material + acabamento +
  │                       BOM + folha de processo + plano de inspeção + RATING final
  ▼
LOOP FÍSICO ─── fabricar (JLC) + testar em bancada → resultado re-entra. Respin = normal.

⟂ TRANSVERSAL: trilha de raciocínio + conclusões visíveis em cada gate (event log JSONL do
   motor + artefato legível de rationale por gate).
```

### 4.1 Reconciliação V&V — onde o erro silencioso morre
Princípio invariante: **nunca confiar num único número de FEA.** Sempre corroborar com uma checagem independente. O *tipo* de corroboração escala pela classe de geometria:

- **Peça tratável por fórmula:** oráculo analítico — `|FEA − analítico| / analítico ≤ tolerância`. Mais barato e mais forte.
- **Peça orgânica / topológica:** pilha de V&V — **equilíbrio global** (reações fecham com cargas aplicadas, sempre, independente de malha), **convergência de malha** (refina h; a grandeza estabiliza? então é tensão real, não singularidade), **validação cruzada** (formulações/malhas diferentes concordam), **bound por envelope simplificado**, e **teste físico antecipado**.

Em ambos os casos, o FS é verificado **por modo de falha** (escoamento, fadiga/limite de resistência, flambagem, deflexão), nunca como número único. Não passou a corroboração → o **modelo** é suspeito, não a peça. (Estas checagens são, em geral, **nós-ferramenta determinísticos** — exit 0/1 — exatamente o que o motor já gateia.)

### 4.2 A métrica de sucesso
Não é "acertar de primeira". É **convergir em poucas iterações sob a pilha de gates**, com respin físico contado como parte do ciclo. Quem se ilude que a simulação fecha a conta projeta peça que passa no virtual e falha na bancada.

---

## 5. Trajetória de maturidade (degraus)

Endurece por **complexidade física + compromisso de fabricação** — não copiando ninguém.

| Degrau | Produz | Física | Roda no motor? |
|---|---|---|---|
| **M0** corpus & ingestão | materiais, peças-padrão, perfis de fornecedor, regras de processo | — | ✅ hoje (`fan_out_sintese`) |
| **M1** requisitos da peça a partir do prompt | cargas, envelope, material, processo, FS-alvo, vida → artefato de requisitos | analítica | ✅ hoje |
| **M2** peça única, estática | param → malha → FEA linear → reconciliação → desenho+BOM | estática + reconciliação | ✅ hoje (`grafo_dependencias`)¹ |
| **M3** multifísica / não-linear | fadiga, térmica, modal, contato, CFD | acoplada | ⚠️ solver pesado + MR-1/MR-2 do motor |
| **M4** submontagem + cadeia de tolerâncias | clash detection inter-peça, tolerância estatística, DFM-produção | + montagem | ⚠️ + loop físico |
| **M5** máquina (CNC 5-eixos) | BOM completo, medidas, manual de montagem | + cinemática/precisão | objetivo intermediário |
| **M∞** armadura | integração hardware+software+mecânica | tudo | santo graal |

¹ A afirmação "M2 roda hoje" é falsificável: o 1º passo concreto é validar uma WorkflowSpec M2 real contra o schema do motor (ver [[02-REQUISITOS-AO-MOTOR]] §"O que já funciona"), antes de qualquer física.

---

## 6. Toolchain (espinha dorsal)

Escolhida para casar 1:1 com o motor (cada etapa = subprocess determinístico, artefato versionável por caminho+hash) — o mesmo motivo que o hardware scriptou o `pcbnew` em vez de clicar.

- **Geometria:** **build123d** (ou CadQuery) — paramétrico, kernel OCCT, fonte Python em git, exporta STEP/STL. É o que torna a modelagem uma *função de parâmetros* iterável.
- **Malha:** **Gmsh** (scriptável, com controle de qualidade — alimenta o gate de malha).
- **FEA:** **CalculiX** (.inp estilo Abaqus; estática, modal, térmica, flambagem, não-linear).
- **CFD/térmica-fluido:** **OpenFOAM**, só quando o degrau exigir.
- **Camada analítica:** Python (NumPy/SymPy + fórmulas de Roark/Shigley codificadas) — pré-dimensionamento **e** oráculo de reconciliação. O coração do harness.
- **Otimização topológica:** SIMP / generativo dirigido pela própria física, **dentro de um nó-ferramenta** (o otimizador itera internamente; o motor vê um artefato entra / sai). Inclui a etapa de 1ª classe de **reconstrução** malha→sólido manufaturável.
- **Desenho 2D / GD&T:** **elo fraco do aberto.** Estratégia: **FreeCAD headless (TechDraw)** como ferramenta pontual, ou gerar um *spec de desenho* estruturado (vistas, cotas, GD&T como dado) + finalização semi-automática. Honestidade registrada: pode ser o primeiro gargalo a exigir mão humana.

**Idioma:** docs em PT-BR; nomes de artefato/ferramenta/arquivo em inglês (`enclosure-constraints.json`, `safety-factor-check`) porque atravessam a fronteira com o hardware, que já cravou esses nomes.

---

## 7. Fronteira inter-harness (microserviço, não monólito)

No futuro, mecânica + hardware + software produzem um projeto inteiro. Para não acoplar, os harnesses **falam por artefatos numa fronteira declarada em disco**, nunca importam o grafo um do outro. O contrato já foi metade-definido pelo hardware:

- **Mecânica consome do hardware:** `board-outline.dxf`, `connector-placement.json`, `mounting-holes.json`, `thermal-envelope.json`.
- **Mecânica publica para o hardware:** `enclosure-constraints.json` (dimensões, zonas de exclusão, furos).

**Mecanismo concreto: o Envelope Espacial Compartilhado.** Um artefato 3D estático (chassi, escaneamento, enclosure) contra o qual todos os harnesses rodam **clash detection** (nó-ferramenta determinístico) antes de comprometer geometria. É o que impede hardware e mecânica de invadirem o mesmo espaço. O manifesto formal de interface só é redigido quando o 1º projeto combinado aparecer — antes disso seria especular sobre interface sem cliente.

---

## 8. Princípios de integração com o motor (herdados, não relitigados)

- **Comunicação inter-nós por referência, nunca binário/string no prompt.** Metadados JSON apontam IDs de arquivo no workspace por execução (`runs/<run_id>/artefatos/`). O motor já impõe isso (`ref_artefato`, artefato por caminho+hash). 
- **Ferramentas determinísticas são entidades do Registry** (`.md` com `tipo: ferramenta`, `comando`, `interpreta_saida`, `produz`) — o mesmo substrato dos modelos-executores. O nó-ferramenta resolve o executável consultando o Registry.
- **Três tipos de gate, não se confundem:** verifier-modelo (rubrica) · gate determinístico de máquina (reconciliação, DFM, clash) · gate do fundador (`interrupt`, humano). O harness mecânico usa os três.

---

## 9. Onde isto pode dar errado

- **Mirar um fornecedor específico (JLC) pode esconder suposições.** Se a capacidade do fornecedor virar número solto no código e eles mudarem o processo — ou você trocar de fornecedor — o DFM fica desatualizado em silêncio. Antídoto: capacidade do fornecedor é **entidade versionada e datada** no corpus; o harness diz contra qual versão validou.
- **O perfil "Econômico" é onde o erro silencioso mais se esconde** (a tentação de pular física "porque é simples"). A Diretiva Primária vale igual: peça simples ainda passa pela reconciliação — só que a corroboração é mais barata (em geral fecha no analítico, sem FEA pesado). Simplicidade reduz o *custo* da confiança, nunca a dispensa.
- **Otimização topológica + reconstrução + DFM-aditivo é o caminho mais ambicioso e o mais frágil em ferramental aberto.** Factível, mas é onde mais vou precisar ser honesto sobre o "quase-manufaturável" que ainda pede mão humana.
- **"Calcular tudo certo desde o início" não elimina o gate físico.** Tolerâncias-desde-o-início reduzem respins; não zeram a bancada. Prometer "sai pronto sem testar" seria mentira.
- **Transparência total tem custo de ruído.** Expor cada alternativa descartada em cada gate faz você parar de ler — e aí a transparência vira opaca por excesso. O nível certo é o que você realmente revisa.
