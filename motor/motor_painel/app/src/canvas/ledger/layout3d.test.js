import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { posicionarNos } from './layout.js';
import { ondasDaRun, PROFUNDIDADE_ONDA, profundidadeDaOnda, projetar3d } from './layout3d.js';

/* O criterio de aceite do 3D, em teste.
 *
 * Duas coisas, e so estas duas:
 *   1. o 3D desenha O MESMO GRAFO que o 2D -- nenhum no a mais, nenhum a menos,
 *      nenhuma aresta inventada;
 *   2. o Z vem da ONDA DECLARADA, nao da fisica.
 *
 * A segunda e a que importa mais, porque e a que impede o 3D de virar o
 * MapaGeral: uma tela bonita mostrando uma estrutura que o ledger nunca
 * afirmou. Se alguem trocar `fz` por `z` (posicao inicial, que a fisica move),
 * os dois primeiros testes de Z caem.
 */

function no(id, onda, extra = {}) {
  return { id, onda, estado: 'sem-portao', falhas: [], artefatos: [], ...extra };
}

const RUN = {
  nos: [
    no('motor', 0),
    no('planner', 1, { estado: 'aprovado' }),
    no('A', 2, { falhas: [{ seq: 9, evento: 'executor.erro' }], estado: 'falhou' }),
    no('B', 2, { artefatos: [{ chave: 'x', nome: 'x.py' }] }),
  ],
  arestas: [
    { de: 'motor', para: 'planner' },
    { de: 'planner', para: 'A' },
    { de: 'planner', para: 'B' },
  ],
};

describe('o Z vem da onda declarada', () => {
  it('dois nós da MESMA onda têm sempre o mesmo Z', () => {
    const { nodes } = projetar3d(RUN);
    const a = nodes.find((n) => n.id === 'A');
    const b = nodes.find((n) => n.id === 'B');
    assert.equal(a.onda, b.onda);
    assert.equal(a.fz, b.fz);
  });

  it('dois nós de ondas DIFERENTES nunca têm o mesmo Z', () => {
    const { nodes } = projetar3d(RUN);
    const zPorOnda = new Map();
    for (const n of nodes) {
      const anterior = zPorOnda.get(n.onda);
      if (anterior !== undefined) assert.equal(anterior, n.fz);
      zPorOnda.set(n.onda, n.fz);
    }
    const zs = [...zPorOnda.values()];
    assert.equal(new Set(zs).size, zPorOnda.size);
  });

  it('o Z é FIXO (`fz`), não posição inicial que a física move', () => {
    /* `d3-force-3d` so respeita eixo prefixado com `f`. Um `z` solto seria
       chute inicial, e a simulacao empurraria o no para fora da sua onda --
       a tela passaria a mostrar profundidade que nao significa nada. */
    const { nodes } = projetar3d(RUN);
    for (const n of nodes) {
      assert.equal(typeof n.fz, 'number');
      assert.equal(Object.hasOwn(n, 'z'), false);
    }
  });

  it('a profundidade é monótona na onda', () => {
    assert.equal(profundidadeDaOnda(0), 0);
    assert.equal(profundidadeDaOnda(3), 3 * PROFUNDIDADE_ONDA);
    assert.ok(profundidadeDaOnda(2) > profundidadeDaOnda(1));
  });

  it('onda ausente não vira NaN', () => {
    /* NaN na física não estoura: o nó simplesmente some da tela. */
    assert.equal(profundidadeDaOnda(undefined), 0);
    assert.equal(profundidadeDaOnda(null), 0);
    assert.equal(profundidadeDaOnda(1.5), 0);
  });

  it('X e Y ficam LIVRES para a física — só o Z é declarado', () => {
    const { nodes } = projetar3d(RUN);
    for (const n of nodes) {
      assert.equal(Object.hasOwn(n, 'fx'), false);
      assert.equal(Object.hasOwn(n, 'fy'), false);
    }
  });

  it('o XY inicial é estável entre chamadas: a mesma run desenha igual', () => {
    const a = projetar3d(RUN).nodes.map((n) => [n.x, n.y]);
    const b = projetar3d(RUN).nodes.map((n) => [n.x, n.y]);
    assert.deepEqual(a, b);
  });

  it('nós da mesma onda não nascem no mesmo ponto', () => {
    const { nodes } = projetar3d(RUN);
    const a = nodes.find((n) => n.id === 'A');
    const b = nodes.find((n) => n.id === 'B');
    assert.ok(Math.hypot(a.x - b.x, a.y - b.y) > 1);
  });
});

describe('mesma run, mesma topologia nos dois renderizadores', () => {
  it('os nós do 3D são exatamente os nós do 2D', () => {
    const doTrid = projetar3d(RUN).nodes.map((n) => n.id);
    const do2d = [...posicionarNos(RUN).keys()];
    assert.deepEqual(doTrid, do2d);
  });

  it('as arestas do 3D são exatamente as arestas da run', () => {
    const { links } = projetar3d(RUN);
    assert.deepEqual(
      links.map((l) => [l.source, l.target]),
      RUN.arestas.map((a) => [a.de, a.para]),
    );
  });

  it('aresta para nó ausente é descartada nos DOIS, não só no 2D', () => {
    /* `Grafo.jsx` faz `if (!de || !para) return null`. Divergir aqui seria
       exatamente a divergencia que este arquivo existe para pegar. */
    const comFantasma = { ...RUN, arestas: [...RUN.arestas, { de: 'A', para: 'nao-existe' }] };
    const { links } = projetar3d(comFantasma);
    assert.equal(links.length, RUN.arestas.length);
  });

  it('não inventa nó a partir de aresta órfã', () => {
    const comFantasma = { ...RUN, arestas: [{ de: 'nao-existe', para: 'outro-inexistente' }] };
    const { nodes, links } = projetar3d(comFantasma);
    assert.equal(nodes.length, RUN.nos.length);
    assert.equal(links.length, 0);
  });

  it('run vazia ou ausente não estoura e não inventa', () => {
    assert.deepEqual(projetar3d(null), { nodes: [], links: [] });
    assert.deepEqual(projetar3d({ nos: [], arestas: [] }), { nodes: [], links: [] });
  });
});

describe('estado vem do projetarRun, não é recalculado aqui', () => {
  it('copia `estado`, `falhas` e `artefatos` sem reler evento', () => {
    const { nodes } = projetar3d(RUN);
    const a = nodes.find((n) => n.id === 'A');
    assert.equal(a.estado, 'falhou');
    assert.equal(a.falhas, 1);
    const b = nodes.find((n) => n.id === 'B');
    assert.equal(b.estado, 'sem-portao');
    assert.equal(b.artefatos, 1);
  });

  it('o módulo não aceita eventos: não há como reprojetar aqui', () => {
    /* A #15 aconteceu porque duas superficies liam o MESMO log e chegavam a
       grafos diferentes. `projetar3d` nunca ve `run.eventos` -- e a garantia
       estrutural de que isso nao se repete neste renderizador. */
    const comEventos = { ...RUN, eventos: [{ seq: 1, evento: 'executor.erro', executor: 'B' }] };
    assert.deepEqual(projetar3d(comEventos), projetar3d(RUN));
  });
});

describe('a régua de ondas', () => {
  it('lista as ondas distintas em ordem', () => {
    assert.deepEqual(ondasDaRun(RUN), [0, 1, 2]);
  });

  it('run vazia não tem régua', () => {
    assert.deepEqual(ondasDaRun(null), []);
  });
});
