import pytest

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import solve_ground_state_energy
from qmmm_vqe_biosim.datasets.io import get_structure_record


def test_qiskit_nature_h2_smoke():
    record = get_structure_record(dataset="mor41", record_id="H2")
    energy = solve_ground_state_energy(record=record, basis="sto3g")
    assert energy == pytest.approx(-1.137, abs=1e-2)
