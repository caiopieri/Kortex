from copy import deepcopy
from math import inf, nan

import pytest

from motor.curador import PISO_CASOS, certificar_sombra, preparar_promocao_gated, rodar_sombra
from motor.eventos_schema import tipos


PROPOSTA = {"slot": "executor/t1", "titular": "modelo-t", "candidato": "modelo-c"}


def _caso(id_caso: str, aprovado: bool, custo: float) -> dict[str, object]:
    return {
        "id": id_caso,
        "slot": PROPOSTA["slot"],
        "meta": {"origem": "held-out"},
        "titular": {
            "aprovado": aprovado,
            "custo_usd": custo,
            "detalhe": {"imutavel": True},
        },
    }


def _agregados(
    taxa_titular: object = 0.0,
    taxa_candidato: object = 1.0,
    custo_titular: object = 2.0,
    custo_candidato: object = 1.0,
    *,
    incluir_casos: bool = True,
) -> dict[str, object]:
    evidencia: dict[str, object] = {
        "status": "sombra_concluida",
        "slot": PROPOSTA["slot"],
        "titular": {
            "modelo": PROPOSTA["titular"],
            "aprovados": 0,
            "total": 1,
            "taxa_aprovacao": taxa_titular,
            "custo_medio_usd": custo_titular,
        },
        "candidato": {
            "modelo": PROPOSTA["candidato"],
            "aprovados": 1,
            "total": 1,
            "taxa_aprovacao": taxa_candidato,
            "custo_medio_usd": custo_candidato,
        },
    }
    if incluir_casos:
        evidencia["casos"] = [
            {
                "id": "caso-agregado",
                "titular": {"aprovado": False, "custo_usd": custo_titular},
                "candidato": {"aprovado": True, "custo_usd": custo_candidato},
            }
        ]
    return evidencia


def test_sombra_isola_caso_do_runner_que_muta_e_lanca_excecao() -> None:
    casos = [_caso("caso-1", False, 2.0)]
    original = deepcopy(casos)

    def runner(caso: dict[str, object], _modelo: str) -> dict[str, object]:
        caso["meta"]["origem"] = "treino"  # type: ignore[index]
        caso["titular"]["aprovado"] = True  # type: ignore[index]
        raise RuntimeError("falha depois da mutacao")

    rodar_sombra(PROPOSTA, casos, runner)

    assert casos == original


def test_evidencia_de_sombra_nao_expoe_aliases_dos_casos() -> None:
    casos = [_caso("caso-1", False, 2.0)]
    original = deepcopy(casos)
    evidencia = rodar_sombra(
        PROPOSTA,
        casos,
        lambda caso, _modelo: {
            "aprovado": False,
            "custo_usd": 1.0,
            "detalhe": caso["meta"],
        },
    )

    evidencia["casos"][0]["titular"]["detalhe"]["imutavel"] = False
    evidencia["casos"][0]["candidato"]["detalhe"]["origem"] = "alterada"

    assert casos == original


def test_excecao_do_runner_vira_reprovacao_sem_abortar_sombra() -> None:
    eventos: list[str] = []

    def runner(_caso: dict[str, object], _modelo: str) -> dict[str, object]:
        raise RuntimeError("runner indisponivel")

    evidencia = rodar_sombra(
        PROPOSTA,
        [_caso("caso-1", True, 2.0)],
        runner,
        lambda nome, _dados: eventos.append(nome),
    )

    resultado = evidencia["casos"][0]["candidato"]
    assert evidencia["status"] == "sombra_concluida"
    assert (resultado["aprovado"], resultado["motivo"]) == (
        False,
        "RuntimeError: runner indisponivel",
    )
    assert certificar_sombra(evidencia)["status"] == "rejeitado"
    assert eventos == ["curador.sombra"]


def test_held_out_vazio_nao_pode_ser_marcado_como_sombra_concluida() -> None:
    evidencia = rodar_sombra(PROPOSTA, [], lambda _caso, _modelo: {})

    assert evidencia["status"] != "sombra_concluida"
    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_caso_de_treino_declarado_nao_pode_certificar_como_held_out() -> None:
    caso = _caso("caso-1", False, 2.0)
    caso["meta"]["origem"] = "treino"  # type: ignore[index]
    evidencia = rodar_sombra(
        PROPOSTA,
        [caso],
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": 1.0},
    )

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_aprovado_exige_bool_estrito_para_certificar() -> None:
    casos = [_caso("caso-1", False, 2.0)]
    evidencia = rodar_sombra(
        PROPOSTA,
        casos,
        lambda _caso, _modelo: {"aprovado": "false", "custo_usd": 1.0},
    )

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_custo_parcial_torna_comparacao_incomparavel() -> None:
    casos = [_caso("caso-1", True, 2.0), _caso("caso-2", False, 2.0)]

    def runner(caso: dict[str, object], _modelo: str) -> dict[str, object]:
        resultado: dict[str, object] = {"aprovado": True}
        if caso["id"] == "caso-1":
            resultado["custo_usd"] = 1.0
        return resultado

    evidencia = rodar_sombra(PROPOSTA, casos, runner)

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_custo_string_do_runner_vira_incomparavel_sem_crash() -> None:
    evidencia = rodar_sombra(
        PROPOSTA,
        [_caso("caso-1", False, 2.0)],
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": "1.0"},
    )

    assert evidencia["candidato"]["custo_medio_usd"] is None
    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_casos_held_out_duplicados_nao_podem_certificar() -> None:
    repetido = _caso("mesmo-id", False, 2.0)
    evidencia = rodar_sombra(
        PROPOSTA,
        [deepcopy(repetido), deepcopy(repetido)],
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": 1.0},
    )

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_agregados_sem_casos_nao_constituem_evidencia_certificavel() -> None:
    evidencia = _agregados(incluir_casos=False)

    assert "casos" not in evidencia
    assert certificar_sombra(evidencia)["status"] == "rejeitado"


