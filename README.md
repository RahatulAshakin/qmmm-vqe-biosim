# qmmm-vqe-biosim

Benchmark-gated QM → active space → qubit Hamiltonian → VQE/ADAPT-VQE workflow,
implemented in Qiskit/Qiskit Nature, with reproducible analysis outputs.

## Data policy
Raw datasets are downloaded locally via scripts and are not committed to Git.

## Reproducibility
See environment setup files committed in this repo.

## VQE Ground-State Example
Run a VQE smoke calculation for a processed geometry record:

```bash
python -m qmmm_vqe_biosim.quantum.run_vqe --dataset mor41 --record H2 --basis sto3g
```

This writes JSON output to `results/vqe/mor41/H2_sto3g.json`.
