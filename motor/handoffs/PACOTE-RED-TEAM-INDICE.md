# Pacote de handoffs — achados do red-team (Fable) verificados

> Origem: `docs/RED-TEAM-RELATORIO-fable.md`, com cada item **verificado por mim contra o
> código** antes de virar handoff. Padrão: Codex executa **1 handoff = 1 commit**, na ordem;
> eu verifico o lote (diff + pytest + sonda independente) quando voltar. Regras permanentes em
> `motor/AGENTS.md` e `kit-processo/METODO-DE-TRABALHO.md`. **Nunca `git add -A`** (mount
> instável: `git status` → `git checkout -- <tracked deletado>` → add específicos).

## Ordem e dependências

**Grupo A — CÓDIGO (sequencial; tocam curador.py/grafo.py/spec.py; commit entre cada):**
1. `HANDOFF-CODEX-item1-marca-nao-certificado.md` — fecha a trava anti-collapse que hoje é
   ficção (a marca "não-certificado" não existe no código). **Faça 1º — é o mais barato e o mais
   grave.**
2. `HANDOFF-CODEX-item4-telemetria-workflow-versao.md` — dá ao curador o eixo template@versão
   (sem ele, "versão carrega evidência" não tem pipeline e erro de template vira conta do modelo).
3. `HANDOFF-CODEX-item2-allowlist-ferramenta.md` — allowlist de executáveis pro nó ferramenta
   (segurança; pré-requisito de ligar a autoria-como-run).

**Grupo B — EXPERIMENTOS (independentes; podem rodar em paralelo à revisão do Grupo A):**
4. `HANDOFF-CODEX-item3-lift-controle-negativo.md` — descobre se o lift do RAG é conhecimento ou
   cópia (controle negativo + métrica derivada). Barato e corrige um overclaim nosso.
5. `HANDOFF-CODEX-item13-teste-especialista-pequeno.md` — **o experimento de maior valor**:
   pequeno+RAG+ferramenta vs generalista, na tarefa mais estreita. Nunca rodou; falsifica (ou
   sustenta) a tese central do flywheel antes de qualquer investimento em data-house/fine-tune.

## O que NÃO virou handoff (e por quê)
- Itens 6, 7, 9, 14 = **desenho antes de construir**, não código pronto (estatística da sombra;
  evento `template.selecionado` só quando a seleção existir; orçamento de decisão; a regra de
  gate por missão real). Ficam pra decidir com o Caio, não pro Codex agora.
- Item 15 (reconciliação de custo) = já rebaixei "$ real"→"$ estimado" nos docs; a reconciliação
  vs fatura é processo, não urgente.
- Itens 8, 10, 11 = parcialmente cobertos (11 doc já corrigido; 8 é o experimento do item 13 num
  domínio conhecido; 10 entra com a composição entre casas, ainda não construída).

## Ao voltar, me traga
Grupo A: o diff + saída do pytest de cada commit. Grupo B: os **números** lado a lado (não
maquiar — se o resultado for negativo, é sinal, reporta). Eu verifico e escrevo o próximo passo.
