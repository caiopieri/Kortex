/* A estante de artefatos: o que a fabrica produziu, cartao a cartao.
 *
 * O arquivo NAO se chama `estante.js` de proposito: `Estante.jsx` mora ao lado,
 * e num sistema de arquivos que ignora maiuscula (macOS) `./pages/Estante`
 * resolvia para ESTE modulo em vez do componente -- build quebrado aqui, e
 * resolucao DIFERENTE no Linux do runner, que e o modo pior de errar.
 *
 * `DECISAO-interface-cortes-e-estante.md` §4. Nao e vitrine de janelas vivas --
 * a janelinha viva depende de QUATRO contratos e so o primeiro existe. E uma
 * estante, e cada cartao carrega o que o evento declara mais SLOTS VAZIOS
 * NOMEADOS, que e o ponto da tela: tornar o contrato que falta visivel toda vez
 * que ela abre, em vez de num documento que ninguem rele.
 *
 * MEDIDO no checkout de producao em 2026-08-22, depois das issues #24/#25/#28:
 *
 *     47 eventos `artefato.atualizou`      1 tipo (`python` 47/47)
 *     3 nomes distintos                    40 caminhos distintos
 *     0 com `hash`                         0 com `run_id`
 *     49 artefatos em disco                9 sem evento nenhum (#22)
 *
 * A #24 destravou o CONTRATO, nao o CORPUS: os dois emissores passam `hash` e o
 * validador exige `run_id`+`hash` juntos ou nenhum, mas nenhuma run rodou desde
 * o merge, entao 47 de 47 sao legado. Este modulo tem de funcionar nos dois
 * mundos e DIZER em qual esta.
 *
 * ARMADILHA MEDIDA, para quem for recontar: o log tem 290 eventos com `run_id`
 * e sao TODOS `custo.*` -- proveniencia monetaria anterior a #24. Contar
 * `run_id` sem separar por tipo de evento faz concluir que a proveniencia de
 * artefato existe. Nao existe.
 */

const EVENTOS_DE_ARTEFATO = new Set([
  'artefato.atualizou',
  /* Nomes legados que ja apareceram no log e nao sao emitidos hoje. Run antiga
     continua legivel; nao e contrato novo. */
  'artefato.gravado',
  'artefato.atualizado',
]);

/* Sobre o que a identidade de um cartao esta apoiada. O cartao MOSTRA isto --
   escolher em silencio entre hash e caminho seria decidir por quem le. */
export const BASE_HASH = 'hash';
export const BASE_CHAVE = 'chave';
export const BASE_CAMINHO = 'caminho';

/* `<run_id>/<resto>` relativo a `artefatos/`, NUNCA o caminho absoluto.
 *
 * O `caminho` do evento aponta para o checkout onde a run rodou. Comparar por
 * absoluto faz TODO artefato virar orfao ao clonar o repositorio noutro
 * diretorio -- um alarme de 100% que nao significa nada. Gemeo de
 * `_chave_de_artefato` no `painel.py`; um teste cruzado roda os dois e prova que
 * derivam a mesma chave para o mesmo caminho.
 *
 * NAO filtra lixo de ferramenta (`__pycache__` e afins). Derivar chave e uma
 * coisa, julgar se algo e produto e outra -- e o julgamento mora onde o DISCO e
 * percorrido (`orfaos_de_artefato`), nao aqui: evento nunca aponta para
 * `__pycache__`. Filtrar so deste lado fazia as duas linguagens discordarem em
 * silencio, que foi o que o teste cruzado pegou. */
export function chaveRelativa(caminho) {
  if (typeof caminho !== 'string' || !caminho) return null;
  const partes = caminho.split('/').filter(Boolean);
  const i = partes.indexOf('artefatos');
  if (i <= 0) return null;
  const resto = partes.slice(i + 1);
  if (resto.length === 0) return null;
  return `${partes[i - 1]}/${resto.join('/')}`;
}

function ehHash(v) {
  return typeof v === 'string' && /^[0-9a-f]{64}$/.test(v);
}

