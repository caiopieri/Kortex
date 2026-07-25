import { useState, useMemo } from 'react';
import { usePoll, fetchDados, getMissaoAtiva } from '../api.js';

/* ── Classificação de eventos ── */
const ERR_EVENTS = new Set([
  'portao.reprovado', 'provedor.esgotado', 'provedor.auto_esgotado',
  'modelo.falha', 'ferramenta.indisponivel', 'executor.erro',
  'tarefa.abortada', 'modelo.reroteado_esgotado', 'modelo.fallback',
]);

const INTER_EVENTS = new Set([
  'escalado', 'decisao.pendente', 'proposta.curador',
  'proposta.orquestrador', 'no.pedido_interacao',
]);

function classify(ev) {
  if (ERR_EVENTS.has(ev.evento))   return 'erros';
  if (INTER_EVENTS.has(ev.evento)) return 'inter';
  return 'normal';
}

function shapeFor(ev) {
  const e = ev.evento;
  if (e.includes('reprovado') || e.includes('erro') || e.includes('esgotado') || e.includes('abortada') || e.includes('indisponivel')) return 'sh red';
  if (e.includes('aprovado') || e.includes('concluida') || e.includes('concluido')) return 'sh green';
  if (e.includes('escalado') || e.includes('pendente') || e.includes('proposta') || e.includes('pedido_interacao')) return 'sh amber';
  if (e.includes('chamado') || e.includes('respondeu') || e.includes('paralelo')) return 'sh blue';
  return 'sh idle';
}

function fmtTime(t) {
  if (!t) return '—';
  return t.toFixed(3) + 's';
}

/* ── Column Component ── */
function LogCol({ title, count, countColor, subLabel, accentClass, rows }) {
  return (
    <div className="log-col">
      <div className={`log-colhead ${accentClass}`}>
        <span className="eyebrow" style={{ color: 'var(--text)' }}>{title}</span>
        <span className="mono" style={{ fontSize: 10, color: countColor }}>{count}</span>
        <div style={{ flex: 1 }}></div>
        <span className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>{subLabel}</span>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {rows.map((l, i) => (
          <div key={i} className={`lrow${accentClass === 'inter' ? ' link' : ''}`}
               onClick={accentClass === 'inter' ? () => { window.location.hash = '/caixa'; } : undefined}>
            <span className="lt">{l.t}</span>
            <span className={l.sh}></span>
            <div style={{ minWidth: 0 }}>
              <div className="lev" style={accentClass === 'erros' ? { color: 'var(--red)' } : accentClass === 'inter' ? { color: 'var(--amber)' } : {}}>{l.evt}</div>
              <div className="ldet">{l.det}</div>
              <div className="lproj">{l.proj}</div>
              {accentClass === 'inter' && <span className="caixa">→ Caixa do Fundador</span>}
            </div>
          </div>
        ))}
        {accentClass === 'inter' && (
          <div className="mono" style={{ fontSize: 9.5, color: 'var(--text3)', padding: '12px 14px', lineHeight: 1.5 }}>
            Não se decide aqui — a porta de decisão é uma só (§8.14). Cada item é um atalho para a Caixa.
          </div>
        )}
      </div>
    </div>
  );
}

