/* Meta-fábrica · API client fino
 * Endpoints do painel.py (:8378) — via proxy Vite em dev, direto em produção.
 */

import { useEffect, useState } from 'react';

const BASE = '/dados';

/* Rota /dados/* que o painel em execucao nao conhece cai no fallback e devolve
   o index.html com status 200 — res.ok passa e o res.json() estoura com erro de
   parse, que nao diz nada. Checar o content-type transforma isso na causa real. */
async function comoJson(res, path) {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const tipo = (res.headers.get('content-type') || '').split(';')[0].trim();
  if (tipo !== 'application/json') {
    throw new Error(
      `${BASE}${path} respondeu ${tipo || 'sem content-type'} em vez de JSON. ` +
      'O painel em execução provavelmente é anterior a esta rota — reinicie com ' +
      'python3 -m motor_painel.painel'
    );
  }
  return res.json();
}

async function get(path) {
  return comoJson(await fetch(`${BASE}${path}`), path);
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return comoJson(res, path);
}

export const fetchRuns = () => get('/runs');
export const getRun = (id) => get(`/runs/${id}`);
export const getAgents = () => get('/agentes');
export const getCosts = () => get('/custos');
export const getGates = () => get('/gates');
export const getCatalogo = () => get('/catalogo');
export const fetchDados = () => get('');
export const postGateDecision = (id, decisao) => post(`/gates/${id}`, { decisao });
export const getMissaoAtiva = () => get('/missoes/ativa');
export const getConexoes = () => get('/conexoes');
export const getInventario = () => get('/inventario');

/* Despacho real do motor — erro devolve a mensagem crua do servidor. */
export async function postMissao(spec, opcoes) {
  const res = await fetch(`${BASE}/missoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec, opcoes }),
  });
  if (!res.ok) {
    const texto = await res.text();
    throw new Error(`HTTP ${res.status}: ${texto}`);
  }
  return res.json();
}

/* Hook de poll a cada 2s para telas vivas */
export function usePoll(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    const tick = () => {
      fetcher()
        .then((d) => { if (active) { setData(d); setError(null); } })
        .catch((e) => { if (active) setError(e.message); });
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => { active = false; clearInterval(id); };
    // eslint-disable-next-line
  }, deps);

  return { data, error };
}
