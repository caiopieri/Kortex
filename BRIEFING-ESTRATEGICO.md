# BRIEFING ESTRATÉGICO — Orquestrador (Meta-fábrica)

> **Para:** o agente dono deste projeto. **De:** estrategista (leitura de 2026-07-04: README, ROADMAP, AGENTS, harness-hardware, motor/).
> **Posição no mapa:** Núcleo 0 — o multiplicador. Todo outro projeto do fundador é produto deste. Cada hora aqui rende em todos.

## O que eu vi (avaliação honesta)

Este é, de longe, o projeto mais maduro do portfólio — e maduro de um jeito raro: motor v0.5 com Fase C completa (auto-correção com reconciliação na fonte), curador com **custo_usd real no desempate**, 48 eventos tipados com guard anti-drift, superfície MCP definida, e um red-team que **derrubou a própria evidência de RAG e refez a régua pré-registrada**. Essa última frase é o que separa engenharia de teatro. A decisão Paperclip (comprar o control-plane, construir motor+curador) também está certa: diferenciação onde há profundidade, commodity onde há acabamento.

## Insights do estrategista

1. **O maior ROI agora é o curador AGIR (fatia 3: sombra + certificação).** O livro-razão já existe; enquanto ele só observa, é contabilidade. Quando ele realoca modelo por papel/tier automaticamente, vira **economia composta** — cada run fica mais barato que o anterior. Cuidado de desenho: certificação precisa de regressão de *qualidade* junto com a de custo, senão Goodhart (o curador otimiza pra barato e a qualidade escorre pelos portões que ainda não medem bem).

2. **Formalize a realidade do rate-limit como estratégia, não como erro.** O fundador tem NVIDIA/Alibaba/HF gratuitos que rendem muito antes do 429. No roteamento papel/tier isso vira: **tier-0 gratuito como primeira tentativa em todo papel de baixo risco, escalada por portão reprovado**. `executor.indisponivel`/quota deve ser evento de 1ª classe que o curador consome — o failover por custo que já existe vira failover por custo *e* disponibilidade. É a vantagem econômica estrutural da fábrica: portões bons permitem executores ruins de graça.

3. **A WorkflowSpec é a propriedade intelectual; o LangGraph é executor.** Mantenha a spec serializável, versionável e testável sem LangGraph importado (parece já ser a direção — proteja isso com teste). Se um dia o substrato mudar (Temporal, runtime próprio), a fábrica sobrevive porque a IP está nos roteiros, portões e eventos, não no grafo.

4. **Síntese "não medida" é o próximo buraco de evidência.** Vocês mesmos anotaram. Repitam a jogada do RAG v3: régua pré-registrada, braços de comparação, critério antes do experimento. A fábrica não pode ter um passo central cuja qualidade é vibes.

5. **harness-hardware: o blueprint está certo — protejam duas coisas.** (a) O "loop físico irredutível" tratado como estado normal (respin) é a decisão mais importante do documento; não deixem nenhum otimismo futuro apagá-la. (b) A parede legal do corpus (boardviews vazados) hoje é uma nota — **elevem a política com gate de proveniência por fonte**, porque no dia em que isso virar produto (ConsertOS/Board-Master), proveniência suja contamina tudo que ela tocou.

6. **Exportem o "contrato de casa".** A fronteira motor↔casas (registry como substrato único, artefatos por referência+hash, gates em pilha barato→caro) já está decidida e é excelente. Escrevam-na como documento normativo curto que toda casa nova assina — é o que permite mecânica, jurídico e CAD plugarem sem reunião com o motor.

## Prioridade (o que provar em seguida)

1. Curador fatia 3 em modo sombra num run real → mostrar no livro-razão a economia que ele *teria* feito.
2. Tier-0 gratuito com escalada num papel de verdade (ex.: redator) → medir taxa de aprovação de portão por tier.
3. Motor 24/7 na VM da Casa Amarano (missão M2 do vault) — executor que dorme com o laptop não é executor.

## Fora de escopo agora

Interface rica própria (o painel é projeção do log — manter fino), generalizar para casas novas antes do contrato de casa escrito, fine-tuning de modelo próprio.

## Missão cumprida quando

Uma missão real (ex.: a fatia ML do sellsystem) atravessa o motor de ponta a ponta com tier-0→escalada, curador em sombra registrando a alocação ótima, e menos decisões do fundador do que o kit-processo manual exigiria — contadas no log.
