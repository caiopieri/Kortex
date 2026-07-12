import { useState } from 'react';
import { usePoll, getAgents } from '../api.js';

// stylesheet injected for agents component
const STYLES = `
  .badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    background: var(--accent);
    color: #0B0C0E;
    border-radius: 2px;
    padding: 1px 6px;
  }
  /* ---- procedural bust ---- */
  .bust {
    position: relative;
    width: 96px;
    height: 74px;
    margin: 0 auto;
  }
  .bust .ring {
    position: absolute;
    left: 50%;
    top: -6px;
    transform: translateX(-50%);
    width: 60px;
    height: 60px;
    border-radius: 50%;
    border: 2px solid var(--text3);
  }
  .bust.big {
    width: 150px;
    height: 150px;
  }
  .bust.big .ring {
    width: 120px;
    height: 120px;
    top: -4px;
  }
  .ring.rblue {
    border-color: var(--blue);
    box-shadow: 0 0 16px -3px var(--blue);
  }
  .ring.rgreen {
    border-color: var(--green);
    box-shadow: 0 0 16px -3px var(--green);
  }
  .ring.ramber {
    border-color: var(--amber);
    box-shadow: 0 0 16px -3px var(--amber);
  }
  .ring.rred {
    border-color: var(--red);
    box-shadow: 0 0 16px -3px var(--red);
  }
  .ring.ridle {
    border-color: var(--focus);
  }
  .shoulders {
    position: absolute;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 96px;
    height: 44px;
    background: linear-gradient(160deg, var(--grap1), var(--grap2));
    border: 1px solid var(--rim);
    border-bottom: none;
    border-radius: 48px 48px 4px 4px;
  }
  .bust.big .shoulders {
    width: 150px;
    height: 72px;
    border-radius: 74px 74px 6px 6px;
  }
  .head {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 48px;
    height: 56px;
    background: linear-gradient(155deg, var(--grap1), var(--grap2));
    border: 1px solid var(--rim);
    border-radius: 20px 20px 18px 18px;
    overflow: hidden;
  }
  .bust.big .head {
    width: 76px;
    height: 88px;
    border-radius: 32px 32px 28px 28px;
    top: 2px;
  }
  .head.hv1 {
    border-radius: 14px 14px 20px 20px;
  }
  .head.hv2 {
    border-radius: 26px 26px 14px 14px;
  }
  .visor {
    position: absolute;
    top: 44%;
    left: 16%;
    right: 16%;
    height: 4px;
    border-radius: 2px;
    background: var(--accent);
    box-shadow: 0 0 8px 0 var(--accent);
  }
  .bust.big .visor {
    height: 6px;
    top: 42%;
  }
  .rimlight {
    position: absolute;
    top: 14%;
    left: 8%;
    width: 2px;
    height: 56%;
    background: linear-gradient(var(--rim), transparent);
    opacity: .7;
  }
  .emblem {
    position: absolute;
    bottom: 5px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 8px;
    letter-spacing: 1px;
    color: var(--text3);
  }
  .bust.big .emblem {
    font-size: 10px;
    bottom: 9px;
  }
  .acard {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 44px 14px 14px;
    cursor: pointer;
    transition: transform .18s ease, border-color .18s ease;
    overflow: visible;
  }
  .acard:hover {
    transform: translateY(-3px);
    border-color: var(--focus);
  }
  .acard .bustwrap {
    position: absolute;
    top: -30px;
    left: 0;
    right: 0;
  }
  .stbadge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--text2);
  }
  .certtag {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    letter-spacing: .8px;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 2px;
    border: 1px solid var(--border);
  }
  .cert-ok {
    color: var(--green);
    border-color: rgba(48, 164, 108, 0.4);
  }
  .cert-shadow {
    color: var(--text2);
    border-color: var(--border);
  }
  .cert-bad {
    color: var(--red);
    border-color: rgba(229, 72, 77, 0.4);
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
  }
  .step {
    position: relative;
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 14px 13px;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .provdot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
`;

