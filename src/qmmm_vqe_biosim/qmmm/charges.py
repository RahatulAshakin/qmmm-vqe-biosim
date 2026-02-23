from __future__ import annotations

import csv
from pathlib import Path


def load_mm_charges_csv(path: str | Path) -> tuple[list[list[float]], list[float]]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"MM charges file not found: {csv_path}")

    coords: list[list[float]] = []
    charges: list[float] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header in MM charges file: {csv_path}")

        field_map = {name.strip().lower(): name for name in reader.fieldnames}
        required = {"x", "y", "z", "q"}
        missing = required - set(field_map)
        if missing:
            raise ValueError(
                f"MM charges CSV must include columns x,y,z,q. Missing: {sorted(missing)}"
            )

        for line_no, row in enumerate(reader, start=2):
            try:
                x = float(row[field_map["x"]])
                y = float(row[field_map["y"]])
                z = float(row[field_map["z"]])
                q = float(row[field_map["q"]])
            except Exception as exc:
                raise ValueError(
                    f"Invalid MM charges value at {csv_path}:{line_no} (expected numeric x,y,z,q)"
                ) from exc

            coords.append([x, y, z])
            charges.append(q)

    if not coords:
        raise ValueError(f"No MM charges rows found in {csv_path}")

    return coords, charges
