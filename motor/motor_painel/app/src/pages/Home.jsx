import { usePoll, getCosts, getGates, fetchRuns, postGateDecision, getAgents } from '../api.js';
import { useState } from 'react';
import { formatarCusto } from '../formatarCusto.js';

const STYLE_TAG = `
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .kpi { padding: 14px 15px; background: var(--surface); border: 1px solid var(--border); border-radius: 2px; }
  .hero { position: relative; }
  .bk { position: absolute; width: 11px; height: 11px; border: 1.5px solid var(--focus); opacity: .7; pointer-events: none; }
  .bk.tl { top: -1px; left: -1px; border-right: 0; border-bottom: 0; }
  .bk.tr { top: -1px; right: -1px; border-left: 0; border-bottom: 0; }
  .bk.bl { bottom: -1px; left: -1px; border-right: 0; border-top: 0; }
  .bk.br { bottom: -1px; right: -1px; border-left: 0; border-top: 0; }
  .theatre { background: var(--bg); border: 1px solid var(--border); border-radius: 2px; position: relative; overflow: hidden; }
  .flow { stroke: var(--blue); stroke-width: 1.4; fill: none; stroke-dasharray: 3 6; animation: mfflow 1.5s linear infinite; }
  @keyframes mfflow { to { stroke-dashoffset: -18; } }
  .npulse { transform-origin: center; transform-box: fill-box; animation: mfnode 2.3s ease-in-out infinite; }
  @keyframes mfnode { 0%, 100% { opacity: .9; } 50% { opacity: .4; } }
  .halo { transform-origin: center; transform-box: fill-box; animation: mfhalo 2.3s ease-out infinite; }
  @keyframes mfhalo { 0% { opacity: .5; transform: scale(.6); } 100% { opacity: 0; transform: scale(2.4); } }
  .avatar { width: 52px; height: 52px; border-radius: 50%; background: var(--surface2); border: 2px solid var(--border); display: flex; align-items: center; justify-content: center; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--text2); flex: none; }
  .avatar.ring-blue { border-color: var(--blue); }
  .avatar.ring-amber { border-color: var(--amber); }
  .avatar.ring-green { border-color: var(--green); }
  .avatar.ring-red { border-color: var(--red); }
  .lnk { font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: .6px; text-transform: uppercase; color: var(--text2); cursor: pointer; text-decoration: none; }
  .lnk:hover { color: var(--text); }
  .toast { position: fixed; right: 26px; bottom: 26px; z-index: 40; max-width: 360px; background: var(--surface); border: 1px solid var(--red); border-left: 3px solid var(--red); border-radius: 2px; padding: 12px 14px; box-shadow: var(--card-shadow, 0 8px 30px rgba(0,0,0,.4)); }
`;

