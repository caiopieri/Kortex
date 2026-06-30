# Mapeamento v0.4 → WorkflowSpec v0.1: anuncio-3d

## O que foi portado

| Passo v0.4 | Subagente / elemento v0.5 | Observação |
|---|---|---|
| `redator()` + `portao_texto_conforme()` | subagente `redator` | Rubrica da spec incorpora as regras do portão (≤60 chars, sem termos proibidos, 3-5 frases). O verifier do motor substitui o critic loop explícito. |
| `pesquisador_mercado()` com WebSearch | subagente `pesquisador-mercado` | Ferramenta `WebSearch` declarada em `ferramentas`; rubrica exige faixa min/med/max com fonte. |
| `calculadora-custo` (simulado via `fake()`) | subagente `calculadora-custo` | Entradas (`gramas`, `horas_impressao`, custos unitários) declaradas em `entradas`; rubrica exige premissas explícitas. |
| `if preco < minimo → caixa_fundador(...)` | `gates[0]` "margem-minima" | Condição, pergunta e opções espelham o v0.4 exatamente. Gate avaliado pelo evaluator nativo do motor v0.5. |
| síntese final (`tarefa.concluida`) | `sintese` | Formato markdown; premissas no topo conforme convenção do v0.4. |

## O que ficou de fora e por quê

| Passo v0.4 | Motivo da exclusão |
|---|---|
| `scraper-modelo` | 100% simulado no v0.4 (`fake()`). Requer integração HTTP real com MakerWorld/Thingiverse. Entra em v0.2+ como subagente com ferramenta HTTP dedicada. |
| `api-mercadolivre`, `api-shopee`, `api-amazon` | 100% simulados. Requerem credenciais OAuth de cada marketplace. Fora do escopo v0.5; publicação manual é o fallback. |
| `sistema-estoque` | 100% simulado. Integração com ERP/planilha é responsabilidade de sistema externo; motor não deve possuir esse estado. |
| `artes_sim()` (subroteiro de artes) | 100% simulado e dependia de agente de imagem (fora do modelo de texto). Padrão `fan_out_sintese` v0 não suporta sub-roteiros; entra em padrão futuro. |

## Decisões de mapeamento

- **Todos os subagentes são paralelos** (`depende_de: []`): o v0.4 iniciava artes/texto/custo/mercado em paralelo; a spec preserva esse comportamento via `fan_out_sintese`.
- **Ciclo redator→crítico virou rubrica**: o v0.4 tinha um loop explícito (redator → portão → retry). Na v0.5 a rubrica no subagente `redator` mais o verifier nativo (retry ≤ `max_tentativas`) reproduzem o mesmo comportamento sem código de orquestração customizado.
- **Entradas de custo na spec**: `gramas` e `horas_impressao` foram fixadas com valores de exemplo (92g, 5.5h); em execução real o planner pode sobrescrevê-los via `entradas` ao criar a spec dinamicamente.
