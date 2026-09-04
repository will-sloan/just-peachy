#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../../.." && pwd)"
PREFIX="${JP_H2_PREFIX:-/opt/just-peachy-h2}"
PYTHON_BIN="${JP_H2_PYTHON:-python3.12}"
WHEELHOUSE=""
INSTALL_SYSTEM_DEPS=0

usage() {
  echo "Usage: $0 [--prefix PATH] [--python PATH] [--wheelhouse PATH] [--system-deps]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --wheelhouse) WHEELHOUSE="$2"; shift 2 ;;
    --system-deps) INSTALL_SYSTEM_DEPS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer requires Linux." >&2
  exit 2
fi
case "$(uname -m)" in
  aarch64|arm64) ;;
  *) echo "This package targets Linux ARM64; observed $(uname -m)." >&2; exit 2 ;;
esac

if [[ ${INSTALL_SYSTEM_DEPS} -eq 1 ]]; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    alsa-utils libasound2 libgomp1 libopenblas0-pthread libportaudio2 \
    libsndfile1 portaudio19-dev python3-tk
fi

"${PYTHON_BIN}" -c 'import sys; assert sys.version_info[:2] == (3, 12), sys.version'
mkdir -p -- "${PREFIX}"
"${PYTHON_BIN}" -m venv "${PREFIX}/venv"
VENV_PYTHON="${PREFIX}/venv/bin/python"
"${VENV_PYTHON}" -m pip install --upgrade "pip==24.2"

PIP_SOURCE=()
if [[ -n "${WHEELHOUSE}" ]]; then
  PIP_SOURCE=(--no-index --find-links "${WHEELHOUSE}")
fi
"${VENV_PYTHON}" -m pip install --only-binary=:all: \
  "${PIP_SOURCE[@]}" -r "${SCRIPT_DIR}/requirements-linux-arm64.txt"

echo "Dependencies installed. No model was downloaded."
echo "Stage checksum-matching assets under ${PREFIX}/models, then run:"
echo "  ${VENV_PYTHON} ${SCRIPT_DIR}/validate_arm64_package.py --asset-root ${PREFIX}/models --require-linux-arm64"
