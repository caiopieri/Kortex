# PARECER DO ARQUITETO — a visão fundadora vs. o sistema construído

> **Para:** Caio (fundador) e os agentes do projeto. **De:** Claude (arquiteto-verificador),
> após leitura de README, LEIA-PRIMEIRO, ROADMAP, BRIEFING-ESTRATEGICO e conversa direta com o
> fundador sobre a aspiração original (2026-07-06). Par do `BRIEFING-ESTRATEGICO.md` — aquele é a
> leitura de um estrategista externo; este é o veredito de quem verifica o código.
> Mantenha vivo: quando a realidade mudar, atualize ou apague. Documento desatualizado mente.

---

## 1. A visão fundadora (registrada com fidelidade)

Kortex (nome pretendido da meta-fábrica): um sistema que produz **toda a parte intelectual de
qualquer coisa** — software, PCB, peça mecânica, máquina de precisão — com a qualidade de uma
empresa profissional inteira, operado por uma pessoa. O caminho: **processo industrializado**
(gates, evidência, verificação) executado por **muitas IAs especialistas, as menores possíveis
para a qualidade exigida**, treinadas e realocadas continuamente por um **curador**, alimentadas
por uma **data-house**, rodando em hardware acessível (casa + VPS + GPU sob demanda), consumidas
por um **Jarvis** que é cliente — não cérebro central.

Duas intuições fundadoras, ambas corretas e já travadas na arquitetura:

1. **O processo garante a qualidade, não o modelo.** Depender de uma IA é perigoso (alucina, se
   perde); depender de um processo que audita a IA é engenharia. → gates, verificação adversarial,
   validadores determinísticos, reconciliação.
2. **Jarvis não é um modelo onisciente; é um chamador de estrutura.** → decisão #5 (músculo, não
   autoridade), fronteira MCP.

## 2. Veredito estrutural

**A redução da visão para o sistema está correta.** O que existe (motor v0.5 + Fase C + curador
read-only + validadores V1 + 48 eventos + MCP + RAG com lift de recuperação provado) é uma
implementação fiel e disciplinada do núcleo da visão. As decisões grandes — comprar o
control-plane (Paperclip), spec como dado e grafo fixo, gate antes de flywheel, software como
primeira vertical, data-house separada guiada por gap map, workflows dinâmicos como subconjunto de
templates certificados — resistem ao teste da aspiração e **não devem ser relitigadas**.

## 3. A hipótese dos especialistas — correção de leitura e estratégia técnica

### 3.1 Correção da leitura da Frente E (registro honesto)

A Frente E (pequeno+RAG 2/5 < piso 4/5) **falsificou o atalho** — "modelo pequeno cru + RAG
substitui um grande hoje" — e **não a tese** — "modelo pequeno treinado + equipado + processo
chega lá". A tese nunca foi testada: não existe dataset de treino, fine-tune nem eval por papel.
Leituras anteriores (inclusive minhas) que usaram a Frente E como evidência contra a tese estavam
erradas de escopo. A tese permanece **aberta e testável**, não negada.

### 3.2 A formulação honesta da tese

- A meta correta não é "modelo nível frontier", é **"output nível frontier com o menor modelo que
  passa no gate"**. A maestria é do sistema (nó + verificação + retry + escalada de tier — que já
  existe no motor), não do nó isolado. Gates bons permitem executores fracos; a escalada cobre
  quando o pequeno não basta. Isso já está no BRIEFING (insight 2) e é a vantagem econômica
  estrutural da fábrica.
- Um especialista 14–32B bem treinado chega a "executor de produção muito bom em tarefa escopada"
  (a literatura de destilação e os modelos de código pequenos sustentam isso). Ele não chega à
  engenharia autônoma aberta de um frontier — e não precisa: o sistema cobre a diferença.
- "Menor possível" não é dogma de tamanho: se a tarefa justificar 20B em vez de 8B, usa-se 20B.
  Eficiência = o menor que passa no piso de qualidade, decidido por eval, não por opinião.

### 3.3 Pesos vs. RAG (a divisão de trabalho canônica)

- **Pesos = habilidade** (lógica, decomposição, idiomas de linguagem, padrões). Vem do
  **pré-treino** — que terceiros já pagaram. **Nunca se ensina uma linguagem via fine-tune**;
  escolhe-se uma base já pré-treinada em código (ela já sabe Python, C e dezenas de outras).
- **Fine-tune = os últimos 10%**: o nosso processo, formato de spec, uso das nossas ferramentas,
  convenções da casa, modos de erro. LoRA/QLoRA, não full fine-tune.
- **RAG = fato volátil**: versão de lib, API que mudou, docs internas, o codebase do projeto.
  A data-house mantendo documentação atualizada existe exatamente para isso — se o Python mudar,
  muda-se o índice, não os pesos.
- **Seleção de base é 90% do jogo.** Cenário "preciso de C": não é agente novo do zero nem lógico
  puro com docs — é a mesma base de código + RAG das docs + eval em C para provar.

