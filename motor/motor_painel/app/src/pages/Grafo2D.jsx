import { useState, useEffect } from 'react';
import ReactFlow, { Background, Controls, useStore } from 'reactflow';
import 'reactflow/dist/style.css';

// Estilo de bordas circulares ou formas do LED/Pill
function Shape({ kind }) {
  const b = { width: 10, height: 10, flex: 'none', display: 'inline-block' };
  if (kind === 'ds') {
    return <span style={{ color: 'var(--text2)', fontSize: 14, lineHeight: 1, marginRight: 4 }}>◇</span>;
  }
  const map = {
    green: { ...b, borderRadius: '50%', background: 'var(--green)' },
    blue: { ...b, borderRadius: '50%', background: 'var(--blue)' },
    idle: { ...b, borderRadius: '50%', background: 'var(--text3)' },
    amber: { ...b, width: 12, height: 11, background: 'var(--amber)', clipPath: 'polygon(50% 0,100% 100%,0 100%)' },
    red: { ...b, width: 11, height: 11, background: 'var(--red)', clipPath: 'polygon(30% 0,70% 0,100% 30%,100% 70%,70% 100%,30% 100%,0 70%,0 30%)' },
    valid: { ...b, background: 'var(--green)' },
  };
  const style = map[kind] || map.idle;
  return <span style={style} />;
}

// Custom Node Card para renderizar no React Flow
function NodeCard({ data, selected }) {
  const st = {
    width: 152,
    minHeight: data.slim ? 130 : 196,
    background: 'var(--surface)',
    border: data.kind === 'ds' ? '1px dashed var(--focus)' : '1px solid ' + (data.paused ? 'var(--amber)' : selected ? 'var(--accent)' : 'var(--border)'),
    borderLeft: data.kind === 'valid' ? '3px solid var(--green)' : undefined,
    boxShadow: data.paused ? '0 0 0 1px var(--amber),0 0 26px rgba(232,163,61,.22)' : (selected ? '0 0 0 1px var(--accent)' : 'none'),
    borderRadius: 2,
    padding: 11,
    display: 'flex',
    flexDirection: 'column',
    gap: 7,
    color: 'var(--text)',
    fontFamily: 'Inter,system-ui,sans-serif',
    opacity: data.dim ? 0.7 : 1,
    cursor: 'pointer',
    boxSizing: 'border-box',
  };
  
  return (
    <div style={st}>
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 2 }}>
        <span className={data.pulse ? 'mfrf-pw' : ''}>
          <Shape kind={data.shape} />
        </span>
      </div>
      <div style={{
        fontFamily: "'IBM Plex Mono',monospace",
        fontSize: '9.5px',
        fontWeight: 600,
        letterSpacing: '.6px',
        textTransform: 'uppercase',
        textAlign: 'center',
        color: data.wordColor || 'var(--text2)'
      }}>
        {data.word}
      </div>
      <div style={{ fontFamily: "'Space Grotesk',system-ui", fontWeight: 600, fontSize: 13, textAlign: 'center' }}>
        {data.name}
      </div>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 9, color: 'var(--text2)', textAlign: 'center', lineHeight: 1.5 }}>
        {data.meta}
      </div>
      {data.badge ? (
        <div style={{
          fontFamily: "'IBM Plex Mono',monospace",
          fontSize: '8.5px',
          color: data.badgeColor || 'var(--accent)',
          border: '1px solid ' + (data.badgeColor || 'var(--border)'),
          borderRadius: 2,
          padding: '1px 5px',
          alignSelf: 'center'
        }}>
          {data.badge}
        </div>
      ) : null}
      <div style={{ flex: 1 }} />
      {data.tokens ? (
        <div style={{
          fontFamily: "'IBM Plex Mono',monospace",
          fontSize: '9.5px',
          color: 'var(--text2)',
          borderTop: '1px solid var(--border)',
          paddingTop: 6,
          display: 'flex',
          justifyContent: 'space-between',
          gap: 6
        }}>
          <span style={{ color: 'var(--text3)', fontSize: '8.5px', letterSpacing: '.6px' }}>TOKENS</span>
          <span>{data.tokens}</span>
        </div>
      ) : null}
      {data.foot ? (
        <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: '8.5px', color: data.footColor || 'var(--text3)', textAlign: 'center' }}>
          {data.foot}
        </div>
      ) : null}
    </div>
  );
}

