import { FONTES } from './ler.js';

/* O selo diz o que foi lido, de onde, quando — e o que NAO foi lido.
 *
 * Substitui o antigo "superficie sem dado": agora ha dado, e o que precisa ser
 * honesto e a procedencia. Tres coisas que ele nunca faz:
 *   - chamar buraco no seq de corrupcao (pode ser evento monetario ainda no
 *     budget_outbox — durável, so nao publicado);
 *   - omitir que o log do servico nao e lido (divida 17(b));
 *   - deixar passar falha cuja forma de motivo nao permite afirmar nada sobre
 *     efeito.
 */

const NAO_LIDAS = FONTES.filter((f) => !f.lida);

export function SeloLeitura({ estado, run, aoRecarregar }) {
  if (estado.fase === 'carregando') {
    return (
      <div className="selo-vazio mono">
        <i />
        lendo {FONTES[0].rotulo}
      </div>
    );
  }

  if (estado.fase === 'erro') {
    return (
      <div className="selo-vazio mono" data-alerta="sim">
        <i />
        ledger ilegível · {estado.motivo}
        <button type="button" className="selo-acao" onClick={aoRecarregar}>
          reler
        </button>
      </div>
    );
  }

  const { leitura } = estado;
  const ausentes = leitura.buracos.reduce((n, b) => n + b.faltando, 0);
  const suspeito = ausentes > 0 || leitura.ilegiveis.length > 0 || Boolean(run?.terminal);

  return (
    <div className="selo-vazio mono" data-alerta={suspeito ? 'sim' : 'nao'}>
      <i />
      {run ? `${run.missao ?? 'sem missão'} · ${run.fonte} seq ${run.seqDe}–${run.seqAte}` : 'nenhuma run'}
      {` · ${leitura.eventos.length} eventos`}
      {ausentes > 0 ? ` · ${ausentes} ausentes no seq (causa não declarada)` : ''}
      {leitura.ilegiveis.length > 0 ? ` · ${leitura.ilegiveis.length} linhas ilegíveis` : ''}
      {leitura.caudaParcial ? ' · cauda parcial (escrita em curso)' : ''}
      {leitura.reinicios > 0 ? ` · ${leitura.reinicios} reinício de arquivo` : ''}
      {run?.terminal ? ' · FALHA TERMINAL: efeito desconhecido, exige run nova' : ''}
      {run?.naoDeclaradas > 0
        ? ` · ${run.naoDeclaradas} falha(s) sem forma declarada de motivo`
        : ''}
      {NAO_LIDAS.length > 0 ? ` · não lê ${NAO_LIDAS.map((f) => f.rotulo).join(', ')}` : ''}
      {` · lido ${new Date(leitura.lidoEm).toLocaleTimeString('pt-BR')}`}
      <button type="button" className="selo-acao" onClick={aoRecarregar}>
        {estado.fase === 'relendo' ? 'relendo' : 'reler'}
      </button>
    </div>
  );
}
