from organizador.classificadores import ClassificadorPorExtensao
from organizador.extracao import extrair, listar_arquivos
from organizador.nomes import nome_seguro


def test_nome_seguro_bloqueia_caminhos_e_nomes_reservados():
    assert "/" not in nome_seguro("../../Windows/System32")
    assert "\\" not in nome_seguro("..\\..\\fora")
    assert nome_seguro("..") == "Outros"
    assert nome_seguro("   ") == "Outros"
    assert nome_seguro("CON") == "_CON"
    assert nome_seguro('Notas: "2026"?') == "Notas 2026"


def test_listar_ignora_subpastas_e_ocultos(pasta):
    (pasta / ".oculto").write_text("x")
    nomes = [p.name for p in listar_arquivos(pasta)]
    assert nomes == ["IMG_4821.png", "LEIAME", "notas.txt"]


def test_extrair_texto_imagem_e_arquivo_quebrado(pasta):
    assert "Grafos" in extrair(pasta / "notas.txt").texto
    imagem = extrair(pasta / "IMG_4821.png")
    assert imagem.tipo_imagem == "image/png" and imagem.imagem_base64
    quebrado = pasta / "quebrado.pdf"
    quebrado.write_bytes(b"isto nao e um pdf")
    amostra = extrair(quebrado)  # não pode levantar exceção
    assert amostra.texto is None


def test_extrair_respeita_limite(pasta):
    (pasta / "grande.txt").write_text("a" * 10_000)
    assert len(extrair(pasta / "grande.txt", limite_caracteres=500).texto) == 500


def test_por_extensao_trata_arquivo_sem_extensao(pasta):
    amostras = [extrair(p) for p in listar_arquivos(pasta)]
    categorias = {d.categoria for d in ClassificadorPorExtensao().classificar(amostras).values()}
    assert categorias == {"PNG", "TXT", "Sem extensão"}


def test_nome_generico():
    from organizador.nomes import nome_generico

    genericos = ["IMG_4821", "download (3)", "doc1", "final_v2_AGORA_VAI", "20261105_143022",
                 "WhatsApp Image 2026-10-01 at 10.22.31", "Sem título", "Currículo (1)"]
    bons = ["LEIAME", "receita", "Lista 2 Teoria dos Grafos", "main", "Relatório final",
            "notas fiscais 2026", "foto da formatura", "Imagens do projeto"]
    assert all(nome_generico(n) for n in genericos), [n for n in genericos if not nome_generico(n)]
    assert not any(nome_generico(n) for n in bons), [n for n in bons if nome_generico(n)]


def test_normalizar_categoria():
    from organizador.nomes import normalizar_categoria

    assert normalizar_categoria("finanças", []) == "Finanças"
    assert normalizar_categoria("FACULDADE", ["Faculdade"]) == "Faculdade"
    assert normalizar_categoria("../x", []) == "x".upper()


def test_arquivo_sem_extensao_e_lido_se_for_texto(pasta):
    assert "sem extensão" in extrair(pasta / "LEIAME").texto
    (pasta / "binario").write_bytes(b"\x00\x01\x02ELF")
    assert extrair(pasta / "binario").texto is None
