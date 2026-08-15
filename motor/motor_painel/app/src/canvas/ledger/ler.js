/* Leitura do ledger real, INCREMENTAL, por (arquivo, seq).
 *
 * SAO DOIS ARQUIVOS DE LOG, nao um — divida 17(b), aberta:
 *     CLI      motor/log.jsonl
 *     servico  workspace_base/<job_id>/log.jsonl
 * Cada um tem sua propria sequencia de `seq` comecando do 1. Projetar por `seq`
 * sozinho colide as duas no dia em que a segunda for lida. Por isso TODO evento
 * sai daqui carimbado com `__fonte`, e a identidade de qualquer coisa derivada
 * e o par (fonte, seq). Hoje so a raiz e lida, e o selo declara isso: run
 * despachada pelo servico simplesmente nao aparece, e a superficie diz que nao
 * aparece em vez de deixar o operador achar que nao existe.
 *
 * INCREMENTAL: guarda o deslocamento em BYTES do fim da ultima linha completa e
 * pede so o que veio depois. O `seq` e estritamente monotonico por arquivo
 * (motor/eventos.py:272-287), entao a continuidade e verificavel sem reler.
 *
 * O motor escreve sob flock exclusivo e o fundador pode estar com missao no ar:
 * NADA aqui abre o arquivo para escrita, e a cauda parcial nunca e consumida —
 * fica para a proxima leitura, que e o comportamento correto para escrita em
 * curso. Reparar linha quebrada seria inventar conteudo (o E-02 foi recusado: o
 * writer nao repara, entao a superficie tambem nao).
 */

export const FONTES = [
  { id: 'cli', rotulo: 'motor/log.jsonl', url: '/ledger/log.jsonl', lida: true },
  /* Divida 17(b). Sem endpoint enquanto o painel tambem nao le — declarada aqui
     para o selo poder dizer o que esta faltando, nao para fingir que le. */
  { id: 'servico', rotulo: 'workspace_base/<job_id>/log.jsonl', url: null, lida: false },
];

/* DOIS ADAPTADORES, porque ha duas maneiras de o mesmo log chegar aqui:
 *
 *   `adaptadorNdjson`  o plugin de dev serve o arquivo cru e aceita
 *                      `?desde_byte=`. E o unico caminho INCREMENTAL.
 *   `adaptadorPainel`  o painel em execucao (`GET /dados`) devolve JSON ja
 *                      parseado, sem deslocamento. Rele tudo a cada chamada,
 *                      que e exatamente o que `painel.py::parse_eventos` faz.
 *
 * O adaptador vem de fora para a superficie nao precisar saber onde esta
 * montada, e o selo mostra qual esta em uso — perder o incremental em silencio
 * seria pior do que nao te-lo. */
export const adaptadorNdjson = { id: 'ndjson', incremental: true, ler: lerIncremental };
export const adaptadorPainel = { id: 'painel', incremental: false, ler: lerDoPainel };

const CODIFICADOR = new TextEncoder();

export function criarLeitor(fonte = FONTES[0]) {
  return { fonte, deslocamento: 0, eventos: [], ilegiveis: [], reinicios: 0 };
}

export async function lerIncremental(leitor) {
  const url = `${leitor.fonte.url}?desde_byte=${leitor.deslocamento}`;
  const resposta = await fetch(url, { cache: 'no-store' });
  if (!resposta.ok) {
    throw new Error(`ledger indisponivel (${resposta.status}) em ${leitor.fonte.rotulo}`);
  }

  const tamanho = Number(resposta.headers.get('x-ledger-tamanho') ?? '0');
  const texto = await resposta.text();

  /* Arquivo encolheu: rotacao ou truncamento. Continuar do deslocamento antigo
     leria lixo. Recomeca do zero e CONTA o reinicio — sumir com o fato faria a
     timeline parecer continua quando nao foi. */
  let base = leitor;
  if (tamanho < leitor.deslocamento) {
    base = { ...criarLeitor(leitor.fonte), reinicios: leitor.reinicios + 1 };
    return lerIncremental(base);
  }

  const { eventos, ilegiveis, bytesConsumidos, caudaParcial } = fatiar(texto);

  const todos = [...base.eventos, ...eventos.map((e) => ({ ...e, __fonte: base.fonte.id }))];

  return {
    ...base,
    deslocamento: base.deslocamento + bytesConsumidos,
    eventos: todos,
    ilegiveis: [...base.ilegiveis, ...ilegiveis],
    caudaParcial,
    tamanho,
    buracos: buracosDeSeq(todos),
    novos: eventos.length,
    lidoEm: new Date().toISOString(),
  };
}

