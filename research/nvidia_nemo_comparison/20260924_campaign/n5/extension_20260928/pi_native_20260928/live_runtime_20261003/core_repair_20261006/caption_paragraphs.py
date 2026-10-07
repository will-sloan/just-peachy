"""Pure display paragraphs over current, authoritative caption spans.

No model, text correction, deduplication or phonetic alignment is performed.
Original spans and their source intervals remain attached to every paragraph.
See README_CAPTION_REPAIR.md for inputs, outputs and regression commands.
"""
from __future__ import annotations

import math


def parent_key(row):
    return str(row.get('caption_key') or row.get('utterance_id') or row['id'])


def _interval(row):
    start, end = row.get('source_start_sec'), row.get('source_end_sec')
    if (type(start) not in (int, float) or type(end) not in (int, float)
            or not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start):
        return None
    return start, end


def _tokens_adjacent(previous, current):
    a, b = previous.get('token_range'), current.get('token_range')
    return (parent_key(previous) == parent_key(current)
            and isinstance(a, (list, tuple)) and isinstance(b, (list, tuple))
            and len(a) == len(b) == 2 and a[1] == b[0])


def _supported_track(row):
    # An internal physical track can support an Unknown paragraph. A displayed
    # roster assumption or an equal name cannot establish that continuity.
    track = row.get('track_id')
    if track in (None, '') or row.get('ownership_state') != 'supported_history':
        return None
    return track


def _text(row):
    if row.get('final') and row.get('final_punctuated_display_text'):
        return str(row['final_punctuated_display_text']).strip()
    value = row.get('provisional_display_text')
    return str(value if value is not None else row.get('raw_asr_text') or '').strip()


def _unattributed(row):
    return (row.get('track_id') in (None,'') and row.get('profile_id') in (None,'')
            and row.get('display_profile_id') in (None,'') and not row.get('closed_group_display')
            and row.get('label') in ('Unknown','Pending identity'))


def source_order_rows(rows):
    """Native parent order, then explicit token order inside coarse windows.

    Individual span starts may honestly fall back to the parent's source start.
    Sorting those starts can move a later token before an earlier one. This is
    a bounded display view and never changes any original source interval.
    """
    indexed = list(enumerate(rows))
    anchors = {}
    for index,row in indexed:
        key = (row.get('session_id'),parent_key(row))
        interval = _interval(row)
        anchor = row.get('_parent_source_start_sec')
        if type(anchor) not in (int,float) or not math.isfinite(anchor) or anchor < 0:
            anchor = interval[0] if interval else float('inf')
        anchors[key] = min(anchors.get(key,float('inf')),anchor)
    def order(item):
        index,row = item
        key = (row.get('session_id'),parent_key(row))
        tokens = row.get('token_range')
        ordinal = tokens[0] if (isinstance(tokens,(list,tuple)) and len(tokens)==2
                               and type(tokens[0]) is int and tokens[0]>=0) else index
        return (anchors[key],str(key[0]),key[1],ordinal,index)
    return [row for index,row in sorted(indexed,key=order)]


def _continues(previous, current, mode, gap_seconds):
    if (current.get('handoff') or current.get('_paragraph_break')
            or current.get('session_id') != previous.get('session_id')):
        return False
    a, b = _interval(previous), _interval(current)
    if a is None or b is None or b[0] - a[1] > gap_seconds:
        return False
    adjacent = _tokens_adjacent(previous, current)
    if b[0] < a[0] and not adjacent:
        return False
    if mode == 'caption_only':
        return True
    # A real BPE continuation belongs to one lexical word. Keeping it readable
    # does not establish speaker continuity; the paragraph below renders an
    # Unknown heading if the word straddles conflicting attribution spans.
    if (current.get('leading_text_joiner') == '' and current.get('utterance_group_id')
            and current.get('utterance_group_id') == previous.get('utterance_group_id')):
        return True
    a_track, b_track = _supported_track(previous), _supported_track(current)
    if a_track is not None or b_track is not None:
        return (a_track is not None and a_track == b_track
                and previous.get('profile_id') == current.get('profile_id')
                and previous.get('display_profile_id') == current.get('display_profile_id')
                and previous.get('label') == current.get('label')
                and bool(previous.get('closed_group_display')) == bool(current.get('closed_group_display')))
    if _unattributed(previous) and _unattributed(current):
        # Presentation grouping of unassigned text makes no claim that the
        # source spans belong to the same biometric speaker.
        return True
    # A pending tail is allowed to revise within its native parent. It must not
    # bridge different anonymous tracks or infer a speaker across utterances.
    return (adjacent and previous.get('track_id') == current.get('track_id')
            and previous.get('profile_id') == current.get('profile_id')
            and previous.get('display_profile_id') == current.get('display_profile_id')
            and previous.get('label') == current.get('label')
            and previous.get('identity_status') == current.get('identity_status'))


