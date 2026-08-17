/* De onde vem uma notificacao.
 *
 * NAO EXISTE sistema de notificacao no motor: procurei em `motor/` e `docs/` e
 * so ha um toast local em `Home.jsx` e mencoes no ROADMAP (#14) e na
 * `DECISAO-canvas-e-operacao.md` §6. Entao a superficie NAO inventa uma fila de
 * avisos — ela deriva as notificacoes do que o andon JA calcula sobre o ledger
 * real. Cada uma aponta para algo que existe e que se pode abrir.
 *
 * A consequencia importante: toda notificacao daqui tem DESTINO declarado ou
 * declara que nao tem. Nenhuma leva a lugar nenhum em silencio.
 *
 * Quando o motor tiver a fila de verdade, ela entra como uma SEGUNDA fonte
 * nesta funcao, e a interface nao muda.
 */

/* Ordem de gravidade — decide o topo da lista e a cor do badge. */
export const SEVERIDADES = ['terminal', 'sistemica', 'localizada', 'leitura'];

const PESO = Object.fromEntries(SEVERIDADES.map((s, i) => [s, i]));

export function derivarNotificacoes(runs, leitura) {
  const avisos = [];

  for (const run of runs) {
    const ondeRun = { runId: run.id, missao: run.missao, seq: run.seqDe };

    /* 1. Terminal ambiguo: o unico caso em que o operador PRECISA agir de forma
       diferente — cadeia parada, efeito possivelmente cobrado, exige run nova. */
    if (run.terminal) {
      avisos.push({
        id: `${run.id}#terminal#${run.terminal.seq}`,
        severidade: 'terminal',
        titulo: 'Falha terminal — efeito desconhecido',
        detalhe: run.terminal.custo?.rotulo ?? run.terminal.motivo,
        destino: { ...ondeRun, no: null },
        seq: run.terminal.seq,
      });
    }

    /* 2. Sistemicas: o destino e a ESTACAO DE PRE-VOO, que e um lugar fixo e
       real na superficie. Nao e "sem destino". */
    for (const f of run.sistemicas) {
      avisos.push({
        id: `${run.id}#sis#${f.seq}`,
        severidade: 'sistemica',
        titulo: f.evento,
        detalhe: f.motivo,
        destino: { ...ondeRun, no: null, estacao: true },
        seq: f.seq,
      });
    }

    /* 3. Localizadas: destino e o no. Uma por NO, nao uma por evento — dez
       tentativas do mesmo executor sao um problema, nao dez. */
    for (const no of run.nos) {
      if (no.falhas.length === 0) continue;
      avisos.push({
        id: `${run.id}#no#${no.id}`,
        severidade: 'localizada',
        titulo: no.id,
        detalhe: `${no.falhas.length} falha${no.falhas.length === 1 ? '' : 's'} · ${
          no.falhas[0].custo?.rotulo ?? no.falhas[0].motivo
        }`,
        destino: { ...ondeRun, no: no.id },
        seq: no.falhas[0].seq,
      });
    }
  }

  /* 4. Saude da leitura. Estes NAO tem destino, e dizem que nao tem: buraco no
     seq nao aponta para um lugar da superficie, aponta para o arquivo. */
  if (leitura) {
    const ausentes = leitura.buracos.reduce((n, b) => n + b.faltando, 0);
    if (ausentes > 0) {
      avisos.push({
        id: 'leitura#buracos',
        severidade: 'leitura',
        titulo: `${ausentes} eventos ausentes no seq`,
        detalhe: `causa não declarada · ${leitura.buracos
          .map((b) => `${b.fonte} ${b.de}–${b.ate}`)
          .join(', ')}`,
        destino: null,
        seq: leitura.buracos[0].de,
      });
    }
    if (leitura.ilegiveis.length > 0) {
      avisos.push({
        id: 'leitura#ilegiveis',
        severidade: 'leitura',
        titulo: `${leitura.ilegiveis.length} linhas ilegíveis`,
        detalhe: 'não reparadas — o writer não repara, a superfície também não',
        destino: null,
        seq: 0,
      });
    }
    if (leitura.reinicios > 0) {
      avisos.push({
        id: 'leitura#reinicios',
        severidade: 'leitura',
        titulo: `${leitura.reinicios} reinício de arquivo`,
        detalhe: 'o log encolheu: rotação ou truncamento',
        destino: null,
        seq: 0,
      });
    }
  }

  return avisos.sort((a, b) => PESO[a.severidade] - PESO[b.severidade] || b.seq - a.seq);
}
