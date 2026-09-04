#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${JP_REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../../../.." && pwd)}"
TOOL_ROOT="${REPO_ROOT}/Software Validation from Datasets/Evaluation Tool"
PREFIX="${JP_H2_PREFIX:-/opt/just-peachy-h2}"
PYTHON_BIN="${JP_H2_PYTHON:-${PREFIX}/venv/bin/python}"
ASSET_ROOT="${JP_H2_ASSET_ROOT:-${PREFIX}/models}"
RESULTS_ROOT="${JP_H2_RESULTS_ROOT:-/var/lib/just-peachy/h2_sessions}"
ENROLLMENT_ROOT="${JP_H2_ENROLLMENT_ROOT:-/var/lib/just-peachy/h2_enrollment}"
PIPELINE_ID="${JP_H2_PIPELINE_ID:-fullpipe_v1_ag_dr_ir}"
PRODUCT_MODE="${JP_H2_PRODUCT_MODE:-H2_SESSION_MEMORY_ENHANCED}"
SESSION_SECONDS="${JP_H2_SESSION_SECONDS:-86400}"
REDIM_SHA256="5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609"
SEGMENTATION_SHA256="b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "H2 Python environment is unavailable: ${PYTHON_BIN}" >&2
  exit 2
fi

"${PYTHON_BIN}" "${SCRIPT_DIR}/validate_arm64_package.py" \
  --asset-root "${ASSET_ROOT}" --require-linux-arm64

export JP_REPO_ROOT="${REPO_ROOT}"
export JP_MODEL_ROOT="${ASSET_ROOT}"
export JP_H2_REDIM_ONNX="${ASSET_ROOT}/h2_onnx/redimnet2_b2_fp32.onnx"
export JP_H2_SEGMENTATION_ONNX="${ASSET_ROOT}/h2_onnx/pyannote_segmentation_3_0_fp32.onnx"
export JP_H2_ONNX_WORKER_PYTHON="${PYTHON_BIN}"
export JP_H2_ASR_WORKER_PYTHON="${PYTHON_BIN}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
mkdir -p -- "${RESULTS_ROOT}" "${ENROLLMENT_ROOT}"
cd -- "${TOOL_ROOT}"
SESSION_ID="h2_portable_$(date -u +%Y%m%dT%H%M%SZ)_$$"

ARGS=(
  -m app.h2_portability runtime-live
  --pipeline-id "${PIPELINE_ID}"
  --product-mode "${PRODUCT_MODE}"
  --duration-sec "${SESSION_SECONDS}"
  --session-id "${SESSION_ID}"
  --output-root "${RESULTS_ROOT}/${SESSION_ID}"
  --enrollment-root "${ENROLLMENT_ROOT}"
  --redim-onnx "${JP_H2_REDIM_ONNX}"
  --redim-sha256 "${REDIM_SHA256}"
  --segmentation-onnx "${JP_H2_SEGMENTATION_ONNX}"
  --segmentation-sha256 "${SEGMENTATION_SHA256}"
)
if [[ -n "${JP_H2_AUDIO_DEVICE:-}" ]]; then
  ARGS+=(--device "${JP_H2_AUDIO_DEVICE}")
fi

# The common factory now consumes the explicit H2_PORTABLE_ONNX_FP32 profile.
# This launch remains PORT_REQUIRES_WORK until real ARM64 validation proves
# wheel compatibility, audio capture, resource use, restart, and recovery.
exec "${PYTHON_BIN}" "${ARGS[@]}"
