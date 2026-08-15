/* Runners — maquinas onde a fabrica executa trabalho.
 *
 * O painel NAO tem fonte para isto. Nao existe /dados/runners, e o log nao
 * registra host, IP nem capacidade de maquina. Enquanto nao existir, esta tela
 * declara a ausencia em vez de desenhar maquinas de exemplo: um runner falso
 * marcado como "online" e pior que tela vazia, porque afirma sobre a
 * infraestrutura de quem le.
 */

export default function Runners() {
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Runners</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
          máquinas de execução
        </span>
      </div>

      <div className="card" style={{ padding: 28, marginTop: 16, textAlign: 'center' }}>
        <div className="title" style={{ fontSize: 15, color: 'var(--text)' }}>
          Sem registro de runners
        </div>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--text2)', lineHeight: 1.7, maxWidth: 460, margin: '10px auto 0' }}>
          O motor executa como processo local nesta máquina. Ele não registra
          host, IP nem capacidade no log, então o painel não tem o que mostrar
          aqui — e não vai inventar.
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: 'var(--text3)', marginTop: 12 }}>
          Os executores configurados estão em{' '}
          <span className="lnk" onClick={() => { window.location.hash = '/conexoes'; }}>Conexões</span>.
        </div>
      </div>
    </>
  );
}
