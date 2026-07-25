import json
import sys

import pytest
from pydantic import ValidationError

import motor.grafo as modulo_grafo
from motor.grafo import construir_grafo
from motor.runner import CommandResult
from motor.spec import WorkflowSpec


class Harness:
    def __init__(self, responder=None, *, plano="prosseguir", cobertura="abortar"):
        self.responder = responder or self._responder_ok
        self.plano, self.cobertura = plano, cobertura
        self.chamadas, self.eventos = [], []

    @staticmethod
    def _responder_ok(papel, _prompt):
        if papel in {"verifier", "evaluator"}:
            return json.dumps({"aprovado": True})
        return "resultado"

    def chamar(self, papel, prompt, **kwargs):
        self.chamadas.append(papel)
        return self.responder(papel, prompt)

    def evento(self, tipo, **dados):
        self.eventos.append((tipo, dados))

    def decisao_auto(self, portao, default=None):
        return self.plano if portao == "plano" else self.cobertura


def modelo(sid="worker", papel="worker", deps=None):
    return {
        "id": sid,
        "papel": papel,
        "objetivo": "Executar",
        "resultado_esperado": "resultado",
        "rubrica": ["contem resultado"],
        "depende_de": deps or [],
    }


def spec_com(*subs, padrao="fan_out_sintese"):
    return {
        "padrao": padrao,
        "missao": {
            "id": "missao-auditoria",
            "objetivo": "Auditar portoes",
            "criterios_cobertura": ["ha resultado aprovado"],
        },
        "restricoes": {"max_tentativas": 1},
        "subagentes": list(subs),
        "sintese": {"instrucao": "Sintetize"},
    }


def rodar(spec, harness, tmp_path, **kwargs):
    grafo = construir_grafo(
        harness, harness, politica=harness, workspace_base=tmp_path, **kwargs
    )
    return grafo.invoke({"spec": spec})


def test_k1_rejeita_validador_sem_configuracao_executavel():
    validador = {
        "id": "validador",
        "tipo": "validador",
        "valida": "alvo",
        "validador": {"kind": "schema_json", "config": {}},
        "objetivo": "Validar",
        "resultado_esperado": "veredito",
        "depende_de": ["alvo"],
    }
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(
            spec_com(modelo("alvo"), validador, padrao="grafo_dependencias")
        )


def test_k1_revalida_edicao_externa_antes_de_executar(monkeypatch, tmp_path):
    spec = spec_com(modelo())
    WorkflowSpec.model_validate(spec)
    monkeypatch.setattr(modulo_grafo, "interrupt", lambda _: {"worker": {"tier": "invalido"}})
    with pytest.raises(ValidationError):
        rodar(spec, Harness(plano=None), tmp_path)


def test_k2_registra_erro_quando_executor_levanta_excecao(tmp_path):
    """Falha de executor vira EVENTO auditável, não exceção que mata a run.

    A auditoria esperava que a exceção propagasse. A decisão do motor é outra e
    é deliberada: uma run de N nós não morre porque um executor falhou — o erro
    é registrado no ledger, a run segue, e o gate de cobertura é quem responde
    pelo buraco no fim. O invariante que importa (nenhuma falha some) continua
    provado aqui: sem o evento, não há como o curador aprender com o erro.
    """
    def falhar(papel, _prompt):
        if papel == "worker":
            raise RuntimeError("falha injetada")
        return "resultado"

    harness = Harness(falhar)
    rodar(spec_com(modelo()), harness, tmp_path)  # não levanta

    erros = [
        dados for tipo, dados in harness.eventos if tipo == "executor.erro"
    ]
    assert erros, "falha de executor tem que deixar rastro auditável"
    assert any(dados.get("executor") == "worker" for dados in erros)
    # e a falha não é promovida a sucesso: o synthesizer não roda em cima do buraco
    assert "synthesizer" not in harness.chamadas


@pytest.mark.parametrize("gate", ["verifier", "evaluator", "ferramenta"])
def test_k3_gate_exige_aprovado_booleano(gate, tmp_path):
    def responder(papel, _prompt):
        if papel == "verifier":
            return json.dumps({"aprovado": "false" if gate == papel else True})
        if papel == "evaluator":
            return json.dumps({"aprovado": "false" if gate == papel else True})
        return "resultado"

    harness, sub, kwargs = Harness(responder), modelo(), {}
    if gate == "ferramenta":
        # `motor.grafo` não expõe mais `subprocess`: execução externa passa pela
        # fronteira `CommandRunner` (runner.py), injetável. Substituir o runner é
        # a forma correta de exercitar o gate sem afrouxar a allowlist.
        class RunnerFalso:
            def run(self, _request):
                return CommandResult(
                    returncode=0, stdout=json.dumps({"aprovado": "false"}), stderr=""
                )

        kwargs["command_runner"] = RunnerFalso()
        kwargs["ferramentas_permitidas"] = [sys.executable]
        sub = {
            "id": "tool", "tipo": "ferramenta", "ferramenta": "probe",
            "objetivo": "Executar", "resultado_esperado": "veredito",
        }
        kwargs["ferramentas"] = {
            "probe": {"comando": sys.executable, "interpreta_saida": "json"}
        }
    rodar(spec_com(sub), harness, tmp_path, **kwargs)
    assert "synthesizer" not in harness.chamadas


def test_k3_nao_propaga_saida_reprovada_para_dependente(tmp_path):
    def responder(papel, prompt):
        if papel == "verifier":
            return json.dumps({"aprovado": "subagente 'fonte'" not in prompt})
        if papel == "evaluator":
            return json.dumps({"aprovado": False, "lacunas": ["fonte reprovada"]})
        return "resultado"

    harness = Harness(responder)
    spec = spec_com(
        modelo("fonte", "papel_fonte"),
        modelo("destino", "papel_destino", ["fonte"]),
        padrao="grafo_dependencias",
    )
    rodar(spec, harness, tmp_path)
    assert "papel_destino" not in harness.chamadas


def test_k3_decisao_invalida_nao_prossegue_parcial(monkeypatch, tmp_path):
    def reprovar(papel, _prompt):
        if papel in {"verifier", "evaluator"}:
            return json.dumps({"aprovado": False, "lacunas": ["sem resultado"]})
        return "resultado"

    monkeypatch.setattr(modulo_grafo, "interrupt", lambda _: "talvez")
    harness = Harness(reprovar, cobertura=None)
    rodar(spec_com(modelo()), harness, tmp_path)
    assert "synthesizer" not in harness.chamadas
