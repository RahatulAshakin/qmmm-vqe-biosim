from __future__ import annotations

import json
from pathlib import Path

from qmmm_vqe_biosim.analysis.sweep import (
    load_records_jsonl,
    parse_records_args,
    select_structure_records,
)


def _write_fake_structures(path: Path) -> None:
    records = [
        {"record_id": "A", "atoms": ["H"]},
        {"record_id": "B", "atoms": ["C", "H"]},
        {"record_id": "C", "atoms": ["C", "O", "O"]},
        {"record_id": "D", "atoms": ["C", "H", "H", "H"]},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def test_selection_smallest_n_with_max_atoms(tmp_path: Path) -> None:
    p = tmp_path / "structures.jsonl"
    _write_fake_structures(p)
    rows = load_records_jsonl(p)

    selected = select_structure_records(rows, smallest_n=2, max_atoms=3)
    assert [r["record_id"] for r in selected] == ["A", "B"]


def test_selection_explicit_records_comma_parse(tmp_path: Path) -> None:
    p = tmp_path / "structures.jsonl"
    _write_fake_structures(p)
    rows = load_records_jsonl(p)

    recs = parse_records_args(["D,B", "B"])
    selected = select_structure_records(rows, selected_record_ids=recs)
    assert [r["record_id"] for r in selected] == ["D", "B"]
