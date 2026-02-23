#!/usr/bin/env bash
set -euo pipefail

DATASET=${1:-mor41}
BASIS=${2:-sto3g}

# Safety: prevent BLAS/OpenMP runaway parallelism
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

# Ensure processed data exists (assumes dataset already downloaded; download step optional here)
python -m qmmm_vqe_biosim.datasets.parse --dataset "$DATASET" --force

# Benchmark: full for H2, active-space for CO/CO2 to keep qubits small
python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "$DATASET" --basis "$BASIS" \
  --records H2 \
  --force

python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "$DATASET" --basis "$BASIS" \
  --records CO \
  --active-electrons 4 --active-orbitals 4 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force

python -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "$DATASET" --basis "$BASIS" \
  --records CO2 \
  --active-electrons 4 --active-orbitals 4 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force

# Summarize
python -m qmmm_vqe_biosim.analysis.summarize --dataset "$DATASET" --basis "$BASIS"