/* Consome so linhas COMPLETAS. Devolve quantos bytes foram consumidos para o
   chamador avancar o deslocamento — a cauda parcial fica no arquivo e volta
   inteira na proxima leitura. */
function fatiar(texto) {
  const eventos = [];
  const ilegiveis = [];
  const ultimoQuebra = texto.lastIndexOf('\n');
  const completo = ultimoQuebra === -1 ? '' : texto.slice(0, ultimoQuebra + 1);
  const resto = texto.slice(ultimoQuebra + 1);

  for (const linha of completo.split('\n')) {
    if (linha.trim() === '') continue;
    try {
      const evento = JSON.parse(linha);
      if (typeof evento?.seq !== 'number') {
        ilegiveis.push({ motivo: 'sem seq numerico', trecho: linha.slice(0, 120) });
        continue;
      }
      eventos.push(evento);
    } catch (erro) {
      /* Linha completa e ilegivel e coisa diferente de cauda parcial. Nao e
         reparada nem descartada em silencio: e contada e mostrada. */
      ilegiveis.push({ motivo: String(erro?.message ?? erro), trecho: linha.slice(0, 120) });
    }
  }

  return {
    eventos,
    ilegiveis,
    bytesConsumidos: CODIFICADOR.encode(completo).length,
    caudaParcial: resto.length > 0 ? { bytes: CODIFICADOR.encode(resto).length } : null,
  };
}

/* Buraco = seq ausente DENTRO DE UMA MESMA FONTE. Devolve o intervalo e nada
   mais: NAO classifica. Ha pelo menos duas causas conhecidas e a superficie nao
   tem como distingui-las de fora — evento monetario ainda no budget_outbox
   (durável, so nao publicado) e linha perdida de verdade. Chamar tudo de
   corrupcao mentiria na metade dos casos. */
export function buracosDeSeq(eventos) {
  const porFonte = new Map();
  for (const e of eventos) {
    const chave = e.__fonte ?? 'cli';
    const lista = porFonte.get(chave) ?? [];
    lista.push(e.seq);
    porFonte.set(chave, lista);
  }

  const buracos = [];
  for (const [fonte, seqs] of porFonte) {
    seqs.sort((a, b) => a - b);
    for (let i = 1; i < seqs.length; i += 1) {
      if (seqs[i] > seqs[i - 1] + 1) {
        buracos.push({
          fonte,
          de: seqs[i - 1] + 1,
          ate: seqs[i] - 1,
          faltando: seqs[i] - seqs[i - 1] - 1,
        });
      }
    }
  }
  return buracos;
}

/* `GET /dados` do painel em execucao devolve {nos, arestas, eventos}. Usamos so
   `eventos`: `nos`/`arestas` vem do `grafo_do_log` do painel, que e outra
   projecao, com outras regras — misturar as duas daria uma superficie que
   discorda de si mesma. A projecao desta pasta e a unica autoridade aqui. */
export async function lerDoPainel(leitor) {
  const resposta = await fetch('/dados', { cache: 'no-store' });
  if (!resposta.ok) {
    throw new Error(`painel indisponivel (${resposta.status}) em /dados`);
  }
  const tipo = (resposta.headers.get('content-type') || '').split(';')[0].trim();
  if (tipo !== 'application/json') {
    /* O painel devolve o index.html com 200 para rota que nao conhece. Sem esta
       checagem o JSON.parse estoura com um erro que nao diz nada. */
    throw new Error(
      `/dados respondeu ${tipo || 'sem content-type'} em vez de JSON — ` +
        'reinicie o painel com python3 -m motor_painel.painel',
    );
  }

  const dados = await resposta.json();
  const brutos = Array.isArray(dados?.eventos) ? dados.eventos : [];
  const eventos = brutos
    .filter((e) => typeof e?.seq === 'number')
    .map((e) => ({ ...e, __fonte: leitor.fonte.id }))
    .sort((a, b) => a.seq - b.seq);

  return {
    ...leitor,
    eventos,
    /* O painel ja descartou o que nao parseou, entao a superficie NAO sabe
       quantas linhas eram ilegiveis: declarar 0 seria afirmar o que nao se viu.
       `null` e a diferenca entre "nenhuma" e "nao da para saber daqui". */
    ilegiveis: [],
    ilegiveisDesconhecidas: true,
    caudaParcial: null,
    reinicios: 0,
    buracos: buracosDeSeq(eventos),
    novos: eventos.length,
    lidoEm: new Date().toISOString(),
  };
}
