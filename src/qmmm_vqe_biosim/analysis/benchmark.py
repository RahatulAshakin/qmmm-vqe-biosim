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

from qmmm_vqe_biosim.chem.active_space import choose_auto_active_space
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


def _apply_active_space(
    problem,
    active_electrons: int | tuple[int, int],
    active_orbitals: int | list[int],
):
    if isinstance(active_orbitals, int):
        transformer = ActiveSpaceTransformer(
            num_electrons=active_electrons,
            num_spatial_orbitals=active_orbitals,
        )
    else:
        transformer = ActiveSpaceTransformer(
            num_electrons=active_electrons,
            num_spatial_orbitals=len(active_orbitals),
            active_orbitals=active_orbitals,
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


def _parse_csv_list(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    values = [v.strip() for v in raw.split(",") if v.strip()]
    return values or None


def _parse_csv_ints(raw: str | None, *, one_based: bool = False) -> list[int] | None:
    values = _parse_csv_list(raw)
    if values is None:
        return None
    parsed = [int(v) for v in values]
    if one_based:
        parsed = [v - 1 for v in parsed]
    return parsed


def run_benchmark(
    dataset: str,
    basis: str,
    records: list[str],
    seed: int = 7,
    maxiter: int = 200,
    method: str = "vqe",
    mm_charges_path: str | None = None,
    backend: str = "local",
    ibm_backend_name: str | None = None,
    shots: int | None = None,
    resilience_level: int | None = None,
    optimization_level: int | None = None,
    dry_run: bool = False,
    max_qubits: int = 16,
    exact_max_qubits: int = 12,
    auto_active_space: bool = False,
    auto_active_space_method: str = "heuristic",
    auto_active_space_max_orbitals: int | None = None,
    auto_active_space_occ_min: float = 0.02,
    auto_active_space_occ_max: float = 1.98,
    auto_active_space_avas_ao_labels: list[str] | None = None,
    auto_active_space_avas_atoms: list[int] | None = None,
    active_electrons: int | None = None,
    active_orbitals: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    method_key = method.strip().lower()
    if method_key not in {"vqe", "adapt_vqe"}:
        raise ValueError(f"Unsupported method: {method}")
    if (active_electrons is None) ^ (active_orbitals is None):
        raise ValueError("Provide both --active-electrons and --active-orbitals together.")
    auto_method_key = auto_active_space_method.strip().lower()
    if auto_method_key not in {"heuristic", "uno_cas", "occ_entropy", "avas"}:
        raise ValueError(f"Unsupported auto active-space method: {auto_active_space_method}")
    if auto_active_space_occ_min > auto_active_space_occ_max:
        raise ValueError("--auto-active-space-occ-min must be <= --auto-active-space-occ-max")

    for record in records:
        geometry = get_structure_record(dataset=dataset, record_id=record)
        full_problem = build_electronic_structure_problem(
            record=geometry,
            basis=basis,
            mm_charges_path=mm_charges_path,
        )
        full_num_qubits = _compute_num_qubits(full_problem)

        chosen_active_electrons: int | tuple[int, int] | None = active_electrons
        chosen_active_orbitals: int | list[int] | None = active_orbitals
        auto_selected_orbitals: list[int] | None = None
        auto_occupations: list[float] | None = None
        auto_metadata: dict[str, Any] | None = None
        resolved_auto_method = auto_method_key
        auto_active_applied = False

        # Manual active-space settings always take precedence.
        if chosen_active_electrons is not None and chosen_active_orbitals is not None:
            problem = _apply_active_space(
                problem=full_problem,
                active_electrons=chosen_active_electrons,
                active_orbitals=chosen_active_orbitals,
            )
        elif auto_active_space and full_num_qubits > max_qubits:
            selection = choose_auto_active_space(
                problem=full_problem,
                record=geometry,
                basis=basis,
                max_qubits=max_qubits,
                method=auto_method_key,
                max_orbitals=auto_active_space_max_orbitals,
                occ_min=auto_active_space_occ_min,
                occ_max=auto_active_space_occ_max,
                avas_ao_labels=auto_active_space_avas_ao_labels,
                avas_atoms=auto_active_space_avas_atoms,
            )
            chosen_active_electrons = selection.active_electrons
            chosen_active_orbitals = selection.active_orbitals
            auto_active_applied = True
            resolved_auto_method = selection.method
            auto_selected_orbitals = selection.selected_orbitals
            auto_occupations = selection.occupations
            auto_metadata = selection.metadata
            problem = _apply_active_space(
                problem=full_problem,
                active_electrons=chosen_active_electrons,
                active_orbitals=chosen_active_orbitals,
            )
        else:
            problem = full_problem

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
        vqe_runtime_metadata: dict[str, Any] | None = None
        resolved_backend = backend
        resolved_ibm_backend_name = ibm_backend_name
        algorithm = method_key
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
                method=method_key,
                backend=backend,
                ibm_backend_name=ibm_backend_name,
                shots=shots,
                resilience_level=resilience_level,
                optimization_level=optimization_level,
                seed=seed,
                maxiter=maxiter,
                active_electrons=chosen_active_electrons,
                active_orbitals=chosen_active_orbitals,
            )
            vqe_energy = float(vqe["energy"])
            vqe_runtime_sec = float(vqe["runtime_sec"])
            vqe_method = "run"
            algorithm = str(vqe.get("algorithm", method_key))
            vqe_ansatz = str(vqe["ansatz"])
            vqe_optimizer = str(vqe["optimizer"])
            vqe_mapper = str(vqe["mapper"])
            vqe_runtime_metadata = vqe.get("runtime_metadata")
            resolved_backend = str(vqe.get("backend", backend))
            maybe_ibm_name = vqe.get("ibm_backend_name")
            resolved_ibm_backend_name = None if maybe_ibm_name is None else str(maybe_ibm_name)

        row = {
            "dataset": dataset,
            "record": record,
            "basis": basis,
            "algorithm": algorithm,
            "mm_charges_path": mm_charges_path,
            "backend": resolved_backend,
            "ibm_backend_name": resolved_ibm_backend_name,
            "shots": shots,
            "resilience_level": resilience_level,
            "optimization_level": optimization_level,
            "full_num_qubits": full_num_qubits,
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
            "vqe_runtime_metadata": vqe_runtime_metadata,
            "seed": seed,
            "maxiter": maxiter,
            "max_qubits": max_qubits,
            "exact_max_qubits": exact_max_qubits,
            "auto_active_space": auto_active_space,
            "auto_active_space_method": resolved_auto_method,
            "auto_active_space_max_orbitals": auto_active_space_max_orbitals,
            "auto_active_space_occ_min": auto_active_space_occ_min,
            "auto_active_space_occ_max": auto_active_space_occ_max,
            "auto_active_space_applied": auto_active_applied,
            "auto_active_space_selected_orbitals": auto_selected_orbitals,
            "auto_active_space_occupations": auto_occupations,
            "auto_active_space_metadata": auto_metadata,
            "active_electrons": (
                list(chosen_active_electrons)
                if isinstance(chosen_active_electrons, tuple)
                else chosen_active_electrons
            ),
            "active_orbitals": (
                list(chosen_active_orbitals)
                if isinstance(chosen_active_orbitals, list)
                else chosen_active_orbitals
            ),
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
        "--mm-charges",
        default=None,
        help="Optional CSV with MM point charges columns x,y,z,q",
    )
    parser.add_argument(
        "--method",
        default="vqe",
        choices=["vqe", "adapt_vqe"],
        help="Algorithm for quantum solve: vqe or adapt_vqe",
    )
    parser.add_argument(
        "--backend",
        default="local",
        choices=["local", "ibm"],
        help="Estimator backend: local (default) or ibm",
    )
    parser.add_argument(
        "--ibm-backend",
        default=None,
        help="IBM Runtime backend name (required when --backend ibm)",
    )
    parser.add_argument("--shots", type=int, default=None, help="Optional shot count")
    parser.add_argument(
        "--resilience-level",
        type=int,
        default=None,
        help="Optional IBM Runtime resilience level",
    )
    parser.add_argument(
        "--optimization-level",
        type=int,
        default=None,
        help="Optional backend optimization level",
    )
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
    parser.add_argument(
        "--auto-active-space",
        action="store_true",
        help=(
            "Automatically choose active_electrons/orbitals when full problem exceeds --max-qubits "
            "and manual active-space values are not provided"
        ),
    )
    parser.add_argument(
        "--auto-active-space-method",
        default="heuristic",
        choices=["heuristic", "uno_cas", "occ_entropy", "avas"],
        help="Method for automatic active-space selection",
    )
    parser.add_argument(
        "--auto-active-space-max-orbitals",
        type=int,
        default=None,
        help="Optional cap on selected active spatial orbitals",
    )
    parser.add_argument(
        "--auto-active-space-occ-min",
        type=float,
        default=0.02,
        help="Minimum spin-summed natural occupation for UNO-CAS",
    )
    parser.add_argument(
        "--auto-active-space-occ-max",
        "--occ-max",
        dest="auto_active_space_occ_max",
        type=float,
        default=1.98,
        help="Maximum spin-summed natural occupation for UNO-CAS",
    )
    parser.add_argument(
        "--auto-active-space-avas-ao-labels",
        default=None,
        help="Comma-separated AVAS AO labels (e.g. '0 C 2p,1 O 2p')",
    )
    parser.add_argument(
        "--auto-active-space-avas-atoms",
        default=None,
        help="Comma-separated 1-based atom indices for AVAS valence label generation",
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
        method=args.method,
        mm_charges_path=args.mm_charges,
        backend=args.backend,
        ibm_backend_name=args.ibm_backend,
        shots=args.shots,
        resilience_level=args.resilience_level,
        optimization_level=args.optimization_level,
        dry_run=args.dry_run,
        max_qubits=args.max_qubits,
        exact_max_qubits=args.exact_max_qubits,
        auto_active_space=args.auto_active_space,
        auto_active_space_method=args.auto_active_space_method,
        auto_active_space_max_orbitals=args.auto_active_space_max_orbitals,
        auto_active_space_occ_min=args.auto_active_space_occ_min,
        auto_active_space_occ_max=args.auto_active_space_occ_max,
        auto_active_space_avas_ao_labels=_parse_csv_list(args.auto_active_space_avas_ao_labels),
        auto_active_space_avas_atoms=_parse_csv_ints(
            args.auto_active_space_avas_atoms, one_based=True
        ),
        active_electrons=args.active_electrons,
        active_orbitals=args.active_orbitals,
    )
    written = write_benchmark_json(rows=rows, out_dir=out_dir, force=args.force)
    print(f"Wrote {len(written)} files to {out_dir}")
    print_summary_table(rows)


if __name__ == "__main__":
    main()
