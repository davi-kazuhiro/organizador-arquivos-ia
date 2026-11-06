"""Transforma decisões em um plano de movimentos, aplica o plano e permite desfazer.

Nada é movido sem antes existir um plano visível. Toda execução grava um histórico em
``<pasta>/.organizador/`` para que ``organizador desfazer`` consiga voltar tudo.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .classificadores import Classificador
from .extracao import extrair, listar_arquivos
from .nomes import nome_seguro, normalizar_categoria

PASTA_HISTORICO = ".organizador"


@dataclass
class Movimento:
    origem: Path
    destino: Path
    categoria: str
    motivo: str
    confianca: str

    @property
    def renomeado(self) -> bool:
        return self.origem.name != self.destino.name


def _destino_livre(caminho: Path, reservados: set[str]) -> Path:
    """Nunca sobrescreve: acrescenta " (2)", " (3)"... até achar um nome livre."""
    candidato, n = caminho, 2
    while candidato.exists() or str(candidato).lower() in reservados:
        candidato = caminho.with_name(f"{caminho.stem} ({n}){caminho.suffix}")
        n += 1
    reservados.add(str(candidato).lower())
    return candidato


def categorias_existentes(pasta: Path) -> list[str]:
    return sorted(
        p.name for p in pasta.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def montar_plano(
    pasta: Path,
    classificador: Classificador,
    limite_caracteres: int = 2000,
    renomear: bool = True,
) -> tuple[list[Movimento], list[Path]]:
    """Retorna (movimentos, arquivos que ficaram de fora)."""
    arquivos = listar_arquivos(pasta)
    amostras = [extrair(a, limite_caracteres) for a in arquivos]
    existentes = categorias_existentes(pasta)
    decisoes = classificador.classificar(amostras, existentes)

    movimentos: list[Movimento] = []
    ignorados: list[Path] = []
    reservados: set[str] = set()
    for i, arquivo in enumerate(arquivos):
        decisao = decisoes.get(i)
        if decisao is None:
            ignorados.append(arquivo)
            continue
        categoria = normalizar_categoria(decisao.categoria, existentes)
        if categoria not in existentes:
            existentes.append(categoria)
        # Os modelos alternam entre "nome_assim" e "nome assim"; padronizamos com espaços.
        base = nome_seguro(decisao.novo_nome.replace("_", " "), padrao=arquivo.stem) if (
            renomear and decisao.novo_nome.strip()
        ) else arquivo.stem
        destino = _destino_livre(pasta / categoria / f"{base}{arquivo.suffix}", reservados)
        movimentos.append(
            Movimento(arquivo, destino, categoria, decisao.motivo, decisao.confianca)
        )
    return movimentos, ignorados


def aplicar(pasta: Path, movimentos: list[Movimento]) -> Path:
    """Move os arquivos e grava o histórico (mesmo se algo falhar no meio)."""
    pasta_hist = pasta / PASTA_HISTORICO
    pasta_hist.mkdir(exist_ok=True)
    historico = pasta_hist / f"historico-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    feitos: list[dict] = []
    try:
        for mov in movimentos:
            mov.destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(mov.origem), str(mov.destino))
            feitos.append({k: str(v) for k, v in asdict(mov).items()})
    finally:
        historico.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
    return historico


def desfazer(pasta: Path) -> tuple[int, list[str]]:
    """Desfaz a execução mais recente. Retorna (quantos voltaram, avisos)."""
    pasta_hist = pasta / PASTA_HISTORICO
    historicos = sorted(pasta_hist.glob("historico-*.json")) if pasta_hist.is_dir() else []
    if not historicos:
        raise FileNotFoundError("Nenhuma organização para desfazer nesta pasta.")
    ultimo = historicos[-1]
    feitos = json.loads(ultimo.read_text(encoding="utf-8"))

    voltaram, avisos = 0, []
    for mov in reversed(feitos):
        origem, destino = Path(mov["origem"]), Path(mov["destino"])
        if not destino.exists():
            avisos.append(f"{destino.name} não está mais em {destino.parent.name}/")
            continue
        if origem.exists():
            avisos.append(f"já existe outro {origem.name} no lugar original; mantive onde está")
            continue
        shutil.move(str(destino), str(origem))
        voltaram += 1
        try:
            destino.parent.rmdir()  # só apaga a pasta se ela ficou vazia
        except OSError:
            pass
    ultimo.rename(ultimo.with_suffix(".desfeito"))
    return voltaram, avisos
