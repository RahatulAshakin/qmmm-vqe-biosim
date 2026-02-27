from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HARTREE_TO_KCAL_MOL = 627.5094740631


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _fmt_md(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        if abs(value) < 1e-4 and value != 0.0:
            return f"{value:.3e}"
        return f"{value:.6f}"
    return str(value)


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def _write_md_table(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_fmt_md(row.get(h, "")) for h in headers) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _classify_json_path(rel: Path) -> str | None:
    key = "/".join(part.lower() for part in rel.parts[:-1])
    if "full_dryrun" in key:
        return "full"
    if "active_adapt" in key:
        return "active_adapt"
    if "active_vqe" in key:
        return "active_vqe"
    if "qm_only" in key:
        return "qm_only"
    if "qmmm" in key:
        return "qmmm"
    return None


def _load_case_json(case_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    json_root = case_dir / "json"
    if not json_root.exists():
        raise FileNotFoundError(f"Missing JSON root: {json_root}")

    buckets: dict[str, dict[str, dict[str, Any]]] = {
        "full": {},
        "active_vqe": {},
        "active_adapt": {},
        "qm_only": {},
        "qmmm": {},
    }
    for path in sorted(json_root.rglob("*.json")):
        rel = path.relative_to(json_root)
        bucket = _classify_json_path(rel)
        if bucket is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = str(payload.get("record") or path.stem)
        payload["_source_path"] = str(path)
        buckets[bucket][record] = payload
    return buckets


def _first_not_none(*values: Any) -> Any | None:
    for value in values:
        if value is not None:
            return value
    return None


def _build_table1_rows(
    full: dict[str, dict[str, Any]],
    active_vqe: dict[str, dict[str, Any]],
    active_adapt: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records = sorted(set(full) | set(active_vqe) | set(active_adapt))
    rows: list[dict[str, Any]] = []
    for rec in records:
        frow = full.get(rec, {})
        vrow = active_vqe.get(rec, {})
        arow = active_adapt.get(rec, {})

        full_qubits = _to_int(frow.get("num_qubits"))
        active_qubits = _to_int(_first_not_none(vrow.get("num_qubits"), arow.get("num_qubits")))
        exact_energy = _to_float(
            _first_not_none(vrow.get("exact_energy"), arow.get("exact_energy"))
        )
        vqe_energy = _to_float(vrow.get("vqe_energy"))
        adapt_energy = _to_float(arow.get("vqe_energy"))

        vqe_error_ha = _to_float(vrow.get("error"))
        adapt_error_ha = _to_float(arow.get("error"))
        if vqe_error_ha is None and exact_energy is not None and vqe_energy is not None:
            vqe_error_ha = vqe_energy - exact_energy
        if adapt_error_ha is None and exact_energy is not None and adapt_energy is not None:
            adapt_error_ha = adapt_energy - exact_energy

        vqe_runtime = _to_float(
            _first_not_none(vrow.get("vqe_runtime_sec"), vrow.get("runtime_sec"))
        )
        adapt_runtime = _to_float(
            _first_not_none(arow.get("vqe_runtime_sec"), arow.get("runtime_sec"))
        )
        exact_runtime = _to_float(
            _first_not_none(vrow.get("exact_runtime_sec"), arow.get("exact_runtime_sec"))
        )

        reduction_pct = None
        if full_qubits is not None and active_qubits is not None and full_qubits > 0:
            reduction_pct = 100.0 * (full_qubits - active_qubits) / full_qubits

        rows.append(
            {
                "record": rec,
                "full_qubits": full_qubits,
                "active_qubits": active_qubits,
                "reduction_pct": reduction_pct,
                "exact_energy_ha": exact_energy,
                "vqe_energy_ha": vqe_energy,
                "adapt_energy_ha": adapt_energy,
                "vqe_error_kcal_mol": (
                    None if vqe_error_ha is None else abs(vqe_error_ha) * HARTREE_TO_KCAL_MOL
                ),
                "adapt_error_kcal_mol": (
                    None if adapt_error_ha is None else abs(adapt_error_ha) * HARTREE_TO_KCAL_MOL
                ),
                "exact_runtime_sec": exact_runtime,
                "vqe_runtime_sec": vqe_runtime,
                "adapt_runtime_sec": adapt_runtime,
            }
        )
    return rows


def _plot_empty(path: Path, title: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8.2, 4.8))
    plt.title(title)
    plt.axis("off")
    plt.text(0.5, 0.5, message, ha="center", va="center")
    plt.tight_layout()
    plt.savefig(path, dpi=220)
    plt.close()


def _plot_fig1_qubits(path: Path, rows: list[dict[str, Any]]) -> None:
    valid = [
        row
        for row in rows
        if isinstance(row.get("full_qubits"), int) and isinstance(row.get("active_qubits"), int)
    ]
    if not valid:
        _plot_empty(path, "Figure 1: Qubit Reduction", "No full/active qubit pairs found")
        return

    labels = [str(row["record"]) for row in valid]
    full_qubits = [float(row["full_qubits"]) for row in valid]
    active_qubits = [float(row["active_qubits"]) for row in valid]
    reduction_pct = [
        float(100.0 * (fq - aq) / fq) if fq > 0 else 0.0
        for fq, aq in zip(full_qubits, active_qubits, strict=True)
    ]

    x = np.arange(len(labels))
    width = 0.36
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(9.2, 4.8))
    ax1.bar(x - width / 2, full_qubits, width=width, label="Full", color="#4C78A8")
    ax1.bar(x + width / 2, active_qubits, width=width, label="Active", color="#F58518")
    ax1.set_xlabel("Record")
    ax1.set_ylabel("Qubits")
    ax1.set_xticks(x, labels)

    ax2 = ax1.twinx()
    ax2.plot(x, reduction_pct, color="#54A24B", marker="o", label="Reduction %")
    ax2.set_ylabel("Reduction (%)")

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper right")
    plt.title("FIG1: Full vs active qubits with percent reduction")
    plt.tight_layout()
    plt.savefig(path, dpi=240)
    plt.close()


def _collect_error_points(
    rows: dict[str, dict[str, Any]], method_label: str
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for rec, row in sorted(rows.items()):
        err_ha = _to_float(row.get("error"))
        runtime = _to_float(_first_not_none(row.get("vqe_runtime_sec"), row.get("runtime_sec")))
        qubits = _to_float(row.get("num_qubits"))
        if err_ha is None:
            continue
        points.append(
            {
                "record": rec,
                "method": method_label,
                "error_kcal": abs(err_ha) * HARTREE_TO_KCAL_MOL,
                "runtime_sec": runtime,
                "num_qubits": qubits,
            }
        )
    return points


def _plot_fig2_error(
    path: Path, active_vqe: dict[str, dict[str, Any]], active_adapt: dict[str, dict[str, Any]]
) -> None:
    vqe_points = _collect_error_points(active_vqe, "VQE")
    adapt_points = _collect_error_points(active_adapt, "ADAPT-VQE")
    points = vqe_points + adapt_points
    if not points:
        _plot_empty(path, "Figure 2: Error Landscape", "No active-space error points found")
        return

    use_runtime = any(p["runtime_sec"] is not None for p in points)
    x_key = "runtime_sec" if use_runtime else "num_qubits"
    x_label = "Runtime (s)" if use_runtime else "Qubits"

    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9.2, 4.8))
    for method, color, marker, subset in [
        ("VQE", "#4C78A8", "o", vqe_points),
        ("ADAPT-VQE", "#E45756", "s", adapt_points),
    ]:
        xs = [p[x_key] for p in subset if p[x_key] is not None]
        ys = [p["error_kcal"] for p in subset if p[x_key] is not None]
        labels = [p["record"] for p in subset if p[x_key] is not None]
        if not xs:
            continue
        plt.scatter(xs, ys, label=method, color=color, marker=marker, s=55, alpha=0.9)
        for x, y, label in zip(xs, ys, labels, strict=True):
            plt.annotate(label, (x, y), textcoords="offset points", xytext=(4, 4), fontsize=8)

    if any(y > 0 for y in [p["error_kcal"] for p in points]):
        plt.yscale("log")
    plt.xlabel(x_label)
    plt.ylabel(r"Absolute error $|E_{\mathrm{var}}-E_{\mathrm{exact}}|$ (kcal/mol)")
    plt.title("FIG2: Active-space error vs computational cost")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=240)
    plt.close()


