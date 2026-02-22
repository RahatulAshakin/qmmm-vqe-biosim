from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeometryRecord:
    """
    Minimal normalized geometry record.

    coords_angstrom: list of [x,y,z] in Angstrom.
    """

    dataset: str
    record_id: str
    structure_id: str
    atoms: list[str]
    coords_angstrom: list[list[float]]
    source_path: str
    charge: int | None = None
    multiplicity: int | None = None
    comment: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def write_jsonl(records: Iterable[GeometryRecord], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.to_json() + "\n")