/* Um cartao por ARTEFATO, nao por escrita.
 *
 * `artefato.atualizou` dispara a cada gravacao, entao a mesma saida aparece
 * varias vezes numa run que refez o trabalho. Agrupar por LUGAR e o que existe
 * hoje; o hash e o que um dia permite agrupar por CONTEUDO. */
export function itensDaEstante(eventos) {
  if (!Array.isArray(eventos)) return [];

  const porLugar = new Map();
  for (const ev of eventos) {
    if (!EVENTOS_DE_ARTEFATO.has(ev?.evento)) continue;
    const caminho = ev.caminho || ev.artefato || ev.arquivo;
    if (!caminho) continue;

    const chave = chaveRelativa(caminho);
    const lugar = chave ?? caminho;
    const anterior = porLugar.get(lugar);

    const entrada = anterior ?? {
      lugar,
      chave,
      caminho,
      escritas: 0,
      hashes: [],
      /* Guarda o PRIMEIRO run_id visto e se algum divergiu: o mesmo lugar
         escrito por duas runs seria buraco de contrato, nao dado a esconder. */
      runId: null,
      runsConflitantes: false,
    };

    entrada.caminho = caminho;
    entrada.nome = ev.nome || caminho.split('/').pop();
    /* `tipo` vem do evento e mais nada. Deduzir de extensao seria inventar o
       campo que decide se ha visualizador -- exatamente o contrato que falta. */
    entrada.tipo = ev.tipo || null;
    entrada.subagente = ev.subagente || null;
    entrada.escritas += 1;
    if (ehHash(ev.hash)) entrada.hashes.push(ev.hash);
    if (typeof ev.run_id === 'string' && ev.run_id) {
      if (entrada.runId && entrada.runId !== ev.run_id) entrada.runsConflitantes = true;
      entrada.runId = entrada.runId ?? ev.run_id;
    }
    porLugar.set(lugar, entrada);
  }

  return [...porLugar.values()].reverse().map((e) => {
    const distintos = [...new Set(e.hashes)];
    /* TODAS as escritas precisam declarar hash para a identidade ser conteudo.
       Uma so faltando e o suficiente para nao dar: nao da para afirmar que o
       conteudo nao mudou na escrita que nao se mediu. */
    const completo = e.hashes.length === e.escritas && distintos.length > 0;
    return {
      lugar: e.lugar,
      caminho: e.caminho,
      nome: e.nome,
      tipo: e.tipo,
      subagente: e.subagente,
      runId: e.runId,
      runsConflitantes: e.runsConflitantes,
      escritas: e.escritas,
      /* Quantas vezes o CONTEUDO mudou. `null` quando nao da para saber -- e a
         diferenca entre "nao mudou" e "nao foi medido". */
      versoes: completo ? distintos.length : null,
      hash: completo && distintos.length === 1 ? distintos[0] : null,
      identidade: completo && distintos.length === 1 ? distintos[0] : e.lugar,
      baseDaIdentidade: completo && distintos.length === 1
        ? BASE_HASH
        : (e.chave ? BASE_CHAVE : BASE_CAMINHO),
    };
  });
}

/* O mesmo CONTEUDO em lugares diferentes. Sem hash e indetectavel, e o §4 nomeia
   o problema: "o mesmo conteudo em dois lugares parece duas coisas". Hoje
   devolve vazio porque nao ha hash -- e vazio por ausencia de medida, o que o
   censo declara. */
export function conteudosRepetidos(itens) {
  const porHash = new Map();
  for (const item of itens) {
    if (!item.hash) continue;
    porHash.set(item.hash, [...(porHash.get(item.hash) ?? []), item.lugar]);
  }
  return [...porHash.entries()]
    .filter(([, lugares]) => lugares.length > 1)
    .map(([hash, lugares]) => ({ hash, lugares }));
}

/* O censo que o cabecalho declara e que alimenta o slot de proveniencia.
 *
 * O slot 2 e um MEDIDOR, nao um aviso: ele se apaga sozinho quando a primeira
 * run pos-#24 rodar. Aviso que nao sabe quando parou de ser verdade e a forma
 * de documento que envelhece -- o defeito que esta interface passou o dia
 * removendo. */
