import { useState } from 'react';
import { usePoll, fetchRuns, getGates, fetchDados, getMissaoAtiva } from '../api.js';

/* ── helpers ── */
const COL_DEFS = [
  { key: 'ideias',  num: '01', label: 'Ideias',          sub: 'backlog cru · você arrasta →',    accent: 'var(--text2)' },
  { key: 'plan',    num: '02', label: 'Planejamento',     sub: 'gate de plano · decisao.plano',   accent: 'var(--blue)' },
  { key: 'prod',    num: '03', label: 'Produção',         sub: 'motor executando · status ao vivo', accent: 'var(--blue)' },
  { key: 'precisa', num: '04', label: 'Precisa de você',  sub: 'gate humano · PARA o run',         accent: 'var(--amber)' },
  { key: 'done',    num: '05', label: 'Concluída',        sub: 'digest · arquivável',              accent: 'var(--green)' },
];

function shapeFor(estado) {
  if (estado === 'ativa')     return 'sh blue pulse';
  if (estado === 'concluida') return 'sh green';
  if (estado === 'abortada')  return 'sh red';
  return 'sh idle';
}

function colFor(run, gateIds) {
  if (run.estado === 'concluida' || run.estado === 'abortada') return 'done';
  if (gateIds.has(run.id))        return 'precisa';
  if (run.estado === 'ativa')     return 'prod';
  return 'plan';
}

/* ── Card ── */
function BCard({ card, col }) {
  let cls = 'bcard';
  if (col === 'ideias' || col === 'plan') cls += ' drag';
  if (col === 'precisa') cls += ' amber';
  if (col === 'done')    cls += ' done';

  return (
    <div className={cls}>
      <div className="btop">
        <span className={card.shape}></span>
        <span className="btitle" style={{ flex: 1, minWidth: 0 }}>{card.title}</span>
        {(col === 'ideias' || col === 'plan') && <span className="handle" title="arrastável">⠿</span>}
        {card.motor && <span className="chip motor">⬡ motor</span>}
      </div>
      <div className="bnote">{card.note}</div>
      {card.cost && <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>custo · {card.cost}</div>}
      <div className="bev">
        <span className={card.shape}></span>
        <span className="t">{card.ev}</span>
      </div>
      {/* Actions */}
      <div style={{ display: 'flex', gap: 7, alignItems: 'center', flexWrap: 'wrap' }}>
        {col === 'ideias' && <span className="btn btn-sm btn-primary" onClick={card.onPromote}>promover →</span>}
        {col === 'plan' && (
          <>
            <span className="btn btn-sm btn-primary" onClick={() => window.location.hash = '/nova-missao'}>empurrar p/ produção →</span>
            <span className="lnk" onClick={() => window.location.hash = '/canvas'}>abrir no Canvas</span>
          </>
        )}
        {col === 'precisa' && <span className="lnk amber" onClick={() => window.location.hash = '/caixa'}>→ abrir na Caixa do Fundador</span>}
        {col === 'done' && (
          <>
            <span className="lnk" onClick={() => window.location.hash = `/runs/${card.id}`}>ver digest</span>
          </>
        )}
      </div>
      {col === 'ideias' && <div className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>candidato · vira missão ou projeto</div>}
    </div>
  );
}

