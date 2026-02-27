# qmmm-vqe-biosim

Benchmark-gated **geometry → electronic structure → (optional) active space → qubit Hamiltonian → VQE/ADAPT-VQE** workflow implemented in **Qiskit / Qiskit Nature**, with reproducible analysis and **paper-ready artifacts** committed under `docs/paper/`.

## Abstract

Near-term quantum chemistry workflows must manage rapidly growing qubit requirements while still producing reproducible, benchmarkable results. This project implements an end-to-end pipeline that:

1. ingests molecular geometries from benchmark datasets,
2. builds ab initio electronic structure problems with Qiskit Nature,
3. applies optional active-space reduction to control qubit counts,
4. maps to qubit Hamiltonians, and
5. solves ground-state energies with VQE or ADAPT-VQE, benchmarked against deterministic references when feasible.

A lightweight QM/MM point-charge embedding hook is included to demonstrate environmental effects without a full MM force-field workflow.

On a MOR41/STO-3G demo subset, small active spaces reduce qubits dramatically (e.g., CO: `18 → 6`, CO2: `28 → 6`) while retaining sub-chemical-accuracy errors (`<< 1 kcal/mol`) for VQE and ADAPT-VQE in selected active spaces.

---

## Why this repo

This repo focuses on **reproducible, benchmark-gated workflows** rather than one-off energy numbers.

Core design goals:

- standardized dataset ingestion/parsing,
- deterministic benchmark runs,
- explicit qubit-budget gating,
- active-space configurability,
- exact-vs-variational comparison,
- machine-readable + paper-ready artifacts.

---

## Methods overview

### 1) Dataset ingestion and normalization

Raw structures are downloaded and parsed into a consistent JSONL schema at:

- `data/processed/<dataset>/structures.jsonl`

Each record stores:

- `atoms`
- `coords_angstrom`
- optional `charge`, `multiplicity`
- provenance (`source_path`)
- `record_id`

### 2) Electronic structure construction

For each record, the pipeline builds a Qiskit Nature electronic structure problem (demo basis: `sto3g`) with optional:

- total charge/multiplicity,
- MM point-charge embedding via CSV (`x,y,z,q`).

### 3) Active-space reduction and qubit mapping

Supports:

- manual active space (e.g., `4e,4o` for CO/CO2 demo),
- auto active-space modes:
  - `heuristic`
  - `uno_cas`
  - `occ_entropy`
  - `avas`

Qubit-budget guards:

- `--exact-max-qubits` for exact reference gating,
- `--max-qubits` for VQE/ADAPT gating.

### 4) Solvers

- **Exact reference** (deterministic) when within threshold.
- **VQE** (UCC-style ansatz, SLSQP by default, deterministic seeds).
- **ADAPT-VQE** (with benchmark integration).

### 5) QM/MM embedding hook

Minimal point-charge embedding from CSV:

- columns: `x,y,z,q`

Also includes a scan utility to study `ΔE` versus charge-environment radius.

### 6) Reproducibility and reporting

Produces:

- per-record benchmark JSON
- summary CSV/JSON
- paper artifacts (`PNG`, `CSV`, `MD`, captions) under `docs/paper/<case>/...`

Thread oversubscription controls are included for WSL/BLAS stability.

---

## MOR41/STO-3G demonstration snapshot

### Qubit reduction (full vs active)

- H2: `2` qubits
- CO: `18 → 6` qubits (**66.7% reduction**)
- CO2: `28 → 6` qubits (**78.6% reduction**)

### Active-space benchmark accuracy (manual active space on CO/CO2)

- CO (6 qubits):
  - Exact: `-111.2596819306813 Ha`
  - VQE: `-111.25960072527755 Ha`
  - `|error| = 8.120540e-05 Ha ≈ 0.051 kcal/mol`
- CO2 (6 qubits):
  - Exact: `-185.13928120411495 Ha`
  - VQE: `-185.13921945665362 Ha`
  - `|error| = 6.174746e-05 Ha ≈ 0.039 kcal/mol`
- H2 (2 qubits, full): Exact and VQE agree to ~`1e-10 Ha`.

### ADAPT-VQE in same active spaces

- CO: `|error| ≈ 1.049693e-04 Ha ≈ 0.066 kcal/mol`
- CO2: `|error| ≈ 6.195523e-05 Ha ≈ 0.039 kcal/mol`

