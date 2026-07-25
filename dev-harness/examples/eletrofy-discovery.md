# Discovery — Eletrofy (exemplo trabalhado)

> Saída real da Sessão 1 de Discovery. Em uso normal, este arquivo vive em `docs/discovery.md`
> do repo da Eletrofy — está aqui como exemplo de referência do método.
> Tier decidido: **T0** (concierge/vitrine no condomínio, sem transação online).

## 1. A dor real
Vender eletrônico usado é caro em *tempo e risco*, não em dinheiro. Quem troca de aparelho fica
com o antigo ocupando espaço, e o caminho de vender (anunciar, responder chat, negociar, evitar
golpe, esperar semanas) é tão penoso que muita gente **doa, repassa ou vende a preço de banana só
pra se livrar** — perdendo valor real. Do outro lado, quem compra usado não tem referência de preço
(não existe "tabela FIPE" de eletrônico), então paga quase preço de novo, ou estranha um barato
achando que é golpe. O mercado não se alinha por falta de um lugar padrão.

## 2. A hipótese mais arriscada
> A que, se for falsa, mata o projeto:

**"A comissão sobre os itens que vendem paga a operação de guardar/manusear/devolver os que NÃO
vendem — e o vendedor topa entregar o aparelho à Eletrofy em vez de repassar pra um parente."**

(O modelo é **consignação gerenciada**: a Eletrofy não compra estoque — guarda em consignação,
vende, tira comissão, devolve o que encalha. Isso tira o risco de *capital*, mas cria risco de
*custo de armazém de encalhe*. Esse número é o que faz ou quebra.)

Hipóteses que NÃO são o risco: "existe demanda por usado barato" (Mercado Livre/Trocafone já provam)
e "dá pra organizar preço por vertical" (Webmotors já prova). O risco é a **economia da consignação**.

## 3. O menor teste
**Vitrine-revista no condomínio (1000+ aptos onde o fundador já é "o cara que vende computador").**
Um catálogo simples (foto, estado, preço justo) dos eletrônicos que o fundador já tem + itens que
vizinhos queiram consignar. Divulgado no prédio; compra e consignação via **WhatsApp** (transação
100% manual). Beachhead de alta confiança que mata os dois cold-starts (audiência + reputação já
existem). Por 3-4 semanas, medir:
- Vizinhos **compram** no preço justo? (demanda)
- Vizinhos **consignam** seus itens? (oferta)
- Quantos dos itens **vendem**, em quanto tempo?
- A comissão dos que venderam **cobre** o encalhe + manuseio dos que não venderam? (a hipótese)

## 4. Tier — T0
Concierge/vitrine, descartável. Nada transaciona online → superfície de segurança ≈ zero (sem
cadastro, cartão, RLS). O risco é de mercado, não técnico. A primeira fatia de **software T1** só
nasce se o T0 fechar o número — e será do lado do vendedor (ex.: "cadastrar item → proposta de
consignação"), não um marketplace de comprador.

## 5. Fora do escopo (explícito — agora)
- Marketplace de dois lados, contas de usuário, carrinho, checkout/pagamento online.
- Estoque/galpão próprio (a "garagem" basta no T0).
- Sair do condomínio (replicação é Later).
- Logística de frete (no T0: retirada no prédio / entrega em mãos).
- App, inspeção formalizada, garantia/7 dias automatizados.

## Onde isto pode dar errado
- **Encalhe come o lucro.** Se poucos itens vendem e muitos ficam parados, a comissão não cobre o
  custo. É *o* risco — por isso o T0 existe pra medir, não pra assumir.
- **Logística da consignação some a fricção do vendedor… pra cima da Eletrofy.** Como o item chega
  ao "armazém"? No condomínio é trivial; fora dele vira custo. Não generalizar cedo.
- **Beachhead que não generaliza.** Funcionar no prédio do fundador (onde ele tem reputação) não
  prova que funciona onde ele é desconhecido. O T0 valida o modelo; a replicação é outra hipótese.
- **Tentação de construir o marketplace.** O maior risco de execução é gastar meses no site dos
  sonhos antes de o número do encalhe fechar. Vitrine read-only + WhatsApp. Nada além disso agora.
