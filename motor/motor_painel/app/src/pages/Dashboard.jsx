import { usePoll, fetchRuns, getCosts, getGates, fetchDados } from '../api.js';
import { formatarCusto } from '../formatarCusto.js';

export default function Dashboard() {
  const { data: runs, error: errorRuns } = usePoll(fetchRuns);
  const { data: costs, error: errorCosts } = usePoll(getCosts);
  const { data: gates, error: errorGates } = usePoll(getGates);
  const { data: fullData, error: errorFullData } = usePoll(fetchDados);

  const isLoading = !runs || !costs || !fullData;
  const error = errorRuns || errorCosts || errorGates || errorFullData;

  if (error) {
    return (
      <div>
        <span className="num">Dashboard</span>
        <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
          <span className="mono" style={{ color: 'var(--red)' }}>Erro ao carregar os dados: {error}</span>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        <span className="num">Dashboard</span>
        <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text3)' }}>Carregando dados...</span>
        </div>
      </div>
    );
  }

  // --- Calculations ---

  // 1. Runs (Ativos / Concluídos / Total)
  const totalRuns = runs.length;
  const activeRuns = runs.filter(r => r.estado === 'ativa').length;
  const completedRuns = runs.filter(r => r.estado === 'concluida').length;
  const totalProjects = new Set(runs.map(r => r.objetivo || r.id)).size;

  // 2. Costs (Hoje, Mês, Projeção)
  const maxStart = runs.length > 0 ? Math.max(...runs.map(r => r.inicio || 0)) : 0;
  const isMockTime = maxStart < 1000000000;

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startOfTodayTs = startOfToday.getTime() / 1000;

  const startOfMonth = new Date();
  startOfMonth.setDate(1);
  startOfMonth.setHours(0, 0, 0, 0);
  const startOfMonthTs = startOfMonth.getTime() / 1000;

  const runsToday = isMockTime ? runs : runs.filter(r => r.inicio >= startOfTodayTs);
  const costToday = runsToday.reduce((acc, r) => acc + (r.custo || 0), 0);

  const runsMonth = isMockTime ? runs : runs.filter(r => r.inicio >= startOfMonthTs);
  const costThisMonth = runsMonth.reduce((acc, r) => acc + (r.custo || 0), 0);

  const todayDate = new Date();
  const currentDay = todayDate.getDate();
  const daysInMonth = new Date(todayDate.getFullYear(), todayDate.getMonth() + 1, 0).getDate();
  const costProjected = currentDay > 0 ? (costThisMonth / currentDay) * daysInMonth : costThisMonth;

  // 3. 1ª tentativa (Approval Rate)
  const eventos = fullData.eventos || [];
  const runEventsMap = {};
  eventos.forEach(ev => {
    const rid = ev.run_id || 'legado:sem-proveniencia';
    if (rid) {
      if (!runEventsMap[rid]) runEventsMap[rid] = [];
      runEventsMap[rid].push(ev);
    }
  });

  let totalRunsWithGates = 0;
  let firstAttemptApprovedRuns = 0;

  Object.entries(runEventsMap).forEach(([rid, evs]) => {
    const hasGates = evs.some(ev => ev.evento === 'portao.aprovado' || ev.evento === 'portao.reprovado');
    if (hasGates) {
      totalRunsWithGates++;
      const hasReprovado = evs.some(ev => ev.evento === 'portao.reprovado');
      if (!hasReprovado) {
        firstAttemptApprovedRuns++;
      }
    }
  });

  const firstAttemptPct = totalRunsWithGates > 0 ? Math.round((firstAttemptApprovedRuns / totalRunsWithGates) * 100) : null;

  // 4. Latency
  const latencies = [];
  const chamadosMap = {};

  eventos.forEach(ev => {
    const rid = ev.run_id || 'legado:sem-proveniencia';
    if (!rid) return;
    const exec = ev.executor;
    if (!exec) return;
    const tent = ev.tentativa || 1;
    const key = `${rid}:${exec}:${tent}`;

    if (ev.evento === 'executor.chamado') {
      chamadosMap[key] = ev.t;
    } else if (ev.evento === 'executor.respondeu' || ev.evento === 'executor.erro' || ev.evento === 'modelo.falha') {
      const chamadoT = chamadosMap[key];
      if (chamadoT !== undefined && ev.t !== undefined) {
        const lat = ev.t - chamadoT;
        if (lat >= 0) {
          latencies.push(lat);
        }
      }
    }
  });

  const getMedian = (arr) => {
    if (arr.length === 0) return null;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  };

  const getP90 = (arr) => {
    if (arr.length === 0) return null;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.floor(sorted.length * 0.9);
    return sorted[idx];
  };

  const medianLatency = getMedian(latencies);
  const p90Latency = getP90(latencies);

  // 5. Escaladas & Convergência
  const escalatedRuns = new Set();
  eventos.forEach(ev => {
    if (ev.evento === 'escalado') {
      const rid = ev.run_id || 'legado:sem-proveniencia';
      if (rid) escalatedRuns.add(rid);
    }
  });
  const escalatedCount = escalatedRuns.size;
  let convergedCount = 0;
  escalatedRuns.forEach(rid => {
    const runMetadata = runs.find(r => r.id === rid);
    if (runMetadata?.estado === 'concluida') {
      convergedCount++;
    }
  });
  const convergencePct = escalatedCount > 0 ? Math.round((convergedCount / escalatedCount) * 100) : null;

  // 6. Pendências
  const pendingCount = gates ? gates.length : null;

  // 7. Saúde dos Provedores — derivada dos eventos modelo.uso / modelo.falha
  const providersMap = {};
  eventos.forEach(ev => {
    if (ev.evento === 'modelo.uso' && ev.modelo) {
      if (!providersMap[ev.modelo]) {
        providersMap[ev.modelo] = { name: ev.modelo, shape: 'sh green', status: 'ok', note: ev.executor || '' };
      }
    }
  });
  eventos.forEach(ev => {
    if (ev.evento === 'modelo.falha' && ev.modelo) {
      providersMap[ev.modelo] = {
        name: ev.modelo,
        shape: 'sh red',
        status: `falhou · ${ev.motivo || ev.erro || 'sem motivo no log'}`,
        note: ev.executor || ''
      };
    }
  });
  const providers = Object.values(providersMap);

  // 8. Digests (Recent Runs)
  const runDigests = [];
  Object.entries(runEventsMap).forEach(([rid, evs]) => {
    const runMetadata = runs.find(r => r.id === rid);
    const objective = runMetadata?.objetivo || evs.find(ev => ev.objetivo)?.objetivo || rid;

    const ts = evs.map(ev => ev.t).filter(t => t !== undefined);
    const minT = ts.length > 0 ? Math.min(...ts) : 0;
    const maxT = ts.length > 0 ? Math.max(...ts) : 0;
    const durationSec = maxT - minT;

    let durationStr = '';
    if (durationSec < 60) {
      durationStr = `${Math.round(durationSec)}s`;
    } else {
      const m = Math.floor(durationSec / 60);
      const s = Math.round(durationSec % 60);
      durationStr = `${m}m${s.toString().padStart(2, '0')}s`;
    }

    const cyclesSet = new Set();
    evs.forEach(ev => {
      if (ev.ciclo) cyclesSet.add(ev.ciclo);
      if (ev.tentativa) cyclesSet.add(ev.tentativa);
    });
    const numCycles = cyclesSet.size || 1;

    let ciclosStr = `${numCycles} ciclo${numCycles !== 1 ? 's' : ''}`;
    const isAbortada = evs.some(ev => ev.evento === 'tarefa.abortada');
    const isPendente = evs.some(ev => ev.evento === 'decisao.pendente' || ev.evento === 'escalado');
    if (isAbortada) {
      ciclosStr = 'abortado';
    } else if (isPendente) {
      ciclosStr = 'pendente';
    }

    let kind = 'idle';
    if (runMetadata?.estado === 'concluida') kind = 'green';
    else if (runMetadata?.estado === 'abortada') kind = 'red';
    else if (runMetadata?.estado === 'ativa') {
      kind = isPendente ? 'amber' : 'blue';
    }

    runDigests.push({
      id: rid,
      run: rid.length > 20 ? `RUN-…-${rid.slice(-5)} · ${objective}` : `${rid} · ${objective}`,
      shape: `sh ${kind}`,
      custo: formatarCusto(runMetadata?.custo),
      dur: durationStr,
      ciclos: ciclosStr,
      inicio: minT
    });
  });

  runDigests.sort((a, b) => b.inicio - a.inicio);
  const digests = runDigests.slice(0, 4);

  // 9. Custo por run (dados reais de getCosts.por_run)
  const porRun = costs.por_run || [];
  const maxRunCost = Math.max(...porRun.map(r => r.custo_total || 0), 0.0001);

  return (
    <>
      {/* HEADER */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <div className="title" style={{ fontSize: 22 }}>Visão geral</div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', marginTop: 3 }}>
            {totalProjects} projeto{totalProjects !== 1 ? 's' : ''} · {totalRuns} run{totalRuns !== 1 ? 's' : ''} ({activeRuns} ativa{activeRuns !== 1 ? 's' : ''})
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="pill" onClick={() => window.location.hash = '/grafo'}>Grafo 2D →</span>
          <span className="pill" onClick={() => window.location.hash = '/grafo3d'}>Grafo 3D →</span>
          <span className="pill" onClick={() => window.location.hash = '/datahouse'}>Datahouse →</span>
        </div>
      </div>

      {/* KPIs */}
      <div>
        <div className="num" style={{ marginBottom: 10 }}>01 — Indicadores</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
          <div className="kpi">
            <div className="eyebrow">Runs</div>
            <div className="kbig">
              {activeRuns}
              <span style={{ fontSize: 13, color: 'var(--text3)' }}> / {completedRuns || totalRuns}</span>
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>ativos / concluídos</div>
          </div>
          <div className="kpi">
            <div className="eyebrow">{isMockTime ? 'Custo · sessão' : 'Custo hoje'}</div>
            <div className="kbig">US$ {costToday.toFixed(2)}</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
              {isMockTime ? 'sem base temporal no log' : `mês ${costThisMonth.toFixed(2)} · proj. ${costProjected.toFixed(2)}`}
            </div>
          </div>
          <div className="kpi">
            <div className="eyebrow">1ª tentativa</div>
            <div className="kbig" style={{ color: firstAttemptPct !== null ? 'var(--green)' : 'var(--text3)' }}>
              {firstAttemptPct !== null ? `${firstAttemptPct}%` : '—'}
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
              {firstAttemptPct !== null ? 'aprovação inicial' : 'sem gates no log'}
            </div>
          </div>
          <div className="kpi">
            <div className="eyebrow">Latência</div>
            <div className="kbig" style={{ color: medianLatency !== null ? 'var(--text)' : 'var(--text3)' }}>
              {medianLatency !== null ? `${medianLatency.toFixed(1)}s` : '—'}
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
              mediana · p90 {p90Latency !== null ? `${p90Latency.toFixed(1)}s` : '—'}
            </div>
          </div>
          <div className="kpi">
            <div className="eyebrow">Escaladas</div>
            <div className="kbig">{escalatedCount}</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
              convergência {convergencePct !== null ? `${convergencePct}%` : '—'}
            </div>
          </div>
          <div className="kpi" style={{ borderColor: 'var(--accent)' }}>
            <div className="eyebrow" style={{ color: 'var(--accent)' }}>Pendências</div>
            <div className="kbig" style={{ color: pendingCount !== null ? 'var(--amber)' : 'var(--text3)' }}>
              {pendingCount !== null ? pendingCount : '—'}
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>aguardando você</div>
          </div>
        </div>
      </div>

      {/* TRENDS */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 20 }}>
        {/* Custo Trend */}
        <div style={{ minWidth: 0, overflow: 'hidden' }}>
          <div className="num" style={{ marginBottom: 10 }}>02 — Custo · por run</div>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 120 }}>
              {porRun.length === 0 ? (
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>— sem runs no histórico</span>
              ) : (
                porRun.map((r, i) => {
                  const hPct = maxRunCost > 0 ? (Math.max(r.custo_total, 0.0001) / maxRunCost) * 100 : 0;
                  return (
                    <div key={i} className="bar" style={{ flex: 1, minWidth: 2, height: '100%', background: 'transparent', position: 'relative' }}>
                      <div className="barf" style={{ height: `${hPct}%`, bottom: 0, top: 'auto', background: 'var(--accent)', opacity: 0.8, width: '100%' }}></div>
                    </div>
                  );
                })
              )}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>anteriores</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>
                {isMockTime
                  ? <>total <b style={{ color: 'var(--text)' }}>US$ {costThisMonth.toFixed(2)}</b></>
                  : <>projeção mês <b style={{ color: 'var(--text)' }}>US$ {costProjected.toFixed(2)}</b></>}
              </span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>recentes</span>
            </div>
          </div>
        </div>
      </div>

      {/* HEALTH & DIGESTS */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Saúde dos Provedores */}
        <div style={{ minWidth: 0 }}>
          <div className="num" style={{ marginBottom: 10 }}>03 — Saúde dos provedores</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {providers.map((p, idx) => (
              <div key={idx} className="trow">
                <span className={p.shape}></span>
                <span style={{ color: 'var(--text)', width: 120, flex: 'none' }}>{p.name}</span>
                <span style={{ color: 'var(--text2)', flex: 1 }}>{p.status}</span>
                <span style={{ color: 'var(--text3)' }}>{p.note}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Últimos Digests */}
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
            <span className="num">04 — Últimos digests</span>
            <span className="lnk" onClick={() => window.location.hash = '/runs'}>Runs &amp; Histórico →</span>
          </div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {digests.map((d, idx) => (
              <div
                key={idx}
                className="trow"
                style={{ cursor: d.id ? 'pointer' : 'default' }}
                onClick={() => d.id && (window.location.hash = `/runs/${d.id}`)}
              >
                <span className={d.shape}></span>
                <span style={{ color: 'var(--text)', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {d.run}
                </span>
                <span style={{ color: 'var(--text3)', width: 64, flex: 'none', textAlign: 'right' }}>{d.custo}</span>
                <span style={{ color: 'var(--text3)', width: 54, flex: 'none', textAlign: 'right' }}>{d.dur}</span>
                <span style={{ color: 'var(--text3)', width: 60, flex: 'none', textAlign: 'right' }}>{d.ciclos}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
