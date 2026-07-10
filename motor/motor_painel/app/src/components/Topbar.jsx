/* Topbar 52px — logo, seletor projeto, toggle tema, +missão, sino */

export default function Topbar({ theme, onToggleTheme }) {
  const label = theme === 'paperclip' ? 'ESCURO' : 'CLARO';

  return (
    <header className="mf-top">
      <div style={{
        width: 19, height: 19,
        border: '1.5px solid var(--text)',
        borderRadius: 2,
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute', inset: 4,
          border: '1.5px solid var(--accent)',
        }} />
      </div>
      <span className="title" style={{ fontSize: 13, letterSpacing: 1 }}>
        META-FÁBRICA
      </span>
      <span className="pill on" style={{ marginLeft: 4 }}>
        Projeto: Todos ▾
      </span>
      <div style={{ flex: 1 }} />
      <button className="pill" onClick={onToggleTheme} title="Alternar tema">
        ◐ {label}
      </button>
      <button className="btn btn-primary btn-sm" style={{ marginLeft: 2 }}>
        + Nova missão
      </button>
      <span className="pill" style={{ padding: '5px 8px' }} title="Caixa do Fundador">
        🔔
      </span>
    </header>
  );
}
