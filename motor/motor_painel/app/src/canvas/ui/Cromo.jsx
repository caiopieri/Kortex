import {
  Caixa,
  Camadas,
  Cursor,
  Fechar,
  Lua,
  Mais,
  Mapa,
  Marca,
  MarcaNome,
  Menos,
  Painel,
  Sino,
  Sol,
} from './Icones.jsx';
import { Menu } from './Menu.jsx';
import { usePresenca } from './usePresenca.js';

/* O cromo flutuante: marca, ferramenta, andares, zoom, tema.
 *
 * Regra do `002-painel-operacional` aplicada literalmente: controle ou faz a
 * acao documentada ou nao existe. Por isso a barra de ferramentas tem UM botao
 * — terminal, nota, anexo, pasta, globo e texto entram quando a acao existir,
 * nao antes. Botao decorativo mente sobre o que o sistema faz.
 */

export function Identidade({ menuAberto, aoAlternarMenu }) {
  return (
    <div className="canto canto-se">
      <div className="capsula">
        <button
          type="button"
          className="btn"
          aria-pressed={menuAberto}
          aria-expanded={menuAberto}
          aria-label={menuAberto ? 'Fechar menu' : 'Abrir menu'}
          title={menuAberto ? 'Fechar menu' : 'Abrir menu'}
          onClick={aoAlternarMenu}
        >
          <Painel />
        </button>
      </div>

      <div className="marca">
        <Marca />
        <MarcaNome />
      </div>

      <Menu aberto={menuAberto} aoFechar={aoAlternarMenu} />
    </div>
  );
}

export function BarraFerramentas({ ferramenta, aoTrocar }) {
  return (
    <div className="canto canto-topo">
      <div className="capsula capsula-linha">
        <button
          type="button"
          className="btn"
          aria-pressed={ferramenta === 'selecionar'}
          aria-label="Selecionar e navegar"
          title="Selecionar e navegar"
          onClick={() => aoTrocar('selecionar')}
        >
          <Cursor />
        </button>
      </div>
    </div>
  );
}

/* Dois eixos independentes, lado a lado: pele (linguagem visual) e tema
   (luminosidade). O seletor de pele existe para a decisao ser tomada olhando,
   nao descrevendo — e sai da tela quando ela for tomada. */
export function Aparencia({ pele, peles, aoTrocarPele, tema, aoTrocarTema }) {
  return (
    <div className="canto canto-sd">
      <div className="capsula capsula-linha">
        {peles.map((p) => (
          <button
            key={p.id}
            type="button"
            className="pele-op"
            aria-pressed={pele === p.id}
            title={`Pele ${p.rotulo}`}
            onClick={() => aoTrocarPele(p.id)}
          >
            {p.rotulo}
          </button>
        ))}
      </div>

      {/* Dentro do painel oficial quem manda no claro/escuro e a Topbar do
          painel, entao o botao de tema simplesmente nao e passado. Some em vez
          de ficar decorativo brigando com o controle de cima. */}
      {aoTrocarTema && (
        <div className="capsula">
          <button
            type="button"
            className="btn"
            aria-label={tema === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
            title={tema === 'dark' ? 'Tema claro' : 'Tema escuro'}
            onClick={aoTrocarTema}
          >
            {tema === 'dark' ? <Sol /> : <Lua />}
          </button>
        </div>
      )}
    </div>
  );
}

function ListaAndares({ aberto, andares, ativoId, aoEscolher, aoCriar, aoRemover }) {
  const { montado, dentro } = usePresenca(aberto);
  if (!montado) return null;

  return (
    <div className="andares" data-dentro={dentro ? 'sim' : 'nao'}>
      <button type="button" className="andar-novo" onClick={aoCriar}>
        <Mais />
        Novo andar
      </button>
      {[...andares].reverse().map((andar) => {
        const ativo = andar.id === ativoId;
        return (
          <div key={andar.id} className="andar" data-ativo={ativo ? 'sim' : 'nao'}>
            {andar.objetos.length > 0 && <span className="andar-conta">{andar.objetos.length}</span>}
            <button
              type="button"
              className="andar-nome"
              onClick={() => aoEscolher(andar.id)}
            >
              <Camadas />
              {andar.nome}
            </button>
            {ativo && andares.length > 1 && (
              <button
                type="button"
                className="andar-fechar"
                aria-label={`Remover ${andar.nome}`}
                title={`Remover ${andar.nome}`}
                onClick={() => aoRemover(andar.id)}
              >
                <Fechar />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ControlesCanto({
  andares,
  ativoId,
  aoEscolherAndar,
  aoCriarAndar,
  aoRemoverAndar,
  vendoAndares,
  aoAlternarAndares,
  vendoMapa,
  aoAlternarMapa,
  minimapa,
  vendoAvisos,
  aoAlternarAvisos,
  painelAvisos,
  totalAvisos = 0,
  projetoNome,
  vendoProjeto,
  aoAlternarProjeto,
  painelProjeto,
  escala,
  aoAmpliar,
  aoReduzir,
  aoReiniciarZoom,
}) {
  return (
    <div className="canto canto-id">
      {minimapa}
      {painelProjeto}
      {painelAvisos}

      <ListaAndares
        aberto={vendoAndares}
        andares={andares}
        ativoId={ativoId}
        aoEscolher={aoEscolherAndar}
        aoCriar={aoCriarAndar}
        aoRemover={aoRemoverAndar}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="capsula capsula-linha">
          <button
            type="button"
            className="btn btn-texto"
            aria-pressed={vendoAndares}
            title="Andares"
            onClick={aoAlternarAndares}
          >
            <Camadas />
            Andares
          </button>

          <button
            type="button"
            className="btn btn-texto"
            aria-pressed={vendoProjeto}
            title="Andar e projeto"
            onClick={aoAlternarProjeto}
          >
            <Caixa />
            {projetoNome}
          </button>
        </div>

        <div className="capsula capsula-linha">
          <button
            type="button"
            className="btn"
            aria-pressed={vendoMapa}
            aria-label="Minimapa"
            title="Minimapa"
            disabled={vendoAndares}
            onClick={aoAlternarMapa}
          >
            <Mapa />
          </button>

          <button
            type="button"
            className="btn btn-sino"
            aria-pressed={vendoAvisos}
            aria-label={`Notificações (${totalAvisos})`}
            title={totalAvisos === 0 ? 'Notificações' : `${totalAvisos} notificações`}
            onClick={aoAlternarAvisos}
          >
            <Sino />
            {/* A contagem so aparece quando ha o que contar. Badge com zero e
                ruido permanente: ensina o olho a ignorar o lugar onde o aviso
                vai aparecer. */}
            {totalAvisos > 0 && (
              <span className="btn-conta mono">{totalAvisos > 99 ? '99+' : totalAvisos}</span>
            )}
          </button>
        </div>

        <div className="zoom">
          <button type="button" className="btn" aria-label="Reduzir zoom" onClick={aoReduzir}>
            <Menos />
          </button>
          <button
            type="button"
            className="zoom-valor mono"
            title="Voltar a 100%"
            onClick={aoReiniciarZoom}
          >
            {Math.round(escala * 100)}%
          </button>
          <button type="button" className="btn" aria-label="Aumentar zoom" onClick={aoAmpliar}>
            <Mais />
          </button>
        </div>
      </div>
    </div>
  );
}
