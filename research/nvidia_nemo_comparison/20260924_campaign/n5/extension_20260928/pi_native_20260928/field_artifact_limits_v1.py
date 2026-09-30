"""Explicit artifact contract; see README_FIELD_ARTIFACT_LIMITS_V1.md."""
import hashlib
import json
from pathlib import Path

MIB = 1024**2
SCHEMA = 'just-peachy.artifact-limits.v1'
DEFAULT = dict(schema=SCHEMA, native_journal_bytes=8*MIB,
               conversation_journal_bytes=8*MIB, pcm_max_frames=960000,
               sample_rate=16000, interchange='UNQUALIFIED_FOR_EXTENDED_ARCHIVES')


def validate(value):
    if type(value) is not dict or set(value) != set(DEFAULT):
        raise ValueError('Artifact contract fields must be exact')
    if value['schema'] != SCHEMA or value['interchange'] != DEFAULT['interchange']:
        raise ValueError('Unknown artifact schema or interchange claim')
    if type(value['sample_rate']) is not int or value['sample_rate'] != 16000:
        raise ValueError('Artifact source must be mono16k')
    for key in ('native_journal_bytes', 'conversation_journal_bytes'):
        if type(value[key]) is not int or not 1024 <= value[key] <= 16*MIB:
            raise ValueError('Explicit journal ceiling is 16MiB')
    if type(value['pcm_max_frames']) is not int or not 0 < value['pcm_max_frames'] <= 2080000:
        raise ValueError('Explicit audio ceiling is 130 seconds')
    return dict(value)


def resolved(value=None):
    return validate(DEFAULT if value is None else value)


def digest(value):
    return hashlib.sha256(json.dumps(validate(value), sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(path, expected_sha256):
    path = Path(path)
    if path.stat().st_size > 4096:
        raise ValueError('Artifact contract too large')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('Artifact contract file hash mismatch')
    return validate(json.loads(data))


def planned_bytes(value):
    """Artifact maxima only; callers must also reserve source/metadata/code space."""
    value = validate(value)
    return value['native_journal_bytes'] + value['conversation_journal_bytes'] + 6*value['pcm_max_frames'] + 44
