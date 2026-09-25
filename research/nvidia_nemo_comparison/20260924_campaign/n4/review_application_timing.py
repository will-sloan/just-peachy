"""Interpret recorded row timing, without claiming word latency. See its README."""
from copy import deepcopy
from pathlib import Path

from common import fingerprint, load, verify
from review_application_content import review_cell as review_content
from review_native_captions import TIMING, review as review_captions
from review_scoring_bank import require
from viewport_ledger_v2 import finite, read_row

MAX_SPANS = 8192
MAX_MEMBERSHIPS = 262144
STAGES = {'first_visible': 'first_row_visible',
          'first_final_visible': 'first_final_row_visible', 'latest': 'latest_row_observation'}


def population(native, *, checkpoint=None):
    """Keep lexical words and the collector's empty-caption virtual IDs separate."""
    require(native['status'] == 'PASS_NATIVE_CAPTION_RAW_PARTITIONS_ONLY', 'Unreviewed native captions')
    words = native['stable_word_spans']
    require(len(words) <= MAX_SPANS and len({w['id'] for w in words}) == len(words), 'Native word census differs')
    result = {}
    for w in words:
        require(w['timing_kind'] == TIMING and w['exact_word_start_sec'] is None
            and w['exact_word_end_sec'] is None and all(finite(w[k]) for k in
                ('source_start_sec', 'source_end_sec', 'first_seen_monotonic_sec'))
            and 0 <= w['source_start_sec'] <= w['source_end_sec'], 'Word timing authority differs')
        result[w['id']] = dict(kind='lexical_word', source_window_seconds=[w['source_start_sec'], w['source_end_sec']],
            native_state_first_seen_monotonic_sec=w['first_seen_monotonic_sec'],
            first_publication=None, first_final_publication=None)
    members = 0
    for d in native['displays']:
        if checkpoint: checkpoint()
        stamp = dict(sequence=d['publication_sequence'], monotonic_sec=d['publication_monotonic_sec'])
        require(type(stamp['sequence']) is int and stamp['sequence'] > 0
            and finite(stamp['monotonic_sec']) and stamp['monotonic_sec'] > 0, 'Invalid native publication clock')
        for part in d['segments']:
            ids = part['span_ids']
            if not ids:
                sid = part['segment_id']
                require(not part['raw_text'].split(), 'Virtual caption contains lexical words')
                require(sid not in result or result[sid]['kind'] == 'empty_caption', 'Virtual/lexical span collision')
                result.setdefault(sid, dict(kind='empty_caption', source_window_seconds=None,
                    native_state_first_seen_monotonic_sec=None, first_publication=None, first_final_publication=None))
                ids = [sid]
            for sid in ids:
                members += 1
                require(sid in result and members <= MAX_MEMBERSHIPS and len(result) <= MAX_SPANS,
                    'Native membership missing or exceeds timing bound')
                entry = result[sid]
                if entry['first_publication'] is None: entry['first_publication'] = deepcopy(stamp)
                if d['final'] and entry['first_final_publication'] is None:
                    entry['first_final_publication'] = deepcopy(stamp)
                require(entry['native_state_first_seen_monotonic_sec'] is None
                    or entry['native_state_first_seen_monotonic_sec'] <= stamp['monotonic_sec'],
                    'Native state first-seen clock follows publication')
    require(all(s['first_publication'] is not None for s in result.values()), 'Native word has no display publication')
    return result


def sampled_state(state, row, entry, origin, stage):
    """Elapsed diagnostics between recorded points, never a continuous exposure."""
    at = state['observed_monotonic_sec']; a, b = state['publication_monotonic_range']
    count = state['compatible_publications']
    require(all(finite(v) for v in (origin, at, a, b)) and 0 < origin <= at
        and entry['first_publication']['monotonic_sec'] <= a <= b <= at,
        'Recorded timing clock order differs')
    require(type(count) is int and count > 0 and state['ambiguous_native_publication'] == (count != 1)
        and state['exact_consumed_event_attribution'] is False, 'Native event ambiguity was discarded')
    require(row['row_id'] == state['row_id'] and row['caption_visible'] == state['caption_visible']
        and row.get('removed_from_controller', False) == state['retired'], 'Timing row state differs')
    if stage != 'latest':
        require(state['caption_visible'] is True and state['retired'] is False, 'Visible stage has no visible row')
    if stage == 'first_final_visible':
        require(row['final'] is True and entry['first_final_publication'] is not None
            and entry['first_final_publication']['monotonic_sec'] <= a, 'Final observation precedes native final publication')
    window = entry['source_window_seconds']
    # This signed interval expresses uncertainty in a revision's source support.
    # It is neither phonetic alignment nor a bound on physical/display latency.
    interval = None if window is None else [at-origin-window[1], at-origin-window[0]]
    return dict(row_ref=deepcopy(state['row_ref']), row_id=state['row_id'],
        observed_monotonic_sec=at, observed_source_elapsed_seconds=at-origin,
        row_has_visible_caption_glyphs=state['caption_visible'], row_is_final=row['final'], retired=state['retired'],
        elapsed_since_first_native_span_publication_seconds=at-entry['first_publication']['monotonic_sec'],
        elapsed_since_first_native_final_publication_seconds=(at-entry['first_final_publication']['monotonic_sec']
            if stage == 'first_final_visible' else None),
        elapsed_from_compatible_native_publications_range_seconds=[at-b, at-a],
        source_window_relative_interval_seconds=interval,
        compatible_native_publications=count, ambiguous_native_publication=state['ambiguous_native_publication'],
        candidate_bindings_sha256=state['candidate_bindings_sha256'], individual_word_glyph_visibility_proven=False,
        exact_consumed_event_attribution=False, continuous_exposure_seconds=None)


