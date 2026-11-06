from organizador.cli import main


def test_sem_aplicar_nao_move(pasta):
    assert main(["organizar", str(pasta), "--sem-ia"]) == 0
    assert (pasta / "notas.txt").exists()


def test_aplicar_e_desfazer_pela_cli(pasta):
    assert main(["organizar", str(pasta), "--sem-ia", "--aplicar", "--sim"]) == 0
    assert (pasta / "TXT" / "notas.txt").exists()
    assert main(["desfazer", str(pasta)]) == 0
    assert (pasta / "notas.txt").exists()
