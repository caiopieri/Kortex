import Superficie from '../canvas/Canvas.jsx';

/* A aba Canvas. O painel e um app de PAGINAS com rolagem; o canvas e uma
   superficie que ocupa tudo e trata a propria rolagem. Por isso a rota
   `/canvas` marca o `<main>` como cheio (sem padding, sem overflow) em vez de
   o canvas tentar escapar do container por conta propria. */
export default function Canvas({ modo }) {
  return <Superficie modo={modo} />;
}
