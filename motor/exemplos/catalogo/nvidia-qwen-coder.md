---
tipo: modelo-executor
transporte: openai-compat
provedor: nvidia-qwen-coder
base_url: https://integrate.api.nvidia.com/v1
api_key_env: NVIDIA_API_KEY
modelo: qwen/qwen3-coder-480b-a35b-instruct
capacidades: [codigo]
custo_ordem: 1
---
NVIDIA qwen3-coder (FREE) = especialista em código. Só a tag `codigo` → ganha as tarefas de código sobre
os generalistas. custo_ordem 1. Rótulo de provedor próprio (nvidia-qwen-coder) pra failover
independente do nvidia-llama.
O teto de complexidade deve ser calibrado por experimento antes de uso em produção.
Requer NVIDIA_API_KEY + certificados do Python.
