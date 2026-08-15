/* O grafo da run desenhado na superficie, em unidades de mundo.
 *
 * POSICAO: derivada da onda DECLARADA (`onda.iniciada`), que e a camada
 * topologica que o ledger emite. Coluna = onda, linha = ordem dentro da onda.
 * Nao ha coordenada no ledger e a superficie nao finge que ha — o rodape diz
 * "posicao derivada da onda". Derivar layout de grafo declarado e diferente de
 * inventar onde uma falha mora; o segundo e o que o ROADMAP proibe.
 *
 * A ESTACAO DE PRE-VOO fica num ponto FIXO do mundo, sempre o mesmo, a esquerda
 * da primeira onda. Falha sistemica nao ganha posicao propria: ela ganha ESTE
 * destino. Fixo e o ponto — se ela flutuasse junto com o grafo, voltaria a
 * parecer que a falha tem lugar.
 */

import { ESTACAO, LARGURA_NO, posicionarNos, TETO_FALHAS } from './layout.js';

/* O excedente de falhas NAO some em silencio: o cartao diz quantas nao estao a
   mostra. Superficie que esconde falha e o oposto do que ela existe para fazer.
   `TETO_FALHAS` vem do layout porque a altura estimada depende dele. */
const TETO_ESTACAO = 6;

export function Grafo({ run, artefatoAberto, aoAbrirArtefato }) {
  if (!run) return null;

  const lugares = posicionarNos(run);

  return (
    <>
      <svg className="fluxo" aria-hidden="true">
        {run.arestas.map((a) => {
          const de = lugares.get(a.de);
          const para = lugares.get(a.para);
          if (!de || !para) return null;
          const x1 = de.x + LARGURA_NO;
          const y1 = de.y + 34;
          const x2 = para.x;
          const y2 = para.y + 34;
          const meio = (x1 + x2) / 2;
          return (
            <path
              key={`${a.de}-${a.para}`}
              className="fluxo-aresta"
              d={`M ${x1} ${y1} C ${meio} ${y1}, ${meio} ${y2}, ${x2} ${y2}`}
            />
          );
        })}
      </svg>

      {run.nos.map((no) => {
        const p = lugares.get(no.id);
        return (
          <article
            key={no.id}
            className="no"
            data-estado={no.estado}
            style={{ transform: `translate(${p.x}px, ${p.y}px)` }}
          >
            <header className="no-topo">
              <span className="no-id">{no.id}</span>
              <span className="no-papel mono">{no.papel ?? 'sem papel'}</span>
            </header>

            {no.artefatos.map((a) => (
              <button
                key={a.chave}
                type="button"
                className="no-artefato"
                data-aberto={artefatoAberto?.caminho === a.caminho ? 'sim' : 'nao'}
                onClick={() => aoAbrirArtefato(a)}
                disabled={!a.caminho}
                title={a.caminho ?? 'evento sem caminho'}
              >
                <span>{a.nome}</span>
                <span className="mono">
                  {a.revisoes > 1 ? `${a.revisoes}× · ` : ''}
                  {a.tipo ?? '—'}
                </span>
              </button>
            ))}

            {no.falhas.slice(0, TETO_FALHAS).map((f) => (
              <Falha key={f.seq} falha={f} />
            ))}
            {no.falhas.length > TETO_FALHAS && (
              <p className="no-mais mono">
                +{no.falhas.length - TETO_FALHAS} falha
                {no.falhas.length - TETO_FALHAS === 1 ? '' : 's'} não exibida
                {no.falhas.length - TETO_FALHAS === 1 ? '' : 's'}
              </p>
            )}
          </article>
        );
      })}

      {/* Sempre montada, mesmo vazia: e uma estacao do andar, nao um alerta que
          aparece so quando ha problema. Some-la quando esta limpa faria a
          superficie parecer nao ter o conceito. */}
      <section
        className="estacao"
        data-carregada={run.sistemicas.length > 0 ? 'sim' : 'nao'}
        style={{ transform: `translate(${ESTACAO.x}px, ${ESTACAO.y}px)` }}
      >
        <header className="estacao-topo">
          <b>Pré-voo</b>
          <span className="mono">
            {run.sistemicas.length === 0 ? 'sem falha sistêmica' : `${run.sistemicas.length}`}
          </span>
        </header>
        <p className="estacao-regra">
          Falha que não nomeia nó resolve aqui. A superfície não inventa onde ela mora.
        </p>
        {run.sistemicas.slice(0, TETO_ESTACAO).map((f) => (
          <Falha key={f.seq} falha={f} naEstacao />
        ))}
        {run.sistemicas.length > TETO_ESTACAO && (
          <p className="no-mais mono">
            +{run.sistemicas.length - TETO_ESTACAO} não exibidas
          </p>
        )}
      </section>
    </>
  );
}

/* Uma falha desenhada. `data-forma` e o que separa visualmente as duas coisas
   que nao podem ser confundidas: `bloqueio-pre-efeito` (nada aconteceu, seguro,
   retentavel) e `terminal-ambiguo` (a cadeia parou, pode ter havido efeito
   cobrado, exige run_id nova). O rotulo diz o efeito em palavra, nao so em cor —
   cor cromatica aqui e telemetria, mas telemetria tambem precisa ser legivel
   sem enxergar cor. */
function Falha({ falha, naEstacao }) {
  const c = falha.custo ?? {};
  return (
    <p
      className={naEstacao ? 'estacao-item' : 'no-falha'}
      data-forma={c.forma ?? 'nao-declarado'}
      /* Terminal NAO descartado nao e o mesmo que terminal confirmado: a
         ausencia do `(status)` pode ser truncamento. O tracejado marca a
         duvida sem afirmar o pior. */
      data-terminal-descartado={
        c.terminalDescartado === true ? 'sim' : c.terminalDescartado === false ? 'nao' : 'na'
      }
    >
      <span className="falha-cabeca mono">
        {falha.evento}
        {falha.tentativa ? ` #${falha.tentativa}` : ''}
      </span>
      {falha.motivo && falha.motivo !== falha.evento ? (
        <span className="falha-motivo" title={falha.motivo}>
          {falha.motivo}
        </span>
      ) : null}
      {c.rotulo ? <em className="falha-efeito">{c.rotulo}</em> : null}
      {c.rotas?.length ? (
        <span className="falha-rotas mono">
          {c.rotas.map((r) => `${r.rota}${r.motivo ? `=${r.motivo}` : ''}`).join(' · ')}
        </span>
      ) : null}
      {falha.naoResolvido ? (
        <em className="falha-efeito">
          citou “{falha.naoResolvido}”, que não está no grafo desta run
        </em>
      ) : null}
    </p>
  );
}
