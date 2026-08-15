/* Meta-fábrica · registro global de temas.
   Carregado no <helmet> de cada tela. Aplica o tema ativo (localStorage
   'mf-theme-active') injetando um <style> que sobrescreve as vars do kit
   (.mf-root escuro / [data-theme="stark"] claro). Temas custom em
   'mf-themes-custom'. Troca em uma tela = troca em todas (evento storage). */
(function () {
  var KEYS = ['bg','surface','surface2','border','focus','text','text2','text3',
    'accent','red','amber','green','blue','inv-bg','inv-text','grap1','grap2','rim'];

  var LIGHT_AZUL = {
    'bg':'#E4E9F2','surface':'#FAFBFD','surface2':'#EDF0F6','border':'#D2DAE7','focus':'#9AA8BF',
    'text':'#26324B','text2':'#4D5B76','text3':'#7E8AA1','accent':'#54718D',
    'red':'#B0413E','amber':'#9A6A1A','green':'#3B7D5D','blue':'#3F62A8',
    'inv-bg':'#26324B','inv-text':'#FAFBFD',
    'grap1':'#C9D1DE','grap2':'#AEB9CB','rim':'#8F9DB5',
    'card-shadow':'0 1px 2px rgba(38,50,75,.06),0 4px 14px rgba(38,50,75,.07)'
  };

  var BUILTINS = [
    { id:'metafabrica', nome:'Meta-fábrica', builtin:true,
      escuro:{
        'bg':'#0B0C0E','surface':'#121417','surface2':'#17191D','border':'#26292E','focus':'#3E434A',
        'text':'#E8E6E1','text2':'#8A8F98','text3':'#5A5F66','accent':'#E8A33D',
        'red':'#E5484D','amber':'#E8A33D','green':'#30A46C','blue':'#3E63DD',
        'inv-bg':'#E8E6E1','inv-text':'#0B0C0E',
        'grap1':'#2A2D33','grap2':'#3A3E46','rim':'#55596200'
      },
      claro: LIGHT_AZUL },
    { id:'gemini', nome:'Gemini (suave)', builtin:true,
      escuro:{
        'bg':'#131314','surface':'#1E1F20','surface2':'#282A2C','border':'#3C4043','focus':'#5F6368',
        'text':'#E3E3E3','text2':'#BDC1C6','text3':'#9AA0A6','accent':'#8AB4F8',
        'red':'#F28B82','amber':'#FDD663','green':'#81C995','blue':'#8AB4F8',
        'inv-bg':'#8AB4F8','inv-text':'#131314',
        'grap1':'#2A2C2E','grap2':'#3A3D40','rim':'#5F636800'
      },
      claro: LIGHT_AZUL },
    { id:'framer', nome:'Framer (elétrico)', builtin:true,
      escuro:{
        'bg':'#0A0A0A','surface':'#161616','surface2':'#232323','border':'#2A2A2A','focus':'#4B4B4B',
        'text':'#F2F2F2','text2':'#B3B3B3','text3':'#7A7A7A','accent':'#0099FF',
        'red':'#FF5555','amber':'#FFB443','green':'#30C453','blue':'#0099FF',
        'inv-bg':'#0099FF','inv-text':'#FFFFFF',
        'grap1':'#242424','grap2':'#343434','rim':'#4B4B4B00'
      },
      claro: LIGHT_AZUL }
  ];

  function customs() {
    try { return JSON.parse(localStorage.getItem('mf-themes-custom')) || []; }
    catch (e) { return []; }
  }
  function all() { return BUILTINS.concat(customs()); }
  function activeId() { return localStorage.getItem('mf-theme-active') || 'metafabrica'; }
  function decl(o) {
    return Object.keys(o).map(function (k) { return '--' + k + ':' + o[k]; }).join(';');
  }
  function apply() {
    var t = all().filter(function (x) { return x.id === activeId(); })[0] || BUILTINS[0];
    var el = document.getElementById('mf-theme-active-style');
    if (!el) {
      el = document.createElement('style');
      el.id = 'mf-theme-active-style';
    }
    // sempre re-anexa no FIM do head, pra vencer o <style> do helmet (mesma especificidade)
    document.head.appendChild(el);
    el.textContent =
      '.mf-root{' + decl(t.escuro) + '}' +
      '.mf-root[data-theme="stark"]{' + decl(t.claro) + '}' +
      'body{background:' + t.escuro.bg + '}';
    document.dispatchEvent(new CustomEvent('mf-theme-applied', { detail: t }));
  }

  // o helmet monta seu <style> depois deste script: re-aplica quando o head ganhar estilos novos
  var mo = new MutationObserver(function (muts) {
    var el = document.getElementById('mf-theme-active-style');
    for (var i = 0; i < muts.length; i++) {
      var added = muts[i].addedNodes;
      for (var j = 0; j < added.length; j++) {
        var n = added[j];
        if (n !== el && (n.tagName === 'STYLE' || n.tagName === 'LINK')) {
          if (el && el !== document.head.lastElementChild) document.head.appendChild(el);
          return;
        }
      }
    }
  });
  mo.observe(document.head, { childList: true });

  window.MFThemes = {
    keys: KEYS,
    builtins: BUILTINS,
    all: all,
    customs: customs,
    activeId: activeId,
    apply: apply,
    setActive: function (id) { localStorage.setItem('mf-theme-active', id); apply(); },
    saveCustoms: function (list) { localStorage.setItem('mf-themes-custom', JSON.stringify(list)); apply(); }
  };

  window.addEventListener('storage', function (e) {
    if (!e.key || e.key.indexOf('mf-theme') === 0) apply();
  });
  apply();
})();
