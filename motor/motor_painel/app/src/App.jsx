import { useState, useEffect, useCallback } from 'react';
import { applyTheme, getStoredTheme, getStoredMode } from './theme.js';
import Sidebar from './components/Sidebar';
import Topbar from './components/Topbar';
import Home from './pages/Home';
import Runs from './pages/Runs';
import CaixaFundador from './pages/CaixaFundador';
import Grafo2D from './pages/Grafo2D';
import Custos from './pages/Custos';
import Dashboard from './pages/Dashboard';
import Agentes from './pages/Agentes';
import Board from './pages/Board';
import CatalogoWorkflows from './pages/CatalogoWorkflows';
import Configuracoes from './pages/Configuracoes';
import Datahouse from './pages/Datahouse';
import Logs from './pages/Logs';
import MapaGeral from './pages/MapaGeral';
import NovaMissao from './pages/NovaMissao';
import Runners from './pages/Runners';
import Skills from './pages/Skills';
import Curador from './pages/Curador';
import Conexoes from './pages/Conexoes';
import Grafo3D from './pages/Grafo3D';

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

  /* Configuracoes troca o tema chamando applyTheme direto; sem isto o themeId
     daqui fica velho e o toggle ◐ reverteria para o tema anterior. */
  useEffect(() => {
    const sincronizar = (e) => setThemeId(e.detail.id);
    document.addEventListener('mf-theme-applied', sincronizar);
    return () => document.removeEventListener('mf-theme-applied', sincronizar);
  }, []);

  /* Reaplica preferências persistidas (densidade/animações) em qualquer rota */
  useEffect(() => {
    document.documentElement.setAttribute('data-density', localStorage.getItem('mf-density') || 'normal');
    document.documentElement.setAttribute('data-anim', localStorage.getItem('mf-anim') !== 'off' ? 'on' : 'off');
  }, []);

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
  else if (route === '/grafo3d') Page = <Grafo3D />;
  else if (route === '/custos') Page = <Custos />;
  else if (route === '/agentes') Page = <Agentes />;
  else if (route === '/dashboard') Page = <Dashboard />;
  else if (route === '/board') Page = <Board />;
  else if (route === '/workflows') Page = <CatalogoWorkflows />;
  else if (route === '/config') Page = <Configuracoes />;
  else if (route === '/datahouse') Page = <Datahouse />;
  else if (route === '/logs') Page = <Logs />;
  else if (route === '/mapa') Page = <MapaGeral />;
  else if (route === '/nova-missao') Page = <NovaMissao />;
  else if (route === '/runners') Page = <Runners />;
  else if (route === '/skills') Page = <Skills />;
  else if (route === '/curador') Page = <Curador />;
  else if (route === '/conexoes') Page = <Conexoes />;
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
