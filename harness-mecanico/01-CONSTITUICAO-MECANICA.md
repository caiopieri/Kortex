# Constituição Mecânica v0

> A **lei** do harness mecânico — os artigos não-negociáveis que toda execução obedece, de M2 à armadura. Análogo em espírito ao `security-DoD` do dev-harness, mas nativo da mecânica.
> Onde o Blueprint ([[00-BLUEPRINT]]) descreve *como* o harness pensa, esta constituição define *o que ele nunca pode violar*. Em caso de conflito entre velocidade e um artigo, **o artigo vence** — e a violação para a execução, não vira "warning".

---

## Artigo 1 — Nenhuma peça com erro silencioso (Diretiva Primária)

Nenhuma geometria é liberada para fabricação enquanto sua física não tiver sido **corroborada por uma checagem independente** ([[00-BLUEPRINT|§4.1]]). Confiança na mecânica é inegociável, mesmo que custe mais simplicidade *ou* mais complexidade. Simplicidade e complexidade são preços aceitáveis da confiança; **confiança nunca é a variável de ajuste.**

Consequência dura: "o solver deu PASS" **não** é prova. Prova é PASS + corroboração independente + FS por modo de falha. Sem isso, o estado é *não-validado*, não *aprovado*.

## Artigo 2 — A reconciliação é obrigatória e dura

Todo resultado de simulação passa pelo gate de reconciliação V&V antes de qualquer gate humano ou doc de manufatura:

- **Estimativa independente** existe e concorda dentro da tolerância declarada (analítico para peça com fórmula fechada; equilíbrio global + convergência de malha + validação cruzada para peça orgânica).
- **Convergência de malha** verificada — uma tensão que cresce com o refino é singularidade, não resultado. Singularidade nunca conta como FS.
- **FS verificado por modo de falha** (escoamento, fadiga, flambagem, deflexão), nunca como número único.

Reprovou a corroboração → **o modelo é suspeito**, e a saída é reabrir o modelo (contorno/malha/caso de carga), não "ajustar a peça até passar".

## Artigo 3 — Escopo de física antes de geometria

Nenhuma simulação roda sem que o **escopo de física** tenha sido decidido e registrado: quais modos de falha importam para esta peça, neste ambiente, sob estas cargas. O escopo é proposto por um modelo-validador e tratado como **hipótese a falsificar**, não como verdade. Confiança baixa no escopo → escala ao humano (gate opcional, mas o gatilho de escalação é obrigatório). Analisar o modo de falha errado é considerado erro silencioso (Artigo 1).

## Artigo 4 — Tolerância é decisão de projeto, alocada de um orçamento

A peça é uma **distribuição**, não uma geometria nominal. Toda peça tem tolerâncias atribuídas **desde o início** e é simulada/verificada como distribuição (cadeia de tolerâncias), não só no nominal.

Regra de alocação: **a tolerância mais folgada que a função ainda permite** — apertada só onde o cálculo prova necessidade (ajuste, vedação, alinhamento). Folga é barata e amplia fornecedores; aperto custa e restringe. O perfil de intenção ([[00-BLUEPRINT|§3.2]]) calibra o ponto. (Tier protótipo *pode* relaxar a cadeia de tolerâncias por velocidade — exceção explícita, nunca default.)

## Artigo 5 — DFM contra a capacidade de um fornecedor real, versionada

Manufaturabilidade é verificada contra o **envelope de capacidade publicado de um fornecedor concreto** (default: JLC — CNC, 3DP, chapa, injeção), não contra regras genéricas. Cada perfil de fornecedor é uma **entidade versionada e datada** no corpus; toda peça registra **contra qual versão** foi validada. Trocar de fornecedor ou versão = revalidar, nunca herdar silenciosamente.

## Artigo 6 — Rating de manufaturabilidade é entregável obrigatório

Toda peça sai com um **veredito de risco de fabricação** explícito: classe de máquina/processo recomendada e as features que puxam o risco. Ex.: *"baixo risco — tolerância padrão do fornecedor, qualquer CNC 3-eixos, muitos fornecedores"* vs. *"alto risco — feature X exige ±0.01 mm / 5-eixos / inspeção dedicada"*. O usuário decide com o risco na mão, nunca às cegas.

## Artigo 7 — Gate humano antes do irreversível

Nenhuma ordem de fabricação é disparada e nenhum recurso irreversível é comprometido sem **gate humano explícito**. O harness *prepara* a ordem (arquivos + orçamento + BOM); o humano aprova o gasto. Fabricar é o passo caro e irreversível — é onde o engenheiro tem que olhar. **Auto-deploy de fabricação é proibido.**

## Artigo 8 — O loop físico é irredutível

Os gates virtuais (FEA/CFD/cadeia de tolerância) existem para **empurrar o erro para antes da fabricação** — nunca para eliminá-la. **Respin** (nova rodada após bancada) é estado **normal**, não falha. O resultado de bancada re-entra no loop como **dado estruturado** (idealmente correlacionado à malha no ponto da falha), não como prosa. Prometer "validado, dispensa teste" viola este artigo.

## Artigo 9 — Comunicação por referência, nunca por conteúdo pesado

Geometria, malha e campos de resultado trafegam como **referência de artefato** (caminho + tipo + hash) no workspace por execução — nunca binário ou string longa embutida no prompt de um modelo. Artefatos textuais versionados em git; binários referenciados por caminho+hash. (O motor já impõe isto via `ref_artefato`.)

## Artigo 10 — Transparência: raciocínio e conclusões visíveis

O processo de pensamento e a conclusão de **cada gate** ficam visíveis ao orquestrador: o quê foi decidido, com qual número, e por quê (ex.: *"alumínio 6061-T6 porque X; FS=2.1 no pior caso da cadeia de tolerâncias"*). Materializa-se no event log JSONL do motor + um artefato legível de *rationale* por gate. Nível default: **resumo de decisão por gate**, com as alternativas descartadas disponíveis sob demanda (não despejadas por padrão — Artigo implícito de não afogar o revisor em ruído).

## Artigo 11 — Padrões de engenharia declarados

Default de cotação e tolerância: **ISO** (GD&T ISO 1101, tolerâncias gerais ISO 2768, ajustes ISO 286) — casa melhor com fornecedor internacional. ASME Y14.5 é opção quando o destino exigir. O padrão usado é sempre **registrado no pacote de manufatura**, nunca implícito.

---

## Onde isto pode dar errado

- Constituição vira burocracia que ninguém lê. Antídoto: ela é **gate executável** onde dá (Artigos 2, 5, 6, 7 viram nós-ferramenta determinísticos), não só prosa. O que não é executável (Artigo 3, escopo) tem gatilho de escalação.
- Rigor demais no degrau errado mata a velocidade (peça de protótipo Econômico não precisa de CFD). O **perfil de intenção** e o **tier** modulam o *custo* da conformidade — mas nunca desligam o Artigo 1.
- Default ISO pode atritar se um projeto futuro for US/ASME. É default, não dogma — trocável por projeto, desde que registrado (Artigo 11).
