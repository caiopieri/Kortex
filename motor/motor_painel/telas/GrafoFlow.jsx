/* GrafoFlow — grafo 2D do workflow em React Flow (UMD), nós = retângulos verticais */
if (!document.getElementById('mfrf-style')) {
  const s = document.createElement('style');
  s.id = 'mfrf-style';
  s.textContent = `
@keyframes mfrfp{0%{opacity:.6;transform:scale(1)}100%{opacity:0;transform:scale(3)}}
.mfrf-pw{position:relative;display:inline-flex}
.mfrf-pw::after{content:"";position:absolute;inset:0;border-radius:50%;background:var(--blue);animation:mfrfp 2.1s ease-out infinite}
@keyframes mfrfflow{to{stroke-dashoffset:-20}}
.mfrf-flow{stroke-dasharray:4 6;animation:mfrfflow 1.2s linear infinite}
.mf-root[data-anim="off"] .mfrf-pw::after,.mf-root[data-anim="off"] .mfrf-flow{animation:none}
.react-flow__attribution{display:none}
`;
  document.head.appendChild(s);
}

const MONO = "'IBM Plex Mono',monospace";

function Shape(props) {
  const kind = props.kind;
  const b = { width: 10, height: 10, flex: 'none', display: 'inline-block' };
  if (kind === 'ds') return window.React.createElement('span', { style: { color: 'var(--text2)', fontSize: 14, lineHeight: 1 } }, '◇');
  const map = {
    green: Object.assign({}, b, { borderRadius: '50%', background: 'var(--green)' }),
    blue: Object.assign({}, b, { borderRadius: '50%', background: 'var(--blue)' }),
    idle: Object.assign({}, b, { borderRadius: '50%', background: 'var(--text3)' }),
    amber: Object.assign({}, b, { width: 12, height: 11, background: 'var(--amber)', clipPath: 'polygon(50% 0,100% 100%,0 100%)' }),
    red: Object.assign({}, b, { width: 11, height: 11, background: 'var(--red)', clipPath: 'polygon(30% 0,70% 0,100% 30%,100% 70%,70% 100%,30% 100%,0 70%,0 30%)' }),
    valid: Object.assign({}, b, { background: 'var(--green)' }),
  };
  return window.React.createElement('span', { style: map[kind] || map.idle });
}

function makeNodeCard(RF) {
  const Handle = RF.Handle, Position = RF.Position;
  return function NodeCard(p) {
    const data = p.data, selected = p.selected;
    const st = {
      width: 152, minHeight: data.slim ? 130 : 196,
      background: 'var(--surface)',
      border: (data.kind === 'ds' ? '1px dashed var(--focus)' : '1px solid ' + (data.paused ? 'var(--amber)' : selected ? 'var(--accent)' : 'var(--border)')),
      borderLeft: data.kind === 'valid' ? '3px solid var(--green)' : undefined,
      boxShadow: data.paused ? '0 0 0 1px var(--amber),0 0 26px rgba(232,163,61,.22)' : (selected ? '0 0 0 1px var(--accent)' : 'none'),
      borderRadius: 2, padding: 11, display: 'flex', flexDirection: 'column', gap: 7,
      color: 'var(--text)', fontFamily: 'Inter,system-ui,sans-serif',
      opacity: data.dim ? 0.7 : 1, cursor: 'pointer', boxSizing: 'border-box',
    };
    const h = { width: 7, height: 7, background: 'var(--focus)', border: '1px solid var(--bg)', borderRadius: 1 };
    return window.React.createElement('div', { style: st },
      data.noIn ? null : window.React.createElement(Handle, { type: 'target', position: Position.Left, style: h, isConnectable: false }),
      window.React.createElement('div', { style: { display: 'flex', justifyContent: 'center', paddingTop: 2 } },
        window.React.createElement('span', { className: data.pulse ? 'mfrf-pw' : '' }, window.React.createElement(Shape, { kind: data.shape }))),
      window.React.createElement('div', { style: { fontFamily: MONO, fontSize: 9.5, fontWeight: 600, letterSpacing: '.6px', textTransform: 'uppercase', textAlign: 'center', color: data.wordColor || 'var(--text2)' } }, data.word),
      window.React.createElement('div', { style: { fontFamily: "'Space Grotesk',system-ui", fontWeight: 600, fontSize: 13, textAlign: 'center' } }, data.name),
      window.React.createElement('div', { style: { fontFamily: MONO, fontSize: 9, color: 'var(--text2)', textAlign: 'center', lineHeight: 1.5 } }, data.meta),
      data.badge ? window.React.createElement('div', { style: { fontFamily: MONO, fontSize: 8.5, color: data.badgeColor || 'var(--accent)', border: '1px solid ' + (data.badgeColor || 'var(--border)'), borderRadius: 2, padding: '1px 5px', alignSelf: 'center' } }, data.badge) : null,
      window.React.createElement('div', { style: { flex: 1 } }),
      data.cost ? window.React.createElement('div', { style: { fontFamily: MONO, fontSize: 9.5, color: 'var(--text2)', borderTop: '1px solid var(--border)', paddingTop: 6, display: 'flex', justifyContent: 'space-between', gap: 6 } },
        window.React.createElement('span', { style: { color: 'var(--text3)', fontSize: 8.5, letterSpacing: '.6px' } }, 'CUSTO'),
        window.React.createElement('span', null, data.cost)) : null,
      data.foot ? window.React.createElement('div', { style: { fontFamily: MONO, fontSize: 8.5, color: data.footColor || 'var(--text3)', textAlign: 'center' } }, data.foot) : null,
      data.noOut ? null : window.React.createElement(Handle, { type: 'source', position: Position.Right, style: h, isConnectable: false })
    );
  };
}

