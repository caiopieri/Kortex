# HANDOFF — v0.2 Hardware, LOTE: REQ-0 (mypy) + REQ-3 + REQ-4 + REQ-5

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR (analisa o LOTE INTEIRO no fim).
> Specs travadas. **Não relitigar.** Pré-req: REQ-1 commitado (`grafo_dependencias`,
> **140 passed**). Origem: `../Harness Hardware/REQUISITOS-MOTOR-harness-hardware.md`.

## Como rodar este lote

São **4 cortes em ordem, cada um seu commit pequeno**. Faça na ordem (REQ-0 → 3 → 4 → 5):
cada corte deixa `python3 -m pytest -q` VERDE antes do próximo. **Cláusula de costura:**
se ao começar um corte a realidade do código divergir do que esta spec assume (interface
diferente da descrita), **PARE e anote em `## DÚVIDAS`** em vez de adaptar no escuro — o
Claude resolve na análise do lote. O Claude só revisa no FIM (os 4 commits juntos).

## Leis (valem para todos os cortes)

1. **1 corte = 1 commit** pequeno. Commitar entre cortes.
2. **Nunca afrouxar/remover teste existente.** A suíte fica VERDE ao fim de CADA corte.
3. **Não tocar** (exceto onde o corte mandar explicitamente): `ClienteRoteador`/Registry de
   modelos, roteamento por papel/tier/capacidade/pin/esgotado/guard, o caminho
   `fan_out_sintese`/`Send`, os gates existentes.
4. **Ambiguidade não se chuta — `## DÚVIDAS`.**
5. Python 3.14, só stdlib + deps do `pyproject.toml`. Sem dep nova.
6. Português, como o resto do repo. `hashlib`, `subprocess`, `pathlib`, `uuid` são stdlib.

## Estado do código (lido e confirmado)

```
spec.py   Subagente: id, papel, objetivo, entradas:dict, resultado_esperado, rubrica,
          ferramentas, tier, capacidades_requeridas, depende_de. padrao =
          Literal["fan_out_sintese","grafo_dependencias"]. _consistencia valida o DAG.
grafo.py  subagente(payload{"sub","spec","feedback"?,"deps"?}) -> {"resultados":[1 dict]}.
          O dict de resultado HOJE = {"id","saida":<texto>,"tentativas","aprovado",
          "motivo"?}. executar_grafo_dep acumula o dict INTEIRO (logo, campos novos no
          resultado fluem sozinhos). subagente injeta deps no prompt via {deps_txt}.
          construir_grafo(cliente, log, checkpointer=None, politica=None).
modelos.py ClienteModelo(Protocol).chamar(papel,prompt,ferramentas=None,tier=None,
          timeout=300,capacidades=None). ClienteRoteador.chamar TEM um param a mais: evitar.
```

---

## CORTE REQ-0 — fechar o mypy (Liskov do `evitar`)

**Por quê:** `ClienteRoteador.chamar` tem `evitar`, mas o Protocol `ClienteModelo.chamar`
e os transportes não — mypy reclama. Fix = uniformizar `evitar` como kwarg ignorado
(exatamente o que já foi feito com `tier` e `capacidades`).

**Passos:** adicione `evitar: Optional[str] = None` à assinatura `chamar` de: o Protocol
`ClienteModelo`, `ClienteStub`, `ClienteClaudeCLI`, `ClienteCodex`, `ClienteOpenCode`,
`ClienteOpenAICompat`. Os transportes IGNORAM (como `tier`/`capacidades`). NÃO mude a
lógica de `ClienteRoteador.chamar` (já tem `evitar`).

**DoD:** `python3 -m pytest -q` segue 140 verde; se mypy estiver disponível,
`python3 -m mypy motor/` não acusa o erro do `evitar`. Commit.

---

## CORTE REQ-3 — artefatos em disco + workspace por execução

**Objetivo:** um nó pode produzir **artefato(s) em disco**; o estado carrega **referência**
(caminho+tipo+hash), **nunca o conteúdo**. A interface `cliente.chamar(...) -> str` **não
muda** — artefato é tratado no NÍVEL DO NÓ, não do cliente.

**Modelo de dado (FIXADO):**
- Referência de artefato: `{"nome": str, "caminho": str, "tipo": str, "hash": str}`
  (hash = sha256 do conteúdo, hex).
- O dict de resultado do subagente ganha uma chave OPCIONAL `"artefatos": [ref, ...]`
  (ausente quando o nó não produz nada → resultados de hoje inalterados).

