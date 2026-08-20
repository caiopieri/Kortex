import test from 'node:test';
import assert from 'node:assert/strict';
import { projetarRun } from './projetar.js';

test('projetarRun preserva a topologia canonica recebida do painel', () => {
  const nos = [
    { id: 'motor', tipo: 'nucleo' },
    { id: 'A', tipo: 'subagente', papel: 'executor', onda: 0 },
    { id: 'B', tipo: 'subagente', papel: 'executor', onda: 1 },
  ];
  const arestas = [{ de: 'motor', para: 'A' }, { de: 'A', para: 'B' }];
  const projetado = projetarRun({ eventos: [], nos, arestas });

  assert.deepEqual(projetado.nos.map((no) => no.id), ['motor', 'A', 'B']);
  assert.deepEqual(projetado.arestas, arestas);
});
