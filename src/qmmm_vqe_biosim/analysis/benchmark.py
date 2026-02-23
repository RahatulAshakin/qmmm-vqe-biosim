from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from qiskit_algorithms.minimum_eigensolvers import NumPyMinimumEigensolver
from qiskit_nature.second_q.algorithms import GroundStateEigensolver
from qiskit_nature.second_q.mappers import ParityMapper
from qiskit_nature.second_q.transformers import ActiveSpaceTransformer

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import build_electronic_structure_problem
from qmmm_vqe_biosim.datasets.io import get_structure_record
from qmmm_vqe_biosim.paths import ensure_project_dirs
from qmmm_vqe_biosim.quantum.vqe_ground_state import run_vqe_for_problem


def _parse_records_args(records_args: list[str]) -> list[str]:
    records: list[str] = []
    for group in records_args:
        parts = [part.strip() for part in group.split(",")]
        records.extend([part for part in parts if part])
    if not records:
        raise ValueError("No records provided. Use --records H2 or --records H2,H3.")
    return records


def _default_out_dir(dataset: str, basis: str) -> Path:
    out_dir = ensure_project_dirs()["results"] / "benchmark" / dataset / basis
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _build_problem(
    geometry: dict[str, Any],
    basis: str,
    active_electrons: int | None,
    active_orbitals: int | None,
):
    problem = build_electronic_structure_problem(record=geometry, basis=basis)
    if active_electrons is None and active_orbitals is None:
        return problem
    if active_electrons is None or active_orbitals is None:
        raise ValueError("Provide both --active-electrons and --active-orbitals together.")
    transformer = ActiveSpaceTransformer(
        num_electrons=active_electrons,
        num_spatial_orbitals=active_orbitals,
    )
    return transformer.transform(problem)


def _compute_num_qubits(problem) -> int:
    mapper = ParityMapper(num_particles=problem.num_particles)
    qubit_op = mapper.map(problem.hamiltonian.second_q_op())
    return int(qubit_op.num_qubits)


def _run_exact(
    problem, num_qubits: int, exact_max_qubits: int
) -> tuple[float | None, float | None, str]:
    if num_qubits > exact_max_qubits:
        return None, None, "skipped"
    solver = NumPyMinimumEigensolver()
    solver.filter_criterion = problem.get_default_filter_criterion()
    gse = GroundStateEigensolver(ParityMapper(num_particles=problem.num_particles), solver)
    start = perf_counter()
    result = gse.solve(problem)
    runtime_sec = perf_counter() - start
    energy = float(result.total_energies[0].real)
    return energy, runtime_sec, "run"


