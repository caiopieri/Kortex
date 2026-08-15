/* Layout do grafo da run, em unidades de MUNDO.
 *
 * Arquivo separado de proposito: o desenho (`Grafo.jsx`) e o enquadramento
 * (`App.jsx`) precisam das mesmas constantes, e duplica-las faria a moldura
 * errar sozinha no dia em que o layout mudar.
 *
 * POSICAO E DERIVADA, NAO LIDA. O ledger nao emite coordenada; a unica coisa
 * parecida com posicao que ele declara e a ONDA (`onda.iniciada`), que e a
 * camada topologica. Coluna = onda, linha = ordem dentro da onda. Derivar
 * layout de grafo declarado nao e o mesmo que inventar onde uma falha mora — o
 * segundo e o que o ROADMAP proibe, e quem cuida dele e `andon.js`.
 */

export const COLUNA = 352;
export const LARGURA_NO = 260;

/* Altura ESTIMADA do cartao, e ela so pode ser estimada porque cada pedaco tem
   altura fixa no CSS: o motivo e cortado em duas linhas (`.falha-motivo`) e as
   rotas em uma. Sem esse corte a altura viraria funcao do texto e a estimativa
   escorregaria — foi exatamente o que fez os cartoes se sobreporem antes.
   Mexer nestes numeros exige mexer no CSS junto. */
const BASE = 46;
const ALTURA_ARTEFATO = 31;
const ALTURA_MAIS = 20;
const RESPIRO = 28;

/* Uma linha de texto do bloco de falha, ja com o espaco entre linhas. */
const LINHA_FALHA = 19;
const MOLDURA_FALHA = 22;

export const TETO_FALHAS = 3;

/* A altura de uma falha depende de QUANTAS linhas ela tem, e quantas linhas ela
   tem depende dos mesmos campos que `Falha` usa para decidir o que renderizar.
   Por isso a condicao esta duplicada aqui de forma literal: se uma das duas
   mudar sozinha, os cartoes voltam a se sobrepor. */
export function alturaDaFalha(falha) {
  const c = falha.custo ?? {};
  let linhas = 1; /* cabeca: evento + tentativa */
  if (falha.motivo && falha.motivo !== falha.evento) linhas += 1;
  if (c.rotulo) linhas += 1;
  if (c.rotas?.length) linhas += 1;
  if (falha.naoResolvido) linhas += 1;
  return MOLDURA_FALHA + linhas * LINHA_FALHA;
}

export function alturaDoNo(no) {
  const visiveis = no.falhas.slice(0, TETO_FALHAS);
  return (
    BASE +
    no.artefatos.length * ALTURA_ARTEFATO +
    visiveis.reduce((soma, f) => soma + alturaDaFalha(f), 0) +
    (no.falhas.length > TETO_FALHAS ? ALTURA_MAIS : 0)
  );
}

/* Ponto FIXO do mundo. Falha sistemica nao ganha posicao propria: ganha ESTE
   destino, sempre o mesmo. Se ele flutuasse junto com o grafo, voltaria a
   parecer que a falha tem lugar. */
export const ESTACAO = { x: -420, y: -60, largura: 300, altura: 140 };

/* Empilha por altura ACUMULADA dentro da onda, nao por passo fixo. Passo fixo
   so funciona com cartao de altura fixa, e o cartao daqui cresce com artefato e
   falha — foi o que fez cartoes se sobreporem na primeira versao. */
export function posicionarNos(run) {
  const proximoY = new Map();
  const lugares = new Map();
  for (const no of run.nos) {
    const y = proximoY.get(no.onda) ?? 0;
    lugares.set(no.id, { x: no.onda * COLUNA, y, altura: alturaDoNo(no) });
    proximoY.set(no.onda, y + alturaDoNo(no) + RESPIRO);
  }
  return lugares;
}

/* Retangulo que contem o grafo E a estacao. */
export function limitesDoGrafo(run) {
  if (!run) return null;
  let x1 = ESTACAO.x;
  let y1 = ESTACAO.y;
  let x2 = ESTACAO.x + ESTACAO.largura;
  let y2 = ESTACAO.y + ESTACAO.altura;

  for (const p of posicionarNos(run).values()) {
    x1 = Math.min(x1, p.x);
    y1 = Math.min(y1, p.y);
    x2 = Math.max(x2, p.x + LARGURA_NO);
    y2 = Math.max(y2, p.y + p.altura);
  }
  return { x1, y1, x2, y2, cx: (x1 + x2) / 2, cy: (y1 + y2) / 2 };
}
