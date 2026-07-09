# ADR 01: Escolha do Framework Front-end, Roteamento e Estrutura de Temas

**Status:** APROVADO  
**Data:** 2026-07-09  

## Contexto
O painel de controle da Meta-fábrica necessita de uma interface rica, reativa e de alta fidelidade para acompanhar a execução de runs, logs, custos e interação com o fundador (Caixa do Fundador). 

O design de referência exige:
1. Grafos 2D/3D interativos (onde o ecossistema React Flow 11 se faz necessário).
2. Sistema de temas modular sem cores hardcoded, operando sob uma única camada de tokens CSS.
3. Roteamento dinâmico no cliente para transição suave de telas sem recarregamento de página.

## Decisões

1. **Framework:** Adotado React (através de scaffold leve com Vite). Isso permite o reaproveitamento direto de componentes ricos de visualização de grafos (React Flow 11) e arquitetura declarativa de componentes.
2. **Roteamento:** Implementado roteador client-side simples hash-based embutido no `App.jsx` (zero dependências externas como `react-router-dom`), minimizando o inchaço de pacotes (princípio YAGNI/Ponytail).
3. **Theme Provider:** Implementado em `theme.js` para propagar dinamicamente os tokens dos temas definidos (`metafabrica`, `gemini`, `framer`) em variantes claro (`stark`) e escuro (`paperclip`) alterando as variáveis CSS diretamente no `:root` (`document.documentElement`).
4. **Contrato de Dados:** O servidor Python nativo `painel.py` foi estendido para servir a API REST `/dados/*` baseada em projeções determinísticas de logs e escrita no SQLite, além de rotear e servir de forma transparente o build de produção do React (`app/dist/`).

## Consequências
- A compilação é ultrarrápida (192ms) e gera um bundle compacto.
- Qualquer tela do Claude Design pode ser adicionada facilmente como rota/view fina consumindo a API reativa de `/dados/*`.
- A compatibilidade com testes automatizados foi totalmente mantida, garantindo que o servidor serve os endpoints com JSON e cai no fallback estático caso o front-end não esteja compilado.
