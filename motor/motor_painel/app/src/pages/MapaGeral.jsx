import { useMemo } from 'react';
import { usePoll, fetchRuns, fetchDados, getAgents, getMissaoAtiva } from '../api.js';

function shapeFor(estado) {
  if (estado === 'ativa')     return 'sh blue pulse';
  if (estado === 'concluida') return 'sh green';
  if (estado === 'abortada')  return 'sh red';
  return 'sh idle';
}

export default function MapaGeral() {
  const { data: runs, error: e1 } = usePoll(fetchRuns);
  const { data: fullData } = usePoll(fetchDados);
  const { data: agents } = usePoll(getAgents);
  const { data: missaoAtiva } = usePoll(getMissaoAtiva);

  const error = e1;
  const isLoading = !runs || !fullData;

  /* Aggregate projects */
  const projects = useMemo(() => {
    if (!runs) return [];
    const grouped = {};
    runs.forEach(r => {
      const key = r.objetivo || r.id;
      if (!grouped[key]) grouped[key] = { id: key, runs: [], totalCost: 0, eventos: 0 };
      grouped[key].runs.push(r);
      grouped[key].totalCost += r.custo || 0;
    });
    Object.values(grouped).forEach(g => {
      g.eventos = g.runs.reduce((acc, r) => acc + (r.n_eventos || 0), 0);
      g.estado = g.runs.some(r => r.estado === 'ativa') ? 'ativa'
        : g.runs.every(r => r.estado === 'concluida') ? 'concluida'
        : g.runs.every(r => r.estado === 'abortada') ? 'abortada' : 'mista';
    });
    return Object.values(grouped).sort((a, b) => b.totalCost - a.totalCost);
  }, [runs, fullData]);

  /* Agent summary */
  const agentSummary = useMemo(() => {
    if (!agents) return [];
    return agents.map(a => ({
      papel: a.papel || a.id,
      chamadas: a.chamadas || 0,
      erros: a.falhas || 0,
      shape: (a.falhas || 0) > 0 ? 'sh red' : (a.chamadas || 0) > 0 ? 'sh green' : 'sh idle',
    })).sort((a, b) => b.chamadas - a.chamadas).slice(0, 8);
  }, [agents]);

  if (error) return (
    <div>
      <span className="num">Mapa Geral</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (isLoading) return (
    <div>
      <span className="num">Mapa Geral</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando mapa…</span>
      </div>
    </div>
  );

  const totalCost = projects.reduce((a, p) => a + p.totalCost, 0);
  const totalRuns = runs.length;
  const activeRuns = runs.filter(r => r.estado === 'ativa').length;

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Mapa geral</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>visão orbital · todos os projetos</span>
        <div style={{ flex: 1 }}></div>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className={missaoAtiva?.ativa ? 'sh blue pulse' : 'sh idle'}></span>
          {missaoAtiva?.ativa ? 'AO VIVO' : 'OCIOSO'}
        </span>
      </div>

      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 16 }}>
        <div className="kpi">
          <div className="eyebrow">Projetos</div>
          <div className="kbig">{projects.length}</div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Runs totais</div>
          <div className="kbig">{totalRuns} <span style={{ fontSize: 13, color: 'var(--text3)' }}>({activeRuns} ativos)</span></div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Custo acumulado</div>
          <div className="kbig">US$ {totalCost.toFixed(2)}</div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Agentes ativos</div>
          <div className="kbig">{agentSummary.filter(a => a.chamadas > 0).length}</div>
        </div>
      </div>

      {/* Two-pane: projects + agents */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20, marginTop: 20, flex: 1, minHeight: 0 }}>
        {/* Projects canvas */}
        <div style={{ minWidth: 0 }}>
          <div className="num" style={{ marginBottom: 10 }}>01 — Projetos · atividade</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {projects.map(p => (
              <div key={p.id} className="card" style={{ padding: '12px 14px', cursor: 'pointer' }} onClick={() => { window.location.hash = '/runs'; }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span className={shapeFor(p.estado)}></span>
                  <span className="title" style={{ fontSize: 14, flex: 1 }}>{p.id}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{p.runs.length} run{p.runs.length !== 1 ? 's' : ''}</span>
                </div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>US$ {p.totalCost.toFixed(2)}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{p.eventos} eventos</span>
                  <span className="mono" style={{ fontSize: 10, color: p.estado === 'ativa' ? 'var(--blue)' : p.estado === 'concluida' ? 'var(--green)' : 'var(--text3)' }}>{p.estado}</span>
                </div>
              </div>
            ))}
            {projects.length === 0 && (
              <div className="card" style={{ padding: 30, textAlign: 'center' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>Nenhum projeto com runs no momento</span>
              </div>
            )}
          </div>
        </div>

        {/* Agents + Knowledge layer */}
        <div style={{ minWidth: 0 }}>
          <div className="num" style={{ marginBottom: 10 }}>02 — Agentes · conhecimento</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {agentSummary.map((a, i) => (
              <div key={i} className="trow">
                <span className={a.shape}></span>
                <span style={{ color: 'var(--text)', flex: 1 }}>{a.papel}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>{a.chamadas} ch</span>
                <span className="mono" style={{ fontSize: 10, color: a.erros > 0 ? 'var(--red)' : 'var(--text3)' }}>{a.erros} err</span>
              </div>
            ))}
            {agentSummary.length === 0 && (
              <div className="trow">
                <span className="mono" style={{ color: 'var(--text3)' }}>Sem agentes registrados</span>
              </div>
            )}
          </div>

          <div className="num" style={{ marginBottom: 10, marginTop: 20 }}>03 — Links rápidos</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="lnk" onClick={() => { window.location.hash = '/canvas'; }}>→ Canvas</span>
            <span className="lnk" onClick={() => { window.location.hash = '/board'; }}>→ Board de missões</span>
            <span className="lnk" onClick={() => { window.location.hash = '/datahouse'; }}>→ Datahouse</span>
            <span className="lnk" onClick={() => { window.location.hash = '/caixa'; }}>→ Caixa do Fundador</span>
          </div>
        </div>
      </div>
    </>
  );
}
