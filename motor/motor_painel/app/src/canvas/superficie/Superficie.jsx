import { useEffect, useRef, useState } from 'react';

/* Passo da grade em unidades de mundo. Isso e nivel de detalhe DA GRADE, nao o
   LOD de conteudo do §6.2 — aquele e da camada de massa e nao se implementa a
   mao. */
const PASSO_BASE = 24;

/* O quadrado e FIXO em unidades de mundo: nao subdivide nem se agrupa, so
   acompanha a escala. Isso so fecha porque o teto de zoom e 300% (ESCALA_MAX) —
   a 300% o passo e 72px, ainda legivel, entao nunca ha o quadro gigante que
   obrigaria a subdividir. Subdivisao trocaria de passo no meio do gesto, e o
   salto e mais incomodo que a densidade que ele evita.
   Se o teto subir, esta funcao volta a precisar de subdivisao. */
function passoNaTela(escala) {
  return PASSO_BASE * escala;
}

/* Desvanecimento ao afastar. Faixa estreita de proposito: no Maestri a grade
   esta visivel a 42% e ausente a 36%, o que e quase corte seco — a rampa curta
   reproduz isso sem o estalo de ligar/desligar. */
const ZOOM_CHEIO = 0.44;
const ZOOM_VAZIO = 0.36;

function opacidadeGrade(escala) {
  if (escala >= ZOOM_CHEIO) return 1;
  if (escala <= ZOOM_VAZIO) return 0;
  return (escala - ZOOM_VAZIO) / (ZOOM_CHEIO - ZOOM_VAZIO);
}

export function Superficie({ vp, deslocar, ampliarEm, children }) {
  const ref = useRef(null);
  const arrasto = useRef(null);
  const [arrastando, setArrastando] = useState(false);

  /* Listener nativo, nao onWheel do React: precisamos de preventDefault e o
     React registra wheel como passivo, onde preventDefault e ignorado. Sem
     isso, ctrl+scroll dispara o zoom do navegador por cima do nosso. */
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    const aoRolar = (evento) => {
      evento.preventDefault();
      const caixa = el.getBoundingClientRect();
      const px = evento.clientX - caixa.left;
      const py = evento.clientY - caixa.top;
      if (evento.ctrlKey || evento.metaKey) {
        /* Pinca de trackpad chega como wheel+ctrl. */
        ampliarEm(Math.exp(-evento.deltaY / 260), px, py);
      } else {
        deslocar(-evento.deltaX, -evento.deltaY);
      }
    };

    el.addEventListener('wheel', aoRolar, { passive: false });
    return () => el.removeEventListener('wheel', aoRolar);
  }, [deslocar, ampliarEm]);

  const aoApertar = (evento) => {
    /* Botao esquerdo (ferramenta selecionar, sem objeto sob o cursor) e botao
       do meio arrastam a superficie. */
    if (evento.button !== 0 && evento.button !== 1) return;
    evento.currentTarget.setPointerCapture(evento.pointerId);
    arrasto.current = { x: evento.clientX, y: evento.clientY };
    setArrastando(true);
  };

  const aoMover = (evento) => {
    if (!arrasto.current) return;
    deslocar(evento.clientX - arrasto.current.x, evento.clientY - arrasto.current.y);
    arrasto.current = { x: evento.clientX, y: evento.clientY };
  };

  const aoSoltar = (evento) => {
    if (!arrasto.current) return;
    evento.currentTarget.releasePointerCapture(evento.pointerId);
    arrasto.current = null;
    setArrastando(false);
  };

  const passo = passoNaTela(vp.escala);
  const grade = {
    backgroundImage: [
      'linear-gradient(to right, var(--grade) 1px, transparent 1px)',
      'linear-gradient(to bottom, var(--grade) 1px, transparent 1px)',
      'linear-gradient(to right, var(--grade-forte) 1px, transparent 1px)',
      'linear-gradient(to bottom, var(--grade-forte) 1px, transparent 1px)',
    ].join(','),
    backgroundSize: [
      `${passo}px ${passo}px`,
      `${passo}px ${passo}px`,
      `${passo * 4}px ${passo * 4}px`,
      `${passo * 4}px ${passo * 4}px`,
    ].join(','),
    backgroundPosition: `${vp.x}px ${vp.y}px`,
    /* Camada propria so para a grade poder ter opacidade sem levar o conteudo
       do mundo junto. */
    opacity: opacidadeGrade(vp.escala),
  };

  return (
    <div
      ref={ref}
      className="superficie"
      data-arrastando={arrastando ? 'sim' : 'nao'}
      onPointerDown={aoApertar}
      onPointerMove={aoMover}
      onPointerUp={aoSoltar}
      onPointerCancel={aoSoltar}
    >
      <div className="grade" style={grade} />
      <div
        className="mundo"
        style={{ transform: `translate(${vp.x}px, ${vp.y}px) scale(${vp.escala})` }}
      >
        <div className="origem" />
        {children}
      </div>
    </div>
  );
}
