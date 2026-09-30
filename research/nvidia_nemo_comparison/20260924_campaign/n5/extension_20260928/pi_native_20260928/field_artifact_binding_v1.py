"""Installed artifact configuration binding; README_FIELD_ARTIFACT_INSTALL_V1.md."""
from pathlib import Path
from field_artifact_limits_v1 import load, digest, planned_bytes


def bound_limits(root, contract):
    binding = contract.get('artifact_limits')
    if type(binding) is not dict or set(binding) != {'file', 'sha256', 'canonical_sha256', 'maximum_artifact_bytes'}:
        raise ValueError('Missing or invalid installed artifact binding')
    if binding['file'] != 'config/artifact_limits.json':
        raise ValueError('Unexpected installed artifact path')
    root = Path(root).resolve()
    path = root/binding['file']
    if path.is_symlink() or path.resolve().parent != root/'config':
        raise ValueError('Linked or escaped artifact configuration')
    limits = load(path, binding['sha256'])
    if digest(limits) != binding['canonical_sha256']:
        raise ValueError('Artifact canonical hash mismatch')
    if type(binding['maximum_artifact_bytes']) is not int or planned_bytes(limits) != binding['maximum_artifact_bytes']:
        raise ValueError('Artifact maximum byte accounting mismatch')
    if limits['pcm_max_frames'] < contract['maximum_recording_seconds']*16000:
        raise ValueError('Audio frame ceiling shorter than declared recording duration')
    if planned_bytes(limits) > contract['session_reservation_bytes']:
        raise ValueError('Artifact maxima exceed Start reservation')
    return limits
