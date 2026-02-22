from __future__ import annotations

import argparse
from pathlib import Path

from qmmm_vqe_biosim.datasets.mor41 import parse_mor41_structures
from qmmm_vqe_biosim.datasets.rost61 import parse_rost61_structures
from qmmm_vqe_biosim.paths import ensure_project_dirs


def parse_dataset(name: str, force: bool = False, limit: int | None = None) -> Path:
    dirs = ensure_project_dirs()
    dataset = name.strip().lower()

    raw_dir = dirs["raw"] / dataset
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw dataset not found: {raw_dir}. Run download first.")

    out_dir = dirs["processed"] / dataset
    out_dir.mkdir(parents=True, exist_ok=True)

    if dataset == "mor41":
        out_path = out_dir / "structures.jsonl"
        if out_path.exists() and not force:
            return out_path
        return parse_mor41_structures(raw_dir=raw_dir, out_path=out_path, limit=limit)
    if dataset == "rost61":
        out_path = out_dir / "structures.jsonl"
        if out_path.exists() and not force:
            return out_path
        return parse_rost61_structures(raw_dir=raw_dir, out_path=out_path, limit=limit)

    raise NotImplementedError(f"Parser not implemented yet for dataset: {dataset}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="qmmm-vqe-biosim.datasets.parse")
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g., mor41)")
    parser.add_argument("--force", action="store_true", help="Overwrite outputs if they exist")
    parser.add_argument(
        "--limit", type=int, default=None, help="Parse only first N structures (debug)"
    )
    args = parser.parse_args()

    out = parse_dataset(args.dataset, force=args.force, limit=args.limit)
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
