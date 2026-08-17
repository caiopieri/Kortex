/* Andon: para onde uma falha leva, e o que ela permite dizer sobre dinheiro.
 *
 * DUAS PERGUNTAS SEPARADAS, e misturar as duas foi o erro que esta versao evita:
 *
 *   ONDE  o evento nomeia um no do grafo? Entao o andon leva a esse no
 *         (LOCALIZADA). Se nao nomeia, leva a estacao de pre-voo FIXA
 *         (SISTEMICA). A superficie nunca inventa localizacao — regra do
 *         ROADMAP, e a saida por DECLARACAO que a issue #11 admite.
 *
 *   O QUE o `motivo` de `executor.erro` declara se o efeito ocorreu, nao
 *         ocorreu, ou e desconhecido. Isso decide se a falha se desenha como
 *         RETENTATIVA ou como FIM DE RUN.
 *
 * A distincao que da sentido a tudo: "bloqueio pre-efeito" (nada aconteceu,
 * seguro, retentavel) contra "terminal ambiguo" (pode ter havido efeito e nao
 * sabemos; a cadeia de failover PARA). Desenhar o segundo como retry mentiria
 * sobre dinheiro ja gasto. Sao os dois unicos estados em que o canvas pode
 * dizer algo verdadeiro sobre custo sem inventar.
 */

export const ESTACAO_PRE_VOO = 'pre-voo';

/* Teto do `motivo` no motor. Aqui serve so para RECONHECER que a string pode
   ter sido cortada — a superficie nunca reconstroi o que foi truncado. */
export const TRUNCAMENTO = 400;

const EXTRATORES = {
  'executor.erro': (e) => e.executor,
  'validador.rodou': (e) => (e.aprovado === false ? e.alvo : null),
  'portao.reprovado': (e) => (typeof e.portao === 'string' ? e.portao.split(':')[1] : null),
  'tarefa.reprovada': () => null,
  'tarefa.abortada': () => null,
  'custo.bloqueado': () => null,
  'escalada.esgotada': () => null,
  'escalada.indisponivel': () => null,
  'decisao.timeout': () => null,
};

export function ehFalha(evento) {
  if (evento?.evento === 'validador.rodou') return evento.aprovado === false;
  return Object.hasOwn(EXTRATORES, evento?.evento);
}

/* Acento nao pode decidir semantica: o motivo e string do motor e ja apareceu
   nas duas grafias ("modelo não respondeu" no log de hoje). Compara sem
   diacritico e sem caixa. */