const DEFAULT_AGENTS = {
  llama: {
    id: 'llama',
    name: 'Órion', model: 'llama-3.3-70b', short: 'Órion', provider: 'NVIDIA · free', emblem: 'NV', hv: '',
    ring: 'rblue', sh: 'sh blue', activity: 'pesquisando', role: 'pesquisador', tierLabel: 'tier simples',
    cert: 'ok', certShort: 'CERT', certLong: 'CERTIFICADO', certcls: 'cert-ok',
    certNote: 'Aprovado pelo Curador para papéis de pesquisa em tier simples.',
    rung: 'Free', rungNote: 'degrau de entrada · NVIDIA NIM',
    hf: 'meta-llama/Llama-3.3-70B ↗', cred: 'configurada', credColor: 'var(--green)',
    finetune: '1 em andamento', sample: 'n=214',
    doing: [{ sh: 'sh blue', node: 'pesquisa-alfa', where: 'csv→json · ao vivo' }, { sh: 'sh green', node: 'pesquisa-beta', where: 'pesquisa-receita · concluído' }],
    chatMsg: 'Estou varrendo o CSV de origem — 3 colunas com encoding inconsistente. Sigo normalizando?',
    metrics: [
      { label: 'aprov. 1ª tent.', val: '61%', color: 'var(--text)', sub: 'média' },
      { label: 'lat. mediana', val: '1.8s', color: 'var(--text)', sub: 'rápido' },
      { label: 'lat. p90', val: '5.2s', color: 'var(--text)', sub: '' },
      { label: 'taxa erro', val: '9%', color: 'var(--amber)', sub: '' },
      { label: 'converg. escal.', val: '88%', color: 'var(--green)', sub: 'pós-escalada' },
    ],
    reasons: [{ pct: '41%', text: 'raciocínio insuficiente em casos-limite; entrega parcial quando o input é ambíguo.' }, { pct: '22%', text: 'formato de saída fora da rubrica (JSON não-estrito).' }],
  },
  qwen: {
    id: 'qwen',
    name: 'Vesta', model: 'qwen-2.5-72b', short: 'Vesta', provider: 'NVIDIA · free', emblem: 'NV', hv: 'hv1',
    ring: 'rblue', sh: 'sh blue', activity: 'redigindo', role: 'redator', tierLabel: 'tier simples',
    cert: 'ok', certShort: 'CERT', certLong: 'CERTIFICADO', certcls: 'cert-ok',
    certNote: 'Sólido em redação e transformação de texto em tier simples.',
    rung: 'Free', rungNote: 'degrau de entrada · NVIDIA NIM',
    hf: 'Qwen/Qwen2.5-72B ↗', cred: 'configurada', credColor: 'var(--green)',
    finetune: 'nenhum', sample: 'n=178',
    doing: [{ sh: 'sh blue', node: 'redator', where: 'pesquisa-receita · ao vivo' }],
    chatMsg: 'Rascunho da seção de metodologia pronto. Quer tom mais técnico ou mais direto?',
    metrics: [
      { label: 'aprov. 1ª tent.', val: '68%', color: 'var(--text)', sub: 'média' },
      { label: 'lat. mediana', val: '2.1s', color: 'var(--text)', sub: '' },
      { label: 'lat. p90', val: '6.0s', color: 'var(--text)', sub: '' },
      { label: 'taxa erro', val: '5%', color: 'var(--text)', sub: '' },
      { label: 'converg. escal.', val: '90%', color: 'var(--green)', sub: '' },
    ],
    reasons: [{ pct: '33%', text: 'perde nuance em textos longos; repete estrutura.' }, { pct: '18%', text: 'citações imprecisas quando a fonte é densa.' }],
  },
  deepseek: {
    id: 'deepseek',
    name: 'Ceres', model: 'deepseek-v3', short: 'Ceres', provider: 'NVIDIA · free', emblem: 'NV', hv: 'hv2',
    ring: 'rgreen', sh: 'sh green', activity: 'concluído', role: 'transformador', tierLabel: 'tier média',
    cert: 'ok', certShort: 'CERT', certLong: 'CERTIFICADO', certcls: 'cert-ok',
    certNote: 'Forte em transformação estruturada de dados.',
    rung: 'Free', rungNote: 'degrau de entrada · NVIDIA NIM',
    hf: 'deepseek-ai/DeepSeek-V3 ↗', cred: 'configurada', credColor: 'var(--green)',
    finetune: 'nenhum', sample: 'n=142',
    doing: [{ sh: 'sh green', node: 'transformador', where: 'csv→json · concluído há 2min' }],
    chatMsg: 'Transformação CSV→JSON fechada, 312 registros. Todos passaram na validação de schema.',
    metrics: [
      { label: 'aprov. 1ª tent.', val: '74%', color: 'var(--text)', sub: 'boa' },
      { label: 'lat. mediana', val: '2.6s', color: 'var(--text)', sub: '' },
      { label: 'lat. p90', val: '7.4s', color: 'var(--text)', sub: '' },
      { label: 'taxa erro', val: '4%', color: 'var(--text)', sub: '' },
      { label: 'converg. escal.', val: '92%', color: 'var(--green)', sub: '' },
    ],
    reasons: [{ pct: '28%', text: 'falha em schemas aninhados profundos.' }],
  },
  kimi: {
    id: 'kimi',
    name: 'Pallas', model: 'kimi-k2', short: 'Pallas', provider: 'Moonshot · free', emblem: 'MS', hv: 'hv1',
    ring: 'ridle', sh: 'sh idle', activity: '429 · aguardando cota', role: 'arquiteto', tierLabel: 'tier média',
    cert: 'shadow', certShort: 'SOMBRA', certLong: 'EM SOMBRA', certcls: 'cert-shadow',
    certNote: 'Em avaliação: o Curador ainda acumula evidência antes de certificar ou reprovar.',
    rung: 'Free+', rungNote: 'candidato a tier média',
    hf: 'moonshotai/Kimi-K2 ↗', cred: 'configurada', credColor: 'var(--green)',
    finetune: 'nenhum', sample: 'n=38 (baixa)',
    doing: [{ sh: 'sh idle', node: '— sem nó ativo', where: 'provedor em 429' }],
    chatMsg: 'Estou throttled pelo provedor (429). O motor me reroteou para DeepSeek nesta rodada.',
    metrics: [
      { label: 'aprov. 1ª tent.', val: '71%', color: 'var(--text2)', sub: 'amostra baixa' },
      { label: 'lat. mediana', val: '3.4s', color: 'var(--text2)', sub: '' },
      { label: 'lat. p90', val: '9.9s', color: 'var(--text2)', sub: '' },
      { label: 'taxa erro', val: '12%', color: 'var(--amber)', sub: 'ruído de dado' },
      { label: 'converg. escal.', val: 'n/d', color: 'var(--text3)', sub: 'sem amostra' },
    ],
    reasons: [{ pct: '—', text: 'amostra insuficiente para agregar motivos com confiança (n=38).' }],
  },
  codex: {
    id: 'codex',
    name: 'Hefesto', model: 'codex-mini', short: 'Hefesto', provider: 'OpenAI · pago', emblem: 'OAI', hv: '',
    ring: 'ramber', sh: 'sh amber', activity: 'aguardando decisão', role: 'qa_engineer · verifier', tierLabel: 'tier complexa',
    cert: 'ok', certShort: 'CERT', certLong: 'CERTIFICADO', certcls: 'cert-ok',
    certNote: 'Certificado como verificador; sua saída atual está num gate humano.',
    rung: 'Média', rungNote: 'degrau pago · escalada a partir do free',
    hf: 'n/d (proprietário)', cred: 'configurada', credColor: 'var(--green)',
    finetune: 'nenhum', sample: 'n=96',
    doing: [{ sh: 'sh amber', node: 'verifier:pesquisa-beta', where: 'gate cobertura → fundador' }],
    chatMsg: 'Reprovei o ciclo 1 da pesquisa-beta por cobertura. A tentativa 2 passou — aguardando você no gate.',
    metrics: [
      { label: 'aprov. 1ª tent.', val: '82%', color: 'var(--green)', sub: 'alta' },
      { label: 'lat. mediana', val: '4.2s', color: 'var(--text)', sub: '' },
      { label: 'lat. p90', val: '11.8s', color: 'var(--text)', sub: '' },
      { label: 'taxa erro', val: '6%', color: 'var(--text)', sub: '' },
      { label: 'converg. escal.', val: '94%', color: 'var(--green)', sub: '' },
    ],
    reasons: [{ pct: '19%', text: 'rigor excessivo: reprova por detalhes de estilo fora da rubrica.' }],
  },
  claude: {
    id: 'claude',
    name: 'Atena', model: 'claude-sonnet-4', short: 'Atena', provider: 'Anthropic · pago', emblem: 'ANT', hv: 'hv2',
    ring: 'ridle', sh: 'sh idle', activity: 'sem credencial', role: 'evaluator · verifier', tierLabel: 'tier complexa',
    cert: 'ok', certShort: 'CERT', certLong: 'CERTIFICADO', certcls: 'cert-ok',
    certNote: 'Certificado no topo, mas indisponível: falta a credencial do provedor.',
    rung: 'Topo', rungNote: 'verificador final · maior capacidade',
    hf: 'n/d (proprietário)', cred: 'NÃO configurada', credColor: 'var(--red)',
    finetune: 'nenhum', sample: 'n=61',
    doing: [{ sh: 'sh idle', node: '— indisponível', where: 'sem credencial · motor cai para Codex' }],
    chatMsg: 'Estou fora: o provedor não tem credencial configurada. O motor está usando Hefesto como verificador.',
    metrics: [
      { label: 'aprov. 1ª tent.', val: '91%', color: 'var(--green)', sub: 'topo' },
      { label: 'lat. mediana', val: '6.1s', color: 'var(--text)', sub: '' },
      { label: 'lat. p90', val: '14.0s', color: 'var(--text)', sub: '' },
      { label: 'taxa erro', val: '3%', color: 'var(--green)', sub: '' },
      { label: 'converg. escal.', val: '97%', color: 'var(--green)', sub: '' },
    ],
    reasons: [{ pct: '8%', text: 'raro; discordâncias de julgamento em rubricas subjetivas.' }],
  }
};

