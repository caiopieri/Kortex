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
import Inventario from './pages/Inventario';
import Canvas from './pages/Canvas';

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

  /* Configuracoes troca tema E modo chamando applyTheme direto. Sem sincronizar
     os dois: o themeId fica velho e o toggle ◐ reverte para o tema anterior; e
     o mode fica velho, entao o data-theme do .mf-root nao acompanha — theme.js
     clareia o body enquanto .mf-root segue com as vars escuras e a tela fica
     metade clara, metade escura. */
  useEffect(() => {
    const sincronizar = (e) => {
      setThemeId(e.detail.id);
      if (e.detail.modo) setMode(e.detail.modo);
    };
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
  /* `/grafo3d` foi removida: era a terceira renderizacao do mesmo grafo.
     Quem tinha o link vai para o Canvas, a projecao que sobrou. */
  else if (route === '/grafo3d') { window.location.hash = '/canvas'; Page = <Canvas modo={mode} />; }
  else if (route === '/custos') Page = <Custos />;
  else if (route === '/agentes') Page = <Agentes />;
  else if (route === '/dashboard') Page = <Dashboard />;
  else if (route === '/board') Page = <Board />;
  /* `/workflows` continua respondendo: a rota foi renomeada porque a tela
     mostra rotas de modelo, nao workflows (#23), e link velho cairia em
     Home sem dizer por que. */
  else if (route === '/rotas' || route === '/workflows') Page = <CatalogoWorkflows />;
  else if (route === '/config') Page = <Configuracoes />;
  else if (route === '/datahouse') Page = <Datahouse />;
  else if (route === '/logs') Page = <Logs />;
  else if (route === '/mapa') Page = <MapaGeral />;
  else if (route === '/nova-missao') Page = <NovaMissao />;
  else if (route === '/runners') Page = <Runners />;
  else if (route === '/skills') Page = <Skills />;
  else if (route === '/curador') Page = <Curador />;
  else if (route === '/conexoes') Page = <Conexoes />;
  else if (route === '/inventario') Page = <Inventario />;
  else if (route === '/canvas') Page = <Canvas modo={mode} />;
  else Page = <Home />;

  return (
    <div
      className={route === '/canvas' ? 'mf-root mf-root--fixo' : 'mf-root'}
      data-theme={mode === 'claro' ? 'stark' : 'paperclip'}
    >
      <Topbar theme={mode === 'claro' ? 'stark' : 'paperclip'} onToggleTheme={toggleTheme} />
      <div className="mf-body">
        <Sidebar route={route} />
        {/* O canvas ocupa a area inteira: sem padding e sem rolagem do
            container, senao ele briga com a propria navegacao. */}
        <main className={route === '/canvas' ? 'mf-main mf-main--cheio' : 'mf-main'}>{Page}</main>
      </div>
    </div>
  );
}

export default App;
