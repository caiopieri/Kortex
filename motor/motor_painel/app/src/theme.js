/* Meta-fábrica · Theme Provider
 * Baseado em telas/mf-themes.js — especificação literal dos temas.
 *
 * ZERO cor hardcoded fora deste arquivo. Todo componente consome var(--token).
 */

const LIGHT_AZUL = {
  '--bg': '#E4E9F2',
  '--surface': '#FAFBFD',
  '--surface2': '#EDF0F6',
  '--border': '#D2DAE7',
  '--focus': '#9AA8BF',
  '--text': '#26324B',
  '--text2': '#4D5B76',
  '--text3': '#7E8AA1',
  '--accent': '#54718D',
  '--red': '#B0413E',
  '--amber': '#9A6A1A',
  '--green': '#3B7D5D',
  '--blue': '#3F62A8',
  '--inv-bg': '#26324B',
  '--inv-text': '#FAFBFD',
  '--grap1': '#C9D1DE',
  '--grap2': '#AEB9CB',
  '--rim': '#8F9DB5',
  '--card-shadow': '0 1px 2px rgba(38,50,75,.06), 0 4px 14px rgba(38,50,75,.07)',
};

const BUILTINS = [
  {
    id: 'metafabrica',
    nome: 'Meta-fábrica',
    escuro: {
      '--bg': '#0B0C0E',
      '--surface': '#121417',
      '--surface2': '#17191D',
      '--border': '#26292E',
      '--focus': '#3E434A',
      '--text': '#E8E6E1',
      '--text2': '#8A8F98',
      '--text3': '#5A5F66',
      '--accent': '#E8A33D',
      '--red': '#E5484D',
      '--amber': '#E8A33D',
      '--green': '#30A46C',
      '--blue': '#3E63DD',
      '--inv-bg': '#E8E6E1',
      '--inv-text': '#0B0C0E',
      '--grap1': '#2A2D33',
      '--grap2': '#3A3E46',
      '--rim': '#55596200',
    },
    claro: LIGHT_AZUL,
  },
  {
    id: 'gemini',
    nome: 'Gemini (suave)',
    escuro: {
      '--bg': '#131314',
      '--surface': '#1E1F20',
      '--surface2': '#282A2C',
      '--border': '#3C4043',
      '--focus': '#5F6368',
      '--text': '#E3E3E3',
      '--text2': '#BDC1C6',
      '--text3': '#9AA0A6',
      '--accent': '#8AB4F8',
      '--red': '#F28B82',
      '--amber': '#FDD663',
      '--green': '#81C995',
      '--blue': '#8AB4F8',
      '--inv-bg': '#8AB4F8',
      '--inv-text': '#131314',
      '--grap1': '#2A2C2E',
      '--grap2': '#3A3D40',
      '--rim': '#5F636800',
    },
    claro: LIGHT_AZUL,
  },
  {
    id: 'framer',
    nome: 'Framer (elétrico)',
    escuro: {
      '--bg': '#0A0A0A',
      '--surface': '#161616',
      '--surface2': '#232323',
      '--border': '#2A2A2A',
      '--focus': '#4B4B4B',
      '--text': '#F2F2F2',
      '--text2': '#B3B3B3',
      '--text3': '#7A7A7A',
      '--accent': '#0099FF',
      '--red': '#FF5555',
      '--amber': '#FFB443',
      '--green': '#30C453',
      '--blue': '#0099FF',
      '--inv-bg': '#0099FF',
      '--inv-text': '#FFFFFF',
      '--grap1': '#242424',
      '--grap2': '#343434',
      '--rim': '#4B4B4B00',
    },
    claro: LIGHT_AZUL,
  },
];

const THEME_KEY = 'mf-theme-active';
const MODE_KEY = 'mf-theme-mode';
const CUSTOM_THEMES_KEY = 'mf-themes-custom';

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

export function getStoredTheme() {
  return localStorage.getItem(THEME_KEY) || 'metafabrica';
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

  // Dispatch event for other parts of the application to listen to
  document.dispatchEvent(new CustomEvent('mf-theme-applied', { detail: theme }));
}

export { BUILTINS };