const AGENT_MAPPING = {
  llama: {
    roles: ['pesquisador', 'planner'],
    ids: ['pesquisa-alfa', 'pesquisa-beta', 'planner']
  },
  qwen: {
    roles: ['redator'],
    ids: ['redator']
  },
  deepseek: {
    roles: ['transformador', 'executor'],
    ids: ['transformador', 'especialista-docs']
  },
  kimi: {
    roles: ['arquiteto'],
    ids: ['arquiteto']
  },
  codex: {
    roles: ['qa_engineer', 'verifier', 'qa_engineer · verifier'],
    ids: ['especificador', 'verifier', 'qa_engineer']
  },
  claude: {
    roles: ['evaluator', 'verifier / evaluator', 'evaluator · verifier', 'synthesizer'],
    ids: ['global_evaluator', 'synthesizer']
  }
};

const getStatsForAgent = (agentKey, defaultAgent, apiAgents) => {
  let chamadas = 0;
  let falhas = 0;
  if (!apiAgents) return { chamadas, falhas };

  const mapping = AGENT_MAPPING[agentKey] || { roles: [], ids: [] };

  for (const a of apiAgents) {
    const id = a.id?.toLowerCase();
    const papel = a.papel?.toLowerCase();

    const matchesId = mapping.ids.some(mapId => id === mapId || id.includes(mapId));
    const matchesPapel = mapping.roles.some(mapRole => papel === mapRole || papel.includes(mapRole));

    if (matchesId || matchesPapel) {
      chamadas += a.chamadas || 0;
      falhas += a.falhas || 0;
    }
  }
  return { chamadas, falhas };
};

