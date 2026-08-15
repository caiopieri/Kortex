/* Projecao do ledger em runs, e de cada run no que a superficie desenha.
 *
 * IDENTIDADE E O PAR (fonte, seq), NUNCA `seq` SOZINHO. Sao dois arquivos de
 * log (divida 17(b)) e cada um tem sua sequencia comecando do 1: `seq` sozinho
 * colide as duas. Por isso a segmentacao roda POR FONTE e o id da run e
 * `<fonte>#<seqDe>`.
 *
 * MEDIDO no log real (1453 eventos, 2026-08-14): dos 765 eventos ESTRUTURAIS
 * (onda.*, executor.*, portao.*, artefato.atualizou, aresta.fluxo,
 * validador.rodou, tarefa.*), ZERO carregam `run_id`. So os 290 eventos
 * `custo.*` carregam. Entao nao da para agrupar run por campo: a run e a JANELA
 * de seq entre um `run.perfil` e o proximo, dentro da mesma fonte. Isso e
 * derivacao por ordem, e quebra se duas runs escreverem intercaladas no mesmo
 * arquivo. Esta no README como a terceira precondicao, que ainda nao virou
 * issue — `run_id` nos eventos estruturais tornaria a derivacao desnecessaria.
 */

import { ehFalha, localizar } from './andon.js';

const ABRE = 'run.perfil';
const FECHA = new Set(['tarefa.concluida', 'tarefa.abortada']);

export function segmentarRuns(eventos) {
  const porFonte = new Map();
  for (const evento of eventos) {
    const fonte = evento.__fonte ?? 'cli';
    const lista = porFonte.get(fonte) ?? [];
    lista.push(evento);
    porFonte.set(fonte, lista);
  }

  const runs = [];
  for (const [fonte, doArquivo] of porFonte) {
    let atual = null;
    for (const evento of doArquivo) {
      if (evento.evento === ABRE) {
        if (atual) runs.push(atual);
        atual = {
          fonte,
          id: `${fonte}#${evento.seq}`,
          perfil: evento.perfil ?? null,
          seqDe: evento.seq,
          seqAte: evento.seq,
          eventos: [],
        };
      }
      if (!atual) continue;
      atual.eventos.push(evento);
      atual.seqAte = evento.seq;
    }
    if (atual) runs.push(atual);
  }

  return runs.map((run) => ({ ...run, ...resumo(run.eventos) }));
}

function resumo(eventos) {
  const spec = eventos.find((e) => e.evento === 'spec.recebida');
  const fim = [...eventos].reverse().find((e) => FECHA.has(e.evento));
  return {
    missao: spec?.missao ?? null,
    desfecho: fim ? fim.evento : 'aberta',
    motivoDoFim: fim?.motivo ?? null,
  };
}

/* Nos declarados pela run. Tres fontes, todas explicitas — nenhum no nasce de
   ser citado por um evento de falha. */
function nosDeclarados(eventos) {
  const nos = new Map();
  const registrar = (id, papel) => {
    if (typeof id !== 'string' || id.trim() === '') return;
    const anterior = nos.get(id);
    nos.set(id, { id, papel: papel ?? anterior?.papel ?? null, onda: anterior?.onda ?? null });
  };

  for (const e of eventos) {
    if (e.evento === 'grafo_dep.iniciado') (e.subagentes ?? []).forEach((id) => registrar(id));
    if (e.evento === 'onda.iniciada') (e.ids ?? []).forEach((id) => registrar(id));
    if (e.evento === 'executor.chamado') registrar(e.executor, e.papel ?? 'executor');
    if (e.evento === 'validador.rodou') registrar(e.id, 'validador');
  }

  /* Onda = camada topologica DECLARADA por `onda.iniciada`. E a unica coisa
     parecida com posicao que o ledger emite; o resto do layout (x, y em pixel)
     e derivado dela e da ordem, e a superficie diz isso em voz alta no rodape.
     Layout derivado de grafo declarado nao e o mesmo que inventar localizacao
     de falha — o que o ROADMAP proibe e o segundo. */
  let camada = 0;
  for (const e of eventos) {
    if (e.evento !== 'onda.iniciada') continue;
    for (const id of e.ids ?? []) {
      const no = nos.get(id);
      if (no && no.onda === null) no.onda = camada;
    }
    camada += 1;
  }
  for (const no of nos.values()) if (no.onda === null) no.onda = camada;

  return nos;
}

