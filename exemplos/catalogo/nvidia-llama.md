---
tipo: modelo-executor
transporte: openai-compat
provedor: nvidia-llama
base_url: https://integrate.api.nvidia.com/v1
api_key_env: NVIDIA_API_KEY
modelo: meta/llama-3.3-70b-instruct
tiers: [simples, media]
capacidades: [redacao, calculo, pesquisa, raciocinio-longo]
custo_ordem: 1
---
NVIDIA llama-3.3-70b (FREE) = executor generalista barato pros tiers simples/media.
custo_ordem 1 = primeiro da escada. Rótulo de provedor PRÓPRIO (nvidia-llama) pra failover
modelo-a-modelo (se este rate-limita, não derruba o qwen-coder).
NÃO tem `codigo` de propósito — código vai pro especialista (qwen-coder). [APTIDÃO: CONFIRMAR
com Caio quais capacidades este modelo realmente cobre bem.]
Requer NVIDIA_API_KEY no ambiente + certificados do Python (Install Certificates.command).
