import { useEffect, useRef, useState } from 'react';
import { ondasDaRun, PROFUNDIDADE_ONDA, profundidadeDaOnda, projetar3d } from './layout3d.js';

/* O grafo da run em 3D. UM RENDERIZADOR, NAO UMA TELA.
 *
 * Este arquivo NAO le o ledger, NAO recebe `eventos` e NAO deriva estado. Ele
 * recebe a run que `projetarRun` ja produziu e a posiciona com `projetar3d`.
 * A versao anterior (a pagina `/grafo3d`, removida no corte 1/7) tinha um
 * `switch` proprio sobre os eventos para colorir no -- uma SEGUNDA projecao de
 * estado, mais fraca que a do `projetar.js` porque nao conhecia a classificacao
 * do andon. Uma falha terminal-ambigua saia como no vermelho comum aqui e como
 * estacao de pre-voo no 2D: a mesma run, duas leituras. Aquele switch nao foi
 * portado, foi apagado.
 *
 * SEM CDN. A versao anterior buscava `three` e `3d-force-graph` no unpkg.com em
 * tempo de execucao -- as unicas dependencias do painel fora do package.json.
 * O painel roda na LAN, num runner que existe para funcionar sozinho: uma tela
 * que precisa de internet publica para abrir e defeito, nao empacotamento.
 * Agora os dois sao `import()` dinamico de pacote instalado: chunk sob demanda,
 * servido pelo proprio painel, e o bundle base nao cresce.
 */

/* O motor 3D e pesado e nao pode entrar no caminho critico do painel. Uma
   promessa unica no modulo garante que trocar de aba e voltar nao rebaixe o
   chunk nem reinstancie a biblioteca. */
let motor = null;
function carregarMotor() {
  if (!motor) {
    motor = Promise.all([import('3d-force-graph'), import('three')]).then(
      ([fg, three]) => ({ ForceGraph3D: fg.default, THREE: three }),
    );
  }
  return motor;
}

const lerCor = (raiz, token, alternativa) =>
  getComputedStyle(raiz).getPropertyValue(token).trim() || alternativa;

/* As TRES formas de `no.estado` que `projetarRun` produz, e nada alem delas.
   Uma quarta cor aqui seria afirmacao que a projecao nao faz. */
function corDoEstado(cores, no) {
  if (no.tipo === 'nucleo') return cores.accent;
  if (no.estado === 'falhou') return cores.alerta;
  if (no.estado === 'aprovado') return cores.verde;
  return cores.neutro;
}

/* Raio cresce com o que o no PRODUZIU (artefatos declarados por evento), nao
   com grau. Grau e propriedade do desenho; artefato e do trabalho.

   A escala e relativa a `PROFUNDIDADE_ONDA` (240): no muito menor que o passo
   entre ondas some, e a tela vira poeira em vez de grafo. */
const raioDoNo = (no) => 16 + Math.min(6, no.artefatos) * 3;

/* Rotulo como sprite de textura. Sem ele o operador ve esferas e nao sabe qual
   e qual -- e uma vista 3D que exige passar o mouse em cada no para se orientar
   e uma vista que ninguem abre duas vezes. */
function rotulo(THREE, texto, cor) {
  const escala = 3;
  const fonte = 34;
  const tela = document.createElement('canvas');
  const ctx = tela.getContext('2d');
  ctx.font = `600 ${fonte}px 'IBM Plex Mono', ui-monospace, monospace`;
  tela.width = Math.ceil(ctx.measureText(texto).width) + 12;
  tela.height = Math.ceil(fonte * 1.4);
  /* Medir zera o contexto: a fonte precisa ser reposta depois do resize. */
  const c2 = tela.getContext('2d');
  c2.font = `600 ${fonte}px 'IBM Plex Mono', ui-monospace, monospace`;
  c2.fillStyle = cor;
  c2.textBaseline = 'middle';
  c2.fillText(texto, 6, tela.height / 2);

  const textura = new THREE.CanvasTexture(tela);
  textura.needsUpdate = true;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: textura, transparent: true, depthWrite: false }),
  );
  sprite.scale.set((tela.width / fonte) * escala * 2, escala * 2.8, 1);
  return sprite;
}

