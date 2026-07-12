import { useMemo } from 'react';
import { usePoll, getAgents, getCosts, fetchDados } from '../api.js';

export default function Curador() {
  const { data: agents, error: e1 } = usePoll(getAgents);
  const { data: costs } = usePoll(getCosts);
  const { data: fullData } = usePoll(fetchDados);

  const error = e1;

  /* Model performance analysis from events */
  const modelStats = useMemo(() => {
    if (!fullData?.eventos) return [];
    const stats = {};
    fullData.eventos.forEach(ev => {
      const model = ev.modelo || ev.provedor;
      if (!model) return;
      if (!stats[model]) stats[model] = { model, chamadas: 0, erros: 0, aprovacoes: 0, reprovacoes: 0, latencias: [], custos: [] };
      if (ev.evento === 'executor.chamado') stats[model].chamadas++;
      if (ev.evento === 'executor.erro' || ev.evento === 'modelo.falha') stats[model].erros++;
      if (ev.evento === 'portao.aprovado') stats[model].aprovacoes++;
      if (ev.evento === 'portao.reprovado') stats[model].reprovacoes++;
    });
    return Object.values(stats).sort((a, b) => b.chamadas - a.chamadas);
  }, [fullData]);

  /* Propostas do curador */
  const propostas = useMemo(() => {
    if (!fullData?.eventos) return [];
    return fullData.eventos
      .filter(ev => ev.evento === 'proposta.curador' || ev.evento === 'proposta.orquestrador')
      .reverse()
      .slice(0, 5);
  }, [fullData]);

  /* Agent comparison */
  const agentList = useMemo(() => {
    if (!agents) return [];
    return agents.map(a => ({
      papel: a.papel || a.id,
      chamadas: a.chamadas || 0,
      erros: a.falhas || 0,
      pct: a.chamadas > 0 ? Math.round(((a.chamadas - (a.falhas || 0)) / a.chamadas) * 100) : 0,
    })).sort((a, b) => b.chamadas - a.chamadas);
  }, [agents]);

  if (error) return (
    <div>
      <span className="num">Curador</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!agents || !fullData) return (
    <div>
      <span className="num">Curador</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando análise…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Curador</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>análise de desempenho · propostas de catálogo</span>
      </div>

      {/* Propostas */}
      <div style={{ marginTop: 16 }}>
        <div className="num" style={{ marginBottom: 10 }}>01 — Propostas do Curador</div>
        {propostas.length === 0 ? (
          <div className="card" style={{ padding: 20, textAlign: 'center' }}>
            <span className="mono" style={{ color: 'var(--text3)' }}>Nenhuma proposta pendente. O curador avalia automaticamente após runs suficientes.</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {propostas.map((p, i) => (
              <div key={i} className="card" style={{ padding: '10px 14px', borderLeftColor: 'var(--amber)', borderLeftWidth: 2 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span className="sh amber"></span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--amber)' }}>{p.evento}</span>
                  <div style={{ flex: 1 }}></div>
                  <span className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>
                    {p.t ? new Date(p.t * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'}
                  </span>
                </div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>{p.detalhe || p.mensagem || JSON.stringify(p)}</div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <span className="btn btn-sm btn-primary" onClick={() => { window.location.hash = '/caixa'; }}>Decidir na Caixa →</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Two columns: model perf + agent comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 20 }}>
        {/* Model performance */}
        <div>
          <div className="num" style={{ marginBottom: 10 }}>02 — Desempenho por modelo</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {modelStats.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Sem dados de modelos nos eventos</span></div>}
            {modelStats.map((m, i) => {
              const rate = m.chamadas > 0 ? Math.round(((m.chamadas - m.erros) / m.chamadas) * 100) : 0;
              return (
                <div key={i} className="trow">
                  <span className={m.erros > 0 ? 'sh amber' : 'sh green'}></span>
                  <span style={{ color: 'var(--text)', flex: 1 }}>{m.model}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', width: 50, textAlign: 'right', flex: 'none' }}>{m.chamadas} ch</span>
                  <span className="mono" style={{ fontSize: 10, color: m.erros > 0 ? 'var(--red)' : 'var(--text3)', width: 40, textAlign: 'right', flex: 'none' }}>{m.erros} err</span>
                  <span className="mono" style={{ fontSize: 10, color: rate >= 80 ? 'var(--green)' : 'var(--amber)', width: 35, textAlign: 'right', flex: 'none' }}>{rate}%</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Agent comparison */}
        <div>
          <div className="num" style={{ marginBottom: 10 }}>03 — Comparativo de agentes</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {agentList.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Sem agentes registrados</span></div>}
            {agentList.map((a, i) => (
              <div key={i} className="trow">
                <span className={a.erros > 0 ? 'sh amber' : a.chamadas > 0 ? 'sh green' : 'sh idle'}></span>
                <span style={{ color: 'var(--text)', flex: 1 }}>{a.papel}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', width: 50, textAlign: 'right', flex: 'none' }}>{a.chamadas} ch</span>
                <span className="mono" style={{ fontSize: 10, color: a.pct >= 80 ? 'var(--green)' : 'var(--amber)', width: 35, textAlign: 'right', flex: 'none' }}>{a.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
