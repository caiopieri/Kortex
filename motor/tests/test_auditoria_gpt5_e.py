import json
from pathlib import Path
from typing import cast

import pytest

import motor.eventos as eventos_mod
from motor.eventos import LogEventos
from motor.eventos_schema import valido


def _eventos(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(linha) for linha in path.read_text(encoding="utf-8").splitlines()
    ]


def test_valido_rejeita_payload_obrigatorio_ausente() -> None:
    evento = {"t": 0.0, "evento": "executor.respondeu"}

    assert valido(evento) is False


def test_valido_rejeita_campo_nao_declarado() -> None:
    evento = {
        "t": 0.0,
        "evento": "executor.respondeu",
        "executor": "executor-a",
        "tentativa": 1,
        "intruso": "nao pertence ao contrato",
    }

    assert valido(evento) is False


def test_valido_rejeita_tipos_invalidos() -> None:
    evento = {
        "t": "agora",
        "evento": "executor.respondeu",
        "executor": ["executor-a"],
        "tentativa": "primeira",
    }

    assert valido(evento) is False


def test_log_rejeita_tipo_fora_do_schema(tmp_path: Path) -> None:
    log = LogEventos(tmp_path / "eventos.jsonl")
    try:
        with pytest.raises((TypeError, ValueError)):
            log.evento("tipo.nao.declarado")
    finally:
        log.fechar()


@pytest.mark.parametrize(
    ("reservado", "valor"),
    [("evento", "tipo.forjado"), ("t", -999.0)],
)
def test_log_rejeita_payload_que_colide_com_envelope(
    tmp_path: Path,
    reservado: str,
    valor: object,
) -> None:
    log = LogEventos(tmp_path / "eventos.jsonl")
    dados = {"executor": "executor-a", "tentativa": 1, reservado: valor}
    try:
        with pytest.raises((TypeError, ValueError)):
            log.evento("executor.respondeu", **dados)
    finally:
        log.fechar()


def test_log_nao_apaga_historico_por_padrao(tmp_path: Path) -> None:
    """Reabrir anexa e nunca trunca — o invariante que a auditoria exigia."""
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="anterior")
    primeiro.fechar()

    log = LogEventos(path)
    log.evento("tarefa.concluida", missao="atual")
    log.fechar()

    registrados = _eventos(path)
    assert [e["missao"] for e in registrados] == ["anterior", "atual"]
    assert [e["seq"] for e in registrados] == [1, 2]


def test_log_v1_sem_seq_e_recusado_em_vez_de_sobrescrito(tmp_path: Path) -> None:
    """Log v1 (sem `seq`) é somente leitura — recusa explícita, não truncamento.

    A auditoria escreveu um log no formato antigo e esperou que ele fosse
    preservado ao reabrir. O hardening do formato v2 escolheu recusar a
    abertura para escrita: sem `seq` não há como garantir contiguidade nem
    detectar tail parcial, e escrever por cima seria pior que falhar. O
    invariante "não apaga histórico" é honrado da forma mais forte possível —
    o arquivo não é tocado.
    """
    path = tmp_path / "eventos.jsonl"
    anterior = {"t": 1.0, "evento": "tarefa.concluida", "missao": "anterior"}
    bruto = json.dumps(anterior) + "\n"
    path.write_text(bruto, encoding="utf-8")

    with pytest.raises(ValueError, match="somente leitura"):
        LogEventos(path)

    assert path.read_text(encoding="utf-8") == bruto, "o log v1 tem que ficar intacto"


def test_log_nao_persiste_constantes_fora_do_json_estrito(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    try:
        log.evento(
            "modelo.uso",
            papel="executor",
            provedor="teste",
            modelo="teste",
            prompt_tokens=float("nan"),
            completion_tokens=0,
            total_tokens=0,
        )
    except (TypeError, ValueError):
        pass
    finally:
        log.fechar()

    for linha in path.read_text(encoding="utf-8").splitlines():
        json.loads(
            linha,
            parse_constant=lambda valor: pytest.fail(
                f"constante JSON invalida: {valor}"
            ),
        )


def test_tempo_relativo_nao_regride_com_relogio_de_parede(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relogio = iter([100.0, 101.0, 99.0])
    monkeypatch.setattr(eventos_mod.time, "time", lambda: next(relogio))
    path = tmp_path / "eventos.jsonl"

    log = LogEventos(path)
    log.evento("tarefa.concluida", missao="primeira")
    log.evento("tarefa.concluida", missao="segunda")
    log.fechar()

    tempos = [cast(float, evento["t"]) for evento in _eventos(path)]
    assert tempos == sorted(tempos)
    assert all(isinstance(t, (int, float)) and t >= 0 for t in tempos)


def test_append_preserva_ordem_temporal_apos_reabertura(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relogio = iter([100.0, 110.0, 200.0, 201.0])
    monkeypatch.setattr(eventos_mod.time, "time", lambda: next(relogio))
    path = tmp_path / "eventos.jsonl"

    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="primeira")
    primeiro.fechar()
    segundo = LogEventos(path, truncar=False)
    segundo.evento("tarefa.concluida", missao="segunda")
    segundo.fechar()

    tempos = [cast(float, evento["t"]) for evento in _eventos(path)]
    assert tempos == sorted(tempos)
