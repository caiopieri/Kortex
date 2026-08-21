/* Sidebar 238px — 4 zonas (Fixas, Projeto, Biblioteca, Sistema)
 * Nav items via hash routing.
 */

const NAV = [
  {
    zone: 'Fixas',
    fixed: true,
    items: [
      { label: 'Board de missões', path: '/' },
      { label: 'Caixa do Fundador', path: '/caixa' },
    ],
  },
  {
    zone: 'Projeto: Todos',
    items: [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Canvas', path: '/canvas' },
      { label: 'Rotas do registro', path: '/rotas' },
      { label: 'Datahouse', path: '/datahouse' },
      { label: 'Runs & Histórico', path: '/runs' },
    ],
  },
  {
    zone: 'Biblioteca',
    items: [
      { label: 'Agentes', path: '/agentes' },
      { label: 'Inventário', path: '/inventario' },
      { label: 'Curador', path: '/curador' },
      { label: 'Logs', path: '/logs' },
      { label: 'Custos', path: '/custos' },
    ],
  },
  {
    zone: 'Sistema',
    items: [
      { label: 'Runners', path: '/runners' },
      { label: 'Conexões', path: '/conexoes' },
      { label: 'Configurações', path: '/config' },
    ],
  },
];

function navTo(path) {
  window.location.hash = path;
}

export default function Sidebar({ route }) {
  const active = (path) => {
    if (path === '/') return route === '/' || route === '';
    return route.startsWith(path);
  };

  return (
    <aside className="mf-side">
      {NAV.map((z, i) => (
        <div key={i}>
          <div className={`zt${z.fixed ? ' fixed' : ''}`}>{z.zone}</div>
          {z.items.map((item, j) => (
            <div
              key={j}
              className={`ni${item.sub ? ' sub' : ''}${active(item.path) ? ' on' : ''}`}
              onClick={() => navTo(item.path)}
              style={{ cursor: 'pointer' }}
            >
              {item.label}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
