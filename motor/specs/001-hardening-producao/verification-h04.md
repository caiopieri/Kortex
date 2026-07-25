# Verificacao - H04 executor de comando

Status: **CONCLUIDA NO ESCOPO H04**  
Data: 2026-07-11  
Ambiente de teste: CPython 3.11.15

## Contrato Entregue

- A policy e default-deny: allowlist ausente, vazia, relativa ou por basename nao executa.
- A identidade permitida e o caminho absoluto canonico de um arquivo executavel existente
  (`motor/motor/grafo.py:385`). Symlink e basename coincidente nao criam outra identidade.
- O primeiro token do template e estatico; input nao seleciona o executavel
  (`motor/motor/grafo.py:694`).
- Placeholder nao pode criar opcao antes de um `--` literal; depois de `--`, positional
  iniciado por hifen continua valido (`motor/motor/grafo.py:701`).
- A execucao usa lista de argumentos e `shell=False` implicito, nunca concatena shell
  (`motor/motor/grafo.py:742`). Erros de resolucao/execucao falham fechados.

`motor/motor/registro.py` nao foi alterado. Entradas antigas como `python3` continuam sendo
lidas, mas agora sao deliberadamente inoperantes; a configuracao deve fornecer um caminho
absoluto confiavel, por exemplo o valor canonico de `sys.executable`.

## Evidencia Causal

| Garantia | Evidencia |
|---|---|
| Corpus congelado H04 | `motor/tests/test_hardening_h04.py:20`; 11 nodeids |
| Executavel nao vem de input | `motor/tests/test_hardening_h04.py:61` |
| Placeholder parcial nao fabrica `-c` | `motor/tests/test_hardening_h04.py:72` |
| `--` preserva positional com hifen | `motor/tests/test_hardening_h04.py:85` |
| Diretorio/arquivo sem bit executavel sao negados | `motor/tests/test_hardening_h04.py:99` |
| Fluxos rastreados usam identidade absoluta | `motor/tests/test_validadores_deterministicos.py:169` |

O terminal delegado inicialmente deixou quatro testes rastreados vermelhos e nao cobriu
executavel escolhido por placeholder, opcao criada por placeholder parcial nem alvo de
allowlist nao executavel. A aceitacao ocorreu somente depois desses casos serem reproduzidos,
corrigidos e reexecutados no processo principal.

## Gate

| Checagem | Resultado |
|---|---|
| H04 + regressao de ferramenta/registro/validadores | `49 passed` |
| Suite rastreada, sem packs futuros | `448 passed` |
| Pack completo como overlay | `66 passed, 45 failed` |
| Ruff | limpo |
| mypy | limpo, 69 arquivos |
| Bandit high/high | limpo |
| compileall | limpo |
| Gitleaks dir (`motor/`) | limpo, 16.30 MB |
| build sdist/wheel | passou |
| install e import do wheel isolado | passou |

O H04 eliminou os seis reprodutores vermelhos de seu owner e preservou os cinco controles
de metacaracteres. Um caso H05a tambem deixou de reproduzir pelo bloqueio estrutural de
opcao, mas H05a permanece aberto: esse efeito incidental nao prova isolamento.

## Security DoD

- Input externo: template e valores sao separados por token; executavel e opcoes estruturais
  nao podem ser selecionados por input.
- Policy: ausencia ou entrada nao canonica falha fechada.
- Injecao shell: nao ha shell; os cinco controles congelados preservam um valor por `argv`.
- Segredos/SAST: Gitleaks e Bandit high/high limpos.
- Ambiente/autonomia: **nao atendido por H04**. Nao ha sandbox de filesystem/rede, ambiente
  limpo, limite de output nem encerramento da arvore de processos; pertencem a H05a/H05b.

Esta verificacao nao declara o motor pronto para producao nem o Gate CI global aprovado.

## Onde isto pode dar errado

- Existe TOCTOU entre `resolve`/`stat` e `subprocess.run`; um path mutavel pode trocar de
  identidade nesse intervalo. H05 deve executar por backend de sandbox com identidade
  imutavel, nao tentar prometer seguranca apenas com mais `Path` checks.
- Caminho absoluto confiavel autoriza o binario, nao a linguagem de argumentos desse binario.
  O guard bloqueia opcao criada integralmente pelo input, mas cada ferramenta ainda precisa
  de contrato de argumentos proprio quando opcoes literais forem perigosas.
- O processo ainda herda ambiente, descritores permitidos pelo runtime e acesso do host. `cwd`
  e organizacao de arquivos, nao confinamento.
- Configuracoes antigas por basename agora falham fechadas. Sem migracao operacional explicita,
  validadores antes funcionais serao reprovados em producao.
