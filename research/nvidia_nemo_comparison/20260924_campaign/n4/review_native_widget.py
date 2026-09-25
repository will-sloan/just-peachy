"""Primary caption/viewport predecessor joins. See README_NATIVE_WIDGET_REVIEW.md."""
from bisect import bisect_right
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import re

from common import bind, fingerprint, load, verify
from review_native_captions import review as review_captions
from review_native_journal import rows
from review_viewport_evidence import decode, review as review_viewport
from review_scoring_bank import require
from viewport_ledger_v2 import MAX_RECORD_BYTES, encoded, read_row

HERE = Path(__file__).resolve().parent
MAX_ENTRIES = 262144
MAX_CHANGES = 32768
MAX_TEXT_BYTES = 16*1024**2
FIELDS = ('row_id', 'caption_key', 'span_ids', 'raw_asr_text', 'final', 'source_start_sec',
          'source_end_sec', 'timing_kind', 'speaker_revision', 'verified_profile_id',
          'display_profile_id', 'naming_state', 'identity_assignment')


def casing(source_receipt):
    q = load(HERE/'NATIVE_CAPTION_REVIEW_CHECK_V1.json')
    require(source_receipt == q['application_source'], 'Widget reader requires the qualified native caption source')
    verify(source_receipt); source = load(source_receipt['path'])
    path = Path(source['prototype'])/'app/casing.py'
    binding = dict(path=str(path), **source['files']['app/casing.py']); verify(binding)
    spec = importlib.util.spec_from_file_location('jp_n4_widget_casing', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    verify(binding)
    return module.provisional_case, binding


def partition(display, parent, part):
    """Independent interpretation of the bound Controller's formatting seam."""
    if display is None: return None
    if len(parent['segments']) == 1: return display
    words = list(re.finditer(r'\S+', display)); raw = parent['text'].split()
    normalize = lambda value: ''.join(c.lower() for c in value if c.isalnum())
    if len(words) != len(raw) or any(normalize(m.group()) != normalize(w) for m, w in zip(words, raw)):
        return None
    a, b = part['token_range']
    if not 0 <= a <= b <= len(words): return None
    start = words[a].start() if a < len(words) else len(display)
    end = words[b].start() if b < len(words) else len(display)
    return display[start:end]


def expected_caption(parent, part, people, case):
    names = [p['name'] for p in people]
    provisional = partition(case(parent['text'], names=names), parent, part) or case(part['raw_text'], names=names)
    learned = partition(parent['display_text'] if parent.get('punctuation_for_text_revision') else None, parent, part)
    return learned if parent['final'] and learned else provisional


def native_fields(parent, part):
    # This version is deliberately restricted to the primary open mode. A
    # closed-roster assignment must not be mistaken for verified recognition.
    require(not part.get('closed_display_assignment'), 'Closed assignment requires a separate mode-specific join')
    known = part.get('known_profile_id') if part.get('naming_state') == 'confirmed' else None
    rid = part['segment_id']
    return dict(row_id=rid, caption_key=parent['caption_key'], span_ids=part['span_ids'] or [rid],
        raw_asr_text=part['raw_text'], final=parent['final'], source_start_sec=part['source_start_sec'],
        source_end_sec=part['source_end_sec'], timing_kind=part['timing_kind'], speaker_revision=part.get('speaker_revision'),
        verified_profile_id=known, display_profile_id=known, naming_state=part.get('naming_state'),
        identity_assignment=part.get('prototype_assignment'))


def signature(value):
    return fingerprint({key: value[key] for key in FIELDS})


def build_index(events, caption_review, *, people, case):
    expected = {d['publication_sequence']: d for d in caption_review['displays']}
    index = {}; spans = set(); count = text_bytes = 0; seen = set()
    for event in events:
        if event['event_type'] != 's6d_display': continue
        p = event['payload']; serial = p['publication_sequence']
        require(serial in expected and serial not in seen and fingerprint(p) == expected[serial]['payload_sha256'],
                'Native caption payload changed between readers')
        seen.add(serial)
        require(not any(key in p for key in ('archived_provisional_display_text','archived_final_formatted_text','manual_edit')),
                'Archived or manually edited captions are outside the primary live-source contract')
        for part in p['segments']:
            fields = native_fields(p, part); key = signature(fields)
            caption = expected_caption(p, part, people, case)
            count += 1; text_bytes += len(caption.encode('utf-8'))
            require(count <= MAX_ENTRIES and text_bytes <= MAX_TEXT_BYTES, 'Native widget index budget exceeded')
            spans.update(fields['span_ids'])
            entry = dict(sequence=serial, publication_monotonic_sec=p['publication_monotonic_sec'],
                raw_revision_id=p['text_revision_id'], caption=caption)
            group = index.setdefault(key, dict(times=[], entries=[]))
            require(not group['times'] or group['times'][-1] <= entry['publication_monotonic_sec'], 'Native index time regressed')
            group['times'].append(entry['publication_monotonic_sec']); group['entries'].append(entry)
    require(seen == set(expected), 'Native display population changed between readers')
    return index, spans, count


def match(row, at, index, *, retired=False):
    require(row['strictly_filtered'] is False, 'Strict filtering is outside the primary open-mode join')
    group = index.get(signature(row)); require(group is not None, 'Widget raw row has no matching native segment')
    stop = bisect_right(group['times'], at)
    candidates = group['entries'][:stop]
    pane_texts = [p['applied_caption_text'] for p in row['panes'].values() if p['present_in_widget']]
    require(retired or pane_texts, 'Unfiltered observed row has no widget text')
    candidates = [entry for entry in candidates if all(value == entry['caption'] for value in pane_texts)]
    require(candidates, 'Widget text/metadata lacks a compatible preceding native publication')
    return dict(compatible_publications=len(candidates),
        publication_sequence_range=[candidates[0]['sequence'], candidates[-1]['sequence']],
        publication_monotonic_range=[candidates[0]['publication_monotonic_sec'], candidates[-1]['publication_monotonic_sec']],
        candidate_bindings_sha256=fingerprint(candidates), ambiguous_native_publication=len(candidates) != 1,
        exact_consumed_event_attribution=False, observed_monotonic_sec=at,
        caption_visible=row['caption_visible'], heading_visible=row['heading_visible'], retired=retired,
        pane_text_sha256={name: fingerprint(p.get('applied_caption_text')) for name, p in row['panes'].items()},
        recorded_headings={name: p.get('applied_heading_text') for name, p in row['panes'].items()})


def join_viewport(summary_binding, viewport, index, native_spans, *, checkpoint=None):
    summary = decode(Path(summary_binding['path']).read_bytes()); log = summary['log']
    require(viewport['input'] == summary_binding and viewport['evidence'] == log, 'Viewport input changed between readers')
    verify(summary_binding); verify(log)
    changes = []; offset = 0; sample_count = 0
    with Path(log['path']).open('rb') as stream:
        while True:
            if checkpoint: checkpoint()
            data = stream.readline(MAX_RECORD_BYTES+1)
            if not data: break
            require(len(data) <= MAX_RECORD_BYTES and data.endswith(b'\n') and offset+len(data) <= log['bytes']
                    and sample_count < viewport['observations'], 'Viewport record changed or exceeds bound')
            record = decode(data); metadata = record['metadata']; at = metadata['observed_monotonic_sec']
            for i, change in enumerate(record['changes']):
                if change['kind'] != 'row': continue
                require(metadata['source_origin_monotonic_sec'] is not None, 'Caption observed without source clock')
                joined = match(change['row'], at, index)
                require(len(changes) < MAX_CHANGES, 'Widget changed-row join budget exceeded')
                ref = dict(offset=offset, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), change_index=i)
                changes.append(dict(row_ref=ref, row_id=change['row']['row_id'], **joined))
            sample_count += 1; offset += len(data)
    require(offset == log['bytes'] and sample_count == viewport['observations'], 'Viewport population changed during join')
    states = {}; spans = {}; cache = {}
    for sid, original in summary['spans'].items():
        if checkpoint: checkpoint()
        spans[sid] = {}
        for kind in ('first_visible','first_final_visible','latest'):
            value = original[kind]
            if value is None: spans[sid][kind] = None; continue
            key = fingerprint(value)
            if key not in states:
                ref = value['row_ref']; rkey = fingerprint(ref)
                if rkey not in cache: cache[rkey] = read_row(log['path'], ref)
                row = cache[rkey]
                require(sid in row['span_ids'], 'Viewport state does not contain its span')
                states[key] = dict(row_ref=ref, row_id=row['row_id'], **match(row, value['observed_monotonic_sec'], index,
                    retired=row.get('removed_from_controller', False)))
            spans[sid][kind] = key
        spans[sid].update(observed_heading_changes=original['observed_heading_changes'],
                          observed_visible_heading_changes=original['observed_visible_heading_changes'])
    require(set(spans) <= native_spans, 'Viewport contains spans absent from the native caption history')
    for binding in (summary_binding, log): verify(binding)
    return dict(changed_rows=changes, states=states, spans=spans,
        native_spans_not_observed=sorted(native_spans-set(spans)), native_span_population=len(native_spans),
        observed_span_population=len(spans),
        observed_spans_never_visible=sum(s['first_visible'] is None for s in spans.values()),
        observed_spans_without_final_visibility=sum(s['first_final_visible'] is None for s in spans.values()),
        ambiguous_state_joins=sum(s['ambiguous_native_publication'] for s in states.values()),
        maximum_observation_interval_seconds=viewport['maximum_observation_interval_seconds'])


