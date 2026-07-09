# INVARIANTES — motor

Este documento é o alvo da auditoria final. Cada linha abaixo é uma promessa que
o motor deve sustentar; quando a suíte não prova a promessa, a linha fica marcada
como dívida em vez de virar confiança verbal.

## Kernel

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| K1 | Nada roda sem roteiro: a execução parte de uma `WorkflowSpec` válida, fornecida pelo usuário ou gerada e validada pelo planner. | `motor/motor/spec.py::WorkflowSpec._consistencia`; `motor/motor/grafo.py::construir_grafo.planner` | `motor/tests/test_spec.py::test_exemplo_valido`, `test_versao_nao_suportada`, `test_sem_subagentes`, `test_rubrica_vazia` |
| K2 | Toda ação relevante emite evento JSONL auditável. | `motor/motor/eventos.py::LogEventos.evento`; chamadas `log.evento(...)` em `motor/motor/grafo.py` e clientes de modelo | `motor/tests/test_eventos_schema.py::test_schema_cobre_todos_eventos_emitidos_no_codigo`; cobertura funcional distribuída em `test_grafo.py`, `test_validadores_deterministicos.py`, `test_caixa.py`, `test_modelos.py` |
| K3 | Nada cruza fronteira de workflow sem portão: executor passa por verifier, validador determinístico ou gate de cobertura antes da síntese. | `motor/motor/grafo.py::construir_grafo.subagente`; `executar_validador`; `avaliar` | `motor/tests/test_grafo.py`; `motor/tests/test_validadores_deterministicos.py::test_schema_json_reprova_e_vira_lacuna_do_alvo`, `test_reconciliacao_refaz_alvo_validado_nao_so_o_validador` |
| K4 | A fábrica só se modifica por dentro e com gate: curador não aplica catálogo automaticamente; ele produz intenção de promoção com `requer_gate=True`. | `motor/motor/curador.py::preparar_promocao_gated` | `motor/tests/test_curador.py::test_preparar_promocao_gera_intencao_pendente_quando_certificado`, `test_cli_sombra_certificacao_e_promocao_read_only` |

## Spec e capacidades

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| S1 | Validador só aceita `kind` em `schema_json`, `contem` ou `comando`; configuração inválida falha na validação da spec. | `motor/motor/spec.py::WorkflowSpec._consistencia` | `motor/tests/test_spec.py::test_validador_comando_exige_config_comando`; `motor/tests/test_validadores_deterministicos.py::test_spec_validador_exige_alvo_e_kind_valido` |
| S2 | Validador sempre aponta para um alvo existente e dependente; reprovação de validador vira `refazer` do alvo, não só do validador. | `motor/motor/spec.py::WorkflowSpec._consistencia`; `motor/motor/grafo.py::construir_grafo.executar_validador` | `motor/tests/test_spec.py::test_validador_comando_exige_valida_em_depende_de`; `motor/tests/test_validadores_deterministicos.py::test_schema_json_reprova_e_vira_lacuna_do_alvo` |
| S3 | Executor recebe roteamento por capacidade mínima declarada no roteiro; se não há executor capaz, cai no padrão e emite evento. | `motor/motor/modelos.py::ClienteRoteador`; `motor/motor/spec.py::Subagente.capacidades_requeridas` | `motor/tests/test_capacidade.py::test_capacidade_escolhe_mais_barato_capaz`, `test_capacidade_sem_cobertura_cai_no_padrao_e_emite_evento`, `test_tier_tem_precedencia_sobre_capacidade` |
| S4 | Orçamento existe como contrato de spec e uso/custo é emitido, mas `teto_custo` ainda não é hard-stop runtime. | `motor/motor/spec.py::Restricoes.teto_custo`; `motor/motor/modelos.py` emite `modelo.uso` e `custo.tick` | ⚠️ SEM TESTE — há teste para emissão de `custo.tick` (`motor/tests/test_modelos.py::test_compat_emite_modelo_uso_e_custo_tick`), mas não há teste nem enforcement de estouro de teto herdado |

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
| C1 | Subprocess só roda executável permitido quando há allowlist configurada. | `motor/motor/grafo.py::construir_grafo.executar_comando_seguro`; `motor/motor/registro.py::ferramentas_permitidas_de_registro` | `motor/tests/test_validadores_deterministicos.py::test_validador_comando_bloqueado_por_allowlist`; `motor/tests/test_ferramenta.py::test_ferramenta_bloqueia_executavel_fora_da_allowlist_sem_subprocess` |
| C2 | Validador `kind:"comando"` roda com `cwd` no workspace isolado da run, não na raiz do repo. | `motor/motor/grafo.py::construir_grafo.executar_validador` chama `executar_comando_seguro(..., cwd=workspace)` | `motor/tests/test_validadores_deterministicos.py::test_validador_comando_sucesso` |
| C3 | Timeout de comando sempre reprova com motivo determinístico, sem travar o motor. | `motor/motor/grafo.py::construir_grafo.executar_comando_seguro` | `motor/tests/test_validadores_deterministicos.py::test_comando_respeita_timeout_configurado`; `motor/tests/test_ferramenta.py::test_ferramenta_timeout_curto_reprova` |
| C4 | Argumentos de comando não devem permitir injeção via placeholders. Hoje o código usa `shlex.split` antes de `format_map`, o que evita shell, mas não prova todos os casos adversariais de placeholder. | `motor/motor/grafo.py::construir_grafo.executar_comando_seguro` | ⚠️ SEM TESTE — falta teste adversarial com espaço, aspas, `;`, `&&`, newline e caminho malicioso em placeholder |

