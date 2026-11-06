"""Provedor local e gratuito: modelos rodando no próprio computador via Ollama.

Nenhum arquivo sai da máquina. Em troca, é mais lento e menos preciso que o Claude,
principalmente em hardware sem GPU dedicada.
"""

from __future__ import annotations

import copy
import logging
import os

import httpx

from .classificadores import (
    PROMPT_SISTEMA,
    ClassificadorLLM,
    ErroProvedor,
    RespostaLote,
    cabecalho_arquivo,
    instrucao_final,
    validar_resposta,
)

log = logging.getLogger(__name__)

MODELO_OLLAMA_PADRAO = "gemma3:4b"
URL_OLLAMA_PADRAO = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def schema_sem_refs(schema: dict) -> dict:
    """Troca os ``$ref`` do Pydantic pela definição em si.

    O Ollama converte o schema numa gramática; um schema "achatado" é o formato mais
    garantido de funcionar em qualquer versão.
    """
    schema = copy.deepcopy(schema)
    definicoes = schema.pop("$defs", {})

    def resolver(no):
        if isinstance(no, dict):
            if "$ref" in no:
                return resolver(definicoes[no["$ref"].split("/")[-1]])
            return {k: resolver(v) for k, v in no.items()}
        if isinstance(no, list):
            return [resolver(v) for v in no]
        return no

    return resolver(schema)


def _mensagem_do_lote(lote, ids, categorias) -> dict:
    """No Ollama as imagens vão numa lista à parte, então o texto diz a ordem delas."""
    partes: list[str] = []
    imagens: list[str] = []
    for id_, amostra in zip(ids, lote):
        cabecalho = cabecalho_arquivo(id_, amostra)
        if amostra.imagem_base64:
            imagens.append(amostra.imagem_base64)
            corpo = f"(é a imagem anexada número {len(imagens)})"
        elif amostra.texto:
            corpo = f"Trecho do conteúdo:\n{amostra.texto}"
        else:
            corpo = "(conteúdo não disponível, decida pelo nome)"
        partes.append(f"{cabecalho}\n{corpo}\n</arquivo>")
    partes.append(instrucao_final(categorias, len(ids)))
    mensagem = {"role": "user", "content": "\n\n".join(partes)}
    if imagens:
        mensagem["images"] = imagens
    return mensagem


class ClassificadorOllama(ClassificadorLLM):
    def __init__(
        self,
        modelo: str = MODELO_OLLAMA_PADRAO,
        tamanho_lote: int = 5,  # modelos pequenos erram mais com lotes grandes
        url: str = URL_OLLAMA_PADRAO,
        contexto: int = 16384,
        cliente: httpx.Client | None = None,
    ):
        self.modelo = modelo
        self.tamanho_lote = tamanho_lote
        self.url = url.rstrip("/")
        self.contexto = contexto
        # Em CPU um lote pode levar minutos; o timeout padrão do httpx (5s) não serve.
        self.cliente = cliente or httpx.Client(timeout=httpx.Timeout(600, connect=5))
        self._schema = schema_sem_refs(RespostaLote.model_json_schema())

    def _chamar_lote(self, lote, ids, categorias):
        corpo = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": PROMPT_SISTEMA},
                _mensagem_do_lote(lote, ids, categorias),
            ],
            "format": self._schema,
            "stream": False,
            # O padrão de contexto do Ollama é pequeno e cortaria o lote em silêncio.
            "options": {"temperature": 0, "num_ctx": self.contexto},
        }
        try:
            resposta = self.cliente.post(f"{self.url}/api/chat", json=corpo)
        except httpx.ConnectError as erro:
            raise ErroProvedor(
                f"Não encontrei o Ollama em {self.url}. Abra o aplicativo Ollama "
                "(ou rode `ollama serve`) e tente de novo."
            ) from erro
        except httpx.TimeoutException:
            log.warning("O Ollama demorou demais neste lote; tente um --lote menor.")
            return None

        if resposta.status_code == 404:
            raise ErroProvedor(
                f"O modelo {self.modelo} não está baixado. Rode: ollama pull {self.modelo}"
            )
        if resposta.status_code >= 400:
            raise ErroProvedor(f"Erro do Ollama ({resposta.status_code}): {resposta.text[:300]}")

        dados = resposta.json()
        if dados.get("done_reason") == "length":
            log.warning("Resposta cortada pelo limite de contexto; use um --lote menor.")
            return None
        return validar_resposta(dados.get("message", {}).get("content", ""))
