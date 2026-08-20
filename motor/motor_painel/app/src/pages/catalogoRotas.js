/* O que a tela de rotas pode afirmar.
 *
 * Existe separado do componente por uma razão só: para ser testável. A regra
 * que este arquivo carrega é a da issue #23 — catálogo vazio produz ZERO
 * cartão. A versão anterior devolvia cinco workflows inventados quando a API
 * não trazia nada, três deles marcados `certificado`, com versão, contagem de
 * nós e data de criação. Nada daquilo existia.
 *
 * E não é só o vazio: a tela exibia `rota`, `nos`, `criado`, `status` e `tags`,
 * campos que só o objeto fabricado tinha. No caminho feliz — com o registro
 * respondendo de verdade — ela renderizava `undefined` neles, e os filtros por
 * `status` casavam com nada. O dado real é `{id, nome, descricao, subagentes,
 * versao}`, e é só isso que sai daqui.
 */

/* `versao` vem null quando o arquivo do registro não a declara — e nenhum
   declara hoje. Antes o servidor preenchia "1.0.0", que é afirmar um fato de
   versionamento que ninguém escreveu. */
export const VERSAO_AUSENTE = 'versão não declarada';

export function linhasDoCatalogo(payload) {
  if (!Array.isArray(payload)) return [];

  return payload
    .filter((item) => item && typeof item === 'object' && item.id)
    .map((item) => ({
      id: String(item.id),
      nome: item.nome || String(item.id),
      descricao: item.descricao || '',
      subagentes: Array.isArray(item.subagentes) ? item.subagentes : [],
      versao: item.versao || null,
    }));
}
