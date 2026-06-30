# HANDOFF — Fabricação do Motor v0.5 (Meta-fábrica)

> Para agentes (Claude Code, sessão limpa) fabricarem via Rota Forja.
> O esqueleto crítico já está pronto e testado (12/12 com stub). Vocês fabricam a
> integração real. **Não relitigar as decisões abaixo.**

## Contexto em 5 linhas

A Meta-fábrica orquestra missões via um **grafo LangGraph fixo que interpreta uma
WorkflowSpec dinâmica** (dado, não código). Referências: blog Anthropic "dynamic
workflows in Claude Code" + harness do rrm86 (`Pesquisa de dynamics workflow.md`
no vault). O motor v0.4 (script no vault, `5. Motor v0/motor.py`) é a referência
de comportamento; este repo o substitui.

## Decisões travadas

- **LangGraph puro** (`langgraph>=1.0,<2`), nada de langchain. Versões pinadas; upgrade deliberado.
- **Nós são funções puras** que só falam com `cliente.chamar(papel, prompt)` — nenhuma
  chamada de modelo direta no grafo. Roteamento modelo↔papel vive em `motor/modelos.py`.
- **A spec é a dinâmica.** Feature nova na missão = mudança na spec, não nó novo no grafo.
- **Eventos JSONL próprios** (`motor/eventos.py`, formato do painel v0.4) além do checkpointer.
  O log é a fonte de auditoria; o checkpointer é só resume.
- Verifier por subagente (retry ≤ max_tentativas) e evaluator global **antes** da síntese —
  combatem self-preferential bias, agentic laziness e goal drift (nomeados pela Anthropic).
- Subagente reprovado vira lacuna **por código**, não por prompt (regra dura em `avaliar`).

## Mapa do código (não mexer sem motivo)

```
motor/spec.py      WorkflowSpec v0.1 (pydantic) — o artefato central
motor/modelos.py   ClienteModelo (Protocol) + ClienteStub + ClienteClaudeCLI
motor/eventos.py   LogEventos JSONL (formato do painel)
motor/grafo.py     planner → fan-out subagentes → avaliar (interrupt) → sintetizar
motor/__main__.py  CLI mínima (claude -p; gate via input())
exemplos/          missao-pesquisa.json (spec dirigida por dado)
tests/             12 testes com stub — NUNCA apagar teste sem autorização
```

## Tarefas de fabricação (1 tarefa = 1 PR ≤ ~300 linhas)

**T1 — Golden run real no Mac.** Rodar `python -m motor --spec exemplos/missao-pesquisa.json`
e `python -m motor "missão livre"` com `claude` CLI real. Corrigir atritos de prompt
(planner devolvendo JSON inválido etc.) **só nos prompts**, não na topologia.
DoD: 2 execuções completas; log.jsonl coerente; nenhum teste quebrado.

**T2 — Portar anuncio-3d para WorkflowSpec.** Criar `exemplos/anuncio-3d.json` traduzindo
o roteiro do v0.4 (redator+crítico = subagente com rubrica; pesquisador-mercado =
subagente com `ferramentas: "WebSearch"`). O gate de margem-mínima vira `gates[]` na spec +
condição avaliada no evaluator. Passos hoje simulados (scraper, APIs) ficam fora do v0.5
ou viram subagentes simulados explícitos na spec.
DoD: spec valida; rodada híbrida no Mac reproduz o comportamento do v0.4 (incl. escalação com `--escalar` análogo).

**T3 — Caixa do fundador no vault.** No interrupt, além de pausar: criar a nota
`Caixa do fundador/PENDENTE — <portao>.md` (formato exato do v0.4, frontmatter `decisao:`);
um runner (`motor/caixa.py`) faz poll da nota e chama `Command(resume=decisao)`.
Checkpointer **SQLite** (`langgraph.checkpoint.sqlite`, dep nova pinada) para resume pós-crash.
DoD: matar o processo com gate pendente, religar, decidir na nota → missão conclui. Evento `decisao.retomada` no log.

