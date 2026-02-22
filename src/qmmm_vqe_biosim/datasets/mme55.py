from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from qmmm_vqe_biosim.datasets.schema import GeometryRecord, write_jsonl
from qmmm_vqe_biosim.datasets.xyz import read_xyz
from qmmm_vqe_biosim.paths import repo_root

_SPIN_NAME_TO_MULT = {
    "singlet": 1,
    "doublet": 2,
    "triplet": 3,
    "quartet": 4,
    "quintet": 5,
    "sextet": 6,
    "septet": 7,
    "octet": 8,
}


def mme55_structures_root(raw_dir: Path) -> Path:
    """
    Raw MME55 download clones into data/raw/mme55/repo/<case>/struc.xyz.

    For tests/debug, also allow raw_dir itself to contain cases.
    """
    sub = raw_dir / "repo"
    return sub if sub.exists() else raw_dir


def _read_int_maybe(path: Path) -> int | None:
    """Read integer-like content from metadata files like .CHRG and .UHF."""
    if not path.exists():
        return None
    txt = path.read_text(encoding="utf-8", errors="replace").strip()
    if not txt:
        return None
    token = txt.split()[0]
    try:
        return int(token)
    except ValueError:
        try:
            f = float(token)
        except ValueError:
            return None
        r = int(round(f))
        if abs(f - r) < 1e-9:
            return r
        return int(f)


def _infer_multiplicity_from_name(case_name: str) -> int | None:
    lower = case_name.lower()
    for spin_name, mult in _SPIN_NAME_TO_MULT.items():
        if lower.endswith(f"_{spin_name}") or f"_{spin_name}_" in lower or lower == spin_name:
            return mult
    return None


def _infer_multiplicity(uhf: int | None, case_name: str) -> int | None:
    """
    If `.UHF` exists: treat it as number of unpaired electrons (2S), so multiplicity = uhf + 1,
    with uhf <= 0 -> multiplicity 1.

    Otherwise, try to infer from case name (e.g., *_singlet, *_triplet).
    """
    if uhf is not None:
        if uhf <= 0:
            return 1
        return uhf + 1
    return _infer_multiplicity_from_name(case_name)


def iter_mme55_xyz_files(raw_dir: Path) -> list[Path]:
    root = mme55_structures_root(raw_dir)
    # Expected: <case>/struc.xyz
    return sorted(root.glob("*/struc.xyz"))


def build_mme55_structure_records(
    raw_dir: Path, limit: int | None = None
) -> Iterable[GeometryRecord]:
    files = iter_mme55_xyz_files(raw_dir)
    if limit is not None:
        files = files[:limit]

    root = repo_root()

    for xyz_path in files:
        case = xyz_path.parent.name
        atoms, coords, comment = read_xyz(xyz_path)

        charge = _read_int_maybe(xyz_path.parent / ".CHRG")
        uhf = _read_int_maybe(xyz_path.parent / ".UHF")
        multiplicity = _infer_multiplicity(uhf, case)

        try:
            source_rel = str(xyz_path.resolve().relative_to(root))
        except Exception:
            source_rel = str(xyz_path.resolve())

        yield GeometryRecord(
            dataset="mme55",
            record_id=case,
            structure_id=case,
            atoms=atoms,
            coords_angstrom=coords,
            source_path=source_rel,
            charge=charge,
            multiplicity=multiplicity,
            comment=comment,
        )


def parse_mme55_structures(raw_dir: Path, out_path: Path, limit: int | None = None) -> Path:
    records = build_mme55_structure_records(raw_dir=raw_dir, limit=limit)
    write_jsonl(records, out_path)
    return out_path