**Workspace (FIXADO):**
- `construir_grafo(...)` ganha o param `workspace_base: str | Path = "runs"`.
- `run_id`: gerado UMA vez no início (no nó `planner`, quando ainda não existe) como
  `f"{AAAAMMDD-HHMMSS}-{uuid4().hex[:6]}"`; guardado no estado (`EstadoMotor` ganha
  `run_id: str`). O diretório do run = `Path(workspace_base) / run_id / "artefatos"`,
  criado sob demanda (`mkdir(parents=True, exist_ok=True)`).
- CLI: flag `--workspace <dir>` (default `"runs"`), passada a `construir_grafo`.

**Produção por nó-modelo (mínimo deste corte):**
- `Subagente` ganha `produz_artefatos: list[dict] = []`; cada item = `{"nome","tipo"}`.
  **Validação:** para nó-modelo, `len(produz_artefatos) <= 1` (um modelo tem UMA saída de
  texto; produção de múltiplos arquivos é o nó-ferramenta do REQ-4). `nome`/`tipo` não-vazios.
- No `subagente`, APÓS o modelo aprovar (`aprovado=True`) e SE `produz_artefatos` tem 1
  item: escreva a `saida` (texto) em `<workspace>/<id>__<nome>`, compute o hash, e anexe a
  ref em `resultado["artefatos"]`. `saida` (resumo_texto) PERMANECE no resultado (vai pro
  log/verifier/síntese). Helper sugerido: `registrar_artefato(workspace, nome, tipo,
  conteudo) -> ref`.
- Quando `produz_artefatos` é vazio (todo o uso atual), nada muda → suíte verde.

**Como o `subagente` acessa o workspace:** passe `workspace` (o Path do run) no payload do
subagente (o `executar_grafo_dep` e o `despachar`/Send já montam o payload; adicione
`"workspace": <path>` a ele, lido do estado). Detalhe de wiring fica a seu critério, mas
**sem quebrar o fan_out** (payload do Send ganha a chave; quando ausente, nó não produz
artefato).

**Resume pós-crash:** as refs são dados de dict (restaurados pelo checkpointer); os
ARQUIVOS vivem em disco independentes. Não serialize conteúdo no estado.

**DoD (tests/test_artefato.py):**
1. Nó-modelo com `produz_artefatos:[{"nome":"saida.txt","tipo":"txt"}]` (stub que devolve
   texto fixo + verifier que aprova) → o arquivo existe em `<workspace>/<id>__saida.txt`,
   o resultado tem `artefatos:[ref]` com hash sha256 correto do texto.
2. O estado carrega a REFERÊNCIA, não o conteúdo (assert: nenhum campo do resultado contém
   o conteúdo além da `saida`; a ref tem só nome/caminho/tipo/hash).
3. `produz_artefatos` vazio → resultado sem chave `artefatos`; **140 seguem verdes**.
4. `len(produz_artefatos)>1` num nó-modelo → `ValueError` na validação da spec.

---

## CORTE REQ-4 — nó-ferramenta determinístico (sem modelo), via Registry

**Objetivo:** um nó que roda um **comando local determinístico** (subprocess, SEM modelo)
e cujo resultado é `pass/fail` objetivo + artefatos. É o "CI verde" do hardware (ex.:
`kicad-cli pcb drc`). Resolve o executável **consultando o Registry** (convergência: o
"registro de ferramentas" é o eixo de domínio do mesmo Registry dos modelos).

**Schema da entidade-ferramenta (Registry, FIXADO)** — novo arquivo `.md`:
```yaml
---
tipo: ferramenta
nome: drc                      # nome lógico referenciado pela spec
comando: "kicad-cli pcb drc {entrada} --output {saida}"   # template com placeholders
interpreta_saida: exit_code    # estratégia: exit_code (0=pass; !=0=fail, stdout=erros)
produz: [{ "nome": "drc.rpt", "tipo": "txt", "de_placeholder": "saida" }]   # opcional
---
Wrapper do DRC do KiCad. Placeholders {entrada}/{saida} resolvidos em runtime.
```
Loader novo `ferramentas_de_registro(pasta) -> dict[nome, dict]` (espelha
`cliente_de_registro`: lê `.md`, filtra `tipo: ferramenta`, indexa por `nome`; nome
duplicado → `ValueError`). Passado a `construir_grafo(... ferramentas: dict = {})`.

**Spec do subagente-ferramenta (FIXADO):**
- `Subagente` ganha `tipo: Literal["modelo","ferramenta"] = "modelo"`.
- Para `tipo=="ferramenta"`: campo `ferramenta: str` (nome lógico) é obrigatório; `papel`/
  `rubrica` deixam de ser exigidos a um nó-ferramenta (validação: ferramenta exige
  `ferramenta`; modelo exige `papel`+`rubrica` como hoje). Os placeholders do comando são
  preenchidos por `entradas` (chave = nome do placeholder) e, no REQ-5, por ref de artefato.

