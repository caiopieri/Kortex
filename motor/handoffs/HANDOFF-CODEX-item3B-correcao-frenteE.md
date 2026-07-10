# HANDOFF CODEX (correção) — Frente E do item3B: isolamento não comprovado

> Veredito do Arquiteto (2026-07-04, `LOG-VERIFICACAO.md`): Frentes A–D aceitas. **Frente E
> reprovada como coleta** — não é punição, é régua: o relato alega "cwd temporário fora do repo",
> mas (a) nenhum tempdir equivalente aos da Frente B existe; (b) `scripts/experimento_matriz_especialista.py`
> não tem chdir/isolamento algum; (c) o SEM RAG 5/5 reportado é **exatamente** o número da 1ª
> tentativa contaminada da Frente B (que caiu pra 1/5 quando isolada de verdade). Relato que não
> bate com evidência não é dado. A leitura "especialista+RAG não avança" está **suspensa**.

## O defeito nomeado
O braço "SEM RAG" da tarefa 2 (`lift-v3-fatos.json`) quase certamente rodou com o repo acessível
no cwd — o modelo leu os docs pelo filesystem e o braço virou "COM RAG por fora". Mesmo modo de
falha que a Frente B já diagnosticou e corrigiu.

## O que fazer
1. **Isolamento estrutural, não manual:** o script da matriz passa a rodar cada célula com
   `cwd` num tempdir **fora do repo** (mesmo mecanismo da Frente B) e **falha alto** se o cwd
   resolver para dentro do repo (assert barato no início da célula). Mudança mínima, só no script
   de experimento — nada no motor core.
2. **Re-rodar a tarefa 2 inteira** (2×2, n≥5 por célula, mesmo pin codex/gpt-5.4-mini vs
   generalista não-Claude). A tarefa 1 (CSV→JSON) não depende de docs do repo — manter os números
   já coletados, declarando isso no relato.
3. **Evidência de isolamento no relato:** caminho de cada tempdir + `ls` do conteúdo + o cwd
   impresso pelo script por célula. Sem isso, o run não conta.
4. Números crus em tabela 2×2; leitura pré-registrada inalterada (a mesma da Frente E original):
   a tese avança se `pequeno+RAG` ≥4/5 na tarefa 2 **e** `pequeno SEM RAG` ≤1/5 **e** custo menor
   que o generalista. Qualquer outra combinação: relatar cru, sem conclusão.

## Restrições
- Nenhum braço usa Claude como modelo sob teste (regra do Fundador).
- Higiene de git: adds específicos; nunca `git add -A`.
- **Não maquiar** — se a reprodução isolada contradisser o relato anterior, isso é o resultado.

## DoD
1. Assert anti-repo no script + teste unitário do assert (cwd dentro do repo → erro).
2. Tabela 2×2 da tarefa 2 com n≥5/célula + evidência de isolamento por célula (item 3 acima).
3. Suíte inteira verde.

## O que prova e o que NÃO prova
Prova (ou refuta) a célula que decide a tese "especialista barato+RAG" com coleta auditável.
NÃO revalida a tarefa 1 (mantida por não depender do corpus) nem generaliza além desta config.
