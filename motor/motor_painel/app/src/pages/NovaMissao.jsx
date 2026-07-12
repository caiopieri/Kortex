import { useState, useMemo } from 'react';
import { postMissao, getMissaoAtiva, usePoll } from '../api';

const ROTAS = {
  pesquisa:    { label: 'pesquisa', n: 7 },
  forja:       { label: 'forja · software', n: 6 },
  construcao:  { label: 'construção', n: 4 },
  hardware:    { label: 'hardware', n: 4 },
};

const PRESETS = {
  'free-escalada':    { map: [['planner', 'kimi-k2.6'], ['exec simples', 'llama-3.3-70b'], ['exec media', 'kimi-k2.6'], ['exec complexa', 'codex/gpt-5.4'], ['verifier', 'codex/gpt-5.4']], custo: 'US$ 0.20 – 0.60', nota: 'Free primeiro; sobe de tier só quando reprova.' },
  codex:              { map: [['todos os papéis', 'codex/gpt-5.4'], ['verifier', 'codex/gpt-5.4']], custo: 'US$ 1.20 – 2.40', nota: 'Confiável e estrito; custo médio.' },
  claude:             { map: [['executores', 'codex/gpt-5.4'], ['verifier/topo', 'claude']], custo: 'US$ 2.50 – 4.00', nota: 'Topo no verificador.' },
  construcao:         { map: [['planner', 'kimi-k2.6'], ['redator', 'deepseek-v4'], ['verifier', 'codex/gpt-5.4']], custo: 'US$ 0.40 – 1.00', nota: 'Rota de construção/documentos.' },
  'pesquisa-sintese': { map: [['pesquisador', 'llama-3.3 → kimi'], ['evaluator', 'codex/gpt-5.4'], ['synthesizer', 'codex/gpt-5.4']], custo: 'US$ 0.30 – 0.80', nota: 'Fan-out de pesquisa com síntese final.' },
};

const PAPEL_POR_ROTA = { pesquisa: 'pesquisador', forja: 'executor', construcao: 'redator', hardware: 'executor' };

/* WorkflowSpec real montada do formulário — única fonte para o despacho
 * pelo botão e para o comando CLI do painel "Despacho manual". */
function montarSpec({ descricao, rota, preset, teto }) {
  const objetivo = descricao.trim() || 'Missão disparada pelo painel (sem descrição)';
  const slug = objetivo
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40) || 'missao-painel';
  return {
    versao: '0.1',
    padrao: 'fan_out_sintese',
    missao: {
      id: slug,
      objetivo,
      contexto: `rota: ${rota} · preset: ${preset}`,
      criterios_cobertura: ['objetivo da missão coberto com evidência'],
    },
    restricoes: { teto_custo: 2.0, max_subagentes: 10, max_tentativas: Math.min(teto, 5) },
    subagentes: [{
      id: 'exec-1',
      papel: PAPEL_POR_ROTA[rota] || 'pesquisador',
      objetivo,
      entradas: {},
      resultado_esperado: 'Resultado que cumpre o objetivo da missão, com evidência',
      rubrica: ['atende ao objetivo declarado', 'cita evidência ou fonte'],
    }],
    gates: [],
    sintese: { instrucao: 'Consolide o resultado em um relatório único e acionável', formato: 'markdown' },
  };
}

function PillGroup({ options, current, onChange }) {
  return options.map(o => (
    <span key={o.value} className={`pill${current === o.value ? ' on' : ''}`} onClick={() => onChange(o.value)}>{o.label}</span>
  ));
}

