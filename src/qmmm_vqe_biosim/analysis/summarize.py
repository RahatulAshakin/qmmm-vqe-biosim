from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def default_in_dir(dataset: str, basis: str) -> Path:
    return Path("results") / "benchmark" / dataset / basis


def _is_result_json(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    # avoid picking up any future summary files
    if path.name.startswith("summary"):
        return False
    return True


def load_results(in_dir: Path) -> list[dict[str, Any]]:
    if not in_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {in_dir}")

    rows: list[dict[str, Any]] = []
    for p in sorted(in_dir.glob("*.json")):
        if not _is_result_json(p):
            continue
        rows.append(json.loads(p.read_text(encoding="utf-8")))

    # stable ordering for output
    rows.sort(key=lambda r: (str(r.get("record", "")), str(r.get("basis", ""))))
    return rows


def normalize_row(r: dict[str, Any]) -> dict[str, Any]:
    # Add a friendly "note" field for summary tables
    note = r.get("skipped_reason") or ""
    out = dict(r)
    out["note"] = note
    return out


def write_summary_csv(rows: list[dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Choose a stable, useful column ordering
    fieldnames = [
        "dataset",
        "basis",
        "record",
        "num_qubits",
        "active_electrons",
        "active_orbitals",
        "exact_energy",
        "vqe_energy",
        "error",
        "exact_runtime_sec",
        "vqe_runtime_sec",
        "runtime_sec",
        "note",
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(normalize_row(r))


def write_summary_json(rows: list[dict[str, Any]], out_json: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = [normalize_row(r) for r in rows]
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fmt(x: Any) -> str:
    if x is None:
        return "None"
    if isinstance(x, float):
        # compact but readable
        return f"{x:.10g}"
    return str(x)


def print_table(rows: list[dict[str, Any]]) -> None:
    cols = ["record", "num_qubits", "exact_energy", "vqe_energy", "error", "note"]
    data = [[_fmt(normalize_row(r).get(c)) for c in cols] for r in rows]

    widths = [len(c) for c in cols]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    print(header)
    print("-" * len(header))
    for row in data:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(cols))))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.analysis.summarize",
        description="Summarize per-record benchmark JSON files into a table + CSV/JSON.",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g. mor41)")
    parser.add_argument("--basis", required=True, help="Basis set (e.g. sto3g)")
    parser.add_argument(
        "--in-dir",
        default=None,
        help="Input directory (default: results/benchmark/<dataset>/<basis>/)",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: same as --in-dir)",
    )
    args = parser.parse_args()

    dataset = args.dataset.strip().lower()
    basis = args.basis.strip().lower()

    in_dir = Path(args.in_dir) if args.in_dir else default_in_dir(dataset, basis)
    out_dir = Path(args.out_dir) if args.out_dir else in_dir

    rows = load_results(in_dir)
    if not rows:
        raise RuntimeError(f"No benchmark JSON files found in: {in_dir}")

    out_csv = out_dir / "summary.csv"
    out_json = out_dir / "summary.json"

    write_summary_csv(rows, out_csv)
    write_summary_json(rows, out_json)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_json}\n")
    print_table(rows)


if __name__ == "__main__":
    main()
