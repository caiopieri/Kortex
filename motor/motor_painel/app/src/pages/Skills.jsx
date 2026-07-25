/* Skills — papeis que a fabrica sabe exercer.
 *
 * Nao existe catalogo de skill no backend. O que existe de verdade e o campo
 * `papel` de cada entidade do registry (/dados/inventario): a capacidade que
 * aquele executor declara. Esta tela e a projecao disso, cruzada com o uso
 * real vindo de /dados/agentes.
 *
 * Nao ha versao, descricao nem tag — o registry nao declara nada disso, entao
 * a tela nao mostra.
 */

import { useMemo } from 'react';
import { usePoll, getInventario, getAgents } from '../api.js';

export default function Skills() {
  const { data: entidades, error } = usePoll(getInventario);
  const { data: agentes } = usePoll(getAgents);

  /* Um papel pode ser declarado por mais de uma entidade. Agrupa por papel e
     guarda quem o declara. */
  const papeis = useMemo(() => {
    if (!entidades) return [];
    const mapa = new Map();
    entidades.forEach((e) => {
      (e.papel || []).forEach((p) => {
        if (!mapa.has(p)) mapa.set(p, []);
        mapa.get(p).push(e.id);
      });
    });
    /* Uso real: soma chamadas dos agentes cujo papel registrado bate. */
    return [...mapa.entries()]
      .map(([papel, declarantes]) => {
        const usos = (agentes || [])
          .filter((a) => a.papel === papel)
          .reduce((s, a) => s + (a.chamadas || 0), 0);
        return { papel, declarantes, usos };
      })
      .sort((a, b) => a.papel.localeCompare(b.papel));
  }, [entidades, agentes]);

  if (error) return (
    <div>
      <span className="num">Skills</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!entidades) return (
    <div>
      <span className="num">Skills</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando papéis…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Skills</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
          papéis declarados no registry
        </span>
        <div style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>
          {papeis.length} {papeis.length === 1 ? 'papel' : 'papéis'}
        </span>
      </div>

      {papeis.length === 0 ? (
        <div className="card" style={{ padding: 20, textAlign: 'center', marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text3)' }}>
            Nenhuma entidade do registry declara papel.
          </span>
        </div>
      ) : (
        <div className="card" style={{ padding: '4px 16px', marginTop: 16 }}>
          {papeis.map((p) => (
            <div key={p.papel} className="trow">
              <span className={p.usos > 0 ? 'sh green' : 'sh idle'}></span>
              <span style={{ color: 'var(--text)', flex: 1, minWidth: 0 }}>{p.papel}</span>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', flex: 2, minWidth: 0 }}>
                {p.declarantes.join(' · ')}
              </span>
              <span
                className="mono"
                style={{ fontSize: 10, color: p.usos > 0 ? 'var(--blue)' : 'var(--text3)', flex: 'none' }}
              >
                {p.usos} {p.usos === 1 ? 'uso' : 'usos'}
              </span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
