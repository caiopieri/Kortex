/* Pele = linguagem visual do canvas, eixo INDEPENDENTE do claro/escuro.
 *
 * Claro/escuro nao mora mais aqui: dentro do painel oficial quem manda e a
 * Topbar, e o canvas recebe `modo` por prop. Manter um segundo dono do tema
 * daria duas fontes de verdade brigando pelo mesmo atributo.
 *
 * As duas peles existem ao mesmo tempo porque a escolha entre elas ainda nao
 * foi feita — quando for, a perdedora sai do CSS e o seletor sai da tela.
 */
const CHAVE_PELE = 'kortex-canvas-pele';

export const PELES = [
  { id: 'origem', rotulo: 'Origem' },
  { id: 'bruma', rotulo: 'Bruma' },
];

export function peleAtual() {
  return document.documentElement.getAttribute('data-pele') === 'origem' ? 'origem' : 'bruma';
}

export function aplicarPele(pele) {
  document.documentElement.setAttribute('data-pele', pele);
  try {
    localStorage.setItem(CHAVE_PELE, pele);
  } catch {
    /* Mesma razao do tema: falhar em persistir nao pode impedir a troca. */
  }
}