@pytest.mark.parametrize(
    ("taxa_t", "taxa_c", "custo_t", "custo_c"),
    [
        (False, True, 2.0, 1.0),
        (0.0, 1.0, "2", "1"),
        (0.0, 1.0, True, False),
        (0.0, 1.0, 1.0, -1.0),
        (0.0, 1.0, inf, 1.0),
        (0.0, 1.0, 1.0, nan),
        (nan, 1.0, 2.0, 1.0),
        (0.0, 1.0, None, 1.0),
        (0.0, 1.0, 2.0, None),
        (-0.1, 1.1, 2.0, 1.0),
    ],
)
def test_certificacao_veta_tipos_e_dominios_numericos_invalidos(
    taxa_t: object,
    taxa_c: object,
    custo_t: object,
    custo_c: object,
) -> None:
    evidencia = _agregados(taxa_t, taxa_c, custo_t, custo_c)

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_promocao_nao_confia_apenas_no_status_certificado() -> None:
    eventos: list[str] = []
    intencao = preparar_promocao_gated(
        {"status": "certificado"},
        lambda nome, _dados: eventos.append(nome),
    )

    assert (intencao["status"], eventos) == ("promocao_vetada", [])


class _RepoCertificacoes:
    """Repositório autoritativo mínimo (ADR-003).

    A certificação não pode chegar "solta" do chamador: ela é resolvida por
    `certification_id` num repositório, copiada, e sua decisão é recomputada.
    """

    def __init__(self, registro: dict) -> None:
        self.registro = registro

    def obter(self, certification_id: str) -> dict | None:
        if self.registro["certification_id"] != certification_id:
            return None
        return self.registro


CHAVE = b"chave-de-teste-gpt5f-com-32-byte!!"


@pytest.fixture(autouse=True)
def _chave_no_ambiente(tmp_path_factory, monkeypatch):
    arquivo = tmp_path_factory.mktemp("chave-gpt5f") / "curador.key"
    arquivo.write_bytes(CHAVE)
    arquivo.chmod(0o600)
    monkeypatch.setenv("KORTEX_CURADOR_CHAVE", str(arquivo))


def test_promocao_valida_permanece_intencao_gateada_sem_evento_de_apply() -> None:
    """Promoção válida vira INTENÇÃO gateada — nunca aplicação automática.

    A auditoria passava a certificação direto como dict. O hardening removeu
    essa autoridade: dict/JSON não promovem nada (ver o teste acima, que segue
    vetando). O invariante auditado — promoção é intenção, nunca apply — é o
    que este teste prova, agora pelo caminho autoritativo.
    """
    # Fixtures locais: a proposta precisa de `politica.min_casos` e os casos de
    # `meta.split="held-out"` com proveniência — a guarda anti-Goodhart passou a
    # exigir que o conjunto seja comprovadamente held-out, não só declarado.
    proposta = {
        "slot": "executor/t1",
        "titular": "modelo-t",
        "candidato": "modelo-c",
        "politica": {"min_casos": PISO_CASOS},
    }
    casos = [
        {
            "id": str(indice),
            "slot": proposta["slot"],
            "meta": {"split": "held-out", "proveniencia": "suite-auditoria"},
        }
        for indice in range(PISO_CASOS)
    ]
    # Os dois lados rodam no runner: o titular deixou de ser declarado no caso.
    evidencia = rodar_sombra(
        proposta,
        casos,
        lambda _caso, modelo: {
            "aprovado": modelo == "modelo-c",
            "custo_usd": 1.0 if modelo == "modelo-c" else 2.0,
        },
        chave=CHAVE,
    )
    repositorio = _RepoCertificacoes({
        "certification_id": "cert-auditoria",
        "evidencia": evidencia,
        "decisao": certificar_sombra(evidencia, chave=CHAVE),
    })
    eventos: list[str] = []
    intencao = preparar_promocao_gated(
        "cert-auditoria",
        repositorio,
        lambda nome, _dados: eventos.append(nome),
    )

    assert (intencao["status"], intencao["requer_gate"]) == (
        "promocao_pendente",
        True,
    )
    assert eventos == ["curador.promocao_pendente"]
    assert "curador.promoveu" not in eventos


def test_eventos_emitidos_pelo_fluxo_curador_estao_no_schema_publico() -> None:
    eventos: list[str] = []

    def emitir(nome: str, _dados: object) -> None:
        eventos.append(nome)

    evidencia = rodar_sombra(
        PROPOSTA,
        [_caso("caso-1", False, 2.0)],
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": 1.0},
        emitir,
    )
    certificacao = certificar_sombra(evidencia, emitir)
    certificar_sombra(_agregados(1.0, 0.0, 1.0, 2.0), emitir)
    preparar_promocao_gated(certificacao, emitir)

    assert set(eventos) <= tipos()
