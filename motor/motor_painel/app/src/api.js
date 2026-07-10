/* Meta-fábrica · API client fino
 * Endpoints do painel.py (:8378) — via proxy Vite em dev, direto em produção.
 */

import { useEffect, useState } from 'react';

const BASE = '/dados';

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const fetchRuns = () => get('/runs');
export const getRun = (id) => get(`/runs/${id}`);
export const getAgents = () => get('/agentes');
export const getCosts = () => get('/custos');
export const getGates = () => get('/gates');
export const getCatalogo = () => get('/catalogo');
export const postGateDecision = (id, decisao) => post(`/gates/${id}`, { decisao });

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
