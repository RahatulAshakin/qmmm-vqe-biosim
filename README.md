# qmmm-vqe-biosim

Benchmark-gated QM → active space → qubit Hamiltonian → VQE/ADAPT-VQE workflow,
implemented in Qiskit/Qiskit Nature, with reproducible analysis outputs.

## Data policy
Raw datasets are downloaded locally via scripts and are not committed to Git.

## Reproducibility
See environment setup files committed in this repo.

## VQE Ground-State Example
Run a VQE smoke calculation for a processed geometry record:

## Quickstart (MOR41 small benchmark)

```bash
# 1) Create env
conda env create -f environment.yml
conda activate qmmm-vqe-biosim

# 2) Install package
python -m pip install -e .

# 3) Download + parse MOR41
python -m qmmm_vqe_biosim.datasets.download --dataset mor41
python -m qmmm_vqe_biosim.datasets.parse --dataset mor41 --force

# 4) Run small benchmark (H2 full; CO/CO2 active-space)
./scripts/run_mor41_smallset.sh mor41 sto3g

# 5) View summary
sed -n '1,20p' results/benchmark/mor41/sto3g/summary.csv
```

This writes JSON output to `results/vqe/mor41/H2_sto3g.json`.
