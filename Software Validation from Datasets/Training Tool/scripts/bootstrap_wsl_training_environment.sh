#!/usr/bin/env bash
set -euo pipefail

ICEFALL_COMMIT="3f848bb6d0acc970c9b294a30ca0a04a7c9c78d1"
ENV_ROOT="${JP_WSL_ENV_ROOT:-$HOME/.local/share/just-peachy/envs/original_adapter_training}"
ICEFALL_ROOT="${JP_ICEFALL_ROOT:-$HOME/.local/share/just-peachy/toolchains/icefall}"
REQUIREMENTS="${JP_REPO_ROOT:?JP_REPO_ROOT is required}/Software Validation from Datasets/Training Tool/requirements.original_adapter_training.txt"

python3.11 -m venv "$ENV_ROOT"
"$ENV_ROOT/bin/python" -m pip install --upgrade pip
"$ENV_ROOT/bin/python" -m pip install \
  torch==2.11.0 torchaudio==2.11.0 \
  --index-url https://download.pytorch.org/whl/cu126
"$ENV_ROOT/bin/python" -m pip install -r "$REQUIREMENTS"
"$ENV_ROOT/bin/python" -m pip install \
  'k2==1.24.4.dev20260625+cuda12.6.torch2.11.0' \
  -f https://k2-fsa.github.io/k2/cuda.html

if [[ ! -d "$ICEFALL_ROOT/.git" ]]; then
  mkdir -p "$(dirname "$ICEFALL_ROOT")"
  git clone https://github.com/k2-fsa/icefall.git "$ICEFALL_ROOT"
fi
git -C "$ICEFALL_ROOT" fetch --tags origin "$ICEFALL_COMMIT"
git -C "$ICEFALL_ROOT" checkout --detach "$ICEFALL_COMMIT"
test "$(git -C "$ICEFALL_ROOT" rev-parse HEAD)" = "$ICEFALL_COMMIT"
test -z "$(git -C "$ICEFALL_ROOT" status --short)"

"$ENV_ROOT/bin/python" - <<'PY'
import importlib.metadata as metadata
import torch

assert torch.cuda.is_available(), "CUDA is unavailable in the pinned environment"
for package in ("torch", "torchaudio", "k2", "lhotse", "sentencepiece", "pandas", "pyarrow"):
    print(f"{package}={metadata.version(package)}")
print(torch.cuda.get_device_name(0))
PY
