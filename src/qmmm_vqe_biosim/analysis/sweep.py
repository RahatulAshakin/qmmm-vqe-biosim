from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from qmmm_vqe_biosim.analysis.summarize import _is_result_json, default_in_dir
from qmmm_vqe_biosim.datasets.io import structures_jsonl_path


def parse_records_args(records_args: list[str] | None) -> list[str]:
    if not records_args:
        return []
    records: list[str] = []
    for group in records_args:
        parts = [part.strip() for part in group.split(",")]
        records.extend([part for part in parts if part])
    return records


def load_records_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input JSONL not found: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _atom_count(record: dict[str, Any]) -> int:
    atoms = record.get("atoms")
    if isinstance(atoms, list):
        return len(atoms)
    return 0


def select_structure_records(
    records: list[dict[str, Any]],
    selected_record_ids: list[str] | None = None,
    smallest_n: int | None = None,
    max_atoms: int | None = None,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        rec_id = str(record.get("record_id", "")).strip()
        if rec_id:
            by_id[rec_id] = record

    if selected_record_ids:
        filtered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec_id in selected_record_ids:
            if rec_id in seen:
                continue
            seen.add(rec_id)
            if rec_id not in by_id:
                raise KeyError(f"Record '{rec_id}' not found in structures input")
            filtered.append(by_id[rec_id])
    else:
        filtered = list(by_id.values())

    if max_atoms is not None:
        filtered = [record for record in filtered if _atom_count(record) <= max_atoms]

    if smallest_n is not None:
        if smallest_n < 1:
            raise ValueError("--smallest-n must be >= 1")
        filtered = sorted(filtered, key=lambda r: (_atom_count(r), str(r.get("record_id", ""))))[
            :smallest_n
        ]

    return filtered


def _run_subprocess(cmd: list[str]) -> tuple[bool, str, str]:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return proc.returncode == 0, proc.stdout, proc.stderr


def _result_path(out_dir: Path, record_id: str) -> Path:
    return out_dir / f"{record_id}.json"


def run_sweep(
    dataset: str,
    basis: str,
    selected_record_ids: list[str] | None = None,
    smallest_n: int | None = None,
    max_atoms: int | None = None,
    out_dir: Path | None = None,
    method: str = "vqe",
    seed: int = 7,
    maxiter: int = 200,
    dry_run: bool = False,
    max_qubits: int = 16,
    exact_max_qubits: int = 12,
    auto_active_space: bool = False,
    active_electrons: int | None = None,
    active_orbitals: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if (active_electrons is None) ^ (active_orbitals is None):
        raise ValueError("Provide both --active-electrons and --active-orbitals together.")

    jsonl_path = structures_jsonl_path(dataset)
    all_records = load_records_jsonl(jsonl_path)
    selected = select_structure_records(
        records=all_records,
        selected_record_ids=selected_record_ids,
        smallest_n=smallest_n,
        max_atoms=max_atoms,
    )

    sweep_out_dir = out_dir if out_dir is not None else default_in_dir(dataset=dataset, basis=basis)
    sweep_out_dir.mkdir(parents=True, exist_ok=True)

    total = len(selected)
    succeeded = 0
    skipped_existing = 0
    failures: list[dict[str, Any]] = []

    for idx, record in enumerate(selected, start=1):
        record_id = str(record["record_id"])
        out_path = _result_path(sweep_out_dir, record_id)

        if out_path.exists() and not force:
            skipped_existing += 1
            print(f"[{idx}/{total}] {record_id}: skip (exists)")
            continue

        cmd = [
            sys.executable,
            "-X",
            "faulthandler",
            "-m",
            "qmmm_vqe_biosim.analysis.benchmark",
            "--dataset",
            dataset,
            "--basis",
            basis,
            "--records",
            record_id,
            "--out",
            str(sweep_out_dir),
            "--method",
            method,
            "--seed",
            str(seed),
            "--maxiter",
            str(maxiter),
            "--max-qubits",
            str(max_qubits),
            "--exact-max-qubits",
            str(exact_max_qubits),
        ]
        if dry_run:
            cmd.append("--dry-run")
        if auto_active_space:
            cmd.append("--auto-active-space")
        if active_electrons is not None and active_orbitals is not None:
            cmd.extend(["--active-electrons", str(active_electrons)])
            cmd.extend(["--active-orbitals", str(active_orbitals)])
        if force:
            cmd.append("--force")

        print(f"[{idx}/{total}] {record_id}: run")
        ok, stdout, stderr = _run_subprocess(cmd)
        if ok:
            succeeded += 1
            print(f"[{idx}/{total}] {record_id}: ok")
            if stdout.strip():
                print(stdout.strip())
            continue

        failures.append(
            {
                "record": record_id,
                "stderr": stderr.strip(),
                "stdout": stdout.strip(),
            }
        )
        print(f"[{idx}/{total}] {record_id}: FAILED")
        if stderr.strip():
            print(stderr.strip())

    # Summarize only if at least one benchmark JSON is present.
    has_results = any(_is_result_json(path) for path in sweep_out_dir.glob("*.json"))
    summary_ok = False
    summary_stderr = ""
    if has_results:
        summarize_cmd = [
            sys.executable,
            "-m",
            "qmmm_vqe_biosim.analysis.summarize",
            "--dataset",
            dataset,
            "--basis",
            basis,
            "--in-dir",
            str(sweep_out_dir),
            "--out-dir",
            str(sweep_out_dir),
        ]
        summary_ok, summary_stdout, summary_stderr = _run_subprocess(summarize_cmd)
        if summary_ok and summary_stdout.strip():
            print(summary_stdout.strip())
        elif not summary_ok and summary_stderr.strip():
            print(summary_stderr.strip())

    report = {
        "dataset": dataset,
        "basis": basis,
        "out_dir": str(sweep_out_dir),
        "selected": total,
        "succeeded": succeeded,
        "skipped_existing": skipped_existing,
        "failed": len(failures),
        "failures": failures,
        "summary_ok": summary_ok,
        "summary_error": summary_stderr.strip() if not summary_ok else "",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.analysis.sweep",
        description="Run benchmark over many records with per-record subprocess isolation.",
    )
    parser.add_argument("--dataset", required=True, help="Dataset name (e.g. mor41)")
    parser.add_argument("--basis", required=True, help="Basis set (e.g. sto3g)")
    parser.add_argument(
        "--records",
        action="append",
        default=[],
        help="Optional comma-separated record IDs (can be repeated)",
    )
    parser.add_argument(
        "--smallest-n",
        type=int,
        default=None,
        help="Select N smallest records by atom count (after other filters)",
    )
    parser.add_argument(
        "--max-atoms",
        type=int,
        default=None,
        help="Keep only records with atom count <= this threshold",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: results/benchmark/<dataset>/<basis>/)",
    )
    parser.add_argument(
        "--method",
        default="vqe",
        choices=["vqe", "adapt_vqe"],
        help="Algorithm for quantum solve: vqe or adapt_vqe",
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
    parser.add_argument(
        "--auto-active-space",
        action="store_true",
        help="Automatically choose active_electrons/orbitals when needed",
    )
    parser.add_argument("--active-electrons", type=int, default=None, help="Active-space electrons")
    parser.add_argument("--active-orbitals", type=int, default=None, help="Active-space orbitals")
    parser.add_argument("--force", action="store_true", help="Overwrite existing record outputs")
    args = parser.parse_args()

    report = run_sweep(
        dataset=args.dataset,
        basis=args.basis,
        selected_record_ids=parse_records_args(args.records),
        smallest_n=args.smallest_n,
        max_atoms=args.max_atoms,
        out_dir=args.out,
        method=args.method,
        seed=args.seed,
        maxiter=args.maxiter,
        dry_run=args.dry_run,
        max_qubits=args.max_qubits,
        exact_max_qubits=args.exact_max_qubits,
        auto_active_space=args.auto_active_space,
        active_electrons=args.active_electrons,
        active_orbitals=args.active_orbitals,
        force=args.force,
    )

    print("\nSweep report:")
    print(f"  selected:        {report['selected']}")
    print(f"  succeeded:       {report['succeeded']}")
    print(f"  skipped existing:{report['skipped_existing']}")
    print(f"  failed:          {report['failed']}")
    print(f"  output dir:      {report['out_dir']}")
    if report["failures"]:
        print("  failed records:")
        for item in report["failures"]:
            print(f"    - {item['record']}")
    if report["failed"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
