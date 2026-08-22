# Fontes locais — IBM Plex Mono

Estes dois arquivos são **binários trazidos de fora do repositório**. A
procedência está aqui inteira porque binário sem procedência é exatamente o que
a gente recusa em todo o resto do projeto.

## O que está aqui, e de onde veio

| arquivo | peso | bytes | sha256 |
|---|---|---|---|
| `ibm-plex-mono-latin-400.woff2` | 400 | 10052 | `c36f509c0a8f9f85f29cb44bc8701d8a9e0b14c499e77a884f789ead7093a7ac` |
| `ibm-plex-mono-latin-600.woff2` | 600 | 10120 | `ad4580d8cb4b5f627c2d18457656732f7f7b070f7837fbc380e08054157e6f6c` |

Origem, baixado em 2026-08-22 (`v20` do Google Fonts, subset **latin**):

    400  https://fonts.gstatic.com/s/ibmplexmono/v20/-F63fjptAgt5VM-kVkqdyU8n1i8q131nj-o.woff2
    600  https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3vAOwlBFgsAXHNk.woff2

Conferir a qualquer momento:

    shasum -a 256 src/fontes/*.woff2

Licença: **SIL Open Font License 1.1**, texto completo em `LICENCA-OFL.txt`,
copiado de `https://raw.githubusercontent.com/IBM/plex/master/LICENSE.txt`.
A OFL permite embutir e redistribuir; exige manter o aviso de copyright e não
vender a fonte isolada. Nenhuma das duas coisas nos limita.

## Por que só a mono, e por que só estes dois pesos

O painel carregava **três famílias e dez pesos** do Google Fonts. Isso fazia a
tela bloquear na folha de estilo remota até o timeout num painel cujo lugar é um
runner de LAN — issue #26.

**A sans saiu e não voltou.** A evidência é um experimento natural que já tinha
rodado sem ninguém notar: `canvas.css` declarava `--fonte-ui: 'Archivo', …` e o
`Archivo` **nunca foi carregado em lugar nenhum**. Uma das peles do canvas
renderizava em fonte de sistema há sabe-se lá quanto tempo e ninguém percebeu.
Se a diferença não é notada, ela não é carga.

**A mono ficou porque a evidência acima é silenciosa sobre ela.** Ninguém testou
a mono caindo, e é nela que mora o dado: hash, `seq`, caminho, contagem. Ali `0`
contra `O` e `1` contra `l` têm custo real — a pessoa lê um hash errado e não
sabe que leu errado. O argumento não é alinhamento (qualquer monoespaçada
alinha), é **forma de caractere**.

Pesos: só **400 e 600**. O CSS não usa nenhum outro na mono — o `500` que existe
em `--micro-peso` está em `.pele-op`, `.menu-titulo` e `.pp-titulo`, que são
fonte de UI, não `.mono`. Trazer o 500 custaria ~10 kB para nada.

Subset: só **latin**. Conferido `unicode-range` caractere a caractere contra
ãçõáéíóúâêôàü, maiúsculas, travessão, reticências e aspas curvas: nenhum fora.
O `latin-ext` é leste-europeu. `latin` = 98.6 kB nas três famílias contra 356.9
kB de todos os sete subsets — foi essa medição que tornou a decisão barata.

## Se um dia precisar atualizar

O `v20` está no caminho da URL, então a versão é rastreável. Baixe, confira o
sha256, e **atualize esta tabela** — o número aqui é o que permite a alguém saber
que o arquivo no repositório é o que diz ser.