def run_benchmark(
    dataset: str,
    basis: str,
    records: list[str],
    seed: int = 7,
    maxiter: int = 200,
    dry_run: bool = False,
    max_qubits: int = 16,
    exact_max_qubits: int = 12,
    active_electrons: int | None = None,
    active_orbitals: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        geometry = get_structure_record(dataset=dataset, record_id=record)
        problem = _build_problem(
            geometry=geometry,
            basis=basis,
            active_electrons=active_electrons,
            active_orbitals=active_orbitals,
        )
        num_qubits = _compute_num_qubits(problem)

        exact_energy: float | None = None
        exact_runtime_sec: float | None = None
        exact_method = "skipped" if dry_run else "run"
        if not dry_run:
            exact_energy, exact_runtime_sec, exact_method = _run_exact(
                problem=problem, num_qubits=num_qubits, exact_max_qubits=exact_max_qubits
            )

        vqe_energy: float | None = None
        vqe_runtime_sec: float | None = None
        vqe_method = "skipped"
        vqe_ansatz: str | None = None
        vqe_optimizer: str | None = None
        vqe_mapper: str | None = None
        skipped_reason: str | None = None

        if dry_run:
            skipped_reason = "dry_run"
        elif num_qubits > max_qubits:
            skipped_reason = "num_qubits>max_qubits"
        else:
            vqe = run_vqe_for_problem(
                problem=problem,
                dataset=dataset,
                record=record,
                basis=basis,
                seed=seed,
                maxiter=maxiter,
            )
            vqe_energy = float(vqe["energy"])
            vqe_runtime_sec = float(vqe["runtime_sec"])
            vqe_method = "run"
            vqe_ansatz = str(vqe["ansatz"])
            vqe_optimizer = str(vqe["optimizer"])
            vqe_mapper = str(vqe["mapper"])

        row = {
            "dataset": dataset,
            "record": record,
            "basis": basis,
            "num_qubits": num_qubits,
            "charge": geometry.get("charge"),
            "multiplicity": geometry.get("multiplicity"),
            "exact_method": exact_method,
            "vqe_method": vqe_method,
            "exact_energy": exact_energy,
            "vqe_energy": vqe_energy,
            "error": (
                None
                if exact_energy is None or vqe_energy is None
                else float(vqe_energy - exact_energy)
            ),
            "exact_runtime_sec": exact_runtime_sec,
            "vqe_runtime_sec": vqe_runtime_sec,
            "runtime_sec": (
                (exact_runtime_sec or 0.0) + (vqe_runtime_sec or 0.0)
                if (exact_runtime_sec is not None or vqe_runtime_sec is not None)
                else None
            ),
            "vqe_ansatz": vqe_ansatz,
            "vqe_optimizer": vqe_optimizer,
            "vqe_mapper": vqe_mapper,
            "seed": seed,
            "maxiter": maxiter,
            "max_qubits": max_qubits,
            "exact_max_qubits": exact_max_qubits,
            "active_electrons": active_electrons,
            "active_orbitals": active_orbitals,
            "skipped_reason": skipped_reason,
        }
        rows.append(row)
    return rows


def write_benchmark_json(
    rows: list[dict[str, Any]], out_dir: Path, force: bool = False
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for row in rows:
        out_path = out_dir / f"{row['record']}.json"
        if out_path.exists() and not force:
            raise FileExistsError(f"Output exists: {out_path}. Re-run with --force to overwrite.")
        out_path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(out_path)
    return written


def print_summary_table(rows: list[dict[str, Any]]) -> None:
    print("record  qubits  exact       vqe         error(Ha)      note")
    for row in rows:
        note = row["skipped_reason"] or ""
        print(
            f"{row['record']:6s}"
            f" {row['num_qubits']:6d}"
            f" {row['exact_energy'] if row['exact_energy'] is not None else 'None':>11}"
            f" {row['vqe_energy'] if row['vqe_energy'] is not None else 'None':>11}"
            f" {row['error'] if row['error'] is not None else 'None':>14}"
            f" {note:>12}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.analysis.benchmark",
        description="Benchmark reference vs VQE ground-state energies on processed records.",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g. mor41)")
    parser.add_argument("--basis", required=True, help="Basis set (e.g. sto3g)")
    parser.add_argument(
        "--records",
        required=True,
        action="append",
        help="Record IDs (comma-separated and/or repeated), e.g. --records H2,H3 --records CO",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: results/benchmark/<dataset>/<basis>/)",
    )
    parser.add_argument("--seed", type=int, default=7, help="Deterministic random seed")
    parser.add_argument("--maxiter", type=int, default=200, help="VQE max optimizer iterations")
    parser.add_argument(
        "--dry-run", action="store_true", help="Only compute metadata + qubit counts"
    )
    parser.add_argument(
        "--max-qubits",
        type=int,
        default=16,
        help="Skip VQE when num_qubits exceeds this threshold",
    )
    parser.add_argument(
        "--exact-max-qubits",
        type=int,
        default=12,
        help="Skip exact solve when num_qubits exceeds this threshold",
    )
    parser.add_argument("--active-electrons", type=int, default=None, help="Active-space electrons")
    parser.add_argument("--active-orbitals", type=int, default=None, help="Active-space orbitals")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output file")
    args = parser.parse_args()

    records = _parse_records_args(args.records)
    out_dir = args.out if args.out is not None else _default_out_dir(args.dataset, args.basis)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = run_benchmark(
        dataset=args.dataset,
        basis=args.basis,
        records=records,
        seed=args.seed,
        maxiter=args.maxiter,
        dry_run=args.dry_run,
        max_qubits=args.max_qubits,
        exact_max_qubits=args.exact_max_qubits,
        active_electrons=args.active_electrons,
        active_orbitals=args.active_orbitals,
    )
    written = write_benchmark_json(rows=rows, out_dir=out_dir, force=args.force)
    print(f"Wrote {len(written)} files to {out_dir}")
    print_summary_table(rows)


if __name__ == "__main__":
    main()
