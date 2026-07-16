# INVARIANTES — motor

Este documento é o alvo da auditoria final. Cada linha abaixo é uma promessa que
o motor deve sustentar; quando a suíte não prova a promessa, a linha fica marcada
como dívida em vez de virar confiança verbal.

## Kernel

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| K1 | Nada roda sem roteiro: a execução parte de uma `WorkflowSpec` válida, fornecida pelo usuário ou gerada e validada pelo planner. | `motor/motor/spec.py::WorkflowSpec._consistencia`; `motor/motor/grafo.py::construir_grafo.planner` | `motor/tests/test_spec.py::test_exemplo_valido`, `test_versao_nao_suportada`, `test_sem_subagentes`, `test_rubrica_vazia` |
| K2 | Toda ação relevante produz evento auditável. Eventos comuns vão direto ao JSONL; eventos monetários nascem em outbox durável e são anexados antes do sucesso normal da CLI/serviço. Crash pode deixá-los pendentes para redelivery. | `motor/motor/eventos.py::LogEventos.evento`; `motor/motor/orcamento.py::publicar_um_pendente`; drains em `motor/motor/__main__.py` e `servico.py` | `motor/tests/test_eventos_schema.py::test_schema_cobre_todos_eventos_emitidos_no_codigo`; `test_hardening_h12b3.py`; `test_hardening_h12b4f_config.py::test_cli_redelivera_outbox_apos_lease_sem_ack` |
| K3 | Nada cruza fronteira de workflow sem portão: executor passa por verifier, validador determinístico ou gate de cobertura antes da síntese. | `motor/motor/grafo.py::construir_grafo.subagente`; `executar_validador`; `avaliar` | `motor/tests/test_grafo.py`; `motor/tests/test_validadores_deterministicos.py::test_schema_json_reprova_e_vira_lacuna_do_alvo`, `test_reconciliacao_refaz_alvo_validado_nao_so_o_validador` |
| K4 | A fábrica só se modifica por dentro e com gate: o curador não aplica catálogo; com repositório autoritativo ele produz somente intenção `promocao_pendente` com `requer_gate=True`. Sem repositório, falha fechado. JSON/CLI não é autoridade de promoção. | `motor/motor/curador.py::preparar_promocao_gated`; `RepositorioCertificacoes` | `motor/tests/test_hardening_h09b.py::test_repo_valido_gera_somente_intencao_gateada_sem_aliases`, `test_promocao_default_deny_sem_repo_ou_id_conhecido` |

## Spec e capacidades

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| S1 | Validador só aceita `kind` em `schema_json`, `contem` ou `comando`; configuração inválida falha na validação da spec. | `motor/motor/spec.py::WorkflowSpec._consistencia` | `motor/tests/test_spec.py::test_validador_comando_exige_config_comando`; `motor/tests/test_validadores_deterministicos.py::test_spec_validador_exige_alvo_e_kind_valido` |
| S2 | Validador sempre aponta para um alvo existente e dependente; reprovação de validador vira `refazer` do alvo, não só do validador. | `motor/motor/spec.py::WorkflowSpec._consistencia`; `motor/motor/grafo.py::construir_grafo.executar_validador` | `motor/tests/test_spec.py::test_validador_comando_exige_valida_em_depende_de`; `motor/tests/test_validadores_deterministicos.py::test_schema_json_reprova_e_vira_lacuna_do_alvo` |
| S3 | Capacidade mínima não vazia declarada no roteiro é requisito estrito: só executor compatível pode rodar e ausência de cobertura falha fechado. `None` e `[]` preservam a rota legada sem requisito de capacidade. | `motor/motor/modelos.py::ClienteRoteador`; `motor/motor/spec.py::Subagente.capacidades_requeridas` | `motor/tests/test_hardening_h12a.py::test_h12a_grafo_executa_somente_rota_que_cobre_todas_capacidades`, `test_h12a_grafo_bloqueia_cliente_direto_sem_enforcement`, `test_h12a_lista_vazia_preserva_rota_legada` |
| S4 | Toda tentativa de modelo alcançável no grafo reserva teto conservador antes do transporte; retry/failover têm identidade própria, e custo ausente ou inconciliável vira `UNKNOWN_COST` e bloqueia novas reservas. | `motor/motor/grafo.py::construir_grafo`; `motor/motor/orcamento.py::executar_tentativa_custeada`; `RepositorioOrcamento` | `motor/tests/test_hardening_h12b4c_grafo.py`; `test_hardening_h12b4d_grafo.py`; `test_hardening_h12b4e_grafo.py` |
| S5 | Adapter real só é composto com pricing e FX versionados, frescos e conservadores; credencial, limites, usage ou identidade divergentes falham fechados. | `motor/motor/composicao_orcamento.py::compor_orcamento_openai`; `motor/motor/openai_orcado.py::ClienteOpenAICusteado` | `motor/tests/test_hardening_h12b4a.py`; `test_hardening_h12b4f_config.py` |

