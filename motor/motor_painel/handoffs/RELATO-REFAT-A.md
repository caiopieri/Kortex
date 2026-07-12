# RELATO REFAT-A

As seguintes alterações foram realizadas conforme os itens do handoff:

1. **MapaGeral.jsx & Curador.jsx**:
   - `Object.entries(agents)` foi substituído por `agents.map(a => ...)` usando `a.papel` (fallback para `a.id`) como rótulo.
   - O campo `erros` foi substituído corretamente por `a.falhas`.
2. **MapaGeral.jsx**:
   - A contagem de eventos por projeto foi alterada para a soma de `run.n_eventos` das runs do grupo, em vez de depender apenas do primeiro evento com `missao`.
3. **Datahouse.jsx**:
   - Atualizada a validação de eventos reais, passando a considerar a string correta: `['artefato.atualizou', 'artefato.gravado', 'artefato.atualizado'].includes(ev.evento)`.
4. **Logs.jsx**:
   - (a) O formato de tempo `ev.t` foi corrigido para `t.toFixed(3) + 's'`, pois é um timestamp de segundos relativos, não horário de relógio.
   - (b) Respeito implementado para `localStorage['mf-stream-limit']` (com padrão 50) de máximo de linhas por coluna.
5. **Topbar.jsx**:
   - (a) "+ Nova missão" agora navega corretamente para a hash `#/nova-missao`.
   - (b) O ícone de sino 🔔 agora redireciona corretamente para `#/caixa`.
   - (c) O pill "Projeto: Todos ▾" teve seu caret removido e perdeu seu estilo clicável, funcionando como label estático.
6. **Sidebar.jsx**:
   - (a) Foi adicionado o item `Runners` (rota `/runners`) na seção `Sistema`.
   - (b) A chave `sub: true` foi removida de `Workflows` e `Datahouse`, promovendo-os para primeiro nível na UI.
7. **Board.jsx**:
   - (a) A função `colFor` foi atualizada para que se o estado for `abortada`, o card vá para a coluna `done`.
   - (b) O botão "empurrar p/ produção →" agora usa a navegação correta `window.location.hash = '/nova-missao'`.
   - (c) O botão "arquivar" foi removido completamente do card `done` para simplificação.
   - (d) O botão "promover →" nas `Ideias` agora altera localmente a propriedade `col` daquele card para `plan` (inserindo-o na coluna Planejamento) ao invés de apagá-lo.
8. **CaixaFundador.jsx**:
   - O link "Abrir Mapa geral" foi corrigido e agora navega para `'/mapa'`, em vez de `'/grafo'`.
9. **CaixaFundador.jsx**:
   - Implementada lógica visual temporária de decisão pendente: os gates que já foram decididos (`postGateDecision`) agora ficam com o texto `'decisão registrada · aguardando motor'` até que efetivamente o motor os limpe da lista.

## Build

`npm run build` foi executado em `motor/motor_painel/app` e rodou com sucesso.

```text
> app@0.0.0 build
> vite build

vite v8.1.3 building client environment for production...
transforming...✓ 200 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.73 kB │ gzip:   0.40 kB
dist/assets/index-D5Nd6SBe.css   10.87 kB │ gzip:   2.44 kB
dist/assets/index-0egq75Sj.js   533.47 kB │ gzip: 150.20 kB

✓ built in 406ms
```
