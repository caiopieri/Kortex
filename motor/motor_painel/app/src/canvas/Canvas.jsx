import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Minimapa } from './superficie/Minimapa.jsx';
import { Superficie } from './superficie/Superficie.jsx';
import { useViewport } from './superficie/useViewport.js';
import { VistaAndares } from './andares/VistaAndares.jsx';
import { PainelProjeto } from './projetos/PainelProjeto.jsx';
import { PainelNotificacoes } from './notificacoes/PainelNotificacoes.jsx';
import { derivarNotificacoes } from './notificacoes/derivar.js';
import { Artefato } from './ledger/Artefato.jsx';
import { Grafo } from './ledger/Grafo.jsx';
import { LARGURA_NO, limitesDoGrafo, posicionarNos } from './ledger/layout.js';
import { SeloLeitura } from './ledger/SeloLeitura.jsx';
import { useLedger } from './ledger/useLedger.js';
import { adaptadorPainel } from './ledger/ler.js';
import { Aparencia, BarraFerramentas, ControlesCanto, Identidade } from './ui/Cromo.jsx';
import { aplicarPele, peleAtual, PELES } from './tema.js';
import './canvas.css';

/* Os quatro andares sao as casas/harness de `DECISAO-canvas-e-operacao.md` §4,
   nao numeracao de predio. */
const ANDARES_INICIAIS = [
  { id: 'software', nome: 'Software', objetos: [] },
  { id: 'hardware', nome: 'Hardware', objetos: [] },
  { id: 'mecanica', nome: 'Mecânica', objetos: [] },
  { id: 'treinamento', nome: 'Treinamento', objetos: [] },
];

/* Lista fixa no codigo, e o painel declara isso. Nao ha cadastro de projeto em
   lugar nenhum do Kortex. */
const PROJETOS = [
  { id: 'via-catholica', nome: 'Via Catholica' },
  { id: 'consertgo', nome: 'Consertgo' },
  { id: 'flint', nome: 'Flint' },
  { id: 'eletrofy', nome: 'Eletrofy' },
];

const SEM_RUNS = [];
const SEM_AVISOS = [];

let sequencia = 0;

/* `modo` vem do painel: quem manda no claro/escuro aqui e a Topbar, nao o
   canvas. A PELE (linguagem visual) continua sendo escolha local enquanto o
   fundador compara as duas. */