**Execução (no `subagente`, ramo `tipo=="ferramenta"`):**
- Resolve a ferramenta no dict `ferramentas`; ausente → evento `ferramenta.indisponivel` +
  resultado `{"aprovado": False, "motivo": "ferramenta '<nome>' não registrada", ...}`.
- Substitui placeholders no `comando` (de `entradas`/refs; saída → caminho no workspace).
- Executável ausente na máquina (`shutil.which` None ou `FileNotFoundError`) → evento
  `ferramenta.indisponivel` + fail explícito (NUNCA passa silenciosamente).
- Roda `subprocess.run` (capture stdout/stderr, timeout). `interpreta_saida=="exit_code"`:
  `aprovado = (returncode == 0)`; `motivo = stdout/stderr` quando falha. Registra os
  artefatos de `produz` (arquivos que o comando escreveu) como refs (REQ-3).
- **SEM verifier-modelo e SEM rubrica** para nó-ferramenta — o comando É o gate. Emite
  eventos no MESMO `log.jsonl` (`ferramenta.executada`, pass/fail) e é checkpointado como
  qualquer nó.

> Mantenha `interpreta_saida` mínimo (só `exit_code`) neste corte; estratégias de parsing
> de stdout/arquivo ficam pra futuro (anote em DÚVIDAS se quiser propor).

**DoD (tests/test_ferramenta.py — com script fake determinístico):**
1. Entidade-ferramenta apontando um script que sai com `0` → resultado `aprovado=True`.
2. Script que sai com `1` e imprime erro → `aprovado=False`, `motivo` traz o stdout.
3. Ferramenta não registrada / executável ausente → evento `ferramenta.indisponivel` +
   `aprovado=False` (nunca silencioso).
4. Um nó-ferramenta que escreve um arquivo → a ref aparece em `artefatos` (REQ-3).
5. **fan_out e grafo_dep com nós-modelo seguem idênticos; suíte verde.**

---

## CORTE REQ-5 — passagem de artefato declarada (`ref_artefato`)

**Objetivo:** a `entradas` de um subagente pode referenciar o **artefato de saída** de uma
dependência, resolvido para o **caminho real** em runtime. Junto de REQ-1 (ordem) + REQ-3
(artefatos), é o que faz a cadeia `Arquiteto→Codificador→Validador` passar arquivos.

**Contrato (FIXADO):** um valor em `entradas` na forma
`{"ref_artefato": {"de": "<id-subagente>", "nome": "<nome-artefato>"}}`.

**Validação (spec.py, só `grafo_dependencias`):** para cada `ref_artefato` nas `entradas`
de um subagente S: `de` deve estar em `S.depende_de` (ancestral direto) **e** o subagente
`de` deve declarar em `produz_artefatos` (ou em `produz`, se ferramenta) um item com aquele
`nome`. Ref a id fora de `depende_de`, ou a artefato não declarado → `ValueError`.

**Resolução (runtime):** no `executar_grafo_dep` (que tem `concluidos`), antes de chamar
`subagente`, resolva cada `ref_artefato` nas `entradas` para o `caminho` real do artefato
correspondente no resultado da dependência (`concluidos[de]["artefatos"]` → match por
`nome` → `caminho`). Passe as entradas JÁ RESOLVIDAS (ref trocada pelo caminho) no payload.
Para nó-ferramenta, o caminho resolvido preenche o placeholder do `comando`.

**DoD (tests/test_ref_artefato.py):**
1. `grafo_dependencias` A→B onde A `produz_artefatos:[{"nome":"x.txt"}]` e B tem
   `entradas:{"fonte":{"ref_artefato":{"de":"A","nome":"x.txt"}}}` → em runtime B recebe o
   CAMINHO real do artefato de A (não a ref crua, não o conteúdo).
2. `ref_artefato` com `de` que NÃO está em `depende_de` → `ValueError`.
3. `ref_artefato` a um `nome` que a dependência não declara → `ValueError`.
4. Suíte verde.

---

## FUTURO (NÃO fazer neste lote)

REQ-2 (loop de revisão bounded → v0.3). Paralelismo intra-onda (threads). `interpreta_saida`
ricos (parse de stdout/arquivo). Bump de `versao` p/ "0.2" quando o conjunto fechar.

---

## DÚVIDAS
(Codex: escreva aqui o que travou em QUALQUER corte, com o nº do REQ.)