const N = (id, x, y, data) => ({ id, type: 'mf', position: { x, y }, data, width: 152, height: data.slim ? 132 : 200, style: { width: 152 } });
const defaultNodes = [
  N('ds', 0, 10, { kind: 'ds', shape: 'ds', word: 'dataset · datahouse', name: 'receitas-benchmark', meta: 'HF · rag.consultado · 6 chunks', slim: true, noIn: true }),
  N('planner', 0, 260, { shape: 'green', word: 'concluído', name: 'planner', meta: 'planner · kimi-k2.6 · nvidia', cost: 'US$ 0,0121', foot: 'salvou plano.md', noIn: true }),
  N('alfa', 230, 40, { shape: 'green', word: 'aprovado', name: 'pesquisa-alfa', meta: 'pesquisador · llama-3.3-70b', badge: '◇ rag · 6 chunks', badgeColor: 'var(--text2)', cost: 'US$ 0,0064', foot: 'salvou alfa.md' }),
  N('beta', 230, 380, { shape: 'blue', pulse: true, word: 'pesquisando', name: 'pesquisa-beta', meta: 'pesquisador · llama-3.3 → kimi-k2.6', badge: '↑ escalado', cost: 'US$ 0,0143', foot: '✎ editando beta.md' }),
  N('vA', 460, 40, { shape: 'green', word: 'aprovado', name: 'verifier:alfa', meta: 'crítico LLM · codex', cost: 'US$ 0,0038', slim: true }),
  N('vB', 460, 330, { shape: 'blue', pulse: true, word: 'verificando', name: 'verifier:beta', meta: 'crítico LLM · ciclo 2', badge: '⚖', cost: 'US$ 0,0052', slim: true }),
  N('valid', 460, 560, { kind: 'valid', shape: 'valid', word: 'passou', wordColor: 'var(--green)', name: 'validador · beta', meta: 'schema_json + contem "ticket médio"', badge: 'determinístico', badgeColor: 'var(--green)', foot: '✓ por algoritmo · sem LLM', footColor: 'var(--green)', slim: true }),
  N('gEval', 690, 210, { shape: 'blue', pulse: true, word: 'executando', name: 'global_evaluator', meta: 'evaluator · codex/gpt-5.4', badge: '⚖ verificação', cost: 'US$ 0,0089', foot: '✎ cobertura.md' }),
  N('gate', 920, 40, { shape: 'amber', word: 'aguardando você', wordColor: 'var(--amber)', name: 'gate cobertura', meta: 'portão humano · reprovado ciclo 2', paused: true, badge: '⏸ run pausado', badgeColor: 'var(--amber)', foot: '→ Caixa do Fundador', footColor: 'var(--amber)' }),
  N('synth', 920, 350, { shape: 'idle', word: 'na fila', wordColor: 'var(--text3)', name: 'synthesizer', meta: 'synthesizer · codex/gpt-5.4', dim: true, foot: 'bloqueado pelo gate' }),
  N('art', 1150, 250, { shape: 'idle', word: 'pendente', wordColor: 'var(--text3)', name: 'artefato · digest', meta: 'saída do run', dim: true, slim: true, noOut: true }),
];

// Arestas desenhadas por camada SVG própria (independe de handleBounds do RF)
const EDGES = [
  { id: 'e-ds-alfa', source: 'ds', target: 'alfa', color: 'var(--focus)', w: 1.2, dash: '2 4' },
  { id: 'e-p-alfa', source: 'planner', target: 'alfa', color: '#2b2f35', w: 1.4 },
  { id: 'e-p-beta', source: 'planner', target: 'beta', color: 'var(--blue)', w: 1.6, animated: true },
  { id: 'e-alfa-va', source: 'alfa', target: 'vA', color: '#2b2f35', w: 1.4 },
  { id: 'e-beta-vb', source: 'beta', target: 'vB', color: 'var(--blue)', w: 1.6, animated: true },
  { id: 'e-beta-valid', source: 'beta', target: 'valid', color: 'var(--green)', w: 1.4, opacity: 0.55 },
  { id: 'e-va-ge', source: 'vA', target: 'gEval', color: '#2b2f35', w: 1.4 },
  { id: 'e-vb-ge', source: 'vB', target: 'gEval', color: 'var(--blue)', w: 1.6, animated: true },
  { id: 'e-ge-gate', source: 'gEval', target: 'gate', color: 'var(--amber)', w: 1.6, opacity: 0.7 },
  { id: 'e-gate-synth', source: 'gate', target: 'synth', color: '#2b2f35', w: 1.4, dash: '4 5' },
  { id: 'e-synth-art', source: 'synth', target: 'art', color: '#2b2f35', w: 1.4, dash: '4 5' },
];

