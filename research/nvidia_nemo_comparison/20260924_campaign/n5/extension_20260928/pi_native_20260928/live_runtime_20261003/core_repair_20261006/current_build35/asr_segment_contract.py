"""Explicit native-resource versus spoken-utterance boundary contract.

Pure helper for the pinned Giga BPE recognizer; no models, audio or native API
mutation. Integration is intentionally separate. See README_ASR_SEGMENTS.md.
"""
from __future__ import annotations

import math
import hashlib
import json


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Finite nonnegative source seconds required')
    return value


def boundary_kind(*, source_start_sec, source_end_sec, native_endpoint,
                  stop=False, native_resource_seconds=20.0, advisory_endpoint=False):
    """Classify conservatively without inventing a native endpoint reason.

    A boolean endpoint at/after the native length threshold may also coincide
    with silence. Treat it as a resource boundary; a later short-stream silence
    endpoint or explicit Stop can close the spoken group. These are source
    window clocks, not new phonetic alignment or measurements of silence.
    """
    start, end = _seconds(source_start_sec), _seconds(source_end_sec)
    if (end < start or type(native_endpoint) is not bool or type(stop) is not bool
            or type(advisory_endpoint) is not bool):
        raise ValueError('Ordered source interval and exact boundary booleans required')
    limit = _seconds(native_resource_seconds)
    if limit <= 0:
        raise ValueError('Positive native resource interval required')
    if stop:
        return 'stop'
    if not native_endpoint:
        return 'advisory' if advisory_endpoint else None
    return 'resource' if end - start + 1e-9 >= limit else 'native_pause'


def bpe_text(tokens):
    """Decode the pinned English vocabulary's explicit word-start markers.

    No suffix/prefix matching or global text deduplication. Every actual token
    occurrence is included exactly once, including genuine repeated words.
    """
    if not isinstance(tokens, (tuple, list)) or any(type(token) is not str or not token for token in tokens):
        raise ValueError('An actual native BPE token list is required')
    return ''.join(tokens).replace('\u2581', ' ').strip()


def join_raw_parts(parts):
    """Join recorded pieces only using their explicitly supplied native joiner."""
    result = ''
    for index, part in enumerate(parts):
        value = part.get('raw_asr_text')
        joiner = part.get('leading_text_joiner', ' ')
        if type(value) is not str or joiner not in ('', ' '):
            raise ValueError('Raw native text and an explicit valid joiner required')
        result += (joiner if index else '') + value
    return result


class NativeSegmentContract:
    """Constant-count metadata state; never accumulate the session's transcript.

    The caller persists each piece and its partial revisions using stable native
    segment IDs. This helper retains only the current segment's contract and the
    immediately preceding boundary. The existing native decoder resource reset
    remains responsible for bounding its token history.
    """
    def __init__(self, *, native_resource_seconds=20.0):
        self.native_resource_seconds = _seconds(native_resource_seconds)
        if self.native_resource_seconds <= 0:
            raise ValueError('Positive native resource interval required')
        self.group_number = 0
        self.current_segment = None
        self.current_contract = None
        self.previous_boundary = None
        self.previous_source_end = None

    def observe(self, *, segment_id, raw_text, tokens, source_start_sec,
                source_end_sec, native_endpoint=False, stop=False, advisory_endpoint=False):
        if type(segment_id) is not str or not segment_id or type(raw_text) is not str:
            raise ValueError('Stable native segment ID and unchanged raw text required')
        start, end = _seconds(source_start_sec), _seconds(source_end_sec)
        if end < start:
            raise ValueError('Ordered native source window required')
        if bpe_text(tokens) != raw_text.strip():
            raise ValueError('Native token/text mismatch; this pinned BPE contract cannot be assumed')
        kind = boundary_kind(source_start_sec=start, source_end_sec=end,
                             native_endpoint=native_endpoint, stop=stop,
                             native_resource_seconds=self.native_resource_seconds,
                             advisory_endpoint=advisory_endpoint)
        token_digest = hashlib.sha256(json.dumps([raw_text,tokens],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        new_segment = segment_id != self.current_segment
        if new_segment:
            if self.current_segment is not None and self.previous_boundary is None:
                raise ValueError('A new native segment needs the preceding reset boundary')
            if self.previous_source_end is not None and start < self.previous_source_end - 1e-9:
                raise ValueError('Native segment source windows cannot go backwards')
            if self.previous_boundary in ('native_pause', 'advisory', 'stop'):
                self.group_number += 1
            self.current_segment = segment_id
            self.current_contract = dict(utterance_group_id='spoken:'+str(self.group_number),
                                         native_segment_id=segment_id,
                                         leading_text_joiner=' ',
                                         _after_resource=self.previous_boundary == 'resource')
            self.previous_boundary = None
        else:
            prior = self.current_contract
            if start != prior['source_start_sec'] or end < prior['source_end_sec']:
                raise ValueError('A native partial revision must retain its source start and advance its end')
            if self.previous_boundary is not None:
                if (end == prior['source_end_sec'] and kind == self.previous_boundary
                        and token_digest == prior['_token_digest']):
                    return {key:value for key,value in prior.items() if not key.startswith('_')}
                raise ValueError('A sealed native segment cannot receive a later partial or conflicting final')
        # The first result after a resource reset may contain no token. Wait for
        # the first actual token before fixing its lexical joiner. No word guess.
        if tokens and not self.current_contract.get('_first_token_observed'):
            continuation = self.current_contract.pop('_after_resource', False)
            self.current_contract['leading_text_joiner'] = '' if continuation and not tokens[0].startswith('\u2581') else ' '
            self.current_contract['_first_token_observed'] = True
        self.current_contract.update(source_start_sec=start, source_end_sec=end,
                                     _token_digest=token_digest,
                                     recognition_segment_final=kind is not None,
                                     utterance_final=kind in ('native_pause', 'advisory', 'stop'),
                                     endpoint_kind=kind)
        if kind:
            self.previous_boundary = kind
            self.previous_source_end = end
        return {key:value for key,value in self.current_contract.items() if not key.startswith('_')}

    def begin_after_reset(self, *, segment_id, raw_text, tokens, source_start_sec,
                          source_end_sec, native_endpoint=False, stop=False):
        """Observe the next segment while retaining whether its word can continue."""
        if segment_id == self.current_segment:
            raise ValueError('The new native segment needs a distinct stable ID')
        return self.observe(segment_id=segment_id, raw_text=raw_text, tokens=tokens,
                            source_start_sec=source_start_sec, source_end_sec=source_end_sec,
                            native_endpoint=native_endpoint, stop=stop)
