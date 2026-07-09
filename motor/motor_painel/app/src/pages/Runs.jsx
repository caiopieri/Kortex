import { useState } from 'react';
import { usePoll, fetchRuns, getRun } from '../api.js';
import StatusShape from '../components/StatusShape';

const estadoCor = {
  concluida: 'var(--green)',
  abortada: 'var(--red)',
  ativa: 'var(--blue)',
};

export default function Runs({ route }) {
  /* Extract id from route: /runs/:id */
  const parts = route.split('/');
  const selectedId = parts.length > 2 && parts[2] ? parts[2] : null;

  if (selectedId) {
    return <RunDetalhe id={selectedId} />;
  }
  return <RunList />;
}

function RunList() {
  const { data: runs, error } = usePoll(fetchRuns);

  const onClick = (id) => {
    window.location.hash = `/runs/${id}`;
  };

  if (error) {
    return (
      <div>
        <span className="num">Runs</span>
        <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
          <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
        </div>
      </div>
    );
  }

  if (!runs) {
    return (
      <div>
        <span className="num">Runs</span>
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text2)' }}>Carregando...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span className="num">Runs & Histórico</span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>
          {runs.length} missão{runs.length !== 1 ? 's' : ''} · poll 2s
        </span>
      </div>

      {runs.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
          <div className="title" style={{ fontSize: 17, color: 'var(--text3)' }}>
            Nenhuma missão registrada
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16 }}>
          {runs.map((run) => (
            <div
              key={run.id}
              className="card hov"
              onClick={() => onClick(run.id)}
              style={{
                padding: '14px 16px',
                display: 'grid',
                gridTemplateColumns: '1fr auto auto auto',
                gap: 16,
                alignItems: 'center',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                  {run.objetivo || run.id}
                </div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                  {run.id}
                </div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 100 }}>
                <div className="eyebrow">Estado</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center', marginTop: 4 }}>
                  <StatusShape kind={run.estado} />
                  <span className="mono" style={{
                    fontSize: 11,
                    color: estadoCor[run.estado] || 'var(--text2)',
                    textTransform: 'uppercase',
                  }}>
                    {run.estado || '—'}
                  </span>
                </div>
              </div>
              <div style={{ textAlign: 'center', minWidth: 80 }}>
                <div className="eyebrow">Custo</div>
                <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                  {typeof run.custo === 'number' ? `US$ ${run.custo.toFixed(2)}` : '—'}
                </span>
              </div>
              <div style={{ textAlign: 'center', minWidth: 60 }}>
                <div className="eyebrow">Eventos</div>
                <span className="mono" style={{ fontSize: 13 }}>{run.n_eventos || 0}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RunDetalhe({ id }) {
  const { data, error } = usePoll(() => getRun(id), [id]);

  if (error) {
    return (
      <div>
        <span className="num">Run · {id}</span>
        <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
          <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
        </div>
      </div>
    );
  }
  
  if (!data) {
    return (
      <div>
        <span className="num">Run · {id}</span>
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text2)' }}>Carregando...</span>
        </div>
      </div>
    );
  }

  const run = data.run || {};
  const eventos = data.eventos || [];
  const gates = data.gates || [];

  return (
    <div>
      <div
        onClick={() => { window.location.hash = '/runs'; }}
        style={{ cursor: 'pointer', marginBottom: 12 }}
      >
        <span className="lnk" style={{
          fontFamily: 'IBM Plex Mono, monospace',
          fontSize: 10,
          letterSpacing: 0.6,
          textTransform: 'uppercase',
          color: 'var(--text2)',
        }}>← voltar</span>
      </div>

      <span className="num">Run · {run.id || id}</span>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16 }}>
          <div>
            <div className="eyebrow">Estado</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
              <StatusShape kind={run.estado} />
              <span className="mono" style={{
                fontSize: 13, fontWeight: 600,
                color: estadoCor[run.estado] || 'var(--text2)',
              }}>{run.estado || '—'}</span>
            </div>
          </div>
          <div>
            <div className="eyebrow">Custo</div>
            <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
              {typeof run.custo === 'number' ? `US$ ${run.custo.toFixed(2)}` : '—'}
            </span>
          </div>
          <div>
            <div className="eyebrow">Eventos</div>
            <span className="mono" style={{ fontSize: 13 }}>{run.n_eventos || eventos.length}</span>
          </div>
          <div>
            <div className="eyebrow">Início</div>
            <span className="mono" style={{ fontSize: 13 }}>{run.inicio || '—'}</span>
          </div>
        </div>
        {run.objetivo && (
          <div style={{ marginTop: 12 }}>
            <div className="eyebrow">Objetivo</div>
            <span className="mono" style={{ fontSize: 12 }}>{run.objetivo}</span>
          </div>
        )}
      </div>

      {gates.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <span className="num">Gates</span>
          <div className="card" style={{ padding: 12, marginTop: 8 }}>
            {gates.map((g, i) => (
              <div key={i} className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text2)', padding: '4px 0' }}>
                <StatusShape kind="amber" />
                <span>{g.evento || g.portao || 'gate'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <span className="num">Eventos ({eventos.length})</span>
        <div className="card" style={{ marginTop: 8, maxHeight: 400, overflow: 'auto' }}>
          {eventos.map((ev, i) => (
            <div
              key={i}
              style={{
                display: 'flex', gap: 12, padding: '8px 12px',
                borderBottom: '1px solid var(--border)',
                fontFamily: 'IBM Plex Mono, monospace', fontSize: 11,
              }}
            >
              <span style={{ color: 'var(--text3)', width: 50, flex: 'none' }}>
                {typeof ev.t === 'number' ? ev.t.toFixed(3) : ev.t || ''}
              </span>
              <span style={{ color: 'var(--text)' }}>{ev.evento || ''}</span>
              {ev.executor && (
                <span style={{ color: 'var(--text2)' }}>· {ev.executor}</span>
              )}
              {ev.portao && (
                <span style={{ color: 'var(--accent)' }}>· {ev.portao}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
