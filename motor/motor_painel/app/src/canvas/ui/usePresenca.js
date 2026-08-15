import { useEffect, useRef, useState } from 'react';

/* Presenca com saida REVERSIVEL.
 *
 * O problema que isto resolve: React desmonta na hora que `aberto` vira falso,
 * e sem o elemento na tela nao existe animacao de saida. Entao o componente
 * fica montado ate a saida terminar — e, se `aberto` voltar a ser verdadeiro no
 * meio, o desmonte e cancelado.
 *
 * Por que TRANSICAO e nao keyframe: keyframe tem inicio e fim fixos, e
 * interromper no meio faz o elemento saltar para o comeco da animacao
 * contraria. Transicao CSS parte SEMPRE do valor computado no instante da
 * troca, entao inverter no meio do fechamento continua de onde estava, so que
 * abrindo. E exatamente o comportamento pedido, e sai de graca do navegador —
 * desde que ninguem troque `transition` por `animation` aqui.
 *
 * Devolve `montado` (renderiza ou nao) e `dentro` (o estado visual alvo).
 */
export function usePresenca(aberto, duracao = 200) {
  const [montado, setMontado] = useState(aberto);
  const [dentro, setDentro] = useState(aberto);
  const relogio = useRef(0);
  const quadro = useRef(0);
  const jaPintado = useRef(false);

  useEffect(() => {
    clearTimeout(relogio.current);
    cancelAnimationFrame(quadro.current);

    if (aberto) {
      setMontado(true);
      if (jaPintado.current) {
        /* Ja esta na tela — provavelmente saindo. Inverte NO MESMO QUADRO: a
           transicao continua do valor atual, so que no outro sentido. Esperar
           um quadro aqui deixaria o painel apagando mais um pouco antes de
           voltar, e a reversao ficaria com um degrau. */
        setDentro(true);
      } else {
        /* Primeira montagem: o elemento precisa ser pintado em "fora" antes de
           ir para "dentro", senao nao ha de onde transicionar e ele aparece
           pronto. */
        quadro.current = requestAnimationFrame(() => {
          jaPintado.current = true;
          setDentro(true);
        });
      }
    } else {
      setDentro(false);
      relogio.current = setTimeout(() => {
        setMontado(false);
        jaPintado.current = false;
      }, duracao);
    }
  }, [aberto, duracao]);

  useEffect(
    () => () => {
      clearTimeout(relogio.current);
      cancelAnimationFrame(quadro.current);
    },
    [],
  );

  return { montado, dentro };
}