const nodeTypes = {
  mf: NodeCard
};

// Camada SVG de arestas customizadas para maior fidelidade visual
function EdgeLayer({ edges }) {
  const transform = useStore((s) => s.transform);
  const nodeInternals = useStore((s) => s.nodeInternals);

  const posOf = (id) => {
    const n = nodeInternals.get(id);
    if (!n) return null;
    const p = n.positionAbsolute || n.position;
    const isSlim = n.data?.slim;
    const w = n.width || 152;
    const h = n.height || (isSlim ? 130 : 196);
    return { x: p.x, y: p.y, w, h };
  };

  const paths = edges.map((e) => {
    const a = posOf(e.source), b = posOf(e.target);
    if (!a || !b) return null;
    const sx = a.x + a.w, sy = a.y + a.h / 2;
    const tx = b.x, ty = b.y + b.h / 2;
    const co = Math.max(36, Math.abs(tx - sx) / 2);
    const d = `M${sx},${sy} C${sx + co},${sy} ${tx - co},${ty} ${tx},${ty}`;
    
    return (
      <path
        key={e.id}
        d={d}
        className={`react-flow__edge-path mfrf-edge${e.animated ? ' mfrf-flow' : ''}`}
        style={{
          fill: 'none',
          stroke: e.color,
          strokeWidth: e.w || 1.4,
          strokeDasharray: e.dash || undefined,
          strokeLinecap: 'round',
          opacity: e.opacity ?? 1,
        }}
      />
    );
  });

  const t = transform || [0, 0, 1];
  return (
    <svg
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 0,
        overflow: 'visible'
      }}
    >
      <g transform={`translate(${t[0]},${t[1]}) scale(${t[2]})`}>
        {paths}
      </g>
    </svg>
  );
}

// Função auxiliar para obter coluna de posicionamento no Grafo 2D
function getColuna(no) {
  const id = no.id.toLowerCase();
  const tipo = no.tipo.toLowerCase();
  
  if (id === 'ds' || id.includes('datahouse') || id.includes('benchmark')) return 0;
  if (id === 'planner' || id === 'motor') return 0;
  if (tipo === 'subagente') return 1;
  if (id.startsWith('verifier:') || id.includes('validador') || id.includes('valid') || (tipo === 'portao' && id !== 'cobertura')) return 2;
  if (id === 'global_evaluator' || id === 'geval') return 3;
  if (id === 'gate' || id === 'cobertura' || id === 'synthesizer' || id === 'synth' || id === 'fundador' || tipo === 'decisor') return 4;
  if (id === 'art' || id.includes('artefato') || id.includes('digest')) return 5;
  
  return 1;
}

