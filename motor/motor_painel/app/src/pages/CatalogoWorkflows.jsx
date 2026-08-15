import { useState, useMemo } from 'react';
import { usePoll, getCatalogo } from '../api.js';

export default function CatalogoWorkflows() {
  const { data: catalogo, error } = usePoll(getCatalogo);
  const [filter, setFilter] = useState('todos');
  const [selected, setSelected] = useState(null);

  /* Fallback data when API has no catalogo */
  const items = useMemo(() => {
    if (catalogo && Array.isArray(catalogo) && catalogo.length > 0) return catalogo;
    return [
      { id: 'pesquisa', nome: 'Pesquisa & Síntese', rota: 'pesquisa', descricao: 'Fan-out de pesquisadores + síntese final avaliada', nos: 7, versao: '1.2', tags: ['pesquisa', 'síntese'], criado: '2026-06-28', status: 'certificado' },
      { id: 'forja', nome: 'Forja · Software', rota: 'forja', descricao: 'Pipeline de código: planejador → executor → verificador → gate', nos: 6, versao: '2.0', tags: ['código', 'software', 'testes'], criado: '2026-06-15', status: 'certificado' },
      { id: 'construcao', nome: 'Construção · Documentos', rota: 'construção', descricao: 'Geração de documentos longos com revisão e formatação', nos: 4, versao: '1.0', tags: ['documentos', 'redação'], criado: '2026-07-01', status: 'beta' },
      { id: 'hardware', nome: 'Hardware · Impressão 3D', rota: 'hardware', descricao: 'Pipeline de fatiamento, validação e envio a impressora', nos: 4, versao: '0.9', tags: ['hardware', '3d'], criado: '2026-07-05', status: 'experimental' },
      { id: 'anuncio', nome: 'Anúncio & Creative', rota: 'criativo', descricao: 'Geração de copy + imagens + variações A/B', nos: 5, versao: '1.1', tags: ['marketing', 'creative'], criado: '2026-06-20', status: 'certificado' },
    ];
  }, [catalogo]);

  const filtered = useMemo(() => {
    if (filter === 'todos') return items;
    return items.filter(i => i.status === filter);
  }, [items, filter]);

  if (error) return (
    <div>
      <span className="num">Catálogo de Workflows</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  const statusColor = (s) => {
    if (s === 'certificado') return 'var(--green)';
    if (s === 'beta') return 'var(--blue)';
    return 'var(--amber)';
  };

  const detail = selected ? items.find(i => i.id === selected) : null;

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Catálogo de Workflows</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>templates · registry</span>
        <div style={{ flex: 1 }}></div>
        <span className="btn btn-primary btn-sm" onClick={() => { window.location.hash = '/nova-missao'; }}>+ Nova missão</span>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        {['todos', 'certificado', 'beta', 'experimental'].map(f => (
          <span key={f} className={`pill${filter === f ? ' on' : ''}`} onClick={() => setFilter(f)}>{f}</span>
        ))}
      </div>

      {/* Grid + detail */}
      <div style={{ display: 'grid', gridTemplateColumns: detail ? '1fr 1fr' : '1fr', gap: 16, marginTop: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(wf => (
            <div
              key={wf.id}
              className="card"
              style={{ padding: '12px 14px', cursor: 'pointer', borderColor: selected === wf.id ? 'var(--accent)' : undefined }}
              onClick={() => setSelected(wf.id === selected ? null : wf.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="title" style={{ fontSize: 14, flex: 1 }}>{wf.nome}</span>
                <span className="mono" style={{ fontSize: 9, color: statusColor(wf.status), border: '1px solid', borderRadius: 2, padding: '1px 6px' }}>{wf.status}</span>
              </div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>{wf.descricao}</div>
              <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>rota: {wf.rota}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>~{wf.nos} nós</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>v{wf.versao}</span>
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
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>rota</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>{detail.rota}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>nós</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>~{detail.nos}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>versão</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>v{detail.versao}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>criado</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>{detail.criado}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>status</span>
                <span className="mono" style={{ fontSize: 10, color: statusColor(detail.status) }}>{detail.status}</span>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                {(detail.tags || []).map(t => (
                  <span key={t} className="pill" style={{ fontSize: 9 }}>{t}</span>
                ))}
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <span className="btn btn-primary btn-sm" onClick={() => { window.location.hash = '/nova-missao'; }}>Disparar com este workflow →</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
