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
NVIDIA qwen3-coder (FREE) = ESPECIALISTA em código (a aptidão que o Caio descreveu:
"código dá pro qwen que dá certo"). Só a tag `codigo` → ganha as tarefas de código sobre
os generalistas. custo_ordem 1. Rótulo de provedor próprio (nvidia-qwen-coder) pra failover
independente do nvidia-llama.
[APTIDÃO + TETO: CONFIRMAR — até que complexidade de código você confia nele antes de escalar?]
Requer NVIDIA_API_KEY + certificados do Python.
