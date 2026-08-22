import { useMemo } from 'react';
import { usePoll, fetchDados, getOrfaos } from '../api.js';
import {
  agruparPorRun,
  BASE_HASH,
  censoDoCorpus,
  conteudosRepetidos,
  itensDaEstante,
  resumoDeOrfaos,
} from './estanteDoLedger.js';

/* A estante de artefatos. `DECISAO-interface-cortes-e-estante.md` §4.
 *
 * NAO e vitrine de janelas vivas: a janelinha viva depende de QUATRO contratos
 * e so o primeiro existe (hash, #24). E uma estante, e cada cartao carrega o que
 * o evento declara mais SLOTS VAZIOS NOMEADOS.
 *
 * O SLOT VAZIO E O PONTO DA TELA, nao um placeholder envergonhado. Ele torna o
 * contrato que falta visivel toda vez que a aba abre -- o que funciona melhor
 * que um documento que ninguem rele. Mesma forma do `Runners.jsx`.
 *
 * Sao DOIS slots, e eles sao de naturezas diferentes:
 *
 *   VISUALIZADOR   travado no contrato 2 (`tipo` virar enum). Estatico: so sai
 *                  quando alguem decidir o enum.
 *   PROVENIENCIA   travado no CORPUS, nao no contrato. E um MEDIDOR: mostra
 *                  quantos artefatos ja declaram run e hash, e SE APAGA SOZINHO
 *                  quando o numero fechar. Aviso que nao sabe quando deixou de
 *                  ser verdade e documento que envelhece -- o defeito que esta
 *                  interface passou a semana removendo.
 *
 * Esta tela SUBSTITUI a Datahouse, nao acompanha. O §3 do mesmo documento diz
 * que "construir a aba de aplicacoes sobre 21 telas e fazer a 22a", e a
 * Datahouse ja era a tela de artefatos: mesmos eventos, mesma contagem. Duas
 * superficies sobre o mesmo `artefato.atualizou` seria o defeito que os sete
 * cortes removeram.
 */

const VAZIO = 'não declarado';

