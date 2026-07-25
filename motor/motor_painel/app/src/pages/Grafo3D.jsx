import { useState, useEffect, useRef, useMemo } from 'react';
import { usePoll, fetchDados, fetchRuns, getMissaoAtiva } from '../api.js';

/* Lê um token de cor do tema ativo (theme.js injeta as vars em :root/.mf-root). */
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* Cor por tipo de nó — sempre resolvida na hora, do tema ativo. */
const TIPO_VAR = {
  nucleo: '--blue',
  executor: '--text',
  subagente: '--green',
  portao: '--amber',
  decisor: '--text3',
};

/* Rotulo legivel por tipo. A cor vem de TIPO_VAR, nunca repetida a mao. */
const LEGENDA = [
  ['nucleo', 'núcleo'],
  ['executor', 'executor'],
  ['subagente', 'subagente'],
  ['portao', 'portão'],
  ['decisor', 'decisor'],
];

const colorOf = (n) => {
  if (n.hot === 'gate') return cssVar('--amber');
  return cssVar(TIPO_VAR[n.tipo] || '--text3');
};

export default function Grafo3D() {
  const { data: runs } = usePoll(fetchRuns);
  const { data: fullData } = usePoll(fetchDados);
  const { data: missaoAtiva } = usePoll(getMissaoAtiva);

  const stageRef = useRef(null);
  const graphRef = useRef(null); // Armazena a instância 3D estável

  // Refs persistentes para manter a referência de objeto e coordenadas físicas (x, y, z) entre atualizações
  const nodesRef = useRef([]);
  const linksRef = useRef([]);
  const prevDataStrRef = useRef(''); // Guarda a string estrutural do grafo anterior para evitar updates redundantes

  // Objetos de cena que precisam recolorir quando o tema troca
  const dustRef = useRef(null);
  const fillLightRef = useRef(null);

  const [selectedNode, setSelectedNode] = useState(null);
  const [paused, setPaused] = useState(false);
  const [flow, setFlow] = useState(true);
  const [layer, setLayer] = useState('full');
  const [linkOp, setLinkOp] = useState(0.35);
  const [themeTick, setThemeTick] = useState(0);

  const [scriptsLoaded, setScriptsLoaded] = useState(false);
  const [erroScript, setErroScript] = useState(null);

  /* Carrega three.js e 3d-force-graph da CDN.
     Sao as unicas dependencias do painel que nao vivem no package.json: sem
     rede, esta tela nao abre. Antes so havia onload — se a CDN falhasse, a
     Promise nunca resolvia e a tela ficava preta e muda para sempre. Agora
     onerror e timeout viram mensagem na tela. */
  useEffect(() => {
    let active = true;

    const carregar = (src) => new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = src;
      el.async = true;
      const limite = setTimeout(() => reject(new Error(`tempo esgotado ao buscar ${src}`)), 15000);
      el.onload = () => { clearTimeout(limite); resolve(); };
      el.onerror = () => { clearTimeout(limite); reject(new Error(`falha ao buscar ${src}`)); };
      document.body.appendChild(el);
    });

    const loadScripts = async () => {
      try {
        if (!window.THREE) await carregar('https://unpkg.com/three@0.160.0/build/three.min.js');
        if (!window.ForceGraph3D) await carregar('https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js');
        if (active) setScriptsLoaded(true);
      } catch (e) {
        if (active) setErroScript(e.message);
      }
    };

    loadScripts();

    return () => {
      active = false;
    };
  }, []);

  /* Reagir a troca de tema.
     Antes isto observava o atributo data-theme do .mf-root, o que so pega
     troca de MODO (claro/escuro). Trocar de TEMA no mesmo modo (kortex ->
     gemini) reescreve as variaveis CSS sem mexer no atributo, entao a cena 3D
     ficava com as cores do tema anterior ate recarregar a pagina.
     applyTheme() emite mf-theme-applied em toda aplicacao — modo e tema. */
  useEffect(() => {
    const recolorir = () => setThemeTick((t) => t + 1);
    document.addEventListener('mf-theme-applied', recolorir);
    return () => document.removeEventListener('mf-theme-applied', recolorir);
  }, []);

  // Grafo real derivado de /dados: nós de data.nos, arestas de data.arestas,
  // estado por nó dos eventos do log. Runs ativas/custo vêm de /dados/runs.
  const rawGraphData = useMemo(() => {
    const nosBrutos = fullData?.nos || [];
    const arestasBrutas = fullData?.arestas || [];
    const eventos = fullData?.eventos || [];

    const activeRuns = runs ? runs.filter((r) => r.estado === 'ativa').length : 0;
    const totalCost = runs ? runs.reduce((acc, r) => acc + (r.custo || 0), 0) : 0;

    // Grau por nó (dimensiona a esfera)
    const grau = {};
    arestasBrutas.forEach((a) => {
      grau[a.de] = (grau[a.de] || 0) + 1;
      grau[a.para] = (grau[a.para] || 0) + 1;
    });

    // Último estado conhecido por nó, derivado dos eventos reais
    const estado = {};
    eventos.forEach((ev) => {
      const alvo = ev.executor || ev.portao ||
        (((ev.evento === 'escalado' && ev.para === 'fundador') || (ev.evento || '').startsWith('decisao')) ? 'fundador' : null);
      if (!alvo) return;
      switch (ev.evento) {
        case 'executor.chamado': estado[alvo] = { status: 'executando', cor: 'var(--blue)', hot: 'live' }; break;
        case 'executor.respondeu': estado[alvo] = { status: 'respondeu', cor: 'var(--green)', hot: '' }; break;
        case 'executor.erro':
        case 'modelo.falha': estado[alvo] = { status: 'falhou', cor: 'var(--red)', hot: '' }; break;
        case 'portao.aprovado': estado[alvo] = { status: 'aprovado', cor: 'var(--green)', hot: '' }; break;
        case 'portao.reprovado': estado[alvo] = { status: 'reprovado', cor: 'var(--red)', hot: 'gate' }; break;
        case 'escalado':
        case 'decisao.pendente': estado[alvo] = { status: 'aguardando decisão', cor: 'var(--amber)', hot: 'gate' }; break;
        case 'decisao.fundador': estado[alvo] = { status: 'decidiu', cor: 'var(--green)', hot: '' }; break;
        default: break;
      }
    });

    const nodes = nosBrutos.map((no) => {
      const st = estado[no.id];
      const g = grau[no.id] || 0;
      const nEv = eventos.filter((ev) => ev.executor === no.id || ev.portao === no.id).length;
      return {
        id: no.id,
        nome: no.id,
        tipo: no.tipo,
        info: no.tipo === 'nucleo'
          ? `${activeRuns} runs ativas · US$ ${totalCost.toFixed(2)} · ${g} conexões`
          : `${g} conexões · ${nEv} eventos`,
        status: st ? st.status : 'sem eventos',
        stColor: st ? st.cor : 'var(--text3)',
        val: 4 + g * 2,
        hot: st ? st.hot : '',
      };
    });

    const liveIds = new Set(nodes.filter((n) => n.hot === 'live').map((n) => n.id));
    const links = arestasBrutas.map((a) => ({
      source: a.de,
      target: a.para,
      live: liveIds.has(a.de) || liveIds.has(a.para),
    }));

    return { nodes, links };
  }, [runs, fullData]);

  // Constrói o objeto 3D de um nó com as cores do tema ativo
  const buildNodeObject = (n) => {
    if (n.__threeObj) return n.__threeObj;
    const THREE = window.THREE;

    const labelSprite = (text, colorStr) => {
      const px = 22, pad = 10;
      const mc = document.createElement('canvas');
      const mx = mc.getContext('2d');
      mx.font = `600 ${px}px "IBM Plex Mono", monospace`;
      const w = Math.ceil(mx.measureText(text.toUpperCase()).width) + pad * 2;
      const h = px + pad * 2;
      mc.width = w * 2;
      mc.height = h * 2;
      mx.scale(2, 2);
      mx.font = `600 ${px}px "IBM Plex Mono", monospace`;
      mx.globalAlpha = 0.78;
      mx.fillStyle = cssVar('--surface');
      mx.fillRect(0, 0, w, h);
      mx.globalAlpha = 1;
      mx.strokeStyle = cssVar('--border');
      mx.lineWidth = 1;
      mx.strokeRect(0.5, 0.5, w - 1, h - 1);
      mx.fillStyle = colorStr;
      mx.textBaseline = 'middle';
      mx.fillText(text.toUpperCase(), pad, h / 2 + 1);
      const tex = new THREE.CanvasTexture(mc);
      tex.anisotropy = 8;
      const m = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
      const s = new THREE.Sprite(m);
      const k = 0.10;
      s.scale.set(w * k, h * k, 1);
      return s;
    };

    const grp = new THREE.Group();
    const col = colorOf(n);
    const r = Math.cbrt(n.val) * (n.hot ? 2.2 : 1.7);
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(r, 12, 12), // Reduzido para melhorar ainda mais o frame rate
      new THREE.MeshStandardMaterial({ color: new THREE.Color(col), roughness: 0.35, metalness: 0.15 })
    );
    grp.add(core);
    const lb = labelSprite(n.nome, n.hot ? col : cssVar('--text3'));
    lb.position.set(0, -r - 2.6, 0);
    grp.add(lb);

    n.__threeObj = grp;
    return grp;
  };

  // Inicializa o Grafo 3D UMA ÚNICA VEZ
  useEffect(() => {
    if (!scriptsLoaded || !stageRef.current || !window.ForceGraph3D || !window.THREE) return;

    const THREE = window.THREE;

    const graph = window.ForceGraph3D()(stageRef.current)
      .width(stageRef.current.clientWidth)
      .height(stageRef.current.clientHeight)
      .backgroundColor(cssVar('--bg'))
      .showNavInfo(false)
      .nodeLabel(n => `<div style="font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.5px;color:var(--text);background:var(--surface);border:1px solid var(--border);padding:3px 7px;border-radius:2px">${n.nome} · ${n.tipo}</div>`)
      .nodeThreeObject(buildNodeObject)
      .linkColor(l => l.live ? cssVar('--blue') : cssVar('--border'))
      .linkOpacity(linkOp)
      .linkWidth(0)
      .linkDirectionalParticles(l => l.live && flow ? 3 : 0)
      .linkDirectionalParticleSpeed(0.004)
      .linkDirectionalParticleWidth(1.4)
      .linkDirectionalParticleColor(() => cssVar('--amber'))
      .onNodeClick(n => setSelectedNode(n))
      .onBackgroundClick(() => setSelectedNode(null));

    // Congela a física depois que o layout assenta, para não recalcular gravidade
    // e atração para sempre e travar a thread principal.
    // O limite era 35 ticks / 1.2s, herdado de quando o grafo tinha 1 nó. Com
    // 15-20 nós de uma missão real isso congela antes de separar o aglomerado —
    // economiza CPU entregando layout errado. 200 ticks dão tempo de assentar e
    // ainda param muito antes de virar custo permanente.
    graph.d3Force('charge').strength(-160);
    graph.d3AlphaDecay(0.0228); // padrão do d3; 0.04 cortava o layout junto com o tempo
    graph.cooldownTicks(200);
    graph.cooldownTime(5000);

    graph.renderer().setPixelRatio(1); // Travar pixel ratio em 1 para poupar a GPU
    graph.renderer().shadowMap.enabled = false; // Desativar sombras WebGL pesadas

    // Luzes: key/ambient neutras (brancas), fill com o azul do tema
    const sc = graph.scene();
    const key = new THREE.DirectionalLight(new THREE.Color(1, 1, 1), 1.4);
    key.position.set(120, 180, 160);
    sc.add(key);

    const fill = new THREE.DirectionalLight(new THREE.Color(cssVar('--blue')), 0.35);
    fill.position.set(-140, -80, -120);
    sc.add(fill);
    fillLightRef.current = fill;

    sc.add(new THREE.AmbientLight(new THREE.Color(1, 1, 1), 0.28));

    // Névoa na cor do fundo do tema
    sc.fog = new THREE.FogExp2(new THREE.Color(cssVar('--bg')), 0.0016);

    // Poeira estelar otimizada
    const particleCount = 100;
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      const radius = 400 + Math.random() * 600;
      const t = Math.random() * Math.PI * 2;
      const p = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = radius * Math.sin(p) * Math.cos(t);
      positions[i * 3 + 1] = radius * Math.sin(p) * Math.sin(t);
      positions[i * 3 + 2] = radius * Math.cos(p);
    }
    const pg = new THREE.BufferGeometry();
    pg.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const dust = new THREE.Points(pg, new THREE.PointsMaterial({ color: new THREE.Color(cssVar('--text3')), size: 1.6, sizeAttenuation: true, transparent: true, opacity: 0.5, depthWrite: false }));
    sc.add(dust);
    dustRef.current = dust;

    // Salvar referência da instância
    graphRef.current = graph;

    const handleResize = () => {
      if (stageRef.current) {
        graph.width(stageRef.current.clientWidth).height(stageRef.current.clientHeight);
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      graph.pauseAnimation();
      graphRef.current = null;
      dustRef.current = null;
      fillLightRef.current = null;
    };
  }, [scriptsLoaded]);

  // Recolorir toda a cena quando o tema (data-theme) troca
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.backgroundColor(cssVar('--bg'));
    graph.linkColor(l => l.live ? cssVar('--blue') : cssVar('--border'));
    graph.linkDirectionalParticleColor(() => cssVar('--amber'));
    const sc = graph.scene();
    if (sc.fog) sc.fog.color.set(cssVar('--bg'));
    if (dustRef.current) dustRef.current.material.color.set(cssVar('--text3'));
    if (fillLightRef.current) fillLightRef.current.color.set(cssVar('--blue'));
    // Reconstruir esferas + labels com as novas cores.
    // Limpar o cache e reatribuir o accessor nao basta: o 3d-force-graph nao
    // regera objeto de no ja montado so porque o accessor mudou. Sem o
    // refresh() o fundo trocava de cor e as esferas ficavam com a cor do tema
    // anterior — medido comparando o pixel da esfera entre dois temas.
    nodesRef.current.forEach((n) => { delete n.__threeObj; });
    graph.nodeThreeObject((n) => buildNodeObject(n));
    graph.refresh();
  }, [themeTick]);

  // Atualização reativa de dados com prevenção de reaquecimento físico redundante (flicker/jitter)
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    // 1. Verificar se a estrutura geométrica crítica (quantidade, IDs e conexões) mudou
    const dataStr = JSON.stringify({
      nodes: rawGraphData.nodes.map(n => ({ id: n.id, hot: n.hot })),
      links: rawGraphData.links.map(l => ({ source: l.source, target: l.target, live: l.live })),
      layer
    });

    const isSameStructure = dataStr === prevDataStrRef.current;

    // 2. Mesclar propriedades dos nós na referência persistente
    const nextNodes = rawGraphData.nodes.map(rawNode => {
      const existing = nodesRef.current.find(n => n.id === rawNode.id);
      if (existing) {
        if (existing.hot !== rawNode.hot) delete existing.__threeObj; // estado mudou → recolorir
        Object.assign(existing, rawNode);
        return existing;
      }
      return rawNode;
    });
    nodesRef.current = nextNodes;

    const nextLinks = rawGraphData.links.map(rawLink => {
      const existing = linksRef.current.find(l => {
        const sId = l.source.id ?? l.source;
        const tId = l.target.id ?? l.target;
        const rawSId = rawLink.source.id ?? rawLink.source;
        const rawTId = rawLink.target.id ?? rawLink.target;
        return sId === rawSId && tId === rawTId;
      });

      if (existing) {
        Object.assign(existing, rawLink);
        return existing;
      }
      return rawLink;
    });
    linksRef.current = nextLinks;

    if (isSameStructure && prevDataStrRef.current !== '') {
      return;
    }

    prevDataStrRef.current = dataStr;

    // 3. Aplicar filtragem de camadas — macro = núcleo + portões + decisores
    let filteredNodes = nodesRef.current;
    let filteredLinks = linksRef.current;

    if (layer === 'macro') {
      const keep = new Set(nodesRef.current.filter(n => n.tipo === 'nucleo' || n.tipo === 'portao' || n.tipo === 'decisor').map(n => n.id));
      filteredNodes = nodesRef.current.filter(n => keep.has(n.id));
      filteredLinks = linksRef.current.filter(l => {
        const sId = l.source.id ?? l.source;
        const tId = l.target.id ?? l.target;
        return keep.has(sId) && keep.has(tId);
      });
    }

    // Injetar dados
    graph.graphData({ nodes: filteredNodes, links: filteredLinks });
  }, [rawGraphData, layer]);

  // Efeitos secundários estáveis
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.linkDirectionalParticles(l => l.live && flow ? 3 : 0);
  }, [flow]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.linkOpacity(linkOp);
  }, [linkOp]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    if (paused) {
      graph.pauseAnimation();
    } else {
      graph.resumeAnimation();
    }
  }, [paused]);

  // Obter detalhes estáveis para o Drawer sem afetar a simulação 3D
  const selectedNodeDetails = useMemo(() => {
    if (!selectedNode) return null;
    return nodesRef.current.find(n => n.id === selectedNode.id) || selectedNode;
  }, [selectedNode, rawGraphData]);

  return (
    <div style={{ position: 'absolute', inset: 0, background: 'var(--bg)', color: 'var(--text)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="bk" style={{ position: 'absolute', width: 14, height: 14, borderColor: 'var(--focus)', borderStyle: 'solid', borderWidth: 0, left: 12, top: 12, borderLeftWidth: 1, borderTopWidth: 1, zIndex: 4, pointerEvents: 'none' }}></div>
      <div className="bk" style={{ position: 'absolute', width: 14, height: 14, borderColor: 'var(--focus)', borderStyle: 'solid', borderWidth: 0, right: 12, top: 12, borderRightWidth: 1, borderTopWidth: 1, zIndex: 4, pointerEvents: 'none' }}></div>
      <div className="bk" style={{ position: 'absolute', width: 14, height: 14, borderColor: 'var(--focus)', borderStyle: 'solid', borderWidth: 0, left: 12, bottom: 12, borderLeftWidth: 1, borderBottomWidth: 1, zIndex: 4, pointerEvents: 'none' }}></div>
      <div className="bk" style={{ position: 'absolute', width: 14, height: 14, borderColor: 'var(--focus)', borderStyle: 'solid', borderWidth: 0, right: 12, bottom: 12, borderRightWidth: 1, borderBottomWidth: 1, zIndex: 4, pointerEvents: 'none' }}></div>

      {/* Top HUD */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, display: 'flex', alignItems: 'center', gap: 14, padding: '12px 22px', zIndex: 3, pointerEvents: 'none' }}>
        <span className="pill" style={{ pointerEvents: 'auto' }} onClick={() => { window.location.hash = '/grafo'; }}>← 2D</span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span className="eyebrow" style={{ color: 'var(--text2)' }}>
            MAPA GERAL · 3D · {missaoAtiva?.ativa ? 'AO VIVO' : 'OCIOSO'}
          </span>
          <span className="title" style={{ fontSize: 14 }}>
            {runs ? `${runs.length} runs catalogados` : 'resumo orbital carregando...'}
          </span>
        </div>
        <div style={{ flex: 1 }}></div>
        <div style={{ display: 'flex', gap: 10 }}>
          {/* Derivada de TIPO_VAR: a legenda nao pode divergir da cor do no. */}
          {LEGENDA.map(([tipo, rotulo]) => (
            <span key={tipo} className="lg" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: "'IBM Plex Mono',monospace", fontSize: '9.5px', textTransform: 'uppercase', color: 'var(--text2)' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: `var(${TIPO_VAR[tipo]})` }}></span>{rotulo}
            </span>
          ))}
        </div>
      </div>

      {/* 3D Canvas stage */}
      <div ref={stageRef} style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}></div>

      {(erroScript || !scriptsLoaded) && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 5, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, padding: 24, textAlign: 'center' }}>
          {erroScript ? (
            <>
              <div className="title" style={{ fontSize: 15, color: 'var(--red)' }}>
                Motor 3D não carregou
              </div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', maxWidth: 420, lineHeight: 1.6 }}>
                Esta tela busca three.js e 3d-force-graph em unpkg.com a cada visita —
                são as únicas dependências do painel que não estão instaladas localmente.
                Sem rede, ela não abre.
              </div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{erroScript}</div>
              <span className="pill" style={{ marginTop: 6 }} onClick={() => { window.location.hash = '/grafo'; }}>
                ver em 2D
              </span>
            </>
          ) : (
            <span className="mono" style={{ fontSize: 11, color: 'var(--text3)' }}>Carregando motor 3D…</span>
          )}
        </div>
      )}

      {/* Selected Node Drawer */}
      {selectedNodeDetails && (
        <div style={{ position: 'absolute', right: 20, top: 64, width: 260, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 2, padding: 13, zIndex: 4, backdropFilter: 'blur(6px)', display: 'flex', flexDirection: 'column', gap: 7 }}>
          <span className="eyebrow" style={{ color: 'var(--text3)' }}>{selectedNodeDetails.tipo}</span>
          <span className="title" style={{ fontSize: 16 }}>{selectedNodeDetails.nome}</span>
          <span className="mono" style={{ fontSize: '10.5px', color: 'var(--text2)', lineHeight: 1.5 }}>{selectedNodeDetails.info}</span>
          <span className="mono" style={{ fontSize: 10, color: selectedNodeDetails.stColor }}>{selectedNodeDetails.status}</span>
          <span className="pill" style={{ alignSelf: 'flex-start', marginTop: 4 }} onClick={() => setSelectedNode(null)}>fechar</span>
        </div>
      )}

      {/* Bottom HUD */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, display: 'flex', alignItems: 'center', gap: 14, padding: '12px 22px', zIndex: 3, pointerEvents: 'none' }}>
        <span className="eyebrow" style={{ pointerEvents: 'auto' }}>camada</span>
        <span className={`pill${layer === 'macro' ? ' on' : ''}`} style={{ pointerEvents: 'auto' }} onClick={() => setLayer('macro')}>macro</span>
        <span className={`pill${layer === 'full' ? ' on' : ''}`} style={{ pointerEvents: 'auto' }} onClick={() => setLayer('full')}>completo</span>
        <div style={{ width: 1, height: 16, background: 'var(--border)' }}></div>
        {/* pauseAnimation() para o loop de render inteiro, nao so a fisica — com
            ele ligado a camera tambem congela. O rotulo agora diz isso. */}
        <span className={`pill${paused ? ' on' : ''}`} style={{ pointerEvents: 'auto' }} onClick={() => setPaused(!paused)}>{paused ? '▶ retomar render' : '⏸ pausar render'}</span>
        <span className={`pill${flow ? ' on' : ''}`} style={{ pointerEvents: 'auto' }} onClick={() => setFlow(!flow)}>⚡ fluxo</span>
        <div style={{ width: 1, height: 16, background: 'var(--border)' }}></div>
        <span className="eyebrow" style={{ pointerEvents: 'auto' }}>arestas</span>
        <input type="range" min="0.05" max="0.6" step="0.05" value={linkOp} onChange={e => setLinkOp(parseFloat(e.target.value))} style={{ pointerEvents: 'auto' }} />
        <div style={{ flex: 1 }}></div>
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>
          nós <b style={{ color: 'var(--text)' }}>{nodesRef.current.length}</b> · arestas <b style={{ color: 'var(--text)' }}>{linksRef.current.length}</b>
        </span>
      </div>
    </div>
  );
}
