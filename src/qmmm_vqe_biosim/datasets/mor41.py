from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from qmmm_vqe_biosim.datasets.schema import GeometryRecord, write_jsonl
from qmmm_vqe_biosim.datasets.xyz import read_xyz
from qmmm_vqe_biosim.paths import repo_root


def iter_mor41_xyz_files(raw_dir: Path) -> list[Path]:
    # Expected layout: data/raw/mor41/<ID>/mol.xyz
    return sorted(raw_dir.glob("**/mol.xyz"))


def build_mor41_structure_records(
    raw_dir: Path, limit: int | None = None
) -> Iterable[GeometryRecord]:
    files = iter_mor41_xyz_files(raw_dir)
    if limit is not None:
        files = files[:limit]

    root = repo_root()

    for xyz_path in files:
        record_id = xyz_path.parent.name
        atoms, coords, comment = read_xyz(xyz_path)

        try:
            source_rel = str(xyz_path.resolve().relative_to(root))
        except Exception:
            source_rel = str(xyz_path.resolve())

        yield GeometryRecord(
            dataset="mor41",
            record_id=record_id,
            structure_id=record_id,
            atoms=atoms,
            coords_angstrom=coords,
            source_path=source_rel,
            comment=comment,
            charge=None,
            multiplicity=None,
        )


def parse_mor41_structures(raw_dir: Path, out_path: Path, limit: int | None = None) -> Path:
    records = build_mor41_structure_records(raw_dir=raw_dir, limit=limit)
    write_jsonl(records, out_path)
    return out_path