const LADDER = [
  { tier: 'tier simples', name: 'Free · NVIDIA', cost: '$0 / 1k', offset: '54px', models: ['llama-3.3-70b', 'qwen-2.5-72b', 'deepseek-v3'] },
  { tier: 'tier média (cand.)', name: 'Free+ · Moonshot', cost: '$0 / 1k · 429', offset: '36px', models: ['kimi-k2 (sombra)'] },
  { tier: 'tier complexa', name: 'Codex · OpenAI', cost: '$0.30 / 1k', offset: '18px', models: ['codex-mini'] },
  { tier: 'topo · verificador', name: 'Claude · Anthropic', cost: '$0.90 / 1k', offset: '0px', models: ['claude-sonnet-4'] },
];

const PRESETS = [
  { name: 'free-escalada', use: 'padrão / barato', map: 'tudo em free (NVIDIA); escala p/ Codex ao reprovar; verificador = Codex.' },
  { name: 'codex', use: 'código médio', map: 'executores free; qa_engineer + verifier = Codex.' },
  { name: 'claude', use: 'crítico / topo', map: 'verifier + evaluator = Claude; executores free ou Codex.' },
  { name: 'construcao', use: 'rota construção', map: 'arquiteto = Kimi/Codex; transformador = DeepSeek; verifier = Codex.' },
  { name: 'pesquisa-sintese', use: 'rota pesquisa', map: 'pesquisadores free em paralelo; synthesizer = Codex; gate cobertura humano.' },
];

