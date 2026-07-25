import { useMemo } from 'react';
import { usePoll, getInventario } from '../api.js';

/* Formas por tipo de entidade — o tipo aqui e a classe da entidade
   (modelo-executor, rota), nao o transporte. */
function shapeFor(tipo) {
  if (tipo === 'modelo-executor') return 'sh green';
  if (tipo === 'rota') return 'sh blue';
  return 'sh idle';
}

export default function Inventario() {
  const { data: entidades, error } = usePoll(getInventario);

  /* Agrupa por tipo, preservando a ordem que o backend ja devolve ordenada. */
  const grupos = useMemo(() => {
    if (!entidades) return [];
    const porTipo = new Map();
    entidades.forEach(e => {
      if (!porTipo.has(e.tipo)) porTipo.set(e.tipo, []);
      porTipo.get(e.tipo).push(e);
    });
    return [...porTipo.entries()].map(([tipo, itens]) => ({ tipo, itens }));
  }, [entidades]);

  if (error) return (
    <div>
      <span className="num">Inventário</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!entidades) return (
    <div>
      <span className="num">Inventário</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando inventário…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Inventário</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
          entidades do registry · fonte em disco
        </span>
        <div style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>
          {entidades.length} {entidades.length === 1 ? 'entidade' : 'entidades'}
        </span>
      </div>

      {entidades.length === 0 ? (
        <div className="card" style={{ padding: 20, textAlign: 'center', marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text3)' }}>
            Sem registry. Nenhuma entidade para mostrar.
          </span>
        </div>
      ) : (
        grupos.map((g, i) => (
          <div key={g.tipo} style={{ marginTop: 16 }}>
            <div className="num" style={{ marginBottom: 10 }}>
              {String(i + 1).padStart(2, '0')} — {g.tipo}
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginLeft: 8 }}>
                {g.itens.length}
              </span>
            </div>
            <div className="card" style={{ padding: '4px 16px' }}>
              {g.itens.map(e => (
                <div key={e.origem} className="trow">
                  <span className={shapeFor(e.tipo)}></span>
                  <span style={{ color: 'var(--text)', flex: 1, minWidth: 0 }}>{e.id}</span>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', flex: 2, minWidth: 0 }}>
                    {e.papel.length > 0
                      ? e.papel.join(' · ')
                      : <span style={{ color: 'var(--text3)' }}>sem papéis declarados</span>}
                  </span>
                  <span className="mono" style={{ fontSize: 9.5, color: 'var(--text3)', flex: 'none' }}>{e.origem}</span>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </>
  );
}
