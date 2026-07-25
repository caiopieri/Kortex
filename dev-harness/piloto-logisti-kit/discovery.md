# Discovery — Logisti (fatia: central de documentos da frota)

> Preenchido em 2026-06-12 (Caio + Claude). Vai para `docs/discovery.md` no repo.

## 1. A dor real

O tio do Caio é caminhoneiro e dono de uma transportadora com 3 caminhões e motoristas
contratados. Hoje ele controla tudo manualmente, e as duas dores que ele mesmo aponta:
(a) **documentos e vencimentos** — licenciamento e seguro dos caminhões, CNH dos
motoristas; vencimento pego de surpresa = multa ou caminhão/motorista parado;
(b) **custos por caminhão** — não sabe com clareza se cada caminhão dá lucro.
A fatia 1 ataca (a); (b) é a fatia 2.

## 2. A hipótese mais arriscada

O tio vai **adotar e manter o sistema atualizado** no lugar do controle manual — não só
cadastrar uma vez e abandonar. Se for falso (ele volta pro caderno/planilha em 2 semanas),
não há produto, por melhor que seja a técnica. (Usuário real, com nome: é isso que torna
o teste honesto.)

## 3. O menor teste

Central de documentos funcional: cadastrar os 3 caminhões + motoristas (mínimo: nome,
CNH, validade) + documentos com data de vencimento (licenciamento, seguro) + painel
"vence em 30/60 dias" com status (ok / vencendo / vencido). Colocar na mão do tio e
observar: ele cadastra tudo sem ajuda? Volta a abrir o sistema na semana seguinte?

## 4. O tier

- [ ] T0 — Spike
- [x] **T1 — MVP.** Segurança inegociável (RLS, segredos, autorização) + teste no caminho crítico (lógica de vencimentos/status) + deploy simples na Vercel. Sem NFR pesado.
- [ ] T2 — Produção/Escala

## 5. Fora do escopo (explícito)

Outros modais (van/carro/moto — o domínio nasce com campo `modal`, mas só caminhão tem
regras/UI nesta fase); custos por caminhão (fatia 2); viagens/fretes; acerto com motoristas;
roteirização; rastreamento/RFID; financeiro; multiempresa (1 conta = a empresa do tio);
app mobile; notificação push/WhatsApp (painel basta no piloto; alerta ativo é fatia futura).

## Onde isto pode dar errado

- O tio é família — vai ser educado. Medir USO (voltou sozinho? atualizou um documento?),
  não opinião.
- Fatia inflar para mini-ERP na spec — o escopo acima é lei.
- O painel passivo pode não bastar (ele precisa ABRIR o sistema para ver o aviso). Se o
  uso morrer por isso, a fatia 2 muda de custos para notificação — decidir com dado.
- Generalizar cedo demais para "transportadoras pequenas": primeiro o tio usa de verdade;
  o mercado vem depois.
