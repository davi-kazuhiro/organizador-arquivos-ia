import json

import httpx
import pytest
from conftest import decisao

from organizador.classificador_ollama import ClassificadorOllama, schema_sem_refs
from organizador.classificadores import ErroProvedor, RespostaLote
from organizador.extracao import extrair, listar_arquivos


def _cliente(responder):
    pedidos = []

    def handler(request):
        pedidos.append(json.loads(request.content))
        return responder(request)

    return httpx.Client(transport=httpx.MockTransport(handler)), pedidos


def _ok(decisoes, done_reason="stop"):
    corpo = {"message": {"content": json.dumps({"decisoes": decisoes})}, "done_reason": done_reason}
    return lambda request: httpx.Response(200, json=corpo)


def test_schema_sem_refs():
    schema = schema_sem_refs(RespostaLote.model_json_schema())
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    assert schema["properties"]["decisoes"]["items"]["properties"]["confianca"]["enum"]


def test_classifica_e_monta_pedido(pasta):
    amostras = [extrair(p) for p in listar_arquivos(pasta)]
    cliente, pedidos = _cliente(_ok([decisao(0, "Fotos"), decisao(1, "Docs"), decisao(2, "Faculdade")]))
    decisoes = ClassificadorOllama(cliente=cliente).classificar(amostras, ["Faculdade"])

    assert {d.categoria for d in decisoes.values()} == {"Fotos", "Docs", "Faculdade"}
    pedido = pedidos[0]
    assert pedido["model"] == "gemma3:4b" and pedido["stream"] is False
    assert pedido["options"]["num_ctx"] >= 8192
    usuario = pedido["messages"][1]
    assert len(usuario["images"]) == 1
    assert "imagem anexada número 1" in usuario["content"]
    assert "Faculdade" in usuario["content"]


def test_ollama_desligado_vira_erro_amigavel(tmp_path):
    (tmp_path / "a.txt").write_text("x")

    def recusa(request):
        raise httpx.ConnectError("conexão recusada")

    cliente, _ = _cliente(recusa)
    with pytest.raises(ErroProvedor, match="Ollama"):
        ClassificadorOllama(cliente=cliente).classificar([extrair(tmp_path / "a.txt")])


def test_modelo_nao_baixado(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    cliente, _ = _cliente(lambda r: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(ErroProvedor, match="ollama pull gemma3:4b"):
        ClassificadorOllama(cliente=cliente).classificar([extrair(tmp_path / "a.txt")])


def test_resposta_cortada_e_ignorada(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    cliente, _ = _cliente(_ok([decisao(0, "A")], done_reason="length"))
    assert ClassificadorOllama(cliente=cliente).classificar([extrair(tmp_path / "a.txt")]) == {}
