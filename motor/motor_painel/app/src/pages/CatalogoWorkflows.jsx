import { useState, useMemo } from 'react';
import { usePoll, getCatalogo } from '../api.js';
import { linhasDoCatalogo, VERSAO_AUSENTE } from './catalogoRotas.js';

/* Rotas do registro — NÃO é o catálogo de workflows (issue #23).
 *
 * A tela se chamava "Catálogo de Workflows" e mostrava outra coisa: o
 * `/dados/catalogo` lê `exemplos/registro/*.md` e filtra por `tipo: rota`. São
 * rotas de modelo, e o próprio `docs/ESTADO.md` §E já registra isso — "hoje o
 * registro cataloga rotas de modelo, não templates".
 *
 * O catálogo de templates de workflow versionado com evidência é o V7 e NÃO
 * EXISTE. A tela diz isso, em vez de deixar o nome sugerir que existe.
 *
 * Aqui não há filtro por status. Não porque foi removido para simplificar: o
 * registro não declara status, e o filtro anterior só casava com os cinco
 * workflows inventados no fallback.
 */
export default function CatalogoWorkflows() {
  const { data: catalogo, error } = usePoll(getCatalogo);
  const [selected, setSelected] = useState(null);

  const items = useMemo(() => linhasDoCatalogo(catalogo), [catalogo]);

  const cabecalho = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span className="title" style={{ fontSize: 20 }}>Rotas do registro</span>
      <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
        exemplos/registro · tipo: rota
      </span>
      <div style={{ flex: 1 }}></div>
      <span className="btn btn-primary btn-sm" onClick={() => { window.location.hash = '/nova-missao'; }}>+ Nova missão</span>
    </div>
  );

  if (error) return (
    <>
      {cabecalho}
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </>
  );

  const detail = selected ? items.find(i => i.id === selected) : null;

  return (
    <>
      {cabecalho}

      {/* O que esta tela NÃO é. Fica acima da lista, não em rodapé: o nome
          antigo prometia catálogo de workflow e alguém vai chegar aqui
          procurando por ele. */}
      <div className="card" style={{ padding: '10px 14px', marginTop: 14, borderStyle: 'dashed' }}>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)', lineHeight: 1.7 }}>
          Estas são <b style={{ color: 'var(--text2)' }}>rotas de modelo</b>, não templates de
          workflow. O catálogo de templates versionado com evidência é o V7 e ainda não existe —
          nem no motor, nem aqui. Enquanto não existir, esta tela não vai fingir que existe.
        </span>
      </div>

      {items.length === 0 && !catalogo && (
        <div className="card" style={{ padding: 28, marginTop: 16, textAlign: 'center' }}>
          <span className="mono" style={{ fontSize: 11.5, color: 'var(--text3)' }}>carregando…</span>
        </div>
      )}

      {/* Vazio declarado, na forma do Runners.jsx: o painel diz que não tem
          fonte, em vez de desenhar conteúdo de exemplo. */}
      {items.length === 0 && catalogo && (
        <div className="card" style={{ padding: 28, marginTop: 16, textAlign: 'center' }}>
          <div className="title" style={{ fontSize: 15, color: 'var(--text)' }}>
            Nenhuma rota no registro
          </div>
          <div className="mono" style={{ fontSize: 11.5, color: 'var(--text2)', lineHeight: 1.7, maxWidth: 460, margin: '10px auto 0' }}>
            O painel lê <span className="mono">exemplos/registro/*.md</span> e mostra as entradas
            com <span className="mono">tipo: rota</span>. Não há nenhuma legível agora, então não
            há o que mostrar aqui — e o painel não vai inventar.
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: 'var(--text3)', marginTop: 12 }}>
            As entidades executoras do mesmo registro estão em{' '}
            <span className="lnk" onClick={() => { window.location.hash = '/inventario'; }}>Inventário</span>.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: detail ? '1fr 1fr' : '1fr', gap: 16, marginTop: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(rota => (
            <div
              key={rota.id}
              className="card"
              style={{ padding: '12px 14px', cursor: 'pointer', borderColor: selected === rota.id ? 'var(--accent)' : undefined }}
              onClick={() => setSelected(rota.id === selected ? null : rota.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="title" style={{ fontSize: 14, flex: 1 }}>{rota.nome}</span>
                <span className="mono" style={{ fontSize: 9, color: 'var(--text3)' }}>
                  {rota.versao ? `v${rota.versao}` : VERSAO_AUSENTE}
                </span>
              </div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>{rota.descricao}</div>
              <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
                  {rota.subagentes.length > 0
                    ? `subagentes: ${rota.subagentes.join(', ')}`
                    : 'subagentes não declarados no registro'}
                </span>
              </div>
            </div>
          ))}
        </div>

        {detail && (
          <div className="card" style={{ padding: 16, alignSelf: 'flex-start' }}>
            <span className="num" style={{ color: 'var(--accent)', marginBottom: 12, display: 'block' }}>Detalhes</span>
            <div className="title" style={{ fontSize: 16, marginBottom: 8 }}>{detail.nome}</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.6, marginBottom: 12 }}>{detail.descricao}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>id</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>{detail.id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>versão</span>
                <span className="mono" style={{ fontSize: 10, color: detail.versao ? 'var(--text2)' : 'var(--text3)' }}>
                  {detail.versao ? `v${detail.versao}` : VERSAO_AUSENTE}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>subagentes</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>{detail.subagentes.length}</span>
              </div>
              {detail.subagentes.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                  {detail.subagentes.map(s => (
                    <span key={s} className="pill" style={{ fontSize: 9 }}>{s}</span>
                  ))}
                </div>
              )}
            </div>
            <div style={{ marginTop: 16 }}>
              <span className="btn btn-primary btn-sm" onClick={() => { window.location.hash = '/nova-missao'; }}>Disparar uma missão →</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
