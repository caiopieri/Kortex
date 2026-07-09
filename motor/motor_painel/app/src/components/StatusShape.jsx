/* StatusShape · Componente compartilhado de status visual (forma + cor) */

export default function StatusShape({ kind, size }) {
  let className = 'sh';
  
  if (kind === 'ativa' || kind === 'running' || kind === 'executando' || kind === 'blue') {
    className += ' blue';
  } else if (kind === 'concluida' || kind === 'sucesso' || kind === 'green') {
    className += ' green';
  } else if (kind === 'abortada' || kind === 'erro' || kind === 'falha' || kind === 'red') {
    className += ' red';
  } else if (kind === 'aguardando' || kind === 'pendente' || kind === 'amber') {
    className += ' amber';
  } else {
    className += ' idle';
  }

  const style = size ? { width: size, height: size } : {};

  return <span className={className} style={style} />;
}
