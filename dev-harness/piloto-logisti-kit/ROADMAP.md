# ROADMAP — Logisti

> Now = em fabricação. Next = provável. Later = ideia. Uma fatia por vez.
> Usuário 0: a transportadora do tio do Caio (3 caminhões, motoristas contratados).

## Now

- **Central de documentos da frota** (fatia do piloto — ver `docs/discovery.md`):
  caminhões + motoristas (mínimo) + documentos com vencimento + painel 30/60 dias
  com status. Auth simples (1 conta = 1 empresa) por ser pré-requisito de RLS. Tier T1.

## Next

- **Custos por caminhão** (2ª dor declarada do tio): lançamentos simples (combustível,
  manutenção, pneu, pedágio) por caminhão + visão mensal por caminhão (dá lucro?).
- Notificação ativa de vencimento (WhatsApp/e-mail) — SE o piloto mostrar que o painel
  passivo não sustenta o uso.
- Viagens/fretes (registro da operação do dia a dia).

## Later

- Acerto com motoristas (comissão, adiantamentos, diárias).
- Outros modais: van, carro, moto (regras próprias por modal — o campo `modal` já existe
  no domínio desde a fatia 1).
- Roteirização; rastreamento/segurança (integração com o Sistema de transporte — RFID + IA).
- Multiempresa / SaaS para outras transportadoras pequenas (generalização do usuário 0).