export default function Estante() {
  const { data, error } = usePoll(fetchDados);
  const { data: orfaosBrutos } = usePoll(getOrfaos);

  const itens = useMemo(() => itensDaEstante(data?.eventos), [data]);
  const censo = useMemo(() => censoDoCorpus(itens), [itens]);
  const grupos = useMemo(() => agruparPorRun(itens), [itens]);
  const repetidos = useMemo(() => conteudosRepetidos(itens), [itens]);
  const orfaos = useMemo(() => resumoDeOrfaos(orfaosBrutos), [orfaosBrutos]);

  if (error) return (
    <div>
      <span className="num">Estante</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!data) return (
    <div>
      <span className="num">Estante</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span className="title" style={{ fontSize: 20 }}>Estante de artefatos</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
          o que a fábrica produziu
        </span>
      </div>

      {/* O CENSO. Nao e vaidade de KPI: e o retrato do corpus, e e ele que
          justifica os slots abaixo. "1 tipo em 40 artefatos" e a verdade sobre a
          fabrica, nao um defeito da tela. */}
      <div className="card" style={{ padding: '11px 15px', marginTop: 14 }}>
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--text2)', lineHeight: 1.7 }}>
          <b style={{ color: 'var(--text)' }}>{censo.artefatos}</b> artefatos
          {' · '}<b style={{ color: 'var(--text)' }}>{censo.tipos}</b> tipo{censo.tipos === 1 ? '' : 's'}
          {censo.tiposDeclarados.length > 0 && ` (${censo.tiposDeclarados.join(', ')})`}
          {' · '}<b style={{ color: 'var(--text)' }}>{censo.nomes}</b> nome{censo.nomes === 1 ? '' : 's'} distinto{censo.nomes === 1 ? '' : 's'}
          {' · '}<b style={{ color: 'var(--text)' }}>{censo.escritas}</b> escritas
          {censo.semTipo > 0 && <> · {censo.semTipo} sem tipo declarado</>}
        </div>
      </div>

      {/* SLOT 2 — PROVENIENCIA. O medidor. Some sozinho quando fechar. */}
      {censo.precisaDeclararProveniencia && (
        <div className="card" style={{ padding: '12px 15px', marginTop: 12, borderColor: 'var(--amber)' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span className="sh amber"></span>
            <span className="title" style={{ fontSize: 13 }}>Nenhuma run e nenhum conteúdo identificados</span>
          </div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.7, marginTop: 8 }}>
            <b style={{ color: 'var(--text)' }}>{censo.comProveniencia}</b> de {censo.artefatos} artefatos
            declaram <span className="mono">run_id</span> e <span className="mono">hash</span> no evento.
          </div>
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.6, marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
            O contrato existe: a issue #24 pôs os dois campos no
            <span className="mono"> artefato.atualizou</span>, e o motor recusa um sem o outro.
            O que falta é <b style={{ color: 'var(--text2)' }}>corpus</b> — nenhuma run rodou desde o
            merge. Este aviso não foi escrito à mão: ele é a contagem, e desaparece sozinho quando
            a primeira run pós-#24 gravar um artefato.
          </div>
        </div>
      )}

      {/* O que NAO existe no modelo, dito antes que alguem procure. */}
      <div className="card" style={{ padding: '10px 14px', marginTop: 12, borderStyle: 'dashed' }}>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text3)', lineHeight: 1.7 }}>
          Não há agrupamento por <b style={{ color: 'var(--text2)' }}>projeto</b>, e não é omissão:
          projeto não existe no modelo do Kortex — cada run é um{' '}
          <span className="mono">runs/&lt;id&gt;</span> que esquece tudo. Métrica por projeto também
          não, porque não teria sujeito. A estante agrupa por <b style={{ color: 'var(--text2)' }}>run</b>,
          e só pela que o evento declara.
        </span>
      </div>

      {/* A declaracao da #22: o que existe em disco e o ledger nao explica. */}
      {orfaos?.precisaDeclarar && (
        <div className="card" style={{ padding: '12px 15px', marginTop: 12, borderColor: 'var(--amber)' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span className="sh amber"></span>
            <span className="title" style={{ fontSize: 13 }}>O ledger não explica tudo que está em disco</span>
          </div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--text2)', lineHeight: 1.7, marginTop: 8 }}>
            <b style={{ color: 'var(--text)' }}>{orfaos.artefatos}</b> de {orfaos.emDisco} artefatos
            em disco não têm evento
            {orfaos.runs > 0 && (
              <> · <b style={{ color: 'var(--text)' }}>{orfaos.runs}</b> de {orfaos.runsEmDisco} runs
              não deixaram log nem foram citadas</>
            )}
            {orfaos.ignorados > 0 && <> · {orfaos.ignorados} arquivos de ferramenta ignorados</>}
          </div>
          {orfaos.legadoIlegivel && (
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--red)', marginTop: 6 }}>
              log legado da raiz ilegível: {orfaos.legadoIlegivel}
            </div>
          )}
          <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.6, marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
            Estes <b>não</b> viram cartão e não recebem run, tipo nem data: o diretório sugere os
            três e nenhum foi registrado. Existir em disco não é existir no ledger.
          </div>
          {orfaos.amostra.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {orfaos.amostra.slice(0, 6).map(caminho => (
                <div key={caminho} className="mono" style={{ fontSize: 10, color: 'var(--text3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  órfão · {caminho}
                </div>
              ))}
              {(orfaos.amostra.length > 6 || orfaos.amostraTruncada) && (
                <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
                  … {orfaos.artefatos - Math.min(6, orfaos.amostra.length)} não listados
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {repetidos.length > 0 && (
        <div className="card" style={{ padding: '10px 14px', marginTop: 12 }}>
          <span className="mono" style={{ fontSize: 11, color: 'var(--text2)' }}>
            {repetidos.length} conteúdo{repetidos.length === 1 ? '' : 's'} idêntico{repetidos.length === 1 ? '' : 's'} em mais de um lugar (por hash)
          </span>
        </div>
      )}

      <div className="num" style={{ margin: '22px 0 10px' }}>
        01 — Os artefatos
      </div>

      {itens.length === 0 && (
        <div className="card" style={{ padding: 28, textAlign: 'center' }}>
          <div className="title" style={{ fontSize: 15 }}>Nenhum artefato no ledger</div>
          <div className="mono" style={{ fontSize: 11.5, color: 'var(--text2)', lineHeight: 1.7, maxWidth: 460, margin: '10px auto 0' }}>
            A estante lê os eventos <span className="mono">artefato.atualizou</span>. Não há nenhum
            agora, então não há o que mostrar — e a tela não vai inventar.
          </div>
        </div>
      )}

      {grupos.map(grupo => (
        <div key={grupo.runId ?? '__sem_run__'} style={{ marginBottom: 22 }}>
          {/* O cabecalho do grupo carrega a run UMA vez. Quando `run_id` chegar,
              grupos de run aparecem ao lado deste e ele encolhe ate sumir --
              mesma forma nos dois mundos, sem redesenho. */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
            {grupo.runId ? (
              <>
                <span className="sh green"></span>
                <span
                  className="mono lnk"
                  style={{ fontSize: 12, color: 'var(--text)' }}
                  onClick={() => { window.location.hash = `/runs/${grupo.runId}`; }}
                >
                  {grupo.runId}
                </span>
              </>
            ) : (
              <>
                <span className="sh amber"></span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--text2)' }}>
                  sem run declarada
                </span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
                  o evento <span className="mono">artefato.atualizou</span> destes não traz{' '}
                  <span className="mono">run_id</span> · o diretório sugere uma run e derivar dele
                  seria inventar
                </span>
              </>
            )}
            <div style={{ flex: 1 }} />
            <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>
              {grupo.itens.length} artefato{grupo.itens.length === 1 ? '' : 's'}
            </span>
          </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(310px, 1fr))', gap: 12 }}>
        {grupo.itens.map(item => (
          <div key={item.lugar} className="card" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 9 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span className="title" style={{ fontSize: 14, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.nome}
              </span>
              <span className="pill" style={{ fontSize: 9, flex: 'none' }}>
                {item.tipo ?? VAZIO}
              </span>
            </div>

            <div className="mono" style={{ fontSize: 10, color: 'var(--text3)', display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span>produzido por: {item.subagente ?? VAZIO}</span>

              {/* `na run` NAO aparece por cartao: virou cabecalho de grupo. A
                  ausencia e do corpus, nao de cada artefato, e diz-la 40 vezes
                  treinaria o olho a pular. Divergencia de run, essa sim, e
                  propriedade do artefato e fica aqui. */}
              {item.runsConflitantes && (
                <span style={{ color: 'var(--red)' }}>escrito por mais de uma run</span>
              )}

              {/* ESCRITAS, nao "revisoes". Contar escrita nao e contar mudanca:
                  duas gravacoes identicas contam 2. So o hash separa as duas
                  coisas, e por isso `versoes` aparece so quando ha hash. */}
              <span>
                escritas: {item.escritas}
                {item.versoes !== null
                  ? ` · ${item.versoes} versão${item.versoes === 1 ? '' : 'ões'} de conteúdo`
                  : ' · quantas mudaram de conteúdo: não medido (sem hash)'}
              </span>

              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                identidade por {item.baseDaIdentidade === BASE_HASH ? 'hash' : 'lugar'}:{' '}
                {item.baseDaIdentidade === BASE_HASH ? `${item.identidade.slice(0, 12)}…` : item.identidade}
              </span>
            </div>

            {/* SLOT 1 — VISUALIZADOR. Estatico ate o contrato 2. */}
            <div style={{ border: '1px dashed var(--border)', borderRadius: 2, padding: '14px 12px', textAlign: 'center' }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text2)' }}>sem pré-visualização</div>
              <div className="mono" style={{ fontSize: 9.5, color: 'var(--text3)', marginTop: 4, lineHeight: 1.5 }}>
                o motor não declara como abrir um artefato{' '}
                {item.tipo ? <>&quot;{item.tipo}&quot;</> : 'sem tipo'} — <span className="mono">tipo</span> é
                string livre, não há registro de visualizador
              </div>
            </div>
          </div>
        ))}
      </div>
        </div>
      ))}
    </>
  );
}
