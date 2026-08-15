/* Agentes — quem a fabrica pode chamar, e o que de fato chamou.
 *
 * Duas fontes reais, nada alem delas:
 *   /dados/conexoes  -> executores configurados no registry + credencial
 *   /dados/agentes   -> chamadas e falhas derivadas do log.jsonl
 *
 * A versao anterior desta tela era um blueprint: seis personas nomeadas
 * (Orion, Vesta, Atena...) com latencia, taxa de aprovacao, escada de tiers,
 * status de provedor e mensagem de chat — tudo constante em codigo, nada
 * vindo do motor. Foi removida inteira. Metrica que o log nao emite nao
 * aparece aqui; quando o motor passar a emitir, a coluna entra.
 */

import { useMemo } from 'react';
import { usePoll, getConexoes, getAgents } from '../api.js';

/* tem_credencial tem TRES estados. null nao e "nao" — e "o painel nao sabe
   comprovar este transporte". Mesmo contrato usado em Conexoes. */
function credencial(tem) {
  if (tem === true) return { cor: 'var(--green)', texto: 'credencial comprovada' };
  if (tem === false) return { cor: 'var(--red)', texto: 'sem credencial' };
  return { cor: 'var(--text3)', texto: 'não verificável' };
}

export default function Agentes() {
  const { data: conexoes, error } = usePoll(getConexoes);
  const { data: agentes } = usePoll(getAgents);

  /* Junta o configurado com o observado. Um executor pode existir no registry
     e nunca ter sido chamado; e o log pode citar um executor que saiu do
     registry. Os dois casos aparecem — sumir com qualquer um esconderia
     divergencia real entre configuracao e execucao. */
  const linhas = useMemo(() => {
    const porId = new Map();
    (conexoes || []).forEach((c) => {
      porId.set(c.id, {
        id: c.id,
        tipo: c.tipo,
        tem_credencial: c.tem_credencial,
        origem: c.origem,
        papel: null,
        chamadas: 0,
        falhas: 0,
        registrado: true,
      });
    });
    (agentes || []).forEach((a) => {
      const atual = porId.get(a.id);
      if (atual) {
        atual.papel = a.papel;
        atual.chamadas = a.chamadas || 0;
        atual.falhas = a.falhas || 0;
      } else {
        porId.set(a.id, {
          id: a.id,
          tipo: null,
          tem_credencial: null,
          origem: null,
          papel: a.papel,
          chamadas: a.chamadas || 0,
          falhas: a.falhas || 0,
          registrado: false,
        });
      }
    });
    return [...porId.values()].sort((a, b) => b.chamadas - a.chamadas || a.id.localeCompare(b.id));
  }, [conexoes, agentes]);

  const shape = (l) => {
    if (l.falhas > 0) return 'sh red';
    if (l.chamadas > 0) return 'sh green';
    if (l.tem_credencial === false) return 'sh amber';
    return 'sh idle';
  };

  if (error) return (
    <div>
      <span className="num">Agentes</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!conexoes) return (
    <div>
      <span className="num">Agentes</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando agentes…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Agentes</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
          executores do registry · atividade do log
        </span>
        <div style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>
          {linhas.length} {linhas.length === 1 ? 'executor' : 'executores'}
        </span>
      </div>

      {linhas.length === 0 ? (
        <div className="card" style={{ padding: 20, textAlign: 'center', marginTop: 16 }}>
          <span className="mono" style={{ color: 'var(--text3)' }}>
            Sem registry e sem execução no log. Nenhum agente para mostrar.
          </span>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
          {linhas.map((l) => {
            const cred = credencial(l.tem_credencial);
            return (
              <div key={l.id} className="card" style={{ padding: '14px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className={shape(l)}></span>
                  <span className="title" style={{ fontSize: 15 }}>{l.id}</span>
                  {l.tipo && (
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{l.tipo}</span>
                  )}
                  {!l.registrado && (
                    <span className="chip" style={{ fontSize: 9, fontWeight: 'normal' }}>
                      fora do registry · visto só no log
                    </span>
                  )}
                  <div style={{ flex: 1 }} />
                  {l.registrado && (
                    <span className="mono" style={{ fontSize: 10, color: cred.cor }}>{cred.texto}</span>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 22, marginTop: 10 }}>
                  <div>
                    <span className="eyebrow" style={{ fontSize: 8 }}>Papel</span>
                    <div className="mono" style={{ fontSize: 11, color: l.papel ? 'var(--text2)' : 'var(--text3)' }}>
                      {l.papel || 'não observado no log'}
                    </div>
                  </div>
                  <div>
                    <span className="eyebrow" style={{ fontSize: 8 }}>Chamadas</span>
                    <div className="mono" style={{ fontSize: 11, color: l.chamadas > 0 ? 'var(--blue)' : 'var(--text3)' }}>
                      {l.chamadas}
                    </div>
                  </div>
                  <div>
                    <span className="eyebrow" style={{ fontSize: 8 }}>Falhas</span>
                    <div className="mono" style={{ fontSize: 11, color: l.falhas > 0 ? 'var(--red)' : 'var(--text3)' }}>
                      {l.falhas}
                    </div>
                  </div>
                  {l.origem && (
                    <div style={{ marginLeft: 'auto' }}>
                      <span className="eyebrow" style={{ fontSize: 8 }}>Origem</span>
                      <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{l.origem}</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
