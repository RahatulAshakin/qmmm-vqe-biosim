from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from qmmm_vqe_biosim.analysis.benchmark import run_benchmark
from qmmm_vqe_biosim.datasets.io import get_structure_record
from qmmm_vqe_biosim.paths import ensure_project_dirs
from qmmm_vqe_biosim.qmmm.charges import write_mm_charges_csv
from qmmm_vqe_biosim.qmmm.generate_charges import generate_charge_coordinates, geometry_centroid


def _parse_radii_list(raw: str) -> list[float]:
    vals = [v.strip() for v in raw.split(",") if v.strip()]
    if not vals:
        raise ValueError("--radii cannot be empty")
    radii = [float(v) for v in vals]
    if any(r <= 0 for r in radii):
        raise ValueError("All radii must be > 0")
    return radii


def _generate_radii(start: float, stop: float, step: float) -> list[float]:
    if start <= 0 or stop <= 0 or step <= 0:
        raise ValueError("radius start/stop/step must be > 0")
    if stop < start:
        raise ValueError("radius-stop must be >= radius-start")
    values: list[float] = []
    x = float(start)
    while x <= stop + 1e-12:
        values.append(round(x, 10))
        x += step
    return values


def _default_out_dir(dataset: str, record: str, basis: str) -> Path:
    results = ensure_project_dirs()["results"]
    out_dir = results / "qmmm_scan" / dataset / f"{record}_{basis}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _radius_tag(radius: float) -> str:
    return f"{radius:.2f}".replace(".", "p")


def _plot_delta_curve(path: Path, rows: list[dict[str, Any]]) -> None:
    xs = [float(r["radius_angstrom"]) for r in rows]
    de = [r["delta_exact_energy_ha"] for r in rows]
    dv = [r["delta_vqe_energy_ha"] for r in rows]

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7.2, 4.4))
    plt.plot(xs, de, marker="o", label="exact ΔE")
    plt.plot(xs, dv, marker="s", label="vqe ΔE")
    plt.axhline(0.0, color="black", linewidth=0.9, linestyle="--")
    plt.xlabel("Charge shell radius (Angstrom)")
    plt.ylabel("Energy shift ΔE = E(QM/MM) - E(QM) [Ha]")
    plt.title("QM/MM embedding shift vs environment strength")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=220)
    plt.close()


