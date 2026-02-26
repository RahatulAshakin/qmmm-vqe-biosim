# qmmm-vqe-biosim

Benchmark-gated **geometry → electronic structure → (optional) active space → qubit Hamiltonian → VQE/ADAPT-VQE**
workflow implemented in **Qiskit / Qiskit Nature**, with reproducible analysis and **paper-ready artifacts** committed under `docs/paper/`.

This repo is designed to be reproducible and “benchmark-first”:
- download raw datasets locally (**not committed**),
- parse to a normalized geometry JSONL format,
- run exact (small) vs VQE benchmarks (gated by qubit count),
- write machine-readable JSON outputs + human-readable tables/figures.

---

## Data policy

Raw datasets are downloaded locally via the CLI and stored under:

- `data/raw/<dataset>/...`

Raw datasets are **not committed** to Git. Parsed/processed geometry records are stored under:

- `data/processed/<dataset>/structures.jsonl`

**Important:** anything under a folder named `results/` is ignored by `.gitignore` (by design).  
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
### Auto active space (heuristic)
```bash
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2,CO,CO2 \
  --auto-active-space \
  --max-qubits 16 --exact-max-qubits 12 \
  --force
```
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
cat > mm_charges.csv <<'EOF'
x,y,z,q
0.0,0.0,2.0,0.5
EOF

python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset mor41 --basis sto3g \
  --records H2 \
  --mm-charges mm_charges.csv \
  --force
```
