import { test } from 'node:test';
import assert from 'node:assert/strict';
import { artefatosDoLedger, resumoDeOrfaos } from './artefatos.js';

const evento = (extra) => ({
  t: 1.5,
  evento: 'artefato.atualizou',
  nome: 'solucao.py',
  tipo: 'python',
  subagente: 'codificador',
  caminho: '/m/runs/r1/artefatos/codificador__solucao.py',
  ...extra,
});

/* ── o artefato que o ledger explica ── */

test('deriva artefato de evento', () => {
  const [a] = artefatosDoLedger([evento()]);
  assert.equal(a.nome, 'solucao.py');
  assert.equal(a.tipo, 'python');
  assert.equal(a.subagente, 'codificador');
  assert.equal(a.revisoes, 1);
});

test('mesmo caminho duas vezes e uma linha com duas revisoes', () => {
  const lista = artefatosDoLedger([evento(), evento({ t: 9 })]);
  assert.equal(lista.length, 1);
  assert.equal(lista[0].revisoes, 2);
});

test('evento que nao e de artefato nao entra', () => {
  assert.deepEqual(artefatosDoLedger([{ evento: 'executor.chamado', caminho: '/x' }]), []);
});

test('tipo ausente fica null em vez de virar extensao do caminho', () => {
  // Deduzir "py" do nome do arquivo seria inferir do disco o que o motor
  // nao declarou — o mesmo defeito da issue #22 numa escala menor.
  const [a] = artefatosDoLedger([evento({ tipo: undefined })]);
  assert.equal(a.tipo, null);
});

test('entrada nao-lista nao estoura', () => {
  assert.deepEqual(artefatosDoLedger(null), []);
  assert.deepEqual(artefatosDoLedger({ eventos: [] }), []);
});

/* ── o teste causal da #22: o orfao aparece, e aparece separado ── */

const payload = {
  artefatos_em_disco: 49,
  artefatos_com_evento: 40,
  artefatos_orfaos: 9,
  arquivos_de_ferramenta_ignorados: 109,
  runs_em_disco: 34,
  runs_explicadas: 26,
  runs_orfas: ['20260623-165836-afef73'],
  amostra: ['20260623-165836-afef73/artefatos/plano-testes__plano-testes.md'],
  amostra_truncada: false,
  legado_ilegivel: null,
};

test('a contagem de orfaos aparece', () => {
  const r = resumoDeOrfaos(payload);
  assert.equal(r.artefatos, 9);
  assert.equal(r.runs, 1);
  assert.equal(r.emDisco, 49);
  assert.equal(r.comEvento, 40);
  assert.equal(r.precisaDeclarar, true);
});

test('orfao nunca entra na lista do ledger', () => {
  // O invariante da issue #22. Fundir as duas listas — mesmo "so para exibir
  // junto" — derruba este teste, que e o ponto.
  const doLedger = artefatosDoLedger([evento()]);
  const orfaos = resumoDeOrfaos(payload);

  const caminhos = doLedger.map((a) => a.caminho);
  for (const orfao of orfaos.amostra) {
    assert.ok(!caminhos.includes(orfao), `orfao ${orfao} vazou para a lista do ledger`);
  }
  assert.equal(doLedger.length, 1);
});

test('sem orfao nenhum a tela nao declara nada', () => {
  const r = resumoDeOrfaos({ ...payload, artefatos_orfaos: 0, runs_orfas: [], amostra: [] });
  assert.equal(r.precisaDeclarar, false);
});

test('ledger legado ilegivel sozinho ja obriga a declarar', () => {
  const r = resumoDeOrfaos({
    ...payload,
    artefatos_orfaos: 0,
    runs_orfas: [],
    legado_ilegivel: 'sequencia invalida na linha 9',
  });
  assert.equal(r.precisaDeclarar, true);
  assert.equal(r.legadoIlegivel, 'sequencia invalida na linha 9');
});

test('amostra truncada e declarada, nunca silenciosa', () => {
  const r = resumoDeOrfaos({ ...payload, amostra_truncada: true });
  assert.equal(r.amostraTruncada, true);
});

test('payload ausente vira null em vez de zero fabricado', () => {
  // null = "nao sei"; 0 = "verifiquei e nao ha". Colapsar os dois faria a tela
  // afirmar saude que ninguem mediu.
  assert.equal(resumoDeOrfaos(null), null);
  assert.equal(resumoDeOrfaos(undefined), null);
});
