# qmmm-vqe-biosim

Benchmark-gated **geometry → electronic structure → (optional) active space → qubit Hamiltonian → VQE**
workflow implemented with **Qiskit / Qiskit Nature**.

This repo is designed to be reproducible and “benchmark-first”:
- download raw datasets locally (not committed),
- parse to a normalized geometry JSONL format,
- run exact (small) vs VQE benchmarks (gated by qubit count),
- write machine-readable JSON outputs + human-readable summaries.

## What’s implemented

### Datasets
- Dataset registry + downloader:
  - `mor41` (tar.gz)
  - `rost61` (tar.gz)
  - `mme55` (git repo)
  - `tmqm` (git repo)

Raw data is stored under:
- `data/raw/<dataset>/...`

A `manifest.json` is written after download with artifact hashes.

### Parsers → normalized schema
Parsers convert raw dataset layouts into:
- `data/processed/<dataset>/structures.jsonl`

Each line is a normalized record containing:
- `record_id`, `atoms`, `coords_angstrom`
- `source_path`
- (when available) `charge`, `multiplicity`
- optional comment metadata

Implemented parsers:
- MOR41: reads `mol.xyz`
- ROST61: reads `mol.xyz` + metadata from `.CHRG` and `.UHF`
- MME55: reads `struc.xyz` (+ metadata where available)

### Quantum / chemistry
- Exact ground-state solve (small problems)
- VQE ground-state solve (UCCSD + SLSQP + parity mapper)
- Results written to JSON under `results/`

### Benchmarking
`analysis.benchmark` runs:
- exact solve (up to `--exact-max-qubits`)
- VQE solve (up to `--max-qubits`)
- optional active-space reduction via user-specified `(active_electrons, active_orbitals)`

Per-record outputs:
- `results/benchmark/<dataset>/<basis>/<record>.json`

### Summaries
`analysis.summarize` reads benchmark JSON files and writes:
- `summary.csv`
- `summary.json`

and prints a compact table to the console.

### Reproducibility / stability
- Thread limits are supported (important on WSL): `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`.
- Example outputs are included under `docs/examples/` (small only).

## Data policy
Raw datasets are downloaded locally and are **not committed** to Git.
Only small example outputs (CSV/JSON summaries) may be committed under `docs/examples/`.

---

## VQE Ground-State Example
Run a VQE smoke calculation for a processed geometry record:

```bash
python -m qmmm_vqe_biosim.quantum.run_vqe --dataset mor41 --record H2 --basis sto3g
```

This writes JSON output to `results/vqe/mor41/H2_sto3g.json`.
