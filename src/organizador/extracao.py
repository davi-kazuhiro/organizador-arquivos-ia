"""Extrai uma amostra representativa de cada arquivo para o modelo classificar.

Para manter custo e latência baixos, mandamos só um trecho do conteúdo (configurável),
nunca o arquivo inteiro. Imagens vão como imagem, porque o Claude enxerga imagens.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

from .nomes import nome_generico

log = logging.getLogger(__name__)

EXTENSOES_TEXTO = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".html", ".htm",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rb", ".php",
    ".sql", ".ipynb", ".log", ".ini", ".toml", ".tex", ".rtf",
}
TIPOS_IMAGEM = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
LIMITE_IMAGEM_BYTES = 3_500_000  # abaixo do limite da API mesmo depois do base64
PAGINAS_PDF = 3


@dataclass
class Amostra:
    """O que o modelo vai ver sobre um arquivo."""

    caminho: Path
    tamanho: int
    texto: str | None = None
    imagem_base64: str | None = None
    tipo_imagem: str | None = None
    nome_generico: bool = False  # detectado por regra fixa; o modelo deve sugerir outro nome

    @property
    def nome(self) -> str:
        return self.caminho.name


def _ler_texto(caminho: Path, limite: int) -> str:
    with caminho.open("r", encoding="utf-8", errors="replace") as f:
        return f.read(limite)


def _parece_texto(caminho: Path) -> bool:
    """Para arquivos sem extensão (LEIAME, Makefile...): texto não tem bytes nulos."""
    with caminho.open("rb") as f:
        return b"\x00" not in f.read(4096)


def _ler_pdf(caminho: Path, limite: int) -> str:
    from pypdf import PdfReader

    leitor = PdfReader(caminho)
    partes: list[str] = []
    for pagina in leitor.pages[:PAGINAS_PDF]:
        partes.append(pagina.extract_text() or "")
        if sum(map(len, partes)) >= limite:
            break
    return "\n".join(partes)[:limite]


def _ler_docx(caminho: Path, limite: int) -> str:
    import docx

    documento = docx.Document(str(caminho))
    texto = "\n".join(p.text for p in documento.paragraphs if p.text.strip())
    return texto[:limite]


def extrair(caminho: Path, limite_caracteres: int = 2000) -> Amostra:
    """Lê um trecho do arquivo. Nunca levanta exceção: na pior hipótese, só o nome vai."""
    amostra = Amostra(
        caminho=caminho,
        tamanho=caminho.stat().st_size,
        nome_generico=nome_generico(caminho.stem),
    )
    extensao = caminho.suffix.lower()
    try:
        if extensao in TIPOS_IMAGEM and amostra.tamanho <= LIMITE_IMAGEM_BYTES:
            amostra.imagem_base64 = base64.standard_b64encode(caminho.read_bytes()).decode()
            amostra.tipo_imagem = TIPOS_IMAGEM[extensao]
        elif extensao == ".pdf":
            amostra.texto = _ler_pdf(caminho, limite_caracteres)
        elif extensao == ".docx":
            amostra.texto = _ler_docx(caminho, limite_caracteres)
        elif extensao in EXTENSOES_TEXTO or (not extensao and _parece_texto(caminho)):
            amostra.texto = _ler_texto(caminho, limite_caracteres)
    except Exception as erro:  # noqa: BLE001 - corrompido, com senha etc.: nunca derruba o plano
        log.warning("Não consegui ler %s (%s); vou classificar só pelo nome.", caminho.name, erro)
    if amostra.texto is not None and not amostra.texto.strip():
        amostra.texto = None
    return amostra


def listar_arquivos(pasta: Path) -> list[Path]:
    """Arquivos do primeiro nível da pasta, ignorando ocultos e a pasta de histórico."""
    return sorted(
        p for p in pasta.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )
