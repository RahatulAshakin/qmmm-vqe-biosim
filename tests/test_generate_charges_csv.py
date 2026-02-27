from __future__ import annotations

from pathlib import Path

import numpy as np

from qmmm_vqe_biosim.qmmm.charges import load_mm_charges_csv, write_mm_charges_csv
from qmmm_vqe_biosim.qmmm.generate_charges import generate_charge_coordinates


def test_generated_charges_csv_format(tmp_path: Path) -> None:
    coords = generate_charge_coordinates(
        pattern="line",
        center=np.asarray([0.0, 0.0, 0.0], dtype=float),
        radius=2.0,
        n=6,
    )
    out = tmp_path / "mm_charges.csv"
    write_mm_charges_csv(
        path=out,
        coords_angstrom=coords.tolist(),
        charges=[0.1] * len(coords),
    )

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "x,y,z,q"
    assert len(lines) == 7

    loaded_coords, loaded_charges = load_mm_charges_csv(out)
    assert len(loaded_coords) == 6
    assert loaded_charges == [0.1] * 6
