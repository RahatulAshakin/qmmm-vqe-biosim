import pytest

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import solve_ground_state_energy
from qmmm_vqe_biosim.datasets.io import get_structure_record
from qmmm_vqe_biosim.quantum.vqe_ground_state import run_vqe_ground_state


def test_vqe_h2_smoke():
    record = get_structure_record(dataset="mor41", record_id="H2")
    reference = solve_ground_state_energy(record=record, basis="sto3g")

    out = run_vqe_ground_state(
        dataset="mor41",
        record="H2",
        basis="sto3g",
        mapper="parity",
        optimizer="slsqp",
        maxiter=30,
        seed=7,
    )

    assert out["method"] == "vqe"
    assert out["dataset"] == "mor41"
    assert out["record"] == "H2"
    assert out["basis"] == "sto3g"
    assert out["energy"] == pytest.approx(reference, abs=1e-3)