def _write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "dataset",
        "record",
        "basis",
        "pattern",
        "num_charges",
        "charge_value",
        "radius_angstrom",
        "exact_energy_ha",
        "vqe_energy_ha",
        "delta_exact_energy_ha",
        "delta_vqe_energy_ha",
        "charges_csv",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def run_qmmm_scan(
    *,
    dataset: str,
    record: str,
    basis: str,
    radii: list[float],
    pattern: str = "shell",
    n: int = 6,
    q: float = 0.1,
    method: str = "vqe",
    maxiter: int = 60,
    seed: int = 7,
    out_dir: Path | None = None,
    force: bool = False,
) -> tuple[Path, Path]:
    if n < 1:
        raise ValueError("n must be >= 1")

    scan_dir = out_dir if out_dir is not None else _default_out_dir(dataset, record, basis)
    scan_dir.mkdir(parents=True, exist_ok=True)
    charges_dir = scan_dir / "charges"
    charges_dir.mkdir(parents=True, exist_ok=True)

    csv_out = scan_dir / "delta_energy_vs_radius.csv"
    png_out = scan_dir / "delta_energy_vs_radius.png"
    if not force and (csv_out.exists() or png_out.exists()):
        raise FileExistsError(f"Outputs already exist under {scan_dir}. Use --force to overwrite.")

    baseline = run_benchmark(
        dataset=dataset,
        basis=basis,
        records=[record],
        method=method,
        maxiter=maxiter,
        seed=seed,
    )[0]

    exact_qm = baseline.get("exact_energy")
    vqe_qm = baseline.get("vqe_energy")
    if exact_qm is None or vqe_qm is None:
        raise RuntimeError("Baseline QM benchmark did not produce exact/vqe energies.")

    geom = get_structure_record(dataset=dataset, record_id=record)
    center = geometry_centroid(geom)
    rows: list[dict[str, Any]] = []

    for radius in radii:
        coords = generate_charge_coordinates(
            pattern=pattern,
            center=center,
            radius=float(radius),
            n=n,
        )
        charges = [float(q)] * n
        charges_path = charges_dir / f"{pattern}_r{_radius_tag(radius)}_n{n}.csv"
        write_mm_charges_csv(path=charges_path, coords_angstrom=coords.tolist(), charges=charges)

        row = run_benchmark(
            dataset=dataset,
            basis=basis,
            records=[record],
            method=method,
            maxiter=maxiter,
            seed=seed,
            mm_charges_path=str(charges_path),
        )[0]

        exact = row.get("exact_energy")
        vqe = row.get("vqe_energy")
        if exact is None or vqe is None:
            raise RuntimeError(
                f"Scan benchmark failed for radius={radius}: exact_energy or vqe_energy is missing"
            )

        rows.append(
            {
                "dataset": dataset,
                "record": record,
                "basis": basis,
                "pattern": pattern,
                "num_charges": n,
                "charge_value": float(q),
                "radius_angstrom": float(radius),
                "exact_energy_ha": float(exact),
                "vqe_energy_ha": float(vqe),
                "delta_exact_energy_ha": float(exact - exact_qm),
                "delta_vqe_energy_ha": float(vqe - vqe_qm),
                "charges_csv": str(charges_path),
            }
        )

    _write_rows_csv(csv_out, rows)
    _plot_delta_curve(png_out, rows)
    return csv_out, png_out


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.analysis.qmmm_scan",
        description="Run a QM/MM radius scan and plot delta energy vs environment strength.",
    )
    parser.add_argument("--dataset", default="mor41", help="Dataset name")
    parser.add_argument("--record", default="H2", help="Record ID")
    parser.add_argument("--basis", default="sto3g", help="Basis set")
    parser.add_argument(
        "--pattern", default="shell", choices=["shell", "line"], help="Charge pattern"
    )
    parser.add_argument("--n", type=int, default=6, help="Number of point charges")
    parser.add_argument("--q", type=float, default=0.1, help="Charge value per point charge")
    parser.add_argument(
        "--radii", default=None, help="Comma-separated radii list, e.g. 1.5,2.0,2.5"
    )
    parser.add_argument("--radius-start", type=float, default=1.5, help="Radius sweep start")
    parser.add_argument("--radius-stop", type=float, default=3.0, help="Radius sweep stop")
    parser.add_argument("--radius-step", type=float, default=0.5, help="Radius sweep step")
    parser.add_argument(
        "--method",
        default="vqe",
        choices=["vqe", "adapt_vqe"],
        help="Quantum algorithm used by benchmark",
    )
    parser.add_argument("--maxiter", type=int, default=60, help="VQE optimizer max iterations")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic random seed")
    parser.add_argument(
        "--out", type=Path, default=None, help="Output directory for scan artifacts"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()

    radii = (
        _parse_radii_list(args.radii)
        if args.radii is not None
        else _generate_radii(args.radius_start, args.radius_stop, args.radius_step)
    )
    csv_out, png_out = run_qmmm_scan(
        dataset=args.dataset,
        record=args.record,
        basis=args.basis,
        radii=radii,
        pattern=args.pattern,
        n=args.n,
        q=args.q,
        method=args.method,
        maxiter=args.maxiter,
        seed=args.seed,
        out_dir=args.out,
        force=args.force,
    )
    print(f"Wrote scan CSV: {csv_out}")
    print(f"Wrote scan PNG: {png_out}")


if __name__ == "__main__":
    main()
