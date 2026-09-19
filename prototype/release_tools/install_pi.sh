#!/usr/bin/env bash
# Non-root offline installer. Read README.md and PI_DEPLOYMENT_WORKFLOW.md.
set -euo pipefail
archive='' checksum='' root='' data_root='' wheelhouse='' models='' activate=0
while (($#)); do
  case "$1" in
    --archive) archive="$2"; shift 2 ;;
    --sha256) checksum="$2"; shift 2 ;;
    --root) root="$2"; shift 2 ;;
    --data-root) data_root="$2"; shift 2 ;;
    --wheelhouse) wheelhouse="$2"; shift 2 ;;
    --models) models="$2"; shift 2 ;;
    --activate) activate=1; shift ;;
    *) printf '{"status":"FAIL","error":"Unknown or missing argument"}\n' >&2; exit 2 ;;
  esac
done
if [[ -z "$archive" || -z "$checksum" || -z "$root" || -z "$data_root" ]]; then
  printf '{"status":"FAIL","error":"Required: --archive --sha256 --root --data-root"}\n' >&2; exit 2
fi
if [[ "$EUID" -eq 0 ]]; then printf '{"status":"FAIL","error":"Use the ordinary non-root desktop user"}\n' >&2; exit 2; fi
if [[ "$(uname -m)" != aarch64 && "$(uname -m)" != arm64 ]]; then printf '{"status":"FAIL","error":"Expected Linux ARM64; no runtime installed"}\n' >&2; exit 2; fi
python3.11 -c 'import sys; assert sys.version_info[:2] == (3,11)'
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
stage_json="$(python3.11 "$here/release.py" stage --archive "$archive" --root "$root" --sha256 "$checksum")"
printf '%s\n' "$stage_json"
version="$(printf '%s' "$stage_json" | python3.11 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
release="$root/releases/$version"
runtime="$root/runtimes/$version"
if [[ -n "$wheelhouse" ]]; then
  if [[ ! -x "$runtime/bin/python" ]]; then python3.11 -m venv "$runtime"; fi
  "$runtime/bin/python" -m pip install --no-index --find-links "$wheelhouse" --require-hashes -r "$release/release_tools/requirements-arm64.lock"
fi
if [[ -n "$models" ]]; then python3.11 "$here/release.py" import-models --release "$release" --source-models "$models" --target-models "$root/models"; fi
if [[ -x "$runtime/bin/python" ]]; then
  "$runtime/bin/python" "$here/release.py" healthcheck --root "$root" --data-root "$data_root" --version "$version" --models --imports
else
  python3.11 "$here/release.py" healthcheck --root "$root" --data-root "$data_root" --version "$version"
  if [[ "$activate" -eq 1 ]]; then printf '{"status":"FAIL","error":"No per-release runtime; supply offline wheelhouse before activation"}\n' >&2; exit 2; fi
fi
if [[ "$activate" -eq 1 ]]; then
  python3.11 "$here/release.py" activate --root "$root" --data-root "$data_root" --version "$version" --require-assets
  "$runtime/bin/python" "$here/release.py" healthcheck --root "$root" --data-root "$data_root" --models --imports
fi
printf '{"status":"INSTALL_FINISHED","gui_started":false,"hardware_qualified":false}\n'