### QM/MM point-charge shift demo

- H2 (QM only): `E ≈ -1.13724338197 Ha`
- H2 (QM + point charge): `E ≈ -1.41540515832 Ha`
- `ΔE ≈ -0.27816177635 Ha ≈ -174.56 kcal/mol`

---

## Repository layout (high level)

- `src/qmmm_vqe_biosim/datasets/` — dataset download/parse/schema/io
- `src/qmmm_vqe_biosim/chem/` — problem building, exact reference, active-space utilities
- `src/qmmm_vqe_biosim/quantum/` — VQE/ADAPT-VQE runners and backend helpers
- `src/qmmm_vqe_biosim/qmmm/` — point-charge CSV utilities + generators
- `src/qmmm_vqe_biosim/analysis/` — benchmarking, sweeps, summaries, paper artifacts
- `docs/paper/<case>/` — committed paper figures/tables/json for selected cases

---

## Data policy

Raw datasets are downloaded locally and are **not committed**:

- `data/raw/<dataset>/...`

Processed records are local:

- `data/processed/<dataset>/structures.jsonl`

Anything under `results/` is ignored by `.gitignore` by design.  
Commit-worthy paper/demo artifacts should go under `docs/paper/`.

---

## Environment + install

### 1) Create env

```bash
conda env create -f environment.yml
conda activate qmmm-vqe-biosim
```

### 2) Install package (editable)

```bash
python -m pip install -e .
```

### 3) Threading safety (important on WSL/BLAS)

```bash
conda env config vars set \
  OMP_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 \
  PYTHONUNBUFFERED=1

conda deactivate
conda activate qmmm-vqe-biosim
```

---

## Quickstart: MOR41 small benchmark demo

### 1) Download + parse MOR41

```bash
python -m qmmm_vqe_biosim.datasets.download --dataset mor41
python -m qmmm_vqe_biosim.datasets.parse --dataset mor41 --force
```

### 2) Run small benchmark script

```bash
./scripts/run_mor41_smallset.sh mor41 sto3g
```

### 3) Summarize benchmark outputs

```bash
python -m qmmm_vqe_biosim.analysis.summarize --dataset mor41 --basis sto3g
sed -n '1,40p' results/benchmark/mor41/sto3g/summary.csv
```

---

## Benchmark CLI

### Dry-run (qubit counts only)

```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2,CO,CO2 \
  --dry-run --force
```

### Manual active space (recommended for stable reporting)

```bash
# H2 full
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2 --force

# CO / CO2 active-space
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records CO,CO2 \
  --active-electrons 4 --active-orbitals 4 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force
```

### Auto active space

```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2,CO,CO2 \
  --auto-active-space \
  --auto-active-space-method heuristic \
  --max-qubits 16 --exact-max-qubits 12 \
  --force
```

Methods:

- `heuristic`: conservative qubit-budget rule preserving spin imbalance when possible.
- `uno_cas`: UHF natural occupations with occupation-window selection.
- `occ_entropy`: top-K orbital selection by entropy proxy.
- `avas`: AVAS-driven valence subspace from AO labels/atoms.

Useful flags:

- `--auto-active-space-method heuristic|uno_cas|occ_entropy|avas`
- `--auto-active-space-max-orbitals N`
- `--auto-active-space-occ-min X`
- `--auto-active-space-occ-max Y` (alias `--occ-max`)

### ADAPT-VQE benchmark

```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2 \
  --method adapt_vqe \
  --active-electrons 2 --active-orbitals 2 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force
```

---

## Single-record quantum run

```bash
python -m qmmm_vqe_biosim.quantum.run_vqe \
  --dataset mor41 --record H2 --basis sto3g
```

Writes JSON to:

- `results/vqe/mor41/H2_sto3g.json`

---

## IBM Runtime quickstart

`analysis.benchmark` supports IBM Runtime in job mode (no explicit session required).

Set credentials (**use real values; do not commit**):

```bash
export QISKIT_IBM_CHANNEL=ibm_quantum_platform
export QISKIT_IBM_TOKEN=YOUR_REAL_TOKEN
export QISKIT_IBM_INSTANCE=YOUR_REAL_INSTANCE
```

List available IBM backends:

