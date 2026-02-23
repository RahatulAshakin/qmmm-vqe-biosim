from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless PNG output
import matplotlib.pyplot as plt


def _load_json_dir(d: Path) -> dict[str, dict[str, Any]]:
    """Load *.json files keyed by record."""
    out: dict[str, dict[str, Any]] = {}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        with p.open("r", encoding="utf-8") as f:
            r = json.load(f)
        rec = r.get("record") or p.stem
        out[str(rec)] = r
    return out


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in headers})


def _write_md_table(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def fmt(v: Any) -> str:
        if v is None or v == "":
            return ""
        if isinstance(v, float):
            # compact scientific notation for tiny errors; fixed for energies
            if abs(v) < 1e-3:
                return f"{v:.3e}"
            return f"{v:.6f}"
        return str(v)

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append("| " + " | ".join(fmt(r.get(h, "")) for h in headers) + " |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bar_png(path: Path, title: str, x_labels: list[str], series: dict[str, list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    keys = list(series.keys())
    n = len(x_labels)
    m = len(keys)

    # bar positions
    width = 0.8 / max(m, 1)
    xs = list(range(n))

    plt.figure(figsize=(9, 4.8))
    for j, k in enumerate(keys):
        offsets = [x + (j - (m - 1) / 2) * width for x in xs]
        plt.bar(offsets, series[k], width=width, label=k)

    plt.xticks(xs, x_labels, rotation=0)
    plt.title(title)
    plt.xlabel("Record")
    plt.ylabel("")
    if m > 1:
        plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate paper-ready tables and figures from docs/results JSON."
    )
    ap.add_argument(
        "--root", type=str, required=True, help="Root dir like docs/results/mor41_sto3g/"
    )
    args = ap.parse_args()

    root = Path(args.root)

    full_dry = _load_json_dir(root / "json_full_dryrun")
    active_vqe = _load_json_dir(root / "json_active_vqe")
    active_adapt = _load_json_dir(root / "json_active_adapt")  # optional
    qm_only = _load_json_dir(root / "qm_only")
    qmmm = _load_json_dir(root / "qmmm_pointcharge")

    fig_dir = root / "figures"
    tab_dir = root / "tables"

    # -------------------------
    # TABLE 1: Qubit reduction
    # -------------------------
    records = sorted(set(full_dry.keys()) | set(active_vqe.keys()))
    rows_qubits: list[dict[str, Any]] = []
    for rec in records:
        fq = full_dry.get(rec, {}).get("num_qubits")
        aq = active_vqe.get(rec, {}).get("num_qubits")
        ae = active_vqe.get(rec, {}).get("active_electrons")
        ao = active_vqe.get(rec, {}).get("active_orbitals")
        reduction = None
        reduction_pct = None
        if isinstance(fq, int) and isinstance(aq, int):
            reduction = fq - aq
            reduction_pct = 100.0 * reduction / fq if fq else None

        rows_qubits.append(
            {
                "record": rec,
                "full_num_qubits": fq,
                "active_num_qubits": aq,
                "active_electrons": ae,
                "active_orbitals": ao,
                "qubit_reduction": reduction,
                "reduction_pct": reduction_pct,
            }
        )

    headers_qubits = [
        "record",
        "full_num_qubits",
        "active_num_qubits",
        "active_electrons",
        "active_orbitals",
        "qubit_reduction",
        "reduction_pct",
    ]
    _write_csv(tab_dir / "table_qubits_reduction.csv", headers_qubits, rows_qubits)
    _write_md_table(tab_dir / "table_qubits_reduction.md", headers_qubits, rows_qubits)

    # FIGURE 1: Full vs active qubits
    full_series = []
    active_series = []
    x_labels = []
    for rec in records:
        fq = full_dry.get(rec, {}).get("num_qubits")
        aq = active_vqe.get(rec, {}).get("num_qubits")
        if isinstance(fq, int) and isinstance(aq, int):
            x_labels.append(rec)
            full_series.append(float(fq))
            active_series.append(float(aq))

    if x_labels:
        _bar_png(
            fig_dir / "fig_qubits_full_vs_active.png",
            "Qubit count: full vs active-space",
            x_labels,
            {"full": full_series, "active": active_series},
        )

    # -------------------------
    # TABLE 2: Active benchmark
    # -------------------------
    rows_bench: list[dict[str, Any]] = []
    for rec, r in sorted(active_vqe.items()):
        rows_bench.append(
            {
                "dataset": r.get("dataset"),
                "basis": r.get("basis"),
                "record": rec,
                "num_qubits": r.get("num_qubits"),
                "active_electrons": r.get("active_electrons"),
                "active_orbitals": r.get("active_orbitals"),
                "exact_energy": r.get("exact_energy"),
                "vqe_energy": r.get("vqe_energy"),
                "error": r.get("error"),
                "exact_runtime_sec": r.get("exact_runtime_sec"),
                "vqe_runtime_sec": r.get("vqe_runtime_sec"),
                "runtime_sec": r.get("runtime_sec"),
            }
        )

    headers_bench = [
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
    ]
    _write_csv(tab_dir / "table_benchmark_active.csv", headers_bench, rows_bench)
    _write_md_table(tab_dir / "table_benchmark_active.md", headers_bench, rows_bench)

    # FIGURE 2: absolute error
    x2 = []
    e2 = []
    for rec, r in sorted(active_vqe.items()):
        err = r.get("error")
        if isinstance(err, (int, float)):
            x2.append(rec)
            e2.append(abs(float(err)))
    if x2:
        _bar_png(
            fig_dir / "fig_energy_error_active_vqe.png",
            "Absolute energy error (|E_VQE - E_exact|) on active-space runs",
            x2,
            {"|error| (Ha)": e2},
        )

    # -------------------------
    # FIGURE 3: QM vs QM/MM (H2)
    # -------------------------
    if "H2" in qm_only and "H2" in qmmm:
        qm = qm_only["H2"]
        mm = qmmm["H2"]
        labels = ["QM", "QM/MM"]
        exacts = [float(qm["exact_energy"]), float(mm["exact_energy"])]
        vqes = [float(qm["vqe_energy"]), float(mm["vqe_energy"])]

        _bar_png(
            fig_dir / "fig_h2_qm_vs_qmmm.png",
            "H2 energies: QM-only vs QM/MM point-charge embedding",
            labels,
            {"exact": exacts, "vqe": vqes},
        )

        # Optional small table for the shift (extra, but useful)
        dq = float(mm["exact_energy"]) - float(qm["exact_energy"])
        dv = float(mm["vqe_energy"]) - float(qm["vqe_energy"])
        rows_shift = [
            {
                "record": "H2",
                "exact_qm": qm["exact_energy"],
                "exact_qmmm": mm["exact_energy"],
                "delta_exact": dq,
                "vqe_qm": qm["vqe_energy"],
                "vqe_qmmm": mm["vqe_energy"],
                "delta_vqe": dv,
            }
        ]
        headers_shift = [
            "record",
            "exact_qm",
            "exact_qmmm",
            "delta_exact",
            "vqe_qm",
            "vqe_qmmm",
            "delta_vqe",
        ]
        _write_csv(tab_dir / "table_h2_qmmm_shift.csv", headers_shift, rows_shift)
        _write_md_table(tab_dir / "table_h2_qmmm_shift.md", headers_shift, rows_shift)

    # -------------------------
    # Optional: ADAPT vs VQE on H2
    # -------------------------
    if "H2" in active_adapt and "H2" in active_vqe:
        v = active_vqe["H2"]
        a = active_adapt["H2"]
        if isinstance(v.get("error"), (int, float)) and isinstance(a.get("error"), (int, float)):
            _bar_png(
                fig_dir / "fig_h2_vqe_vs_adapt_error.png",
                "H2: VQE vs ADAPT-VQE absolute error",
                ["VQE", "ADAPT-VQE"],
                {"|error| (Ha)": [abs(float(v["error"])), abs(float(a["error"]))]},
            )

    print(f"Wrote figures to: {fig_dir}")
    print(f"Wrote tables  to: {tab_dir}")


if __name__ == "__main__":
    main()
