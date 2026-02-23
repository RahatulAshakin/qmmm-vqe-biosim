import pytest

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import solve_ground_state_energy
from qmmm_vqe_biosim.datasets.io import get_structure_record
from qmmm_vqe_biosim.quantum.vqe_ground_state import run_vqe_ground_state


def test_adapt_vqe_h2_smoke():
    record = get_structure_record(dataset="mor41", record_id="H2")
    reference = solve_ground_state_energy(record=record, basis="sto3g")

    out = run_vqe_ground_state(
        dataset="mor41",
        record="H2",
        basis="sto3g",
        method="adapt_vqe",
        mapper="parity",
        optimizer="slsqp",
        maxiter=20,
        seed=7,
    )

    assert out["method"] == "adapt_vqe"
    assert out["algorithm"] == "adapt_vqe"
    assert out["energy"] == pytest.approx(reference, abs=1e-6)
