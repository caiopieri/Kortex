import { useMemo } from 'react';
import { usePoll, fetchDados, getAgents } from '../api.js';

const SKILL_PRESETS = [
  { id: 'pesquisa-web', nome: 'Pesquisa Web', descricao: 'Busca fontes na internet, coleta links e resumos com RAG', versao: '1.3', papel: 'pesquisador', tags: ['web', 'rag', 'fontes'] },
  { id: 'analise-codigo', nome: 'Análise de Código', descricao: 'Lê repositório, identifica padrões e propõe melhorias', versao: '2.0', papel: 'arquiteto', tags: ['código', 'review', 'refactor'] },
  { id: 'redacao-longa', nome: 'Redação Longa', descricao: 'Gera documentos de 2000+ palavras com estrutura editorial', versao: '1.1', papel: 'redator', tags: ['documentos', 'redação'] },
  { id: 'validacao-schema', nome: 'Validação de Schema', descricao: 'Valida JSON/YAML contra schema definido, gera relatório de erros', versao: '1.0', papel: 'validador', tags: ['json', 'yaml', 'schema'] },
  { id: 'testes-unitarios', nome: 'Geração de Testes', descricao: 'Gera suite de testes unitários para código fornecido', versao: '1.2', papel: 'testador', tags: ['testes', 'pytest', 'jest'] },
  { id: 'sintese-dados', nome: 'Síntese de Dados', descricao: 'Agrega múltiplas fontes de pesquisa em relatório consolidado', versao: '1.0', papel: 'synthesizer', tags: ['síntese', 'dados', 'relatório'] },
  { id: 'fatiamento-3d', nome: 'Fatiamento 3D', descricao: 'Prepara modelo 3D para impressão: suportes, infill, G-code', versao: '0.9', papel: 'fatiador', tags: ['3d', 'hardware', 'gcode'] },
  { id: 'copy-criativo', nome: 'Copy Criativo', descricao: 'Gera variações de copy publicitário para A/B testing', versao: '1.1', papel: 'copywriter', tags: ['marketing', 'copy', 'ab-test'] },
];

export default function Skills() {
  const { data: agents } = usePoll(getAgents);
  const { data: fullData } = usePoll(fetchDados);

  /* Enrich skills with real usage data */
  const skills = useMemo(() => {
    const eventos = fullData?.eventos || [];
    return SKILL_PRESETS.map(s => {
      const usage = eventos.filter(ev => ev.executor === s.papel).length;
      return { ...s, usage };
    });
  }, [fullData]);

  /* Active papéis from agents */
  const activePapeis = useMemo(() => {
    if (!agents) return new Set();
    return new Set(Object.keys(agents));
  }, [agents]);

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Skills <span className="chip" style={{ fontSize: 10, fontWeight: 'normal', marginLeft: 8 }}>catálogo estático</span></span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>biblioteca de capacidades · prompts reutilizáveis</span>
      </div>

      {/* Grid of skill cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginTop: 16 }}>
        {skills.map(s => (
          <div key={s.id} className="card" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className={activePapeis.has(s.papel) ? 'sh green' : 'sh idle'}></span>
              <span className="title" style={{ fontSize: 14, flex: 1 }}>{s.nome}</span>
              <span className="mono" style={{ fontSize: 9, color: 'var(--text3)', border: '1px solid var(--border)', borderRadius: 2, padding: '1px 5px' }}>v{s.versao}</span>
            </div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.5 }}>{s.descricao}</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {s.tags.map(t => (
                <span key={t} className="pill" style={{ fontSize: 8, padding: '2px 6px' }}>{t}</span>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 6, borderTop: '1px solid var(--border)' }}>
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>papel: {s.papel}</span>
              <span className="mono" style={{ fontSize: 10, color: s.usage > 0 ? 'var(--blue)' : 'var(--text3)' }}>{s.usage} usos</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
