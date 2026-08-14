import ast
from pathlib import Path

from motor.eventos_schema import SCHEMA_VERSAO, categoria_de, tipos, valido


RAIZ_MOTOR = Path(__file__).resolve().parents[1] / "motor"


def _analise_tipos_emitidos(fonte: str) -> tuple[set[str], set[int]]:
    tree = ast.parse(fonte)
    pais = {
        filho: pai
        for pai in ast.walk(tree)
        for filho in ast.iter_child_nodes(pai)
    }
    atribuicoes: dict[ast.AST, dict[str, list[ast.AST]]] = {}

    def escopo(node: ast.AST) -> ast.AST:
        atual = pais.get(node)
        while atual is not None and not isinstance(
            atual, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            atual = pais.get(atual)
        return atual or tree

    for node in ast.walk(tree):
        nome: str | None = None
        valor: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            alvo = node.targets[0]
            if isinstance(alvo, ast.Name):
                nome, valor = alvo.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nome, valor = node.target.id, node.value
        if nome is not None and valor is not None:
            atribuicoes.setdefault(escopo(node), {}).setdefault(nome, []).append(valor)

    def resolver(expr: ast.AST, no_chamada: ast.Call) -> set[str] | None:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return {expr.value}
        if isinstance(expr, ast.Name):
            escopo_atual = escopo(no_chamada)
            candidatas = [
                valor
                for valor in atribuicoes.get(escopo_atual, {}).get(expr.id, [])
                if valor.lineno < no_chamada.lineno
            ]
            if escopo_atual is not tree and not candidatas:
                candidatas = atribuicoes.get(tree, {}).get(expr.id, [])
            if not candidatas:
                return None
            resolvidas: set[str] = set()
            for candidata in candidatas:
                valores = resolver(candidata, no_chamada)
                if valores is None:
                    return None
                resolvidas |= valores
            return resolvidas
        if isinstance(expr, ast.IfExp):
            corpo = resolver(expr.body, no_chamada)
            alternativa = resolver(expr.orelse, no_chamada)
            if corpo is None or alternativa is None:
                return None
            return corpo | alternativa
        if isinstance(expr, ast.JoinedStr):
            partes = {""}
            for parte in expr.values:
                if isinstance(parte, ast.Constant) and isinstance(parte.value, str):
                    valores = {parte.value}
                elif isinstance(parte, ast.FormattedValue):
                    valores = resolver(parte.value, no_chamada)
                else:
                    return None
                if valores is None:
                    return None
                partes = {prefixo + valor for prefixo in partes for valor in valores}
            return partes
        return None

    emitidos: set[str] = set()
    nao_resolvidos: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        eh_log_evento = isinstance(func, ast.Attribute) and func.attr == "evento"
        eh_wrapper_evento = (
            isinstance(func, ast.Name) and func.id == "_evento"
        ) or (
            isinstance(func, ast.Attribute) and func.attr == "_evento"
        )
        if not (eh_log_evento or eh_wrapper_evento):
            continue

        tipo = node.args[0]
        escopo_atual = escopo(node)
        if (
            eh_log_evento
            and isinstance(escopo_atual, (ast.FunctionDef, ast.AsyncFunctionDef))
            and escopo_atual.name == "_evento"
            and isinstance(tipo, ast.Name)
            and any(argumento.arg == tipo.id for argumento in escopo_atual.args.args)
        ):
            continue

        valores = resolver(tipo, node)
        if valores is None:
            nao_resolvidos.add(node.lineno)
        else:
            emitidos |= valores
    return emitidos, nao_resolvidos


def _tipos_emitidos_em_codigo(fonte: str) -> set[str]:
    return _analise_tipos_emitidos(fonte)[0]


def _tipos_emitidos() -> tuple[set[str], set[tuple[str, int]]]:
    encontrados: set[str] = set()
    nao_resolvidos: set[tuple[str, int]] = set()
    for path in RAIZ_MOTOR.glob("*.py"):
        emitidos, pendentes = _analise_tipos_emitidos(path.read_text(encoding="utf-8"))
        encontrados |= emitidos
        nao_resolvidos |= {(path.name, linha) for linha in pendentes}
    return encontrados, nao_resolvidos


def test_schema_tem_versao_e_helpers():
    assert SCHEMA_VERSAO == 2
    assert "executor.chamado" in tipos()
    assert valido({"evento": "executor.chamado", "t": 0.0, "seq": 1, "executor": "e", "tentativa": 1})
    assert not valido({"evento": "evento.inexistente"})
    assert categoria_de("aresta.fluxo") == "fluxo"


def test_schema_cobre_todos_eventos_emitidos_no_codigo():
    emitidos, nao_resolvidos = _tipos_emitidos()
    assert len(emitidos) == 56
    assert nao_resolvidos == set()
    assert emitidos - tipos() == set()


def test_guarda_anti_drift_falharia_com_evento_nao_declarado():
    fonte = """
class Log:
    def evento(self, tipo, **dados):
        pass

def f(log):
    log.evento("evento.novo", campo=1)
"""
    assert _tipos_emitidos_em_codigo(fonte) - tipos() == {"evento.novo"}


def test_guarda_anti_drift_resolve_wrapper_constante_e_dominios_finitos():
    fonte = '''
TIPO = "evento.novo"

class Emissor:
    def _evento(self, tipo, **dados):
        self.log.evento(tipo, **dados)

    def emitir(self, pin):
        self._evento("evento.literal")
        tipo = "evento.pin" if pin else "evento.tier"
        self._evento(tipo)
        self._evento(f"evento.{'derivado'}")
        self._evento(TIPO)
'''
    emitidos, nao_resolvidos = _analise_tipos_emitidos(fonte)

    assert emitidos == {
        "evento.derivado",
        "evento.literal",
        "evento.novo",
        "evento.pin",
        "evento.tier",
    }
    assert nao_resolvidos == set()


def test_guarda_anti_drift_falha_fechado_em_tipo_sem_dominio_finito():
    fonte = '''
def emitir(log, tipo):
    log.evento(tipo)
'''
    emitidos, nao_resolvidos = _analise_tipos_emitidos(fonte)

    assert emitidos == set()
    assert nao_resolvidos == {3}
