import pytest

from organizador.classificadores import ClassificadorPorExtensao
from organizador.plano import aplicar, desfazer, montar_plano


def test_aplicar_e_desfazer_volta_tudo(pasta):
    antes = sorted(p.relative_to(pasta) for p in pasta.rglob("*"))
    movimentos, ignorados = montar_plano(pasta, ClassificadorPorExtensao())
    assert len(movimentos) == 3 and not ignorados

    aplicar(pasta, movimentos)
    assert (pasta / "TXT" / "notas.txt").exists()
    assert (pasta / "Sem extensão" / "LEIAME").exists()
    assert (pasta / "Faculdade" / "antigo.txt").exists()  # subpastas não são tocadas

    voltaram, avisos = desfazer(pasta)
    assert voltaram == 3 and not avisos
    depois = sorted(
        p.relative_to(pasta) for p in pasta.rglob("*") if ".organizador" not in p.parts
    )
    assert depois == antes


def test_nunca_sobrescreve(pasta):
    (pasta / "TXT").mkdir()
    (pasta / "TXT" / "notas.txt").write_text("outro arquivo")
    movimentos, _ = montar_plano(pasta, ClassificadorPorExtensao())
    destino = next(m.destino for m in movimentos if m.origem.name == "notas.txt")
    assert destino.name == "notas (2).txt"


def test_desfazer_sem_historico(pasta):
    with pytest.raises(FileNotFoundError):
        desfazer(pasta)


def test_plano_nao_move_nada(pasta):
    montar_plano(pasta, ClassificadorPorExtensao())
    assert (pasta / "notas.txt").exists()
