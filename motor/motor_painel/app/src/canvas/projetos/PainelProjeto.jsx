import { usePresenca } from '../ui/usePresenca.js';
import { useArrastavel } from '../ui/useArrastavel.js';

/* O seletor de andar e projeto.
 *
 * Duas dimensoes, e a superficie e o par das duas: o ANDAR e a casa/harness
 * (`DECISAO-canvas-e-operacao.md` §4 — softwarehouse, hardware, mecanica,
 * treinamento) e o PROJETO e o que se constroi dentro dela. Por isso o andar
 * rola na horizontal, como quem anda pelo predio, e o projeto na vertical, como
 * lista.
 *
 * Escolher aqui vai DIRETO para a superficie escolhida — o painel nao passa
 * pela vista em perspectiva. A perspectiva continua existindo no botao
 * "Andares", que e outra coisa: la se olha a pilha, aqui se troca de sala.
 *
 * O painel se arrasta pelo pegador e nao fecha ao escolher: e ferramenta que
 * fica aberta enquanto se compara, nao menu de uma decisao so.
 */

export function PainelProjeto({
  aberto,
  andares,
  andarAtivoId,
  aoEscolherAndar,
  projetos,
  projetoAtivoId,
  aoEscolherProjeto,
  runs = [],
  runAtivaId,
  aoEscolherRun,
}) {
  const { montado, dentro } = usePresenca(aberto);
  const { alvo, arrastando, pegador, estilo } = useArrastavel();

  if (!montado) return null;

  return (
    <div
      className="pp"
      ref={alvo}
      data-dentro={dentro ? 'sim' : 'nao'}
      /* Enquanto arrasta, a transicao de transform sai do caminho: ela
         atrasaria o painel em relacao ao ponteiro. */
      data-arrastando={arrastando ? 'sim' : 'nao'}
      style={estilo}
    >
      <div className="pp-pegador" data-arrastando={arrastando ? 'sim' : 'nao'} {...pegador}>
        <span />
      </div>

      <div className="pp-secao">
        <div className="pp-titulo mono">Andar</div>
        <div className="pp-trilho">
          {andares.map((andar) => (
            <button
              key={andar.id}
              type="button"
              className="pp-chip"
              data-ativo={andar.id === andarAtivoId ? 'sim' : 'nao'}
              onClick={() => aoEscolherAndar(andar.id)}
            >
              {andar.nome}
            </button>
          ))}
        </div>
      </div>

      <div className="pp-secao">
        <div className="pp-titulo mono">Projeto</div>
        <div className="pp-lista">
          {projetos.map((projeto) => (
            <button
              key={projeto.id}
              type="button"
              className="pp-item"
              data-ativo={projeto.id === projetoAtivoId ? 'sim' : 'nao'}
              onClick={() => aoEscolherProjeto(projeto.id)}
            >
              {projeto.nome}
            </button>
          ))}
        </div>
      </div>

      <div className="pp-secao">
        <div className="pp-titulo mono">Run</div>
        <div className="pp-lista">
          {runs.length === 0 && <p className="pp-vazio mono">nenhuma run no ledger</p>}
          {[...runs].reverse().map((run) => (
            <button
              key={run.id}
              type="button"
              className="pp-item pp-run"
              data-ativo={run.id === runAtivaId ? 'sim' : 'nao'}
              data-desfecho={run.desfecho}
              onClick={() => aoEscolherRun(run.id)}
              title={run.motivoDoFim ?? run.desfecho}
            >
              <span className="pp-run-nome">{run.missao ?? 'sem missão'}</span>
              <span className="pp-run-seq mono">
                {run.fonte} {run.seqDe}–{run.seqAte}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Andar e projeto sao lista fixa no codigo; run vem do ledger. O rodape
          separa as duas origens, senao o painel faz os tres parecerem cadastro
          da mesma fonte. */}
      <div className="pp-rodape mono">
        <i />
        andar e projeto fixos no código · {runs.length} runs lidas do ledger
      </div>
    </div>
  );
}
