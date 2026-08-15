/* Minimapa: onde a vista esta, em relacao a origem do mundo.
 *
 * Num canvas infinito e vazio nao existe "mapa do conteudo" — existe mapa da
 * POSICAO. Entao o minimapa mostra duas coisas reais e nenhuma inventada: o
 * retangulo da vista atual e a origem (0,0). Quando houver objeto, ele entra
 * aqui como marca — ate la o rodape diz que nao ha objeto, em vez de exibir uma
 * area de conteudo que nao existe.
 *
 * A extensao desenhada e o retangulo que contem a vista E a origem, com margem.
 * E por isso que o minimapa serve para voltar: por mais longe que se navegue, a
 * origem continua enquadrada e a um clique de distancia.
 */

import { usePresenca } from '../ui/usePresenca.js';

const LARGURA = 190;
const ALTURA = 126;
const MARGEM = 0.18;

export function Minimapa({ aberto, vp, tela, objetos, aoNavegar }) {
  const { montado, dentro } = usePresenca(aberto);

  /* Vista atual convertida para coordenadas de mundo. */
  const vistaL = tela.largura / vp.escala;
  const vistaA = tela.altura / vp.escala;
  const vistaX = -vp.x / vp.escala;
  const vistaY = -vp.y / vp.escala;

  const minX = Math.min(vistaX, 0);
  const minY = Math.min(vistaY, 0);
  const maxX = Math.max(vistaX + vistaL, 0);
  const maxY = Math.max(vistaY + vistaA, 0);
  const folga = Math.max(maxX - minX, maxY - minY) * MARGEM;

  const extX = minX - folga;
  const extY = minY - folga;
  const extL = maxX - minX + folga * 2;
  const extA = maxY - minY + folga * 2;

  /* Um fator so nos dois eixos: minimapa com aspecto diferente do mundo mente
     sobre a forma da area. */
  const k = Math.min(LARGURA / extL, ALTURA / extA);
  const deslX = (LARGURA - extL * k) / 2;
  const deslY = (ALTURA - extA * k) / 2;
  const paraMapa = (mx, my) => [deslX + (mx - extX) * k, deslY + (my - extY) * k];

  const [vx, vy] = paraMapa(vistaX, vistaY);
  const [ox, oy] = paraMapa(0, 0);

  const aoClicar = (evento) => {
    const caixa = evento.currentTarget.getBoundingClientRect();
    const px = evento.clientX - caixa.left;
    const py = evento.clientY - caixa.top;
    aoNavegar(extX + (px - deslX) / k, extY + (py - deslY) / k);
  };

  if (!montado) return null;

  return (
    <div className="minimapa" data-dentro={dentro ? 'sim' : 'nao'}>
      <svg
        width={LARGURA}
        height={ALTURA}
        onClick={aoClicar}
        role="presentation"
        className="mm-tela"
      >
        <rect
          className="mm-vista"
          x={vx}
          y={vy}
          width={vistaL * k}
          height={vistaA * k}
          rx="2"
        />
        <path className="mm-origem" d={`M${ox - 5} ${oy} h10 M${ox} ${oy - 5} v10`} />
      </svg>
      <div className="mm-rodape mono">
        {objetos.length === 0 ? 'vista e origem · sem objeto' : `${objetos.length} objetos`}
      </div>
    </div>
  );
}
