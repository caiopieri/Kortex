# Conformidade — backend de executor (a costura de harness)

> Contrato que um backend de executor precisa satisfazer para ocupar o lugar do nó
> executor do motor. **Certificado contra este documento, nunca por auto-declaração** —
> mesma disciplina de `sandbox-conformance.md`.
>
> Decisão que o motiva: `docs/DECISAO-harness-e-costura-de-execucao.md`.
> Contrato em código: `motor/costura_executor.py`.

---

## 1. Por que existe

O motor não é um harness. Hoje o nó executor é uma chamada de modelo que devolve texto:
não lê arquivo, não roda código, não itera. Um harness faz isso, é mantido por times
grandes e comoditiza rápido — então **aluga-se o laço**.

O que não se aluga são três invariantes. Este documento é o que um backend precisa
provar para ser montado.

## 2. Os três requisitos

### R1 — Envelope de orçamento

O motor reserva **antes do efeito**. O backend recebe `PedidoExecucao.teto` já
reservado e **não pode alterá-lo**: o pedido é `frozen`.

`teto = None` significa medição monetária desligada **explicitamente**
(`sem_contencao_monetaria`), nunca "sem limite por omissão". Backend que trate `None`
como ilimitado **reprova**.

Um laço agêntico não sabe o próprio custo antes de rodar. O envelope é como se roda
livre sem gastar sem controle — e é o requisito com maior chance de reprovar um
harness real. Ver `DECISAO-harness-e-costura-de-execucao.md` §5.

### R2 — Roteamento de execução

Todo comando desce por `PedidoExecucao.command_runner`, certificado contra
`sandbox-conformance.md`. **O padrão é `DenyCommandRunner`**: sem runner composto
explicitamente, o backend não executa nada.

Backend que abra shell próprio, `subprocess`, ou qualquer caminho de execução que não
seja o runner recebido **reprova** — e anula a conformidade de sandbox inteira, porque
passa a existir um segundo contrato de execução no mesmo sistema.

### R3 — Emissão de evidência

O backend recebe `emitir`, **nunca o log**. Ele relata; quem escreve no ledger é o
motor, que carimba `papel` e `fase` do pedido em cada evento.

Isso não é cerimônia: é o que impede uma falha do backend de se apresentar como falha
de outro nó — o defeito que as issues #12 e #20 consertaram no motor.

## 3. Como se certifica

Um backend candidato roda a suíte `tests/test_costura_executor.py` **com sua própria
implementação no lugar do fixture**, e os oito testes passam sem edição.

Cada guarda é portador de carga, provado por mutação um de cada vez:

| mutação | teste que cai |
|---|---|
| runner padrão deixa de negar | execução negada por omissão |
| pedido deixa de ser imutável | backend não pode alterar o envelope |
| envelope inválido passa | envelope reprova antes do efeito |
| saída não textual aceita | saída não textual reprova |
| evento perde a coordenada | evento carrega coordenada do pedido |

Falha cirúrgica em todas: uma mutação, um teste. **Auto-declaração não certifica.**

## 4. O que este contrato NÃO cobre

Registrado para ninguém citá-lo como mais forte do que é:

- **Não há backend de harness implementado.** O contrato existe; o montador não. A
  costura ainda não está ligada ao `chamar_orcado` do `grafo.py`.
- **R2 não é verificável por tipo em Python.** Nada impede um backend de chamar
  `subprocess` diretamente. A garantia é de auditoria e conformidade, não de linguagem
  — igual ao `CommandRunner`, cujo `Protocol` também não valida a implementação.
- **R1 verifica o envelope, não o consumo.** O motor reserva antes; reconciliar o que o
  laço realmente gastou é problema aberto e é o que a
  `DECISAO-harness-e-costura-de-execucao.md` §5 registra como não resolvido.
- **Qualidade de saída não é coberta.** O portão de processo julga o artefato; esta
  costura só garante que o caminho até ele respeita os invariantes.
