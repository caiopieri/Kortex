import { useRef, useState } from 'react';

/* Painel flutuante que se arrasta pelo pegador.
 *
 * Extraido porque agora sao DOIS paineis com o mesmo comportamento (projeto e
 * notificacoes) e a logica de limite e chata o bastante para nao valer copiar:
 * dois donos da mesma regra de borda viram duas regras diferentes na primeira
 * correcao.
 *
 * O deslocamento sai como variaveis CSS `--dx`/`--dy`, nao como `transform`
 * inline: a transicao de entrada tambem escreve em `transform` e as duas se
 * anulariam. Assim a saida compoe o arrasto em vez de brigar com ele.
 */

const MARGEM = 8;

/* Limita o deslocamento para o painel nao sair da janela. Sem isto um arrasto
   longo o joga para fora e nao ha como traze-lo de volta. */
function limitar(atual, dx, dy, el) {
  if (!el) return { x: atual.x + dx, y: atual.y + dy };
  const r = el.getBoundingClientRect();
  return {
    x: atual.x + Math.min(window.innerWidth - MARGEM - r.right, Math.max(MARGEM - r.left, dx)),
    y: atual.y + Math.min(window.innerHeight - MARGEM - r.bottom, Math.max(MARGEM - r.top, dy)),
  };
}

export function useArrastavel() {
  const [desloc, setDesloc] = useState({ x: 0, y: 0 });
  const [arrastando, setArrastando] = useState(false);
  const alvo = useRef(null);
  const ultimo = useRef(null);

  const pegador = {
    onPointerDown: (evento) => {
      evento.currentTarget.setPointerCapture(evento.pointerId);
      ultimo.current = { x: evento.clientX, y: evento.clientY };
      setArrastando(true);
    },
    onPointerMove: (evento) => {
      if (!ultimo.current) return;
      const dx = evento.clientX - ultimo.current.x;
      const dy = evento.clientY - ultimo.current.y;
      ultimo.current = { x: evento.clientX, y: evento.clientY };
      setDesloc((d) => limitar(d, dx, dy, alvo.current));
    },
    onPointerUp: (evento) => {
      if (!ultimo.current) return;
      evento.currentTarget.releasePointerCapture(evento.pointerId);
      ultimo.current = null;
      setArrastando(false);
    },
    onDoubleClick: () => setDesloc({ x: 0, y: 0 }),
    title: 'Arrastar · dois cliques devolve ao canto',
  };
  pegador.onPointerCancel = pegador.onPointerUp;

  return {
    alvo,
    arrastando,
    pegador,
    estilo: { '--dx': `${desloc.x}px`, '--dy': `${desloc.y}px` },
  };
}
