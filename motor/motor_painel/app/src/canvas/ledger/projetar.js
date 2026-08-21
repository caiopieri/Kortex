/* Projecao do ledger em runs, e de cada run no que a superficie desenha.
 *
 * `run_id` no envelope e a identidade declarada da execucao. `seq` continua
 * sendo apenas cursor local da fonte: o consumidor incremental deve usar
 * (fonte, seq), nunca seq sozinho. Linhas legadas sem run_id ficam num unico
 * balde por fonte, sem repartir o passado por ordem ou timestamp.
 */

import { ehFalha, localizar } from './andon.js';

const ABRE = 'run.perfil';
const FECHA = new Set(['tarefa.concluida', 'tarefa.abortada']);

export function segmentarRuns(eventos) {
  const porIdentidade = new Map();
  for (const evento of eventos) {
    const fonte = evento.__fonte ?? 'cli';
    const runId = typeof evento.run_id === 'string' && evento.run_id
      ? evento.run_id
      : null;
    const chave = runId ? `run:${runId}` : `legado:${fonte}`;
    const grupo = porIdentidade.get(chave) ?? {
      fonte,
      id: runId ?? `legado:${fonte}`,
      eventos: [],
    };
    if (grupo.fonte !== fonte) grupo.fonte = 'multiplas-fontes';
    grupo.eventos.push(evento);
    porIdentidade.set(chave, grupo);
  }

  const runs = [];
  for (const grupo of porIdentidade.values()) {
    const seqs = grupo.eventos
      .map((evento) => evento.seq)
      .filter((seq) => Number.isInteger(seq));
    runs.push({
      ...grupo,
      perfil: grupo.eventos.find((evento) => evento.evento === ABRE)?.perfil ?? null,
      seqDe: seqs.length ? Math.min(...seqs) : null,
      seqAte: seqs.length ? Math.max(...seqs) : null,
    });
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

export function projetarRun(run) {
  const eventos = run.eventos;
  /* A topologia vem do contrato de /dados. Este módulo só enriquece os nós
     com estado, falhas e artefatos para a apresentação; não pode reconstruir
     uma segunda versão de nós ou arestas a partir dos mesmos eventos. */
  const nos = new Map(
    (Array.isArray(run.nos) ? run.nos : []).map((no) => [no.id, {
      ...no,
      /* `motor` é o nó raiz legado do contrato e não declara onda; isso é
         apenas um valor de layout, não uma nova decisão topológica. */
      onda: Number.isInteger(no.onda) ? no.onda : 0,
    }]),
  );
  const conjunto = new Set(nos.keys());

  const arestas = Array.isArray(run.arestas)
    ? run.arestas.map((aresta) => ({ de: aresta.de, para: aresta.para }))
    : [];

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

  const lista = [...nos.values()].map((no) => ({
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
