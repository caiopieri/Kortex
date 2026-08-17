import { usePresenca } from '../ui/usePresenca.js';

/* Vista de andares: a pilha em perspectiva.
 *
 * Andar = casa/harness (`DECISAO-canvas-e-operacao.md` §4), a camada acima do
 * motor — nao e agrupamento visual. Por isso a vista mostra a pilha inteira e
 * so uma esta em foco: escolher andar e trocar de casa, nao filtrar objeto.
 *
 * Nao ha ligacao desenhada entre andares aqui de proposito. Ligacao entre
 * andares nao e fio solto: e artefato tipado com proveniencia atravessando a
 * fronteira. Desenhar a linha antes de existir o artefato seria inventar
 * relacao — o mesmo erro que a regra "nada existe por estar no canvas" proibe.
 *
 * A pilha se DESDOBRA a partir do plano ao entrar e se deita de volta ao sair,
 * com a superficie plana continuando montada por baixo. Os dois sentidos sao a
 * mesma transicao, entao interromper no meio inverte de onde estava.
 */

const DURACAO = 380;

const GRADE_PLANO = {
  backgroundImage: [
    'linear-gradient(to right, var(--grade) 1px, transparent 1px)',
    'linear-gradient(to bottom, var(--grade) 1px, transparent 1px)',
  ].join(','),
  backgroundSize: '24px 24px, 24px 24px',
};

export function VistaAndares({ aberto, andares, ativoId, aoEscolher }) {
  const { montado, dentro } = usePresenca(aberto, DURACAO);
  const indiceAtivo = andares.findIndex((a) => a.id === ativoId);

  if (!montado) return null;

  return (
    <div className="pilha" data-dentro={dentro ? 'sim' : 'nao'}>
      {andares.map((andar, indice) => {
        const nivel = indice - indiceAtivo;
        const distancia = Math.abs(nivel);
        return (
          <button
            key={andar.id}
            type="button"
            className="plano"
            style={{
              ...GRADE_PLANO,
              zIndex: indice,
              /* Deitado e sem elevacao quando fora; inclinado e no seu nivel
                 quando dentro. Inline porque o mesmo `transform` precisa
                 carregar o nivel do andar E o estado de entrada. */
              transform: dentro
                ? `rotateX(58deg) translateZ(${nivel * 120}px)`
                : 'rotateX(0deg) translateZ(0)',
              opacity: distancia === 0 ? 1 : Math.max(0.25, 1 - distancia * 0.3),
              filter: distancia === 0 ? 'none' : `blur(${Math.min(5, distancia * 1.6)}px)`,
            }}
            onClick={() => aoEscolher(andar.id)}
            aria-current={distancia === 0 ? 'true' : undefined}
          >
            <span className="plano-rotulo">
              <b>{andar.nome}</b>
              <span>{andar.objetos.length === 0 ? 'vazio' : `${andar.objetos.length} obj`}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
