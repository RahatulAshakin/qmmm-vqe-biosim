from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qmmm_vqe_biosim.paths import data_root


def structures_jsonl_path(dataset: str, data_dir: Path | None = None) -> Path:
    base = data_dir if data_dir is not None else data_root()
    return base / "processed" / dataset / "structures.jsonl"


def load_structure_records(dataset: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    path = structures_jsonl_path(dataset=dataset, data_dir=data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Missing processed dataset file: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def get_structure_record(
    dataset: str, record_id: str, data_dir: Path | None = None
) -> dict[str, Any]:
    for record in load_structure_records(dataset=dataset, data_dir=data_dir):
        if record.get("record_id") == record_id:
            return record
    raise KeyError(f"Record '{record_id}' not found in dataset '{dataset}'")
