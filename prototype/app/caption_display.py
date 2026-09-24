"""Bounded GUI-only identity labels and conservative paragraph continuity.

No inference, audio, events or personal-store writes. See README_CAPTION_DISPLAY.md.
"""
from __future__ import annotations

import re


class IdentityLabels:
    """Never retain a contradicted name; pending cannot renew on partial revisions."""
    def __init__(self, pending_seconds=1.2, stable_seconds=.2):
        self.pending_seconds = pending_seconds
        self.stable_seconds = stable_seconds
        self.turns = {}
        self.candidates = {}

    def prune(self, rows):
        ids = {str(row['id']) for row in rows}
        turns = {self.turn_key(row) for row in rows}
        self.candidates = {k:v for k,v in self.candidates.items() if k in ids}
        self.turns = {k:v for k,v in self.turns.items() if k in turns}

    @staticmethod
    def turn_key(row):
        # S7 can replace a segment ID as support arrives. That must not restart
        # the pending deadline for the same utterance/epoch.
        return str(row.get('caption_key') or row['id'])

    def label(self, row, mode, now, numbered=False):
        if mode == 'caption_only':
            return 'Transcription'
        raw = str(row.get('label') or 'Unknown')
        # This mode explicitly promises a roster name, including a separately
        # marked display assumption. Open-mode pending/hysteresis must not hide it.
        if mode=='selected_closed' and row.get('closed_group_display') and row.get('display_profile_id'):
            return raw
        anonymous = bool(re.fullmatch(r'speaker[ _-]*\d+', raw, re.IGNORECASE))
        unknown = raw.casefold() in {'unknown', 'pending identity', 'unresolved', ''}
        if anonymous and (mode == 'enrolled_names' or not numbered):
            unknown = True
        rid = str(row['id'])
        first = self.turns.setdefault(self.turn_key(row), now)
        candidate = None if unknown else (raw, row.get('profile_id'), row.get('track_id'))
        old, since = self.candidates.get(rid, (None, now))
        if candidate != old:
            since = now
        self.candidates[rid] = (candidate, since)
        unavailable = row.get('identity_status') == 'unavailable'
        if unavailable:
            return 'Unknown · voice unavailable'
        if candidate is not None and now - since >= self.stable_seconds - 1e-9:
            return raw
        # Stable anonymous continuity is available but is intentionally generic
        # in the ordinary display. It does not need a pretend name lookup wait.
        if anonymous and mode == 'anonymous_conversation' and not numbered:
            return 'Unknown'
        if now - first >= self.pending_seconds - 1e-9:
            return 'Unknown'
        return '••• · collecting voice'


def continues(previous, current, previous_label, current_label):
    """Same supported person inside one native utterance; never name equality alone."""
    if not previous or current.get('handoff') or previous_label != current_label:
        return False
    if current_label.startswith(('Unknown', '•••')):
        return False
    if not current.get('caption_key') or previous.get('caption_key') != current['caption_key']:
        return False
    if previous.get('ownership_state') != 'supported_history' or current.get('ownership_state') != 'supported_history':
        return False
    a, b = previous.get('token_range'), current.get('token_range')
    if not a or not b or a[1] != b[0]:
        return False
    # A track is stronger continuity evidence than a coincidentally shared name;
    # session/utterance and contiguous ownership also have to agree.
    track = current.get('track_id')
    return track is not None and track == previous.get('track_id') and current.get('profile_id') == previous.get('profile_id')
