from __future__ import annotations

from pathlib import Path

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import solve_ground_state_energy
from qmmm_vqe_biosim.qmmm.charges import load_mm_charges_csv


def test_load_mm_charges_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "charges.csv"
    csv_path.write_text("x,y,z,q\n1.0,0.0,0.0,0.5\n-1.0,0.0,0.0,-0.5\n", encoding="utf-8")

    coords, charges = load_mm_charges_csv(csv_path)
    assert coords == [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]
    assert charges == [0.5, -0.5]


def test_mm_embedded_energy_differs_from_unembedded(tmp_path: Path) -> None:
    record = {
        "atoms": ["H", "H"],
        "coords_angstrom": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.735]],
        "charge": 0,
        "multiplicity": 1,
    }
    charges_path = tmp_path / "mm_charges.csv"
    charges_path.write_text("x,y,z,q\n2.0,0.0,0.0,0.8\n", encoding="utf-8")

    e_plain = solve_ground_state_energy(record=record, basis="sto3g")
    e_embed = solve_ground_state_energy(
        record=record,
        basis="sto3g",
        mm_charges_path=charges_path,
    )

    assert abs(e_embed - e_plain) > 1e-6
