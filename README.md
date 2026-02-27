# qmmm-vqe-biosim

Benchmark-gated **geometry → electronic structure → (optional) active space → qubit Hamiltonian → VQE/ADAPT-VQE**
workflow implemented in **Qiskit / Qiskit Nature**, with reproducible analysis and **paper-ready artifacts** committed under `docs/paper/`.

This repo is designed to be reproducible and benchmark-first:
- download raw datasets locally (**not committed**),
- parse to a normalized geometry JSONL format,
- run exact (small) vs VQE benchmarks (gated by qubit count),
- write machine-readable JSON outputs plus human-readable tables/figures.

---

## Data policy

Raw datasets are downloaded locally via the CLI and stored under:

- `data/raw/<dataset>/...`

Raw datasets are **not committed** to Git. Parsed/processed geometry records are stored under:

- `data/processed/<dataset>/structures.jsonl`

Anything under a folder named `results/` is ignored by `.gitignore` (by design).
Paper artifacts that should be committed live under `docs/paper/`.

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

## Quickstart: MOR41 small benchmark (paper-demo subset)

### 1) Download + parse MOR41
```bash
python -m qmmm_vqe_biosim.datasets.download --dataset mor41
python -m qmmm_vqe_biosim.datasets.parse --dataset mor41 --force
```

### 2) Run the small benchmark script
```bash
./scripts/run_mor41_smallset.sh mor41 sto3g
```

### 3) Summarize results (table + CSV/JSON)
```bash
python -m qmmm_vqe_biosim.analysis.summarize --dataset mor41 --basis sto3g
sed -n '1,40p' results/benchmark/mor41/sto3g/summary.csv
```

## Benchmark CLI

### Dry-run (qubit counts only)
```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2,CO,CO2 \
  --dry-run --force
```

### Manual active space (recommended for reproducible reference demos)
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
- `uno_cas`: UHF natural occupations, keep orbitals in occupation window.
- `occ_entropy`: choose top-K orbitals by entropy proxy.
- `avas`: AVAS-driven valence subspace (AO labels or atoms).

Useful flags:
- `--auto-active-space-method heuristic|uno_cas|occ_entropy|avas`
- `--auto-active-space-max-orbitals N`
- `--auto-active-space-occ-min X`
- `--auto-active-space-occ-max Y` (alias `--occ-max`)

### ADAPT-VQE
```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2 \
  --method adapt_vqe \
  --active-electrons 2 --active-orbitals 2 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force
```

### QM/MM point-charge embedding
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

## VQE single-record example

```bash
python -m qmmm_vqe_biosim.quantum.run_vqe --dataset mor41 --record H2 --basis sto3g
```

Writes JSON to `results/vqe/mor41/H2_sto3g.json`.

## IBM Runtime quickstart

`analysis.benchmark` supports IBM Runtime in job mode (no explicit session required).

Set credentials:

```bash
export QISKIT_IBM_CHANNEL=ibm_quantum_platform
export QISKIT_IBM_TOKEN=<your_token>
export QISKIT_IBM_INSTANCE=<your_instance>
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

Run the H2 IBM demo script:

```bash
bash scripts/run_ibm_h2.sh
# or
bash scripts/run_ibm_h2.sh ibm_kyoto
```

Equivalent benchmark command:

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

## QM/MM radius scan demo

Generate MM point charges:

```bash
python -m qmmm_vqe_biosim.qmmm.generate_charges \
  --pattern shell \
  --radius 2.0 \
  --n 6 \
  --q 0.1 \
  --out mm_charges.csv
```

Run a QM/MM scan for H2 and produce a figure of embedding shift vs radius:

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

If `qmmm_scan` outputs exist under `docs/paper/<case>/qmmm_scan/`,
`analysis.paper_artifacts` includes the scan figure in the generated figure set.
