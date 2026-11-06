"""Cria uma pasta "Downloads" bagunçada para testar o organizador.

    python exemplos/criar_pasta_demo.py demo
    organizador organizar demo
"""

import sys
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw

ARQUIVOS_TEXTO = {
    "download (3).txt": "Lista 2 - Teoria dos Grafos. Exercício 1: prove que toda árvore com n "
                        "vértices tem n-1 arestas. Exercício 2: implemente BFS.",
    "doc1.txt": "NOTA FISCAL DE SERVIÇO ELETRÔNICA\nPrestador: Provedor Internet LTDA\n"
                "Valor total: R$ 119,90\nCompetência: 10/2026",
    "anotacoes.md": "# Reunião do projeto Present\n- validar QR code da chamada\n"
                    "- deploy do backend até sexta",
    "receita.txt": "Bolo de cenoura: 3 cenouras, 4 ovos, 1 xícara de óleo, 2 de açúcar, "
                   "2 de farinha. Cobertura de chocolate.",
    "dados.csv": "data,descricao,valor\n2026-10-01,Mercado,-312.40\n2026-10-05,Salário,2500.00\n"
                 "2026-10-09,Uber,-23.10",
    "main.py": "import torch\nfrom torch import nn\n\nclass MLP(nn.Module):\n"
               "    def __init__(self):\n        super().__init__()\n"
               "        self.camadas = nn.Sequential(nn.Linear(784, 128), nn.ReLU(), "
               "nn.Linear(128, 10))\n",
    "LEIAME": "Arquivo sem extensão: instruções de instalação do driver da impressora.",
}


def criar(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in ARQUIVOS_TEXTO.items():
        (pasta / nome).write_text(conteudo, encoding="utf-8")

    curriculo = Document()
    curriculo.add_heading("Fulano de Tal", 0)
    curriculo.add_paragraph("Estudante de Ciência da Computação. Experiência: Python, React, SQL.")
    curriculo.save(pasta / "final_v2_AGORA_VAI.docx")

    imagem = Image.new("RGB", (400, 200), "white")
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle([20, 20, 380, 180], outline="black", width=3)
    desenho.text((40, 80), "Grafico de vendas Q3 - barras", fill="black")
    imagem.save(pasta / "IMG_4821.png")


if __name__ == "__main__":
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "demo")
    criar(destino)
    print(f"Pasta de demonstração criada em {destino.resolve()}")
