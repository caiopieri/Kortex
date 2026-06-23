---
tipo: modelo-executor
transporte: codex
modelo: gpt-5.4-mini
papeis: [planner, verifier, evaluator, synthesizer]
tiers: [complexa]
capacidades: [codigo, redacao, calculo, pesquisa, raciocinio-longo]
custo_ordem: 4
---
Codex (assinatura, sem chave) = BACKSTOP confiável. Faz o JULGAMENTO (planner/verifier/
evaluator/synthesizer via `papeis`) pra NÃO cair no Claude reservado, e pega o tier `complexa`.
custo_ordem 4 = mais caro que os free (1) mas barato e confiável; é pra onde o failover desce
quando o free falha. Trocar `modelo` pra gpt-5.5 quando precisar de mais força (custo sobe).
NOTA: codex-mini e codex-5.5 dividem o MESMO rótulo de provedor 'codex' (mesma assinatura/limite)
— esgotam juntos, o que é correto aqui (mesma conta).
