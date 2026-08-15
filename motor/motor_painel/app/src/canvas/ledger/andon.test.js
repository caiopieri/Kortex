import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { classificarMotivo, ehFalha, localizar, TRUNCAMENTO } from './andon.js';

/* Este arquivo existe por um motivo so: as strings abaixo sao um CONTRATO com o
 * motor, copiadas literais do codigo dele. Contrato de string quebra em
 * silencio — nada aqui estoura, a falha so passa a ser desenhada errada. Um
 * teste e o unico lugar onde a mudanca aparece.
 *
 * Nao teste layout aqui. So a leitura das quatro formas.
 */

describe('as quatro formas literais de motivo', () => {
  it('1 · modelo não respondeu: efeito OCORREU e é retentável', () => {
    const r = classificarMotivo('modelo não respondeu');
    assert.equal(r.forma, 'sem-resposta');
    assert.equal(r.efeito, 'ocorreu');
    assert.equal(r.retentavel, true);
    assert.equal(r.terminal, false);
  });

  it('1 · sem acento também casa: acento não pode decidir semântica', () => {
    assert.equal(classificarMotivo('modelo nao respondeu').forma, 'sem-resposta');
  });

  it('2 · bloqueio pré-efeito: NENHUM efeito, e lista as rotas na ordem', () => {
    const r = classificarMotivo('bloqueio pré-efeito: rota-a=teto; rota-b=sessao invalida');
    assert.equal(r.forma, 'bloqueio-pre-efeito');
    assert.equal(r.efeito, 'nenhum');
    assert.equal(r.retentavel, true);
    assert.deepEqual(r.rotas, [
      { rota: 'rota-a', motivo: 'teto' },
      { rota: 'rota-b', motivo: 'sessao invalida' },
    ]);
  });

  it('2 · o motivo da rota pode conter "=" e só o primeiro separa', () => {
    const r = classificarMotivo('bloqueio pré-efeito: rota-a=chave=valor');
    assert.deepEqual(r.rotas, [{ rota: 'rota-a', motivo: 'chave=valor' }]);
  });

  it('3 · status entre parênteses no fim: TERMINAL, não é retry', () => {
    const r = classificarMotivo('reserva não confirmada (reservado)');
    assert.equal(r.forma, 'terminal-ambiguo');
    assert.equal(r.efeito, 'desconhecido');
    assert.equal(r.retentavel, false);
    assert.equal(r.terminal, true);
    assert.equal(r.statusReserva, 'reservado');
  });

  it('4 · nenhuma rota elegível NÃO tem o prefixo da forma 2, e mesmo assim casa', () => {
    const r = classificarMotivo('nenhuma rota elegível');
    assert.equal(r.forma, 'sem-rota');
    assert.equal(r.efeito, 'nenhum');
    assert.equal(r.retentavel, false);
  });
});

describe('truncamento em 400 pode comer o status da forma 3', () => {
  it('motivo no limite vira aviso, nunca "seguro"', () => {
    const r = classificarMotivo('x'.repeat(TRUNCAMENTO));
    assert.equal(r.forma, 'nao-declarado');
    assert.equal(r.truncado, true);
    assert.match(r.rotulo, /truncado/);
  });

  /* A regra que o fundador fixou: presença de `(algo)` CONFIRMA terminal;
     ausência NÃO prova que não é. */
  it('ausência de status nunca descarta terminal', () => {
    for (const m of ['falha externa do executor', 'x'.repeat(TRUNCAMENTO)]) {
      assert.equal(classificarMotivo(m).terminalDescartado, false, m.slice(0, 20));
    }
  });

  it('as formas declaradas DESCARTAM terminal, porque declaram o efeito', () => {
    for (const m of ['modelo não respondeu', 'bloqueio pré-efeito: a=b', 'nenhuma rota elegível']) {
      assert.equal(classificarMotivo(m).terminalDescartado, true, m);
    }
  });
});

describe('motivos legados do log de hoje', () => {
  /* Copiados do motor/log.jsonl real. Nenhum casa com as quatro formas, e e
     correto que nao casem: sao pre-commit e nao declaram efeito. */
  const legados = [
    'falha externa do executor',
    'falha externa do executor: ErroOrcamento: teto divergente para sessao existente',
    'orcamento indisponivel',
  ];

  for (const m of legados) {
    it(`"${m.slice(0, 40)}" → não-declarado, efeito desconhecido`, () => {
      const r = classificarMotivo(m);
      assert.equal(r.forma, 'nao-declarado');
      assert.equal(r.efeito, 'desconhecido');
      assert.equal(r.retentavel, null);
    });
  }
});

describe('onde a falha resolve', () => {
  const nos = new Set(['codificador', 'testador']);

  it('executor.erro nomeia o nó e vai para ele', () => {
    const d = localizar({ evento: 'executor.erro', executor: 'codificador', seq: 1 }, nos);
    assert.equal(d.classe, 'localizada');
    assert.equal(d.no, 'codificador');
  });

  it('nó citado que a run não declarou NÃO vira nó novo: cai na estação', () => {
    const d = localizar({ evento: 'executor.erro', executor: 'fantasma', seq: 2 }, nos);
    assert.equal(d.classe, 'sistemica');
    assert.equal(d.naoResolvido, 'fantasma');
  });

  it('portao.reprovado resolve o nó depois do ":"', () => {
    const d = localizar({ evento: 'portao.reprovado', portao: 'verifier:testador', seq: 3 }, nos);
    assert.equal(d.classe, 'localizada');
    assert.equal(d.no, 'testador');
  });

  it('portão sem nó resolvível é sistêmico, não um chute', () => {
    const d = localizar({ evento: 'portao.reprovado', portao: 'cobertura', seq: 4 }, nos);
    assert.equal(d.classe, 'sistemica');
  });

  it('custo.bloqueado não nomeia nó: sistêmico', () => {
    assert.equal(localizar({ evento: 'custo.bloqueado', seq: 5 }, nos).classe, 'sistemica');
  });

  it('validador aprovado não é falha', () => {
    assert.equal(ehFalha({ evento: 'validador.rodou', aprovado: true }), false);
    assert.equal(ehFalha({ evento: 'validador.rodou', aprovado: false }), true);
  });
});

describe('não se aplica é diferente de não descartado', () => {
  const nos = new Set(['codificador']);

  it('falha sem cadeia de failover não vira alarme de terminal', () => {
    for (const e of [
      { evento: 'custo.bloqueado', seq: 1 },
      { evento: 'portao.reprovado', portao: 'cobertura', seq: 2 },
      { evento: 'tarefa.abortada', seq: 3 },
    ]) {
      const d = localizar(e, nos);
      assert.equal(d.custo.forma, 'nao-se-aplica');
      assert.equal(d.custo.terminalDescartado, null, e.evento);
    }
  });

  it('executor.erro sem forma declarada continua sendo dúvida real', () => {
    const d = localizar(
      { evento: 'executor.erro', executor: 'codificador', motivo: 'falha externa', seq: 4 },
      nos,
    );
    assert.equal(d.custo.terminalDescartado, false);
  });
});
