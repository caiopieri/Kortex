import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { colFor } from './boardState.js';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../');
const ledger = fs.readFileSync(
  path.join(repo, 'exemplos', 'log-legado-10-runs.jsonl'),
  'utf8',
).trim().split('\n').map(JSON.parse);

test('gate pendente continua visivel mesmo com estado null do balde legado', () => {
  const specs = ledger.filter((evento) => evento.evento === 'spec.recebida');
  const escalouAoFundador = ledger.some(
    (evento) => evento.evento === 'escalado' && evento.para === 'fundador',
  );
  const houveDecisao = ledger.some(
    (evento) => evento.evento === 'decisao.fundador' || evento.evento === 'decisao.timeout',
  );
  assert.equal(specs.length, 10);
  assert.equal(escalouAoFundador, true);
  assert.equal(houveDecisao, false);

  const run = { id: 'legado:sem-proveniencia', estado: null };
  const gates = new Set([run.id]);
  assert.equal(colFor(run, gates), 'precisa');
  assert.equal(colFor({ ...run, estado: 'concluida' }, gates), 'precisa');
});