export function censoDoCorpus(itens) {
  const lista = Array.isArray(itens) ? itens : [];
  const comProveniencia = lista.filter((i) => i.runId && i.hash).length;
  const tipos = new Set(lista.map((i) => i.tipo).filter(Boolean));
  const semTipo = lista.filter((i) => !i.tipo).length;

  return {
    artefatos: lista.length,
    escritas: lista.reduce((s, i) => s + i.escritas, 0),
    tipos: tipos.size,
    tiposDeclarados: [...tipos].sort(),
    semTipo,
    nomes: new Set(lista.map((i) => i.nome).filter(Boolean)).size,
    comProveniencia,
    semProveniencia: lista.length - comProveniencia,
    /* Reescrito ao menos uma vez. Conta ESCRITA, nao mudanca: e o teto das
       revisoes reais, nao as revisoes. */
    reescritos: lista.filter((i) => i.escritas > 1).length,
    /* Em quantos da para afirmar se o conteudo mudou. Zero enquanto nao houver
       hash, e e esse zero que o slot 2 mostra. */
    comVersaoMedida: lista.filter((i) => i.versoes !== null).length,
    precisaDeclararProveniencia: lista.length > 0 && comProveniencia < lista.length,
  };
}

/* Agrupa por RUN DECLARADA, e o grupo sem run e um grupo, nao 47 excecoes.
 *
 * A alternativa era cada cartao dizer "na run: --". Medido hoje, isso repetiria
 * a mesma frase 40 vezes -- e repeticao treina o olho a pular, que e o oposto de
 * declarar. Alem disso seria dizer errado: a ausencia NAO e propriedade de cada
 * artefato, e propriedade do CORPUS. Os 40 nao tem run pelo mesmo unico motivo
 * (nenhuma run rodou desde a #24), e um fato so nao deve aparecer 40 vezes.
 *
 * A forma tambem nao muda quando o corpus chegar: hoje ha um grupo, o
 * indeclarado; amanha aparecem grupos de run ao lado e o indeclarado encolhe ate
 * sumir. Mesma tela nos dois mundos, sem redesenho -- igual ao slot de
 * proveniencia.
 *
 * NAO le `/dados/runs`. O agrupamento sai do `run_id` do proprio
 * `artefato.atualizou`, entao a forma do resumo de run (issue #29) nao alcanca
 * esta tela. */
export function agruparPorRun(itens) {
  const lista = Array.isArray(itens) ? itens : [];
  const grupos = new Map();
  for (const item of lista) {
    const chave = item.runId ?? null;
    grupos.set(chave, [...(grupos.get(chave) ?? []), item]);
  }
  /* O grupo sem run vai por ULTIMO: o que tem procedencia e o que da para
     investigar, entao vem primeiro. Enquanto for 100% indeclarado, tanto faz --
     e quando deixar de ser, a ordem ja esta certa. */
  return [...grupos.entries()]
    .sort((a, b) => (a[0] === null ? 1 : b[0] === null ? -1 : String(a[0]).localeCompare(String(b[0]))))
    .map(([runId, itens_]) => ({ runId, itens: itens_ }));
}

/* O resumo que a tela declara. Vem inteiro do `/dados/orfaos`, que é quem
   enxerga o disco — a tela não lê diretório e não deve começar a ler. */
export function resumoDeOrfaos(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const artefatos = Number(payload.artefatos_orfaos) || 0;
  const runs = Array.isArray(payload.runs_orfas) ? payload.runs_orfas : [];
  return {
    artefatos,
    runs: runs.length,
    runsIds: runs,
    emDisco: Number(payload.artefatos_em_disco) || 0,
    comEvento: Number(payload.artefatos_com_evento) || 0,
    runsEmDisco: Number(payload.runs_em_disco) || 0,
    ignorados: Number(payload.arquivos_de_ferramenta_ignorados) || 0,
    amostra: Array.isArray(payload.amostra) ? payload.amostra : [],
    amostraTruncada: payload.amostra_truncada === true,
    legadoIlegivel: payload.legado_ilegivel || null,
    /* Só vale ocupar espaço na tela quando há de fato algo que o ledger não
       explica. Zero órfão não merece banner — merece silêncio. */
    precisaDeclarar: artefatos > 0 || runs.length > 0 || Boolean(payload.legado_ilegivel),
  };
}
