from pathlib import Path

from qmmm_vqe_biosim.datasets.xyz import read_xyz


def test_read_xyz_basic(tmp_path: Path):
    p = tmp_path / "mol.xyz"
    p.write_text(
        "3\ncomment line\nH 0.0 0.0 0.0\nH 0.0 0.0 1.0\nO 0.0 0.0 2.0\n",
        encoding="utf-8",
    )
    atoms, coords, comment = read_xyz(p)
    assert atoms == ["H", "H", "O"]
    assert len(coords) == 3
    assert comment == "comment line"