export default function Canvas({ modo = 'escuro', adaptador = adaptadorPainel }) {
  const { vp, deslocar, ampliarEm, ampliarSuave, escalaSuave, centralizarEm } = useViewport();
  const [andares, setAndares] = useState(ANDARES_INICIAIS);
  const [ativoId, setAtivoId] = useState('software');
  const [projetoId, setProjetoId] = useState(PROJETOS[0].id);
  const [vendoProjeto, setVendoProjeto] = useState(false);
  const [vendoAndares, setVendoAndares] = useState(false);
  const [vendoAvisos, setVendoAvisos] = useState(false);
  const [ferramenta, setFerramenta] = useState('selecionar');
  const [menuAberto, setMenuAberto] = useState(false);
  const [vendoMapa, setVendoMapa] = useState(false);
  const [pele, setPele] = useState(peleAtual);

  const ledger = useLedger(adaptador);
  const [runAtivaId, setRunAtivaId] = useState(null);
  const [artefato, setArtefato] = useState(null);
  const [dispensados, setDispensados] = useState(() => new Set());

  /* Alvo de uma notificacao. ESTADO, nao ref, e o efeito de enquadre NAO o
     consome — le e decide. Com ref, o StrictMode (que invoca o efeito duas
     vezes em dev) fazia a primeira passada centralizar no no e a segunda, ja
     com o ref limpo, reenquadrar o grafo inteiro por cima. O alvo ficava
     visivelmente fora de centro. Efeito idempotente resolve na raiz. */
  const [foco, setFoco] = useState(null);

  const runs = ledger.runs ?? SEM_RUNS;
  const runAtiva = useMemo(
    () => (runAtivaId ? runs.find((r) => r.id === runAtivaId) : runs[runs.length - 1]) ?? null,
    [runs, runAtivaId],
  );

  const avisos = useMemo(
    () => (ledger.fase === 'pronto' ? derivarNotificacoes(runs, ledger.leitura) : SEM_AVISOS),
    [runs, ledger.leitura, ledger.fase],
  );
  const visiveis = useMemo(
    () => avisos.filter((a) => !dispensados.has(a.id)),
    [avisos, dispensados],
  );

  /* O canvas NAO ocupa a janela quando mora dentro do painel: ocupa o `<main>`.
     Medir `window.innerWidth` aqui poria o minimapa e o enquadramento errados
     por toda a largura da sidebar. */
  const raiz = useRef(null);
  const [tela, setTela] = useState({ largura: 0, altura: 0 });

  useEffect(() => {
    const el = raiz.current;
    if (!el) return undefined;
    const observador = new ResizeObserver(([entrada]) => {
      const { width, height } = entrada.contentRect;
      setTela({ largura: width, altura: height });
    });
    observador.observe(el);
    return () => observador.disconnect();
  }, []);

  const centro = useCallback(() => [tela.largura / 2, tela.altura / 2], [tela]);

  /* Enquadra ao TROCAR de run, ou no no que a notificacao apontou. Nao a cada
     leitura: reler o ledger nao pode arrancar a vista de onde o operador a
     deixou. */
  useEffect(() => {
    if (!runAtiva || tela.largura === 0) return;

    if (foco?.runId === runAtiva.id && foco.no) {
      const lugar = posicionarNos(runAtiva).get(foco.no);
      if (lugar) {
        /* Centro REAL do cartao: a altura varia com artefato e falha, entao
           meia-altura fixa erraria justo nos nos que mais interessam, que sao
           os mais carregados. */
        centralizarEm(
          lugar.x + LARGURA_NO / 2,
          lugar.y + lugar.altura / 2,
          tela.largura,
          tela.altura,
        );
        return;
      }
    }

    const limites = limitesDoGrafo(runAtiva);
    if (limites) centralizarEm(limites.cx, limites.cy, tela.largura, tela.altura);
    /* `tela` so entra pelo zero inicial: redimensionar nao deve reenquadrar. */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runAtiva?.id, foco, centralizarEm, tela.largura === 0]);

  /* Levar ate o lugar que notificou. Sem destino o botao nem chega aqui — fica
     desabilitado no painel, em vez de virar link morto. */
  const irPara = (aviso) => {
    if (!aviso.destino) return;
    setAtivoId('software');
    setVendoAndares(false);
    setRunAtivaId(aviso.destino.runId);

    if (aviso.destino.no) {
      setFoco(aviso.destino);
      return;
    }

    /* Sem no: o destino e a estacao de pre-voo, que fica num ponto fixo do
       mundo. Enquadrar o grafo inteiro deixaria a estacao na beirada. */
    setFoco(null);
    if (aviso.destino.runId === runAtiva?.id) {
      const l = limitesDoGrafo(runAtiva);
      if (l) centralizarEm(l.x1 + 150, l.y1 + 70, tela.largura, tela.altura);
    }
  };

  const trocarPele = (nova) => {
    aplicarPele(nova);
    setPele(nova);
  };

  const criarAndar = () => {
    sequencia += 1;
    const novo = { id: `andar-${sequencia}`, nome: `Andar ${andares.length}`, objetos: [] };
    setAndares((lista) => [...lista, novo]);
    setAtivoId(novo.id);
  };

  /* O ultimo andar nao sai: canvas sem andar nenhum nao tem onde desenhar. */
  const removerAndar = (id) => {
    if (andares.length <= 1) return;
    const restante = andares.filter((a) => a.id !== id);
    setAndares(restante);
    if (ativoId === id) setAtivoId(restante[restante.length - 1].id);
  };

  const escolherAndar = (id) => {
    setAtivoId(id);
    setVendoAndares(false);
  };

  const andarAtivo = andares.find((a) => a.id === ativoId) ?? andares[0];
  const projetoAtivo = PROJETOS.find((p) => p.id === projetoId) ?? PROJETOS[0];

  return (
    <div
      className="kxc"
      ref={raiz}
      data-theme={modo === 'claro' ? 'light' : 'dark'}
      data-pele={pele}
    >
      <div className="app">
        <Superficie vp={vp} deslocar={deslocar} ampliarEm={ampliarEm}>
          {andarAtivo.id === 'software' && (
            <Grafo run={runAtiva} artefatoAberto={artefato} aoAbrirArtefato={setArtefato} />
          )}
        </Superficie>

        <VistaAndares
          aberto={vendoAndares}
          andares={andares}
          ativoId={ativoId}
          aoEscolher={escolherAndar}
        />

        <Identidade menuAberto={menuAberto} aoAlternarMenu={() => setMenuAberto((v) => !v)} />
        <BarraFerramentas ferramenta={ferramenta} aoTrocar={setFerramenta} />
        <Aparencia pele={pele} peles={PELES} aoTrocarPele={trocarPele} />

        <Artefato artefato={artefato} aoFechar={() => setArtefato(null)} />

        {!vendoAndares &&
          (andarAtivo.id === 'software' ? (
            <SeloLeitura estado={ledger} run={runAtiva} aoRecarregar={ledger.recarregar} />
          ) : (
            <div className="selo-vazio mono">
              <i />
              {projetoAtivo.nome} · {andarAtivo.nome} · sem ledger para este andar
            </div>
          ))}

        <ControlesCanto
          andares={andares}
          ativoId={ativoId}
          aoEscolherAndar={escolherAndar}
          aoCriarAndar={criarAndar}
          aoRemoverAndar={removerAndar}
          vendoAndares={vendoAndares}
          aoAlternarAndares={() => setVendoAndares((v) => !v)}
          vendoMapa={vendoMapa}
          aoAlternarMapa={() => setVendoMapa((v) => !v)}
          projetoNome={projetoAtivo.nome}
          vendoProjeto={vendoProjeto}
          aoAlternarProjeto={() => setVendoProjeto((v) => !v)}
          vendoAvisos={vendoAvisos}
          aoAlternarAvisos={() => setVendoAvisos((v) => !v)}
          totalAvisos={visiveis.length}
          painelAvisos={
            <PainelNotificacoes
              aberto={vendoAvisos}
              avisos={visiveis}
              aoIr={irPara}
              aoLimpar={() => setDispensados(new Set(avisos.map((a) => a.id)))}
              aoDispensar={(id) => setDispensados((s) => new Set(s).add(id))}
            />
          }
          painelProjeto={
            <PainelProjeto
              aberto={vendoProjeto}
              andares={andares}
              andarAtivoId={ativoId}
              aoEscolherAndar={escolherAndar}
              projetos={PROJETOS}
              projetoAtivoId={projetoId}
              aoEscolherProjeto={setProjetoId}
              runs={runs}
              runAtivaId={runAtiva?.id ?? null}
              /* Escolher run na mao apaga o foco: senao a run nova herdaria o
                 no da notificacao anterior e a vista pularia para um lugar que
                 o operador nao pediu. */
              aoEscolherRun={(id) => {
                setFoco(null);
                setRunAtivaId(id);
              }}
            />
          }
          minimapa={
            <Minimapa
              aberto={vendoMapa && !vendoAndares}
              vp={vp}
              tela={tela}
              objetos={andarAtivo.objetos}
              aoNavegar={(mx, my) => centralizarEm(mx, my, tela.largura, tela.altura)}
            />
          }
          escala={vp.escala}
          aoAmpliar={() => ampliarSuave(1.25, ...centro())}
          aoReduzir={() => ampliarSuave(1 / 1.25, ...centro())}
          aoReiniciarZoom={() => escalaSuave(1, ...centro())}
        />
      </div>
    </div>
  );
}
