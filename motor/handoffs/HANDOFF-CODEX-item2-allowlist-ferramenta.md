# HANDOFF CODEX — allowlist de executáveis para o nó ferramenta (fecha o RCE latente)

> Red-team item 2/12 (verificado): `grafo.py:601/609/624` — o nó `ferramenta` monta
> `comando = comando_tpl.format_map(valores)` → `shlex.split` → `subprocess.run(partes)` **no host**,
> com **único guard = `shutil.which(partes[0])`**. Sem allowlist, sem sandbox. Não há `shell=True`
> (pipe cru não dispara), mas `comando: "bash -c '<qualquer coisa>'"` executa arbitrário. **Latente
> hoje** (nada emite nó ferramenta ainda) — vira real quando a **autoria-como-run** gerar specs a
> partir de conteúdo da web. Este handoff põe a trava antes disso.

## Por quê (amarra à arquitetura)
"Músculo, não autoridade" limita dinheiro/identidade (Jarvis), **não** impede RCE no músculo. A
direção de runners sempre-ligados multiplica a superfície. A spec é dado — e dado que vira comando
de shell precisa de allowlist.

## O que fazer (1 commit)
1. **Allowlist opcional**: uma lista de executáveis permitidos, vinda da config
   (`cliente_de_config`/`cliente_de_registro` — mesmo lugar de onde já vêm provedores/tiers), campo
   `ferramentas_permitidas: list[str]` (nomes de executável, ex.: `["python3","pytest","kicad-cli"]`).
   Propagar até o nó ferramenta (mesma via que já leva ferramentas/config ao grafo).
2. **Enforcement** em `grafo.py` (bloco do nó ferramenta, antes do `subprocess.run`): se a allowlist
   estiver **configurada** e `partes[0]` (basename) **não** estiver nela → NÃO executa; emite
   `ferramenta.indisponivel` com motivo `"executável não permitido: <exec>"` e retorna reprovado.
3. **Inerte**: allowlist **ausente/vazia** → comportamento de hoje (só `which`). (Nota no doc:
   quando a autoria-como-run existir, o default deve virar allowlist obrigatória pra specs autoradas
   — mas isso é decisão futura, não entra neste commit.)

## Restrições
- Aditivo/inerte: sem `ferramentas_permitidas` na config, zero mudança de comportamento.
- stdlib; sem chamar modelo. Não mexer no roteador nem nos outros tipos de nó.
- Higiene de git: add específicos; nunca `git add -A`.

## DoD (falsificável)
1. Config com `ferramentas_permitidas: ["python3"]` + spec com nó ferramenta cujo comando começa
   por `bash` → bloqueado, evento `ferramenta.indisponivel` motivo "executável não permitido",
   subagente reprovado, **subprocess NÃO chamado**.
2. Mesma config + comando começando por `python3` (e existente) → roda como hoje.
3. Sem `ferramentas_permitidas` na config → comportamento idêntico ao atual (regressão intacta).
4. Suíte verde; mypy ok.

## O que isto prova e o que NÃO prova
Prova que dá pra restringir o que o nó ferramenta executa. NÃO é sandbox completa (não isola FS/
rede) — allowlist é a 1ª camada; sandbox real (usuário separado/container por runner) é Later, na
camada de runner.
