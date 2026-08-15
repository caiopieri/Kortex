import { usePresenca } from '../ui/usePresenca.js';
import { useArrastavel } from '../ui/useArrastavel.js';
import { Seta, Vassoura } from '../ui/Icones.jsx';

/* Painel de notificacoes — mesma linguagem do painel de projeto: arrasta pelo
 * pegador, dois cliques devolve ao canto, nao fecha ao clicar num item.
 *
 * O QUE ELE NAO E, e o rodape diz isso na tela: nao ha fila de notificacao no
 * motor. Confirmado com o coordenador — nenhum evento, tabela, endpoint ou
 * campo de destino existe, e ninguem esta construindo. Entao esta lista e
 * DERIVADA do andon sobre o ledger, e cada item aponta para algo que ja existe
 * na superficie ou declara que nao tem para onde levar.
 *
 * "Limpar" e estado do cliente e sO isso: nao ha onde persistir "lido", e o
 * ledger continua dizendo a mesma coisa. Recarregar traz tudo de volta — e o
 * rodape avisa, porque um botao que parece apagar e nao apaga e pior do que
 * botao nenhum.
 */

const ROTULO = {
  terminal: 'terminal',
  sistemica: 'sistêmica',
  localizada: 'nó',
  leitura: 'leitura',
};

export function PainelNotificacoes({ aberto, avisos, aoIr, aoLimpar, aoDispensar }) {
  const { montado, dentro } = usePresenca(aberto);
  const { alvo, arrastando, pegador, estilo } = useArrastavel();

  if (!montado) return null;

  return (
    <div
      className="pp pn"
      ref={alvo}
      data-dentro={dentro ? 'sim' : 'nao'}
      data-arrastando={arrastando ? 'sim' : 'nao'}
      style={estilo}
    >
      <div className="pp-pegador" data-arrastando={arrastando ? 'sim' : 'nao'} {...pegador}>
        <span />
      </div>

      <div className="pn-topo">
        <div className="pp-titulo mono">Notificações</div>
        <button
          type="button"
          className="pn-limpar"
          onClick={aoLimpar}
          disabled={avisos.length === 0}
          title="Limpar tudo — só nesta aba"
        >
          <Vassoura />
          Limpar
        </button>
      </div>

      <div className="pp-lista pn-lista">
        {avisos.length === 0 && <p className="pp-vazio mono">nada a reportar no ledger lido</p>}

        {avisos.map((a) => (
          <div key={a.id} className="pn-item" data-severidade={a.severidade}>
            <button
              type="button"
              className="pn-ir"
              onClick={() => aoIr(a)}
              /* Sem destino o botao NAO vira link morto: fica desabilitado e o
                 titulo diz por que. Buraco no seq aponta para o arquivo, nao
                 para um lugar da superficie. */
              disabled={!a.destino}
              title={a.destino ? 'Ir até o lugar que notificou' : 'Este aviso não tem destino'}
            >
              <span className="pn-cabeca">
                <span className="pn-tag mono">{ROTULO[a.severidade]}</span>
                <b>{a.titulo}</b>
              </span>
              <span className="pn-detalhe">{a.detalhe}</span>
              {a.destino && (
                <span className="pn-destino mono">
                  {a.destino.missao ?? 'sem missão'}
                  {a.destino.no ? ` · ${a.destino.no}` : a.destino.estacao ? ' · pré-voo' : ''}
                  <Seta />
                </span>
              )}
            </button>
            <button
              type="button"
              className="pn-dispensar"
              aria-label="Dispensar"
              title="Dispensar"
              onClick={() => aoDispensar(a.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="pp-rodape mono">
        <i />
        derivado do ledger · não há fila de notificação no motor · limpar é só nesta aba
      </div>
    </div>
  );
}
