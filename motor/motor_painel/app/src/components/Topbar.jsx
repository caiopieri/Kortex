/* Topbar 52px — logo, toggle claro/escuro, +missão, sino.
 *
 * NAO ha mais "seletor projeto". Havia uma pilula "Projeto: Todos" aqui, com
 * `cursor: default` — parecia filtro, nao filtrava, e nao havia o que filtrar:
 * projeto nao existe no modelo do Kortex (cada run e um `runs/<id>` que esquece
 * tudo, §G do ESTADO.md). Foi o mesmo motivo que tirou o MapaGeral no corte 3.
 */

export default function Topbar({ theme, onToggleTheme }) {
  const label = theme === 'paperclip' ? 'ESCURO' : 'CLARO';

  return (
    <header className="mf-top">
      <a
        href="#/"
        aria-label="Kortex — início"
        style={{ display: 'flex', alignItems: 'center', gap: 9, color: 'var(--text)' }}
      >
        <svg viewBox="0 0 180 180" style={{ height: 22, width: 22, flex: 'none' }} aria-hidden="true">
          <g fill="none" stroke="currentColor" strokeWidth="18" strokeLinejoin="miter" strokeLinecap="square">
            <path d="M75 13 20 52v76l42 30" />
            <path d="m105 13 55 39v76l-42 30" />
          </g>
          <g fill="none" stroke="currentColor" strokeWidth="8" strokeLinecap="round">
            <path d="m53 70 37 27 37-27M90 97v43" />
          </g>
          <g fill="currentColor">
            <circle cx="53" cy="70" r="14.5" />
            <circle cx="127" cy="70" r="12.5" />
            <circle cx="90" cy="98" r="15.5" />
            <circle cx="90" cy="145" r="14.5" />
          </g>
        </svg>
        <svg viewBox="-8 0 1200 120" style={{ height: 12, width: 'auto', flex: 'none' }} aria-label="Kortex">
          <g fill="currentColor">
            <path d="M0 6h27v108H0zM27 58 90 6h42L68 59l70 55H94L27 63z" />
            <path fillRule="evenodd" d="M198 6h116c24 0 39 14 39 36v36c0 22-15 36-39 36H198c-24 0-39-14-39-36V42c0-22 15-36 39-36Zm4 24c-10 0-15 5-15 14v32c0 9 5 14 15 14h108c10 0 15-5 15-14V44c0-9-5-14-15-14H202Z" />
            <path fillRule="evenodd" d="M405 6h125c25 0 39 13 39 34v14c0 18-10 29-28 33l37 27h-43l-34-26h-68v26h-28V6Zm28 24v35h93c10 0 15-5 15-13v-9c0-8-5-13-15-13h-93Z" />
            <path d="M614 6h164v25h-68v83h-28V31h-68z" />
            <path d="M821 6h159v24H849v19h119v23H849v18h131v24H821z" />
            <path d="m1020 6 63 52-65 56h42l45-39 46 39h42l-66-56 62-52h-42l-42 35-43-35z" />
          </g>
        </svg>
      </a>
      <div style={{ flex: 1 }} />
      <button className="pill" onClick={onToggleTheme} title="Alternar tema">
        ◐ {label}
      </button>
      <button className="btn btn-primary btn-sm" style={{ marginLeft: 2 }} onClick={() => window.location.hash = '/nova-missao'}>
        + Nova missão
      </button>
      <span className="pill" style={{ padding: '5px 8px', cursor: 'pointer' }} title="Caixa do Fundador" onClick={() => window.location.hash = '/caixa'}>
        🔔
      </span>
    </header>
  );
}
