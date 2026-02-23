import json
import subprocess
import sys
from pathlib import Path


def test_benchmark_smoke(tmp_path: Path):
    out_dir = tmp_path / "benchmark_out"
    max_qubits = 8
    cmd = [
        sys.executable,
        "-m",
        "qmmm_vqe_biosim.analysis.benchmark",
        "--dataset",
        "mor41",
        "--basis",
        "sto3g",
        "--records",
        "CO2",
        "--dry-run",
        "--auto-active-space",
        "--max-qubits",
        str(max_qubits),
        "--maxiter",
        "5",
        "--seed",
        "7",
        "--out",
        str(out_dir),
        "--force",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert "qubits" in proc.stdout.lower()

    out_path = out_dir / "CO2.json"
    assert out_path.exists()
    row = json.loads(out_path.read_text(encoding="utf-8"))

    required = {
        "dataset",
        "record",
        "basis",
        "full_num_qubits",
        "num_qubits",
        "exact_energy",
        "vqe_energy",
        "runtime_sec",
        "seed",
        "active_electrons",
        "active_orbitals",
        "auto_active_space_applied",
        "skipped_reason",
    }
    assert required.issubset(row.keys())
    assert row["dataset"] == "mor41"
    assert row["record"] == "CO2"
    assert row["basis"] == "sto3g"
    assert isinstance(row["num_qubits"], int)
    assert row["num_qubits"] > 0
    assert row["full_num_qubits"] > max_qubits
    assert row["num_qubits"] <= max_qubits
    assert row["auto_active_space_applied"] is True
    assert row["active_electrons"] is not None
    assert row["active_orbitals"] is not None
    assert row["skipped_reason"] == "dry_run"