export default function Home() {
  const { data: costsData } = usePoll(getCosts);
  const { data: gatesData } = usePoll(getGates);
  const { data: runsData } = usePoll(fetchRuns);
  const { data: agentsData } = usePoll(getAgents);
  
  const [toastMessage, setToastMessage] = useState(null);

  // Decision Handler
  const handleDecision = async (portaoId, decisao) => {
    try {
      await postGateDecision(portaoId, decisao);
      setToastMessage({ type: 'success', text: `Decisão '${decisao}' enviada com sucesso para o portão ${portaoId}.` });
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err) {
      console.error(err);
      setToastMessage({ type: 'error', text: `Erro ao enviar decisão: ${err.message}` });
      setTimeout(() => setToastMessage(null), 4000);
    }
  };

  const loading = !costsData && !runsData;
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <span className="num">Fábrica</span>
        <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
          <div className="title" style={{ fontSize: 17, color: 'var(--text2)' }}>
            Carregando painel...
          </div>
          <div className="mono" style={{ fontSize: 12, color: 'var(--text3)', marginTop: 8 }}>
            Sincronizando estado da Meta-fábrica · aguarde
          </div>
        </div>
      </div>
    );
  }

  const runs = runsData || [];
  const gates = gatesData || [];
  const isEmpty = runs.length === 0;

  // Costs calculation
  const totalCusto = costsData?.total?.custo_total ?? 0.0;
  const totalTokens = costsData?.total?.tokens_total ?? 0;
  const nChamadas = costsData?.total?.n_chamadas ?? 0;

  const hoje = `US$ ${totalCusto.toFixed(2)}`;
  const hojeD = `${nChamadas} chamadas (${(totalTokens / 1000).toFixed(1)}k tokens)`;
  const prov = costsData?.por_modelo?.map(m => m.modelo.split('/').pop()).join(' · ') || '—';

  // AO VIVO or OCIOSO status
  const temAtivas = runs.some(r => r.estado === 'ativa');
  const liveLabel = temAtivas ? 'AO VIVO' : 'OCIOSO';
  const liveShape = temAtivas ? 'sh blue' : 'sh idle';

  // Dynamic process feed
  const feed = [];
  if (gates.length > 0) {
    gates.forEach(g => {
      feed.push({
        txt: `escalado → fundador · gate ${g.portao}`,
        hasBtn: true,
        btn: 'Decidir',
        onClick: () => window.location.hash = '/caixa'
      });
    });
  }
  runs.slice(0, 3).forEach(r => {
    if (r.estado === 'ativa') {
      feed.push({
        txt: `missão ativa · ${r.id}`,
        hasBtn: true,
        btn: 'Ver',
        onClick: () => window.location.hash = `/runs/${r.id}`
      });
    } else if (r.estado === 'concluida') {
      feed.push({
        txt: `tarefa concluída · ${r.id}`,
        hasBtn: false
      });
    }
  });
  /* Feed curto fica curto. Encher com linha generica ("conector inicializado")
     e inventar evento que nunca aconteceu. */

  const getAgentAvatarClass = (agent) => {
    if (agent.falhas > 0) return 'avatar ring-red';
    if (agent.chamadas > 0) return 'avatar ring-blue';
    return 'avatar ring-green';
  };

  const getAgentLabel = (id) => {
    if (id.includes('alfa')) return 'αlf';
    if (id.includes('beta')) return 'βet';
    if (id.includes('planner')) return 'pln';
    if (id.includes('qa')) return 'qae';
    if (id.includes('synth')) return 'syn';
    if (id.includes('arq')) return 'arq';
    return id.slice(0, 3);
  };

  const hasRealAgents = agentsData && agentsData.length > 0;
  const activeAgents = hasRealAgents ? agentsData.map(a => ({
    mono: getAgentLabel(a.id),
    role: a.papel || 'agente',
    now: a.falhas > 0 ? 'falhou' : a.chamadas > 0 ? 'ativo' : 'ocioso',
    avatarClass: getAgentAvatarClass(a)
  })) : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 26 }}>
      <style dangerouslySetInnerHTML={{ __html: STYLE_TAG }} />

      {!isEmpty ? (
        <>
          {/* 01 CUSTOS */}
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
              <span className="num">01 — Custos</span>
              <span className="lnk" onClick={() => window.location.hash = '/custos'}>abrir custos →</span>
            </div>
            <div className="kpis">
              <div className="kpi">
                <div className="eyebrow">Hoje</div>
                <div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 6 }}>{hoje}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>{hojeD}</div>
              </div>
              <div className="kpi">
                <div className="eyebrow">Mês</div>
                <div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 6, color: 'var(--text3)' }}>—</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>requer histórico com timestamp</div>
              </div>
              <div className="kpi">
                <div className="eyebrow">Por provedor</div>
                <div className="mono" style={{ fontSize: 13, marginTop: 10, color: 'var(--text2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{prov}</div>
              </div>
              <div className="kpi">
                <div className="eyebrow">Projeção do mês</div>
                <div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 6, color: 'var(--text3)' }}>—</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>requer histórico com timestamp</div>
              </div>
            </div>
          </div>

          {/* 02 FILA DE DECISÃO */}
          {gates.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
                <span className="num" style={{ color: 'var(--accent)' }}>02 — Fila de decisão · {gates.length}</span>
                <span className="lnk" onClick={() => window.location.hash = '/caixa'}>ver todas na Caixa do Fundador →</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {gates.map((g) => (
                  <div key={g.portao} className="card" style={{ borderLeft: '2px solid var(--accent)', padding: '14px 15px', display: 'flex', flexDirection: 'column', gap: 9 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                      <span className="sh amber"></span>
                      <span className="eyebrow" style={{ color: 'var(--accent)' }}>Gate Humano</span>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>{g.run} · {g.portao}</span>
                    </div>
                    <div className="title" style={{ fontSize: 14.5 }}>{g.pergunta}</div>
                    <div className="mono" style={{ fontSize: 11.5, color: 'var(--text2)' }}>portão — {g.portao}</div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                      {g.opcoes.map((opt, optIdx) => (
                        <button
                          key={opt}
                          className={optIdx === 0 ? "btn btn-primary btn-sm" : "btn btn-sm"}
                          onClick={() => handleDecision(g.portao, opt)}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 03 MAPA GERAL VIVO */}
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
              <span className="num">03 — Mapa geral vivo</span>
              <span className="lnk" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={() => window.location.hash = '/grafo'}>
                <span className={liveShape}></span>{liveLabel} · expandir →
              </span>
            </div>
            <div className="theatre hero" style={{ height: 230 }}>
              <span className="bk tl" style={{ borderColor: 'var(--border)' }}></span>
              <span className="bk tr" style={{ borderColor: 'var(--border)' }}></span>
              <span className="bk bl" style={{ borderColor: 'var(--border)' }}></span>
              <span className="bk br" style={{ borderColor: 'var(--border)' }}></span>
              <div style={{ position: 'absolute', left: 14, top: 12 }} className="eyebrow">Teatro de operações · escopo Todos</div>
              <svg viewBox="0 0 900 230" preserveAspectRatio="xMidYMid slice" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
                <g strokeLinecap="round">
                  <path d="M150,120 C260,120 260,70 380,70" stroke="var(--border)" strokeWidth="1.2" fill="none" />
                  <path d="M150,120 C260,120 260,170 380,170" stroke="var(--border)" strokeWidth="1.2" fill="none" />
                  <path className="flow" d="M380,70 C500,70 500,120 620,120" />
                  <path d="M380,170 C500,170 500,120 620,120" stroke="var(--border)" strokeWidth="1.2" fill="none" />
                  <path className="flow" d="M620,120 C720,120 720,90 800,90" />
                  <path d="M620,120 C720,120 720,160 800,160" stroke="var(--border)" strokeWidth="1.2" fill="none" />
                  <path d="M150,120 C90,120 90,60 60,50" stroke="var(--border)" strokeWidth="1" fill="none" />
                </g>
                <circle className="halo" cx="380" cy="70" r="9" fill="var(--blue)" />
                <circle className="npulse" cx="380" cy="70" r="6" fill="var(--blue)" />
                <circle cx="150" cy="120" r="7" fill="var(--text2)" />
                <circle cx="380" cy="170" r="6" fill="var(--green)" />
                <circle className="npulse" cx="620" cy="120" r="6" fill="var(--blue)" />
                <circle cx="800" cy="90" r="5" fill="var(--text2)" />
                <circle cx="800" cy="160" r="5" fill="var(--amber)" />
                <circle cx="60" cy="50" r="4" fill="var(--text3)" />
                <text x="150" y="145" fill="var(--text3)" fontFamily="IBM Plex Mono" fontSize="10">planner</text>
                <text x="360" y="55" fill="var(--text2)" fontFamily="IBM Plex Mono" fontSize="10">pesquisa-alfa</text>
                <text x="360" y="192" fill="var(--text2)" fontFamily="IBM Plex Mono" fontSize="10">pesquisa-beta</text>
                <text x="600" y="145" fill="var(--text2)" fontFamily="IBM Plex Mono" fontSize="10">global_evaluator</text>
              </svg>
            </div>
          </div>

          {/* 04 RUNS & MISSÕES */}
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
              <span className="num">04 — Runs &amp; Missões</span>
              <span className="lnk" onClick={() => window.location.hash = '/runs'}>abrir runs →</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
              {runs.map((run) => {
                let shapeClass = 'sh idle';
                if (run.estado === 'ativa') shapeClass = 'sh blue';
                else if (run.estado === 'concluida') shapeClass = 'sh green';
                else if (run.estado === 'abortada') shapeClass = 'sh red';

                return (
                  <div
                    key={run.id}
                    className="card hov"
                    onClick={() => window.location.hash = `/runs/${run.id}`}
                    style={{ padding: 14, position: 'relative', overflow: 'hidden', minHeight: 120, display: 'flex', flexDirection: 'column' }}
                  >
                    <svg viewBox="0 0 200 120" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.09, pointerEvents: 'none' }}>
                      <path d="M20,90 C70,90 70,30 130,30 C170,30 170,80 190,60" stroke="currentColor" strokeWidth="1.5" fill="none" />
                      <circle cx="20" cy="90" r="4" fill="currentColor" />
                      <circle cx="130" cy="30" r="4" fill="currentColor" />
                      <circle cx="190" cy="60" r="3" fill="currentColor" />
                    </svg>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <div className="title" style={{ fontSize: 14 }}>{run.id}</div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', marginTop: 5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {run.objetivo || 'Sem objetivo definido'}
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                        Estado: {run.estado}
                      </div>
                    </div>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8, paddingTop: 10, marginTop: 8, borderTop: '1px solid var(--border)' }}>
                      <span className={shapeClass}></span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {run.n_eventos} eventos · {formatarCusto(run.custo, '—')}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 05 ORQUESTRADOR */}
          <div>
            <div style={{ marginBottom: 10 }}><span className="num">05 — Orquestrador</span></div>
            <div className="card hero" style={{ display: 'grid', gridTemplateColumns: '1.1fr 1.3fr 0.8fr', gap: 0, minHeight: 200, overflow: 'hidden' }}>
              <span className="bk tl"></span><span className="bk tr"></span><span className="bk bl"></span><span className="bk br"></span>
              {/* chat */}
              <div style={{ padding: 16, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
                <div className="eyebrow">Resumo · status ao vivo</div>
                <div style={{ flex: 1, margin: '12px 0', display: 'flex', flexDirection: 'column', gap: 8, justifyContent: 'flex-end' }}>
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--text)', alignSelf: 'flex-end', maxWidth: '92%', lineHeight: 1.5 }}>
                    {runs.length} missão{runs.length !== 1 ? 's' : ''} registrada{runs.length !== 1 ? 's' : ''} ({runs.filter(r => r.estado === 'ativa').length} ativa{runs.filter(r => r.estado === 'ativa').length !== 1 ? 's' : ''}). {gates.length > 0 ? `${gates.length} aguarda você na Caixa do Fundador.` : 'Nenhuma pendência activa.'} Custo total {hoje}.
                  </div>
                </div>
              </div>
              {/* feed */}
              <div style={{ padding: 16, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
                <div className="eyebrow">Feed de processos · tempo real</div>
                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column' }}>
                  {feed.slice(0, 4).map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
                      <span className="mono" style={{ fontSize: 11.5, color: 'var(--text2)', flex: 1 }}>{f.txt}</span>
                      {f.hasBtn && (
                        <button className="btn btn-sm" style={{ padding: '3px 9px', fontSize: 10.5 }} onClick={f.onClick}>
                          {f.btn}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              {/* avatar */}
              <div style={{ padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', background: 'var(--surface2)' }}>
                <div className="eyebrow" style={{ alignSelf: 'flex-start' }}>Presença</div>
                <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end' }}>
                  <div style={{ width: 96, height: 130, background: 'linear-gradient(180deg, var(--surface) 0%, var(--surface2) 100%)', border: '1px solid var(--border)', borderRadius: '48px 48px 4px 4px', position: 'relative', display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
                    <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--bg)', border: '1.5px solid var(--focus)', marginTop: 16, position: 'relative' }}>
                      <div style={{ position: 'absolute', left: 12, right: 12, top: 19, height: 3, background: 'var(--accent)', borderRadius: 2, boxShadow: '0 0 8px var(--accent)' }}></div>
                    </div>
                  </div>
                </div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 8 }}>avatar · slot P1</div>
              </div>
            </div>
          </div>

          {/* 06 AGENTES */}
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
              <span className="num" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                06 — Agentes
              </span>
              <span className="lnk" onClick={() => window.location.hash = '/agentes'}>ver todos →</span>
            </div>
            <div style={{ display: 'flex', gap: 22, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              {!hasRealAgents && (
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>
                  Nenhum executor chamado ainda nesta run.
                </span>
              )}
              {activeAgents.map((a, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, width: 78 }} title={a.now}>
                  <div className={a.avatarClass}>{a.mono}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--text2)', textAlign: 'center', lineHeight: 1.3 }}>{a.role}</div>
                  <div className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>{a.now}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        /* ============ EMPTY STATE ============ */
        <>
          <div>
            <div style={{ marginBottom: 10 }}><span className="num">01 — Custos</span></div>
            <div className="kpis">
              <div className="kpi"><div className="eyebrow">Hoje</div><div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 6, color: 'var(--text3)' }}>US$ 0.00</div></div>
              <div className="kpi"><div className="eyebrow">Mês</div><div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 6, color: 'var(--text3)' }}>US$ 0.00</div></div>
              <div className="kpi"><div className="eyebrow">Por provedor</div><div className="mono" style={{ fontSize: 13, marginTop: 10, color: 'var(--text3)' }}>—</div></div>
              <div className="kpi"><div className="eyebrow">Projeção</div><div className="mono" style={{ fontSize: 20, fontWeight: 600, marginTop: 6, color: 'var(--text3)' }}>—</div></div>
            </div>
          </div>
          <div className="theatre hero" style={{ height: 280, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
            <span className="bk tl" style={{ borderColor: 'var(--border)' }}></span>
            <span className="bk tr" style={{ borderColor: 'var(--border)' }}></span>
            <span className="bk bl" style={{ borderColor: 'var(--border)' }}></span>
            <span className="bk br" style={{ borderColor: 'var(--border)' }}></span>
            <div style={{ width: 38, height: 38, border: '1.5px dashed var(--focus)', borderRadius: 2 }}></div>
            <div className="title" style={{ fontSize: 17, color: 'var(--text)' }}>Nenhuma missão ainda</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text2)', maxWidth: 380, textAlign: 'center', lineHeight: 1.6 }}>
              A fábrica está ociosa. Dispare a primeira missão e este teatro passa a pulsar com a execução ao vivo.
            </div>
          </div>
        </>
      )}

      {/* TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="toast" style={{ borderColor: toastMessage.type === 'error' ? 'var(--red)' : 'var(--green)', borderLeft: `3px solid ${toastMessage.type === 'error' ? 'var(--red)' : 'var(--green)'}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className={`sh ${toastMessage.type === 'error' ? 'red' : 'green'}`}></span>
            <span className="eyebrow" style={{ color: toastMessage.type === 'error' ? 'var(--red)' : 'var(--green)' }}>
              {toastMessage.type === 'error' ? 'Erro' : 'Sucesso'}
            </span>
          </div>
          <div className="mono" style={{ fontSize: 12, color: 'var(--text)', marginTop: 6 }}>
            {toastMessage.text}
          </div>
        </div>
      )}
    </div>
  );
}
