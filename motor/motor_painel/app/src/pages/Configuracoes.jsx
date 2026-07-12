import { useState, useCallback, useEffect } from 'react';
import { getAllThemes, getStoredTheme, getStoredMode, applyTheme } from '../theme.js';

export default function Configuracoes() {
  const [themeId, setThemeId] = useState(getStoredTheme);
  const [mode, setMode] = useState(getStoredMode);
  const [density, setDensity] = useState(() => localStorage.getItem('mf-density') || 'normal');
  const [animations, setAnimations] = useState(() => localStorage.getItem('mf-anim') !== 'off');
  const [streamLimit, setStreamLimit] = useState(() => parseInt(localStorage.getItem('mf-stream-limit') || '50', 10));

  const themes = getAllThemes();

  const handleThemeChange = useCallback((id) => {
    setThemeId(id);
    applyTheme(id, mode);
  }, [mode]);

  const handleModeChange = useCallback((m) => {
    setMode(m);
    applyTheme(themeId, m);
  }, [themeId]);

  useEffect(() => {
    localStorage.setItem('mf-density', density);
    document.documentElement.setAttribute('data-density', density);
  }, [density]);

  useEffect(() => {
    localStorage.setItem('mf-anim', animations ? 'on' : 'off');
    document.documentElement.setAttribute('data-anim', animations ? 'on' : 'off');
  }, [animations]);

  useEffect(() => {
    localStorage.setItem('mf-stream-limit', String(streamLimit));
  }, [streamLimit]);

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Configurações</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>aparência · comportamento</span>
      </div>

      {/* Theme selection */}
      <div style={{ marginTop: 20 }}>
        <div className="num" style={{ marginBottom: 12 }}>01 — Tema</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {themes.map(t => (
            <div
              key={t.id}
              className="card"
              style={{
                padding: '12px 14px',
                cursor: 'pointer',
                width: 180,
                borderColor: themeId === t.id ? 'var(--accent)' : undefined,
              }}
              onClick={() => handleThemeChange(t.id)}
            >
              {/* Mini preview */}
              <div style={{
                height: 36,
                borderRadius: 2,
                marginBottom: 8,
                background: t.escuro['--bg'],
                border: `1px solid ${t.escuro['--border']}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
              }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: t.escuro['--accent'] }}></span>
                <span style={{ width: 20, height: 3, borderRadius: 1, background: t.escuro['--text2'] }}></span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="title" style={{ fontSize: 12 }}>{t.nome}</span>
                {themeId === t.id && <span className="mono" style={{ fontSize: 9, color: 'var(--accent)' }}>ativo</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Mode */}
      <div style={{ marginTop: 24 }}>
        <div className="num" style={{ marginBottom: 12 }}>02 — Modo</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className={`pill${mode === 'escuro' ? ' on' : ''}`} onClick={() => handleModeChange('escuro')}>◐ Escuro</span>
          <span className={`pill${mode === 'claro' ? ' on' : ''}`} onClick={() => handleModeChange('claro')}>◑ Claro</span>
        </div>
      </div>

      {/* Density */}
      <div style={{ marginTop: 24 }}>
        <div className="num" style={{ marginBottom: 12 }}>03 — Densidade</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className={`pill${density === 'normal' ? ' on' : ''}`} onClick={() => setDensity('normal')}>Normal</span>
          <span className={`pill${density === 'compacto' ? ' on' : ''}`} onClick={() => setDensity('compacto')}>Compacto</span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 6 }}>
          Compacto reduz padding dos cards, sidebar e tabelas.
        </div>
      </div>

      {/* Animations */}
      <div style={{ marginTop: 24 }}>
        <div className="num" style={{ marginBottom: 12 }}>04 — Animações</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className={`pill${animations ? ' on' : ''}`} onClick={() => setAnimations(true)}>● Ligadas</span>
          <span className={`pill${!animations ? ' on' : ''}`} onClick={() => setAnimations(false)}>○ Desligadas</span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 6 }}>
          Desativa pulsos dos shapes de status e transições CSS.
        </div>
      </div>

      {/* Stream limit */}
      <div style={{ marginTop: 24 }}>
        <div className="num" style={{ marginBottom: 12 }}>05 — Limite de streaming</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[20, 50, 100, 200].map(n => (
            <span key={n} className={`pill${streamLimit === n ? ' on' : ''}`} onClick={() => setStreamLimit(n)}>{n}</span>
          ))}
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 6 }}>
          Número máximo de eventos renderizados por coluna na tela de Logs.
        </div>
      </div>

      {/* System info */}
      <div style={{ marginTop: 24 }}>
        <div className="num" style={{ marginBottom: 12 }}>06 — Sistema</div>
        <div className="card" style={{ padding: '10px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>versão do painel</span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>v0.5</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>motor</span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>meta-fábrica v0.5</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>API base</span>
            <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>/dados</span>
          </div>
        </div>
      </div>
    </>
  );
}
