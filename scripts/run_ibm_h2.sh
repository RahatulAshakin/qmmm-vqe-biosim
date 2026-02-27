#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

DATASET="mor41"
BASIS="sto3g"
RECORD="H2"
IBM_BACKEND="${1:-ibm_kyoto}"
OUT_DIR="docs/paper/mor41_sto3g/json/ibm_runtime_h2"

# IBM Runtime job mode requires channel/token/instance or a saved account.
export QISKIT_IBM_CHANNEL="${QISKIT_IBM_CHANNEL:-ibm_quantum_platform}"

mkdir -p "${OUT_DIR}"

python -X faulthandler -m qmmm_vqe_biosim.analysis.benchmark \
  --dataset "${DATASET}" \
  --basis "${BASIS}" \
  --records "${RECORD}" \
  --backend ibm \
  --ibm-backend "${IBM_BACKEND}" \
  --shots 4096 \
  --out "${OUT_DIR}" \
  --force

echo "Wrote benchmark JSON: ${OUT_DIR}/${RECORD}.json"
