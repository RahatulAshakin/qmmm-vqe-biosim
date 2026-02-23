from __future__ import annotations

import argparse
from time import perf_counter
from typing import Any

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import solve_ground_state_energy
from qmmm_vqe_biosim.datasets.io import get_structure_record


def run_reference_ground_state(
    dataset: str,
    record: str,
    basis: str = "sto3g",
    mm_charges_path: str | None = None,
) -> dict[str, Any]:
    geometry = get_structure_record(dataset=dataset, record_id=record)
    start = perf_counter()
    energy = solve_ground_state_energy(
        record=geometry, basis=basis, mm_charges_path=mm_charges_path
    )
    runtime_sec = perf_counter() - start
    return {
        "dataset": dataset,
        "record": record,
        "basis": basis,
        "method": "reference_ground_state",
        "energy": energy,
        "runtime_sec": runtime_sec,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.chem.solve_ground_state",
        description="Solve electronic ground-state energy from a processed geometry record.",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g. mor41)")
    parser.add_argument("--record", required=True, help="Record ID (e.g. H2)")
    parser.add_argument("--basis", default="sto3g", help="Basis set (default: sto3g)")
    parser.add_argument(
        "--mm-charges",
        default=None,
        help="Optional CSV with MM point charges columns x,y,z,q",
    )
    args = parser.parse_args()

    out = run_reference_ground_state(
        dataset=args.dataset,
        record=args.record,
        basis=args.basis,
        mm_charges_path=args.mm_charges,
    )
    print(f"{args.dataset}:{args.record} ({args.basis}) E0 = {out['energy']:.12f} Ha")


if __name__ == "__main__":
    main()
