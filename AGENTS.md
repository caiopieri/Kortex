# AGENTS.md — Configuração de sub-agentes e MCPs

Instruções específicas do projeto para orquestrar sub-agentes, MCPs e skills no Cowork.

## 🛰️ Sub-agentes disponíveis

### Claude (Orquestrador)
- **Especialidades:** Arquitetura, design, revisão, julgamento
- **Gate:** Verifica qualidade, aprova antes de ship
- **Custo:** Premium (Opus/Sonnet)

### Codex (OpenAI — Fallback)
- **Especialidades:** Scaffold, boilerplate, review
- **Trigger:** `/codex:rescue`, `/codex:review --background`
- **Custo:** Mais barato que Claude
- **Nota:** Requer OpenAI API key + autenticação

### Antigravity / Gemini (Executor)
- **Especialidades:** Teste generation, migrations, scaffold repetitivo
- **Trigger:** `/antigravity:delegate <task>`, `/antigravity:review`
- **Custo:** ~27% mais barato que Claude solo (benchmark)
- **Setup:** `agy` CLI + Vertex AI auth

### Alibaba / Qwen (Especializado)
- **Especialidades:** Imagem, vídeo, TTS, ASR, chat
- **Trigger:** `/alibaba:image`, `/alibaba:video`, `/alibaba:transcribe`
- **Custo:** Mais barato que Claude para geração
- **Setup:** ✅ Já autenticado (`~/.claude/secrets/alibaba-model-studio.env`)

---

## 📋 Routing de tarefas (Decision Tree)

```
Tarefa chega
  ├─ É geração de imagem/vídeo?
  │  └─ SIM → Alibaba (mcp__alibaba-model-studio__*)
  │           └─ Claude verifica resultado
  │
  ├─ É teste generation massivo?
  │  └─ SIM → Antigravity/Gemini (/antigravity:delegate)
  │           └─ Claude verifica cobertura
  │
  ├─ É refactor/review complexo?
  │  └─ SIM → Codex (/codex:rescue) OU Antigravity
  │           └─ Claude decide, aprova, integra
  │
  ├─ É decisão arquitetural, code review crítico, ou spec?
  │  └─ SIM → Claude (só Claude)
  │
  └─ É boilerplate claro + testável?
     └─ SIM → Codex ou Antigravity (mais barato)
              └─ Claude verifica
```

---

## 🔌 MCPs habilitados

| MCP | Status | Autenticação | Use case |
|-----|--------|--------------|----------|
| **Alibaba Model Studio** | ✅ Ativo | ✅ Autenticado | Imagem, vídeo, TTS, ASR |
| **Firecrawl** | ✅ Ativo | ✅ Via token | Web scraping, search |
| **Codex Plugin** | ⏳ Pronto | 📝 Registrar | Code review, rescue |
| **Antigravity Plugin** | ⏳ Pronto | 📝 Registrar | Teste gen, migrations |

---

## 💼 Integração Cowork

### Para Claude Code (seu laptop)
```bash
# Registrar plugins em sessão interativa
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex

/plugin marketplace add yuting0624/antigravity-for-claude-code
/plugin install antigravity@antigravity-for-claude-code

# Usar
/codex:review
/antigravity:delegate "Gere 50 testes para payments.py"
/alibaba:image "Hero section para landing"
```

### Para Cowork (cloud agents)
```markdown
## Task: Gerar assets para landing page

1. **Prompt para Alibaba** (via antigravity-delegate)
   ```
   Gere 3 variações de hero image (1600x900):
   - Tema: Startup tech, cores azul/branco
   - Estilo: Minimalista, sem pessoas
   - Formato: PNG high-quality
   ```

2. **Verificação Claude** 
   - ✅ Qualidade visual
   - ✅ Brand alignment
   - ✅ Performance (file size < 500KB)

3. **Ship**
   - Salvar em `assets/landing/`
   - Commit com mensagem clara
```

---

## 🎯 Exemplos de workflow

### Workflow 1: Code → Test → Ship (Integrado)
```
1. Claude: Escreve código (spec clara)
2. Antigravity: Gera testes exhaustivos (/antigravity:delegate)
3. Claude: Verifica cobertura, aprova (/antigravity:result)
4. Ship: Commit com sign-off
```

### Workflow 2: Conteúdo visual (Alibaba-first)
```
1. Claude: Especifica requerimentos (dimensões, estilo, brand)
2. Alibaba: Gera imagem (/alibaba:image) 
3. Claude: Verifica qualidade, aprova
4. Ship: Usa asset
```

### Workflow 3: Análise pesada (Antigravity-first)
```
1. Claude: Define questão (o que, por quê, critérios de sucesso)
2. Antigravity: Digere logs massivos, RAG em KB interno (/antigravity:research)
3. Claude: Verifica citations, conclui
4. Comunica: Resultado > doc/análise.md
```

---

## 📊 Custo-benefício por sub-agente

| Agente | Custo | Qualidade | Velocidade | Ideal para |
|--------|-------|-----------|-----------|-----------|
| Claude | 100% | 10/10 | Média | Decisão, design, crítica |
| Antigravity | 30% | 8/10 | Rápido | Scaffold, testes, migrations |
| Codex | 40% | 8/10 | Rápido | Review, boilerplate |
| Alibaba | 20% | 9/10 (imagem) | Muito rápido | Geração visual, TTS, ASR |

---

## 🔐 Segurança & Credenciais

Todos os MCPs usam credenciais armazenadas em `~/.claude/secrets/`:
- ✅ Nunca commitidas no repo
- ✅ Rotação gerenciada externamente
- ✅ Auditadas via logs do MCP

Para adicionar nova credencial:
```bash
# Criar arquivo seguro
echo "API_KEY=sk-..." > ~/.claude/secrets/novo-mcp.env

# Nunca fazer
git add .env  # ❌
echo "API_KEY=sk-..." >> .env  # ❌
```

---

## 📚 Leitura obrigatória

- [`~/.claude/CLAUDE.md`](~/.claude/CLAUDE.md) — Princípios globais
- [`.agents/skills/alibaba-cowork.md`](.agents/skills/alibaba-cowork.md) — Usar Alibaba
- [Ponytail Skill](https://github.com/DietrichGebert/ponytail) — Minimizar código
- [Karpathy Guidelines](https://github.com/multica-ai/andrej-karpathy-skills) — Evitar erros comuns

---

## ✅ Checklist: Novo feature com sub-agentes

- [ ] **Claude:** Spec clara, success criteria, arquitectura
- [ ] **Sub-agente:** Executa tarefa (Alibaba/Antigravity/Codex)
- [ ] **Claude:** Verifica resultado, gate passa
- [ ] **Tests:** Passam (próprio code + sub-agente output)
- [ ] **Ship:** Commit + PR com traço de quem fez quê
- [ ] **Custo:** Estimado vs real (rastrear em LOG-VERIFICACAO.md)
