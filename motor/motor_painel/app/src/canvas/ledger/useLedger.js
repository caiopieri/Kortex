import { useCallback, useEffect, useRef, useState } from 'react';
import { adaptadorPainel, criarLeitor, FONTES } from './ler.js';
import { projetarRun, segmentarRuns } from './projetar.js';

/* Estado da leitura do ledger.
 *
 * Sem polling automatico: o ledger nao notifica, e reler em laco fingiria tempo
 * real. A recarga e explicita e INCREMENTAL — o leitor guarda o deslocamento em
 * bytes e pede so o que veio depois. O selo mostra a hora da leitura para
 * ninguem confundir o que esta na tela com agora.
 *
 * A reprojecao ainda roda sobre tudo o que ja foi lido. Isso e barato e correto:
 * o custo que importava era o de trazer 355 kB pela rede a cada tique, e esse
 * sumiu. Projetar incrementalmente exigiria estado por run e so vale quando
 * houver medida dizendo que precisa.
 */
export function useLedger(adaptador = adaptadorPainel) {
  const [estado, setEstado] = useState({ fase: 'carregando' });
  const leitor = useRef(criarLeitor(FONTES[0]));

  const recarregar = useCallback(async () => {
    setEstado((a) => ({ ...a, fase: a.fase === 'pronto' ? 'relendo' : 'carregando' }));
    try {
      const leitura = await adaptador.ler(leitor.current);
      leitor.current = leitura;
      /* O adaptador do painel entrega a topologia canônica por run. A
         segmentação local só permanece para adaptadores crus que não têm o
         contrato de /dados; eles não podem inventar nós/arestas. */
      const runsBrutas = Array.isArray(leitura.runs)
        ? leitura.runs
        : segmentarRuns(leitura.eventos);
      const runs = runsBrutas.map(projetarRun);
      setEstado({ fase: 'pronto', leitura, runs, adaptador });
    } catch (erro) {
      /* Falhar em ler nao pode virar tela vazia sem explicacao: a regra do andon
         vale para a propria superficie. */
      setEstado({ fase: 'erro', motivo: String(erro?.message ?? erro) });
    }
  }, [adaptador]);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  return { ...estado, recarregar };
}
