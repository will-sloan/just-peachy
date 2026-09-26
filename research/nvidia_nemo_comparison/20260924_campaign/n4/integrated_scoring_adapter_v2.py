"""Pure evaluator reader for V2 method artifacts. README_SCORING_CLOCK_V2.md."""
import gzip
import hashlib
import json

from common import verify
from integrated_scoring_adapter import convert, read_component_events

LIMIT = 64 * 1024**2


def read_artifact(binding):
    """Verify bounded full content; do not import the predictor's writer module."""
    size = binding.get('expanded_bytes')
    if type(size) is not int or not 0 <= size <= LIMIT:
        raise ValueError('Invalid expanded method artifact size')
    verify(binding['compressed'])
    with gzip.open(binding['compressed']['path'], 'rb') as stream:
        data = stream.read(LIMIT + 1)
    if (len(data) != size or len(data) > LIMIT
            or hashlib.sha256(data).hexdigest() != binding['expanded_sha256']):
        raise ValueError('Expanded method artifact changed or exceeded bound')
    return json.loads(data)
