/*
 * A gate pendente e um fato independente de o ledger descrever o estado da run.
 * Com estado null antes do gate, o unico gate humano nao respondido da producao
 * sumia da coluna que existe para mostra-lo. O perigo esta no else final: ele
 * engole o desconhecido junto com o resto, como um ternario sobre campo anulavel.
 */
export function colFor(run, gateIds) {
  if (gateIds.has(run.id)) return 'precisa';
  if (run.estado === 'concluida' || run.estado === 'abortada') return 'done';
  if (run.estado === 'ativa') return 'prod';
  return 'indeterminado';
}
