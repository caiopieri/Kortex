import { test } from 'node:test';
import assert from 'node:assert/strict';
import { linhasDoCatalogo } from './catalogoRotas.js';

/* O teste causal da issue #23: catálogo vazio NÃO pode produzir cartão.
   Reintroduzir o fallback de cinco workflows derruba os três primeiros. */

test('catalogo vazio produz zero linhas', () => {
  assert.deepEqual(linhasDoCatalogo([]), []);
});

test('catalogo ausente produz zero linhas', () => {
  assert.deepEqual(linhasDoCatalogo(null), []);
  assert.deepEqual(linhasDoCatalogo(undefined), []);
});

test('payload que nao e lista produz zero linhas', () => {
  // A API pode devolver `{erro: ...}`; isso é zero rota, não uma rota.
  assert.deepEqual(linhasDoCatalogo({ erro: 'x' }), []);
  assert.deepEqual(linhasDoCatalogo('pesquisa'), []);
});

test('nao inventa status, rota, nos, criado nem tags', () => {
  const [linha] = linhasDoCatalogo([
    { id: 'construcao', nome: 'construcao', descricao: 'd', subagentes: [], versao: null },
  ]);

  assert.deepEqual(Object.keys(linha).sort(), ['descricao', 'id', 'nome', 'subagentes', 'versao']);
  assert.equal(linha.status, undefined);
  assert.equal(linha.nos, undefined);
  assert.equal(linha.criado, undefined);
});

test('versao ausente permanece null, nunca 1.0.0', () => {
  assert.equal(linhasDoCatalogo([{ id: 'a' }])[0].versao, null);
  assert.equal(linhasDoCatalogo([{ id: 'a', versao: null }])[0].versao, null);
});

test('versao declarada e preservada', () => {
  assert.equal(linhasDoCatalogo([{ id: 'a', versao: '2.1' }])[0].versao, '2.1');
});

test('item sem id e descartado em vez de virar cartao sem identidade', () => {
  assert.deepEqual(linhasDoCatalogo([{ nome: 'sem id' }, null, 7]), []);
});

test('subagentes nao-lista vira lista vazia em vez de estourar a tela', () => {
  assert.deepEqual(linhasDoCatalogo([{ id: 'a', subagentes: 'codificador' }])[0].subagentes, []);
});
