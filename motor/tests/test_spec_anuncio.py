"""Testes da WorkflowSpec anuncio-3d.

Verifica que a spec carrega do arquivo JSON, valida com WorkflowSpec.model_validate
e faz roundtrip de serialização (model_dump → revalida → igual ao original).
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from motor.spec import WorkflowSpec

ANUNCIO_PATH = Path(__file__).parent.parent / "exemplos" / "anuncio-3d.json"


@pytest.fixture(scope="module")
def raw():
    return json.loads(ANUNCIO_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def spec(raw):
    return WorkflowSpec.model_validate(raw)


# --- carregamento e campos obrigatórios ---

def test_arquivo_existe():
    assert ANUNCIO_PATH.exists(), "exemplos/anuncio-3d.json não encontrado"


def test_carrega_e_valida(raw):
    spec = WorkflowSpec.model_validate(raw)
    assert spec.missao.id == "anuncio-3d"


def test_tres_subagentes(spec):
    assert len(spec.subagentes) == 3


def test_ids_esperados(spec):
    ids = {s.id for s in spec.subagentes}
    assert ids == {"redator", "pesquisador-mercado", "calculadora-custo"}


# --- padrão e versão ---

def test_padrao_fan_out_sintese(spec):
    assert spec.padrao == "fan_out_sintese"


def test_versao_suportada(spec):
    assert spec.versao == "0.1"


# --- subagentes sem depende_de (todos paralelos) ---

def test_todos_paralelos(spec):
    for s in spec.subagentes:
        assert s.depende_de == [], f"subagente '{s.id}' tem depende_de inesperado"


# --- rubrica do redator ---

def test_rubrica_redator_cobertura(spec):
    redator = next(s for s in spec.subagentes if s.id == "redator")
    texto = " ".join(redator.rubrica).lower()
    assert "60" in texto, "rubrica do redator deve mencionar limite de 60 caracteres"
    assert "proibid" in texto or "falsa" in texto, "rubrica do redator deve proibir promessas falsas"
    assert len(redator.rubrica) >= 3


# --- rubrica do pesquisador-mercado ---

def test_pesquisador_tem_websearch(spec):
    pesq = next(s for s in spec.subagentes if s.id == "pesquisador-mercado")
    assert pesq.ferramentas == "WebSearch"


def test_rubrica_pesquisador_faixa(spec):
    pesq = next(s for s in spec.subagentes if s.id == "pesquisador-mercado")
    texto = " ".join(pesq.rubrica).lower()
    assert "min" in texto or "mínimo" in texto, "rubrica deve exigir mínimo de faixa"
    assert "med" in texto or "median" in texto, "rubrica deve exigir mediano de faixa"
    assert "max" in texto or "máximo" in texto, "rubrica deve exigir máximo de faixa"
    assert "fonte" in texto, "rubrica deve exigir fonte citada"


# --- rubrica da calculadora ---

def test_rubrica_calculadora_premissas(spec):
    calc = next(s for s in spec.subagentes if s.id == "calculadora-custo")
    texto = " ".join(calc.rubrica).lower()
    assert "premissa" in texto, "rubrica da calculadora deve exigir premissas"
    assert len(calc.rubrica) >= 2


# --- gate margem-minima ---

def test_gate_presente(spec):
    assert len(spec.gates) == 1
    gate = spec.gates[0]
    assert gate.id == "margem-minima"


def test_gate_condicao_menciona_custo_e_margem(spec):
    gate = spec.gates[0]
    texto = gate.condicao.lower()
    assert "custo" in texto
    assert "1.3" in texto or "30%" in texto


def test_gate_opcoes_contem_tres_caminhos(spec):
    gate = spec.gates[0]
    opcoes = gate.opcoes.lower()
    # deve conter: um preço numérico, 'mercado', 'abortar'
    assert "mercado" in opcoes
    assert "abortar" in opcoes


# --- criterios de cobertura ---

def test_criterios_cobrem_tres_dimensoes(spec):
    assert len(spec.missao.criterios_cobertura) >= 3
    cobertura = " ".join(spec.missao.criterios_cobertura).lower()
    assert "texto" in cobertura or "conforme" in cobertura
    assert "faixa" in cobertura or "mercado" in cobertura
    assert "custo" in cobertura


# --- síntese ---

def test_sintese_formato_markdown(spec):
    assert spec.sintese.formato == "markdown"


def test_sintese_instrucao_menciona_premissas(spec):
    assert "premissa" in spec.sintese.instrucao.lower()


# --- roundtrip de serialização ---

def test_roundtrip(spec):
    dump = spec.model_dump()
    revalidado = WorkflowSpec.model_validate(dump)
    assert revalidado.model_dump() == dump, "roundtrip model_dump → model_validate falhou"