export function projetarRun(run) {
  const eventos = run.eventos;
  const nos = nosDeclarados(eventos);
  const conjunto = new Set(nos.keys());

  const arestas = [];
  const vistas = new Set();
  for (const e of eventos) {
    if (e.evento !== 'aresta.fluxo') continue;
    const chave = `${e.de}→${e.para}`;
    if (vistas.has(chave) || !conjunto.has(e.de) || !conjunto.has(e.para)) continue;
    vistas.add(chave);
    arestas.push({ de: e.de, para: e.para });
  }

  /* `artefato.atualizou` dispara a cada ESCRITA, entao o mesmo arquivo aparece
     varias vezes numa run que refez o trabalho. E um artefato so, com N
     revisoes: mantem a ultima (maior seq) e conta as anteriores. Listar cada
     escrita como um artefato separado inflaria a contagem e faria a superficie
     mentir sobre quanto foi produzido. */
  const porArtefato = new Map();
  for (const e of eventos) {
    if (e.evento !== 'artefato.atualizou') continue;
    const chave = e.caminho ?? `${e.subagente}/${e.nome}`;
    const anterior = porArtefato.get(chave);
    porArtefato.set(chave, {
      chave,
      nome: e.nome,
      tipo: e.tipo ?? null,
      no: e.subagente ?? null,
      caminho: e.caminho ?? null,
      seq: e.seq,
      revisoes: (anterior?.revisoes ?? 0) + 1,
    });
  }
  const artefatos = [...porArtefato.values()].sort((a, b) => a.seq - b.seq);

  const localizadas = new Map();
  const sistemicas = [];
  for (const e of eventos) {
    if (!ehFalha(e)) continue;
    const destino = localizar(e, conjunto);
    const falha = {
      evento: e.evento,
      motivo: destino.motivo,
      /* Classificacao das quatro formas de `motivo`. E ela que decide se a
         falha se desenha como retentativa ou como FIM DE RUN — desenhar
         "terminal ambiguo" como retry esconderia efeito possivelmente cobrado. */
      custo: destino.custo,
      tentativa: destino.tentativa,
      seq: e.seq,
    };
    if (destino.classe === 'localizada') {
      const lista = localizadas.get(destino.no) ?? [];
      lista.push(falha);
      localizadas.set(destino.no, lista);
    } else {
      sistemicas.push({ ...falha, naoResolvido: destino.naoResolvido });
    }
  }

  const aprovados = new Set();
  for (const e of eventos) {
    if (e.evento === 'portao.aprovado' && typeof e.portao === 'string') {
      const alvo = e.portao.split(':')[1];
      if (alvo && conjunto.has(alvo)) aprovados.add(alvo);
    }
    if (e.evento === 'validador.rodou' && e.aprovado === true) aprovados.add(e.id);
  }

  const lista = [...nos.values()]
    .sort((a, b) => a.onda - b.onda || a.id.localeCompare(b.id))
    .map((no) => ({
      ...no,
      estado: localizadas.has(no.id) ? 'falhou' : aprovados.has(no.id) ? 'aprovado' : 'sem-portao',
      falhas: localizadas.get(no.id) ?? [],
      artefatos: artefatos.filter((a) => a.no === no.id),
    }));

  const todasFalhas = [...sistemicas, ...[...localizadas.values()].flat()];

  return {
    ...run,
    nos: lista,
    arestas,
    artefatos,
    sistemicas,
    /* Uma falha terminal-ambigua muda o que o operador deve fazer: a cadeia de
       failover parou e e preciso run_id NOVA, nao retentativa. A run inteira
       carrega o fato para o cromo nao precisar varrer os nos. */
    terminal: todasFalhas.find((f) => f.custo?.terminal) ?? null,
    /* Formas nao declaradas sao o log de hoje (pre-commit do #11). Contadas
       para o selo dizer quantas falhas ainda nao permitem afirmar nada sobre
       efeito, em vez de a superficie assumir a leitura benigna. */
    naoDeclaradas: todasFalhas.filter((f) => f.custo?.forma === 'nao-declarado').length,
    cobertura: eventos.find((e) => e.evento === 'evidencia.cobertura') ?? null,
  };
}
