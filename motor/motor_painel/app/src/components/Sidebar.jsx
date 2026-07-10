/* Sidebar 238px — 4 zonas (Fixas, Projeto, Biblioteca, Sistema)
 * Nav items via hash routing.
 */

const NAV = [
  {
    zone: 'Fixas',
    fixed: true,
    items: [
      { label: 'Home', path: '/' },
      { label: 'Runs', path: '/runs' },
      { label: 'Caixa do Fundador', path: '/caixa' },
      { label: 'Grafo 2D', path: '/grafo' },
    ],
  },
  {
    zone: 'Projeto: Todos',
    items: [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Grafos', path: '/grafos' },
      { label: 'Workflows', path: '/workflows', sub: true },
      { label: 'Datahouse', path: '/datahouse', sub: true },
    ],
  },
  {
    zone: 'Biblioteca',
    items: [
      { label: 'Agentes', path: '/agentes' },
      { label: 'Skills', path: '/skills' },
      { label: 'Curador', path: '/curador' },
      { label: 'Logs', path: '/logs' },
      { label: 'Custos', path: '/custos' },
    ],
  },
  {
    zone: 'Sistema',
    items: [
      { label: 'Conexões', path: '/conexoes' },
      { label: 'Configurações', path: '/config' },
    ],
  },
];

function navTo(path) {
  window.location.hash = path;
}

export default function Sidebar({ route }) {
  const isActive = (path) => {
    if (path === '/') return route === '/' || route === '';
    return route === path || route.startsWith(path + '/');
  };

  return (
    <aside className="mf-side">
      {NAV.map((group) => (
        <div key={group.zone}>
          <div className={`zt${group.fixed ? ' fixed' : ''}`}>{group.zone}</div>
          {group.items.map((item) => (
            <div
              key={item.path}
              className={`ni${item.sub ? ' sub' : ''}${isActive(item.path) ? ' on' : ''}`}
              onClick={() => navTo(item.path)}
            >
              {item.label}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