## Grafo e reconciliação

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| G1 | No padrão `grafo_dependencias`, a execução respeita ordem topológica e injeta dependências no prompt do dependente. | `motor/motor/spec.py::WorkflowSpec._consistencia`; `motor/motor/grafo.py::construir_grafo.executar_grafo_dep` | `motor/tests/test_grafo_dep.py::test_cadeia_executa_em_ordem_e_injeta_dependencia`, `test_diamante_respeita_ordem_topologica` |
| G2 | Reconciliação aponta o nó culpado (`nos_a_refazer`/`refazer`), refaz ele e seus dependentes, não o grafo inteiro. | `motor/motor/grafo.py::avaliar_cobertura`; `preencher_lacunas` | `motor/tests/test_grafo.py::test_gate_cobertura_preencher_refaz_fonte_e_dependentes_em_ordem`; `motor/tests/test_validadores_deterministicos.py::test_reconciliacao_refaz_alvo_validado_nao_so_o_validador` |
| G3 | Loop de reconciliação é bounded por `max_rodadas_reconciliacao`; ao esgotar, emite evento e só prossegue parcial por decisão/política. | `motor/motor/grafo.py::construir_grafo.avaliar` | `motor/tests/test_grafo.py::test_gate_cobertura_preencher_loop_converge_com_teto_dois`, `test_gate_cobertura_preencher_teto_dois_prossegue_parcial` |
| G4 | Falha de executor/modelo vira evento e resultado reprovado, não crash silencioso do motor. | `motor/motor/grafo.py::subagente`; `motor/motor/modelos.py` clientes concretos | `motor/tests/test_modelos.py::test_compat_falha_total_devolve_none`; cobertura de `executor.erro` em `motor/tests/test_grafo.py` |

## Segurança de subprocesso

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| C1 | Só identidade absoluta resolvida e presente na allowlist pode atravessar a fronteira do runner; allowlist ausente ou ambígua falha fechado. | `motor/motor/grafo.py::construir_grafo.executar_comando_seguro`; `motor/motor/registro.py::ferramentas_permitidas_de_registro` | `motor/tests/test_hardening_h04.py`; controles em `motor/tests/test_validadores_deterministicos.py` e `test_ferramenta.py` |
| C2 | Comando, se habilitado, deve executar com filesystem, ambiente e rede confinados ao sandbox; `cwd` sozinho não satisfaz isolamento. | `motor/motor/runner.py::DockerSandboxRunner`; default `DenyCommandRunner` | ⚠️ ADAPTER NÃO CERTIFICADO — policy/argv/preflight têm testes locais, mas falta daemon Docker Linux, imagem por digest e job H05b real. |
| C3 | Backend de comando deve limitar timeout, output e árvore de processos com TERM/KILL determinísticos. | `motor/motor/runner.py::DockerSandboxRunner` | ⚠️ NÃO SUSTENTADO — timeout/kill são implementados, mas output ainda não é limitado por streaming e nenhum deployment prova cleanup da árvore; ver `sandbox-conformance.md`. |
| C4 | Placeholder produz elemento de `argv`, nunca shell ou nova estrutura de comando; metacaracteres, whitespace e caminhos hostis não alteram a identidade executável. | `motor/motor/grafo.py::construir_grafo.executar_comando_seguro`; `CommandRequest.argv` | `motor/tests/test_hardening_h04.py`; wrapper H01/H04/H05a |