const PROVIDERS = [
  { name: 'NVIDIA NIM', status: 'disponível', color: 'var(--green)', cred: 'sim', note: 'llama · qwen · deepseek' },
  { name: 'Moonshot (Kimi)', status: 'throttled · 429', color: 'var(--amber)', cred: 'sim', note: 'cota estourada; reroteando' },
  { name: 'OpenAI (Codex)', status: 'disponível', color: 'var(--green)', cred: 'sim', note: 'tier pago médio' },
  { name: 'Anthropic (Claude)', status: 'sem-chave', color: 'var(--red)', cred: 'não', note: 'verificador de topo indisponível' },
];

const ROUTING = [
  { role: 'planner', tier: 'simples', model: 'llama-3.3-70b', fallback: '→ qwen-2.5-72b' },
  { role: 'pesquisador', tier: 'simples', model: 'llama-3.3-70b', fallback: '→ deepseek-v3' },
  { role: 'transformador', tier: 'média', model: 'deepseek-v3', fallback: '→ codex-mini' },
  { role: 'arquiteto', tier: 'média', model: 'kimi-k2', fallback: '→ codex-mini (429)' },
  { role: 'verifier / evaluator', tier: 'complexa', model: 'claude-sonnet-4', fallback: '→ codex-mini (sem-chave)' },
];

