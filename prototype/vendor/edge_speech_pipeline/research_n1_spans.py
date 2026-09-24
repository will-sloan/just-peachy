"""N1 timestamped revision spans; acoustic word alignment is never inferred.

See README_N1_SPANS.md. Pure functions mutate only their locked caller's row.
"""
from copy import deepcopy
import math
import re

MODE = 'timestamped_spans_v3'
TIMING = 'ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT'


def update_tokens(row, prior_text, payload, now):
    previous, current = re.findall(r'\S+', prior_text), re.findall(r'\S+', row['text'])
    prefix = 0
    while prefix < min(len(previous), len(current)) and previous[prefix] == current[prefix]:
        prefix += 1
    old = row.get('word_spans', [])
    row['retired_spans_delta'] = deepcopy(old[prefix:])
    row['retired_span_count'] = row.get('retired_span_count', 0) + len(old[prefix:])
    spans = deepcopy(old[:prefix])
    owners = deepcopy(row.get('_token_owners', [])[:prefix])
    serial = row.get('_token_serial', 0)
    # This is an observation window of the hypothesis revision, not a word's
    # acoustic start/end. Rewrites receive the full caption uncertainty interval.
    start = row.get('_previous_source_end_sec', row['source_start_sec']) if prefix == len(previous) else row['source_start_sec']
    end = row['source_end_sec']
    if start > end:
        raise ValueError('Revision source clock regressed')
    for word in current[prefix:]:
        serial += 1
        spans.append(dict(id=f"{row['caption_key']}/token:{serial}", text=word,
            source_start_sec=start, source_end_sec=end, timing_kind=TIMING,
            exact_word_start_sec=None, exact_word_end_sec=None,
            first_seen_monotonic_sec=now, first_shown_label='Pending identity',
            first_shown_label_scope='initial presentation event; physical GUI receipt separate',
            committed_label=None, speaker_revision=0, speaker_history=[]))
        owners.append(None)
    row.update(word_spans=spans, token_ids=[s['id'] for s in spans], _token_serial=serial,
               _token_owners=owners, upstream_token_ids=deepcopy(payload.get('token_ids')))


def apply_identity(state, row, payload):
    support, target = state._span(payload), state._span(payload, target=True)
    version = state._version(payload, identity=True)
    if payload.get('target_text_revision_id') is not None and payload['target_text_revision_id'] != row.get('text_revision_id'):
        return state._reject('identity_wrong_target_revision')
    if support is None or target is None or version is None or version[1] < 0:
        return state._reject('identity_missing_span_or_version')
    if target[0] != row['source_start_sec'] or target[1] < row['source_end_sec']:
        return state._reject('identity_wrong_target_span')
    if max(support[0], row['source_start_sec']) >= min(support[1], row['source_end_sec']):
        return state._reject('identity_disjoint_source')
    ids = row.get('token_ids', [])
    explicit = payload.get('target_span_ids', payload.get('target_token_ids'))
    if explicit is not None and (not isinstance(explicit, list) or not explicit
            or any(not isinstance(s, str) for s in explicit) or len(set(explicit)) != len(explicit)
            or not set(explicit).issubset(ids)
            or payload.get('target_text_revision_id') != row.get('text_revision_id')):
        return state._reject('identity_invalid_explicit_span_target')
    owner = dict(label=payload.get('latest_label', payload.get('speaker', 'Unknown')),
        known_profile_id=payload.get('latest_known_profile_id'), known_name=payload.get('latest_known_name'),
        naming_state=payload.get('latest_naming_state', 'unresolved'),
        track_id=payload.get('replacement_tracker_id', payload.get('tracker_id')),
        anonymous_label=payload.get('latest_anonymous_label', 'Unknown'),
        identity_source_span=list(support), identity_target_span=list(target), identity_version=list(version),
        identity_event_id=payload.get('event_id'), identity_input_event_id=payload.get('input_event_id'),
        evidence_ids=deepcopy(payload.get('evidence_ids', [])), accepted_text_revision_id=row['text_revision_id'],
        accepted_raw_text=row['text'], target_revision_authority='EXACT_TARGET_REVISION' if payload.get('target_text_revision_id') else 'LEGACY_MISSING_COUNTERFACTUAL')
    # Preserve all source/publication clocks supplied by the policy, without
    # converting source spans into invented per-word acoustic timestamps.
    from .research_s7_presentation import IDENTITY_CLOCK_FIELDS
    owner.update({key: deepcopy(payload.get(key)) for key in IDENTITY_CLOCK_FIELDS})
    targets = []
    for i, span in enumerate(row.get('word_spans', [])):
        prior = row['_token_owners'][i]
        if explicit is not None:
            if span['id'] not in explicit:
                continue
        else:
            # A new speaker cannot revise committed earlier words merely because
            # their utterance/paragraph is shared. Same-track naming can mature.
            if prior is not None and not (prior.get('track_id') is not None
                    and prior.get('track_id') == owner['track_id']
                    and (not prior.get('known_profile_id') or prior.get('known_profile_id') == owner['known_profile_id'])):
                continue
        if max(support[0], span['source_start_sec']) >= min(support[1], span['source_end_sec']):
            continue
        previous_version = tuple(prior.get('identity_version', ())) if prior else ()
        if previous_version and version <= previous_version:
            continue
        targets.append(i)
    if not targets:
        return state._reject('identity_no_new_supported_span')
    accepted_ids = [ids[i] for i in targets]
    owner['accepted_token_ids'] = accepted_ids
    for i in targets:
        span, prior = row['word_spans'][i], row['_token_owners'][i]
        changed = prior is None or any(prior.get(k) != owner.get(k) for k in ('label', 'known_profile_id', 'track_id', 'naming_state'))
        row['_token_owners'][i] = deepcopy(owner)
        if changed:
            span['speaker_revision'] += 1
            span['speaker_history'].append(dict(revision=span['speaker_revision'], label=owner['label'],
                profile_id=owner['known_profile_id'], track_id=owner['track_id'],
                event_id=owner['identity_event_id'], source_evidence_span=list(support),
                explicit_correction=explicit is not None, identity_version=list(version)))
            # The first accepted label stays immutable; subsequent corrections
            # are separate revisions. The native append-only event log persists all.
            if span['committed_label'] is None:
                span['committed_label'] = owner['label']
            if len(span['speaker_history']) > 32:
                span['speaker_history'] = [span['speaker_history'][0], *span['speaker_history'][-31:]]
                span['history_truncated_in_memory'] = True
    row['accepted_identity_snapshot'] = deepcopy(owner)
    row.setdefault('first_supported_identity', deepcopy(owner))
    state._refresh_segments(row)
    return True
