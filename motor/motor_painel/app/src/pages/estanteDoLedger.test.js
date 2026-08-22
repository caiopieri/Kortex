import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  BASE_CAMINHO,
  BASE_CHAVE,
  BASE_HASH,
  censoDoCorpus,
  chaveRelativa,
  conteudosRepetidos,
  agruparPorRun,
  itensDaEstante,
  resumoDeOrfaos,
} from './estanteDoLedger.js';

/* A estante, e as duas coisas que ela nao pode fazer: inventar tipo e escolher
 * identidade em silencio.
 *
 * ATENCAO AO CORPUS DESTES TESTES. Todo evento aqui que carrega `hash` e
 * `run_id` e SINTETICO -- escrito a mao neste arquivo. Medido no ledger de
 * producao em 2026-08-22: 0 de 47 `artefato.atualizou` carregam qualquer um dos
 * dois. O contrato entrou com a #24 e nenhuma run rodou desde entao.
 *
 * Testar com fixture inventada aqui e deliberado e e a unica maneira de travar
 * o caminho novo ANTES de existir corpus -- mas ninguem pode ler estes testes e
 * concluir que a proveniencia ja aparece no log. Ela nao aparece.
 */

const HASH_A = 'a'.repeat(64);
const HASH_B = 'b'.repeat(64);

function escrita(caminho, extra = {}) {
  return {
    evento: 'artefato.atualizou',
    nome: caminho.split('/').pop(),
    tipo: 'python',
    subagente: 'codificador',
    caminho,
    ...extra,
  };
}

describe('identidade: hash quando ha, lugar quando nao, e o cartao diz qual', () => {
  it('sem hash a identidade e a CHAVE RELATIVA, e o cartão declara isso', () => {
    const [item] = itensDaEstante([escrita('/x/runs/r1/artefatos/cod__a.py')]);
    assert.equal(item.identidade, 'r1/cod__a.py');
    assert.equal(item.baseDaIdentidade, BASE_CHAVE);
    assert.equal(item.hash, null);
  });

  it('com hash em TODAS as escritas, a identidade e o hash [corpus SINTÉTICO]', () => {
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
    ]);
    assert.equal(item.identidade, HASH_A);
    assert.equal(item.baseDaIdentidade, BASE_HASH);
  });

  it('hash em ALGUMAS escritas não basta: volta para o lugar [SINTÉTICO]', () => {
    /* Uma escrita sem hash é uma escrita cujo conteúdo não foi medido. Afirmar
       identidade de conteúdo com um buraco no meio seria afirmar o não-medido. */
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
      escrita('/x/runs/r1/artefatos/cod__a.py'),
    ]);
    assert.equal(item.baseDaIdentidade, BASE_CHAVE);
    assert.equal(item.hash, null);
    assert.equal(item.versoes, null);
  });

  it('hash malformado é ignorado: só SHA-256 de 64 hex conta', () => {
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: 'nao-e-hash', run_id: 'r1' }),
    ]);
    assert.equal(item.baseDaIdentidade, BASE_CHAVE);
  });

  it('caminho fora de `artefatos/` cai para o caminho cru, e declara', () => {
    const [item] = itensDaEstante([escrita('/solto/a.py')]);
    assert.equal(item.baseDaIdentidade, BASE_CAMINHO);
    assert.equal(item.identidade, '/solto/a.py');
  });
});

describe('a chave é relativa: clonar o repo não pode criar 40 órfãos', () => {
  it('o mesmo artefato em dois checkouts tem a MESMA chave', () => {
    assert.equal(
      chaveRelativa('/Users/x/Kortex/motor/runs/r1/artefatos/cod__a.py'),
      chaveRelativa('/home/cap/Kortex/motor/runs/r1/artefatos/cod__a.py'),
    );
  });

  it('duas máquinas produzem UM cartão, não dois', () => {
    const itens = itensDaEstante([
      escrita('/Users/x/Kortex/motor/runs/r1/artefatos/cod__a.py'),
      escrita('/home/cap/Kortex/motor/runs/r1/artefatos/cod__a.py'),
    ]);
    assert.equal(itens.length, 1);
    assert.equal(itens[0].escritas, 2);
  });

  it('recusa caminho sem pasta `artefatos/`, e a pasta sozinha', () => {
    assert.equal(chaveRelativa('/tmp/solto.py'), null);
    assert.equal(chaveRelativa('artefatos/solto.py'), null);
    /* A pasta sem arquivo dentro daria `r1/` -- uma chave que nomeia uma run e
       um artefato vazio. O lado Python tinha esse defeito e foi corrigido junto:
       o teste cruzado é quem pegou. */
    assert.equal(chaveRelativa('/x/runs/r1/artefatos'), null);
    assert.equal(chaveRelativa('/x/runs/r1/artefatos/a/b.py'), 'r1/a/b.py');
  });

  it('derivar chave NÃO julga se é produto: `__pycache__` recebe chave', () => {
    /* Deliberado, e o teste cruzado com o Python depende disto. Decidir o que é
       produto acontece onde o DISCO é percorrido (`orfaos_de_artefato`), porque
       é lá que lixo de ferramenta aparece -- 109 arquivos contra 49 de produto,
       medido. Evento nunca aponta para `__pycache__`. Filtrar aqui fazia as duas
       linguagens discordarem em silêncio. */
    assert.equal(chaveRelativa('/x/runs/r1/artefatos/__pycache__/a.pyc'), 'r1/__pycache__/a.pyc');
  });
});