### 3.4 Serving em hardware acessível: uma base, N adaptadores

LoRA resolve a economia de VRAM da visão: **uma base (~14–32B) carregada uma vez + adaptadores
LoRA trocáveis por papel** (centenas de MB cada). Dezenas de especialistas pelo custo de memória
de um modelo. "Não tenho 1TB de VRAM" deixa de ser limitação. QLoRA de 14–32B cabe nas 12h/mês de
B200 do fundador; artefatos de treino e modelos ficam no Hugging Face (storage), não na máquina.

### 3.5 O que falta de verdade antes do primeiro fine-tune (não é GPU)

1. **Eval held-out por papel** — a régua. Sem ela, não se sabe se o fine-tune melhorou ou só
   mudou. É o mesmo princípio pétreo nº 3 (gate antes de flywheel) aplicado ao treino.
2. **Dataset ouro** — já sendo colhido de graça (princípio "colher agora, treinar depois": todo
   run loga `spec→plano→código→evidência→correção`; só dado gate-verificado treina).

**Escada falsificável do primeiro especialista** (cada degrau barato e reversível):
escolher UM papel de grader barato e volume real → medir a base crua nele (baseline) → QLoRA com
dado gate-verificado → re-medir no held-out → promover só se bater o titular em qualidade E custo
(disciplina (b)/(c) do Later, inalterada). Treino é uma run gated do próprio motor.

## 4. O gradiente do grader (o mapa real da ambição física)

"Fabricar qualquer coisa" tem uma ordem imposta pelo custo de verificação, não pela vontade:

| Vertical | Grader | Custo |
|---|---|---|
| Software | compila/testa/lint/SAST | segundos, ~grátis |
| Hardware digital | simulação (Verilog/testbench) | barato |
| **PCB** | **ERC/DRC/SPICE/SI (KiCad etc.)** | **barato e determinístico — melhor porta de entrada física do que "CAD genérico"** |
| CAD mecânico | FEM ajuda; tolerância/manufaturabilidade | caro |
| Físico | a realidade (respin, refugo) | o mais caro |

Consenso com o fundador: a indústria chega a **2–3 respins via simulação, não a zero** — a meta é
respin barato e raro, e o ferramental existe. O blueprint do harness-hardware já trata o loop
físico como estado normal; proteger essa decisão. A armadura e a impressora SLM moram no fim do
gradiente: chegam por subida de degrau, não por salto.

## 5. Resolução do conflito de prioridade (ROADMAP × BRIEFING)

ROADMAP dizia interface primeiro; BRIEFING dizia curador fatia 3. Posição deste parecer:

1. **Gate externo de CI** (Fase 4 p1, estreia no Logisti) — o gate hoje é auto-reportado pelo
   agente; toda evidência que o curador vai usar nasce de fonte que pode se enganar. É o tijolo
   mais barato e destrava a confiança em tudo. Gate antes de flywheel é princípio pétreo.
2. **Curador fatia 3** (sombra + certificação) — o primeiro momento em que a fábrica se melhora
   com freio. Coração da aspiração; usa a evidência que o passo 1 tornou confiável.
3. **Interface viva P0, fina** — projeção do log; nasce mínima (board + Caixa do Fundador),
   engorda depois.
Em paralelo, como experimento barato: **item 13 do red-team** reformulado pela §3.5 — é a hipótese
estrutural da visão e custa pouco começar (a régua, não o treino).

## 6. Infra 24/7 (registrado, sem compromisso de construção)

Escada acordada: hoje local+manual → VPS free 24/7 como plano de controle (a máquina do fundador
como runner acionado) → hardware melhor em casa (ex.: Mac Studio) quando justificar. GPU sob
demanda (B200 12h/mês) para treino; HF para storage de datasets/modelos. Nada disso bloqueia o
Now; "executor que dorme com o laptop não é executor" vira real quando a VPS entrar.

## 7. Onde este parecer pode estar errado

- **A tese dos especialistas pode falhar mesmo bem executada** — se o held-out mostrar que o piso
  de qualidade exige modelos médios em quase todo papel, a fábrica segue funcionando (roteamento
  para modelos maiores/assinaturas), mas fica mais cara e menos "em casa". O parecer trata isso
  como resultado aceitável, não como fracasso do sistema.
- **O gradiente do grader pode ser mais íngreme do que parece** — simulação de PCB/mecânica cobre
  menos do que a indústria aparenta (know-how tácito de DFM não está nos softwares). Mitigação:
  entrar pelo degrau com grader determinístico (PCB/ERC/DRC) e medir taxa de respin.
- **A priorização da §5 pode estar errada se o Logisti atrasar** — o gate CI estreia lá; se a
  fornalha esfriar, a fatia 3 do curador pode subir para 1º sem quebrar o argumento (a sombra
  também gera evidência confiável, só mais devagar).
- **Risco permanente inalterado:** largura sobre profundidade. Este parecer adiciona zero frentes
  novas — só ordena as existentes.
