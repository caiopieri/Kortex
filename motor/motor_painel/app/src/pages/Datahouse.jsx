import { useMemo } from 'react';
import { usePoll, fetchDados } from '../api.js';

export default function Datahouse() {
  const { data, error } = usePoll(fetchDados);

  const artefatos = useMemo(() => {
    if (!data?.eventos) return [];
    const arts = [];
    const seen = new Set();
    data.eventos.forEach(ev => {
      if (['artefato.atualizou', 'artefato.gravado', 'artefato.atualizado'].includes(ev.evento)) {
        const path = ev.caminho || ev.artefato || ev.arquivo;
        if (path && !seen.has(path)) {
          seen.add(path);
          arts.push({
            path,
            run: ev.missao || ev.run || '—',
            executor: ev.executor || '—',
            t: ev.t,
          });
        }
      }
    });
    return arts.reverse();
  }, [data]);

  /* Aggregate by extension */
  const byExt = useMemo(() => {
    const m = {};
    artefatos.forEach(a => {
      const ext = a.path.split('.').pop() || 'outro';
      if (!m[ext]) m[ext] = 0;
      m[ext]++;
    });
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [artefatos]);

  /* Aggregate by run */
  const byRun = useMemo(() => {
    const m = {};
    artefatos.forEach(a => {
      if (!m[a.run]) m[a.run] = 0;
      m[a.run]++;
    });
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [artefatos]);

  if (error) return (
    <div>
      <span className="num">Datahouse</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!data) return (
    <div>
      <span className="num">Datahouse</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Datahouse</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>artefatos gerados · fontes de dados</span>
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 16 }}>
        <div className="kpi">
          <div className="eyebrow">Artefatos</div>
          <div className="kbig">{artefatos.length}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>arquivos únicos gerados</div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Tipos</div>
          <div className="kbig">{byExt.length}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>extensões distintas</div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Runs produtores</div>
          <div className="kbig">{byRun.length}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>runs com artefatos</div>
        </div>
      </div>

      {/* Two columns: by type + by run */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 20 }}>
        <div>
          <div className="num" style={{ marginBottom: 10 }}>01 — Por tipo de arquivo</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {byExt.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Nenhum artefato ainda</span></div>}
            {byExt.map(([ext, count]) => (
              <div key={ext} className="trow">
                <span className="mono" style={{ color: 'var(--text)', width: 60, flex: 'none' }}>.{ext}</span>
                <div style={{ flex: 1, height: 6, background: 'var(--surface2)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, (count / Math.max(1, artefatos.length)) * 100)}%`, background: 'var(--blue)', borderRadius: 2 }}></div>
                </div>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', width: 30, textAlign: 'right', flex: 'none' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="num" style={{ marginBottom: 10 }}>02 — Por run</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {byRun.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Nenhuma run com artefatos</span></div>}
            {byRun.map(([run, count]) => (
              <div key={run} className="trow" style={{ cursor: 'pointer' }} onClick={() => { window.location.hash = `/runs/${run}`; }}>
                <span className="sh green"></span>
                <span style={{ color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', flex: 'none' }}>{count} arquivo{count !== 1 ? 's' : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent artifacts list */}
      <div style={{ marginTop: 20 }}>
        <div className="num" style={{ marginBottom: 10 }}>03 — Últimos artefatos gerados</div>
        <div className="card" style={{ padding: '4px 16px' }}>
          {artefatos.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Nenhum artefato registrado nos eventos</span></div>}
          {artefatos.slice(0, 12).map((a, i) => (
            <div key={i} className="trow">
              <span className="sh green"></span>
              <span className="mono" style={{ color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>{a.path}</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', flex: 'none' }}>{a.executor}</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', flex: 'none', width: 60, textAlign: 'right' }}>{a.run.length > 8 ? a.run.slice(-6) : a.run}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
