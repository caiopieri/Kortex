import test from 'node:test';
import assert from 'node:assert/strict';

import { criarLeitor, lerIncremental } from './ler.js';

test('offset desalinhado usa o header de recuperacao sem repetir 416', async () => {
  const respostas = [
    {
      status: 416,
      ok: false,
      headers: new Headers({
        'x-ledger-offset-corrigido': '0',
        'x-ledger-tamanho': '42',
      }),
      text: async () => '',
    },
    {
      status: 200,
      ok: true,
      headers: new Headers({ 'x-ledger-tamanho': '42' }),
      text: async () => '{"seq":1,"evento":"onda.iniciada"}\n',
    },
  ];
  const urls = [];
  const fetchAnterior = globalThis.fetch;
  globalThis.fetch = async (url) => {
    urls.push(url);
    return respostas.shift();
  };

  try {
    const leitor = { ...criarLeitor({ id: 'cli', rotulo: 'cli', url: '/ledger/log.jsonl' }), deslocamento: 7 };
    const resultado = await lerIncremental(leitor);
    assert.equal(resultado.reinicios, 1);
    assert.equal(resultado.eventos.length, 1);
    assert.equal(resultado.eventos[0].seq, 1);
    assert.deepEqual(urls, ['/ledger/log.jsonl?desde_byte=7', '/ledger/log.jsonl?desde_byte=0']);
  } finally {
    globalThis.fetch = fetchAnterior;
  }
});