/* Enquadramento proprio, em vez de `zoomToFit`.
 *
 * `zoomToFit` mede a cena inteira, e os sprites de rotulo sao muito mais largos
 * que as esferas: um no chamado `verifier:transformador-csv-json` inflava a
 * caixa a ponto de o grafo abrir minusculo no meio da tela. Aqui a caixa e a
 * dos NOS -- que e o que o operador precisa ver -- e o rotulo pode transbordar,
 * porque rotulo cortado na borda incomoda menos que grafo ilegivel no centro.
 *
 * A DIRECAO E OBLIQUA e isso nao e estetica: a camera padrao olha ao longo de
 * -Z, que e exatamente o eixo da onda. De frente, as ondas se sobrepoem na tela
 * e a profundidade -- a unica coisa que este renderizador da e o 2D nao -- fica
 * invisivel. De frente, o 3D e um 2D pior. */
const DIRECAO = { x: 0.62, y: 0.34, z: 0.71 };

function enquadrar(g) {
  const { nodes } = g.graphData();
  if (!nodes.length) return;

  let cx = 0;
  let cy = 0;
  let cz = 0;
  for (const n of nodes) {
    cx += n.x ?? 0;
    cy += n.y ?? 0;
    cz += n.z ?? n.fz ?? 0;
  }
  cx /= nodes.length;
  cy /= nodes.length;
  cz /= nodes.length;

  let raio = 0;
  for (const n of nodes) {
    raio = Math.max(
      raio,
      Math.hypot((n.x ?? 0) - cx, (n.y ?? 0) - cy, (n.z ?? n.fz ?? 0) - cz),
    );
  }
  /* Run de um no so tem raio zero: sem piso, a camera cairia dentro dele. */
  raio = Math.max(raio, 120);

  const fov = (g.camera().fov * Math.PI) / 180;
  const distancia = (raio / Math.tan(fov / 2)) * 1.35;

  g.cameraPosition(
    {
      x: cx + DIRECAO.x * distancia,
      y: cy + DIRECAO.y * distancia,
      z: cz + DIRECAO.z * distancia,
    },
    { x: cx, y: cy, z: cz },
    600,
  );
}