def review(session, *, job, expected_envelope, viewport_summary, source_receipt, people,
           mode, checkpoint=None):
    """Caller supplies a independently bound fixed roster and primary V2 cell.

    This API does not replace transport, ownership, primary settings, roster or
    plan admission. People are display spellings only, never evaluator truth.
    """
    require(mode == 'open_with_names', 'Only the declared primary open mode is qualified here')
    require(type(people) is list and len(people) <= 256 and all(type(p) is dict and set(p) == {'id','name'}
        and all(type(p[k]) is str and 0 < len(p[k]) <= 128 for k in ('id','name')) for p in people)
        and len({p['id'] for p in people}) == len(people), 'Bounded fixed display roster required')
    case, case_binding = casing(source_receipt)
    native = review_captions(session, job=job, expected_envelope=expected_envelope, checkpoint=checkpoint)
    viewport = review_viewport(viewport_summary, checkpoint=checkpoint)
    require(viewport['source_origin_monotonic_sec'] == expected_envelope['source_start']['source_epoch_monotonic_sec'],
            'Native and viewport source origins differ')
    index, native_spans, entry_count = build_index(rows(expected_envelope['journal'], checkpoint), native, people=people, case=case)
    joined = join_viewport(viewport_summary, viewport, index, native_spans, checkpoint=checkpoint)
    for b in native['evidence']+[viewport_summary, viewport['evidence'], source_receipt, case_binding]: verify(b)
    return dict(status='PASS_NATIVE_WIDGET_PRIMARY_CONTENT_JOINS_ONLY', **joined, mode=mode,
        native_caption_review_sha256=fingerprint(native), viewport_review_sha256=fingerprint(viewport),
        people_sha256=fingerprint(people), source_receipt=source_receipt, casing_source=case_binding,
        native_segment_history_entries=entry_count, missing_native_caption_revisions=native['missing_raw_revision_ids'],
        evidence=native['evidence']+[viewport_summary, viewport['evidence']],
        primary_caption_text_consistency_reviewed=True, exact_consumed_event_attribution=False,
        roster_and_primary_settings_independently_admitted=False, application_owner_reviewed=False,
        naming_accuracy_qualified=False, source_to_widget_latency_qualified=False, continuous_exposure_measured=False,
        physical_scanout_measured=False, production_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False)