def _paragraph(parts):
    first, last = parts[0], parts[-1]
    result = dict(first)
    token_range = first.get('token_range')
    anchor = token_range[0] if isinstance(token_range, (list, tuple)) and len(token_range) == 2 else 'start'
    # S7 child IDs, names and text revisions can change. The paragraph anchor
    # belongs to the native utterance and first token, so Tk edits it in place.
    result['id'] = 'paragraph:' + parent_key(first) + ':' + str(anchor)
    result['caption_key'] = parent_key(first)
    result['_caption_parts'] = tuple(dict(part) for part in parts)
    def join(value):
        return ''.join(('' if index == 0 else part.get('leading_text_joiner',' '))+value(part)
                       for index,part in enumerate(parts))
    result['raw_asr_text'] = join(lambda part:str(part.get('raw_asr_text') or '').strip())
    result['provisional_display_text'] = join(_text)
    result['final'] = (all(part.get('final') is True for part in parts)
                       and last.get('utterance_final',True) is True)
    # Casing a native continuation independently can create "particulAr".
    # Ask the retained formatter to case the assembled raw word once, until
    # the actual spoken-group PnC revisions are available.
    one_group = first.get('utterance_group_id') and all(part.get('utterance_group_id')==first['utterance_group_id'] for part in parts)
    result['_needs_group_casing'] = (len(parts)>1 and (one_group or any(part.get('leading_text_joiner')=='' for part in parts[1:]))
                                     and not all(part.get('spoken_punctuation_ready') for part in parts))
    if result['_needs_group_casing']:
        result['provisional_display_text'] = None
    result['final_punctuated_display_text'] = result['provisional_display_text'] if result['final'] else None
    result['source_start_sec'] = min(part['source_start_sec'] for part in parts) if all(_interval(part) for part in parts) else first.get('source_start_sec')
    result['source_end_sec'] = max(part['source_end_sec'] for part in parts) if all(_interval(part) for part in parts) else last.get('source_end_sec')
    result['speaker_revision'] = tuple((str(part['id']), part.get('speaker_revision')) for part in parts)
    result['selected'] = any(part.get('selected') for part in parts)
    tracks = [_supported_track(part) for part in parts]
    result['paragraph_claims_shared_speaker'] = bool(tracks[0] is not None and all(track==tracks[0] for track in tracks))
    if all(_unattributed(part) for part in parts):
        result.update(label='Unknown',paragraph_identity='unverified_unattributed',
                      paragraph_claims_shared_speaker=False)
    if any((part.get('track_id'),part.get('profile_id'),part.get('display_profile_id'),part.get('label'))
           != (first.get('track_id'),first.get('profile_id'),first.get('display_profile_id'),first.get('label'))
           for part in parts):
        result.update(track_id=None,profile_id=None,display_profile_id=None,label='Unknown',
                      identity_status='unavailable',ownership_state='pending',closed_group_display=False)
    if parent_key(first) == parent_key(last) and first.get('token_range') and last.get('token_range'):
        result['token_range'] = [first['token_range'][0], last['token_range'][1]]
    else:
        result.pop('token_range', None)
    # Preserve the existing per-span opt-in without displaying only the first
    # span's optional text or adding a new correction operation.
    if len(parts) > 1:
        corrected = any(part.get('show_corrected_text') and part.get('optional_corrected_text') for part in parts)
        result['show_corrected_text'] = corrected
        result['optional_corrected_text'] = join(lambda part:
            str(part['optional_corrected_text']) if part.get('show_corrected_text') and part.get('optional_corrected_text')
            else _text(part)) if corrected else None
    return result


def paragraph_rows(rows, mode, *, gap_seconds=2.5, max_chars=600):
    """Aggregate a bounded, source-ordered current partition without losing words.

    max_chars is a soft limit at existing span boundaries: an individual span is
    never split using invented timestamps. No source rows are mutated or hidden.
    """
    if (type(gap_seconds) not in (int, float) or not math.isfinite(gap_seconds) or gap_seconds < 0
            or type(max_chars) is not int or max_chars < 1):
        raise ValueError('Valid paragraph gap and character bound required')
    result, parts, length = [], [], 0
    for row in source_order_rows(rows):
        continuation = (parts and row.get('leading_text_joiner') == ''
                        and row.get('utterance_group_id')
                        and row.get('utterance_group_id') == parts[-1].get('utterance_group_id'))
        if parts and (not _continues(parts[-1], row, mode, gap_seconds)
                      or (not continuation and length + 1 + len(_text(row)) > max_chars)):
            result.append(_paragraph(parts))
            parts, length = [], 0
        parts.append(row)
        length += (1 if len(parts) > 1 else 0) + len(_text(row))
    if parts:
        result.append(_paragraph(parts))
    return result
