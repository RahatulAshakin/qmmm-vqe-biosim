from __future__ import annotations

import json
from pathlib import Path

from qmmm_vqe_biosim.analysis.summarize import load_results, write_summary_csv, write_summary_json


def test_summarize_writes_csv_and_json(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir(parents=True)

    (in_dir / "H2.json").write_text(
        json.dumps(
            {
                "dataset": "mor41",
                "basis": "sto3g",
                "record": "H2",
                "num_qubits": 2,
                "exact_energy": -1.0,
                "vqe_energy": -0.99,
                "error": 0.01,
                "skipped_reason": None,
            }
        ),
        encoding="utf-8",
    )
    (in_dir / "CO.json").write_text(
        json.dumps(
            {
                "dataset": "mor41",
                "basis": "sto3g",
                "record": "CO",
                "num_qubits": 6,
                "exact_energy": None,
                "vqe_energy": None,
                "error": None,
                "skipped_reason": "num_qubits>max_qubits",
            }
        ),
        encoding="utf-8",
    )

    rows = load_results(in_dir)
    assert len(rows) == 2

    out_csv = tmp_path / "summary.csv"
    out_json = tmp_path / "summary.json"

    write_summary_csv(rows, out_csv)
    write_summary_json(rows, out_json)

    assert out_csv.exists()
    assert out_json.exists()

    csv_text = out_csv.read_text(encoding="utf-8")
    assert "record" in csv_text
    assert "H2" in csv_text
    assert "CO" in csv_text

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert {r["record"] for r in payload} == {"H2", "CO"}