// Derivação detalhada dos metadados de cada nó a partir da lista de eventos brutos
function derivarDetalhesNo(no, eventos) {
  const id = no.id;
  
  let shape = 'idle';
  let pulse = false;
  let word = 'na fila';
  let wordColor = 'var(--text3)';
  let meta = '';
  let badge = '';
  let badgeColor = '';
  let tokens = '';
  let totalTokens = 0;
  let foot = '';
  let footColor = '';
  let slim = false;
  let paused = false;
  let role = '';
  let model = '';
  let liveLogs = [];
  let files = [];
  
  const evsNo = eventos.filter(ev => {
    return ev.executor === id || 
           ev.portao === id || 
           (ev.evento === 'paralelo.iniciado' && ev.subagentes && ev.subagentes.includes(id)) ||
           (id === 'fundador' && (ev.evento === 'escalado' || ev.evento?.startsWith('decisao')));
  });
  
  if (id === 'ds' || id.includes('benchmark')) {
    role = 'dataset · datahouse';
    meta = 'dataset';
    wordColor = 'var(--text2)';
    slim = true;
    shape = 'ds';
  } else if (id === 'planner') {
    role = 'planner';
    meta = 'planner';
    slim = false;
  } else if (id === 'global_evaluator' || id === 'gEval') {
    role = 'global_evaluator';
    meta = 'evaluator';
    badge = '⚖ verificação';
    slim = false;
  } else if (id === 'synthesizer' || id === 'synth') {
    role = 'synthesizer';
    meta = 'synthesizer';
    slim = false;
  } else if (id === 'gate' || id === 'cobertura') {
    role = 'portão humano';
    meta = 'cobertura · pendente';
    slim = false;
  } else if (id === 'fundador') {
    role = 'decisor humano';
    meta = 'fundador';
    slim = true;
  } else if (id === 'art' || id.includes('artefato')) {
    role = 'artefato final';
    meta = 'saída do run';
    slim = true;
  } else if (id.startsWith('verifier:')) {
    role = 'verificador · crítico LLM';
    meta = 'crítico LLM';
    slim = true;
  } else if (id.includes('valid') || id.includes('validador')) {
    role = 'validador determinístico';
    meta = 'validador';
    badge = 'determinístico';
    badgeColor = 'var(--green)';
    foot = '✓ por algoritmo · sem LLM';
    footColor = 'var(--green)';
    slim = true;
    shape = 'valid';
  } else {
    role = 'pesquisador';
    meta = 'pesquisador';
    slim = false;
  }
  
  evsNo.forEach(ev => {
    const evName = ev.evento || '';
    const tStr = ev.t ? `${ev.t.toFixed(3)}s` : '';
    let logMsg = `${tStr} ${evName}`;
    if (ev.modelo) logMsg += ` (${ev.modelo})`;
    if (ev.mensagem) logMsg += `: ${ev.mensagem}`;
    if (ev.motivo) logMsg += ` - ${ev.motivo}`;
    liveLogs.push(logMsg);
    
    if (ev.modelo) {
      model = ev.modelo;
      if (id !== 'ds' && id !== 'art') {
        meta = `${role} · ${model}`;
      }
    }
    
    if (evName === 'executor.chamado') {
      word = id === 'planner' ? 'planejando' : (id.includes('beta') || id.includes('alfa') ? 'pesquisando' : 'executando');
      shape = 'blue';
      pulse = true;
      wordColor = 'var(--blue)';
    } else if (evName === 'executor.respondeu') {
      word = id === 'planner' ? 'concluído' : 'aprovado';
      shape = 'green';
      pulse = false;
      wordColor = 'var(--green)';
    } else if (evName === 'executor.erro' || evName === 'modelo.falha') {
      word = 'falhou';
      shape = 'red';
      pulse = false;
      wordColor = 'var(--red)';
    } else if (evName === 'portao.aprovado') {
      word = 'aprovado';
      shape = 'green';
      pulse = false;
      wordColor = 'var(--green)';
    } else if (evName === 'portao.reprovado') {
      word = 'reprovado';
      shape = 'red';
      pulse = false;
      wordColor = 'var(--red)';
    } else if (evName === 'decisao.pendente' || evName === 'escalado') {
      if (evName === 'escalado' && ev.para === 'fundador') {
        word = 'aguardando você';
        shape = 'amber';
        pulse = false;
        wordColor = 'var(--amber)';
        paused = true;
      }
    } else if (evName === 'decisao.fundador') {
      word = 'aprovado';
      shape = 'green';
      pulse = false;
      wordColor = 'var(--green)';
      paused = false;
    }
    
    if (evName === 'modelo.uso') {
      totalTokens += (ev.prompt_tokens || 0) + (ev.completion_tokens || 0);
    }

    if (evName === 'artefato.atualizou') {
      const caminho = ev.artefato || ev.caminho;
      if (caminho) files.push({ n: caminho });
    }
  });

  if (totalTokens > 0) {
    tokens = totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : String(totalTokens);
  }
  
  if (liveLogs.length === 0) {
    liveLogs.push('sem eventos registrados para este nó.');
  }

  if (id === 'art') {
    word = 'artefato · digest';
    meta = 'saída final do run';
    if (eventos.some(e => e.evento === 'tarefa.concluida')) {
      word = 'concluído';
      shape = 'green';
      wordColor = 'var(--green)';
    }
  }
  
  return {
    shape,
    pulse,
    word,
    wordColor,
    meta,
    badge,
    badgeColor,
    tokens,
    foot,
    footColor,
    slim,
    paused,
    role,
    model,
    live: liveLogs.join('\n'),
    files,
    noFiles: files.length === 0
  };
}

