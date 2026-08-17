import { useEffect } from 'react';
import { usePresenca } from './usePresenca.js';

/* As abas do painel do Kortex, nas mesmas 4 zonas e na mesma ordem de
   `motor_painel/app/src/components/Sidebar.jsx`. A LISTA e copiada; o estilo
   nao — este menu usa os tokens de marca do canvas.
 *
 * Nenhum destino esta ligado neste app: nao existe rota, nao existe pagina.
 * Por isso todo item nasce DESABILITADO, e nao "clicavel sem efeito". Item que
 * aceita clique e nao leva a lugar nenhum mente sobre o que o sistema faz —
 * mesma regra que deixou a barra de ferramentas com um botao so.
 * Ligar um item = trocar `destino: null` pela rota real e so entao habilitar. */
const ZONAS = [
  {
    zona: 'Fixas',
    itens: [
      { rotulo: 'Home', destino: null },
      { rotulo: 'Board de missões', destino: null },
      { rotulo: 'Caixa do Fundador', destino: null },
      { rotulo: 'Mapa geral', destino: null },
    ],
  },
  {
    zona: 'Projeto: Todos',
    itens: [
      { rotulo: 'Dashboard', destino: null },
      { rotulo: 'Grafo 2D', destino: null },
      { rotulo: 'Grafo 3D', destino: null },
      { rotulo: 'Workflows', destino: null },
      { rotulo: 'Datahouse', destino: null },
      { rotulo: 'Runs & Histórico', destino: null },
    ],
  },
  {
    zona: 'Biblioteca',
    itens: [
      { rotulo: 'Agentes', destino: null },
      { rotulo: 'Inventário', destino: null },
      { rotulo: 'Skills', destino: null },
      { rotulo: 'Curador', destino: null },
      { rotulo: 'Logs', destino: null },
      { rotulo: 'Custos', destino: null },
    ],
  },
  {
    zona: 'Sistema',
    itens: [
      { rotulo: 'Runners', destino: null },
      { rotulo: 'Conexões', destino: null },
      { rotulo: 'Configurações', destino: null },
    ],
  },
];

const LIGADOS = ZONAS.flatMap((z) => z.itens).filter((i) => i.destino).length;
const TOTAL = ZONAS.reduce((soma, z) => soma + z.itens.length, 0);

export function Menu({ aberto, aoFechar }) {
  const { montado, dentro } = usePresenca(aberto);

  useEffect(() => {
    if (!aberto) return undefined;
    const aoTeclar = (evento) => {
      if (evento.key === 'Escape') aoFechar();
    };
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, [aberto, aoFechar]);

  if (!montado) return null;

  return (
    <nav className="menu" data-dentro={dentro ? 'sim' : 'nao'} aria-label="Navegação do Kortex">
      {ZONAS.map((z) => (
        <div key={z.zona} className="menu-zona">
          <div className="menu-titulo mono">{z.zona}</div>
          {z.itens.map((item) => (
            <button
              key={item.rotulo}
              type="button"
              className="menu-item"
              disabled={!item.destino}
              title={item.destino ? item.rotulo : 'Destino ainda não existe neste app'}
            >
              {item.rotulo}
            </button>
          ))}
        </div>
      ))}
      <div className="menu-rodape mono">
        <i />
        {LIGADOS} de {TOTAL} destinos ligados
      </div>
    </nav>
  );
}
