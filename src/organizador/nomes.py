"""Higienização de nomes de pasta/arquivo.

A categoria e o novo nome vêm de um LLM, então são tratados como entrada não confiável:
nada de separadores de caminho, "..", caracteres proibidos no Windows ou nomes reservados.
"""

from __future__ import annotations

import re
import unicodedata

_PROIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVADOS = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
TAMANHO_MAXIMO = 80


_NOME_GENERICO = re.compile(
    r"""^(
        (img|dsc|dscn|pxl|photo|foto|screenshot|captura\ de\ tela|scan)[\s_-]*\d[\d_\-\s.]*
      | whatsapp\ (image|video|imagem)\ .*
      | (download|downloads|arquivo|documento|doc|document|untitled|sem\ t[ií]tulo|novo|new|file)
        [\s_-]*(\(\d+\)|\d+)?
      | [\d_\-\s]+
    )$""",
    re.IGNORECASE | re.VERBOSE,
)
_VERSAO_SOLTA = re.compile(
    r"(^|[\s_-])(v\d+|agora[\s_-]*vai|c[oó]pia|copy)($|[\s_-])", re.IGNORECASE
)
_SUFIXO_NUMERADO = re.compile(r"\s\(\d+\)$")


def nome_generico(stem: str) -> bool:
    """Regra fixa (sem IA) para nomes que não dizem nada sobre o conteúdo."""
    stem = stem.strip()
    return bool(
        _NOME_GENERICO.match(stem) or _VERSAO_SOLTA.search(stem) or _SUFIXO_NUMERADO.search(stem)
    )


def normalizar_categoria(categoria: str, existentes: list[str]) -> str:
    """Nome de pasta seguro, com inicial maiúscula, reaproveitando uma pasta existente
    quando a única diferença é maiúscula/minúscula (no Windows elas seriam a mesma pasta)."""
    categoria = nome_seguro(categoria.replace("_", " "))
    for existente in existentes:
        if existente.casefold() == categoria.casefold():
            return existente
    return categoria[0].upper() + categoria[1:]


def nome_seguro(texto: str, padrao: str = "Outros") -> str:
    """Converte um texto qualquer em um único segmento de caminho válido."""
    texto = unicodedata.normalize("NFC", texto or "")
    texto = _PROIBIDOS.sub(" ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .")
    texto = texto[:TAMANHO_MAXIMO].strip(" .")
    if not texto or set(texto) <= {"."}:
        return padrao
    if texto.upper().split(".")[0] in _RESERVADOS:
        texto = f"_{texto}"
    return texto
