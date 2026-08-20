import { useMemo } from 'react';
import { usePoll, fetchDados, getOrfaos } from '../api.js';
import { artefatosDoLedger, resumoDeOrfaos } from './artefatos.js';

/* Datahouse — o que a fábrica produziu, e o que ela produziu sem contar (#22).
 *
 * Duas listas que nunca se misturam:
 *   1. o que o ledger explica — derivado de `artefato.atualizou`;
 *   2. o que só existe em disco — declarado como órfão, sem run, sem tipo e
 *      sem tempo, porque nada disso foi registrado por ninguém.
 *
 * Medido no checkout de produção quando a issue #22 foi aberta: 49 artefatos
 * de produto em disco, 40 com evento; 29 workspaces de run, 26 explicados. A lista de cima estava certa e era
 * silenciosamente incompleta — que é o pior estado possível para uma tela de
 * catálogo, porque parece completa.
 */
export default function Datahouse() {
  const { data, error } = usePoll(fetchDados);
  const { data: orfaosBrutos } = usePoll(getOrfaos);

  const artefatos = useMemo(() => artefatosDoLedger(data?.eventos), [data]);
  const orfaos = useMemo(() => resumoDeOrfaos(orfaosBrutos), [orfaosBrutos]);

  /* Agrupa pelo `tipo` DECLARADO no evento, não pela extensão do caminho.
     Extensão é palpite sobre o arquivo; `tipo` é o que o motor afirmou. Hoje
     ele é string livre e vem "python" em tudo — e é honesto que a tela mostre
     essa pobreza em vez de disfarçá-la com extensões. */
  const porTipo = useMemo(() => {
    const m = {};
    artefatos.forEach(a => {
      const t = a.tipo || 'não declarado';
      m[t] = (m[t] || 0) + 1;
    });
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [artefatos]);

  /* `artefato.atualizou` NÃO carrega run: medido no ledger de produção, os 47
     eventos têm exatamente {t, seq, evento, nome, tipo, subagente, caminho}.
     A versão anterior lia `ev.missao || ev.run || '—'`, bucketava tudo no '—' e
     o KPI anunciava "Runs produtoras: 1" — uma run que não existe, fabricada
     por agregação. Aqui as duas coisas ficam separadas: run declarada é
     contada, artefato sem run é contado como sem run. */
  const porRun = useMemo(() => {
    const m = {};
    artefatos.forEach(a => { if (a.run) m[a.run] = (m[a.run] || 0) + 1; });
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [artefatos]);

  const semRun = useMemo(() => artefatos.filter(a => !a.run).length, [artefatos]);

  if (error) return (
    <div>
      <span className="num">Datahouse</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!data) return (
    <div>
      <span className="num">Datahouse</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Datahouse</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>artefatos explicados pelo ledger</span>
      </div>

      {/* A declaração de incompletude. Mesma forma do buraco de `seq` que o
          canvas já detecta: o número aparece, e o que ele não sabe fica dito.
          Só ocupa espaço quando há de fato algo que o ledger não explica. */}
      {orfaos?.precisaDeclarar && (
        <div className="card" style={{ padding: '12px 15px', marginTop: 14, borderColor: 'var(--amber)' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span className="sh amber"></span>
            <span className="title" style={{ fontSize: 13 }}>O ledger não explica tudo que está em disco</span>
          </div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.7, marginTop: 8 }}>
            <b style={{ color: 'var(--text)' }}>{orfaos.artefatos}</b> de {orfaos.emDisco} artefatos
            em disco não têm evento <span className="mono">artefato.atualizou</span>
            {orfaos.runs > 0 && (
              <> · <b style={{ color: 'var(--text)' }}>{orfaos.runs}</b> de {orfaos.runsEmDisco} runs
              não deixaram log nem foram citadas por evento</>
            )}
            {orfaos.ignorados > 0 && (
              <> · {orfaos.ignorados} arquivos de ferramenta (<span className="mono">__pycache__</span>,
              <span className="mono"> .pytest_cache</span>) não foram contados como artefato</>
            )}
          </div>
          {orfaos.legadoIlegivel && (
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--red)', marginTop: 6 }}>
              log legado da raiz ilegível: {orfaos.legadoIlegivel}
            </div>
          )}
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.6, marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
            Estes artefatos <b>não</b> aparecem nas listas abaixo e não recebem run, tipo nem data:
            o diretório sugere os três e nenhum foi registrado. Existir em disco não é existir no
            ledger, e o painel não reconstrói o que ninguém escreveu.
          </div>
          {orfaos.amostra.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {orfaos.amostra.slice(0, 8).map(caminho => (
                <div key={caminho} className="mono" style={{ fontSize: 10, color: 'var(--text3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  órfão · {caminho}
                </div>
              ))}
              {(orfaos.amostra.length > 8 || orfaos.amostraTruncada) && (
                <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
                  … {orfaos.artefatos - Math.min(8, orfaos.amostra.length)} não listados
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginTop: 16 }}>
        <div className="kpi">
          <div className="eyebrow">Artefatos</div>
          <div className="kbig">{artefatos.length}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>com evento no ledger</div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Tipos declarados</div>
          <div className="kbig">{porTipo.length}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>campo `tipo` do evento</div>
        </div>
        <div className="kpi">
          <div className="eyebrow">Runs declaradas</div>
          <div className="kbig">{porRun.length}</div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
            {semRun > 0 ? `${semRun} artefatos sem run no evento` : 'runs citadas pelo evento'}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginTop: 20 }}>
        <div>
          <div className="num" style={{ marginBottom: 10 }}>01 — Por tipo declarado</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {porTipo.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Nenhum artefato explicado pelo ledger</span></div>}
            {porTipo.map(([tipo, count]) => (
              <div key={tipo} className="trow">
                <span className="mono" style={{ color: 'var(--text)', width: 90, flex: 'none', overflow: 'hidden', textOverflow: 'ellipsis' }}>{tipo}</span>
                <div style={{ flex: 1, height: 6, background: 'var(--surface2)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, (count / Math.max(1, artefatos.length)) * 100)}%`, background: 'var(--blue)', borderRadius: 2 }}></div>
                </div>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text2)', width: 30, textAlign: 'right', flex: 'none' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="num" style={{ marginBottom: 10 }}>02 — Por run</div>
          <div className="card" style={{ padding: '4px 16px' }}>
            {porRun.length === 0 && (
              <div className="trow">
                <span className="mono" style={{ color: 'var(--text3)', lineHeight: 1.6 }}>
                  Nenhuma run declarada · o evento <span className="mono">artefato.atualizou</span> não
                  carrega identificador de run, então o painel não sabe qual run produziu o quê
                </span>
              </div>
            )}
            {semRun > 0 && porRun.length > 0 && (
              <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>+ {semRun} sem run declarada no evento</span></div>
            )}
            {porRun.map(([run, count]) => (
              <div key={run} className="trow" style={{ cursor: 'pointer' }} onClick={() => { window.location.hash = `/runs/${run}`; }}>
                <span className="sh green"></span>
                <span style={{ color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run}</span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', flex: 'none' }}>{count} arquivo{count !== 1 ? 's' : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <div className="num" style={{ marginBottom: 10 }}>03 — Últimos artefatos com evento</div>
        <div className="card" style={{ padding: '4px 16px' }}>
          {artefatos.length === 0 && <div className="trow"><span className="mono" style={{ color: 'var(--text3)' }}>Nenhum artefato registrado nos eventos</span></div>}
          {artefatos.slice(0, 12).map(a => (
            <div key={a.caminho} className="trow">
              <span className="sh green"></span>
              <span className="mono" style={{ color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>{a.caminho}</span>
              {a.revisoes > 1 && (
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', flex: 'none' }}>{a.revisoes}×</span>
              )}
              {/* O evento carrega `subagente`. A versão anterior lia `executor`,
                  que o evento nunca teve, e mostrava "—" em todas as linhas. */}
              <span className="mono" style={{ fontSize: 10, color: 'var(--text3)', flex: 'none' }}>{a.subagente || 'sem subagente'}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
