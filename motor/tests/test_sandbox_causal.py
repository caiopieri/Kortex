"""Suite causal do sandbox de comando (H05b).

Estes testes NAO usam fake: eles sobem container de verdade e provam que o
isolamento acontece. Sao a diferenca entre "o adapter monta o argv certo" -- que
os testes de precondicao ja cobriam -- e "o comando realmente nao alcanca a rede
nem o disco do host".

Que essa distincao importa ficou provado em 2026-07-28: o adapter montava
`--mount ...,rw`, que o Docker rejeita com exit 125 ANTES de subir o container.
Nenhum teste pegou porque nenhum executava; e nenhum ponto de entrada compunha o
runner, entao a producao inteira rodava com DenyCommandRunner e o defeito era
invisivel. Codigo que nunca roda nao tem bug conhecido.

Pular por padrao e deliberado: o gate determinista da carta tem orcamento de 5
minutos e nao pode depender de daemon externo. O job de conformidade exporta
`KORTEX_SANDBOX_IMAGE` e ai a ausencia de pre-requisito FALHA, nao pula --
conforme `specs/001-hardening-producao/sandbox-conformance.md`.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from motor.runner import (
    MAX_COMBINED_OUTPUT_BYTES,
    CommandRequest,
    DockerSandboxRunner,
)

_IMAGEM = os.environ.get("KORTEX_SANDBOX_IMAGE", "")
_PYTHON = os.environ.get("KORTEX_SANDBOX_PYTHON", "/usr/local/bin/python3")

pytestmark = pytest.mark.skipif(
    not _IMAGEM,
    reason="conformidade de sandbox exige KORTEX_SANDBOX_IMAGE (digest imutavel)",
)


@pytest.fixture(scope="module")
def runner() -> DockerSandboxRunner:
    r = DockerSandboxRunner(_IMAGEM, (_PYTHON,))
    # Pre-requisito ausente FALHA a conformidade; nao pula.
    r.deployment_evidence()
    return r


def _py(runner: DockerSandboxRunner, workspace: Path, codigo: str, timeout: int = 60):
    (workspace / "prova.py").write_text(codigo, encoding="utf-8")
    return runner.run(CommandRequest((_PYTHON, "prova.py"), workspace, timeout))


def _containers_do_motor() -> set[str]:
    saida = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=motor-sandbox-"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    return {linha for linha in saida.split() if linha}


# --------------------------------------------------------------------------
# Identidade do deployment
# --------------------------------------------------------------------------

def test_evidencia_registra_engine_os_politica_e_digest_efetivo(runner) -> None:
    ev = runner.deployment_evidence()
    assert ev.os_type == "linux" and ev.engine_version
    assert ev.adapter == "motor.runner.DockerSandboxRunner"
    assert ev.policy_version == "h05b-docker-v1"
    # O digest EFETIVO tem que bater com o pedido -- e isso que impede a imagem
    # ser trocada por baixo mantendo a mesma tag.
    assert (ev.effective_repo_digest.rsplit("@", 1)[-1]
            == ev.requested_image_digest.rsplit("@", 1)[-1])


# --------------------------------------------------------------------------
# Sistema de arquivos
# --------------------------------------------------------------------------

def test_escrita_no_workspace_funciona_e_persiste_no_host(runner, tmp_path) -> None:
    res = _py(runner, tmp_path, "open('saida.txt','w').write('gerado')")
    assert res.returncode == 0, res.stderr
    assert (tmp_path / "saida.txt").read_text() == "gerado"


def test_escrita_fora_do_workspace_falha(runner, tmp_path) -> None:
    """Raiz read-only: sem isso o comando gerado por modelo escreve no container
    inteiro, e o proximo run herda o estado."""
    res = _py(runner, tmp_path, "open('/etc/invadido','w').write('x')")
    assert res.returncode != 0
    assert "Read-only file system" in res.stderr or "Permission denied" in res.stderr


def test_arquivo_irmao_do_workspace_e_invisivel(runner, tmp_path) -> None:
    """So o workspace e montado. O diretorio-pai -- onde moram os outros jobs e,
    num runner compartilhado, os segredos do host -- nao pode ser alcancavel."""
    segredo = tmp_path.parent / "segredo-do-host.txt"
    segredo.write_text("credencial")
    ws = tmp_path / "ws"
    ws.mkdir()
    res = _py(runner, ws, f"print(open({str(segredo)!r}).read())")
    assert res.returncode != 0
    assert "credencial" not in res.stdout


def test_socket_do_engine_nao_esta_montado(runner, tmp_path) -> None:
    """Socket do Docker dentro do sandbox e fuga trivial: quem fala com o engine
    sobe outro container privilegiado."""
    res = _py(runner, tmp_path, "import os;print(os.path.exists('/var/run/docker.sock'))")
    assert res.returncode == 0 and res.stdout.strip() == "False"


# --------------------------------------------------------------------------
# Rede
# --------------------------------------------------------------------------

def test_dns_indisponivel_sem_depender_de_servico_publico(runner, tmp_path) -> None:
    res = _py(runner, tmp_path, (
        "import socket\n"
        "try:\n"
        "    socket.getaddrinfo('exemplo.invalido', 80); print('RESOLVEU')\n"
        "except OSError as e: print('SEM-DNS')\n"
    ))
    assert res.returncode == 0 and res.stdout.strip() == "SEM-DNS"


def test_saida_de_rede_indisponivel(runner, tmp_path) -> None:
    """Conecta a um IP literal, sem servico publico: `--network none` deixa so o
    loopback, entao a tentativa falha por rede inalcancavel, nao por timeout."""
    res = _py(runner, tmp_path, (
        "import socket\n"
        "s=socket.socket(); s.settimeout(5)\n"
        "try:\n"
        "    s.connect(('1.1.1.1',53)); print('CONECTOU')\n"
        "except OSError: print('SEM-REDE')\n"
    ))
    assert res.returncode == 0 and res.stdout.strip() == "SEM-REDE"


# --------------------------------------------------------------------------
# Privilegios
# --------------------------------------------------------------------------

def test_processo_roda_sem_root_e_sem_capabilities(runner, tmp_path) -> None:
    res = _py(runner, tmp_path, (
        "import os\n"
        "print(os.getuid())\n"
        "print([l for l in open('/proc/self/status') if l.startswith('CapEff')][0].strip())\n"
    ))
    assert res.returncode == 0, res.stderr
    uid, capeff = res.stdout.split("\n")[:2]
    assert uid.strip() == str(os.getuid()) and uid.strip() != "0"
    assert set(capeff.split(":")[1].strip()) == {"0"}


def test_no_new_privileges_impede_escalonar_por_setuid(runner, tmp_path) -> None:
    res = _py(runner, tmp_path, (
        "print([l for l in open('/proc/self/status') if l.startswith('NoNewPrivs')][0].strip())"
    ))
    assert res.returncode == 0 and res.stdout.strip().endswith("1")


# --------------------------------------------------------------------------
# Limites de saida e de tempo
# --------------------------------------------------------------------------

def test_saida_combinada_limitada_a_1_mib_durante_o_stream(runner, tmp_path) -> None:
    """O limite tem que valer NO STREAM. Buferizar tudo para so entao truncar
    deixa um comando gerado por modelo estourar a memoria do host antes do corte.
    """
    res = _py(runner, tmp_path, (
        "import sys\n"
        "bloco='x'*65536\n"
        "for _ in range(64): sys.stdout.write(bloco); sys.stderr.write(bloco)\n"
    ))
    assert res.truncated and res.erro == "output_overflow"
    assert len(res.stdout) + len(res.stderr) <= MAX_COMBINED_OUTPUT_BYTES + 1


@pytest.mark.parametrize("timeout", [0, -1, 301, 1.5, True, "10"])
def test_timeout_aceita_somente_inteiro_estrito_de_1_a_300(runner, tmp_path, timeout) -> None:
    """`True` esta na lista de proposito: `isinstance(True, int)` e verdadeiro em
    Python, entao a checagem precisa ser de TIPO EXATO, senao `timeout=True` vira
    1 segundo silenciosamente."""
    res = runner.run(CommandRequest((_PYTHON, "-c", "pass"), tmp_path, timeout))
    assert res.erro == "request_invalido" and "timeout" in res.motivo


def test_timeout_encerra_a_arvore_inteira_e_nada_sobrevive(runner, tmp_path) -> None:
    antes = _containers_do_motor()
    res = _py(runner, tmp_path, (
        "import subprocess,sys,time\n"
        "subprocess.Popen([sys.executable,'-c','import time;time.sleep(600)'])\n"
        "time.sleep(600)\n"
    ), timeout=5)
    assert res.timed_out and res.erro == "timeout"
    # Nenhum descendente sobrevive: o container e removido, e com ele o PID
    # namespace inteiro. Container vazado aqui e vazamento de recurso silencioso.
    assert _containers_do_motor() <= antes


# --------------------------------------------------------------------------
# Ciclo de vida da unidade
# --------------------------------------------------------------------------

@pytest.mark.parametrize("codigo,esperado", [
    ("print('ok')", "sucesso"),
    ("import sys;sys.exit(3)", "falha"),
    ("import sys\nfor _ in range(64): sys.stdout.write('x'*65536)", "overflow"),
])
def test_unidade_removida_apos_sucesso_falha_e_overflow(
    runner, tmp_path, codigo, esperado
) -> None:
    antes = _containers_do_motor()
    _py(runner, tmp_path, codigo)
    assert _containers_do_motor() <= antes, f"container vazou apos {esperado}"


def test_executavel_fora_da_allowlist_nao_roda(runner, tmp_path) -> None:
    """A allowlist e de caminhos absolutos DENTRO da imagem -- e o `--entrypoint`,
    nao um binario do host. Sem ela, o modelo escolhe o proprio interpretador e o
    `--read-only` deixa de ser a unica contencao."""
    res = runner.run(CommandRequest(("/bin/sh", "-c", "echo x"), tmp_path, 30))
    assert res.erro == "request_invalido" and "allowlist" in res.motivo


def test_argv_executa_sem_shell_intermediario(runner, tmp_path) -> None:
    """Se houvesse shell no meio, isto expandiria e escreveria o arquivo."""
    res = runner.run(CommandRequest(
        (_PYTHON, "-c", "import sys;print(sys.argv[1])", "$(touch /workspace/injetado)"),
        tmp_path, 30,
    ))
    assert res.returncode == 0
    assert "$(touch" in res.stdout
    assert not (tmp_path / "injetado").exists()


def test_evidencia_serializa_para_o_relatorio_de_conformidade(runner) -> None:
    ev = runner.deployment_evidence()
    assert json.loads(json.dumps(ev.__dict__))["policy_version"] == "h05b-docker-v1"


# --------------------------------------------------------------------------
# Elo final: o GRAFO executando pelo sandbox
# --------------------------------------------------------------------------

def _rodar_ferramenta_no_grafo(tmp_path, runner, comando_args, **over):
    """Roda uma spec de um no de ferramenta com o sandbox composto de verdade."""
    from langgraph.checkpoint.memory import InMemorySaver

    from motor.eventos import LogEventos
    from motor.grafo import construir_grafo
    from motor.modelos import ClienteStub
    from motor.politica import PoliticaGates

    log = LogEventos(tmp_path / "eventos.jsonl")
    grafo = construir_grafo(
        ClienteStub(lambda papel, _p: json.dumps({"aprovado": True, "lacunas": []})
                    if papel == "evaluator" else "final"),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
        workspace_base=tmp_path / "runs",
        ferramentas={"audit": {"comando": " ".join(comando_args),
                               "interpreta_saida": "exit_code"}},
        command_runner=runner,
        **over,
    )
    spec = {
        "versao": "0.1", "padrao": "fan_out_sintese",
        "missao": {"id": "sandbox", "objetivo": "executar de verdade",
                   "contexto": "", "criterios_cobertura": ["comando executou"]},
        "restricoes": {"teto_custo": 1.0, "max_subagentes": 1, "max_tentativas": 1},
        "subagentes": [{"id": "tool", "tipo": "ferramenta", "ferramenta": "audit",
                        "objetivo": "executar", "entradas": {},
                        "resultado_esperado": "exit code"}],
        "gates": [], "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }
    try:
        return grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "sbx"}})
    finally:
        log.fechar()


def test_grafo_executa_de_verdade_pelo_sandbox(runner, tmp_path) -> None:
    """O que separa "gerou codigo" de "entregou software".

    Ate 2026-07-28 nenhum ponto de entrada compunha runner, e o grafo resolvia a
    allowlist contra o HOST -- `/usr/local/bin/python3` nao existe no macOS, entao
    mesmo com sandbox ligado todo comando morreria em `executavel_nao_permitido`.
    Contencao que reprova tudo parece funcionar exatamente como contencao que
    funciona; so um teste que EXECUTA distingue as duas.
    """
    # `exit(N)` sem espaco nem aspas de proposito: a fronteira de comando
    # serializa com espacos, re-splita e descarta aspas, entao literal de string
    # nao sobrevive ate o container. E limitacao do formato de `ferramentas`, nao
    # do sandbox -- mas ao escrever spec vale saber: comando com argumento
    # composto precisa virar arquivo no workspace, nunca `-c`.
    #
    # O exit code e justamente o que o portao le, e o par 0/3 abaixo prova que
    # ele vem do processo real: um runner que nao executa nada nao consegue
    # produzir os dois desfechos.
    aprovado = _rodar_ferramenta_no_grafo(tmp_path, runner, (_PYTHON, "-c", "exit(0)"))
    assert aprovado["resultados"][0]["aprovado"] is True, aprovado["resultados"]

    reprovado = _rodar_ferramenta_no_grafo(tmp_path, runner, (_PYTHON, "-c", "exit(3)"))
    assert reprovado["resultados"][0]["aprovado"] is False


def test_grafo_recusa_executavel_fora_da_allowlist_selada(runner, tmp_path) -> None:
    """Com namespace proprio a allowlist vem da imagem, mas continua fail-closed:
    trocar o interpretador nao pode passar so porque o host nao opina mais."""
    resultado = _rodar_ferramenta_no_grafo(
        tmp_path, runner, ("/bin/sh", "-c", "echo x"),
    )
    assert resultado["resultados"][0]["aprovado"] is False


def test_ferramentas_permitidas_do_host_nao_afrouxam_o_sandbox(runner, tmp_path) -> None:
    """A config de ferramentas do host nao pode ampliar a allowlist selada --
    senao o operador reabre no `--registro` o que a imagem fechou."""
    resultado = _rodar_ferramenta_no_grafo(
        tmp_path, runner, ("/bin/sh", "-c", "echo x"),
        ferramentas_permitidas=["/bin/sh"],
    )
    assert resultado["resultados"][0]["aprovado"] is False
