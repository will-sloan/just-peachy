#!/usr/bin/env bash
# Prepare the isolated Stage 8 NeMo candidate environment on a Linux/CUDA host.

set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "[BLOCKED] The nemo-linux-cuda profile must be prepared on Linux." >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/.." && pwd)"
python_command="${STAGE8_PYTHON:-python3.12}"
environment_path="${project_root}/.stage8-envs/nemo-linux-cuda"
environment_python="${environment_path}/bin/python"
requirements_path="${project_root}/requirements/stage8/nemo-linux-cuda.txt"

if ! command -v "${python_command}" >/dev/null 2>&1; then
  echo "[BLOCKED] ${python_command} is not available. Set STAGE8_PYTHON to Python 3.12." >&2
  exit 2
fi

"${python_command}" -c 'import sys; assert sys.version_info[:2] == (3, 12), sys.version'
"${python_command}" -m venv "${environment_path}"

# The wheel pair is isolated and pinned. This does not alter the Stage 0-7 core
# environment or claim NeMo compatibility before the real qualifier passes.
"${environment_python}" -m pip install \
  torch==2.11.0 torchaudio==2.11.0 \
  --index-url https://download.pytorch.org/whl/cu128
"${environment_python}" -m pip install -r "${requirements_path}"
"${environment_python}" -m pip check
"${environment_python}" -m pip freeze --all > "${environment_path}/environment.freeze.txt"

"${environment_python}" -c \
  'import torch; assert torch.cuda.is_available(), "CUDA is unavailable"; print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))'

echo "[PASS] NeMo candidate environment prepared at ${environment_path}"
echo "[NEXT] Acquire and hash the selected local checkpoints, then run the Stage 8 qualifier."
