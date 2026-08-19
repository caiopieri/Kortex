import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatarCusto } from './formatarCusto.js';

test('custo nulo não estoura a renderização do resumo', () => {
  assert.doesNotThrow(() => formatarCusto(null));
  assert.equal(formatarCusto(null), 'US$ 0.00');
  assert.equal(formatarCusto(null, '—'), '—');
});