**T4 — Painel.** Apontar o `painel.py`/`painel.html` do vault para o `log.jsonl` deste repo
(ou copiar o painel para cá). Eventos novos (`spec.criada`, `paralelo.*`) aparecem no mapa.
DoD: painel mostra uma missão v0.5 ao vivo.

**T5 — ClienteOpenAICompat (executor: modelo de tier BARATO — DeepSeek/Kimi via proxy).**
Implementar a classe `ClienteOpenAICompat` em `motor/modelos.py`, plugando endpoints
OpenAI-compatíveis (NVIDIA API) como executores baratos. O `ClienteRoteador` (pronto,
não tocar) decide quem atende cada papel; esta classe é só o transporte HTTP.

*Interface FIXADA (não relitigar — os testes são o contrato):*

```python
class ClienteOpenAICompat:
    suporta_ferramentas = False  # atributo de CLASSE; o roteador lê isto

    def __init__(self, base_url: str, api_key: str, modelo: str,
                 mapa_papeis: Optional[dict[str, str]] = None,
                 log: Optional[Any] = None, tentativas: int = 3, backoff: float = 2.0): ...

    def _post(self, payload: dict, timeout: int) -> dict:
        """POST {base_url}/chat/completions, header Authorization: Bearer {api_key},
        body JSON = payload. Devolve o JSON da resposta como dict. stdlib urllib
        APENAS — nenhuma dependência nova no pyproject. Erros HTTP/rede: deixar
        a exceção subir (quem trata é chamar)."""

    def chamar(self, papel, prompt, ferramentas=None, timeout=300) -> Optional[str]:
        """1. ferramentas pedidas → return None imediato (sem chamar _post).
        2. payload: {"model": mapa_papeis.get(papel, modelo),
                     "messages": [{"role": "user", "content": prompt}]}
        3. extrai choices[0].message.content e aplica .strip().
        4. Falha transiente (exceção do _post, JSON sem o campo, conteúdo vazio)
           → evento "modelo.falha" no log (papel=, tentativa=, motivo=) e retry,
           até `tentativas` vezes, sleep backoff×tentativa (linear, igual ClienteClaudeCLI).
        5. Esgotou → None. Falha vira evento, não crash."""
```

*Regras duras:* (a) tocar SOMENTE em `motor/modelos.py`, adicionando a classe — nenhuma
outra classe, teste ou arquivo; (b) dependência nova = PROIBIDO (urllib da stdlib);
(c) NUNCA editar `tests/test_modelos.py` — se um teste parecer errado, PARAR e reportar;
(d) ambiguidade na spec → PARAR e perguntar, não decidir.
*DoD:* `python -m pytest tests/test_modelos.py -q` → os 7 testes `@t5` saem de skip e
passam; suíte completa sem regressão. Smoke real (opcional, requer chave NVIDIA):
`python -c "..."` com 1 chamada ao endpoint.

## Critérios de falsificação da migração (DoD global — medir e reportar)

1. Resume pós-crash funciona via checkpointer nativo no mesmo cenário testado no v0.4.
2. Caixa do fundador funciona via `interrupt()` nativo (T3).
3. Código de orquestração próprio deletado (motor.py v0.4: 225 linhas) > código de
   integração novo escrito. Se falhar qualquer um: **parar e reportar**, não contornar.

## Onde isto pode dar errado

- `claude -p` real devolve prosa em volta do JSON → ajustar prompts, não adicionar parser mágico.
- iCloud (vault) + poll da caixa: latência de sync; manter poll ≥ 5s.
- Tentação de adicionar padrões novos (chain, tournament) — **não**: v0.5 é fan_out_sintese
  certificado primeiro; padrões novos = spec versão 0.2, decisão do orquestrador (Caio).
