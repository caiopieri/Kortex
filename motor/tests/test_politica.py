"""Política de gates (Corte C): auto-mode global + override por gate."""
from motor.politica import PoliticaGates, politica_de_config


def test_default_tudo_manual():
    p = PoliticaGates()
    assert p.decisao_auto("cobertura") is None  # manual → interrupt


def test_auto_mode_resolve_com_default_do_gate():
    p = PoliticaGates(auto_mode=True)
    assert p.decisao_auto("cobertura", default="prosseguir") == "prosseguir"
    # Gate desconhecido falha fechado em modo manual.
    assert p.decisao_auto("desconhecido") is None


def test_override_manual_vence_auto_mode():
    p = PoliticaGates(auto_mode=True, overrides={"cobertura": "manual"})
    assert p.decisao_auto("cobertura") is None  # exceção: esse fica manual


def test_override_automatiza_so_um_gate_sem_auto_mode():
    p = PoliticaGates(auto_mode=False, overrides={"cobertura": "abortar"})
    assert p.decisao_auto("cobertura") == "abortar"   # automatizado
    assert p.decisao_auto("outro") is None            # os demais seguem manuais


def test_politica_de_config():
    p = politica_de_config({"auto_mode": True, "gates": {"cobertura": "manual"}})
    assert p.auto_mode is True and p.overrides == {"cobertura": "manual"}
    assert politica_de_config(None).auto_mode is False  # ausente → tudo manual
