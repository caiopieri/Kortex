# PROMPT — instalar e configurar o LiteLLM (colar num agente na máquina do Caio)

> Cole tudo abaixo (da linha `---` em diante) num agente com acesso ao terminal da máquina (OpenCode, Codex CLI, Claude Code — tanto faz). Ele instala, configura e testa o gateway. O `config.yaml` já está pronto em `~/Desktop/Projects/Orquestrador/infra/litellm/config.yaml`.

---

Você vai instalar e validar um proxy **LiteLLM** que serve como gateway de fallback de modelos, na minha máquina (macOS). O arquivo de configuração já existe em `~/Desktop/Projects/Orquestrador/infra/litellm/config.yaml`. Faça:

**1. Instalar**
```bash
pip install 'litellm[proxy]'      # se pip falhar, use pipx ou um venv; me diga qual usou
litellm --version
```

**2. Variáveis de ambiente** (crie `~/Desktop/Projects/Orquestrador/infra/litellm/.env`, e **garanta que `.env` está no .gitignore** — nunca commitar chave):
```
NVIDIA_API_KEY=<minha chave da NVIDIA — me pergunte se não estiver setada>
GEMINI_API_KEY=<minha chave do Google AI Studio — me pergunte>
LITELLM_MASTER_KEY=sk-local-<gere uma string aleatória>
```

**3. Conferir os IDs dos modelos (não confie no config cegamente)**
```bash
curl -s https://integrate.api.nvidia.com/v1/models -H "Authorization: Bearer $NVIDIA_API_KEY" | grep -o '"id":"[^"]*"'
```
Compare com os `model:` do `config.yaml`. Se algum ID divergir (maiúsculas, sufixo de versão), corrija no `config.yaml`. Faça o mesmo raciocínio pro `gemini/gemini-2.5-flash` (confirme o nome atual do modelo free do AI Studio).

**4. Subir o proxy**
```bash
cd ~/Desktop/Projects/Orquestrador/infra/litellm
export $(grep -v '^#' .env | xargs)
litellm --config config.yaml --port 4000
```

**5. Smoke test (o que prova que funciona)** — em outro terminal:
```bash
# a) responde no modelo virtual "operario"?
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"model":"operario","messages":[{"role":"user","content":"responda só: ok"}]}'

# b) repita para "arquiteto" e "revisor".
```
Esperado: JSON com uma resposta. Se der erro de auth/ID, ajuste e repita.

**6. Testar o FALLBACK de verdade** (o ponto crítico): edite temporariamente a chave do 1º modelo do `operario` pra um valor inválido (ou aponte o principal pra um ID inexistente), suba de novo e refaça o teste (a). Ele deve **cair pro operario_fb1 e ainda responder**. Confirme no log do proxy que houve o fallback. Depois **reverta** a alteração. Me relate se o fallback funcionou.

**7. Deixar rodando** (fica de pé pra eu usar): rode com `nohup ... &` ou num `tmux`/`screen`, e me diga o comando exato pra parar e reiniciar. Se eu tiver o Oracle Free configurado, me pergunte se prefiro rodar lá em vez de local (roda 24/7).

**Regras:** não commite `.env` nem chaves; não altere as filas de `fallbacks` do config (a ordem foi escolhida a dedo); se um modelo não existir mais, me avise em vez de inventar substituto. No fim, me entregue: (1) confirmou que os 3 virtuais respondem, (2) confirmou o fallback, (3) o comando pra iniciar/parar.
