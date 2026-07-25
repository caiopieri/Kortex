# Verificacao - H05b sandbox real

Status: **BLOQUEADA; PRE-CONDICAO DE TIMEOUT CONCLUIDA**
Data: 2026-07-12
Ambiente de teste: macOS, CPython 3.11.15

## Escopo auditado

Graphify foi consultado antes da leitura integral dos dois unicos arquivos de producao desta
fatia: `motor/motor/runner.py` e `motor/motor/grafo.py`. Tambem foram lidos os contratos H05,
os testes owner e o workflow de CI relevante.

## Discovery falsificavel do backend

Nenhuma imagem foi baixada e nenhum backend foi iniciado. O estado observado foi:

| Probe | Resultado |
|---|---|
| `docker` | CLI 29.6.1 em `/usr/local/bin/docker` |
| contextos Docker | `desktop-linux` ativo e `default`; ambos apontam para o mesmo socket morto |
| Docker daemon | socket indisponivel; `docker version`, `info`, `image ls` e `network inspect none` falharam fechados |
| `podman`, `nerdctl`, `colima` | ausentes |
| Lima | instancia `pmos` parada; `containerd.system=false` e `containerd.user=false` |
| imagem confiavel local | nao enumeravel e nao declarada no repositorio |
| policy de sandbox versionada | ausente |
| job H05b no CI | ausente |

Este ambiente nao permite provar filesystem, ambiente, rede, output ou arvore de processos.
Iniciar Docker Desktop ou uma VM sem antes fixar imagem e policy tambem nao seria suficiente.

## Resultado dos reprodutores C3

O baseline H05b tinha cinco nodeids. Antes desta fatia, todos falhavam:

- tres timeouts invalidos levantavam `TypeError` ou `ValueError`;
- o teste de descendentes recebia `runner_indisponivel`;
- o teste de output recebia `runner_indisponivel`.

A pre-condicao agora rejeita valores que nao sejam `int` estrito entre 1 e 300 antes de
delegar ao runner (`motor/motor/grafo.py:683`). `bool`, floats, strings, listas, zero,
negativos e valores acima de 300 falham fechados. Os limites 1 e 300 sao delegados sem
coercao.

Evidencia:

| Checagem | Resultado |
|---|---|
| pre-condicoes H05b | `11 passed` |
| reprodutores de timeout invalido | `3 passed` |
| H04/H05a + pre-condicoes H05b | `32 passed` |
| grafo/ferramenta/validadores + H04/H05a/pre-condicoes | `97 passed` |
| limite de output | bloqueado por backend real |
| TERM/KILL da arvore | bloqueado por backend real |
| Ruff, mypy, Bandit high/high e compileall focados | limpos |

H05b, C2 e C3 nao sao declarados sustentados. A capacidade `kind:"comando"` permanece
indisponivel em producao por `DenyCommandRunner`.

## Job minimo de conformidade proposto

O job deve ser separado do pytest unitario e falhar, nunca pular, quando os pre-requisitos
nao estiverem presentes. Pre-requisitos de deployment:

1. runner Linux efemero e dedicado, com Docker ou Podman identificado por versao;
2. adapter de producao separado e composto explicitamente;
3. imagem pre-provisionada e referenciada apenas por digest `repo@sha256:...`;
4. versao imutavel da policy de sandbox e allowlist de executaveis dentro da imagem;
5. nenhum pull implicito durante a certificacao.

O preflight deve registrar engine, OS, adapter, policy e digest efetivo e verificar por
`inspect`:

- `network=none` e namespace contendo somente loopback;
- root filesystem read-only;
- um unico bind RW, o workspace do caso; nenhum mount do pai ou do socket do engine;
- ambiente construido por allowlist, sem heranca do host;
- usuario nao-root, `cap-drop=ALL`, `no-new-privileges` e limite de PIDs;
- processo sem shell intermediario e argv preservado.

A suite de conformidade deve provar causalmente:

- escrita no workspace e recusa de escrita fora dele;
- segredo do host ausente e ambiente minimo conhecido;
- leitura de sibling/host negada;
- rede externa e DNS indisponiveis sem depender de servico publico;
- stdout+stderr combinados limitados a 1 MiB durante streaming, sem buffer ilimitado;
- timeout estrito de 1 a 300 segundos;
- TERM no workload e KILL de toda a unidade apos 2 segundos, sem descendente sobrevivente;
- remocao da unidade de sandbox depois de sucesso, falha, overflow e timeout.

O artefato do job deve conter o relatorio assinado da execucao e os identificadores acima.
Somente essa combinacao adapter + engine + policy + imagem pode habilitar comando no
deployment testado; o protocolo Python isolado nao recebe selo global.

## Security DoD

- Nenhum runner host foi adicionado.
- Nenhuma rede, imagem ou daemon foi ativado durante o discovery.
- Timeout invalido falha antes da fronteira externa e nao chama o runner.
- Rollback preserva `DenyCommandRunner`.
- H13 restaurou `motor/docs/security-DoD.md`; a ausencia historica nao altera o bloqueio de
  H05b nem constitui certificacao retroativa.

## Onde isto pode dar errado

- Um daemon disponivel em outro host ou contexto nao certifica este deployment nem resolve a
  ausencia de imagem e policy versionadas.
- `--network=none` e rootfs read-only isolados nao bastam; mount do socket do engine, caps ou
  usuario root restaurariam autoridade sobre o host.
- Limitar o resultado depois de `communicate()` nao limita memoria. O adapter precisa drenar
  stdout e stderr com um orcamento combinado enquanto o processo executa.
- Matar apenas o PID pai deixa descendentes. A conformidade deve observar a unidade inteira e
  provar ausencia do marcador tardio.
- Os dois reprodutores restantes nao podem ser tornados verdes com o runner fake; isso seria
  uma falsa certificacao de H05b.
