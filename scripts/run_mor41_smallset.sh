#!/usr/bin/env bash
set -euo pipefail

DATASET=${1:-mor41}
BASIS=${2:-sto3g}

# Force thread limits (do NOT inherit possibly-corrupt values)
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1

run() {
  echo ""
  echo "+ $*"
  "$@"
}

run_pinned() {
  # Pin again at process start (some libs read env only at startup)
  env \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    "$@"
}

retry_once() {
  # retry once on failure (e.g., transient BLAS/WSL crash)
  if run_pinned "$@"; then
    return 0
  fi
  echo "!! Command failed; retrying once: $*"
  sleep 2
  run_pinned "$@"
}

# Ensure processed data exists
run python -m qmmm_vqe_biosim.datasets.parse --dataset "$DATASET" --force

# H2 full benchmark
run_pinned python -X faulthandler -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "$DATASET" --basis "$BASIS" \
  --records H2 \
  --force

# CO active-space benchmark
retry_once python -X faulthandler -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "$DATASET" --basis "$BASIS" \
  --records CO \
  --active-electrons 4 --active-orbitals 4 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force

# CO2 active-space benchmark
retry_once python -X faulthandler -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "$DATASET" --basis "$BASIS" \
  --records CO2 \
  --active-electrons 4 --active-orbitals 4 \
  --max-qubits 16 --exact-max-qubits 12 \
  --force

# Summarize
run python -m qmmm_vqe_biosim.analysis.summarize --dataset "$DATASET" --basis "$BASIS"