export default function Logs() {
  const { data, error } = usePoll(fetchDados);
  const { data: missaoAtiva } = usePoll(getMissaoAtiva);
  const [query, setQuery] = useState('');
  const [projFilter, setProjFilter] = useState('todos');

  const eventos = useMemo(() => (data?.eventos || []).slice().reverse(), [data]);

  /* projetos únicos */
  const projetos = useMemo(() => {
    const s = new Set();
    eventos.forEach(ev => { const p = ev.missao || ev.run; if (p) s.add(p); });
    return ['todos', ...Array.from(s)];
  }, [eventos]);

  /* mapear e filtrar */
  const mapped = useMemo(() => {
    const q = query.trim().toLowerCase();
    return eventos
      .map(ev => {
        const proj = ev.missao || ev.run || '—';
        const det = [ev.executor, ev.tier, ev.portao, ev.tentativa ? `tent.${ev.tentativa}` : null, ev.provedor].filter(Boolean).join(' · ');
        return {
          t: fmtTime(ev.t),
          sh: shapeFor(ev),
          evt: ev.evento,
          det: det || '—',
          proj,
          kind: classify(ev),
        };
      })
      .filter(l => {
        if (projFilter !== 'todos' && l.proj !== projFilter) return false;
        if (q && !(l.evt + ' ' + l.det + ' ' + l.proj).toLowerCase().includes(q)) return false;
        return true;
      });
  }, [eventos, query, projFilter]);

  const limit = parseInt(localStorage.getItem('mf-stream-limit') || '50', 10);
  const normal = mapped.filter(l => l.kind === 'normal').slice(0, limit);
  const erros  = mapped.filter(l => l.kind === 'erros').slice(0, limit);
  const inter  = mapped.filter(l => l.kind === 'inter').slice(0, limit);

  if (error) return (
    <div>
      <span className="num">Logs</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!data) return (
    <div>
      <span className="num">Logs</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando logs…</span>
      </div>
    </div>
  );

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: 0 }}>
        <div className="eyebrow" style={{ marginBottom: 3 }}>Telemetria · stream de eventos JSONL</div>
        <div className="title" style={{ fontSize: 19 }}>Logs</div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 0', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
        <label className="srch">
          <span className="mono" style={{ color: 'var(--text3)', fontSize: 12 }}>⌕</span>
          <input type="text" placeholder="buscar evento, executor, id…" value={query} onInput={e => setQuery(e.target.value)} />
        </label>
        <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 2px' }}></div>
        <span className="eyebrow" style={{ marginRight: 2 }}>projeto</span>
        {projetos.map(p => (
          <span key={p} className={`pill${projFilter === p ? ' on' : ''}`} onClick={() => setProjFilter(p)}>{p}</span>
        ))}
        <div style={{ flex: 1 }}></div>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className={missaoAtiva?.ativa ? 'sh blue pulse' : 'sh idle'}></span>
          {missaoAtiva?.ativa ? 'AO VIVO · MOTOR' : 'MOTOR OCIOSO'}
        </span>
      </div>

      {/* 3 Columns */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0, marginTop: 0 }}>
        <LogCol title="Normal" count={normal.length} countColor="var(--text3)" subLabel="execução · roteamento" accentClass="normal" rows={normal} />
        <LogCol title="Erros" count={erros.length} countColor="var(--red)" subLabel="reprovado · esgotado · degradado" accentClass="erros" rows={erros} />
        <LogCol title="Interação" count={inter.length} countColor="var(--amber)" subLabel="→ decidir na Caixa" accentClass="inter" rows={inter} />
      </div>

      <style>{`
        .log-col{flex:1;min-width:0;display:flex;flex-direction:column;border-right:1px solid var(--border)}
        .log-col:last-child{border-right:none}
        .log-colhead{display:flex;align-items:center;gap:8px;padding:11px 14px;border-bottom:1px solid var(--border);background:var(--surface);position:relative}
        .log-colhead::before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px}
        .log-colhead.normal::before{background:var(--blue)}
        .log-colhead.erros::before{background:var(--red)}
        .log-colhead.inter::before{background:var(--amber)}
        .lrow{display:flex;gap:9px;padding:9px 14px;border-bottom:1px solid var(--border);align-items:flex-start}
        .lrow.link{cursor:pointer}
        .lrow.link:hover{background:var(--surface2)}
        .lt{font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:var(--text3);flex:none;width:52px;margin-top:2px}
        .lev{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text);word-break:break-word}
        .ldet{font-size:10.5px;color:var(--text2);line-height:1.5;margin-top:2px}
        .lproj{font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--text3)}
        .caixa{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--amber);margin-top:6px;display:inline-flex;align-items:center;gap:4px}
        .srch{display:flex;align-items:center;gap:8px;border:1px solid var(--border);border-radius:2px;padding:7px 11px;background:var(--surface);min-width:220px}
        .srch input{border:none;outline:none;background:transparent;color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;width:100%}
        .srch input::placeholder{color:var(--text3)}
      `}</style>
    </>
  );
}