export default function Grafo2D() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState('planner');
  const [mode, setMode] = useState('live');
  const [filter, setFilter] = useState('todos');
  const [tlOpen, setTlOpen] = useState(true);
  const [tlExpandId, setTlExpandId] = useState(null);

  // Polling de 2 segundos ativo apenas se mode for 'live'
  useEffect(() => {
    if (mode !== 'live') return;
    
    let active = true;
    const tick = () => {
      fetch('/dados')
        .then(r => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then(d => {
          if (active) {
            setData(d);
            setError(null);
          }
        })
        .catch(e => {
          if (active) {
            setError(e.message);
          }
        });
    };
    
    tick();
    const intervalId = setInterval(tick, 2000);
    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [mode]);

  // Se estiver carregando pela primeira vez sem erro
  if (!data && !error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--text3)' }}>
        <span className="mono">carregando grafo…</span>
      </div>
    );
  }

  // Se houver erro
  if (error && !data) {
    return (
      <div style={{ padding: 20 }}>
        <span className="num">Grafo 2D · Erro</span>
        <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
          <span className="mono" style={{ color: 'var(--red)' }}>Erro ao obter dados: {error}</span>
        </div>
      </div>
    );
  }

  const eventos = data?.eventos || [];
  const nos_brutos = data?.nos || [];
  const arestas_brutas = data?.arestas || [];

  // Mapear nós do React Flow e calcular suas posições
  const nosPorColuna = { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [] };
  nos_brutos.forEach(no => {
    const col = getColuna(no);
    nosPorColuna[col].push(no);
  });

  const colunasX = [40, 260, 480, 700, 920, 1140];
  const flowNodes = [];

  Object.keys(nosPorColuna).forEach(colIdx => {
    const col = parseInt(colIdx);
    const lista = nosPorColuna[col];
    const total = lista.length;
    
    lista.forEach((no, index) => {
      let y = 100;
      if (total === 1) {
        y = 200;
      } else {
        const totalHeight = 550;
        const gap = totalHeight / (total + 1);
        y = (index + 1) * gap;
      }
      
      // Coordenadas fixas alinhadas com o protótipo
      if (no.id === 'ds') y = 10;
      else if (no.id === 'planner') y = 260;
      else if (no.id === 'pesquisa-alfa' || no.id === 'alfa') y = 40;
      else if (no.id === 'pesquisa-beta' || no.id === 'beta') y = 380;
      else if (no.id === 'verifier:pesquisa-alfa' || no.id === 'vA') y = 40;
      else if (no.id === 'verifier:pesquisa-beta' || no.id === 'vB') y = 330;
      else if (no.id === 'validador · beta' || no.id === 'valid') y = 560;
      else if (no.id === 'global_evaluator' || no.id === 'gEval') y = 210;
      else if (no.id === 'gate cobertura' || no.id === 'gate') y = 40;
      else if (no.id === 'synthesizer' || no.id === 'synth') y = 350;
      else if (no.id === 'artefato · digest' || no.id === 'art') y = 250;
      
      const details = derivarDetalhesNo(no, eventos);
      
      flowNodes.push({
        id: no.id,
        type: 'mf',
        position: { x: colunasX[col], y: y },
        data: {
          id: no.id,
          kind: no.id === 'ds' ? 'ds' : (no.id.includes('valid') ? 'valid' : 'normal'),
          shape: details.shape,
          pulse: details.pulse,
          word: details.word,
          wordColor: details.wordColor,
          name: no.id,
          meta: details.meta,
          badge: details.badge,
          badgeColor: details.badgeColor,
          tokens: details.tokens,
          foot: details.foot,
          footColor: details.footColor,
          slim: details.slim,
          noIn: col === 0,
          noOut: col === 5,
          paused: details.paused,
        }
      });
    });
  });

  // Mapear arestas do React Flow com estilos dinâmicos baseados no estado dos nós
  const flowEdges = arestas_brutas.map((edge, idx) => {
    const sourceNodeDetails = derivarDetalhesNo({ id: edge.de }, eventos);
    const targetNodeDetails = derivarDetalhesNo({ id: edge.para }, eventos);
    
    let color = 'var(--border)';
    let animated = false;
    let opacity = 1;
    let dash = undefined;
    let w = 1.4;
    
    if (edge.de === 'ds') {
      color = 'var(--focus)';
      dash = '2 4';
      w = 1.2;
    } else if (sourceNodeDetails.pulse || targetNodeDetails.pulse) {
      color = 'var(--blue)';
      animated = true;
      w = 1.6;
    } else if (targetNodeDetails.shape === 'green') {
      color = 'var(--border)';
    } else if (targetNodeDetails.shape === 'amber') {
      color = 'var(--amber)';
      opacity = 0.7;
      w = 1.6;
    } else if (targetNodeDetails.shape === 'red') {
      color = 'var(--red)';
    }

    return {
      id: `edge-${edge.de}-${edge.para}-${idx}`,
      source: edge.de,
      target: edge.para,
      color,
      animated,
      opacity,
      dash,
      w
    };
  });

  // Derivação do nó atualmente selecionado no Drawer
  const selectedNodeBruto = nos_brutos.find(n => n.id === selectedNodeId) || nos_brutos[0] || { id: 'planner', tipo: 'executor' };
  const selectedNodeDetails = derivarDetalhesNo(selectedNodeBruto, eventos);

  // Derivação do tipo do evento para filtragem na Timeline
  const getTipoEvento = (ev) => {
    const name = ev.evento || '';
    if (name.startsWith('portao.')) return 'gate';
    if (name === 'escalado' || name === 'decisao.pendente') return 'esc';
    if (name.startsWith('decisao.')) return 'fund';
    return 'exec';
  };

  // Filtragem dos eventos
  const filteredEvents = eventos.filter(ev => {
    if (filter === 'todos') return true;
    return getTipoEvento(ev) === filter;
  });

  // O grafo agrega TODAS as runs presentes no log — rótulo honesto com o N real
  const missoes = new Set();
  eventos.forEach(e => { if (e.missao) missoes.add(e.missao); if (e.run) missoes.add(e.run); });
  const runsLabel = missoes.size > 0 ? `todas as runs · ${missoes.size}` : '—';

  const liveShape = mode === 'live' ? 'sh blue pulse' : 'sh idle';
  const liveLabel = mode === 'live' ? 'AO VIVO' : 'PAUSADO';

  return (
    <div style={{
      height: 'calc(100vh - 52px)',
      margin: '-22px -24px -60px',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Estilos das animações e layouts locais */}
      <style>{`
        @keyframes mfrfp {
          0% { opacity: 0.6; transform: scale(1); }
          100% { opacity: 0; transform: scale(3); }
        }
        .mfrf-pw { position: relative; display: inline-flex; }
        .mfrf-pw::after {
          content: "";
          position: absolute;
          inset: -4px;
          border-radius: 50%;
          background: var(--blue);
          animation: mfrfp 2.1s ease-out infinite;
        }
        @keyframes mfrfflow {
          to { stroke-dashoffset: -20; }
        }
        .mfrf-flow {
          stroke-dasharray: 4 6;
          animation: mfrfflow 1.2s linear infinite;
        }
        .react-flow__attribution { display: none; }
        .react-flow__handle { opacity: 0; }
        
        .canvasarea {
          flex: 1;
          position: relative;
          overflow: hidden;
          background: var(--bg);
          background-image: radial-gradient(circle, var(--grap1) 1px, transparent 1px);
          background-size: 26px 26px;
        }
        
        .drawer {
          width: 346px;
          flex: none;
          border-left: 1px solid var(--border);
          background: var(--surface);
          display: flex;
          flex-direction: column;
          overflow: auto;
        }
        .term {
          background: var(--bg);
          border: 1px solid var(--border);
          border-radius: 2px;
          padding: 11px;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
          line-height: 1.6;
          color: var(--text);
          white-space: pre-wrap;
        }
        .lnk {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px;
          letter-spacing: .6px;
          text-transform: uppercase;
          color: var(--text2);
          cursor: pointer;
        }
        .lnk:hover { color: var(--text); }
        .tl { border-top: 1px solid var(--border); background: var(--surface); flex: none; }
        .evrow {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 7px 16px;
          border-bottom: 1px solid var(--border);
          cursor: pointer;
          font-family: 'IBM Plex Mono', monospace;
          font-size: 11px;
        }
        .evrow:hover { background: var(--surface2); }
      `}</style>

      {/* CANVAS TOOLBAR */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        flex: 'none'
      }}>
        <span className="num" style={{ cursor: 'pointer' }} onClick={() => window.location.hash = '/grafo'}>Grafo 2D</span>
        <span className="num" style={{ color: 'var(--text3)' }}>|</span>
        <span className="num" style={{ cursor: 'pointer', color: 'var(--text3)' }} onClick={() => window.location.hash = '/grafo3d'}>Grafo 3D</span>
        <span className="num" style={{ color: 'var(--text3)', marginLeft: 8 }}>· {runsLabel}</span>
        <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 2px' }} />
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: "'IBM Plex Mono',monospace", fontSize: 9, letterSpacing: '.5px', textTransform: 'uppercase', color: 'var(--text2)' }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', border: '1.4px solid var(--text2)', flex: 'none' }} />
          verificador · juízo LLM
        </div>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: "'IBM Plex Mono',monospace", fontSize: 9, letterSpacing: '.5px', textTransform: 'uppercase', color: 'var(--text2)' }}>
          <span style={{ width: 9, height: 9, background: 'var(--text2)', flex: 'none' }} />
          validador · determinístico
        </div>
        <div style={{ flex: 1 }} />
        <span className={`pill${mode === 'live' ? ' on' : ''}`} onClick={() => setMode('live')}>
          ● Ao vivo
        </span>
        <span className={`pill${mode === 'pausado' ? ' on' : ''}`} onClick={() => setMode('pausado')}>
          ⏸ pausar
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className={liveShape} />
          {liveLabel}
        </span>
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* WORLD / REACT FLOW */}
        <div className="canvasarea force-dark" style={{ overflow: 'hidden', padding: 0, background: 'var(--bg)' }}>
          <ReactFlow
            defaultNodes={flowNodes}
            defaultEdges={[]}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.12 }}
            minZoom={0.35}
            maxZoom={1.6}
            nodesConnectable={false}
            deleteKeyCode={null}
            proOptions={{ hideAttribution: true }}
            onNodeClick={(e, n) => setSelectedNodeId(n.id)}
          >
            <EdgeLayer edges={flowEdges} />
            <Background gap={26} size={1} style={{ '--rf-background-pattern-color': 'var(--grap1)' }} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        {/* DRAWER */}
        {selectedNodeDetails && (
          <div className="drawer">
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className="eyebrow">Drawer do nó · MICRO</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{selectedNodeDetails.role}</span>
            </div>
            <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Shape kind={selectedNodeDetails.shape} />
                  <span className="ndword" style={{ fontSize: 11, fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, textTransform: 'uppercase' }}>
                    {selectedNodeDetails.word}
                  </span>
                  <span className="ndtier" style={{ marginLeft: 'auto', fontFamily: "'IBM Plex Mono',monospace", fontSize: 9, color: 'var(--text3)' }}>
                    {selectedNodeDetails.paused ? 'pausado' : 'ativo'}
                  </span>
                </div>
                <div className="title" style={{ fontSize: 16, marginTop: 8 }}>{selectedNodeId}</div>
                {selectedNodeDetails.model && (
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', marginTop: 3 }}>
                    {selectedNodeDetails.model}
                  </div>
                )}
              </div>

              {selectedNodeDetails.paused && (
                <button 
                  className="btn" 
                  style={{ background: 'var(--amber)', borderColor: 'var(--amber)', color: 'var(--bg)', justifyContent: 'center' }}
                  onClick={() => window.location.hash = '/caixa'}
                >
                  → Decidir na Caixa do Fundador
                </button>
              )}

              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                  <span className="eyebrow">Janela ao vivo · nó em foco</span>
                  <span className="mono" style={{ fontSize: 9, color: 'var(--blue)' }}>stream ativa</span>
                </div>
                <div className="term force-dark">{selectedNodeDetails.live}</div>
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 }}>
                  <span className="eyebrow">Alterações · últimos arquivos</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {selectedNodeDetails.files && selectedNodeDetails.files.map((f, i) => (
                    <div key={i} style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: 'var(--text2)', padding: '5px 8px', border: '1px solid var(--border)', borderRadius: 2 }}>
                      {f.n}
                    </div>
                  ))}
                  {(!selectedNodeDetails.files || selectedNodeDetails.files.length === 0) && (
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>nenhum arquivo registrado</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* TIMELINE */}
      <div className="tl">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 16px', borderBottom: '1px solid var(--border)' }}>
          <span className="num">Timeline · {runsLabel}</span>
          <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 2px' }} />
          <span className={`pill${filter === 'todos' ? ' on' : ''}`} onClick={() => setFilter('todos')}>todos</span>
          <span className={`pill${filter === 'exec' ? ' on' : ''}`} onClick={() => setFilter('exec')}>execução</span>
          <span className={`pill${filter === 'gate' ? ' on' : ''}`} onClick={() => setFilter('gate')}>portões</span>
          <span className={`pill${filter === 'esc' ? ' on' : ''}`} onClick={() => setFilter('esc')}>escalada</span>
          <span className={`pill${filter === 'fund' ? ' on' : ''}`} onClick={() => setFilter('fund')}>fundador</span>
          <div style={{ flex: 1 }} />
          <span className="lnk" onClick={() => setTlOpen(!tlOpen)}>{tlOpen ? 'recolher −' : 'expandir +'}</span>
        </div>
        {tlOpen && (
          <div style={{ maxHeight: 172, overflow: 'auto' }}>
            {filteredEvents.map((e, idx) => {
              const hasMotivo = !!e.motivo;
              const showMotivo = tlExpandId === e.id;
              const motivoColor = e.dot === 'sh red' ? 'var(--red)' : 'var(--green)';
              const motivoLabel = e.dot === 'vsh' ? 'validador · resultado objetivo' : (e.dot === 'sh red' ? 'motivo · texto do verificador' : 'detalhe');
              const expLabel = showMotivo ? '− fechar' : '⊕ motivo';
              
              let dotCls = 'sh idle';
              if (e.evento === 'portao.aprovado' || e.evento === 'paralelo.concluido' || e.evento === 'executor.respondeu') dotCls = 'sh green';
              else if (e.evento === 'portao.reprovado' || e.evento === 'executor.erro' || e.evento === 'modelo.falha') dotCls = 'sh red';
              else if (e.evento === 'executor.chamado') dotCls = 'sh blue';
              else if (e.evento === 'escalado' || e.evento === 'decisao.pendente') dotCls = 'sh amber';
              
              return (
                <div key={e.id || idx}>
                  <div className="evrow" onClick={() => hasMotivo && setTlExpandId(showMotivo ? null : e.id)}>
                    <span className="mono" style={{ color: 'var(--text3)', width: 42, flex: 'none' }}>
                      {typeof e.t === 'number' ? e.t.toFixed(3) : e.t}s
                    </span>
                    <span className={dotCls} />
                    <span style={{ color: 'var(--text2)' }}>
                      {e.evento} {e.executor ? `· ${e.executor}` : ''} {e.portao ? `· ${e.portao}` : ''} {e.modelo ? `(${e.modelo})` : ''}
                    </span>
                    {hasMotivo && (
                      <span className="lnk" style={{ marginLeft: 'auto' }}>{expLabel}</span>
                    )}
                  </div>
                  {showMotivo && (
                    <div style={{ padding: '10px 16px 12px 68px', borderBottom: '1px solid var(--border)', background: 'var(--surface2)' }}>
                      <span className="eyebrow" style={{ color: motivoColor }}>{motivoLabel}</span>
                      <div className="mono" style={{ fontSize: '11.5px', color: 'var(--text)', marginTop: 5, lineHeight: 1.6 }}>
                        "{e.motivo}"
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