describe('escrita não é revisão, e a tela não pode dizer que é', () => {
  it('sem hash, `versoes` é null — não 1, não 0', () => {
    /* `null` é "não foi medido". Um `1` afirmaria que o conteúdo nunca mudou,
       e ninguém mediu isso. É a mesma distinção do `ilegiveisDesconhecidas`. */
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r1/artefatos/cod__a.py'),
    ]);
    assert.equal(item.escritas, 2);
    assert.equal(item.versoes, null);
  });

  it('duas escritas do MESMO conteúdo são 2 escritas e 1 versão [SINTÉTICO]', () => {
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
    ]);
    assert.equal(item.escritas, 2);
    assert.equal(item.versoes, 1);
  });

  it('duas escritas com conteúdo diferente são 2 versões [SINTÉTICO]', () => {
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_B, run_id: 'r1' }),
    ]);
    assert.equal(item.versoes, 2);
    /* Dois hashes distintos no mesmo lugar: a identidade não pode ser um deles. */
    assert.equal(item.baseDaIdentidade, BASE_CHAVE);
  });
});

describe('o mesmo conteúdo em dois lugares', () => {
  it('com hash, é detectável [SINTÉTICO]', () => {
    const itens = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
      escrita('/x/runs/r2/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r2' }),
    ]);
    const rep = conteudosRepetidos(itens);
    assert.equal(rep.length, 1);
    assert.deepEqual(rep[0].lugares.sort(), ['r1/cod__a.py', 'r2/cod__a.py']);
  });

  it('sem hash é INDETECTÁVEL, e o resultado vazio é por falta de medida', () => {
    const itens = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r2/artefatos/cod__a.py'),
    ]);
    assert.deepEqual(conteudosRepetidos(itens), []);
    assert.equal(censoDoCorpus(itens).comVersaoMedida, 0);
  });
});

describe('a tela não inventa tipo', () => {
  it('tipo ausente fica null — nunca deduzido da extensão', () => {
    const [item] = itensDaEstante([
      { evento: 'artefato.atualizou', caminho: '/x/runs/r1/artefatos/a.py', nome: 'a.py' },
    ]);
    assert.equal(item.tipo, null);
    assert.equal(censoDoCorpus([item]).semTipo, 1);
  });

  it('47 de 47 "python" produzem UM tipo, e isso é a verdade sobre a fábrica', () => {
    const itens = itensDaEstante(
      Array.from({ length: 5 }, (_, i) => escrita(`/x/runs/r1/artefatos/cod__a${i}.py`)),
    );
    const censo = censoDoCorpus(itens);
    assert.deepEqual(censo.tiposDeclarados, ['python']);
    assert.equal(censo.tipos, 1);
  });
});

describe('o censo, que é o slot de proveniência', () => {
  it('sem proveniência nenhuma, o slot precisa aparecer', () => {
    const itens = itensDaEstante([escrita('/x/runs/r1/artefatos/cod__a.py')]);
    const censo = censoDoCorpus(itens);
    assert.equal(censo.comProveniencia, 0);
    assert.equal(censo.semProveniencia, 1);
    assert.equal(censo.precisaDeclararProveniencia, true);
  });

  it('o slot SE APAGA sozinho quando todo artefato declara [SINTÉTICO]', () => {
    /* É a propriedade que separa este slot de um aviso escrito à mão: ele para
       de aparecer quando deixa de ser verdade, sem ninguém editar nada. */
    const itens = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
    ]);
    assert.equal(censoDoCorpus(itens).precisaDeclararProveniencia, false);
  });

  it('corpus vazio não acende slot nenhum', () => {
    const censo = censoDoCorpus([]);
    assert.equal(censo.artefatos, 0);
    assert.equal(censo.precisaDeclararProveniencia, false);
  });

  it('conta escrita e artefato separadamente', () => {
    const itens = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r1/artefatos/t__b.py'),
    ]);
    const censo = censoDoCorpus(itens);
    assert.equal(censo.artefatos, 2);
    assert.equal(censo.escritas, 3);
    assert.equal(censo.reescritos, 1);
  });

  it('entrada inválida não estoura e não inventa', () => {
    assert.deepEqual(itensDaEstante(null), []);
    assert.deepEqual(itensDaEstante([{ evento: 'outro.evento' }]), []);
    assert.equal(censoDoCorpus(null).artefatos, 0);
  });
});

