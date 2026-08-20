import { useState, useEffect } from 'react';
import { usePoll, getGates, getRun, postGateDecision } from '../api.js';

function GateDetail({ gate, onDecision, submitting }) {
  const { data, error } = usePoll(() => getRun(gate.run), [gate.run]);

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <div className="card" style={{ padding: 16, borderColor: 'var(--red)' }}>
          <span className="mono" style={{ color: 'var(--red)' }}>Erro ao carregar run: {error}</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 24 }}>
        <div className="card" style={{ padding: 16 }}>
          <span className="mono" style={{ color: 'var(--text2)' }}>Carregando contexto da run...</span>
        </div>
      </div>
    );
  }

  const run = data.run || {};
  const eventos = data.eventos || [];
  const artefatos = data.artefatos || [];

  // Filtra histórico de decisões desta run
  const decisionEvents = eventos.filter(
    (e) => e.evento === 'decisao.fundador' || e.evento === 'decisao.timeout'
  );

  return (
    <div style={{ padding: '22px 24px 40px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* header */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, borderLeft: '3px solid var(--amber)', paddingLeft: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="sh amber"></span>
          <span className="eyebrow" style={{ color: 'var(--amber)' }}>
            Aguardando você · {gate.portao === 'cobertura' ? 'Gate Humano' : `Gate ${gate.portao}`}
          </span>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
            {run.id}
          </span>
        </div>
        <div className="title" style={{ fontSize: 20, lineHeight: 1.3, maxWidth: 760 }}>
          {gate.pergunta}
        </div>
      </div>

      {/* context panels */}
      <div>
        <div className="num" style={{ marginBottom: 10 }}>Contexto que embasa a decisão</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'stretch' }}>
          
          {/* Mission Objective */}
          {run.objetivo && (
            <div className="ctxpanel wide">
              <div className="eyebrow" style={{ marginBottom: 9 }}>Objetivo da Missão</div>
              <div className="mono" style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.65 }}>
                {run.objetivo}
              </div>
            </div>
          )}

          {/* Run Details */}
          <div className="ctxpanel">
            <div className="eyebrow" style={{ marginBottom: 9 }}>Métricas da Run</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>Estado</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text)', textTransform: 'uppercase' }}>{run.estado}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>Custo</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>
                  {typeof run.custo === 'number' ? `US$ ${run.custo.toFixed(2)}` : '—'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>Eventos</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>{run.n_eventos}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>Início</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>{run.inicio || '—'}</span>
              </div>
            </div>
          </div>

          {/* Artifacts */}
          <div className="ctxpanel">
            <div className="eyebrow" style={{ marginBottom: 9 }}>Artefatos Gerados</div>
            {artefatos.length > 0 ? (
              <div className="mono" style={{ fontSize: '11.5px', color: 'var(--text2)', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 2, padding: 10, lineHeight: 1.6, whiteSpace: 'pre-wrap', maxHeight: 150, overflow: 'auto' }}>
                {artefatos.map((art, idx) => (
                  <div key={idx} style={{ borderBottom: idx < artefatos.length - 1 ? '1px solid var(--border)' : 'none', paddingBottom: 4, marginTop: idx > 0 ? 4 : 0 }}>
                    {art}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mono" style={{ fontSize: '11.5px', color: 'var(--text3)' }}>
                Nenhum artefato gerado.
              </div>
            )}
          </div>

        </div>
      </div>

      {/* options */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 2, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <span className="num">Decisão · individual desta pendência</span>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
            registra <b style={{ color: 'var(--text2)' }}>decisao.fundador</b> · destrava o run na hora
          </span>
        </div>
        <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
          {(gate.opcoes || []).map((opt, idx) => {
            const isPrimary = idx === 0 || opt === 'prosseguir' || opt === 'aprovar';
            return (
              <button
                key={opt}
                disabled={submitting}
                className={isPrimary ? 'btn btn-amber' : 'btn'}
                onClick={() => onDecision(gate, opt)}
              >
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </button>
            );
          })}
        </div>
      </div>

      {/* history */}
      {decisionEvents.length > 0 && (
        <div>
          <div className="num" style={{ marginBottom: 10 }}>Histórico de decisões · auditável</div>
          <div style={{ border: '1px solid var(--border)', borderRadius: 2, overflow: 'hidden' }}>
            {decisionEvents.map((h, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 14px', borderBottom: i < decisionEvents.length - 1 ? '1px solid var(--border)' : 'none', fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 }}>
                <span style={{ color: 'var(--text3)', width: 52, flex: 'none' }}>
                  {typeof h.t === 'number' ? h.t.toFixed(1) + 's' : h.t}
                </span>
                <span className="sh green"></span>
                <span style={{ color: 'var(--text2)', flex: 1 }}>
                  Decisão no portão "{h.portao}"
                </span>
                <span style={{ color: 'var(--text)', textTransform: 'uppercase', fontSize: 9, letterSpacing: 0.6 }}>
                  {h.decisao || h.evento}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CaixaFundador() {
  const { data: gates, error: gatesError } = usePoll(getGates, []);
  const [selectedGate, setSelectedGate] = useState(null);
  const [selectMode, setSelectMode] = useState(false);
  const [checked, setChecked] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [resolvedGates, setResolvedGates] = useState(new Set());

  // Auto-seleciona o primeiro gate se nada estiver selecionado
  useEffect(() => {
    if (gates && gates.length > 0) {
      if (!selectedGate || !gates.some((g) => g.run === selectedGate.run && g.portao === selectedGate.portao)) {
        setSelectedGate(gates[0]);
      }
    } else {
      setSelectedGate(null);
    }
  }, [gates, selectedGate]);

  const toggleSelect = () => {
    setSelectMode(!selectMode);
    setChecked([]);
  };

  const handleCheck = (e, q) => {
    e.stopPropagation();
    const key = `${q.run}_${q.portao}`;
    setChecked((prev) => 
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const loteApprove = async () => {
    if (checked.length === 0) return;
    setSubmitting(true);
    try {
      const queueLocal = (gates || []);
      const checkedGates = queueLocal.filter((q) => checked.includes(`${q.run}_${q.portao}`));
      for (const g of checkedGates) {
        const decision = g.opcoes && g.opcoes.length > 0 ? g.opcoes[0] : 'prosseguir';
        await postGateDecision(g.portao, decision);
        setResolvedGates((prev) => new Set(prev).add(`${g.run}_${g.portao}`));
      }
    } catch (e) {
      console.error("Erro na aprovação em lote:", e);
    } finally {
      setSelectMode(false);
      setChecked([]);
      setSubmitting(false);
    }
  };

  const handleDecision = async (gate, option) => {
    setSubmitting(true);
    try {
      await postGateDecision(gate.portao, option);
      setResolvedGates((prev) => new Set(prev).add(`${gate.run}_${gate.portao}`));
      setSelectedGate(null);
    } catch (e) {
      console.error("Erro ao registrar decisão:", e);
    } finally {
      setSubmitting(false);
    }
  };

  const queue = (gates || []).map((q) => {
    const isSelected = selectedGate && selectedGate.run === q.run && selectedGate.portao === q.portao;
    const isChecked = checked.includes(`${q.run}_${q.portao}`);
    const isResolved = resolvedGates.has(`${q.run}_${q.portao}`);
    return {
      ...q,
      isSelected,
      isChecked,
      icon: q.portao === 'cobertura' ? '⛒' : '◆',
      origin: q.portao === 'cobertura' ? 'Gate humano' : `Gate ${q.portao}`,
      project: q.run,
      when: isResolved ? 'decisão registrada' : 'pendente',
      short: isResolved ? 'decisão registrada · aguardando motor' : q.pergunta,
    };
  });

  const pendCount = queue.length;
  const hasItems = pendCount > 0;
  const isEmpty = pendCount === 0;

  return (
    <div style={{
      display: 'flex',
      flex: 1,
      minHeight: 0,
      height: 'calc(100vh - 52px)',
      margin: '-22px -24px -60px',
      overflow: 'hidden',
    }}>
      <style>{`
        .qitem {
          padding: 14px 16px;
          border-bottom: 1px solid var(--border);
          cursor: pointer;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .qitem:hover {
          background: var(--surface2);
        }
        .qitem.on {
          background: var(--surface2);
          box-shadow: inset 2px 0 0 var(--accent);
        }
        .ico {
          width: 26px;
          height: 26px;
          flex: none;
          border: 1px solid var(--border);
          border-radius: 2px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          color: var(--text2);
        }
        .ctxpanel {
          flex: 1 1 280px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 2px;
          padding: 14px;
          min-width: 0;
        }
        .ctxpanel.wide {
          flex: 1 1 100%;
        }
        .diffline {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11.5px;
          line-height: 1.7;
          white-space: pre-wrap;
          padding: 0 6px;
        }
        .lnk {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: .6px;
          text-transform: uppercase;
          color: var(--text2);
          cursor: pointer;
        }
        .lnk:hover {
          color: var(--text);
        }
        .cbox {
          width: 15px;
          height: 15px;
          border: 1px solid var(--focus);
          border-radius: 2px;
          flex: none;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          color: var(--accent);
          cursor: pointer;
        }
        .cbox.ck {
          background: var(--accent);
          border-color: var(--accent);
          color: var(--bg);
        }
        table.tel {
          width: 100%;
          border-collapse: collapse;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
        }
        table.tel th {
          text-align: left;
          color: var(--text3);
          font-weight: 600;
          padding: 5px 8px;
          border-bottom: 1px solid var(--border);
          text-transform: uppercase;
          letter-spacing: .5px;
          font-size: 9px;
        }
        table.tel td {
          padding: 6px 8px;
          border-bottom: 1px solid var(--border);
          color: var(--text2);
        }
      `}</style>

      {/* QUEUE */}
      <div style={{
        width: 322,
        flex: 'none',
        borderRight: '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 16px',
          borderBottom: '1px solid var(--border)',
        }}>
          <span className="num" style={{ color: 'var(--accent)' }}>
            Fila de decisão · {pendCount}
          </span>
          {hasItems && (
            <span className="lnk" onClick={toggleSelect}>
              {selectMode ? 'cancelar' : 'selecionar'}
            </span>
          )}
        </div>

        {selectMode && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 16px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface2)',
          }}>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', flex: 1 }}>
              {checked.length} selecionados
            </span>
            <button
              disabled={submitting || checked.length === 0}
              className="btn btn-sm"
              onClick={loteApprove}
            >
              Aprovar selecionados
            </button>
          </div>
        )}

        <div style={{ flex: 1, overflow: 'auto', backgroundColor: 'var(--bg)' }}>
          {gatesError ? (
            <div style={{ padding: 16, color: 'var(--red)' }} className="mono">
              Erro: {gatesError}
            </div>
          ) : !gates ? (
            <div style={{ padding: 16, color: 'var(--text3)' }} className="mono">
              Carregando gates...
            </div>
          ) : isEmpty ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--text3)' }} className="mono">
              Fila vazia
            </div>
          ) : (
            queue.map((q) => (
              <div
                key={`${q.run}_${q.portao}`}
                className={`qitem ${q.isSelected ? 'on' : ''}`}
                onClick={() => setSelectedGate(q)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  {selectMode && (
                    <span
                      className={q.isChecked ? 'cbox ck' : 'cbox'}
                      onClick={(e) => handleCheck(e, q)}
                    >
                      ✓
                    </span>
                  )}
                  <span className="ico">{q.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className="sh amber"></span>
                      <span className="eyebrow" style={{ color: 'var(--accent)' }}>{q.origin}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 2 }}>{q.project}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 9, color: 'var(--text3)', flex: 'none' }}>{q.when}</span>
                </div>
                <div className="mono" style={{ fontSize: 11.5, color: 'var(--text2)', lineHeight: 1.45 }}>{q.short}</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* DETAIL */}
      <div style={{ flex: 1, overflow: 'auto', minWidth: 0, backgroundColor: 'var(--bg)' }}>
        {selectedGate ? (
          <GateDetail
            gate={selectedGate}
            onDecision={handleDecision}
            submitting={submitting}
          />
        ) : isEmpty ? (
          <div style={{
            height: '100%',
            minHeight: 520,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 40,
          }}>
            <div style={{
              width: 40,
              height: 40,
              border: '1.5px solid var(--green)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--green)',
              fontSize: 18,
            }}>✓</div>
            <div className="title" style={{ fontSize: 19 }}>Nada precisa de você agora</div>
            <div className="mono" style={{ fontSize: 12, color: 'var(--text2)', maxWidth: 420, textAlign: 'center', lineHeight: 1.6 }}>
              A fila está vazia. Quando um gate humano, o Curador ou o Orquestrador precisarem de uma decisão, a pendência aparece aqui e o sino acende. Você pode seguir observando os runs.
            </div>
            <div style={{ display: 'flex', gap: 9 }}>
              <span className="btn btn-sm" onClick={() => { window.location.hash = '/'; }}>Ir para a Home</span>
              <span className="btn btn-sm" onClick={() => { window.location.hash = '/runs'; }}>Abrir Runs &amp; Histórico</span>
            </div>
          </div>
        ) : (
          <div style={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <span className="mono" style={{ color: 'var(--text3)' }}>
              Selecione uma pendência para ver os detalhes
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
