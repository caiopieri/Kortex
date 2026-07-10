import { useState, useEffect, useCallback } from 'react';
import { applyTheme, getStoredTheme, getStoredMode } from './theme.js';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import Home from './pages/Home';
import Runs from './pages/Runs';
import CaixaFundador from './pages/CaixaFundador';
import Grafo2D from './pages/Grafo2D';
import Custos from './pages/Custos';

/* Roteador hash-based — mais leve possível, zero deps */
function useHashRoute() {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || '/');
  useEffect(() => {
    const onChange = () => setRoute(window.location.hash.slice(1) || '/');
    window.addEventListener('hashchange', onChange);
    if (!window.location.hash) window.location.hash = '/';
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

function App() {
  const route = useHashRoute();
  const [themeId, setThemeId] = useState(getStoredTheme());
  const [mode, setMode] = useState(getStoredMode());

  /* Inicializa o tema no mount e quando muda */
  useEffect(() => {
    applyTheme(themeId, mode);
  }, [themeId, mode]);

  const toggleTheme = useCallback(() => {
    setMode((prev) => {
      const next = prev === 'escuro' ? 'claro' : 'escuro';
      return next;
    });
  }, []);

  /* Renderiza página com base na rota */
  let Page;
  if (route === '/' || route === '') Page = <Home />;
  else if (route.startsWith('/runs')) Page = <Runs route={route} />;
  else if (route === '/caixa') Page = <CaixaFundador />;
  else if (route === '/grafo') Page = <Grafo2D />;
  else if (route === '/custos') Page = <Custos />;
  else Page = <Home />;

  return (
    <div className="mf-root" data-theme={mode === 'claro' ? 'stark' : 'paperclip'}>
      <Topbar theme={mode === 'claro' ? 'stark' : 'paperclip'} onToggleTheme={toggleTheme} />
      <div className="mf-body">
        <Sidebar route={route} />
        <main className="mf-main">{Page}</main>
      </div>
    </div>
  );
}

export default App;