```bash
python - <<'PY'
import os
from qiskit_ibm_runtime import QiskitRuntimeService

service = QiskitRuntimeService(
    channel=os.getenv("QISKIT_IBM_CHANNEL", "ibm_quantum_platform"),
    token=os.getenv("QISKIT_IBM_TOKEN"),
    instance=os.getenv("QISKIT_IBM_INSTANCE"),
)
for backend in sorted(service.backends(simulator=False, operational=True), key=lambda b: b.name):
    print(backend.name)
PY
```

Run IBM H2 demo script:

```bash
bash scripts/run_ibm_h2.sh
# or
bash scripts/run_ibm_h2.sh ibm_kyoto
```

Equivalent command:

```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 \
  --basis sto3g \
  --records H2 \
  --backend ibm \
  --ibm-backend <backend_name> \
  --shots 4096 \
  --out docs/paper/mor41_sto3g/json/ibm_runtime_h2/ \
  --force
```

Expected output:

- `docs/paper/mor41_sto3g/json/ibm_runtime_h2/H2.json`

---

## QM/MM point-charge embedding

### Minimal one-off run

```bash
cat > mm_charges.csv <<'EOF2'
x,y,z,q
0.0,0.0,2.0,0.5
EOF2

python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2 \
  --mm-charges mm_charges.csv \
  --force
```

### Generate synthetic charge sets

```bash
python -m qmmm_vqe_biosim.qmmm.generate_charges \
  --pattern shell \
  --radius 2.0 \
  --n 6 \
  --q 0.1 \
  --out mm_charges.csv
```

Patterns:

- `shell`: charges around molecular centroid on a sphere
- `line`: charges distributed along z-axis

### Radius scan (paper-ready curve)

```bash
python -m qmmm_vqe_biosim.analysis.qmmm_scan \
  --dataset mor41 \
  --record H2 \
  --basis sto3g \
  --pattern shell \
  --n 6 \
  --q 0.1 \
  --radius-start 1.5 \
  --radius-stop 3.0 \
  --radius-step 0.5 \
  --out docs/paper/mor41_sto3g/qmmm_scan \
  --force
```

Outputs:

- `docs/paper/mor41_sto3g/qmmm_scan/delta_energy_vs_radius.csv`
- `docs/paper/mor41_sto3g/qmmm_scan/delta_energy_vs_radius.png`

---

## Paper artifact generation

Generate primary paper outputs from `docs/paper/<case>/json/**`:

```bash
python -m qmmm_vqe_biosim.analysis.paper_artifacts --case mor41_sto3g
```

Writes to:

- `docs/paper/<case>/figures/`
- `docs/paper/<case>/tables/`
- `docs/paper/<case>/CAPTIONS.md` (overwritten)

Primary outputs:

- `fig01_qubit_reduction.png`
- `fig02_error_vs_runtime_or_qubits.png`
- `fig03_qm_vs_qmmm_shift.png`
- `table01_active_benchmark_summary.csv`
- `table01_active_benchmark_summary.md`
- `table02_qmmm_shift_summary.csv`
- `table02_qmmm_shift_summary.md`

---

## Testing and quality checks

```bash
python -m ruff check .
python -m black --check .
python -m pytest -q
```

Run slow tests explicitly:

```bash
RUN_SLOW=1 python -m pytest -q -m slow
```

---

## Limitations and future work

- Auto active-space policy is currently heuristic/NO/AVAS-style and can be improved with stronger AutoCAS-like criteria.
- QM/MM currently supports point-charge embedding only (no full force-field coupling, polarization, or dynamics).
- IBM Runtime integration is implemented; reproducible hardware studies require valid credentials and backend availability.
- Scaling to broad benchmark coverage requires careful active-space policy and runtime budgeting.

---

## Conclusion

This project delivers a reproducible, benchmark-gated quantum chemistry workflow from real dataset geometries through Qiskit Nature problem construction, active-space reduction, qubit mapping, and VQE/ADAPT-VQE solving, with deterministic outputs and paper-ready reporting. In the MOR41/STO-3G demonstration, large qubit reductions (CO: `18→6`, CO2: `28→6`) are achieved while maintaining sub-chemical-accuracy errors in selected active spaces, and a QM/MM point-charge hook demonstrates consistent environmental perturbation analysis.

---

## License

MIT (see `LICENSE`).
