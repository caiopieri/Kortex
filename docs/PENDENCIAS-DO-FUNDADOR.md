# PENDÊNCIAS DO FUNDADOR

> **O que é este arquivo.** A lista curta do que **só o Caio pode resolver** — porque
> depende de acesso que os agentes não têm, de dinheiro, ou de um juízo que não é técnico.
> Tudo o mais anda sem ele.
>
> **O que NÃO entra aqui:** trabalho técnico bloqueado em outro trabalho técnico. Isso vive
> nas issues e no `ESTADO.md` §4. Se um item aqui puder ser resolvido medindo em vez de
> perguntando, ele sai daqui e vira medição.
>
> Cada item diz **o que trava**, **por que precisa dele** e **o que acontece se ficar parado**.
> Última revisão: 2026-08-22.

---

## 1. Os 131 diretórios de run vazios — apagar ou não (issue #30)

**O que trava.** A issue #28 fechou a fonte: a suíte não escreve mais no workspace real.
Sobrou o acúmulo de antes — 131 diretórios `motor/runs/<32 hex>/` com `log.jsonl` de 0 bytes.

**Por que precisa dele.** O critério que os classifica como resíduo (nome hexadecimal + log
vazio) descreve igualmente bem uma **run real que morreu antes do primeiro evento** — e
sabemos que isso acontece. Apagar em bloco pode destruir a única pista de que uma run
existiu. Além disso, um diretório com log vazio **e produto dentro** não é resíduo: é
evidência perdida com produto sobrevivente.

**Recomendação:** duas passadas. A primeira remove só os que não têm nada além do log vazio
e do `.lock` — essa eu faço sozinho se você autorizar. A segunda é a que tem produto dentro,
e essa se olha, não se varre.

**Se ficar parado:** nada quebra. Não custa disco que importe, e o efeito que doía — a tela
listando esses diretórios como runs — morre pela issue #29, que é leitura, não limpeza.

---

## 2. Moeda de contenção para rota grátis (issue #7)

**O que trava.** As rotas grátis não têm moeda de contenção, então o motor não consegue
reservar antes do efeito nelas.

**Por que precisa dele.** Exige **evidência de faturamento real nas contas dele**, nos
provedores. Já foi verificado que o `omniroute pricing` **não serve**: ele sincroniza de uma
tabela do litellm e classifica gratuidade por catálogo — catálogo não é fatura.
Disponibilidade (HTTP 200) também não é gratuidade.

**Se ficar parado:** as rotas grátis continuam bloqueadas, e isso está **correto** — preço
zero seria pior que o bloqueio, porque preço zero é uma afirmação falsa sobre custo.

---

## 3. Cotação por limite superior verificável (issue #6)

**O que trava.** A reserva orçamentária usa uma cotação que não tem limite superior provável.

**Por que precisa dele.** É decisão de política de risco, não de implementação: quanto se
aceita reservar a mais para nunca reservar a menos. **Atenção:** a issue esteve enunciada ao
contrário, como *"reduzir reserva"* — que seria afrouxamento. O enunciado certo é limite
superior **verificável**.

**Se ficar parado:** o motor continua conservador. Custa oportunidade, não correção.

---

## 4. O Mac migra para Python 3.13? (issue #8)

**O que trava.** O ambiente de desenvolvimento principal roda 3.14, e o `pydantic.v1`
**quebra de verdade** em 3.14 — não é cosmético. O `<3.14` no pyproject está certo; era a
issue que estava enunciada ao contrário.

**Por que precisa dele.** Mexer no interpretador da máquina de trabalho dele é decisão dele.

**Se ficar parado:** a suíte roda no venv 3.11 e o runner roda 3.13. Funciona. O risco é
alguém invocar `python3` direto e receber 3.14, com erro confuso.

---

## 5. Uma run está parada num portão esperando decisão

**O que trava.** No ledger de produção há **uma escalada ao fundador sem resolução**:
`escalado {para: fundador}` no `seq 38`, sem nenhum `decisao.*` nos 426 eventos. A run parou
no `interrupt()` e nunca foi retomada. Das dez runs daquele arquivo, é a única sem desfecho.

A pergunta, capturada antes de a máquina cair:

> **Portão `cobertura`** · opções: `prosseguir` · `corrigir` · `abortar`
>
> *Cobertura insuficiente. Lacunas: não há suíte de testes commitada nem evidência de
> execução no sandbox com exit code 0; não foi demonstrada cobertura testada da construção
> de filtros; não foi demonstrada cobertura testada do tratamento de erros HTTP; o
> verificador não apresentou um veredito válido, portanto a ausência de segredos
> operacionais não foi validada por execução; subagente reprovado: codificador,
> contrato-do-modulo, testador, prova.*

**Ressalva honesta:** não sei se ela ainda é retomável. Retomar exige o estado do
checkpointer do LangGraph, e não verifiquei se ele sobreviveu. Pode ser que a única ação
disponível seja registrar que foi abandonada.

**Se ficar parado:** nada muda — já está parada há tempo. O que se perde é o registro de que
alguém decidiu, em vez de ela ter simplesmente sumido.

---

## 6. O runner está em manutenção

Não é pendência de decisão, é estado. `192.168.15.50` saiu do ar em 2026-08-22 para
manutenção. Consequências enquanto isso:

- **nenhuma medição sobre o ledger de produção** é possível; tudo o que os agentes medirem
  sai do checkout local, que tem corpus diferente;
- **a publicação fica para o fim** — a main pode andar à frente do que está servido lá;
- quando voltar: `git pull`, `npm run build` (precisa de
  `export PATH=$HOME/.nvm/versions/node/v24.19.0/bin:$PATH`), e o painel sobe sozinho —
  `kortex-painel.service` está `enabled` com `Linger=yes`. **O boot vai ser o primeiro teste
  real disso**, que até agora só foi provado contra `kill -9`.
