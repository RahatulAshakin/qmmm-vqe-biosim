from __future__ import annotations

import os

import pytest

from qmmm_vqe_biosim.analysis.benchmark import run_benchmark

pytestmark = pytest.mark.slow


@pytest.mark.skipif(
    os.getenv("RUN_SLOW") != "1",
    reason="Set RUN_SLOW=1 to run ADAPT-VQE CO active-space smoke test.",
)
def test_adapt_vqe_co_active_space_smoke() -> None:
    rows = run_benchmark(
        dataset="mor41",
        basis="sto3g",
        records=["CO"],
        method="adapt_vqe",
        active_electrons=4,
        active_orbitals=4,
        seed=7,
        maxiter=8,
        max_qubits=16,
        exact_max_qubits=12,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["dataset"] == "mor41"
    assert row["record"] == "CO"
    assert row["basis"] == "sto3g"
    assert row["algorithm"] == "adapt_vqe"
    assert row["active_electrons"] == 4
    assert row["active_orbitals"] == 4
    assert row["vqe_method"] == "run"
    assert row["vqe_ansatz"] in {"uccsd", "ucc"}
    assert isinstance(row["vqe_energy"], float)