/* ── Main ── */
export default function Board() {
  const { data: runs, error: e1 } = usePoll(fetchRuns);
  const { data: gates, error: e2 } = usePoll(getGates);
  const { data: fullData } = usePoll(fetchDados);
  const { data: missaoAtiva } = usePoll(getMissaoAtiva);
  /* Comecava semeado com duas ideias inventadas ("Nota fiscal PDF -> JSON",
     "Landing de produto"), que pareciam backlog real e nao eram de ninguem
     (issue #23). Nao ha onde guardar ideia no Kortex: nao existe tabela, nem
     evento, nem endpoint. Entao a coluna nasce vazia e declara o que ela e. */
  const [ideas, setIdeas] = useState([]);

  const error = e1 || e2;
  const isLoading = !runs || !gates;

  if (error) return (
    <div>
      <span className="num">Board</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (isLoading) return (
    <div>
      <span className="num">Board</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando board…</span>
      </div>
    </div>
  );

  /* Gate IDs for "Precisa de você" column */
  const gateRunIds = new Set((gates || []).map(g => g.run || g.missao).filter(Boolean));

  /* Build run-based cards */
  const runCards = (runs || []).map(r => {
    const col = colFor(r, gateRunIds);
    const eventos = (fullData?.eventos || []).filter(ev => (ev.missao || ev.run) === r.id);
    const lastEv = eventos.length > 0 ? eventos[eventos.length - 1] : null;
    return {
      id: r.id,
      col,
      title: r.objetivo || r.id,
      note: `${eventos.length} eventos · estado: ${r.estado}`,
      shape: shapeFor(r.estado),
      ev: lastEv ? `${lastEv.evento}` : `estado: ${r.estado}`,
      cost: r.custo > 0 ? `US$ ${r.custo.toFixed(2)}` : null,
      motor: col === 'prod' || col === 'precisa',
    };
  });

  /* Idea cards */
  const ideaCards = ideas.map(i => ({
    ...i,
    col: i.col || 'ideias',
    shape: 'sh idle',
    onPromote: () => setIdeas(prev => prev.map(x => x.id === i.id ? { ...x, col: 'plan' } : x)),
  }));

  /* Group into columns */
  const columns = COL_DEFS.map(def => {
    let cards;
    if (def.key === 'ideias') {
      cards = ideaCards.filter(c => c.col === 'ideias');
    } else {
      cards = [...runCards.filter(c => c.col === def.key), ...ideaCards.filter(c => c.col === def.key)];
    }
    return { ...def, cards, count: cards.length, empty: cards.length === 0 };
  });

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 0 }}>
        <span className="title" style={{ fontSize: 20 }}>Board de missões</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>ciclo de vida da missão</span>
        <div style={{ flex: 1 }}></div>
        {/* Antes isto dizia AO VIVO com a bolinha pulsando sempre, mesmo com o
            motor parado. /dados/missoes/ativa sabe a verdade. */}
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className={missaoAtiva?.ativa ? 'sh blue pulse' : 'sh idle'}></span>
          {missaoAtiva?.ativa ? 'AO VIVO · MOTOR' : 'MOTOR OCIOSO'}
        </span>
      </div>

      {/* Honest rule banner */}
      <div className="card" style={{ padding: '9px 14px', margin: '12px 0 0' }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>
          <b style={{ color: 'var(--text)' }}>Você</b> arrasta <b style={{ color: 'var(--text)' }}>Ideias → Planejamento</b> e empurra para <b style={{ color: 'var(--text)' }}>Produção</b>. Da Produção em diante, <b style={{ color: 'var(--text)' }}>o motor</b> move os cards — o board reflete o estado real dos eventos, não comanda por arrasto.
        </span>
      </div>

      {/* Board Kanban */}
      <div style={{ display: 'flex', gap: 14, overflowX: 'auto', marginTop: 16, flex: 1, minHeight: 0 }}>
        {columns.map(col => (
          <div key={col.key} style={{ width: 262, flex: 'none', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 2px 9px', borderBottom: '1px solid var(--border)', marginBottom: 10 }}>
              <span className="num" style={{ color: col.accent }}>{col.num} — {col.label}</span>
              <span style={{ marginLeft: 'auto', fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: 'var(--text3)', border: '1px solid var(--border)', borderRadius: 2, padding: '0 6px' }}>{col.count}</span>
            </div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, letterSpacing: '.6px', textTransform: 'uppercase', color: 'var(--text3)', margin: '-4px 2px 10px' }}>{col.sub}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9, overflowY: 'auto', paddingRight: 2 }}>
              {col.cards.map(card => (
                <BCard key={card.id} card={card} col={col.key} />
              ))}
              {col.empty && (
                <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', padding: 10, border: '1px dashed var(--border)', borderRadius: 2, textAlign: 'center', lineHeight: 1.6 }}>
                  {col.key === 'ideias'
                    ? 'sem backlog · o Kortex não guarda ideia em lugar nenhum'
                    : 'vazio'}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <style>{`
        .bcard{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:11px 12px;display:flex;flex-direction:column;gap:8px}
        .bcard.drag{border-left:2px solid var(--focus)}
        .bcard.amber{border-left:2px solid var(--amber);box-shadow:0 0 22px color-mix(in srgb, var(--amber) 14%, transparent)}
        .bcard.done{opacity:.86}
        .btop{display:flex;align-items:center;gap:7px}
        .handle{cursor:grab;color:var(--text3);font-size:13px;letter-spacing:-2px}
        .chip{font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:.5px;text-transform:uppercase;color:var(--text3);border:1px solid var(--border);border-radius:2px;padding:1px 5px}
        .chip.motor{color:var(--text2)}
        .btitle{font-family:'Space Grotesk',system-ui;font-weight:600;font-size:13.5px;line-height:1.25}
        .bnote{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text2);line-height:1.45}
        .bev{display:flex;align-items:center;gap:7px;padding-top:8px;border-top:1px solid var(--border)}
        .bev .t{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
      `}</style>
    </>
  );
}
