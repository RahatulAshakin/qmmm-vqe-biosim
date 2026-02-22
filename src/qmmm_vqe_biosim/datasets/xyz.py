from __future__ import annotations

from pathlib import Path


def read_xyz(path: Path) -> tuple[list[str], list[list[float]], str | None]:
    """
    Read a standard XYZ file.

    Returns:
      atoms: list of element symbols
      coords: list of [x,y,z] floats (Angstrom)
      comment: second line comment if present
    """
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [ln.strip() for ln in raw_lines if ln.strip()]
    if not lines:
        raise ValueError(f"Empty XYZ file: {path}")

    n_atoms: int | None = None
    comment: str | None = None
    start = 0

    try:
        n_atoms = int(lines[0])
        comment = lines[1] if len(lines) > 1 else None
        start = 2
    except ValueError:
        n_atoms = None
        comment = None
        start = 0

    body = lines[start:]
    if n_atoms is not None:
        body = body[:n_atoms]

    atoms: list[str] = []
    coords: list[list[float]] = []

    for ln in body:
        parts = ln.split()
        if len(parts) < 4:
            raise ValueError(f"Invalid XYZ line in {path}: {ln!r}")
        sym = parts[0]
        x, y, z = map(float, parts[1:4])
        atoms.append(sym)
        coords.append([x, y, z])

    if n_atoms is not None and len(atoms) != n_atoms:
        raise ValueError(f"Atom count mismatch in {path}: expected {n_atoms}, got {len(atoms)}")

    return atoms, coords, comment
