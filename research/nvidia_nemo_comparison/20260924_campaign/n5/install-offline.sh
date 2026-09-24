#!/usr/bin/env bash
# Ordinary-user offline install; README.md and INSTALL_CM5.md explain prerequisites.
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo 'Usage: bash install-offline.sh INSTALL_ROOT EXTERNAL_DATA_ROOT [--activate]' >&2
  exit 2
fi
if [[ $# -eq 3 && "$3" != --activate ]]; then exit 2; fi
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3.11 "$here/bootstrap/verify_bundle.py" --root "$here"
archive="$(python3.11 -c 'import json,sys; print(json.load(open(sys.argv[1]))["application_archive"])' "$here/BUNDLE_MANIFEST.json")"
checksum="$(python3.11 -c 'import json,sys; print(json.load(open(sys.argv[1]))["application_sha256"])' "$here/BUNDLE_MANIFEST.json")"
args=(--archive "$here/$archive" --sha256 "$checksum" --root "$1" --data-root "$2"
      --wheelhouse "$here/wheelhouse" --models "$here/models")
if [[ $# -eq 3 ]]; then args+=(--activate); fi
exec bash "$here/bootstrap/install_pi.sh" "${args[@]}"
