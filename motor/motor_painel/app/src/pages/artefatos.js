/* Artefato do ledger e artefato órfão são duas listas, e nunca uma (issue #22).
 *
 * O ledger não era durável. Medido no checkout de produção: 29 workspaces de
 * run em disco, 26 explicados; 49 artefatos de produto, 40 com evento
 * `artefato.atualizou`.
 * Uma tela que lista só o que o ledger explica é silenciosamente incompleta —
 * e a medição "tipo python em 47 de 47" é sobre o que sobrou, não sobre o que
 * houve.
 *
 * A correção NÃO é reconstruir. `<workspace>/<run>/artefatos/x.stl` sugere run
 * e sugere tipo, e essa inferência é exatamente o que a regra canônica proíbe:
 * existe por estar no ledger ou numa spec, não por estar no disco. Então o
 * órfão entra na tela COMO ÓRFÃO — caminho e mais nada — numa lista separada
 * que nunca se mistura com a derivada de evento.
 *
 * Juntar as duas listas derruba `orfao_nunca_entra_na_lista_do_ledger`.
 */

const EVENTOS_DE_ARTEFATO = new Set([
  'artefato.atualizou',
  // Nomes legados que já apareceram no log e não são emitidos hoje. Mantidos
  // porque run antiga continua legível; não são contrato novo.
  'artefato.gravado',
  'artefato.atualizado',
]);

/* Derivado de evento: cada campo aqui foi escrito pelo motor, nenhum foi
   deduzido do caminho. `tipo` vem do evento — hoje ele é string livre, e é
   por isso que a tela não promete mais do que "o que o motor declarou". */
export function artefatosDoLedger(eventos) {
  if (!Array.isArray(eventos)) return [];

  const porCaminho = new Map();
  for (const ev of eventos) {
    if (!EVENTOS_DE_ARTEFATO.has(ev?.evento)) continue;
    const caminho = ev.caminho || ev.artefato || ev.arquivo;
    if (!caminho) continue;

    const anterior = porCaminho.get(caminho);
    const entrada = {
      caminho,
      nome: ev.nome || caminho.split('/').pop(),
      tipo: ev.tipo || null,
      subagente: ev.subagente || null,
      run: ev.run_id || null,
      t: ev.t ?? null,
      revisoes: (anterior?.revisoes ?? 0) + 1,
    };
    porCaminho.set(caminho, entrada);
  }
  return [...porCaminho.values()].reverse();
}

/* O resumo que a tela declara. Vem inteiro do `/dados/orfaos`, que é quem
   enxerga o disco — a tela não lê diretório e não deve começar a ler. */
export function resumoDeOrfaos(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const artefatos = Number(payload.artefatos_orfaos) || 0;
  const runs = Array.isArray(payload.runs_orfas) ? payload.runs_orfas : [];
  return {
    artefatos,
    runs: runs.length,
    runsIds: runs,
    emDisco: Number(payload.artefatos_em_disco) || 0,
    comEvento: Number(payload.artefatos_com_evento) || 0,
    runsEmDisco: Number(payload.runs_em_disco) || 0,
    ignorados: Number(payload.arquivos_de_ferramenta_ignorados) || 0,
    amostra: Array.isArray(payload.amostra) ? payload.amostra : [],
    amostraTruncada: payload.amostra_truncada === true,
    legadoIlegivel: payload.legado_ilegivel || null,
    /* Só vale ocupar espaço na tela quando há de fato algo que o ledger não
       explica. Zero órfão não merece banner — merece silêncio. */
    precisaDeclarar: artefatos > 0 || runs.length > 0 || Boolean(payload.legado_ilegivel),
  };
}
