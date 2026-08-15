import { usePoll, getConexoes } from '../api.js';

/* tem_credencial tem TRES estados. null nao e "nao" — e "o painel nao sabe
   comprovar este transporte". Colapsar os dois mentiria. */
function credencial(tem) {
  if (tem === true) return { shape: 'sh green', cor: 'var(--green)', texto: 'credencial comprovada' };
  if (tem === false) return { shape: 'sh red', cor: 'var(--red)', texto: 'sem credencial' };
  return { shape: 'sh idle', cor: 'var(--text3)', texto: 'não verificável · transporte desconhecido' };
}

export default function Conexoes() {
  const { data: conexoes, error } = usePoll(getConexoes);

  if (error) return (
    <div>
      <span className="num">Conexões</span>
      <div className="card" style={{ padding: 16, marginTop: 16, borderColor: 'var(--red)' }}>
        <span className="mono" style={{ color: 'var(--red)' }}>Erro: {error}</span>
      </div>
    </div>
  );

  if (!conexoes) return (
    <div>
      <span className="num">Conexões</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <span className="mono" style={{ color: 'var(--text3)' }}>Carregando conexões…</span>
      </div>
    </div>
  );

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className="title" style={{ fontSize: 20 }}>Conexões</span>
        <span className="eyebrow" style={{ borderLeft: '1px solid var(--border)', paddingLeft: 12 }}>
          executores do registry · transporte e credencial
        </span>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="num" style={{ marginBottom: 10 }}>01 — Conexões da fábrica</div>

        {conexoes.length === 0 ? (
          <div className="card" style={{ padding: 20, textAlign: 'center' }}>
            <span className="mono" style={{ color: 'var(--text3)' }}>
              Sem registry. Nenhuma conexão para mostrar.
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {conexoes.map(c => {
              const cred = credencial(c.tem_credencial);
              return (
                <div key={c.id} className="card" style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span className={cred.shape}></span>
                    <span className="title" style={{ fontSize: 14, flex: 1 }}>{c.nome}</span>
                    <span className="mono" style={{ fontSize: 9, color: cred.cor, border: '1px solid', borderRadius: 2, padding: '1px 6px' }}>
                      {cred.texto}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text2)' }}>transporte · {c.tipo}</span>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--text3)' }}>{c.origem}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="card" style={{ padding: '9px 14px', marginTop: 16 }}>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text2)', lineHeight: 1.6 }}>
          O painel só mostra o <b style={{ color: 'var(--text)' }}>fato</b> de haver credencial — nunca a chave.
          Para transporte por CLI a prova é o executável estar no PATH; por chave, a variável de ambiente estar
          definida. Cadastro é pelo registry em disco, não por esta tela.
        </span>
      </div>
    </>
  );
}