function simplificar(texto) {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

/* As quatro formas declaradas de `motivo`, COPIADAS LITERALMENTE do motor:
 *
 *   1. "modelo não respondeu"
 *   2. f"bloqueio pré-efeito: {'; '.join(f'{route_id}={motivo}')}"
 *   3. f"{motivo} ({status_reserva})"        <- status no FIM, entre parenteses
 *   4. "nenhuma rota elegível"               <- MESMA familia da 2, mas SEM o
 *                                               prefixo. Casar so pelo prefixo
 *                                               jogaria esta em nao-declarado.
 *
 * Todas com acento e todas truncadas em 400. A comparacao roda sem diacritico
 * de proposito: acento nao pode decidir semantica.
 *
 * Forma nao reconhecida NAO vira nenhuma delas: vira `nao-declarado`, com efeito
 * DESCONHECIDO. O log de hoje e todo `nao-declarado`, e a superficie diz isso em
 * vez de assumir a leitura benigna.
 */
export function classificarMotivo(motivo) {
  const bruto = typeof motivo === 'string' ? motivo : '';
  const s = simplificar(bruto);
  /* O motor trunca a string INTEIRA em 400, e na forma 3 o `(status_reserva)`
     esta no FIM — entao motivo longo de provedor come justamente o marcador que
     distingue terminal de bloqueio seguro. Consequencia para o desenho: a
     PRESENCA de `(algo)` no fim confirma terminal, mas a AUSENCIA nao prova que
     nao e. Por isso o comprimento no limite vira aviso explicito em vez de
     silencio. Conserto pedido ao motor; o parser nao muda antes da forma final. */
  const truncado = bruto.length >= TRUNCAMENTO;

  if (s.startsWith('bloqueio pre-efeito')) {
    const corpo = bruto.slice(bruto.indexOf(':') + 1);
    const rotas = corpo
      .split(';')
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => {
        const i = p.indexOf('=');
        return i === -1
          ? { rota: p, motivo: null }
          : { rota: p.slice(0, i).trim(), motivo: p.slice(i + 1).trim() };
      });
    return {
      forma: 'bloqueio-pre-efeito',
      efeito: 'nenhum',
      retentavel: true,
      terminal: false,
      terminalDescartado: true,
      rotas,
      /* O prefixo ja garante "nenhum efeito"; truncar so pode ter comido rotas
         do fim da lista, nao a semantica. */
      truncado,
      rotulo: truncado
        ? `nenhum efeito · ${rotas.length}+ rotas bloquearam (lista truncada)`
        : `nenhum efeito · ${rotas.length} rota${rotas.length === 1 ? '' : 's'} bloquearam`,
    };
  }

  if (s === 'modelo nao respondeu') {
    return {
      forma: 'sem-resposta',
      efeito: 'ocorreu',
      retentavel: true,
      terminal: false,
      terminalDescartado: true,
      rotas: [],
      rotulo: 'efeito ocorreu, custo reconciliado · faltou texto',
    };
  }

  if (s === 'nenhuma rota elegivel') {
    return {
      forma: 'sem-rota',
      efeito: 'nenhum',
      /* Cadeia vazia: retentar sem mudar rota reproduz o mesmo resultado. */
      retentavel: false,
      terminal: false,
      terminalDescartado: true,
      rotas: [],
      rotulo: 'cadeia vazia · nenhuma rota elegível',
    };
  }

  /* Forma 3: "<motivo> (<status_reserva>)". Testada por ultimo porque e a mais
     permissiva — a forma 2 tambem pode terminar em parenteses. */
  const terminal = bruto.match(/\(([^()]+)\)\s*$/);
  if (terminal) {
    return {
      forma: 'terminal-ambiguo',
      efeito: 'desconhecido',
      /* O ponto todo: NAO e retry. A cadeia de failover parou aqui e o operador
         precisa de run_id nova. Desenhar isto como retentativa esconderia que
         pode ter havido efeito cobrado. */
      retentavel: false,
      terminal: true,
      terminalDescartado: false,
      statusReserva: terminal[1].trim(),
      rotas: [],
      rotulo: `fim de run · efeito desconhecido (${terminal[1].trim()})`,
    };
  }

  /* Nenhuma forma casou. Nao ha o que afirmar sobre efeito — e, com o
     truncamento na string inteira, tambem nao ha como DESCARTAR terminal: o
     `(status)` pode ter sido cortado. `terminalDescartado: false` e o que
     impede a superficie de desenhar isto como se fosse seguro. */
  return {
    forma: 'nao-declarado',
    efeito: 'desconhecido',
    retentavel: null,
    terminal: false,
    terminalDescartado: false,
    truncado,
    rotas: [],
    rotulo: truncado
      ? 'motivo truncado em 400 · o status de reserva pode ter sido cortado — terminal não descartado'
      : 'forma de motivo não declarada · efeito desconhecido — terminal não descartado',
  };
}

/* `nos` e o conjunto de nos que a run declarou. No citado que nao esta la nao
   vira no novo: a superficie so desenha o que o ledger declarou existir. */
export function localizar(evento, nos) {
  if (!ehFalha(evento)) return null;

  const bruto = EXTRATORES[evento.evento]?.(evento);
  const no = typeof bruto === 'string' && bruto.trim() !== '' ? bruto.trim() : null;
  const motivo = evento.motivo ?? evento.nota ?? evento.portao ?? evento.evento;

  /* So `executor.erro` declara as quatro formas. Os outros eventos de falha nao
     dizem nada sobre efeito, e fingir que dizem seria a mesma invencao. */
  const custo =
    evento.evento === 'executor.erro'
      ? classificarMotivo(evento.motivo)
      : {
          /* So `executor.erro` tem cadeia de failover e status de reserva. Para
             `custo.bloqueado`, `portao.reprovado` e companhia a pergunta
             "terminal ou nao?" NAO SE APLICA — e `null`, nao `false`. Marcar
             como duvida o que nem tem a duvida seria alarme por atacado, e
             alarme por atacado e o mesmo que nenhum. */
          forma: 'nao-se-aplica',
          efeito: 'desconhecido',
          retentavel: null,
          terminal: false,
          terminalDescartado: null,
          rotas: [],
        };

  const base = { motivo, custo, tentativa: evento.tentativa ?? null, seq: evento.seq };

  if (no && nos.has(no)) return { ...base, classe: 'localizada', no };
  return { ...base, classe: 'sistemica', estacao: ESTACAO_PRE_VOO, naoResolvido: no ?? null };
}
