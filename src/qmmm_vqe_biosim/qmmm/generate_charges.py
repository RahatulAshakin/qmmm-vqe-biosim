from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from qmmm_vqe_biosim.datasets.io import get_structure_record
from qmmm_vqe_biosim.qmmm.charges import write_mm_charges_csv


def geometry_centroid(record: dict) -> np.ndarray:
    coords = record.get("coords_angstrom")
    if not isinstance(coords, list) or not coords:
        raise ValueError("record is missing coords_angstrom")
    arr = np.asarray(coords, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("coords_angstrom must have shape (n_atoms, 3)")
    return arr.mean(axis=0)


def shell_points(center: np.ndarray, radius: float, n: int) -> np.ndarray:
    if n < 1:
        raise ValueError("n must be >= 1")
    if radius <= 0:
        raise ValueError("radius must be > 0")

    # Fibonacci sphere for approximately uniform sampling.
    golden_angle = np.pi * (3.0 - np.sqrt(5.0))
    points = []
    for i in range(n):
        z = 1.0 - (2.0 * (i + 0.5) / n)
        r_xy = np.sqrt(max(0.0, 1.0 - z * z))
        phi = i * golden_angle
        x = np.cos(phi) * r_xy
        y = np.sin(phi) * r_xy
        points.append(center + radius * np.asarray([x, y, z], dtype=float))
    return np.asarray(points, dtype=float)


def line_points(center: np.ndarray, radius: float, n: int) -> np.ndarray:
    if n < 1:
        raise ValueError("n must be >= 1")
    if radius <= 0:
        raise ValueError("radius must be > 0")
    if n == 1:
        z_offsets = np.asarray([0.0], dtype=float)
    else:
        z_offsets = np.linspace(-radius, radius, n)

    points = np.tile(center, (n, 1))
    points[:, 2] = center[2] + z_offsets
    return points


def generate_charge_coordinates(
    *,
    pattern: str,
    center: np.ndarray,
    radius: float,
    n: int,
) -> np.ndarray:
    key = pattern.strip().lower()
    if key == "shell":
        return shell_points(center=center, radius=radius, n=n)
    if key == "line":
        return line_points(center=center, radius=radius, n=n)
    raise ValueError(f"Unsupported charge pattern: {pattern}")


def _parse_center(raw: str | None) -> np.ndarray | None:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 3:
        raise ValueError("--center must be a comma-separated triple x,y,z")
    return np.asarray([float(parts[0]), float(parts[1]), float(parts[2])], dtype=float)


def _determine_center(
    *,
    center_raw: str | None,
    dataset: str,
    record: str,
) -> np.ndarray:
    explicit_center = _parse_center(center_raw)
    if explicit_center is not None:
        return explicit_center
    geometry = get_structure_record(dataset=dataset, record_id=record)
    return geometry_centroid(geometry)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.qmmm.generate_charges",
        description="Generate MM point-charge CSV (x,y,z,q) for QM/MM embedding demos.",
    )
    parser.add_argument(
        "--pattern",
        choices=["shell", "line"],
        default="shell",
        help="Charge placement pattern",
    )
    parser.add_argument("--radius", type=float, required=True, help="Placement radius (Angstrom)")
    parser.add_argument("--n", type=int, required=True, help="Number of point charges")
    parser.add_argument("--q", type=float, required=True, help="Charge value per point charge (e)")
    parser.add_argument(
        "--dataset",
        default="mor41",
        help="Dataset used to compute molecule centroid when --center is omitted",
    )
    parser.add_argument(
        "--record",
        default="H2",
        help="Record used to compute molecule centroid when --center is omitted",
    )
    parser.add_argument(
        "--center",
        default=None,
        help="Optional explicit center as x,y,z (overrides --dataset/--record centroid)",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output CSV path")
    args = parser.parse_args()

    center = _determine_center(center_raw=args.center, dataset=args.dataset, record=args.record)
    coords = generate_charge_coordinates(
        pattern=args.pattern,
        center=center,
        radius=args.radius,
        n=args.n,
    )
    charges = [float(args.q)] * int(args.n)
    out_path = write_mm_charges_csv(
        path=args.out,
        coords_angstrom=coords.tolist(),
        charges=charges,
    )

    print(f"Wrote MM charges CSV: {out_path}")
    print(f"pattern={args.pattern} n={args.n} radius={args.radius} q={args.q}")
    print(f"center=({center[0]:.6f}, {center[1]:.6f}, {center[2]:.6f})")


if __name__ == "__main__":
    main()
