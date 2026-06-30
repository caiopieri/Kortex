import ast
from pathlib import Path

from motor.eventos_schema import ESQUEMA, SCHEMA_VERSAO, categoria_de, tipos, valido


RAIZ_MOTOR = Path(__file__).resolve().parents[1] / "motor"


def _tipos_emitidos_em_codigo(fonte: str) -> set[str]:
    tree = ast.parse(fonte)
    emitidos: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        eh_log_evento = isinstance(func, ast.Attribute) and func.attr == "evento"
        eh_wrapper_evento = isinstance(func, ast.Name) and func.id == "_evento"
        if not (eh_log_evento or eh_wrapper_evento):
            continue
        tipo = node.args[0]
        if isinstance(tipo, ast.Constant) and isinstance(tipo.value, str):
            emitidos.add(tipo.value)
    return emitidos


def _tipos_emitidos() -> set[str]:
    encontrados: set[str] = set()
    for path in RAIZ_MOTOR.glob("*.py"):
        encontrados |= _tipos_emitidos_em_codigo(path.read_text(encoding="utf-8"))
    return encontrados


def test_schema_tem_versao_e_helpers():
    assert SCHEMA_VERSAO == 1
    assert "executor.chamado" in tipos()
    assert valido({"evento": "executor.chamado"})
    assert not valido({"evento": "evento.inexistente"})
    assert categoria_de("aresta.fluxo") == "fluxo"


def test_schema_cobre_todos_eventos_emitidos_no_codigo():
    assert _tipos_emitidos() - tipos() == set()


def test_guarda_anti_drift_falharia_com_evento_nao_declarado():
    fonte = """
class Log:
    def evento(self, tipo, **dados):
        pass

def f(log):
    log.evento("evento.novo", campo=1)
"""
    assert _tipos_emitidos_em_codigo(fonte) - tipos() == {"evento.novo"}