export default function Agentes() {
  const [view, setView] = useState('gallery'); // 'gallery', 'page', 'ladder'
  const [selected, setSelected] = useState(null);
  const [inputText, setInputText] = useState('');
  const [customMessages, setCustomMessages] = useState({});

  // ponytail: usePoll fetches live agent call and failure data from /dados/agentes every 2s
  const { data: apiAgents, error } = usePoll(getAgents);

  // Map dynamic metrics and status rings onto the local blueprint
  const agentsList = Object.keys(DEFAULT_AGENTS).map(key => {
    const defaultAgent = DEFAULT_AGENTS[key];
    const stats = getStatsForAgent(key, defaultAgent, apiAgents);
    
    let activity = defaultAgent.activity;
    let sh = defaultAgent.sh;
    let ring = defaultAgent.ring;
    
    if (apiAgents && apiAgents.length > 0) {
      if (stats.chamadas === 0) {
        activity = 'inativo · pronto';
        sh = 'sh idle';
        ring = 'ridle';
      } else if (stats.falhas > 0) {
        activity = `ativo · ${stats.falhas} falha(s)`;
        sh = 'sh red';
        ring = 'rred';
      } else {
        activity = 'ativo · saudável';
        sh = 'sh green';
        ring = 'rgreen';
      }
    }
    
    return {
      ...defaultAgent,
      chamadas: stats.chamadas,
      falhas: stats.falhas,
      activity,
      sh,
      ring
    };
  });

  const ag = selected ? agentsList.find(a => a.id === selected) : null;

  const handleSend = () => {
    if (!inputText.trim()) return;
    setCustomMessages(prev => ({
      ...prev,
      [selected]: [...(prev[selected] || []), { text: inputText.trim(), isUser: true }]
    }));
    setInputText('');
  };

  return (
    <>
      <style>{STYLES}</style>
      
      {/* Header + Tabs */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 20px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        margin: '-22px -24px 20px -24px',
        flex: 'none'
      }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
            {view === 'page' && (
              <span className="mono" style={{ fontSize: 12, color: 'var(--text2)', cursor: 'pointer' }} onClick={() => { setView('gallery'); setSelected(null); }}>
                ← Agentes
              </span>
            )}
            <div>
              <div className="eyebrow" style={{ marginBottom: 3 }}>Biblioteca · Modelos personificados</div>
              <div className="title" style={{ fontSize: 19, display: 'flex', alignItems: 'center' }}>
                {view === 'page' && ag ? ag.name : view === 'ladder' ? 'Escada & Rotas' : 'Agentes'}
                {view === 'gallery' && <span className="chip" style={{ marginLeft: 12, fontWeight: 'normal', fontSize: 10 }}>blueprint · estático</span>}
              </div>
            </div>
        </div>
        <div style={{ width: 1, height: 30, background: 'var(--border)', margin: '0 6px' }} />
        <span
          className={view === 'gallery' || view === 'page' ? 'pill on' : 'pill'}
          onClick={() => { setView('gallery'); setSelected(null); }}
          style={{ cursor: 'pointer' }}
        >
          Galeria
        </span>
        <span
          className={view === 'ladder' ? 'pill on' : 'pill'}
          onClick={() => setView('ladder')}
          style={{ cursor: 'pointer' }}
        >
          Escada &amp; Rotas
        </span>
        <div style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="sh blue" />
          AO VIVO · MOTOR v0.5
        </span>
      </div>

      {/* GALLERY VIEW */}
      {(view === 'gallery') && (
        <div style={{ flex: 1, padding: '24px 0 20px' }}>
          {error && (
            <div style={{ color: 'var(--red)', fontFamily: 'monospace', marginBottom: 20 }}>
              Aviso: Erro ao carregar dados dinâmicos do log ({error}). Exibindo catálogo local.
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: '38px 16px' }}>
            {agentsList.map(a => (
              <div key={a.id} className="acard" onClick={() => { setSelected(a.id); setView('page'); }}>
                <div className="bustwrap">
                  <div className={`bust ${a.hv}`}>
                    <div className={`ring ${a.ring}`} />
                    <div className="shoulders" />
                    <div className={`head ${a.hv}`}>
                      <div className="rimlight" />
                      <div className="visor" />
                    </div>
                    <div className="emblem mono">{a.emblem}</div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', width: '100%', justifyContent: 'space-between', gap: 6 }}>
                  <span className="title" style={{ fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {a.name}
                  </span>
                  <span className={`${a.certcls} certtag`}>{a.certShort}</span>
                </div>
                
                <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 3 }}>{a.model}</div>
                <div className="stbadge" style={{ marginTop: 10 }}>
                  <span className={a.sh} />
                  {a.activity}
                </div>
                
                <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 2 }}>{a.role} · {a.tierLabel}</div>
                
                {/* Dynamically wired call & error stats */}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)', fontSize: 10.5 }} className="mono">
                  <span style={{ color: 'var(--text2)' }}>Chamadas: <span className="num" style={{ color: 'var(--text)' }}>{a.chamadas}</span></span>
                  <span style={{ color: a.falhas > 0 ? 'var(--red)' : 'var(--text3)' }}>Falhas: <span className="num" style={{ color: a.falhas > 0 ? 'var(--red)' : 'var(--text2)' }}>{a.falhas}</span></span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{a.provider}</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>Falar →</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* DETAIL VIEW */}
      {view === 'page' && ag && (
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '340px 1fr', gap: 18, alignItems: 'start', padding: '10px 0 20px' }}>
          
          {/* Left Column: Portrait + doing + chat */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>
            <div className="card" style={{ padding: '92px 18px 18px', position: 'relative', overflow: 'visible', marginTop: 34 }}>
              <div style={{ position: 'absolute', top: -70, left: 0, right: 0 }}>
                <div className={`bust big ${ag.hv}`}>
                  <div className={`ring ${ag.ring}`} />
                  <div className="shoulders" />
                  <div className={`head ${ag.hv}`}>
                    <div className="rimlight" />
                    <div className="visor" />
                  </div>
                  <div className="emblem mono">{ag.emblem}</div>
                </div>
              </div>
              <div style={{ textAlign: 'center', marginTop: 6 }}>
                <div className="title" style={{ fontSize: 20 }}>{ag.name}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', marginTop: 4 }}>{ag.model}</div>
                <div className="stbadge" style={{ justifyContent: 'center', marginTop: 12 }}>
                  <span className={ag.sh} />
                  {ag.activity}
                </div>
                <div style={{ marginTop: 12 }}>
                  <span className={`${ag.certcls} certtag`}>{ag.certLong}</span>
                </div>
              </div>
            </div>

            <div className="card">
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                <span className="eyebrow">Fazendo agora</span>
              </div>
              <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {ag.doing.map((d, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <span className={d.sh} />
                    <div style={{ minWidth: 0 }}>
                      <div className="mono" style={{ fontSize: 11.5, color: 'var(--text)' }}>{d.node}</div>
                      <div className="mono" style={{ fontSize: 9.5, color: 'var(--text3)' }}>{d.where}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Chat Box */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="eyebrow">Falar com {ag.short}</span>
                <span className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>canal de direcionamento</span>
              </div>
              <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 200, overflowY: 'auto' }}>
                <div style={{ alignSelf: 'flex-start', maxWidth: '85%', backgroundColor: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 2, padding: '9px 11px' }}>
                  <div className="mono" style={{ fontSize: 9, color: 'var(--text3)', marginBottom: 4 }}>{ag.short}</div>
                  <div style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.5 }}>{ag.chatMsg}</div>
                </div>
                
                {/* Dynamically populated user messages */}
                {(customMessages[ag.id] || []).map((m, idx) => (
                  <div key={idx} style={{ alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: 'var(--inv-bg)', color: 'var(--inv-text)', borderRadius: 2, padding: '9px 11px', fontSize: 12.5, lineHeight: 1.5 }}>
                    {m.text}
                  </div>
                ))}
              </div>
              
              <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="text"
                  disabled
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
                  placeholder="canal de direcionamento · em breve"
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: '1px solid var(--border)',
                    borderRadius: 2,
                    padding: '8px 10px',
                    fontSize: 12,
                    color: 'var(--text)',
                    outline: 'none',
                    opacity: 0.5,
                    cursor: 'not-allowed'
                  }}
                />
                <button className="btn btn-primary btn-sm" disabled style={{ opacity: 0.5, cursor: 'not-allowed' }}>Enviar</button>
              </div>
            </div>
          </div>

          {/* Right Column: details + telemetry + recurrent rejections */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 18, alignItems: 'start' }}>
              <div className="card">
                <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                  <span className="eyebrow">01 — Ficha técnica</span>
                </div>
                <div style={{ padding: '6px 14px 10px' }}>
                  <div className="row">
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)' }}>modelo</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>{ag.model}</span>
                  </div>
                  <div className="row">
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)' }}>provedor</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>{ag.provider}</span>
                  </div>
                  <div className="row">
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)' }}>Hugging Face</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--accent)' }}>
                      {ag.hf.includes('↗') ? <a href={`https://huggingface.co/${ag.hf.split(' ')[0]}`} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>{ag.hf}</a> : ag.hf}
                    </span>
                  </div>
                  <div className="row">
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)' }}>credencial</span>
                    <span className="mono" style={{ fontSize: 11, color: ag.credColor }}>{ag.cred}</span>
                  </div>
                  <div className="row" style={{ borderBottom: 'none' }}>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)' }}>fine-tunings</span>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>{ag.finetune}</span>
                  </div>
                </div>
              </div>

              <div className="card">
                <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                  <span className="eyebrow">02 — Posição na escada</span>
                </div>
                <div style={{ padding: 14 }}>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', marginBottom: 10 }}>degrau atual</div>
                  <div className="title" style={{ fontSize: 22, color: 'var(--text)' }}>{ag.rung}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>{ag.rungNote}</div>
                  <div style={{ marginTop: 16 }}>
                    <span className={`${ag.certcls} certtag`}>{ag.certLong}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.5, marginTop: 10 }}>{ag.certNote}</div>
                </div>
              </div>
            </div>

            {/* Dynamic Telemetry */}
            <div className="card">
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="eyebrow">03 — Telemetria do Curador</span>
                <span className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>{ag.sample}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)' }}>
                {ag.metrics.map((m, idx) => {
                  let val = m.val;
                  let color = m.color;
                  if (m.label === 'taxa erro') {
                    val = ag.chamadas > 0 ? ((ag.falhas / ag.chamadas) * 100).toFixed(0) + '%' : '0%';
                    color = ag.falhas > 0 ? 'var(--red)' : 'var(--green)';
                  } else {
                    val = '—';
                    color = 'var(--text3)';
                  }
                  return (
                    <div key={idx} style={{ padding: 14, borderRight: idx < 4 ? '1px solid var(--border)' : 'none' }}>
                      <div className="eyebrow" style={{ fontSize: 9 }}>{m.label}</div>
                      <div className="num" style={{ fontSize: 20, color, marginTop: 8 }}>{val}</div>
                      <div className="mono" style={{ fontSize: 9, color: 'var(--text3)', marginTop: 3 }}>{m.sub}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card">
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                <span className="eyebrow">04 — Motivos de reprovação recorrentes (agregado)</span>
              </div>
              <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 9 }}>
                {ag.reasons.map((r, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--red)', width: 30, flex: 'none' }}>{r.pct}</span>
                    <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5 }}>{r.text}</span>
                  </div>
                ))}
              </div>
            </div>

          </div>

        </div>
      )}

      {/* LADDER & ROUTES VIEW */}
      {view === 'ladder' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 18, padding: '10px 0 20px' }}>
          
          {/* 01 — Escada */}
          <div className="card">
            <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
              <span className="eyebrow">01 — Escada de custo × capacidade</span>
            </div>
            <div style={{ padding: 16, display: 'flex', gap: 12, alignItems: 'stretch', overflowX: 'auto' }}>
              {LADDER.map((s, idx) => (
                <div key={idx} className="step" style={{ marginTop: s.offset }}>
                  <div className="eyebrow" style={{ fontSize: 9 }}>{s.tier}</div>
                  <div className="title" style={{ fontSize: 15 }}>{s.name}</div>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{s.cost}</div>
                  <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                  {s.models.map((m, mIdx) => (
                    <span key={mIdx} className="mono" style={{ fontSize: 10.5, color: 'var(--text2)' }}>{m}</span>
                  ))}
                </div>
              ))}
            </div>
            <div className="mono" style={{ padding: '0 16px 14px', fontSize: 10, color: 'var(--text3)' }}>
              → sobe de degrau só quando reprova; free primeiro, topo (verificador) por último.
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 18, alignItems: 'start' }}>
            
            {/* Presets */}
            <div className="card">
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                <span className="eyebrow">02 — Presets de catálogo</span>
              </div>
              <div style={{ padding: '4px 14px 10px' }}>
                {PRESETS.map((p, idx) => (
                  <div key={idx} style={{ padding: '11px 0', borderBottom: idx < PRESETS.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span className="mono" style={{ fontSize: 12, color: 'var(--accent)' }}>{p.name}</span>
                      <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{p.use}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 10.5, color: 'var(--text2)', marginTop: 4, lineHeight: 1.5 }}>
                      {p.map}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Providers */}
            <div className="card">
              <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
                <span className="eyebrow">03 — Status por provedor</span>
              </div>
              <div style={{ padding: '4px 14px 10px' }}>
                {PROVIDERS.map((p, idx) => (
                  <div key={idx} style={{ padding: '11px 0', borderBottom: idx < PROVIDERS.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="provdot" style={{ background: p.color }} />
                      <span className="mono" style={{ fontSize: 12, color: 'var(--text)' }}>{p.name}</span>
                      <span className="mono" style={{ fontSize: 10, color: p.color, marginLeft: 'auto' }}>{p.status}</span>
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
                      credencial: {p.cred} · {p.note}
                    </div>
                  </div>
                ))}
                <div className="mono" style={{ fontSize: 9.5, color: 'var(--text3)', lineHeight: 1.5, paddingTop: 10 }}>
                  A UI nunca exibe a chave — apenas se a credencial está configurada.
                </div>
              </div>
            </div>

          </div>

          {/* Routing */}
          <div className="card">
            <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
              <span className="eyebrow">04 — Roteamento papel → tier → modelo (+ fallback por esgotamento)</span>
            </div>
            <div className="row" style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
              <span className="eyebrow" style={{ flex: 1 }}>Papel</span>
              <span className="eyebrow" style={{ width: 110 }}>Tier</span>
              <span className="eyebrow" style={{ width: 180 }}>Modelo</span>
              <span className="eyebrow" style={{ width: 180 }}>Fallback (429/esgotado)</span>
            </div>
            {ROUTING.map((r, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', borderBottom: idx < ROUTING.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <span className="mono" style={{ fontSize: 11.5, color: 'var(--text)', flex: 1 }}>{r.role}</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text2)', width: 110 }}>{r.tier}</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text)', width: 180 }}>{r.model}</span>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text3)', width: 180 }}>{r.fallback}</span>
              </div>
            ))}
          </div>

        </div>
      )}
    </>
  );
}
