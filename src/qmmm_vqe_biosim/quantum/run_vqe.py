from __future__ import annotations

import argparse
import json

from qmmm_vqe_biosim.paths import ensure_project_dirs
from qmmm_vqe_biosim.quantum.vqe_ground_state import run_vqe_ground_state


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.quantum.run_vqe",
        description="Run VQE ground-state energy for a processed geometry record.",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g. mor41)")
    parser.add_argument("--record", required=True, help="Record ID (e.g. H2)")
    parser.add_argument("--basis", required=True, help="Basis set (e.g. sto3g)")
    parser.add_argument("--mapper", default="parity", help="Qubit mapper: parity|jw|bk")
    parser.add_argument("--optimizer", default="slsqp", help="Optimizer: slsqp|cobyla|spsa")
    parser.add_argument("--maxiter", type=int, default=200, help="Maximum optimizer iterations")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic random seed")
    args = parser.parse_args()

    out = run_vqe_ground_state(
        dataset=args.dataset,
        record=args.record,
        basis=args.basis,
        mapper=args.mapper,
        optimizer=args.optimizer,
        maxiter=args.maxiter,
        seed=args.seed,
    )

    results_dir = ensure_project_dirs()["results"] / "vqe" / args.dataset
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / f"{args.record}_{args.basis}.json"
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Saved VQE result: {out_path}")
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
