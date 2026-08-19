export function formatarCusto(custo, fallback = 'US$ 0.00') {
  return typeof custo === 'number' ? `US$ ${custo.toFixed(2)}` : fallback;
}
