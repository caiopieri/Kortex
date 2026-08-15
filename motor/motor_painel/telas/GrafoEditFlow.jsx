/* GrafoEditFlow — prévia compilada da spec em React Flow (nós = retângulos verticais).
   Controlado pela spec: recebe nodesData/edgesData por prop e remonta quando a estrutura muda. */

if (!document.getElementById('mfef-style')) {
  const s = document.createElement('style');
  s.id = 'mfef-style';
  s.textContent = `
@keyframes mfefflow{to{stroke-dashoffset:-20}}
.mfef-flow{stroke-dasharray:4 6;animation:mfefflow 1.2s linear infinite}
.react-flow__attribution{display:none}
`;
  document.head.appendChild(s);
}

const MONO = "'IBM Plex Mono',monospace";

function makeNodeCard(RF) {
  const Handle = RF.Handle, Position = RF.Position;
  const R = window.React;
  return function NodeCard(p) {
    const d = p.data, selected = p.selected;
    const accent = d.kind === 'gate' ? 'var(--amber)' : (d.kind === 'valid' ? 'var(--green)' : 'var(--focus)');
    const st = {
      width: 150, minHeight: 96,
      background: 'var(--surface)',
      border: '1px solid ' + (selected ? 'var(--accent)' : 'var(--border)'),
      borderLeft: d.kind === 'valid' ? '3px solid var(--green)' : undefined,
      boxShadow: selected ? '0 0 0 1px var(--accent)' : 'none',
      borderRadius: 2, padding: 10, display: 'flex', flexDirection: 'column', gap: 5,
      color: 'var(--text)', fontFamily: 'Inter,system-ui,sans-serif', cursor: 'pointer', boxSizing: 'border-box',
    };
    const h = { width: 6, height: 6, background: 'var(--focus)', border: '1px solid var(--bg)', borderRadius: 1, opacity: 0 };
    return R.createElement('div', { style: st },
      d.noIn ? null : R.createElement(Handle, { type: 'target', position: Position.Left, style: h, isConnectable: false }),
      R.createElement('div', { style: { fontFamily: MONO, fontSize: 9, letterSpacing: '.5px', textTransform: 'uppercase', color: 'var(--text2)' } }, d.label),
      R.createElement('div', { style: { fontFamily: "'Space Grotesk',system-ui", fontWeight: 600, fontSize: 12.5 } }, d.name),
      d.hasValid ? R.createElement('div', { style: { fontFamily: MONO, fontSize: 9, color: 'var(--green)' } }, '■ ' + d.validN + ' validador(es)') : null,
      d.showGates ? R.createElement('div', { style: { fontFamily: MONO, fontSize: 9, color: 'var(--text3)' } }, '○ verificador') : null,
      d.noOut ? null : R.createElement(Handle, { type: 'source', position: Position.Right, style: h, isConnectable: false })
    );
  };
}

function makeEdgeLayer(RF, edgesData) {
  const R = window.React;
  return function EdgeLayer() {
    const transform = RF.useStore(function (s) { return s.transform; });
    const nodeInternals = RF.useStore(function (s) { return s.nodeInternals; });
    const posOf = function (id) {
      const n = nodeInternals.get(id);
      if (!n) return null;
      const pp = n.positionAbsolute || n.position;
      return { x: pp.x, y: pp.y, w: n.width || 150, h: n.height || 96 };
    };
    const paths = (edgesData || []).map(function (e) {
      const a = posOf(e.source), b = posOf(e.target);
      if (!a || !b) return null;
      const sx = a.x + a.w, sy = a.y + a.h / 2;
      const tx = b.x, ty = b.y + b.h / 2;
      const co = Math.max(30, Math.abs(tx - sx) / 2);
      const dd = 'M' + sx + ',' + sy + ' C' + (sx + co) + ',' + sy + ' ' + (tx - co) + ',' + ty + ' ' + tx + ',' + ty;
      return R.createElement('path', {
        key: e.id, d: dd, className: 'react-flow__edge-path mfef-edge' + (e.animated ? ' mfef-flow' : ''),
        style: { fill: 'none', stroke: e.color || 'var(--focus)', strokeWidth: 1.4, strokeDasharray: e.dash || undefined, strokeLinecap: 'round', opacity: e.opacity == null ? 1 : e.opacity },
      });
    });
    const t = transform || [0, 0, 1];
    return R.createElement('svg', { style: { position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 0, overflow: 'visible' } },
      R.createElement('g', { transform: 'translate(' + t[0] + ',' + t[1] + ') scale(' + t[2] + ')' }, paths));
  };
}

function GrafoEditFlow(props) {
  const R = window.React;
  const [ready, setReady] = R.useState(!!window.ReactFlow);
  R.useEffect(function () {
    if (window.ReactFlow) { setReady(true); return; }
    const t = setInterval(function () { if (window.ReactFlow) { clearInterval(t); setReady(true); } }, 60);
    return function () { clearInterval(t); };
  }, []);

  if (!ready) {
    return R.createElement('div', { style: { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontFamily: MONO, fontSize: 11, letterSpacing: '1px' } }, 'carregando prévia…');
  }

  const RF = window.ReactFlow;
  const Flow = RF.ReactFlow || RF.default;
  const Background = RF.Background, Controls = RF.Controls;

  const nodesData = props.nodes || [];
  const edgesData = props.edges || [];
  const sig = props.sig || '';

  const nodeTypes = R.useMemo(function () { return { mf: makeNodeCard(RF) }; }, []);
  const EdgeLayer = R.useMemo(function () { return makeEdgeLayer(RF, edgesData); }, [sig]);

  const nodes = nodesData.map(function (n) {
    return { id: n.id, type: 'mf', position: { x: n.x, y: n.y }, data: n, width: 150, height: 96, style: { width: 150 } };
  });

  const instRef = R.useRef(null);
  const onInit = function (inst) { instRef.current = inst; window.__efInst = inst; setTimeout(function () { inst.fitView({ padding: 0.14 }); }, 40); };

  return R.createElement('div', { style: { position: 'absolute', inset: 0 } },
    R.createElement(Flow, {
      key: sig,
      defaultNodes: nodes, defaultEdges: [], nodeTypes: nodeTypes,
      onInit: onInit, fitView: true, fitViewOptions: { padding: 0.14 },
      minZoom: 0.3, maxZoom: 1.8, deleteKeyCode: null, nodesConnectable: false,
      proOptions: { hideAttribution: true },
      onNodeClick: function (e, n) { if (props.onSelect) props.onSelect(n.id); },
    },
      R.createElement(EdgeLayer, null),
      Background ? R.createElement(Background, { gap: 24, size: 1, color: '#1a1d21' }) : null,
      Controls ? R.createElement(Controls, { showInteractive: false }) : null
    )
  );
}

window.GrafoEditFlow = GrafoEditFlow;
module.exports = { GrafoEditFlow: GrafoEditFlow };