export function Grafo3D({ run, modo }) {
  const palco = useRef(null);
  const grafo = useRef(null);
  const enquadrado = useRef(null);
  const [erro, setErro] = useState(null);
  const [pronto, setPronto] = useState(false);

  useEffect(() => {
    let vivo = true;
    let instancia = null;

    carregarMotor().then(
      ({ ForceGraph3D, THREE }) => {
        if (!vivo || !palco.current) return;
        instancia = ForceGraph3D()(palco.current)
          .backgroundColor('rgba(0,0,0,0)')
          .showNavInfo(false)
          .enableNodeDrag(false);
        /* Travar o pixel ratio e desligar sombra: o painel roda em maquina
           modesta e a cena nao precisa de nenhum dos dois. */
        instancia.renderer().setPixelRatio(1);
        instancia.renderer().shadowMap.enabled = false;
        instancia.__THREE = THREE;
        grafo.current = instancia;
        setPronto(true);
      },
      (e) => {
        if (vivo) setErro(String(e?.message ?? e));
      },
    );

    return () => {
      vivo = false;
      /* `_destructor` solta o contexto WebGL. Sem ele, entrar e sair do modo 3D
         algumas vezes esgota os contextos que o navegador concede e a tela
         passa a abrir preta sem erro nenhum. */
      instancia?._destructor?.();
      grafo.current = null;
    };
  }, []);

  /* Redimensiona junto com o contenedor: o canvas do three nao e responsivo
     sozinho e ficaria com a largura do primeiro quadro para sempre. */
  useEffect(() => {
    if (!pronto || !palco.current) return undefined;
    const alvo = palco.current;
    const medir = () => {
      const g = grafo.current;
      if (g) g.width(alvo.clientWidth).height(alvo.clientHeight);
    };
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(alvo);
    return () => observador.disconnect();
  }, [pronto]);

  useEffect(() => {
    const g = grafo.current;
    if (!pronto || !g || !run) return;
    const THREE = g.__THREE;
    const raiz = palco.current.closest('.kxc') ?? document.documentElement;

    const cores = {
      accent: lerCor(raiz, '--accent', '#f2f1ed'),
      alerta: lerCor(raiz, '--alerta', '#e0553d'),
      verde: lerCor(raiz, '--green', '#3dc97e'),
      neutro: lerCor(raiz, '--text-faint', '#6c7077'),
      texto: lerCor(raiz, '--text-soft', '#a7aab2'),
      linha: lerCor(raiz, '--line-strong', 'rgba(235,236,240,0.18)'),
    };

    const { nodes, links } = projetar3d(run);

    g.nodeThreeObject((no) => {
      const grupo = new THREE.Group();
      const cor = corDoEstado(cores, no);
      grupo.add(
        new THREE.Mesh(
          new THREE.SphereGeometry(raioDoNo(no), 16, 12),
          new THREE.MeshBasicMaterial({ color: cor }),
        ),
      );
      /* Falha ganha ANEL, nao cor propria. O 2D tambem nao pinta o no que
         falhou: ele engrossa a borda e deixa a cor semantica para o item de
         falha, porque a borda chama atencao sem afirmar causa. Repetir aqui
         mantem as duas superficies dizendo a mesma coisa. */
      if (no.falhas > 0) {
        const anel = new THREE.Mesh(
          new THREE.TorusGeometry(raioDoNo(no) + 6, 1.6, 8, 32),
          new THREE.MeshBasicMaterial({ color: cores.alerta }),
        );
        grupo.add(anel);
      }
      const etiqueta = rotulo(THREE, no.id, cores.texto);
      etiqueta.position.set(0, raioDoNo(no) + 16, 0);
      grupo.add(etiqueta);
      return grupo;
    });

    g.nodeLabel((no) => {
      const partes = [no.id, no.papel ?? 'sem papel', `onda ${no.onda}`];
      if (no.artefatos) partes.push(`${no.artefatos} artefato${no.artefatos > 1 ? 's' : ''}`);
      if (no.falhas) partes.push(`${no.falhas} falha${no.falhas > 1 ? 's' : ''}`);
      return partes.join(' · ');
    });
    g.linkColor(() => cores.linha).linkWidth(0.6).linkOpacity(0.45);

    g.graphData({ nodes, links });
    /* `numDimensions(3)` com `fz` fixado por no: a simulacao move X e Y e nunca
       o Z. E aqui que a onda declarada deixa de ser numero e vira lugar. */
    g.numDimensions(3);
    /* A carga precisa ser fraca o bastante para a fisica nao tentar vencer o
       eixo fixo empurrando tudo para as bordas do plano. */
    g.d3Force('charge')?.strength(-90);
    g.d3Force('link')?.distance(70);

    /* O padrao do `3d-force-graph` e esfriar por 15 segundos. Um grafo de run
       tem dezenas de nos, nao milhares: 15s de quadro mal enquadrado antes do
       primeiro enquadramento e tempo de espera que o operador nao tem por que
       pagar. */
    g.cooldownTime(2500);

    /* ENQUADRAR SO DEPOIS QUE A FISICA PARA, e uma vez por run.
       `zoomToFit` logo apos `graphData` mede um grafo que ainda esta se
       abrindo e trava a camera num quadro que nao serve para o resultado. */
    enquadrado.current = null;
    g.onEngineStop(() => {
      if (enquadrado.current === run.id) return;
      enquadrado.current = run.id;
      /* A CAMERA PRECISA SER OBLIQUA.
         O padrao do `3d-force-graph` olha ao longo de -Z -- que e exatamente o
         eixo da onda. De frente, as ondas se sobrepoem na tela e a
         profundidade, unica coisa que este renderizador da e o 2D nao, fica
         invisivel: vira um 2D pior. O angulo nao e enfeite, e o que torna o
         eixo legivel. */
      enquadrar(g);
    });
  }, [pronto, run, modo]);

  const ondas = ondasDaRun(run);

  if (erro) {
    return (
      <div className="kx3d-aviso mono">
        <b>Motor 3D não carregou</b>
        <span>{erro}</span>
        <span>
          O 2D desenha o mesmo grafo desta run — a diferença é só o renderizador.
        </span>
      </div>
    );
  }

  return (
    <div className="kx3d">
      <div className="kx3d-palco" ref={palco} />
      {!pronto && <div className="kx3d-aviso mono">carregando motor 3D…</div>}

      {/* A regua. Sem ela o operador ve nos flutuando e nao ve que a
          profundidade SIGNIFICA alguma coisa — que e a unica razao deste
          renderizador existir depois do 2D. */}
      {pronto && ondas.length > 0 && (
        <div className="kx3d-regua mono">
          <b>profundidade = onda declarada</b>
          <span>
            {ondas.length} onda{ondas.length > 1 ? 's' : ''} ·{' '}
            {ondas.map((o) => `${o}→${profundidadeDaOnda(o)}`).join('  ')}
          </span>
          <span>
            Z vem de <code>onda.iniciada</code>; X e Y são arranjo da física e não
            significam nada — o ledger não emite coordenada. Passo {PROFUNDIDADE_ONDA}.
          </span>
        </div>
      )}
    </div>
  );
}