## Eventos e projeções

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| E1 | O conjunto de tipos de evento é fechado; evento emitido no código e ausente do schema quebra o guard anti-drift. | `motor/motor/eventos_schema.py::ESQUEMA`; AST guard em teste | `motor/tests/test_eventos_schema.py::test_schema_cobre_todos_eventos_emitidos_no_codigo`, `test_guarda_anti_drift_falharia_com_evento_nao_declarado` |
| E2 | Ledger JSONL v2 é append-only, durável e estrito: writer único, `seq` contígua, tempo não regressivo, recovery de tail com quarentena e defesa contra troca/link de arquivo. Eventos monetários entregues pelo relay preservam `event_id` e deduplicam após reabertura; divergência falha antes do ACK. V1 permanece somente leitura e não autoriza gate. Painel e curador são projeções. | `motor/motor/eventos.py::LogEventos`; `motor_painel.painel::parse_eventos`; `motor/motor/curador.py::carregar_runs` | `motor/tests/test_hardening_h07a.py` até `test_hardening_h07e.py`; `motor/tests/test_hardening_h12b3.py`; manifest em `motor/tests/test_hardening_h07.py` |

## Curador

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| U1 | Sombra é read-only e isolada por cópia profunda: mutação/alias do runner não altera casos, proposta, catálogo, config, roteamento ou logs; falha de um caso não aborta os seguintes. | `motor/motor/curador.py::rodar_sombra` | `motor/tests/test_hardening_h08.py` |
| U2 | Certificação recomputa evidência v2 selada e só aprova qualidade estritamente maior **e** custo médio estritamente menor. Evidência incompleta, agregados do chamador, empate, custo incomparável ou não finito vetam. | `motor/motor/curador.py::certificar_sombra` | `motor/tests/test_hardening_h09a.py`; `motor/tests/test_hardening_h09c.py` |
| U3 | Só certificação recuperada de `RepositorioCertificacoes` autoritativo pode gerar intenção; repositório ausente ou divergência veta. Sucesso continua sendo apenas `promocao_pendente`, nunca apply ou `curador.promoveu`. | `motor/motor/curador.py::preparar_promocao_gated`; `RepositorioCertificacoes` | `motor/tests/test_hardening_h09b.py` |

## Fundador e caixa

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| F1 | Decisão pendente e retomada sobrevivem a crash por outbox SQLite com claim/lease/ack e reconciliação automática. A entrega é **at-least-once**, deduplicada por `decision_id`; não há promessa de exactly-once entre stores. | `motor/motor/caixa.py::LedgerCaixa`; `rodar_com_caixa`; `motor/motor/servico.py::GerenciadorJobs` | `motor/tests/test_hardening_h11.py::test_crash_em_cada_fronteira_converge_apos_restart`, `test_servico_reconcilia_automaticamente_apos_restart_de_processo` |
| F2 | Gate humano persiste decisão antes de arquivar nota; múltiplos interrupts exigem `decision_id`, são serializados por job e continuam independentes entre jobs. Timeout preserva evidência para depuração. | `motor/motor/caixa.py::CaixaFundador`; `LedgerCaixa`; `motor/motor/servico.py::GerenciadorJobs` | `motor/tests/test_hardening_h11.py::test_servico_serializa_dois_interrupts_paralelos_por_job`, `test_claim_serializa_mesmo_job_e_mantem_jobs_distintos_paralelos`; controles em `motor/tests/test_caixa.py` |
| F3 | Gate `promocao` é sensível e nunca é auto-respondido, mesmo com `auto_mode`, override ou default. `plano` e `cobertura` não são classificados como sensíveis pelo contrato atual. | `motor/motor/politica.py::PoliticaGates` | `motor/tests/test_hardening_h01.py::test_reprodutor_h01` materializa os casos F3 aceitos em `motor/specs/001-hardening-producao/reproducer-manifest.jsonl` |

## Dívidas conhecidas

1. **H05b — sandbox real:** existe `DockerSandboxRunner` com policy fail-closed e preflight, mas C2/C3 continuam indisponíveis até existir daemon Linux, imagem/policy por digest, output streaming/cleanup causal e job de conformidade do deployment. Default-deny é seguro, mas não oferece a capacidade.
2. **Operação do orçamento:** uma única rota OpenAI não prova independência executor-verifier, e a reserva conservadora atual excede o bootstrap de R$ 2. Studio e experimentos reais permanecem fail-closed; recovery do relay exige polling no serviço ou o mesmo `run_id` na CLI.
3. **Backend autoritativo do curador:** U3/K4 falham fechado sem `RepositorioCertificacoes` real. O protocolo e os testes não fornecem autoridade de produção.
4. **Operação H11:** expor saúde do reconciliador e garantir lifecycle explícito; efeitos externos continuam responsáveis por idempotência durável por `decision_id`.
