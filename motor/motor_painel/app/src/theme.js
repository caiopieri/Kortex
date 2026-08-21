/* Meta-fábrica · Theme Provider
 * Baseado em telas/mf-themes.js — especificação literal dos temas.
 *
 * ZERO cor hardcoded fora deste arquivo. Todo componente consome var(--token).
 */

/* UM tema embutido, dois modos (claro/escuro). Eram quatro -- `metafabrica`,
   `gemini`, `framer` e `kortex` -- e os tres primeiros sairam no corte 6/7.
   Quatro linguagens visuais para um produto de um usuario e quatro caminhos de
   codigo que quebram sozinhos: o `applyTheme` sincroniza tema E modo, e o
   `App.jsx` ja carregava comentario sobre a tela ficar "metade clara, metade
   escura" quando os dois dessincronizam. Menos combinacoes, menos maneiras de
   dessincronizar.

   `kortex` fica porque ja era o `TEMA_PADRAO` e porque e o unico portado de uma
   fonte real (landing/styles.css). Tema salvo por quem usava um dos removidos
   cai neste, e a queda e explicita em `getStoredTheme`. Temas customizados do
   `localStorage` continuam valendo -- nada foi apagado do navegador de
   ninguem. */
const BUILTINS = [
  {
    /* Portado de landing/styles.css (branch landing-page) — monocromatico de
       precisao, dark-first com claro espelhado. A landing reserva cor
       cromatica para telemetria e nunca para UI, por isso o accent aqui e o
       proprio off-white e nao uma cor de marca.
       Ressalva: a landing nao define ambar nem azul. Esses dois tokens vieram
       do tema `metafabrica` (removido no corte 6/7), porque as 4 formas de
       status do painel exigem os quatro. Nao inventei cor de marca para
       preencher. */
    id: 'kortex',
    nome: 'Kortex (landing)',
    escuro: {
      '--bg': '#0B0C0E',
      '--surface': '#111318',
      '--surface2': '#161920',
      '--border': 'rgba(235,236,240,.09)',
      '--focus': 'rgba(235,236,240,.18)',
      '--text': '#F2F1ED',
      '--text2': '#A7AAB2',
      '--text3': '#6C7077',
      '--accent': '#F2F1ED',
      '--red': '#E05B4E',
      '--amber': '#E8A33D',
      '--green': '#3DC97E',
      '--blue': '#3E63DD',
      '--inv-bg': '#F2F1ED',
      '--inv-text': '#0B0C0E',
      '--grap1': '#1E2128',
      '--grap2': '#2A2E37',
      '--rim': '#6C707700',
    },
    claro: {
      '--bg': '#F4F3EF',
      '--surface': '#FFFFFF',
      '--surface2': '#F8F7F3',
      '--border': 'rgba(23,24,26,.10)',
      '--focus': 'rgba(23,24,26,.22)',
      '--text': '#141518',
      '--text2': '#4C4F54',
      '--text3': '#8B8E93',
      '--accent': '#141518',
      '--red': '#E05B4E',
      '--amber': '#9A6A1A',
      '--green': '#3DC97E',
      '--blue': '#3F62A8',
      '--inv-bg': '#141518',
      '--inv-text': '#F4F3EF',
      '--grap1': '#EDECE6',
      '--grap2': '#DAD8D0',
      '--rim': '#8B8E93',
      '--card-shadow': '0 1px 2px rgba(23,24,26,.06), 0 4px 14px rgba(23,24,26,.07)',
    },
  },
];

const THEME_KEY = 'mf-theme-active';
const MODE_KEY = 'mf-theme-mode';
const CUSTOM_THEMES_KEY = 'mf-themes-custom';
const TEMA_PADRAO = 'kortex';

export function getCustomThemes() {
  try {
    return JSON.parse(localStorage.getItem(CUSTOM_THEMES_KEY)) || [];
  } catch (e) {
    return [];
  }
}

export function saveCustomThemes(list) {
  try {
    localStorage.setItem(CUSTOM_THEMES_KEY, JSON.stringify(list));
  } catch (e) {}
}

export function getAllThemes() {
  return [...BUILTINS, ...getCustomThemes()];
}

/* Le o tema ativo, e SO devolve tema que existe.
   Antes daqui havia uma migracao pontual do default antigo (`metafabrica`) para
   o `kortex`, guardada por uma chave de "ja migrou". O corte 6/7 removeu os
   tres embutidos antigos, entao o caso deixou de ser um: qualquer id salvo que
   nao exista mais cai no padrao, uma vez e para sempre, sem chave de controle.
   Devolver o id morto faria o seletor de Configuracoes abrir sem nada marcado
   enquanto a tela ja estaria pintada com outro tema. */
export function getStoredTheme() {
  const salvo = localStorage.getItem(THEME_KEY);
  if (!salvo) return TEMA_PADRAO;
  return getAllThemes().some((t) => t.id === salvo) ? salvo : TEMA_PADRAO;
}

export function getStoredMode() {
  return localStorage.getItem(MODE_KEY) || 'escuro';
}

export function applyTheme(themeId, mode) {
  const themes = getAllThemes();
  const theme = themes.find((t) => t.id === themeId) || themes[0];
  
  const decl = (obj) =>
    Object.entries(obj || {})
      .map(([k, v]) => {
        const key = k.startsWith('--') ? k : `--${k}`;
        return `${key}:${v}`;
      })
      .join(';');

  let el = document.getElementById('mf-theme-active-style');
  if (!el) {
    el = document.createElement('style');
    el.id = 'mf-theme-active-style';
  }
  document.head.appendChild(el);
  
  const escuroBg = theme.escuro['--bg'] || theme.escuro['bg'] || '#0B0C0E';
  const claroBg = theme.claro['--bg'] || theme.claro['bg'] || '#FAFBFD';
  
  el.textContent = `
    :root, .mf-root { ${decl(theme.escuro)} }
    :root[data-theme="stark"], html[data-theme="stark"], .mf-root[data-theme="stark"] { ${decl(theme.claro)} }
    body { background: ${mode === 'claro' ? claroBg : escuroBg}; }
  `;

  const root = document.documentElement;
  root.setAttribute('data-theme', mode === 'claro' ? 'stark' : 'paperclip');
  
  localStorage.setItem(THEME_KEY, themeId);
  localStorage.setItem(MODE_KEY, mode);

  /* O modo vai junto no detail. Sem ele o App nao tem como saber que alguem
     trocou de modo por fora e o atributo data-theme do .mf-root fica velho —
     o body clareia e o conteudo continua escuro. */
  document.dispatchEvent(new CustomEvent('mf-theme-applied', { detail: { ...theme, modo: mode } }));
}

export { BUILTINS };

