from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from qmmm_vqe_biosim.datasets.schema import GeometryRecord, write_jsonl
from qmmm_vqe_biosim.datasets.xyz import read_xyz
from qmmm_vqe_biosim.paths import repo_root


def rost61_structures_root(raw_dir: Path) -> Path:
    """
    Raw ROST61 extracts into data/raw/rost61/rost61/<case>/mol.xyz.
    For tests/debug we also allow raw_dir itself to contain the cases.
    """
    sub = raw_dir / "rost61"
    return sub if sub.exists() else raw_dir


def _read_int_maybe(path: Path) -> int | None:
    """
    Read integer-ish content from metadata files like .CHRG and .UHF.
    If parsing fails, returns None.
    """
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


def _infer_multiplicity_from_uhf(uhf: int | None) -> int | None:
    """
    Many Grimme/Turbomole benchmark folders include `.UHF` which is commonly
    the number of unpaired electrons (n_alpha - n_beta) = 2S.

    If uhf = 0 -> closed shell -> multiplicity 1
    If uhf = 1 -> doublet -> multiplicity 2
    If uhf = 2 -> triplet -> multiplicity 3
    """
    if uhf is None:
        return None
    if uhf <= 0:
        return 1
    return uhf + 1


def iter_rost61_xyz_files(raw_dir: Path) -> list[Path]:
    root = rost61_structures_root(raw_dir)
    return sorted(root.glob("*/mol.xyz"))


def build_rost61_structure_records(
    raw_dir: Path, limit: int | None = None
) -> Iterable[GeometryRecord]:
    files = iter_rost61_xyz_files(raw_dir)
    if limit is not None:
        files = files[:limit]

    root = repo_root()

    for xyz_path in files:
        record_id = xyz_path.parent.name
        atoms, coords, comment = read_xyz(xyz_path)

        charge = _read_int_maybe(xyz_path.parent / ".CHRG")
        uhf = _read_int_maybe(xyz_path.parent / ".UHF")
        multiplicity = _infer_multiplicity_from_uhf(uhf)

        try:
            source_rel = str(xyz_path.resolve().relative_to(root))
        except Exception:
            source_rel = str(xyz_path.resolve())

        yield GeometryRecord(
            dataset="rost61",
            record_id=record_id,
            structure_id=record_id,
            atoms=atoms,
            coords_angstrom=coords,
            source_path=source_rel,
            charge=charge,
            multiplicity=multiplicity,
            comment=comment,
        )


def parse_rost61_structures(raw_dir: Path, out_path: Path, limit: int | None = None) -> Path:
    records = build_rost61_structure_records(raw_dir=raw_dir, limit=limit)
    write_jsonl(records, out_path)
    return out_path