const NODE_IDS = ['ds', 'planner', 'alfa', 'beta', 'vA', 'vB', 'valid', 'gEval', 'gate', 'synth', 'art'];

// Camada SVG de arestas — lê posições/dimensões dos nós do store do RF e o transform do
// viewport; independe do passe de medição de handles (handleBounds), que não roda sob x-import.
function EdgeLayer() {
  const RF = window.ReactFlow;
  const transform = RF.useStore(function (s) { return s.transform; });
  const nodeInternals = RF.useStore(function (s) { return s.nodeInternals; });

  const posOf = function (id) {
    const n = nodeInternals.get(id);
    if (!n) return null;
    const p = n.positionAbsolute || n.position;
    return { x: p.x, y: p.y, w: n.width || 152, h: n.height || 200 };
  };

  const paths = EDGES.map(function (e) {
    const a = posOf(e.source), b = posOf(e.target);
    if (!a || !b) return null;
    const sx = a.x + a.w, sy = a.y + a.h / 2;
    const tx = b.x, ty = b.y + b.h / 2;
    const co = Math.max(36, Math.abs(tx - sx) / 2);
    const d = 'M' + sx + ',' + sy + ' C' + (sx + co) + ',' + sy + ' ' + (tx - co) + ',' + ty + ' ' + tx + ',' + ty;
    return window.React.createElement('path', {
      key: e.id, d: d, className: 'react-flow__edge-path mfrf-edge' + (e.animated ? ' mfrf-flow' : ''),
      style: {
        fill: 'none', stroke: e.color, strokeWidth: e.w || 1.5,
        strokeDasharray: e.dash || undefined, strokeLinecap: 'round',
        opacity: e.opacity == null ? 1 : e.opacity,
      },
    });
  });

  const t = transform || [0, 0, 1];
  return window.React.createElement('svg', {
    style: { position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0, overflow: 'visible' },
  }, window.React.createElement('g', { transform: 'translate(' + t[0] + ',' + t[1] + ') scale(' + t[2] + ')' }, paths));
}

function GrafoFlow(props) {
  const [ready, setReady] = window.React.useState(!!window.ReactFlow);
  window.React.useEffect(function () {
    if (window.ReactFlow) { setReady(true); return; }
    const t = setInterval(function () {
      if (window.ReactFlow) { clearInterval(t); setReady(true); }
    }, 60);
    return function () { clearInterval(t); };
  }, []);

  const nodeTypes = window.React.useMemo(function () {
    return window.ReactFlow ? { mf: makeNodeCard(window.ReactFlow) } : {};
  }, [ready]);

  if (!ready) {
    return window.React.createElement('div', { style: { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontFamily: MONO, fontSize: 11, letterSpacing: '1px' } }, 'carregando grafo…');
  }

  const RF = window.ReactFlow;
  const Flow = RF.ReactFlow || RF.default;
  const Background = RF.Background, Controls = RF.Controls;
  const instRef = window.React.useRef(null);

  const onInit = function (inst) {
    instRef.current = inst;
    window.__rfInst = inst;
    const nudge = function () {
      try { window.dispatchEvent(new Event('resize')); } catch (e) {}
      if (instRef.current && instRef.current.fitView) instRef.current.fitView({ padding: 0.12 });
    };
    setTimeout(nudge, 30);
    setTimeout(nudge, 180);
    setTimeout(nudge, 500);
  };

  return window.React.createElement('div', { style: { position: 'absolute', inset: 0 } },
    window.React.createElement(Flow, {
      defaultNodes: defaultNodes, defaultEdges: [], nodeTypes: nodeTypes,
      onInit: onInit,
      fitView: true, fitViewOptions: { padding: 0.12 },
      minZoom: 0.35, maxZoom: 1.6,
      nodesConnectable: false, deleteKeyCode: null,
      proOptions: { hideAttribution: true },
      onNodeClick: function (e, n) { if (props.onSelect) props.onSelect(n.id); },
    },
      window.React.createElement(EdgeLayer, null),
      Background ? window.React.createElement(Background, { gap: 26, size: 1, color: '#1a1d21' }) : null,
      Controls ? window.React.createElement(Controls, { showInteractive: false }) : null
    )
  );
}

window.GrafoFlow = GrafoFlow;
module.exports = { GrafoFlow: GrafoFlow };