describe('run: do evento, nunca do diretório', () => {
  it('sem run_id no evento, o cartão não recebe run [é o caso de 47/47 hoje]', () => {
    /* O diretório `runs/r1/` SUGERE a run e é exatamente essa inferência que a
       regra canônica proíbe. A chave usa `r1` como localização, não como run. */
    const [item] = itensDaEstante([escrita('/x/runs/r1/artefatos/cod__a.py')]);
    assert.equal(item.runId, null);
    assert.equal(item.lugar, 'r1/cod__a.py');
  });

  it('o mesmo lugar escrito por duas runs é marcado, não escondido [SINTÉTICO]', () => {
    const [item] = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'r1' }),
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_B, run_id: 'r2' }),
    ]);
    assert.equal(item.runsConflitantes, true);
  });
});

describe('a declaração de incompletude (#22): órfão aparece, e aparece SEPARADO', () => {
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

  it('a contagem de orfaos aparece', () => {
    const r = resumoDeOrfaos(payload);
    assert.equal(r.artefatos, 9);
    assert.equal(r.runs, 1);
    assert.equal(r.emDisco, 49);
    assert.equal(r.comEvento, 40);
    assert.equal(r.precisaDeclarar, true);
  });

  it('orfao nunca entra na lista do ledger', () => {
    // O invariante da issue #22. Fundir as duas listas — mesmo "so para exibir
    // junto" — derruba este teste, que e o ponto.
    const doLedger = itensDaEstante([escrita('/x/runs/r9/artefatos/cod__a.py')]);
    const orfaos = resumoDeOrfaos(payload);

    const caminhos = doLedger.map((a) => a.caminho);
    for (const orfao of orfaos.amostra) {
      assert.ok(!caminhos.includes(orfao), `orfao ${orfao} vazou para a lista do ledger`);
    }
    assert.equal(doLedger.length, 1);
  });

  it('sem orfao nenhum a tela nao declara nada', () => {
    const r = resumoDeOrfaos({ ...payload, artefatos_orfaos: 0, runs_orfas: [], amostra: [] });
    assert.equal(r.precisaDeclarar, false);
  });

  it('ledger legado ilegivel sozinho ja obriga a declarar', () => {
    const r = resumoDeOrfaos({
      ...payload,
      artefatos_orfaos: 0,
      runs_orfas: [],
      legado_ilegivel: 'sequencia invalida na linha 9',
    });
    assert.equal(r.precisaDeclarar, true);
    assert.equal(r.legadoIlegivel, 'sequencia invalida na linha 9');
  });

  it('amostra truncada e declarada, nunca silenciosa', () => {
    const r = resumoDeOrfaos({ ...payload, amostra_truncada: true });
    assert.equal(r.amostraTruncada, true);
  });

  it('payload ausente vira null em vez de zero fabricado', () => {
    // null = "nao sei"; 0 = "verifiquei e nao ha". Colapsar os dois faria a tela
    // afirmar saude que ninguem mediu.
    assert.equal(resumoDeOrfaos(null), null);
    assert.equal(resumoDeOrfaos(undefined), null);
  });

});

describe('agrupar por run: a ausência é do corpus, não de cada artefato', () => {
  it('sem run declarada, tudo cai num grupo só', () => {
    /* Hoje é 40 de 40. A alternativa — cada cartão dizendo "na run: —" —
       repetiria a mesma frase 40 vezes, e repetição treina o olho a pular. */
    const itens = itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r2/artefatos/cod__b.py'),
    ]);
    const grupos = agruparPorRun(itens);
    assert.equal(grupos.length, 1);
    assert.equal(grupos[0].runId, null);
    assert.equal(grupos[0].itens.length, 2);
  });

  it('o diretório NÃO vira grupo: r1 e r2 são lugares, não runs', () => {
    /* O caso que separa agrupar de inventar. Os dois caminhos vivem em
       diretórios diferentes e nenhum evento declara run: um grupo, não dois. */
    const grupos = agruparPorRun(itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r2/artefatos/cod__b.py'),
    ]));
    assert.equal(grupos.length, 1);
  });

  it('run declarada vira grupo próprio, e vem ANTES do indeclarado [SINTÉTICO]', () => {
    const grupos = agruparPorRun(itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py'),
      escrita('/x/runs/r2/artefatos/cod__b.py', { hash: HASH_A, run_id: 'run-viva' }),
    ]));
    assert.deepEqual(grupos.map((g) => g.runId), ['run-viva', null]);
  });

  it('quando tudo declarar, o grupo indeclarado SOME [SINTÉTICO]', () => {
    /* A propriedade que faz a tela não precisar de redesenho quando o corpus
       chegar: mesma forma nos dois mundos. */
    const grupos = agruparPorRun(itensDaEstante([
      escrita('/x/runs/r1/artefatos/cod__a.py', { hash: HASH_A, run_id: 'run-viva' }),
      escrita('/x/runs/r2/artefatos/cod__b.py', { hash: HASH_B, run_id: 'run-viva' }),
    ]));
    assert.equal(grupos.length, 1);
    assert.equal(grupos[0].runId, 'run-viva');
    assert.ok(!grupos.some((g) => g.runId === null));
  });

  it('lista vazia não inventa grupo', () => {
    assert.deepEqual(agruparPorRun([]), []);
    assert.deepEqual(agruparPorRun(null), []);
  });
});
