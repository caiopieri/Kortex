import pytest

from motor.orcamento import ErroOrcamento
from motor.studio import make_graph


def test_studio_falha_antes_de_compor_cliente_ou_sink_noop() -> None:
    with pytest.raises(ErroOrcamento, match="sink monetario duravel"):
        make_graph()
