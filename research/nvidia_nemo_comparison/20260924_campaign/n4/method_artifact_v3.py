"""Lossless bounded method artifacts. See README_INTEGRATED_HISTORY_V3.md."""
import gzip
import hashlib
import json

from common import verify
from probe_component_s7 import save_private as original_save

LIMIT = 128 * 1024**2


def save_private(path, value):
    return original_save(path, value, limit=LIMIT)


def read_replay(binding):
    if type(binding.get('expanded_bytes')) is not int or not 0 <= binding['expanded_bytes'] <= LIMIT:
        raise ValueError('Method artifact declared expansion exceeds bound')
    verify(binding['compressed'])
    with gzip.open(binding['compressed']['path'], 'rb') as stream:
        raw = stream.read(LIMIT + 1)
    if (len(raw) > LIMIT or len(raw) != binding['expanded_bytes']
            or hashlib.sha256(raw).hexdigest() != binding['expanded_sha256']):
        raise ValueError('Method artifact expanded hash/size mismatch')
    return json.loads(raw)
