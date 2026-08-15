import { useEffect, useState } from 'react';
import { usePresenca } from '../ui/usePresenca.js';
import { Fechar } from '../ui/Icones.jsx';

/* Visor de artefato: o conteudo REAL do arquivo que a run produziu.
 *
 * O caminho vem do evento `artefato.atualizou`, mas evento e dado de entrada:
 * quem valida e o servidor de dev, que so serve o que resolve para dentro de
 * motor/runs. Se o arquivo sumiu do disco depois do evento, o visor diz que
 * sumiu — nao cai para um cache nem mostra a ultima versao que viu. O ledger
 * registra que o artefato existiu; so o disco diz se ele ainda existe. */
export function Artefato({ artefato, aoFechar }) {
  const { montado, dentro } = usePresenca(Boolean(artefato));
  const [conteudo, setConteudo] = useState({ fase: 'vazio' });

  useEffect(() => {
    if (!artefato?.caminho) return undefined;
    let vivo = true;
    setConteudo({ fase: 'carregando' });
    fetch(`/ledger/artefato?caminho=${encodeURIComponent(artefato.caminho)}`, {
      cache: 'no-store',
    })
      .then(async (r) => {
        const texto = await r.text();
        if (!vivo) return;
        setConteudo(r.ok ? { fase: 'pronto', texto } : { fase: 'erro', motivo: texto });
      })
      .catch((erro) => vivo && setConteudo({ fase: 'erro', motivo: String(erro?.message ?? erro) }));
    return () => {
      vivo = false;
    };
  }, [artefato?.caminho]);

  if (!montado || !artefato) return null;

  return (
    <aside className="artefato" data-dentro={dentro ? 'sim' : 'nao'}>
      <header className="artefato-topo">
        <b>{artefato.nome}</b>
        <span className="mono">
          {artefato.no} · seq {artefato.seq}
        </span>
        <button type="button" className="btn" aria-label="Fechar artefato" onClick={aoFechar}>
          <Fechar />
        </button>
      </header>

      <pre className="artefato-corpo mono">
        {conteudo.fase === 'carregando' && 'lendo do disco…'}
        {conteudo.fase === 'erro' && `não foi possível ler: ${conteudo.motivo}`}
        {conteudo.fase === 'pronto' && conteudo.texto}
      </pre>

      <footer className="artefato-rodape mono">
        <i />
        {artefato.caminho}
      </footer>
    </aside>
  );
}
