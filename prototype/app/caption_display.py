"""Bounded GUI-only identity labels and conservative paragraph continuity.

No inference, audio, events or personal-store writes. See README_CAPTION_DISPLAY.md.
"""
from __future__ import annotations

import re


def active_caption_rows(rows):
    """Latest turn plus overlapping unfinished turns; timestamped EVENT data only.

    Source windows can be coarse ASR revision windows. Their overlap is a display
    grouping hint, never a claim of phonetic timing or simultaneous speech truth.
    Full rows remain in the independently scrollable transcript history.
    """
    if not rows:
        return []
    latest = rows[-1]
    key = lambda row: str(row.get('caption_key') or row['id'])
    latest_key = key(latest)
    peers = {latest_key}
    start, end = latest.get('source_start_sec'), latest.get('source_end_sec')
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        for row in rows:
            a, b = row.get('source_start_sec'), row.get('source_end_sec')
            if (not row.get('final') and isinstance(a, (int, float)) and isinstance(b, (int, float))
                    and max(start, a) < min(end, b)):
                peers.add(key(row))
    return [row for row in rows if key(row) in peers]


class ActiveCaptionPane:
    """Stable marked rows in a fixed active pane; revise only the changed suffix."""
    def __init__(self, text):
        self.text = text
        self.marks = {}
        self.values = {}
        self.order = []
        self.sequence = 0
        self.follow = True
        self.edits = 0
        self.initialized = False

    def render(self, rows, values, placeholder):
        ids = [str(row['id']) for row in rows]
        current = {rid: values[rid] for rid in ids}
        if self.initialized and ids == self.order and current == self.values:
            return
        self.initialized = True
        text = self.text
        view = text.yview()
        text.configure(state='normal')
        for rid in list(self.order):
            if rid not in current:
                start, end = self.marks.pop(rid)
                text.delete(start, end)
                text.mark_unset(start, end)
                self.order.remove(rid)
        if not ids:
            text.delete('1.0', 'end')
            text.insert('1.0', placeholder, 'placeholder')
        else:
            if not self.order:
                text.delete('1.0', 'end')
            for index, rid in enumerate(ids):
                if rid in self.marks and self.order.index(rid) != index:
                    start, end = self.marks.pop(rid)
                    text.delete(start, end)
                    text.mark_unset(start, end)
                    self.order.remove(rid)
                next_id = self.order[index] if rid not in self.marks and index < len(self.order) else (
                    self.order[index+1] if rid in self.marks and index+1 < len(self.order) else None)
                next_start = self.marks[next_id][0] if next_id else None
                if rid in self.marks and self.values.get(rid) == current[rid]:
                    continue
                if rid not in self.marks:
                    self.sequence += 1
                    start, end = f'active_{self.sequence}_start', f'active_{self.sequence}_end'
                    text.mark_set(start, next_start or 'end-1c')
                    text.mark_gravity(start, 'left')
                    text.mark_set(end, start)
                    self.marks[rid] = start, end
                    self.order.insert(index, rid)
                else:
                    start, end = self.marks[rid]
                if next_start:
                    text.mark_gravity(next_start, 'right')
                label, caption, selected = current[rid]
                replacement = (label+'\n' if label else '') + caption + '\n'
                before = text.get(start, end)
                prefix = 0
                while prefix < min(len(before), len(replacement)) and before[prefix] == replacement[prefix]:
                    prefix += 1
                chars = lambda value: int(text.tk.call('string', 'length', value))
                edit_start = f'{start}+{chars(before[:prefix])}c'
                text.mark_gravity(end, 'right')
                text.delete(edit_start, end)
                text.insert(edit_start, replacement[prefix:])
                self.edits += 1
                text.mark_gravity(end, 'left')
                for tag in ('speaker', 'pending', 'selected'):
                    text.tag_remove(tag, start, end)
                if label:
                    text.tag_add('speaker', start, f'{start}+{chars(label)}c')
                if label.startswith('•••'):
                    text.tag_add('pending', start, f'{start}+3c')
                if selected:
                    text.tag_add('selected', start, end)
                if next_start:
                    text.mark_gravity(next_start, 'left')
        self.order, self.values = ids, current
        text.configure(state='disabled')
        if self.follow:
            text.see('end-1c')
        else:
            text.yview_moveto(view[0])


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
