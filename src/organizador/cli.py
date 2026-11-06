"""Interface de linha de comando.

    organizador organizar ~/Downloads            # só mostra o plano (nada é movido)
    organizador organizar ~/Downloads --aplicar  # mostra, pede confirmação e move
    organizador desfazer ~/Downloads             # volta a última organização
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import __version__
from .classificador_ollama import MODELO_OLLAMA_PADRAO, ClassificadorOllama
from .classificadores import (
    MODELO_PADRAO,
    ClassificadorClaude,
    ClassificadorPorExtensao,
    ErroProvedor,
)
from .plano import aplicar, desfazer, montar_plano

console = Console()

_COR_CONFIANCA = {"alta": "green", "media": "yellow", "baixa": "red"}


def _pasta(valor: str) -> Path:
    caminho = Path(valor).expanduser().resolve()
    if not caminho.is_dir():
        raise argparse.ArgumentTypeError(f"pasta não encontrada: {valor}")
    return caminho


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organizador",
        description="Organiza uma pasta lendo o conteúdo dos arquivos com IA.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="comando", required=True)

    org = sub.add_parser("organizar", help="planeja (e opcionalmente aplica) a organização")
    org.add_argument("pasta", type=_pasta)
    org.add_argument("--aplicar", action="store_true", help="move os arquivos depois de confirmar")
    org.add_argument("-y", "--sim", action="store_true", help="não pede confirmação")
    org.add_argument(
        "-p", "--provedor", choices=["claude", "ollama", "extensao"], default="claude",
        help="claude (nuvem, pago), ollama (local, gratuito) ou extensao (sem IA)",
    )
    org.add_argument("--sem-ia", action="store_true", help="atalho para --provedor extensao")
    org.add_argument("--sem-renomear", action="store_true", help="mantém os nomes originais")
    org.add_argument(
        "--modelo",
        help=f"padrão: {MODELO_PADRAO} (claude) ou {MODELO_OLLAMA_PADRAO} (ollama)",
    )
    org.add_argument(
        "--lote", type=int,
        help="arquivos por chamada ao modelo (padrão: 10 no claude, 5 no ollama)",
    )
    org.add_argument(
        "--caracteres", type=int, default=2000,
        help="quantos caracteres de cada arquivo o modelo lê",
    )

    des = sub.add_parser("desfazer", help="desfaz a última organização da pasta")
    des.add_argument("pasta", type=_pasta)
    return parser


def _mostrar_plano(pasta: Path, movimentos, ignorados) -> None:
    tabela = Table(title=f"Plano para {pasta}", show_lines=False)
    tabela.add_column("Arquivo")
    tabela.add_column("Vai para")
    tabela.add_column("Confiança")
    tabela.add_column("Motivo", style="dim")
    for mov in movimentos:
        destino = f"{mov.categoria}/{mov.destino.name}"
        if mov.renomeado:
            destino += " [cyan](renomeado)[/cyan]"
        cor = _COR_CONFIANCA.get(mov.confianca, "white")
        tabela.add_row(mov.origem.name, destino, f"[{cor}]{mov.confianca}[/{cor}]", mov.motivo)
    console.print(tabela)

    resumo = Counter(m.categoria for m in movimentos)
    console.print(
        f"[bold]{len(movimentos)}[/bold] arquivo(s) em [bold]{len(resumo)}[/bold] pasta(s): "
        + ", ".join(f"{cat} ({n})" for cat, n in resumo.most_common())
    )
    if ignorados:
        console.print(f"[yellow]{len(ignorados)} arquivo(s) ficam onde estão (sem decisão).[/yellow]")


def _organizar(args) -> int:
    provedor = "extensao" if args.sem_ia else args.provedor
    opcoes = {k: v for k, v in {"modelo": args.modelo, "tamanho_lote": args.lote}.items() if v}
    if provedor == "extensao":
        classificador = ClassificadorPorExtensao()
    elif provedor == "ollama":
        classificador = ClassificadorOllama(**opcoes)
    else:
        classificador = ClassificadorClaude(**opcoes)

    inicio = time.perf_counter()
    with console.status("Lendo e classificando os arquivos..."):
        movimentos, ignorados = montar_plano(
            args.pasta, classificador, args.caracteres, renomear=not args.sem_renomear
        )
    duracao = time.perf_counter() - inicio

    if not movimentos and not ignorados:
        console.print("A pasta não tem arquivos para organizar.")
        return 0
    _mostrar_plano(args.pasta, movimentos, ignorados)
    console.print(f"[dim]Classificado em {duracao:.1f}s.[/dim]")

    if not args.aplicar:
        console.print("\nNada foi movido. Rode de novo com [bold]--aplicar[/bold] para executar.")
        return 0
    if not movimentos:
        return 0
    if not args.sim and console.input("\nAplicar este plano? [s/N] ").strip().lower() not in {"s", "sim"}:
        console.print("Cancelado. Nada foi movido.")
        return 0

    historico = aplicar(args.pasta, movimentos)
    console.print(
        f"[green]Pronto![/green] {len(movimentos)} arquivo(s) organizados. "
        f"Para desfazer: [bold]organizador desfazer \"{args.pasta}\"[/bold]"
    )
    logging.getLogger(__name__).debug("Histórico salvo em %s", historico)
    return 0


def _desfazer(args) -> int:
    try:
        voltaram, avisos = desfazer(args.pasta)
    except FileNotFoundError as erro:
        console.print(f"[yellow]{erro}[/yellow]")
        return 1
    for aviso in avisos:
        console.print(f"[yellow]Aviso:[/yellow] {aviso}")
    console.print(f"[green]{voltaram} arquivo(s) voltaram para o lugar original.[/green]")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False)],
    )
    args = _criar_parser().parse_args(argv)
    if args.comando == "desfazer":
        return _desfazer(args)

    import anthropic

    sem_chave = (
        "[red]Chave da API inválida ou ausente.[/red] Defina ANTHROPIC_API_KEY, "
        "ou use --provedor ollama (gratuito, local) ou --sem-ia."
    )
    try:
        return _organizar(args)
    except ErroProvedor as erro:
        console.print(f"[red]{erro}[/red]")
    except anthropic.AuthenticationError:
        console.print(sem_chave)
    except TypeError as erro:
        # A SDK levanta TypeError quando não encontra nenhuma credencial configurada.
        if "authentication" not in str(erro):
            raise
        console.print(sem_chave)
    except anthropic.RateLimitError:
        console.print("[red]Limite de requisições atingido.[/red] Tente de novo em instantes.")
    except anthropic.APIStatusError as erro:
        console.print(f"[red]Erro da API ({erro.status_code}):[/red] {erro.message}")
    except anthropic.APIConnectionError:
        console.print("[red]Sem conexão com a API.[/red] Verifique sua internet.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
