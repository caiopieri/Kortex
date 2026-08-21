/* Layout 3D da run. UMA PROJECAO, N RENDERIZADORES.
 *
 * Este modulo NAO projeta nada. Ele recebe a run que o `projetarRun` ja
 * produziu -- que por sua vez recebe a topologia canonica de `/dados`
 * (`grafo_do_log`, issue #15) -- e so decide ONDE cada no fica no espaco. Nao
 * deriva estado, nao classifica falha, nao inventa no nem aresta. Se um no
 * aparecer aqui e nao no 2D, ou vice-versa, o teste irmao do #15 cai.
 *
 * A ONDA E O EIXO Z, E ISSO NAO E ESCOLHA ESTETICA.
 *
 * Grafo force-directed livre INVENTA POSICAO: a coordenada vira funcao da
 * fisica e nao de nada que o ledger declare. Seria a mesma falta que tirou o
 * MapaGeral do painel (ele inventava "projeto" a partir de `objetivo`), so que
 * em coordenada. A unica coisa parecida com posicao que o ledger emite e a
 * ONDA (`onda.iniciada`) -- a camada topologica.
 *
 * Entao:
 *   Z  = onda declarada. FIXO (`fz`), a fisica nao encosta.
 *   XY = livre para a fisica espalhar DENTRO da onda.
 *
 * O 2D usa a mesma onda como eixo X (`layout.js`: `x = no.onda * COLUNA`) e
 * arbitra a ordem dentro da onda empilhando em linha. O 3D arbitra a mesma
 * ordem com fisica no plano. Os dois arbitram exatamente a mesma coisa -- o que
 * o ledger nao diz -- e nenhum dos dois arbitra a onda, que o ledger diz.
 *
 * O que o 3D ganha e o que o 2D nao da: profundidade de onda legivel de relance.
 */

/* Espacamento entre ondas em unidades de mundo 3D. Nao ha relacao com o
   `COLUNA` do 2D: la a largura do cartao manda, aqui a escala e da camera. */
export const PROFUNDIDADE_ONDA = 240;

/* `motor` e o no raiz legado do contrato e nao declara onda; `projetarRun` ja
   normaliza isso para 0. A guarda aqui e para o modulo continuar puro mesmo se
   chamado com run de outra origem -- e para `profundidadeDaOnda` nunca devolver
   NaN, que na fisica vira no desaparecido em vez de erro. */
export function profundidadeDaOnda(onda) {
  return (Number.isInteger(onda) ? onda : 0) * PROFUNDIDADE_ONDA;
}

/* Semente ESTAVEL para o XY inicial, derivada do id.
 *
 * Sem semente, `d3-force-3d` sorteia a posicao inicial e o mesmo grafo cai
 * diferente a cada abertura. Com ela, a mesma run desenha igual toda vez: o
 * layout continua sendo arbitrio (o ledger nao diz XY), mas e arbitrio
 * REPRODUZIVEL, e operador que reabre a tela reconhece o que viu. */
function anguloDoId(id) {
  let h = 0x811c9dc5;
  for (let i = 0; i < id.length; i += 1) {
    h = Math.imul(h ^ id.charCodeAt(i), 0x01000193) >>> 0;
  }
  /* Avalanche final. Sem ela, `h * 31 + c` deixa ids vizinhos ("A" e "B") com
     hashes vizinhos e portanto angulos quase iguais -- dois nos da mesma onda
     nasciam praticamente em cima um do outro e dependiam da fisica para se
     separar. */
  h ^= h >>> 16;
  h = Math.imul(h, 0x7feb352d) >>> 0;
  h ^= h >>> 15;
  return (h / 0x100000000) * Math.PI * 2;
}

const RAIO_INICIAL = 90;

/* Traduz a run projetada no par (nodes, links) que o renderizador consome.
 *
 * Todo campo copiado aqui vem de `projetarRun`. Nenhum e recalculado: `estado`
 * e do portao/andon, `falhas` ja vem classificada, `artefatos` ja vem
 * deduplicada por caminho. A tentacao de reler `eventos` aqui para colorir no
 * e exatamente o defeito da #15, e e por isso que esta funcao nem recebe
 * `run.eventos`. */
export function projetar3d(run) {
  if (!run || !Array.isArray(run.nos)) return { nodes: [], links: [] };

  const nodes = run.nos.map((no) => {
    const angulo = anguloDoId(no.id);
    return {
      id: no.id,
      tipo: no.tipo ?? null,
      papel: no.papel ?? null,
      onda: Number.isInteger(no.onda) ? no.onda : 0,
      estado: no.estado,
      falhas: no.falhas?.length ?? 0,
      artefatos: no.artefatos?.length ?? 0,
      /* `fz` FIXO: d3-force-3d nunca move um eixo fixado. E aqui que a onda
         declarada para de ser um numero e vira o lugar. */
      fz: profundidadeDaOnda(no.onda),
      x: Math.cos(angulo) * RAIO_INICIAL,
      y: Math.sin(angulo) * RAIO_INICIAL,
    };
  });

  const presentes = new Set(nodes.map((n) => n.id));
  /* Aresta para no ausente e descartada em silencio NO 2D tambem
     (`Grafo.jsx` faz `if (!de || !para) return null`). Manter o mesmo
     comportamento e o que faz "mesmo grafo" ser verdade; divergir aqui seria a
     divergencia que o teste existe para pegar. */
  const links = (run.arestas ?? [])
    .filter((a) => presentes.has(a.de) && presentes.has(a.para))
    .map((a) => ({ source: a.de, target: a.para }));

  return { nodes, links };
}

/* Ondas distintas, na ordem. Usado pelo renderizador para desenhar a regua de
   profundidade -- sem ela o operador ve nos flutuando e nao ve que a
   profundidade SIGNIFICA algo. */
export function ondasDaRun(run) {
  const vistas = new Set();
  for (const no of run?.nos ?? []) {
    vistas.add(Number.isInteger(no.onda) ? no.onda : 0);
  }
  return [...vistas].sort((a, b) => a - b);
}
