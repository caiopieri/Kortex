import test from 'node:test';
import assert from 'node:assert/strict';
import { projetarRun, segmentarRuns } from './projetar.js';

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

test('segmentarRuns usa run_id e nao reparte legado por seq ou timestamp', () => {
  const eventos = [
    { __fonte: 'a', run_id: 'run-a', seq: 1, t: 10, evento: 'spec.recebida' },
    { __fonte: 'b', run_id: 'run-b', seq: 1, t: 10, evento: 'spec.recebida' },
    { __fonte: 'a', run_id: 'run-a', seq: 2, t: 1, evento: 'tarefa.concluida' },
    { __fonte: 'b', run_id: 'run-b', seq: 2, t: 1, evento: 'tarefa.concluida' },
    { __fonte: 'a', seq: 1, t: 0, evento: 'tarefa.concluida' },
    { __fonte: 'a', seq: 2, t: 100, evento: 'executor.chamado' },
  ];

  const runs = segmentarRuns(eventos);

  assert.deepEqual(runs.map((run) => run.id), ['run-a', 'run-b', 'legado:a']);
  assert.deepEqual(runs.map((run) => run.eventos.length), [2, 2, 2]);
});