## Eventos e projeções

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| E1 | Os 49 tipos de evento são fechados; evento emitido no código e ausente do schema quebra o guard anti-drift. | `motor/motor/eventos_schema.py::ESQUEMA`; AST guard em teste | `motor/tests/test_eventos_schema.py::test_schema_cobre_todos_eventos_emitidos_no_codigo`, `test_guarda_anti_drift_falharia_com_evento_nao_declarado` |
| E2 | Log JSONL é fonte de verdade append/read para auditoria; painel e curador derivam projeções a partir dele. | `motor/motor/eventos.py::LogEventos`; `motor/motor/curador.py::carregar_runs`; `motor_painel.painel::parse_eventos` | `motor/tests/test_painel.py::test_parse_eventos_log_amostra_sem_erro`, `test_parse_eventos_arquivo_inexistente_retorna_lista_vazia`; `motor/tests/test_curador.py::test_analisar_metricas_sinteticas_do_observador` |

## Curador

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| U1 | Sombra é read-only: compara titular e candidato sobre casos held-out sem alterar proposta, casos, catálogo, config, roteamento ou logs originais. | `motor/motor/curador.py::rodar_sombra`; runner injetado | `motor/tests/test_curador.py::test_rodar_sombra_emite_evento_read_only`, `test_cli_sombra_certificacao_e_promocao_read_only` |
| U2 | Certificação anti-Goodhart só aprova quando o candidato tem qualidade estritamente maior e custo médio estritamente menor; empate ou custo incomparável veta. | `motor/motor/curador.py::certificar_sombra` | `motor/tests/test_curador.py::test_certificar_aprova_quando_candidato_melhor_em_qualidade_e_custo`, `test_certificar_rejeita_candidato_mais_barato_com_qualidade_menor`, `test_certificar_rejeita_qualidade_igual_mesmo_com_custo_menor`, `test_certificar_rejeita_custo_ausente` |
| U3 | Promoção sem certificação aprovada vira `promocao_vetada`; promoção aprovada vira intenção pendente e não emite `curador.promoveu`. | `motor/motor/curador.py::preparar_promocao_gated`; CLI `--promocao` | `motor/tests/test_curador.py::test_preparar_promocao_veta_certificacao_rejeitada`, `test_preparar_promocao_veta_certificacao_com_status_desconhecido`, `test_cli_sombra_certificacao_e_promocao_read_only` |

## Fundador e caixa

| # | Invariante | Enforço | Teste que prova |
|---|---|---|---|
| F1 | Decisão pendente sobrevive a crash: checkpoint SQLite retoma o grafo e nota `PENDENTE` pré-existente é reaproveitada. | `motor/motor/caixa.py::CaixaFundador`; `rodar_com_caixa` | `motor/tests/test_caixa.py::test_resume_pos_crash_sqlite`, `test_resume_pos_crash_via_runner`, `test_nota_pendente_preexistente_reaproveitada` |
| F2 | Gate humano registra decisão, arquiva nota decidida e mantém nota em timeout para depuração. | `motor/motor/caixa.py::CaixaFundador.aguardar_decisao` | `motor/tests/test_caixa.py::test_interrupt_cria_nota_e_decisao_conclui`, `test_timeout_levanta_e_mantem_nota` |
| F3 | Gate sensível nunca deve ser auto-respondido pelo modelo. O default de política é manual, mas `auto_mode`/overrides podem automatizar `cobertura`; não há classificação de gate sensível. | `motor/motor/politica.py::PoliticaGates` | ⚠️ SEM TESTE — falta política explícita de classe sensível que ignore auto-mode e exija fundador |

## Dívidas conhecidas

1. **C4 — injeção por argumentos de `comando`:** escrever teste adversarial para placeholders com metacaracteres e caminhos maliciosos. Prioridade alta por ser superfície de subprocesso.
2. **S4 — orçamento como teto herdado:** definir enforcement runtime para `teto_custo` e teste de estouro; hoje há medição (`modelo.uso`/`custo.tick`), não hard-stop.
3. **F3 — gate sensível nunca automático:** introduzir classificação de gate sensível e teste que prove que `auto_mode` não responde esse tipo de gate.
