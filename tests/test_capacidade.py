from __future__ import annotations

from pathlib import Path

from motor.modelos import ClienteRoteador, ClienteStub
from motor.registro import cliente_de_registro


RAIZ = Path(__file__).parent.parent


class FakeLog:
    def __init__(self):
        self.eventos: list[tuple[str, dict]] = []

    def evento(self, tipo: str, **dados):
        self.eventos.append((tipo, dados))

    def tipos(self) -> list[str]:
        return [t for t, _ in self.eventos]


def _stub(resposta: str, provedor: str):
    cliente = ClienteStub(lambda papel, prompt: resposta)
    cliente.provedor = provedor
    return cliente


def _roteador(catalogo=None, **kw):
    padrao = _stub("CLAUDE", "claude")
    return ClienteRoteador(padrao=padrao, catalogo=catalogo or [], **kw)


def test_capacidade_escolhe_mais_barato_capaz():
    barato = _stub("A", "A")
    caro = _stub("B", "B")
    r = _roteador(catalogo=[
        (barato, frozenset({"x", "y"}), 1),
        (caro, frozenset({"x", "y"}), 5),
    ])

    assert r.provedor_de("p", capacidades=["x"]) == "A"


def test_capacidade_sem_cobertura_cai_no_padrao_e_emite_evento():
    barato = _stub("A", "A")
    log = FakeLog()
    r = _roteador(catalogo=[(barato, frozenset({"x"}), 1)], log=log)

    assert r.chamar("p", "prompt", capacidades=["x", "z"]) == "CLAUDE"
    assert "registro.sem_executor" in log.tipos()


def test_capacidade_respeita_independencia_do_juiz():
    barato = _stub("A", "A")
    caro = _stub("B", "B")
    r = _roteador(catalogo=[
        (barato, frozenset({"x"}), 1),
        (caro, frozenset({"x"}), 5),
    ])

    assert r.chamar("verifier", "p", evitar="A", capacidades=["x"]) == "B"
    assert len(barato.chamadas) == 0
    assert len(caro.chamadas) == 1


def test_capacidade_so_evitar_cai_no_padrao():
    barato = _stub("A", "A")
    r = _roteador(catalogo=[(barato, frozenset({"x"}), 1)])

    assert r.chamar("verifier", "p", evitar="A", capacidades=["x"]) == "CLAUDE"
    assert len(barato.chamadas) == 0


def test_capacidade_ignora_provedor_esgotado():
    barato = _stub("A", "A")
    caro = _stub("B", "B")
    r = _roteador(catalogo=[
        (barato, frozenset({"x"}), 1),
        (caro, frozenset({"x"}), 5),
    ], esgotados={"A"})

    assert r.provedor_de("p", capacidades=["x"]) == "B"


def test_tier_tem_precedencia_sobre_capacidade():
    por_tier = _stub("TIER", "tier")
    por_capacidade = _stub("CAP", "cap")
    log = FakeLog()
    r = _roteador(tiers={"simples": por_tier},
                  catalogo=[(por_capacidade, frozenset({"x"}), 1)],
                  log=log)

    assert r.chamar("p", "prompt", tier="simples", capacidades=["x"]) == "TIER"
    assert "modelo.roteado_tier" in log.tipos()
    assert "modelo.roteado_capacidade" not in log.tipos()
    assert len(por_capacidade.chamadas) == 0


def test_catalogo_vazio_e_capacidades_vazias_mantem_roteamento_antigo():
    por_papel = _stub("PAPEL", "papel")
    r = ClienteRoteador(padrao=_stub("CLAUDE", "claude"), mapa={"redator": por_papel})

    assert r.chamar("redator", "p") == "PAPEL"
    assert r.chamar("outro", "p", capacidades=["x"]) == "CLAUDE"


def test_fixtures_registry_selecionam_por_vocabulario(monkeypatch):
    r = cliente_de_registro(RAIZ / "exemplos/registro-modelos")

    assert r.provedor_de("x", capacidades=["codigo"]) == "oc"
    assert r.provedor_de("x", capacidades=["raciocinio-longo"]) == "codex"
    assert r.provedor_de("x", capacidades=["pesquisa", "redacao"]) == "codex"

    monkeypatch.setattr(r.padrao, "chamar", lambda *args, **kwargs: "CLAUDE")
    assert r.chamar("verifier", "p", evitar="codex",
                    capacidades=["raciocinio-longo"]) is not None
