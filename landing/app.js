/* ================= KORTEX — landing v2 =================
   Globo-grafo interativo (canvas 2D, sem dependências) + tema +
   reveals + demos (portão, roteiro, terminal) + contadores.        */

"use strict";

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- tema ---------- */
const root = document.documentElement;
const themeToggle = document.getElementById("themeToggle");
const storedTheme = localStorage.getItem("kortex-theme");
if (storedTheme) root.dataset.theme = storedTheme;
else if (matchMedia("(prefers-color-scheme: light)").matches) root.dataset.theme = "light";

themeToggle.addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("kortex-theme", root.dataset.theme);
  orb.readColors();
});

/* ---------- reveals ---------- */
const revealIO = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); revealIO.unobserve(e.target); }
}, { threshold: 0.15 });
document.querySelectorAll(".reveal").forEach((el) => revealIO.observe(el));

/* ================= globo-grafo do hero =================
   Esfera de fibonacci com relevo (nebulosa), subconjunto "nós de grafo"
   com arestas, rotação lenta e repulsão ao cursor com mola de retorno.  */
const orb = (() => {
  const canvas = document.getElementById("orb");
  const ctx = canvas.getContext("2d");
  const N = 4000;          // partículas da nuvem
  const NODES = 190;       // subconjunto sorteado vira nó de grafo
  const EDGE_ANG = 0.32;   // distância angular máxima para aresta (máx. 2 por nó)
  const pts = [];
  const edges = [];
  let W = 0, H = 0, dpr = 1, cx = 0, cy = 0, R = 0;
  let rotY = 0, lastT = 0, running = true, visible = true;
  let mx = -1e4, my = -1e4;
  let dotRGB = "235,236,240";

  // relevo pseudo-orgânico determinístico sobre a direção (θ, φ)
  const bump = (t, p) =>
    1 + 0.09 * Math.sin(3 * t + 2 * p) + 0.06 * Math.sin(5 * p - 2 * t) + 0.04 * Math.sin(8 * t + 5 * p);
  const hash01 = (i, k) => { const x = Math.sin(i * 127.1 + k * 311.7) * 43758.5453; return x - Math.floor(x); };

  const GA = Math.PI * (3 - Math.sqrt(5)); // ângulo áureo
  const nodeIdx = [];
  for (let i = 0; i < N; i++) {
    const y0 = 1 - (i / (N - 1)) * 2;
    const rr = Math.sqrt(1 - y0 * y0);
    const th = GA * i;
    const dx = Math.cos(th) * rr, dz = Math.sin(th) * rr;
    const t = Math.atan2(rr, y0), p = th % (2 * Math.PI);
    const node = hash01(i, 5) < 0.08 && nodeIdx.length < NODES; // sorteio: evita bandas da espiral
    const halo = !node && hash01(i, 1) < 0.05;
    let f;
    if (node) f = bump(t, p);
    else if (halo) f = 1.04 + hash01(i, 2) * 0.15;
    else f = bump(t, p) * (0.62 + 0.38 * Math.pow(hash01(i, 3), 0.32)); // denso perto da casca
    if (node) nodeIdx.push(pts.length);
    pts.push({
      x: dx * f, y: y0 * f, z: dz * f,
      node, halo, shell: f,
      ox: 0, oy: 0, vx: 0, vy: 0,   // deslocamento em tela (empurrão do mouse)
      sx: 0, sy: 0, depth: 0,
    });
  }
  for (let a = 0; a < nodeIdx.length; a++) {
    let links = 0;
    for (let b = a + 1; b < nodeIdx.length && links < 2; b++) {
      const A = pts[nodeIdx[a]], B = pts[nodeIdx[b]];
      const dot = (A.x * B.x + A.y * B.y + A.z * B.z) /
        (Math.hypot(A.x, A.y, A.z) * Math.hypot(B.x, B.y, B.z));
      if (Math.acos(Math.min(1, Math.max(-1, dot))) < EDGE_ANG) { edges.push([nodeIdx[a], nodeIdx[b]]); links++; }
    }
  }

  function readColors() {
    const cs = getComputedStyle(root);
    dotRGB = cs.getPropertyValue("--orb-dot").trim() || dotRGB;
    if (reduceMotion) frame(0, true); // re-render estático na troca de tema
  }

  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const narrow = W < 760;
    cx = narrow ? W * 0.5 : W * 0.70;
    cy = narrow ? H * 0.30 : H * 0.46;
    R = Math.min(W, H) * (narrow ? 0.30 : 0.34);
    if (reduceMotion) frame(0, true);
  }

  function frame(t, force) {
    if (!force) {
      if (!running || !visible) return;
      requestAnimationFrame(frame);
    }
    const dt = Math.min(t - lastT, 50) || 16;
    lastT = t;
    rotY += dt * 0.00011;
    const sinY = Math.sin(rotY), cosY = Math.cos(rotY);
    const tiltX = 0.35, sinX = Math.sin(tiltX), cosX = Math.cos(tiltX);
    const F = 5; // perspectiva

    ctx.clearRect(0, 0, W, H);

    // glow de volume atrás da esfera
    const g = ctx.createRadialGradient(cx - R * 0.25, cy - R * 0.2, R * 0.1, cx, cy, R * 1.35);
    g.addColorStop(0, `rgba(${dotRGB},0.07)`);
    g.addColorStop(0.6, `rgba(${dotRGB},0.03)`);
    g.addColorStop(1, `rgba(${dotRGB},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(cx - R * 1.5, cy - R * 1.5, R * 3, R * 3);

    for (const p of pts) {
      // rotação Y depois inclinação X
      let x = p.x * cosY + p.z * sinY;
      let z = -p.x * sinY + p.z * cosY;
      let y = p.y * cosX - z * sinX;
      z = p.y * sinX + z * cosX;

      const s = F / (F + z);
      let sx = cx + x * R * s, sy = cy + y * R * s;

      // empurrão do cursor + mola de retorno
      const dxm = sx + p.ox - mx, dym = sy + p.oy - my;
      const d2 = dxm * dxm + dym * dym;
      if (d2 < 19600) { // 140px
        const d = Math.sqrt(d2) || 1;
        const push = (1 - d / 140) * 2.6;
        p.vx += (dxm / d) * push;
        p.vy += (dym / d) * push;
      }
      p.vx = (p.vx - p.ox * 0.055) * 0.86;
      p.vy = (p.vy - p.oy * 0.055) * 0.86;
      p.ox += p.vx; p.oy += p.vy;

      p.sx = sx + p.ox; p.sy = sy + p.oy; p.depth = s;

      const surf = Math.min(1, Math.max(0, (p.shell - 0.6) / 0.4)); // 0 núcleo → 1 casca
      const b = 0.18 + (s - 0.81) * 1.4;                            // frente mais viva
      const a = p.halo ? 0.12 : (0.16 + 0.6 * surf) * b;
      if (p.node) {
        ctx.fillStyle = `rgba(${dotRGB},${Math.min(0.95, a + 0.3)})`;
        const r2 = 0.9 + s * 0.9;
        ctx.fillRect(p.sx - r2 / 2, p.sy - r2 / 2, r2, r2);
      } else {
        ctx.fillStyle = `rgba(${dotRGB},${Math.min(0.75, a)})`;
        const r1 = p.halo ? 1 : 0.7 + s * 0.7;
        ctx.fillRect(p.sx, p.sy, r1, r1);
      }
    }

    ctx.lineWidth = 0.5;
    for (const [i, j] of edges) {
      const a = pts[i], b = pts[j];
      const al = Math.min(0.14, 0.03 + (Math.min(a.depth, b.depth) - 0.9) * 0.35);
      if (al <= 0.02) continue;
      ctx.strokeStyle = `rgba(${dotRGB},${al})`;
      ctx.beginPath(); ctx.moveTo(a.sx, a.sy); ctx.lineTo(b.sx, b.sy); ctx.stroke();
    }
  }

  addEventListener("resize", resize);
  addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    mx = e.clientX - r.left; my = e.clientY - r.top;
  });
  addEventListener("pointerleave", () => { mx = my = -1e4; });

  new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && running && !reduceMotion) { lastT = performance.now(); requestAnimationFrame(frame); }
  }).observe(canvas);
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running && visible && !reduceMotion) { lastT = performance.now(); requestAnimationFrame(frame); }
  });

  resize(); readColors();
  if (!reduceMotion) requestAnimationFrame(frame); else frame(0, true);
  return { readColors };
})();

/* ================= demo: portão de evidência ================= */
(() => {
  if (reduceMotion) return;
  const wall = document.getElementById("gateWall");
  const log = document.getElementById("gateLog");
  const pulse = document.querySelector(".gate-pulse");
  const pulseOut = document.querySelector(".gate-pulse-out");
  const track = document.querySelector(".gate-track");
  const run = (el, ms) => el.animate(
    [{ left: "0%", opacity: 1 }, { left: "100%", opacity: 1 }],
    { duration: ms, easing: "ease-in-out", fill: "forwards" });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  (async function loop() {
    for (;;) {
      wall.className = "gate-wall mono"; pulseOut.style.opacity = 0;
      log.textContent = "spec.recebida · executor.chamado (barato primeiro)";
      run(pulse, 1100); await sleep(1200);
      wall.classList.add("deny");
      log.textContent = "portao.reprovado — evidência insuficiente · executor.escalado";
      await sleep(1600);
      wall.classList.remove("deny");
      log.textContent = "executor.respondeu · portao.avaliando…";
      run(pulse, 1100); await sleep(1200);
      wall.classList.add("pass"); pulseOut.style.opacity = 1;
      run(pulseOut, 900);
      log.textContent = "portao.aprovado ✓ · tarefa.concluida · custo no livro-razão";
      await sleep(2600);
    }
  })();
})();

/* ================= demo: roteiro-como-texto ================= */
(() => {
  const code = document.querySelector("#roteiroDemo code");
  const SRC = `roteiro: lancamento-feature
etapas:
  - especificar   @arquiteto
  - implementar   @construtor   modelo: barato→capaz
  - atacar        @revisor      # adversarial
portao:
  exige: [testes, lint, sast, build]
  reprova: escala e re-executa`;
  if (reduceMotion) { code.textContent = SRC; return; }
  let i = 0, dir = 1;
  const tick = () => {
    i += dir;
    code.textContent = SRC.slice(0, i);
    if (i >= SRC.length) { setTimeout(() => { dir = 1; i = 0; setTimeout(tick, 400); }, 6000); return; }
    setTimeout(tick, SRC[i - 1] === "\n" ? 90 : 16);
  };
  new IntersectionObserver(([e], io) => { if (e.isIntersecting) { io.disconnect(); tick(); } })
    .observe(code.parentElement);
})();

/* ================= replay do terminal ================= */
(() => {
  const body = document.getElementById("terminalBody");
  const SCRIPT = [
    ["00:00.4", "spec.recebida", "ev", "roteiro lancamento-feature v3", ""],
    ["00:01.1", "executor.chamado", "ev", "construtor · modelo barato", "$0.0007"],
    ["00:14.9", "artefato.atualizou", "ev", "3 arquivos · 142 linhas", ""],
    ["00:15.2", "portao.avaliando", "warn", "testes + lint + sast", ""],
    ["00:19.8", "portao.reprovado", "err", "2 testes falharam", ""],
    ["00:20.1", "executor.escalado", "warn", "barato → capaz", ""],
    ["00:58.7", "executor.respondeu", "ev", "diff mínimo · 38 linhas", "$0.0121"],
    ["01:03.3", "portao.aprovado", "ok", "333/333 verdes", ""],
    ["01:03.6", "tarefa.concluida", "ok", "custo total R$ 0,09", ""],
  ];
  let i = 0, timer = null, playing = false;
  const push = () => {
    const [t, ev, cls, note, cost] = SCRIPT[i];
    const line = document.createElement("div");
    line.className = "tl";
    line.innerHTML =
      `<span class="t">${t}</span><span class="${cls}">${ev}</span>` +
      `<span class="ev">${note}</span>` + (cost ? `<span class="cost">${cost}</span>` : "");
    body.appendChild(line);
    while (body.children.length > 11) body.firstChild.remove();
    i++;
    if (i >= SCRIPT.length) { i = 0; timer = setTimeout(() => { body.replaceChildren(); push(); }, 5200); }
    else timer = setTimeout(push, 420 + Math.random() * 720);
  };
  if (reduceMotion) { i = 0; SCRIPT.forEach((_, k) => { i = k; push.call(null); clearTimeout(timer); }); return; }
  new IntersectionObserver(([e]) => {
    if (e.isIntersecting && !playing) { playing = true; push(); }
    else if (!e.isIntersecting && playing) { playing = false; clearTimeout(timer); }
  }, { threshold: 0.2 }).observe(body);
})();

/* ================= contadores ================= */
(() => {
  const els = document.querySelectorAll(".stat-n[data-count]");
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      io.unobserve(e.target);
      const target = +e.target.dataset.count, suffix = e.target.dataset.suffix || "";
      if (reduceMotion) { e.target.textContent = target + suffix; continue; }
      const t0 = performance.now(), D = 1300;
      (function step(t) {
        const k = Math.min((t - t0) / D, 1), eased = 1 - Math.pow(1 - k, 3);
        e.target.textContent = Math.round(target * eased) + suffix;
        if (k < 1) requestAnimationFrame(step);
      })(t0);
    }
  }, { threshold: 0.4 });
  els.forEach((el) => io.observe(el));
})();

/* ================= waitlist (Formspree) ================= */
(() => {
  const form = document.getElementById("waitlist");
  const msg = document.getElementById("waitlistMsg");
  const btn = form.querySelector("button");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = form.email.value.trim();
    msg.style.color = "";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      msg.textContent = "e-mail inválido — confere aí.";
      msg.style.color = "#E05B4E";
      return;
    }
    btn.disabled = true;
    msg.textContent = "enviando…";
    try {
      const r = await fetch("https://formspree.io/f/xykrgqjg", {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!r.ok) throw new Error(r.status);
      form.reset();
      msg.textContent = "✓ você está na lista — bem-vindo ao build in public.";
    } catch {
      msg.textContent = "falhou ao enviar — tenta de novo em instantes.";
      msg.style.color = "#E05B4E";
    } finally {
      btn.disabled = false;
    }
  });
})();