export default function NovaMissao() {
  const [descricao, setDescricao] = useState('');
  const [rota, setRota] = useState('pesquisa');
  const [preset, setPreset] = useState('free-escalada');
  const [modo, setModo] = useState('supervisionado');
  const [escalada, setEscalada] = useState(true);
  const [reconciliacao, setReconciliacao] = useState(true);
  const [gateCobertura, setGateCobertura] = useState(true);
  const [teto, setTeto] = useState(3);
  const [arquivo, setArquivo] = useState('');
  const [aceite, setAceite] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [copiado, setCopiado] = useState(false);

  const { data: missaoAtiva } = usePoll(getMissaoAtiva);
  const ativa = missaoAtiva?.ativa === true;

  const P = PRESETS[preset];
  const R = ROTAS[rota];

  const spec = useMemo(
    () => montarSpec({ descricao, rota, preset, teto }),
    [descricao, rota, preset, teto]
  );

  /* Alternativa manual — mesma spec, mesmas opções do botão de despacho. */
  const comandoCli = useMemo(() => {
    const json = JSON.stringify(spec).replace(/'/g, "'\\''");
    let cmd = `python3 -m motor --spec <(printf '%s' '${json}') --caixa runs/caixa`;
    if (modo === 'auto') cmd += ' --auto';
    if (escalada) cmd += ' --escalar';
    return cmd;
  }, [spec, modo, escalada]);

  const copiarComando = () => {
    navigator.clipboard.writeText(comandoCli).then(() => {
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    });
  };

  const resumo = useMemo(() => ({
    rota: R.label,
    preset,
    custo: P.custo,
    map: P.map.map(m => ({ k: m[0], v: m[1] })),
    modo: modo === 'auto' ? 'auto (--auto, sem parar)' : 'supervisionado',
    escalada: escalada ? 'ligada · sobe tier ao reprovar' : 'desligada',
    recon: reconciliacao ? `ligada · teto ${teto} rodadas` : 'desligada',
    gate: gateCobertura ? 'humano' : 'sem gate',
    nodes: `~${R.n}`,
  }), [rota, preset, modo, escalada, reconciliacao, gateCobertura, teto, R, P]);

  const handleConfirm = async () => {
    if (!aceite || enviando || ativa) return;
    setEnviando(true);
    setErro(null);
    try {
      const r = await postMissao(spec, { auto: modo === 'auto', escalar: escalada });
      setResultado(r);
    } catch (e) {
      setErro(e.message);
    }
    setEnviando(false);
  };

  if (resultado) {
    return (
      <div style={{ padding: '56px 40px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, textAlign: 'center' }}>
        <div style={{ width: 40, height: 40, border: '1.5px solid var(--blue)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ width: 11, height: 11, borderRadius: '50%', background: 'var(--blue)' }}></span>
        </div>
        <div className="title" style={{ fontSize: 20 }}>Motor despachado</div>
        <div className="mono" style={{ fontSize: 12, color: 'var(--text2)' }}>pid {resultado.pid}</div>
        <div className="mono" style={{ fontSize: 11, color: 'var(--text3)', maxWidth: 520, lineHeight: 1.6, wordBreak: 'break-all' }}>
          spec: {resultado.spec}<br />log: {resultado.log}
        </div>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--text3)', maxWidth: 440, lineHeight: 1.6 }}>
          O motor está rodando como processo real neste pid. Acompanhe o log acima no terminal (<span className="mono" style={{ color: 'var(--text2)' }}>tail -f</span>) ou os nós no Grafo 2D; gates aparecem na Caixa do Fundador.
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 6 }}>
          <span className="btn btn-primary" onClick={() => { window.location.hash = '/grafo'; }}>Abrir Grafo 2D →</span>
          <span className="btn" onClick={() => setResultado(null)}>Nova missão</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <div style={{ marginBottom: 0 }}>
        <div className="eyebrow" style={{ marginBottom: 3 }}>Disparo de run · formulário</div>
        <div className="title" style={{ fontSize: 19 }}>Nova missão</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', flex: 1, minHeight: 0, marginTop: 16 }}>
        {/* Left: form */}
        <div style={{ padding: '0 20px 20px 0', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Descrição */}
          <div className="nm-field">
            <span className="eyebrow">Descrição da missão</span>
            <textarea
              className="nm-textarea"
              placeholder="O que você quer que aconteça? Ex: 'Pesquisa de canais de venda para plano trimestral…'"
              value={descricao}
              onChange={e => setDescricao(e.target.value)}
            />
          </div>

          {/* Rota */}
          <div className="nm-field">
            <span className="eyebrow">Rota / Workflow</span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <PillGroup
                options={Object.entries(ROTAS).map(([k, v]) => ({ value: k, label: v.label }))}
                current={rota}
                onChange={setRota}
              />
            </div>
          </div>

          {/* Insumos */}
          <div className="nm-field">
            <span className="eyebrow">Insumos</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
              <input className="nm-inp" style={{ flex: 1 }} placeholder="caminho, arquivo ou spec — ex.: exemplos/missao-pesquisa.json" />
              <label className="btn" style={{ flex: 'none', cursor: 'pointer', whiteSpace: 'nowrap', padding: '9px 14px', fontSize: 12 }}>
                ⬆ Anexar arquivo
                <input type="file" onChange={e => { const f = e.target.files?.[0]; setArquivo(f ? f.name : ''); }} style={{ display: 'none' }} />
              </label>
            </div>
            <span className="mono" style={{ fontSize: 10, color: arquivo ? 'var(--green)' : 'var(--text3)' }}>
              {arquivo ? `arquivo anexado · ${arquivo}` : 'arraste um arquivo ou cole um caminho · opcional'}
            </span>
          </div>

          {/* Preset */}
          <div className="nm-field">
            <span className="eyebrow">Preset de catálogo</span>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <PillGroup
                options={Object.keys(PRESETS).map(k => ({ value: k, label: k }))}
                current={preset}
                onChange={setPreset}
              />
            </div>
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--text2)' }}>{P.nota}</span>
          </div>

          {/* Opções */}
          <div className="nm-field">
            <span className="eyebrow">Opções</span>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <span className={`pill${modo === 'auto' ? ' on' : ''}`} onClick={() => setModo(modo === 'auto' ? 'supervisionado' : 'auto')}>{modo === 'auto' ? '● auto' : '○ supervisionado'}</span>
              <span className={`pill${escalada ? ' on' : ''}`} onClick={() => setEscalada(!escalada)}>{escalada ? '●' : '○'} escalada</span>
              <span className={`pill${reconciliacao ? ' on' : ''}`} onClick={() => setReconciliacao(!reconciliacao)}>{reconciliacao ? '●' : '○'} reconciliação</span>
              <span className={`pill${gateCobertura ? ' on' : ''}`} onClick={() => setGateCobertura(!gateCobertura)}>{gateCobertura ? '●' : '○'} gate cobertura</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)' }}>teto de reconciliação</span>
              <div style={{ display: 'flex', gap: 6 }}>
                {[1, 2, 3, 4, 5].map(n => (
                  <span key={n} className={`pill${teto === n ? ' on' : ''}`} onClick={() => setTeto(n)}>{n}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Orquestrador door */}
          <div style={{ border: '1px dashed var(--border)', borderRadius: 2, padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span className="eyebrow">Ou peça ao Orquestrador</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 11px', border: '1px solid var(--border)', borderRadius: 2, background: 'var(--bg)' }}>
              <span className="mono" style={{ fontSize: 11.5, color: 'var(--text3)', flex: 1 }}>"Roda uma pesquisa de canais e me traz um digest…"</span>
              <span style={{ color: 'var(--text3)' }}>↑</span>
            </div>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.5 }}>Ele preenche este mesmo formulário e devolve o mesmo resumo pra você confirmar — uma só mecânica de disparo, duas portas.</span>
          </div>
        </div>

        {/* Right: summary */}
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', background: 'var(--surface2)', borderLeft: '1px solid var(--border)', overflowY: 'auto' }}>
          <span className="num" style={{ color: 'var(--accent)', marginBottom: 14 }}>O que vai acontecer</span>
          <div style={{ flex: 1 }}>
            <div className="nm-rsum"><span className="nm-k">rota</span><span className="nm-v">{resumo.rota}</span></div>
            <div className="nm-rsum"><span className="nm-k">preset</span><span className="nm-v">{resumo.preset}</span></div>
            <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <span className="eyebrow" style={{ fontSize: 9 }}>mapeamento papel → modelo</span>
              <div style={{ marginTop: 7, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {resumo.map.map((m, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{m.k}</span>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', textAlign: 'right' }}>{m.v}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="nm-rsum"><span className="nm-k">modo</span><span className="nm-v">{resumo.modo}</span></div>
            <div className="nm-rsum"><span className="nm-k">escalada</span><span className="nm-v">{resumo.escalada}</span></div>
            <div className="nm-rsum"><span className="nm-k">reconciliação</span><span className="nm-v">{resumo.recon}</span></div>
            <div className="nm-rsum"><span className="nm-k">gate cobertura</span><span className="nm-v">{resumo.gate}</span></div>
            <div className="nm-rsum"><span className="nm-k">nós estimados</span><span className="nm-v">{resumo.nodes}</span></div>
          </div>
          <div style={{ margin: '16px 0 12px', padding: 12, border: '1px solid var(--border)', borderRadius: 2, background: 'var(--surface)' }}>
            <span className="eyebrow" style={{ fontSize: 9 }}>custo estimado · run</span>
            <div className="mono" style={{ fontSize: 18, fontWeight: 600, marginTop: 5, color: 'var(--text)' }}>{resumo.custo}</div>
            <span className="mono" style={{ fontSize: 9.5, color: 'var(--text3)' }}>escolhas custam tempo e dinheiro</span>
          </div>
          <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 10, cursor: 'pointer' }}>
            <input type="checkbox" checked={aceite} onChange={e => setAceite(e.target.checked)} style={{ marginTop: 2 }} />
            <span className="mono" style={{ fontSize: 10.5, color: 'var(--text2)', lineHeight: 1.5 }}>entendo que isto executa o motor e consome créditos</span>
          </label>
          {erro && (
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--red)', marginBottom: 10, lineHeight: 1.5, wordBreak: 'break-all' }}>{erro}</div>
          )}
          <div
            className="btn btn-primary"
            style={(!aceite || ativa || enviando) ? { opacity: 0.45, pointerEvents: 'none' } : undefined}
            onClick={handleConfirm}
          >
            {ativa ? 'já há uma missão em curso' : enviando ? 'despachando…' : 'Confirmar disparo →'}
          </div>

          {/* Despacho manual — alternativa por terminal, mesma spec */}
          <div style={{ marginTop: 16, padding: 12, border: '1px dashed var(--border)', borderRadius: 2, background: 'var(--surface)', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span className="eyebrow" style={{ fontSize: 9 }}>Despacho manual · alternativa</span>
            <pre className="mono" style={{ fontSize: 9.5, color: 'var(--text2)', maxHeight: 140, overflow: 'auto', margin: 0, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 2, padding: 8, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {JSON.stringify(spec, null, 2)}
            </pre>
            <span className="btn" style={{ alignSelf: 'flex-start', fontSize: 11, padding: '7px 12px' }} onClick={copiarComando}>
              {copiado ? 'copiado ✓' : 'copiar comando'}
            </span>
            <span className="mono" style={{ fontSize: 9.5, color: 'var(--text3)', lineHeight: 1.5 }}>
              cole e rode na raiz de motor/ — mesma spec e opções do botão acima.
            </span>
          </div>
        </div>
      </div>

      <style>{`
        .nm-field{display:flex;flex-direction:column;gap:7px}
        .nm-textarea{border:1px solid var(--border);border-radius:2px;background:var(--surface);color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;padding:11px;min-height:72px;resize:vertical;outline:none}
        .nm-textarea:focus{border-color:var(--focus)}
        .nm-textarea::placeholder{color:var(--text3)}
        .nm-inp{border:1px solid var(--border);border-radius:2px;background:var(--surface);color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;padding:9px 11px;outline:none}
        .nm-inp:focus{border-color:var(--focus)}
        .nm-inp::placeholder{color:var(--text3)}
        .nm-rsum{display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--border)}
        .nm-k{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text3)}
        .nm-v{font-family:'IBM Plex Mono',monospace;font-size:10.5px;color:var(--text2);text-align:right}
      `}</style>
    </>
  );
}
