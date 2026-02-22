from __future__ import annotations

import argparse

from qmmm_vqe_biosim.chem.qiskit_nature_ground_state import solve_ground_state_energy
from qmmm_vqe_biosim.datasets.io import get_structure_record


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.chem.solve_ground_state",
        description="Solve electronic ground-state energy from a processed geometry record.",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g. mor41)")
    parser.add_argument("--record", required=True, help="Record ID (e.g. H2)")
    parser.add_argument("--basis", default="sto3g", help="Basis set (default: sto3g)")
    args = parser.parse_args()

    record = get_structure_record(dataset=args.dataset, record_id=args.record)
    energy = solve_ground_state_energy(record=record, basis=args.basis)
    print(f"{args.dataset}:{args.record} ({args.basis}) E0 = {energy:.12f} Ha")


if __name__ == "__main__":
    main()
