"""Injected stage only; invoked by host_operations.py, see README_HOST_OPERATIONS.md."""
import base64
import hashlib
import json

source = base64.b64decode(PAYLOAD['installer_source_base64'], validate=True)
if len(source) > 131072 or hashlib.sha256(source).hexdigest() != PAYLOAD['installer_source_sha256']:
    raise ValueError('Pinned bounded installer source required')
if BASELINE['boot_id'] != PAYLOAD['expected_boot_id']:
    raise ValueError('Current boot differs from reviewed staging admission')
if BASELINE['target_free_bytes'] < 5*1024**3 + PAYLOAD['target_reservation_bytes']:
    raise OSError('Independent staging reservation exceeds current free capacity')
namespace = dict(__name__='injected_candidate_installer')
exec(compile(source, '<pinned-candidate-installer>', 'exec'), namespace)
RESULT = namespace['stage_archive'](PAYLOAD['archive_base64'],
    PAYLOAD['archive_sha256'], PAYLOAD['manifest_sha256'])
RESULT['purpose'] = 'PREPARED_PACKAGE_STAGED_FOR_NATIVE_COMPONENT_CHECKS'
RESULT['native_models_started'] = False
RESULT['desktop_changed'] = False
