# Red-team brief — Meta-fábrica (para o Fable)

> **Seu papel: Revisor Adversarial.** Ataque, não reescreva. Para cada fraqueza, dê três
> coisas: (1) a fraqueza específica, (2) o cenário concreto que a expõe, (3) como testar/
> verificar. Ordene por severidade × probabilidade. Separe **"tenho evidência"** de
> **"suspeito"**. Sua saída é uma **lista de candidatos**, não veredito — o Arquiteto verifica
> cada um contra código/dados. Ataque também o que "todo mundo assume que está certo".
> Contexto completo: `LEIA-PRIMEIRO.md`, `PRD-META-FABRICA-reverso.md`,
> `DECISAO-ciclo-de-vida-workflow.md`, `design/BRIEF-DESIGN-interface-meta-fabrica.md`,
> `../motor/docs/EVOLUCAO.md`. Este doc é o **resumo do pacote** a atacar.

## O que a meta-fábrica é (em um parágrafo)
Um "simulador de organização": recebe um objetivo, instancia um time de papéis-agente
especialistas e roda o processo inteiro num **motor** (grafo LangGraph fixo interpretando uma
**WorkflowSpec** dinâmica), com verificação adversarial, **validadores determinísticos**, gates
e evidência. Um **curador** mede e propõe melhorias; uma **camada de conhecimento (RAG)** dá
maestria barata; uma **interface própria** vê a fábrica rodando. Software é a 1ª vertical.
Função-objetivo: minimizar tempo-até-decisão do humano e retrabalho.

## O que já está construído e validado (não é aspiração)
- Motor + **Fase C completa** (prevenção em ondas + escalada de tier + reconciliação na fonte
  em loop bounded; validada em run real cobertura reprovado→aprovado).
- **Validadores determinísticos V1** (`schema_json`/`contem`/`test`) — gate por algoritmo.
- **RAG com lift provado**: 0/3 → 3/3 num corpus que o modelo base ignora, por métrica
  determinística.
- **Curador-fundação** read-only: observa, perfila por modelo, propõe por slot (piso de
  qualidade, ciente de timeouts), livro-razão de custo (tokens+tempo+$ real).
- Roteamento provider-agnóstico + failover por custo; **48 eventos tipados** + superfície MCP.
- Suíte ~262+. Repo: github.com/caiopieri/meta-fabrica.

## As decisões que tomamos (ataque estas)
1. **Topologia travada em 2 padrões** (`fan_out_sintese`, `grafo_dependencias`=DAG). Workflow
   novo = spec nova (livre); padrão novo (topologia) = versão certificada, raro. **Não é n8n.**
2. **Ciclo de vida do workflow:** catálogo de templates versionados; autoria de workflow **é
   uma run do motor**; versão carrega evidência (= certificação); execução parcial/MVP marcada
   **não-certificada** e fora do corpus do curador; composição entre casas via artefato tipado.
3. **Guardrail da medição:** "melhor/pior" de um workflow vem de **run em sombra ou telemetria**,
   nunca de opinião do agente.
4. **Hospedagem (direção, NÃO decidida — ataque forte):** separar **plano de controle** (motor/
   orquestrador/curador — leve, 24/7 em VPS/casa via Docker) do **ambiente de execução** (pool de
   **runners** heterogêneos roteados por capacidade: macOS pro iOS, Linux pro resto, GPU pro
   pesado). Autoridade (Jarvis: dinheiro/identidade) fica separada e endurecida, de preferência
   em casa; músculo pode ir pra nuvem.
5. **Orquestrador escala** porque é **roteador sobre metadados + resumos**, não guardião de
   estado: estado mora em arquivos/catálogo/log; ele consulta, não memoriza; fractal
   (casa→run→nó, cada nível vê o digest do de baixo).
6. **Fronteira pétrea:** o motor é **músculo, não autoridade** — não decide risco/dinheiro/
   identidade (isso é do Jarvis, projeto separado). Control-plane pesado fica nas casas (reusar
   Paperclip), nunca no kernel.

## Alvos que eu (Arquiteto) já suspeito que são frágeis — confirme ou refute
- **Autoria-como-run pode ter partida a frio:** um workflow bom exige a spec estar boa, mas a
  spec é gerada por uma run que ainda não tem workflow bom. Há circularidade? Onde quebra?
- **Guardrail de sombra custa caro:** rodar em sombra toda mudança de workflow dobra custo/tempo.
  Em que ponto isso vira proibitivo e o usuário simplesmente ignora o guardrail?
- **Seleção do orquestrador vira gargalo em volume:** com muitos templates/runners/modelos, achar
  a combinação certa é um problema de ranking que depende do catálogo+curador estarem bons. Como
  isso degrada? Qual o modo de falha silenciosa?
- **"Não-certificado" pode vazar:** o modo MVP marca o run como rascunho, mas humanos reusam
  rascunho. Como um artefato não-certificado contamina decisões/treino apesar da marca?
- **Runners heterogêneos = superfície de ataque + complexidade operacional:** um agente sempre-
  ligado com ferramentas, rede e credenciais. Onde isso fura (segurança, custo, uptime)?
- **Composição entre casas sem contrato forte:** "artefato tipado com proveniência" é fácil de
  dizer. Que tipo de inconsistência atravessa a fronteira mesmo com tipo declarado?
- **Determinístico vs. LLM:** os validadores determinísticos cobrem só schema/contém/teste. Que
  fração das "verdades" que importam NÃO é capturável assim, criando falso conforto?
- **Risco-mãe do projeto:** largura sobre profundidade. Estamos adicionando muita capacidade
  (board, editor, catálogo, runners, curador) validada só em missão-brinquedo (CSV→JSON). Qual a
  evidência de que isso aguenta um projeto real?

## Perguntas abertas onde sua visão de fora vale mais
- A separação plano-de-controle / runners é a abstração certa, ou há um acoplamento que ela
  esconde?
- O curador "propõe, humano aprova" escala, ou o humano vira o gargalo que a fábrica queria
  eliminar?
- A tese central — "modelo pequeno especialista bate o generalista em custo+qualidade numa
  tarefa estreita" — ainda **não** foi provada. Qual o teste mais barato que a refutaria cedo?

## Como entregar
Lista priorizada. Cada item: fraqueza · cenário que a expõe · como testar. Marque o que é
evidência vs. suspeita. Não precisa ser gentil; precisa ser falsificável.
