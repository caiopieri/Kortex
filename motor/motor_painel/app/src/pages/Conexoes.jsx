import { useState } from 'react';

const INITIAL_CONNECTIONS = [
  { id: 'alibaba', nome: 'Alibaba Model Studio', status: 'ativo', autenticado: true, arquivo: '~/.claude/secrets/alibaba-model-studio.env', tipo: 'MCP Server', desc: 'Imagem, vídeo, TTS, ASR' },
  { id: 'firecrawl', nome: 'Firecrawl Search & Scrape', status: 'ativo', autenticado: true, arquivo: 'token cadastrado', tipo: 'MCP Server', desc: 'Web scraping, search' },
  { id: 'codex', nome: 'Codex Plugin', status: 'pronto', autenticado: false, arquivo: 'pendente', tipo: 'Plugin / CLI', desc: 'Code review, rescue' },
  { id: 'antigravity', nome: 'Antigravity Plugin', status: 'pronto', autenticado: false, arquivo: 'pendente', tipo: 'Plugin / CLI', desc: 'Teste gen, migrations' },
];

export default function Conexoes() {
  const [connections, setConnections] = useState(INITIAL_CONNECTIONS);
  const [newKey, setNewKey] = useState('');
  const [selectedPlugin, setSelectedPlugin] = useState('');

  const registerConnection = (id) => {
    setConnections(prev => prev.map(c => c.id === id ? { ...c, status: 'ativo', autenticado: true, arquivo: 'token inserido via UI' } : c));
  };

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Conexões</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>mcp &amp; plugins cadastrados</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20, marginTop: 16 }}>
        {/* List of connections */}
        <div>
          <div className="num" style={{ marginBottom: 10 }}>01 — Conexões habilitadas <span className="chip">exemplo · estático</span></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {connections.map(c => (
              <div key={c.id} className="card" style={{ padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span className={c.status === 'ativo' ? 'sh green' : 'sh idle'}></span>
                  <span className="title" style={{ fontSize: 14, flex: 1 }}>{c.nome}</span>
                  <span className="mono" style={{ fontSize: 9, color: c.status === 'ativo' ? 'var(--green)' : 'var(--text3)', border: '1px solid', borderRadius: 2, padding: '1px 6px' }}>{c.status}</span>
                </div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>{c.desc}</div>
                <div style={{ display: 'flex', gap: 12, marginTop: 8, alignItems: 'center' }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{c.tipo}</span>
                  <span className="mono" style={{ fontSize: 10, color: c.autenticado ? 'var(--green)' : 'var(--amber)' }}>{c.arquivo}</span>
                  {!c.autenticado && (
                    <span className="lnk amber" style={{ marginLeft: 'auto' }} onClick={() => setSelectedPlugin(c.id)}>Registrar credencial →</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Register panel */}
        <div>
          <div className="num" style={{ marginBottom: 10 }}>02 — Registrar nova credencial</div>
          <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="nm-field">
              <span className="eyebrow">Selecionar plugin/MCP</span>
              <select
                className="nm-inp"
                value={selectedPlugin}
                onChange={e => setSelectedPlugin(e.target.value)}
                style={{ background: 'var(--surface)' }}
              >
                <option value="">Selecione...</option>
                {connections.filter(c => !c.autenticado).map(c => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
              </select>
            </div>

            <div className="nm-field">
              <span className="eyebrow">API Key ou Caminho do Env</span>
              <input
                className="nm-inp"
                type="text"
                placeholder="Ex: sk-... ou ~/.claude/secrets/meu-mcp.env"
                value={newKey}
                onChange={e => setNewKey(e.target.value)}
              />
            </div>

            <div
              className="btn btn-primary"
              style={{ textAlign: 'center', justifyContent: 'center', opacity: 0.5, cursor: 'not-allowed' }}
            >
              Registrar Conexão →
            </div>

            <div className="mono" style={{ fontSize: 9.5, color: 'var(--text3)', lineHeight: 1.5, marginTop: 8 }}>
              Nota: registro via UI não implementado — configure em ~/.claude/ (CLI).
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .nm-field{display:flex;flex-direction:column;gap:7px}
        .nm-inp{border:1px solid var(--border);border-radius:2px;background:var(--surface);color:var(--text);font-family:'IBM Plex Mono',monospace;font-size:12px;padding:9px 11px;outline:none}
        .nm-inp:focus{border-color:var(--focus)}
      `}</style>
    </>
  );
}
