/* Icones em traco de 1.6, currentColor, viewBox 24. Nenhum vem de pacote:
   sao cinco, e dependencia de icones para cinco glifos e peso sem retorno. */

const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export const Cursor = () => (
  <svg {...base} fill="currentColor" stroke="none">
    <path d="M5.5 3.2 19 11.4c.7.4.5 1.5-.3 1.6l-5.6.9a1 1 0 0 0-.7.5l-2.6 5c-.4.8-1.5.6-1.6-.3L4.4 4.1c-.1-.8.5-1.3 1.1-.9Z" />
  </svg>
);

export const Painel = () => (
  <svg {...base}>
    <rect x="3" y="4.5" width="18" height="15" rx="2.6" />
    <path d="M9.6 4.5v15" />
  </svg>
);

export const Caixa = () => (
  <svg {...base}>
    <path d="M12 3.2 20.2 7v10L12 20.8 3.8 17V7L12 3.2Z" />
    <path d="M3.9 7.1 12 11l8.1-3.9M12 11v9.6" />
  </svg>
);

export const Mapa = () => (
  <svg {...base}>
    <path d="M9 4 3.4 6.2v13.4L9 17.4l6 2.2 5.6-2.2V4L15 6.2 9 4Z" />
    <path d="M9 4v13.4M15 6.2v13.4" />
  </svg>
);

export const Camadas = () => (
  <svg {...base}>
    <path d="m12 3 8.5 4.5L12 12 3.5 7.5 12 3Z" />
    <path d="m3.5 12.2 8.5 4.5 8.5-4.5" />
    <path d="m3.5 16.7 8.5 4.5 8.5-4.5" />
  </svg>
);

export const Mais = () => (
  <svg {...base}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const Menos = () => (
  <svg {...base}>
    <path d="M5 12h14" />
  </svg>
);

export const Fechar = () => (
  <svg {...base} strokeWidth={2.4}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const Sol = () => (
  <svg {...base}>
    <circle cx="12" cy="12" r="4.5" />
    <path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5 5l1.7 1.7M17.3 17.3 19 19M19 5l-1.7 1.7M6.7 17.3 5 19" />
  </svg>
);

export const Lua = () => (
  <svg {...base}>
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" />
  </svg>
);

/* Simbolo oficial da marca — geometria do kortex-brand-system, identica a
   `#kx-symbol` da landing. Herda cor por currentColor, entao serve nos dois
   temas sem duplicata. */
export const Marca = () => (
  <svg viewBox="0 0 180 180" aria-hidden="true" className="marca-simbolo">
    <g
      fill="none"
      stroke="currentColor"
      strokeWidth="18"
      strokeLinejoin="miter"
      strokeLinecap="square"
    >
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
);

/* Logotipo oficial — `#kx-wordmark`. E geometria propria, nao texto: escrever
   "Kortex" numa fonte qualquer seria uma aproximacao do logotipo, nao ele. */
export const MarcaNome = () => (
  <svg viewBox="-8 0 1200 120" aria-hidden="true" className="marca-nome">
    <g fill="currentColor">
      <path d="M0 6h27v108H0zM27 58 90 6h42L68 59l70 55H94L27 63z" />
      <path
        fillRule="evenodd"
        d="M198 6h116c24 0 39 14 39 36v36c0 22-15 36-39 36H198c-24 0-39-14-39-36V42c0-22 15-36 39-36Zm4 24c-10 0-15 5-15 14v32c0 9 5 14 15 14h108c10 0 15-5 15-14V44c0-9-5-14-15-14H202Z"
      />
      <path
        fillRule="evenodd"
        d="M405 6h125c25 0 39 13 39 34v14c0 18-10 29-28 33l37 27h-43l-34-26h-68v26h-28V6Zm28 24v35h93c10 0 15-5 15-13v-9c0-8-5-13-15-13h-93Z"
      />
      <path d="M614 6h164v25h-68v83h-28V31h-68z" />
      <path d="M821 6h159v24H849v19h119v23H849v18h131v24H821z" />
      <path d="m1020 6 63 52-65 56h42l45-39 46 39h42l-66-56 62-52h-42l-42 35-43-35z" />
    </g>
  </svg>
);

export const Sino = () => (
  <svg {...base}>
    <path d="M18 8.7a6 6 0 1 0-12 0c0 5.2-1.7 6.7-1.7 6.7h15.4S18 13.9 18 8.7Z" />
    <path d="M13.7 19a2 2 0 0 1-3.4 0" />
  </svg>
);

export const Vassoura = () => (
  <svg {...base}>
    <path d="M14.5 3.5 20.5 9.5" />
    <path d="M13 5 5.5 12.5l6 6L19 11" />
    <path d="M5.5 12.5 3 21l8.5-2.5" />
  </svg>
);

export const Seta = () => (
  <svg {...base}>
    <path d="M5 12h13M13 6.5 18.5 12 13 17.5" />
  </svg>
);
