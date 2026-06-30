# ROADMAP — Eletrofy (exemplo trabalhado)

> Saída da Sessão 1. Em uso normal vive na raiz do repo da Eletrofy como `ROADMAP.md`.
> Now/Next/Later por horizonte, não por data.

## Estado atual
Ideia validada no Discovery. Modelo escolhido: **consignação gerenciada**, beachhead = condomínio
do fundador (1000+ aptos, reputação já existente). Nada construído ainda.

## Now (em execução — 1 fatia)
- [ ] **Vitrine-revista no condomínio** — tier **T0**. Catálogo read-only (foto, estado, preço justo)
  dos itens próprios + consignados de vizinhos; compra/consignação via WhatsApp; transação manual.
  Valida a hipótese: *comissão cobre o encalhe? vizinhos compram e consignam?*
  **Sem código de marketplace** — pode ser até no-code (Carrd/Notion/Instagram) ou uma página estática.

## Next (fila — entra quando o T0 fechar o número)
1. **Cadastro de item + proposta de consignação (lado vendedor)** — tier T1. Primeira fatia de
   software de verdade: vendedor submete item, recebe a proposta (comissão menor se leva ele mesmo,
   maior se consigna no armazém). *Só se o T0 provar que vizinhos consignam.*
2. **Catálogo dinâmico com filtro por categoria + preço justo por estado** — tier T1. A "referência
   tipo FIPE" começa a tomar forma com os dados reais das vendas do T0.

## Later (capturado, não comprometido)
- **Pagamento/checkout online + contas de usuário** — depende de: volume que justifique tirar a
  transação do WhatsApp. Traz RLS, PCI, segurança de pagamento (security-DoD Web/pagamentos).
- **Replicação pra outros condomínios/bairros** — depende de: T0 provar o modelo no beachhead.
- **Inspeção formalizada + garantia/7 dias + devolução automatizada** — depende de: virar T2.
- **Estoque/galpão próprio** — depende de: encalhe gerenciável e volume que pague o aluguel.
- **Marketplace de dois lados aberto** — o sonho; só faz sentido com liquidez provada.

## Princípios de sequenciamento (Eletrofy)
- **Beachhead primeiro.** Domina o condomínio antes de sonhar com o Brasil. Replicação é Later.
- **A transação fica manual (WhatsApp) o máximo possível.** Código só entra quando o manual virar gargalo.
- **A hipótese da economia (encalhe) é portão.** Nenhuma fatia T1 começa antes de o T0 fechar o número.
- **Promoção a T2 (pagamento, RLS, garantia) é decisão consciente** — não acontece por inércia ao crescer.

## Onde isto pode dar errado
- "Now" com mais de uma fatia = foco perdido. Uma de cada vez.
- "Later" virar gaveta de lixo: cada item tem a dependência/bloqueio explícito acima — respeite-os.
- Pular o T0 e ir pro cadastro de software porque "é mais legal de mostrar" — constrói antes de validar a economia.
