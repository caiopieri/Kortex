# HANDOFF REFAT-C — Teatro → honestidade (dados fabricados e ações que fingem)

> Executor: Antigravity (Gemini). Base: `motor/motor_painel/app/src/`. Contexto:
> `motor/docs/auditoria/AUDITORIA-PAINEL-TELAS.md`.
> **Toque SOMENTE**: `pages/Home.jsx`, `pages/Custos.jsx`, `pages/Dashboard.jsx`,
> `pages/Conexoes.jsx`, `pages/NovaMissao.jsx`, `pages/Agentes.jsx`, `pages/Skills.jsx`,
> `pages/Runners.jsx`, `index.css`.
> NÃO tocar: painel.py, api.js, App.jsx, Grafo*.jsx, MapaGeral, Curador, Datahouse, Logs,
> Board, CaixaFundador, Topbar, Sidebar, Configuracoes (lotes A/B em paralelo).

Princípio: **número na tela ou vem de dado real (API/eventos) ou vira "—" com legenda honesta.**
Ação na tela ou executa de verdade ou é claramente marcada `em breve`/desabilitada.
Chip padrão para conteúdo estático: `<span class="chip">exemplo · estático</span>` (chip já existe no Board; replicar estilo local se preciso).

## Home.jsx
1. KPI "Mês" = `custo*12.5+18.2` e "Projeção" = `custo*25` (linhas 79–82): remover fórmulas.
   "Mês"/"Projeção" → `—` com sub "requer histórico com timestamp". "Hoje" (real) fica.
2. Chat do Orquestrador (seção 05): é decorativo (span, sem input). Trocar o rótulo
   "Chat · dispara missão em linguagem natural" por "Resumo · status ao vivo"; manter a resposta
   templated (dados reais); REMOVER a linha do falso input "Peça um status…" + seta.
3. `defaultAgents` fictícios: só renderizar quando não houver agentes reais, com chip
   "exemplo · estático".

## Custos.jsx
4. Pills hoje/7d/mês fatiam o dataset artificialmente (25%/60% — linhas 47–77): remover as 3
   pills e o código de fatiamento; rótulo único "sessão · log completo" (eventos não têm
   timestamp absoluto).
5. "Projeção do mês" (92) fórmula inventada → remover KPI ou `—`.
6. Gráfico "01 — Tendência" senóide (99–106): remover a seção (os gráficos reais por run/modelo ficam).
7. "Anomalias" (108–128): manter só a regra `custo > 1.8×média` com legenda
   "heurística local · custo acima de 1.8× a média"; remover o match por substring 'fail/err/abort'.

## Dashboard.jsx
8. Título fixo "csv→json · rota forja…" (353–355) → "Visão geral" + subtítulo real
   "N projetos · M runs (X ativas)".
9. Link "Grafo 3D →" (360) → `'/grafo3d'`.
10. "Saúde dos provedores" hardcoded (230–235): derivar dos eventos — modelos vistos em
    `modelo.uso` = ok; modelos com `modelo.falha` = "falhou · <motivo>"; sem eventos →
    "sem sinal de provedores no log". Nada de lista fixa nvidia/codex/claude.
11. Fallbacks inventados: `firstAttemptPct=74` (90), tiers `58/82/94` (148–158), mediana `3.2` (192),
    p90 `8.1` (199), convergência `83` (224), `pendingCount=1` (227), digests fake (310–315),
    trend `[2,3,2,4…]` (318) → quando não computável de evento real, exibir `—`; a seção
    "aprovação por tier" sem dado real de tier → remover.
12. Gráfico "Custo · 14 dias" renderiza vazio: substituir por barras de custo POR RUN
    (dados reais de getCosts.por_run) e consertar o overflow do card vizinho (o gráfico deve
    respeitar o container; `overflow:hidden` + larguras relativas).

## Conexoes.jsx
13. "Registrar Conexão →" só muda state e o texto de segurança mente (15–17, 81–96): desabilitar
    o botão com nota "registro via UI não implementado — configure em ~/.claude/ (CLI)";
    remover o texto "as credenciais… são guardadas em ~/.claude/secrets/". Manter a lista de
    conexões com chip "exemplo · estático".

## NovaMissao.jsx
14. `handleConfirm` (52–56) finge disparo (id aleatório + "O motor emitiu spec.recebida"):
    remover a simulação. Novo comportamento: montar o objeto spec real do formulário
    (rota/preset/opções/teto) e exibir painel "Despacho manual" com (a) JSON da spec e
    (b) comando pronto para copiar:
    `python3 -m motor --spec '<json>' --caixa runs/caixa` (botão "copiar comando" via
    navigator.clipboard). Texto honesto: "o painel ainda não despacha; copie e rode no terminal".
    Remover o run id fake e a frase "O motor emitiu spec.recebida".

## Agentes.jsx
15. Métricas fixas da "Telemetria do Curador" (só taxa erro é real): trocar as 4 fixas por `—`
    ou derivação real de eventos; latência/convergência sem fonte → `—`.
16. Chat "Falar → / Enviar" (642–659) só ecoa localmente: desabilitar input+botão com nota
    "canal de direcionamento · em breve" (não simular resposta).
17. Link HF "↗" sem href (682): remover o ↗ ou tornar `<a href>` real para huggingface.co do
    modelo; escolher UM.
18. Cards/personas (Órion etc.): manter visual, adicionar chip "blueprint · estático" no
    cabeçalho da galeria; `chamadas/falhas` reais continuam.

## Skills.jsx / Runners.jsx
19. Skills: chip "catálogo estático" no header; contagens de uso reais ficam.
20. Runners: máquinas/IPs fictícios (4–8) → chip "exemplo · não conectado" por card e sub
    no header "nenhum runner real registrado"; fila derivada de eventos fica.

## index.css (consumidores das Configurações — hoje ninguém lê)
21. `[data-density="compacto"]`: reduzir paddings de `.card` e linhas de tabela (~30%).
22. `[data-anim="off"]`: `animation: none !important` nos pulsos (`.pulse`, keyframes de shape)
    e desligar transições decorativas.

## DoD (falsificável)
- `cd motor/motor_painel/app && npm run build` verde.
- `grep -nE "12\.5 \+ 18\.2|\* ?25\b" src/pages/Home.jsx` → 0; `grep -n "csv→json" src/pages/Dashboard.jsx` → 0;
  `grep -nE "RUN-2026|spec\.recebida" src/pages/NovaMissao.jsx` → 0 (a menos que em texto honesto de instrução);
  `grep -n "secrets/" src/pages/Conexoes.jsx` → 0.
- `grep -n "data-density" src/index.css` → ≥1; `grep -n "data-anim" src/index.css` → ≥1.
- Nenhum arquivo fora da lista tocado.
- Relatar em `motor/motor_painel/handoffs/RELATO-REFAT-C.md`: mudanças por arquivo + build.
