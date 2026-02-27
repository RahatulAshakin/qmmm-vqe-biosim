from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from qmmm_vqe_biosim.chem.active_space import choose_auto_active_space
from qmmm_vqe_biosim.datasets.io import get_structure_record


def test_auto_active_space_uno_cas_h2_deterministic(monkeypatch) -> None:
    record = get_structure_record(dataset="mor41", record_id="H2")
    problem = SimpleNamespace(num_particles=(1, 1), num_spatial_orbitals=2)

    monkeypatch.setattr(
        "qmmm_vqe_biosim.chem.active_space.natural_occupations_uhf",
        lambda record, basis: np.asarray([1.98, 0.02], dtype=float),
    )

    sel = choose_auto_active_space(
        problem=problem,
        record=record,
        basis="sto3g",
        max_qubits=8,
        method="uno_cas",
        max_orbitals=2,
    )

    assert sel.method == "uno_cas"
    assert sel.active_orbitals == [0, 1]
    assert sel.active_electrons == 2


def test_auto_active_space_occ_entropy_co_deterministic(monkeypatch) -> None:
    record = get_structure_record(dataset="mor41", record_id="CO")
    problem = SimpleNamespace(num_particles=(7, 7), num_spatial_orbitals=10)

    monkeypatch.setattr(
        "qmmm_vqe_biosim.chem.active_space.natural_occupations_uhf",
        lambda record, basis: np.asarray(
            [2.0, 1.6, 1.0, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=float
        ),
    )

    sel = choose_auto_active_space(
        problem=problem,
        record=record,
        basis="sto3g",
        max_qubits=8,
        method="occ_entropy",
        max_orbitals=3,
    )

    assert sel.method == "occ_entropy"
    assert sel.active_orbitals == [1, 2, 3]
    assert sel.active_electrons == 4
