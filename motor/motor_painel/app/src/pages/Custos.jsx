import { useState } from 'react';
import { usePoll, getCosts, getGates } from '../api.js';

export default function Custos() {
  const { data, error } = usePoll(getCosts);
  const { data: gatesData } = usePoll(getGates);
  const gates = gatesData || [];
  const [groupBy, setGroupBy] = useState('run'); // 'run' | 'modelo'
  const [sortBy, setSortBy] = useState('cost'); // 'name' | 'cost' | 'tokens' | 'calls'
  const [sortDesc, setSortDesc] = useState(true);

  // Hover states for tooltips
  const [hoveredCostIndex, setHoveredCostIndex] = useState(null);
  const [hoveredTokenIndex, setHoveredTokenIndex] = useState(null);

  if (error) {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span className="num">Custos</span>
        </div>
        <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
          <span className="mono" style={{ color: 'var(--red)' }}>Erro ao carregar dados: {error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span className="num">Custos</span>
        </div>
        <div className="card" style={{ padding: 16, marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text2)' }}>Carregando dados de custos...</span>
        </div>
      </div>
    );
  }

  const rawRuns = data.por_run || [];
  const rawModels = data.por_modelo || [];

  // Sessão inteira: eventos não têm timestamp absoluto, então não há recorte temporal honesto
  const filteredRuns = rawRuns;
  const filteredModels = rawModels;

  // Calculate dynamic totals
  const totalCusto = filteredRuns.reduce((sum, r) => sum + r.custo_total, 0);
  const totalTokens = filteredRuns.reduce((sum, r) => sum + r.tokens_total, 0);
  const totalCalls = filteredRuns.reduce((sum, r) => sum + r.n_chamadas, 0);
  const avgCostPerCall = totalCalls > 0 ? totalCusto / totalCalls : 0;

  // Find overall top source (model)
  const topModel = filteredModels.reduce((max, m) => m.custo_total > max.custo_total ? m : max, { modelo: 'Nenhum', custo_total: 0 });
  const topModelPct = totalCusto > 0 ? Math.round((topModel.custo_total / totalCusto) * 100) : 0;

  // Anomaly detector — heurística local: custo acima de 1.8× a média
  const avgRunCost = filteredRuns.length > 0 ? (totalCusto / filteredRuns.length) : 0;
  const anomaliesList = filteredRuns.map(r => {
    const isHigh = r.custo_total > 1.8 * avgRunCost && r.custo_total > 0.15;
    if (isHigh) {
      return {
        run: r.id,
        motivo: `Pico de consumo (${(r.custo_total / avgRunCost).toFixed(1)}x acima da média da run)`,
        custo: r.custo_total
      };
    }
    return null;
  }).filter(Boolean);

  // Map to unified item shape
  const items = (groupBy === 'run' ? filteredRuns : filteredModels).map(item => {
    return {
      key: groupBy === 'run' ? item.id : item.modelo,
      cost: item.custo_total || 0,
      tokens: item.tokens_total || 0,
      calls: item.n_chamadas || 0,
    };
  });

  // Sort items
  const sortedItems = [...items].sort((a, b) => {
    let valA, valB;
    if (sortBy === 'name') {
      valA = a.key.toLowerCase();
      valB = b.key.toLowerCase();
    } else if (sortBy === 'cost') {
      valA = a.cost;
      valB = b.cost;
    } else if (sortBy === 'tokens') {
      valA = a.tokens;
      valB = b.tokens;
    } else if (sortBy === 'calls') {
      valA = a.calls;
      valB = b.calls;
    }

    if (valA < valB) return sortDesc ? 1 : -1;
    if (valA > valB) return sortDesc ? -1 : 1;
    return 0;
  });

  // Top 10 items for the two side-by-side distribution charts
  const topByCost = [...items].sort((a, b) => b.cost - a.cost).slice(0, 10);
  const maxCost = Math.max(...topByCost.map(i => i.cost), 0.0001);

  const topByTokens = [...items].sort((a, b) => b.tokens - a.tokens).slice(0, 10);
  const maxTokens = Math.max(...topByTokens.map(i => i.tokens), 1);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortDesc(!sortDesc);
    } else {
      setSortBy(field);
      setSortDesc(true);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Title & Period Switcher */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <div className="title" style={{ fontSize: '22px' }}>Custos</div>
          <div className="mono" style={{ fontSize: '11px', color: 'var(--text3)', marginTop: '3px' }}>
            detalhamento de consumo · projeto → provedor → modelo → run
          </div>
          {gates.length > 0 && (
            <div className="mono" style={{ fontSize: '11px', color: 'var(--accent)', marginTop: '6px', cursor: 'pointer' }} onClick={() => { window.location.hash = '/caixa'; }}>
              {gates.length} gate{gates.length !== 1 ? 's' : ''} pendente{gates.length !== 1 ? 's' : ''} → Ir para a Caixa do Fundador
            </div>
          )}
        </div>
        <span className="mono" style={{ fontSize: '10px', color: 'var(--text3)' }}>sessão · log completo</span>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
        <div className="kpi">
          <div className="eyebrow">Total · sessão</div>
          <div className="kbig">US$ {totalCusto.toFixed(2)}</div>
          <div className="mono" style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>
            {totalTokens.toLocaleString()} tokens
          </div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Projeção do mês</div>
          <div className="kbig" style={{ color: 'var(--text3)' }}>—</div>
          <div className="mono" style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>
            requer histórico com timestamp
          </div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Maior fonte</div>
          <div className="kbig" style={{ fontSize: '16px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={topModel.modelo}>
            {topModel.modelo || '—'}
          </div>
          <div className="mono" style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>
            {topModelPct}% do gasto total
          </div>
        </div>
        <div className="kpi" style={{ borderColor: anomaliesList.length > 0 ? 'var(--red)' : 'var(--border)' }}>
          <div className="eyebrow" style={{ color: anomaliesList.length > 0 ? 'var(--red)' : 'var(--text3)' }}>Anomalias</div>
          <div className="kbig" style={{ color: anomaliesList.length > 0 ? 'var(--red)' : 'var(--text)' }}>
            {anomaliesList.length}
          </div>
          <div className="mono" style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '2px' }}>
            heurística local · custo acima de 1.8× a média
          </div>
        </div>
      </div>

      {/* Side-by-side Top Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        {/* Cost Distribution Chart */}
        <div className="card" style={{ padding: '16px' }}>
          <div className="eyebrow" style={{ marginBottom: '12px' }}>
            Custo por {groupBy === 'run' ? 'Run' : 'Modelo'} (Top 10)
          </div>
          <div className="cbars" style={{ height: '96px' }}>
            {topByCost.map((item, idx) => {
              const pct = (item.cost / maxCost) * 100;
              return (
                <div
                  key={item.key}
                  className="cb"
                  onMouseEnter={() => setHoveredCostIndex(idx)}
                  onMouseLeave={() => setHoveredCostIndex(null)}
                  style={{ height: '100%' }}
                >
                  <div className="cbf" style={{ height: `${pct}%`, background: 'var(--accent)', opacity: 0.7 }} />
                </div>
              );
            })}
          </div>
          <div style={{ height: '14px', marginTop: '8px', textAlign: 'center' }} className="mono">
            {hoveredCostIndex !== null && topByCost[hoveredCostIndex] ? (
              <span style={{ fontSize: '10px', color: 'var(--text2)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {topByCost[hoveredCostIndex].key} · US$ {topByCost[hoveredCostIndex].cost.toFixed(4)}
              </span>
            ) : (
              <span style={{ fontSize: '9px', color: 'var(--text3)' }}>Distribuição de dólares</span>
            )}
          </div>
        </div>

        {/* Tokens Distribution Chart */}
        <div className="card" style={{ padding: '16px' }}>
          <div className="eyebrow" style={{ marginBottom: '12px' }}>
            Tokens por {groupBy === 'run' ? 'Run' : 'Modelo'} (Top 10)
          </div>
          <div className="cbars" style={{ height: '96px' }}>
            {topByTokens.map((item, idx) => {
              const pct = (item.tokens / maxTokens) * 100;
              return (
                <div
                  key={item.key}
                  className="cb"
                  onMouseEnter={() => setHoveredTokenIndex(idx)}
                  onMouseLeave={() => setHoveredTokenIndex(null)}
                  style={{ height: '100%' }}
                >
                  <div className="cbf" style={{ height: `${pct}%`, background: 'var(--blue)', opacity: 0.7 }} />
                </div>
              );
            })}
          </div>
          <div style={{ height: '14px', marginTop: '8px', textAlign: 'center' }} className="mono">
            {hoveredTokenIndex !== null && topByTokens[hoveredTokenIndex] ? (
              <span style={{ fontSize: '10px', color: 'var(--text2)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {topByTokens[hoveredTokenIndex].key} · {topByTokens[hoveredTokenIndex].tokens.toLocaleString()} tokens
              </span>
            ) : (
              <span style={{ fontSize: '9px', color: 'var(--text3)' }}>Distribuição de tokens</span>
            )}
          </div>
        </div>
      </div>

      {/* Main Sortable Table */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span className="num">01 — Detalhamento por {groupBy === 'run' ? 'run' : 'modelo de IA'}</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span
              className={`pill ${groupBy === 'run' ? 'on' : ''}`}
              onClick={() => { setGroupBy('run'); setSortBy('cost'); }}
            >
              agrupar por run
            </span>
            <span
              className={`pill ${groupBy === 'modelo' ? 'on' : ''}`}
              onClick={() => { setGroupBy('modelo'); setSortBy('cost'); }}
            >
              agrupar por modelo
            </span>
          </div>
        </div>

        <div className="card">
          {/* Header Row */}
          <div
            className="drow"
            style={{
              color: 'var(--text3)',
              textTransform: 'uppercase',
              letterSpacing: '.5px',
              fontSize: '9px',
              fontWeight: 600,
              borderBottom: '1px solid var(--border)'
            }}
          >
            <span
              style={{
                flex: 1.5,
                cursor: 'pointer',
                userSelect: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                color: sortBy === 'name' ? 'var(--text)' : 'var(--text3)'
              }}
              onClick={() => handleSort('name')}
            >
              {groupBy === 'run' ? 'Identificador da Run' : 'Modelo de IA'} {sortBy === 'name' ? (sortDesc ? '▼' : '▲') : ''}
            </span>
            <span style={{ flex: 1 }}>Participação</span>
            <span
              style={{
                width: '100px',
                textAlign: 'right',
                cursor: 'pointer',
                userSelect: 'none',
                color: sortBy === 'cost' ? 'var(--accent)' : 'var(--text3)'
              }}
              onClick={() => handleSort('cost')}
            >
              Custo {sortBy === 'cost' ? (sortDesc ? '▼' : '▲') : ''}
            </span>
            <span
              style={{
                width: '100px',
                textAlign: 'right',
                cursor: 'pointer',
                userSelect: 'none',
                color: sortBy === 'tokens' ? 'var(--blue)' : 'var(--text3)'
              }}
              onClick={() => handleSort('tokens')}
            >
              Tokens {sortBy === 'tokens' ? (sortDesc ? '▼' : '▲') : ''}
            </span>
            <span
              style={{
                width: '80px',
                textAlign: 'right',
                cursor: 'pointer',
                userSelect: 'none',
                color: sortBy === 'calls' ? 'var(--text)' : 'var(--text3)'
              }}
              onClick={() => handleSort('calls')}
            >
              Chamadas {sortBy === 'calls' ? (sortDesc ? '▼' : '▲') : ''}
            </span>
          </div>

          {/* Table Data Rows */}
          {sortedItems.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center' }} className="mono">
              Nenhum dado disponível.
            </div>
          ) : (
            sortedItems.map((item, idx) => {
              const maxVal = sortBy === 'tokens' ? maxTokens : maxCost;
              const currentVal = sortBy === 'tokens' ? item.tokens : item.cost;
              const pct = maxVal > 0 ? Math.round((currentVal / maxVal) * 100) : 0;
              const isAnom = anomaliesList.some(anom => anom.run === item.key);

              return (
                <div key={item.key} className="drow">
                  <span
                    className="mono"
                    style={{
                      flex: 1.5,
                      color: 'var(--text)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      minWidth: 0,
                      overflow: 'hidden'
                    }}
                  >
                    {isAnom && <span className="sh red" title="Comportamento atípico detectado nesta run" />}
                    {groupBy === 'run' ? (
                      <a
                        href={`#/runs/${item.key}`}
                        style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', color: 'var(--text)', textDecoration: 'none' }}
                        title={item.key}
                      >
                        {item.key}
                      </a>
                    ) : (
                      <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={item.key}>
                        {item.key}
                      </span>
                    )}
                  </span>
                  <span style={{ flex: 1 }}>
                    <span className="bar" style={{ width: '100%', display: 'block' }}>
                      <span
                        className="barf"
                        style={{
                          width: `${pct}%`,
                          background: sortBy === 'tokens' ? 'var(--blue)' : 'var(--accent)'
                        }}
                      />
                    </span>
                  </span>
                  <span className="mono" style={{ width: '100px', textAlign: 'right', color: 'var(--text)' }}>
                    US$ {item.cost.toFixed(4)}
                  </span>
                  <span className="mono" style={{ width: '100px', textAlign: 'right', color: 'var(--text2)' }}>
                    {item.tokens.toLocaleString()}
                  </span>
                  <span className="mono" style={{ width: '80px', textAlign: 'right', color: 'var(--text3)' }}>
                    {item.calls}
                  </span>
                </div>
              );
            })
          )}
        </div>
        <div className="mono" style={{ fontSize: '10px', color: 'var(--text3)', marginTop: '8px' }}>
          Clique nos títulos das colunas (Identificador/Modelo, Custo, Tokens ou Chamadas) para ordenar a visualização.
        </div>
      </div>

      {/* Anomalies Highlight Section */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span className="num">02 — Anomalias destacadas</span>
          <span className="mono" style={{ fontSize: '10px', color: 'var(--text3)' }}>heurística local · custo acima de 1.8× a média</span>
        </div>
        <div className="card" style={{ padding: '4px 15px' }}>
          {anomaliesList.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px 0', color: 'var(--text3)' }} className="mono">
              Nenhuma anomalia de consumo detectada na sessão.
            </div>
          ) : (
            anomaliesList.map((a, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '11px 0',
                  borderBottom: i < anomaliesList.length - 1 ? '1px solid var(--border)' : 'none',
                  fontFamily: 'IBM Plex Mono, monospace',
                  fontSize: '11.5px'
                }}
              >
                <span className="sh red"></span>
                <span style={{ color: 'var(--text)', width: '150px', flex: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.run}>
                  {a.run}
                </span>
                <span style={{ color: 'var(--text2)', flex: 1 }}>{a.motivo}</span>
                <span style={{ color: 'var(--red)', flex: 'none' }}>US$ {a.custo.toFixed(4)}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
