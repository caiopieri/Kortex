import { useCallback, useEffect, useRef, useState } from 'react';

/* A INTERFACE FINA sobre o renderizador.
 *
 * `DECISAO-canvas-e-operacao.md` §6.3 exige que a escolha de renderizador nao
 * seja porta de mao unica, e §6.2 exige UMA fonte de coordenadas. Este modulo e
 * as duas coisas: quem desenha (hoje DOM+transform, amanha WebGL/tldraw/PixiJS)
 * consome `vp` e devolve gestos por estas funcoes. Nenhum componente calcula
 * coordenada por conta propria.
 *
 * O viewport e o mapa mundo -> tela:  tela = mundo * escala + (x, y)
 */

export const ESCALA_MIN = 0.1;
export const ESCALA_MAX = 3;

const limitar = (v) => Math.min(ESCALA_MAX, Math.max(ESCALA_MIN, v));

/* easeOutQuart — parte rapido e pousa devagar. E a curva do sistema de marca
   (`cubic-bezier(.22,.8,.24,1)`) na forma que da para escrever em JS. */
const suavizar = (t) => 1 - (1 - t) ** 4;

const reduzMovimento = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function useViewport(inicial = { x: 0, y: 0, escala: 1 }) {
  const [vp, setVp] = useState(inicial);

  /* Espelho sincrono do viewport. As animacoes precisam do valor de AGORA para
     montar o quadro, e `vp` da closure e o do render que agendou. */
  const vpAgora = useRef(vp);
  vpAgora.current = vp;

  const quadroPendente = useRef(0);

  const cancelarAnimacao = useCallback(() => {
    if (quadroPendente.current) {
      cancelAnimationFrame(quadroPendente.current);
      quadroPendente.current = 0;
    }
  }, []);

  /* Animacao aberta ao gesto: qualquer manipulacao direta cancela. Animacao que
     disputa com o dedo do usuario e pior do que animacao nenhuma. */
  const animar = useCallback(
    (quadro, duracao = 260) => {
      cancelarAnimacao();
      if (reduzMovimento()) {
        setVp(quadro(1));
        return;
      }
      const inicio = performance.now();
      const passo = (agora) => {
        const t = Math.min(1, (agora - inicio) / duracao);
        setVp(quadro(suavizar(t)));
        quadroPendente.current = t < 1 ? requestAnimationFrame(passo) : 0;
      };
      quadroPendente.current = requestAnimationFrame(passo);
    },
    [cancelarAnimacao],
  );

  useEffect(() => cancelarAnimacao, [cancelarAnimacao]);

  const deslocar = useCallback(
    (dx, dy) => {
      cancelarAnimacao();
      setVp((v) => ({ ...v, x: v.x + dx, y: v.y + dy }));
    },
    [cancelarAnimacao],
  );

  /* Zoom ancorado: o ponto de tela sob o cursor tem que continuar sobre o mesmo
     ponto do mundo. Sem a ancora o conteudo foge da mao em zoom de trackpad. */
  const ampliarEm = useCallback(
    (fator, ancoraX, ancoraY) => {
      cancelarAnimacao();
      setVp((v) => {
        const escala = limitar(v.escala * fator);
        if (escala === v.escala) return v;
        const k = escala / v.escala;
        return {
          escala,
          x: ancoraX - (ancoraX - v.x) * k,
          y: ancoraY - (ancoraY - v.y) * k,
        };
      });
    },
    [cancelarAnimacao],
  );

  const definirEscala = useCallback((escala, ancoraX, ancoraY) => {
    setVp((v) => {
      const nova = limitar(escala);
      if (nova === v.escala) return v;
      const k = nova / v.escala;
      return {
        escala: nova,
        x: ancoraX - (ancoraX - v.x) * k,
        y: ancoraY - (ancoraY - v.y) * k,
      };
    });
  }, []);

  /* Zoom animado. A escala interpola em ESCALA LOGARITMICA, nao linear: de 50%
     a 200% o meio percebido e 100%, nao 125%. E o x/y sai da ancora a cada
     quadro, entao o ponto sob o cursor fica cravado o tempo todo — interpolar
     x/y direto faria o conteudo deslizar por baixo do dedo. */
  const escalaSuave = useCallback(
    (escalaAlvo, ancoraX, ancoraY, duracao = 260) => {
      const de = vpAgora.current;
      const para = limitar(escalaAlvo);
      if (Math.abs(para - de.escala) < 1e-6) return;
      const passoLog = Math.log(para) - Math.log(de.escala);
      animar((t) => {
        const escala = Math.exp(Math.log(de.escala) + passoLog * t);
        const k = escala / de.escala;
        return {
          escala,
          x: ancoraX - (ancoraX - de.x) * k,
          y: ancoraY - (ancoraY - de.y) * k,
        };
      }, duracao);
    },
    [animar],
  );

  const ampliarSuave = useCallback(
    (fator, ancoraX, ancoraY) => escalaSuave(vpAgora.current.escala * fator, ancoraX, ancoraY),
    [escalaSuave],
  );

  const reiniciar = useCallback(() => setVp({ x: 0, y: 0, escala: 1 }), []);

  /* Coloca um ponto do mundo no centro da tela, sem mexer na escala. E o que o
     minimapa usa para levar de volta a origem — animado, senao a vista teleporta
     e o operador perde a nocao de para onde foi. Um pouco mais longo que o zoom
     porque o percurso costuma ser maior. */
  const centralizarEm = useCallback(
    (mundoX, mundoY, larguraTela, alturaTela) => {
      const de = vpAgora.current;
      const alvoX = larguraTela / 2 - mundoX * de.escala;
      const alvoY = alturaTela / 2 - mundoY * de.escala;
      animar(
        (t) => ({
          escala: de.escala,
          x: de.x + (alvoX - de.x) * t,
          y: de.y + (alvoY - de.y) * t,
        }),
        340,
      );
    },
    [animar],
  );

  /* Conversao publica tela -> mundo. Quem for colocar objeto no canvas usa
     ESTA funcao; e o ponto onde a fonte unica de coordenadas se sustenta. */
  const paraMundo = useCallback(
    (telaX, telaY) => ({ x: (telaX - vp.x) / vp.escala, y: (telaY - vp.y) / vp.escala }),
    [vp],
  );

  return {
    vp,
    deslocar,
    ampliarEm,
    ampliarSuave,
    escalaSuave,
    definirEscala,
    reiniciar,
    centralizarEm,
    paraMundo,
  };
}