def _load_scan_rows(case_dir: Path) -> list[dict[str, Any]]:
    scan_csv = case_dir / "qmmm_scan" / "delta_energy_vs_radius.csv"
    if not scan_csv.exists():
        return []
    rows: list[dict[str, Any]] = []
    with scan_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            radius = _to_float(row.get("radius_angstrom"))
            de = _to_float(row.get("delta_exact_energy_ha"))
            dv = _to_float(row.get("delta_vqe_energy_ha"))
            if radius is None or de is None or dv is None:
                continue
            rows.append(
                {
                    "dataset": row.get("dataset"),
                    "record": row.get("record"),
                    "radius_angstrom": radius,
                    "delta_exact_energy_ha": de,
                    "delta_vqe_energy_ha": dv,
                }
            )
    rows.sort(key=lambda r: float(r["radius_angstrom"]))
    return rows


def _scan_slopes(scan_rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    if len(scan_rows) < 2:
        return None, None
    x = np.asarray([float(r["radius_angstrom"]) for r in scan_rows], dtype=float)
    y_exact = np.asarray([float(r["delta_exact_energy_ha"]) for r in scan_rows], dtype=float)
    y_vqe = np.asarray([float(r["delta_vqe_energy_ha"]) for r in scan_rows], dtype=float)
    slope_exact = float(np.polyfit(x, y_exact, deg=1)[0])
    slope_vqe = float(np.polyfit(x, y_vqe, deg=1)[0])
    return slope_exact, slope_vqe


def _compute_pointcharge_shift_rows(
    qm_only: dict[str, dict[str, Any]], qmmm: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in sorted(set(qm_only) & set(qmmm)):
        qm = qm_only[rec]
        mm = qmmm[rec]
        exact_qm = _to_float(qm.get("exact_energy"))
        exact_mm = _to_float(mm.get("exact_energy"))
        vqe_qm = _to_float(qm.get("vqe_energy"))
        vqe_mm = _to_float(mm.get("vqe_energy"))
        delta_exact = None if exact_qm is None or exact_mm is None else exact_mm - exact_qm
        delta_vqe = None if vqe_qm is None or vqe_mm is None else vqe_mm - vqe_qm
        mismatch = (
            None
            if delta_exact is None or delta_vqe is None
            else abs(delta_vqe - delta_exact) * HARTREE_TO_KCAL_MOL
        )
        rows.append(
            {
                "record": rec,
                "delta_exact_ha": delta_exact,
                "delta_exact_kcal_mol": (
                    None if delta_exact is None else delta_exact * HARTREE_TO_KCAL_MOL
                ),
                "delta_vqe_ha": delta_vqe,
                "delta_vqe_kcal_mol": (
                    None if delta_vqe is None else delta_vqe * HARTREE_TO_KCAL_MOL
                ),
                "shift_mismatch_kcal_mol": mismatch,
            }
        )
    return rows


def _plot_fig3_qmmm(
    path: Path,
    scan_rows: list[dict[str, Any]],
    shift_rows: list[dict[str, Any]],
) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if scan_rows:
        x = [float(r["radius_angstrom"]) for r in scan_rows]
        de = [float(r["delta_exact_energy_ha"]) for r in scan_rows]
        dv = [float(r["delta_vqe_energy_ha"]) for r in scan_rows]
        plt.figure(figsize=(9.2, 4.8))
        plt.plot(x, de, marker="o", color="#4C78A8", label="Exact ΔE")
        plt.plot(x, dv, marker="s", color="#E45756", label="VQE ΔE")
        plt.axhline(0.0, color="black", linestyle="--", linewidth=0.9)
        plt.xlabel("Environment radius (Angstrom)")
        plt.ylabel(r"Energy shift $\Delta E = E_{\mathrm{QM/MM}} - E_{\mathrm{QM}}$ (Ha)")
        plt.title("FIG3: QM/MM embedding shift vs environment strength")
        plt.legend()
        plt.tight_layout()
        plt.savefig(path, dpi=240)
        plt.close()
        return True

    valid = [
        row
        for row in shift_rows
        if row.get("delta_exact_kcal_mol") is not None and row.get("delta_vqe_kcal_mol") is not None
    ]
    if not valid:
        _plot_empty(path, "Figure 3: QM/MM Shift", "No QM vs QM/MM shift data found")
        return False

    x = [float(row["delta_exact_kcal_mol"]) for row in valid]
    y = [float(row["delta_vqe_kcal_mol"]) for row in valid]
    labels = [str(row["record"]) for row in valid]
    lo = min(min(x), min(y))
    hi = max(max(x), max(y))
    pad = 0.05 * (hi - lo + 1e-9)
    plt.figure(figsize=(9.2, 4.8))
    plt.scatter(x, y, color="#54A24B", s=60)
    for xi, yi, label in zip(x, y, labels, strict=True):
        plt.annotate(label, (xi, yi), textcoords="offset points", xytext=(4, 4), fontsize=8)
    plt.plot([lo - pad, hi + pad], [lo - pad, hi + pad], linestyle="--", color="black")
    plt.xlabel(r"Exact shift $\Delta E$ (kcal/mol)")
    plt.ylabel(r"VQE shift $\Delta E$ (kcal/mol)")
    plt.title("FIG3: QM/MM point-charge shift consistency (Exact vs VQE)")
    plt.tight_layout()
    plt.savefig(path, dpi=240)
    plt.close()
    return False


def _augment_table2_with_scan_slopes(
    shift_rows: list[dict[str, Any]], scan_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    slope_exact, slope_vqe = _scan_slopes(scan_rows)
    scan_record = str(scan_rows[0].get("record")) if scan_rows else None

    rows = [dict(row) for row in shift_rows]
    if not rows and scan_rows:
        rows.append(
            {
                "record": scan_record or "scan",
                "delta_exact_ha": None,
                "delta_exact_kcal_mol": None,
                "delta_vqe_ha": None,
                "delta_vqe_kcal_mol": None,
                "shift_mismatch_kcal_mol": None,
            }
        )

    for row in rows:
        attach = scan_record is None or row.get("record") == scan_record
        row["scan_slope_exact_ha_per_angstrom"] = slope_exact if attach else None
        row["scan_slope_exact_kcal_mol_per_angstrom"] = (
            None if slope_exact is None or not attach else slope_exact * HARTREE_TO_KCAL_MOL
        )
        row["scan_slope_vqe_ha_per_angstrom"] = slope_vqe if attach else None
        row["scan_slope_vqe_kcal_mol_per_angstrom"] = (
            None if slope_vqe is None or not attach else slope_vqe * HARTREE_TO_KCAL_MOL
        )
    return rows


def _write_captions(case_dir: Path, used_scan_curve: bool) -> Path:
    path = case_dir / "CAPTIONS.md"
    fig3_caption = (
        "FIG3: QM/MM embedding shift versus environment radius. Curves show "
        r"$\Delta E = E_{\mathrm{QM/MM}} - E_{\mathrm{QM}}$ for exact and VQE."
        if used_scan_curve
        else "FIG3: QM vs QM/MM point-charge shift consistency. Each point is a record; "
        "agreement is indicated by proximity to the y=x line."
    )
    text = "\n".join(
        [
            f"# {case_dir.name} Captions",
            "",
            "## Figures",
            "",
            "FIG1: Qubit reduction from full to active-space representation across available records, "
            "including percent reduction.",
            "",
            "FIG2: Active-space variational error (kcal/mol) versus computational cost "
            "(runtime if available, otherwise qubit count) for VQE and ADAPT-VQE.",
            "",
            fig3_caption,
            "",
            "## Tables",
            "",
            "TABLE1: Active-space benchmark summary by record with qubits, energies, "
            "VQE/ADAPT errors, and runtimes.",
            "",
            "TABLE2: QM/MM shift summary with exact and VQE shifts and optional scan slopes.",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m qmmm_vqe_biosim.analysis.paper_artifacts",
        description="Generate paper-grade primary figures/tables from docs/paper/<case>/json/**",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Deprecated explicit case directory (e.g. docs/paper/mor41_sto3g)",
    )
    parser.add_argument(
        "--case",
        default=None,
        help="Case folder under docs/paper (e.g. mor41_sto3g)",
    )
    parser.add_argument(
        "--paper-root",
        default="docs/paper",
        help="Paper root directory (default: docs/paper)",
    )
    args = parser.parse_args()

    if args.root is not None:
        case_dir = Path(args.root)
    else:
        if args.case is None:
            raise ValueError("Provide --case (or deprecated --root).")
        case_dir = Path(args.paper_root) / args.case
    json_root = case_dir / "json"
    if not json_root.exists():
        raise FileNotFoundError(f"Missing required JSON directory: {json_root}")

    figures_dir = case_dir / "figures"
    tables_dir = case_dir / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    buckets = _load_case_json(case_dir)
    full = buckets["full"]
    active_vqe = buckets["active_vqe"]
    active_adapt = buckets["active_adapt"]
    qm_only = buckets["qm_only"]
    qmmm = buckets["qmmm"]

    table1_rows = _build_table1_rows(full=full, active_vqe=active_vqe, active_adapt=active_adapt)
    table1_headers = [
        "record",
        "full_qubits",
        "active_qubits",
        "reduction_pct",
        "exact_energy_ha",
        "vqe_energy_ha",
        "adapt_energy_ha",
        "vqe_error_kcal_mol",
        "adapt_error_kcal_mol",
        "exact_runtime_sec",
        "vqe_runtime_sec",
        "adapt_runtime_sec",
    ]
    _write_csv(tables_dir / "table01_active_benchmark_summary.csv", table1_headers, table1_rows)
    _write_md_table(tables_dir / "table01_active_benchmark_summary.md", table1_headers, table1_rows)

    shift_rows = _compute_pointcharge_shift_rows(qm_only=qm_only, qmmm=qmmm)
    scan_rows = _load_scan_rows(case_dir)
    table2_rows = _augment_table2_with_scan_slopes(shift_rows=shift_rows, scan_rows=scan_rows)
    table2_headers = [
        "record",
        "delta_exact_ha",
        "delta_exact_kcal_mol",
        "delta_vqe_ha",
        "delta_vqe_kcal_mol",
        "shift_mismatch_kcal_mol",
        "scan_slope_exact_ha_per_angstrom",
        "scan_slope_exact_kcal_mol_per_angstrom",
        "scan_slope_vqe_ha_per_angstrom",
        "scan_slope_vqe_kcal_mol_per_angstrom",
    ]
    _write_csv(tables_dir / "table02_qmmm_shift_summary.csv", table2_headers, table2_rows)
    _write_md_table(tables_dir / "table02_qmmm_shift_summary.md", table2_headers, table2_rows)

    fig1 = figures_dir / "fig01_qubit_reduction.png"
    fig2 = figures_dir / "fig02_error_vs_runtime_or_qubits.png"
    fig3 = figures_dir / "fig03_qm_vs_qmmm_shift.png"
    _plot_fig1_qubits(fig1, table1_rows)
    _plot_fig2_error(fig2, active_vqe, active_adapt)
    used_scan_curve = _plot_fig3_qmmm(fig3, scan_rows=scan_rows, shift_rows=shift_rows)

    captions_path = _write_captions(case_dir, used_scan_curve=used_scan_curve)

    print(f"Input JSON root : {json_root}")
    print(f"Wrote figures   : {figures_dir}")
    print(f"Wrote tables    : {tables_dir}")
    print(f"Wrote captions  : {captions_path}")
    print("Primary outputs:")
    print(f"  {fig1.name}")
    print(f"  {fig2.name}")
    print(f"  {fig3.name}")
    print("  table01_active_benchmark_summary.csv/.md")
    print("  table02_qmmm_shift_summary.csv/.md")


if __name__ == "__main__":
    main()
