import { useMemo } from 'react';
import { usePoll, fetchDados } from '../api.js';

const RUNNERS_PRESETS = [
  { id: 'local-macbook', nome: 'MacBook Pro M4', tipo: 'local', caps: ['docker', 'python', 'node', 'xcode'], ip: '127.0.0.1', status: 'online' },
  { id: 'remote-gpu-1', nome: 'GPU Server #1', tipo: 'remoto', caps: ['docker', 'python', 'cuda', 'fatiador-3d'], ip: '10.0.1.42', status: 'online' },
  { id: 'ci-github', nome: 'GitHub Actions', tipo: 'ci', caps: ['docker', 'python', 'node'], ip: '—', status: 'idle' },
];

export default function Runners() {
  const { data: fullData } = usePoll(fetchDados);

  /* Determine runner health from events */
  const runners = useMemo(() => {
    const eventos = fullData?.eventos || [];
    return RUNNERS_PRESETS.map(r => {
      const toolErrors = eventos.filter(ev =>
        ev.evento === 'ferramenta.indisponivel' &&
        r.caps.some(c => (ev.ferramenta || '').includes(c))
      );
      const status = toolErrors.length > 0 ? 'degradado' : r.status;
      /* Count queue items */
      const queue = eventos.filter(ev =>
        ev.evento === 'executor.chamado' &&
        !eventos.some(e2 => e2.evento === 'executor.respondeu' && e2.executor === ev.executor && e2.tentativa === ev.tentativa)
      ).length;
      return { ...r, status, queue: Math.min(queue, 5), toolErrors: toolErrors.length };
    });
  }, [fullData]);

  const statusShape = (s) => {
    if (s === 'online') return 'sh green';
    if (s === 'degradado') return 'sh amber';
    if (s === 'offline') return 'sh red';
    return 'sh idle';
  };

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Runners</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>nenhum runner real registrado</span>
      </div>

      {/* Runner cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
        {runners.map(r => (
          <div key={r.id} className="card" style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span className={statusShape(r.status)}></span>
              <span className="title" style={{ fontSize: 15, flex: 1 }}>{r.nome} <span className="chip" style={{ fontSize: 9, fontWeight: 'normal', marginLeft: 6 }}>exemplo · não conectado</span></span>
              <span className="mono" style={{ fontSize: 10, color: r.status === 'online' ? 'var(--green)' : r.status === 'degradado' ? 'var(--amber)' : 'var(--text3)' }}>{r.status}</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{r.tipo}</span>
            </div>

            <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
              <div>
                <span className="eyebrow" style={{ fontSize: 8 }}>IP</span>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text2)' }}>{r.ip}</div>
              </div>
              <div>
                <span className="eyebrow" style={{ fontSize: 8 }}>Fila</span>
                <div className="mono" style={{ fontSize: 11, color: r.queue > 0 ? 'var(--blue)' : 'var(--text3)' }}>{r.queue} pendente{r.queue !== 1 ? 's' : ''}</div>
              </div>
              {r.toolErrors > 0 && (
                <div>
                  <span className="eyebrow" style={{ fontSize: 8 }}>Erros</span>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--red)' }}>{r.toolErrors} ferramenta{r.toolErrors !== 1 ? 's' : ''}</div>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {r.caps.map(c => (
                <span key={c} className="pill" style={{ fontSize: 9, padding: '2px 7px' }}>{c}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
