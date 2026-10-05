"""Read current deployment/resources before restoration. See README.md."""
import hashlib
from pathlib import Path

ROOT = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-17')
expected = '35cd64d5d92e6f2d19dc753b889000dc68428563fa7ce6e4da8590f27b3e6494'
if hashlib.sha256((ROOT/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest() != expected:
    raise ValueError('Current build17 rollback package differs')
RESULT = dict(status='CURRENT_ROLLBACK_PACKAGE_VERIFIED', target=str(ROOT),
    package_manifest_sha256=expected, current_native_preflight=BASELINE,
    capture_started=False, model_loaded=False, files_changed=False)