def project(native, widget, *, origin, log, checkpoint=None):
    """Internal arithmetic seam. The production API below admits every input."""
    require(widget['status'] == 'PASS_NATIVE_WIDGET_PRIMARY_CONTENT_JOINS_ONLY'
        and widget['native_caption_review_sha256'] == fingerprint(native), 'Caption input changed between timing readers')
    require(finite(origin) and origin > 0, 'Finite source clock required')
    entries = population(native, checkpoint=checkpoint)
    spans = widget['spans']; missing = sorted(set(entries)-set(spans))
    require(set(spans) <= set(entries) and widget['native_span_population'] == len(entries)
        and widget['observed_span_population'] == len(spans) and widget['native_spans_not_observed'] == missing,
        'Timing visibility denominator differs')
    require(widget['observed_spans_never_visible'] == sum(s['first_visible'] is None for s in spans.values())
        and widget['observed_spans_without_final_visibility'] == sum(s['first_final_visible'] is None for s in spans.values()),
        'Timing missing-stage denominator differs')
    verify(log); cache = {}; output = {}
    for sid, entry in entries.items():
        if checkpoint: checkpoint()
        stages = {}
        observed = spans.get(sid)
        for old, new in STAGES.items():
            key = observed[old] if observed else None
            if key is None: stages[new] = None; continue
            require(key in widget['states'], 'Timing state reference missing')
            state = widget['states'][key]; refkey = fingerprint(state['row_ref'])
            if refkey not in cache:
                require(len(cache) < MAX_SPANS*3, 'Timing row cache exceeds bound')
                cache[refkey] = read_row(log['path'], state['row_ref'])
            row = cache[refkey]
            require(sid in row['span_ids'], 'Timing row no longer contains its span')
            stages[new] = sampled_state(state, row, entry, origin, old)
        output[sid] = dict(**entry, observed_in_any_row=observed is not None, stages=stages,
            observed_heading_changes=observed['observed_heading_changes'] if observed else None,
            observed_visible_heading_changes=observed['observed_visible_heading_changes'] if observed else None)
    counts = {}
    for kind in ('lexical_word', 'empty_caption'):
        group = [v for v in output.values() if v['kind'] == kind]
        counts[kind] = dict(native=len(group), observed=sum(v['observed_in_any_row'] for v in group),
            unobserved=sum(not v['observed_in_any_row'] for v in group),
            without_row_visible_observation=sum(v['stages']['first_row_visible'] is None for v in group),
            without_final_row_visible_observation=sum(v['stages']['first_final_row_visible'] is None for v in group))
    verify(log)
    gap = widget['maximum_observation_interval_seconds']
    require(finite(gap) and gap >= 0, 'Invalid observation interval')
    return dict(status='PASS_RECORDED_ROW_TIMING_DIAGNOSTICS_ONLY', spans=output, counts=counts,
        source_origin_monotonic_sec=origin, source_window_authority=TIMING,
        maximum_observation_interval_seconds=gap,
        native_caption_review_sha256=fingerprint(native), widget_review_sha256=fingerprint(widget),
        partial_only_utterance_ids=native['partial_only_utterance_ids'],
        missing_raw_revision_ids=native['missing_raw_revision_ids'],
        point_observation_arithmetic_reviewed=True, individual_word_glyph_visibility_proven=False,
        exact_consumed_event_attribution=False, phonetic_word_alignment_available=False,
        source_callback_deadlines_reviewed=False, source_to_widget_latency_qualified=False,
        continuous_exposure_measured=False, physical_scanout_measured=False,
        naming_accuracy_qualified=False, complete_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False)


def review_cell(folder, *, checkpoint=None, **expected):
    """Compose independently admitted V2 cell/content with recorded timing facts."""
    content = review_content(folder, checkpoint=checkpoint, **expected)
    cell = content['cell']; registry = {}
    viewport = cell['observations']['viewport_review']
    for b in cell['joins']['evidence']+[viewport['input'], viewport['evidence']]+content['roster']['evidence']:
        require(b['path'] not in registry or registry[b['path']] == b, 'Timing evidence binding conflicts')
        registry[b['path']] = b; verify(b)
    closure_path = str((Path(folder)/'application/ENGINE_CLOSURE.json').resolve(strict=True))
    require(closure_path in registry, 'Unjoined timing source closure')
    closure = load(closure_path); envelope = cell['transport']['native_envelope_review']
    native = review_captions(Path(closure['session']), job=expected['payload']['job'],
        expected_envelope=envelope, checkpoint=checkpoint)
    for b in native['evidence']:
        require(registry.get(b['path']) == b, 'Native timing bindings differ from cell')
    origin = envelope['source_start']['source_epoch_monotonic_sec']
    require(viewport['source_origin_monotonic_sec'] == origin, 'Source/viewport clock origin differs')
    result = project(native, content['widget'], origin=origin, log=viewport['evidence'], checkpoint=checkpoint)
    for b in list(registry.values())+[content['application_qualification'], content['source_context']]: verify(b)
    return dict(status='PASS_V2_APPLICATION_RECORDED_ROW_TIMING_ONLY', content=content, timing=result,
        content_review_sha256=fingerprint(content), evidence=list(registry.values()),
        point_observation_arithmetic_reviewed=True, individual_word_glyph_visibility_proven=False,
        exact_consumed_event_attribution=False, source_to_widget_latency_qualified=False,
        continuous_exposure_measured=False, physical_scanout_measured=False, complete_panel_reviewed=False,
        names_independently_scored=False, controlled_resources_qualified=False,
        actual_continuity_test=False, stop_restart_qualified=False, deployment_tier='UNKNOWN',
        integrated_N4_cells=0, N4_accepted=False)
