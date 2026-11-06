import json
from types import SimpleNamespace

import pytest


class ClienteFalso:
    """Imita ``anthropic.Anthropic`` para testar sem rede e sem custo."""

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas.append(kwargs)
        resposta = self._respostas.pop(0)
        return resposta(kwargs) if callable(resposta) else resposta


def resposta_texto(dados, stop_reason="end_turn", antes=()):
    texto = dados if isinstance(dados, str) else json.dumps(dados)
    conteudo = [*antes, SimpleNamespace(type="text", text=texto)]
    return SimpleNamespace(stop_reason=stop_reason, content=conteudo)


def decisao(id_, categoria, novo_nome="", confianca="alta"):
    return {
        "id": id_, "categoria": categoria, "novo_nome": novo_nome,
        "motivo": "teste", "confianca": confianca,
    }


@pytest.fixture
def pasta(tmp_path):
    (tmp_path / "notas.txt").write_text("Lista de exercícios de Grafos - PUCPR", encoding="utf-8")
    (tmp_path / "IMG_4821.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    (tmp_path / "LEIAME").write_text("arquivo sem extensão", encoding="utf-8")
    (tmp_path / "Faculdade").mkdir()
    (tmp_path / "Faculdade" / "antigo.txt").write_text("já estava aqui", encoding="utf-8")
    return tmp_path
