"""Released-session native text/widget joins. README_RESTART_NATIVE_CONTENT.md."""
from pathlib import Path

from common import bind, fingerprint, load, verify
from metric_process import exact_process
from restart_native_journal import inspect, require_complete
from review_application_transport import record
from review_native_journal import rows, segments
from review_native_text import project as project_text
from review_native_captions import project as project_captions
from review_native_widget import casing, build_index, join_viewport, MAX_ENTRIES
from review_viewport_evidence import review as review_viewport
from review_scoring_bank import require
from viewport_ledger_v2 import read_row

HERE = Path(__file__).resolve().parent
OWN = ('review_restart_native_content.py', 'test_restart_native_content.py',
       'probe_restart_native_content.py', 'README_RESTART_NATIVE_CONTENT.md')


def code_bindings():
    result = {}
    for name, status in (
        ('RESTART_COMPLETE_REVIEW_CHECK_V1.json', 'PASS_RESTART_COMPLETE_REVIEW_DEVELOPMENT_ONLY'),
        ('NATIVE_WIDGET_REVIEW_CHECK_V1.json', 'PASS_NATIVE_WIDGET_REVIEW_DEVELOPMENT_ONLY')):
        qb, q = record(HERE/name, HERE); require(q['status'] == status, 'Native-content prerequisite differs')
        verify(q['private_receipt']); receipt = load(q['private_receipt']['path']); verify(receipt['admission'])
        require(exact_process(load(receipt['admission']['path'])['owner']) is None, 'Prerequisite probe remains active')
        for b in [qb]+q['code']:
            verify(b); require(b['path'] not in result or result[b['path']] == b, 'Native-content dependency conflict')
            result[b['path']] = b
    for name in OWN:
        b = bind(HERE/name); result[b['path']] = b
    return [b for _, b in sorted(result.items())]


def review_native(session, *, job, delivered_frames, intent, expected_envelope, checkpoint=None):
    """Reconstruct the released envelope without shortening the planned job."""
    envelope = require_complete(inspect(session, job=job, delivered_frames=delivered_frames,
                                        intent=intent, checkpoint=checkpoint))
    require(fingerprint(envelope) == fingerprint(expected_envelope), 'Released envelope changed before content interpretation')
    origin = envelope['source_start']['source_epoch_monotonic_sec']
    raw = project_text(rows(envelope['journal'], checkpoint), session_id=Path(session).name,
                       source_origin=origin, duration=delivered_frames/16000)
    captions = project_captions(rows(envelope['journal'], checkpoint), raw=raw)
    require(segments(session) == envelope['journal'], 'Native segment set changed during content interpretation')
    evidence = envelope['journal']+envelope['terminal']
    for b in evidence: verify(b)
    return dict(status='PASS_RELEASED_NATIVE_TEXT_AND_CAPTION_LINEAGE_ONLY', session_id=Path(session).name,
        full_job_sha256=fingerprint(job), planned_frames=job['frames'], delivered_frames=delivered_frames, intent=intent,
        source_origin_monotonic_sec=origin, envelope_sha256=fingerprint(envelope), evidence=evidence,
        raw=raw, captions=captions, raw_caption_partitions_reviewed=True, actual_widget_content_joined=False,
        full_planned_audio_coverage=delivered_frames == job['frames'], source_to_widget_latency_qualified=False,
        actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False)


def review_widget(sources, *, job, index, viewport_summary, source_receipt, people, mode, checkpoint=None):
    """Read both native histories for retained captions; admit the pair separately.

    sources is the ordered pair of {session, delivered_frames, intent, envelope}
    reconstructed by the qualified pair reader, not a list of arbitrary prefixes.
    index selects the viewport ledger. Its clock must equal its own source origin;
    each row's arithmetic uses its native session's original clock instead.
    """
    require(type(index) is int and index in (0, 1) and type(sources) is list and len(sources) == 2,
            'Two ordered native sources and explicit viewport index required')
    require(mode == 'open_with_names', 'Only primary open-mode content is qualified')
    require(type(people) is list and len(people) <= 256 and all(type(p) is dict and set(p) == {'id','name'}
        and all(type(p[k]) is str and 0 < len(p[k]) <= 128 for k in ('id','name')) for p in people)
        and len({p['id'] for p in people}) == len(people) and len({p['name'] for p in people}) == len(people),
        'Bounded unique display roster required')
    require([s['intent'] for s in sources] == ['mid_file_stop', 'completed_release']
            and len({str(Path(s['session']).resolve()) for s in sources}) == 2
            and len({Path(s['session']).name for s in sources}) == 2, 'Native session order or identities differ')
    case, case_binding = casing(source_receipt)
    native = []; merged = {}; all_spans = set(); count = 0; origins = {}; bindings = {}
    def keep(b):
        require(b['path'] not in bindings or bindings[b['path']] == b, 'Evidence changed across native histories')
        bindings[b['path']] = b
    for number, source in enumerate(sources[:index+1]):
        reviewed = review_native(source['session'], job=job, delivered_frames=source['delivered_frames'],
            intent=source['intent'], expected_envelope=source['envelope'], checkpoint=checkpoint)
        if number:
            require(reviewed['source_origin_monotonic_sec'] > sources[number-1]['envelope']['completion_publication_monotonic_sec'],
                    'Second source precedes first native completion')
        native.append(reviewed); origins[reviewed['session_id']] = reviewed['source_origin_monotonic_sec']
        entry, spans, n = build_index(rows(source['envelope']['journal'], checkpoint), reviewed['captions'], people=people, case=case)
        require(not set(merged).intersection(entry) and not all_spans.intersection(spans), 'Native caption identities collide across sessions')
        count += n; require(count <= MAX_ENTRIES, 'Combined native widget index budget exceeded')
        merged.update(entry); all_spans.update(spans)
        for b in reviewed['evidence']: keep(b)
    viewport = review_viewport(viewport_summary, checkpoint=checkpoint)
    current = native[-1]['session_id']
    require(viewport['source_origin_monotonic_sec'] == origins[current], 'Current native and viewport source origins differ')
    joined = join_viewport(viewport_summary, viewport, merged, all_spans, checkpoint=checkpoint)
    # Each row retains its own original source clock even in a later ledger.
    # Predecessor matching above uses absolute publication/observation clocks.
    cache = {}
    def attribute(value):
        key = fingerprint(value['row_ref'])
        if key not in cache: cache[key] = read_row(viewport['evidence']['path'], value['row_ref'])
        row = cache[key]; session = row['caption_key'].split('/', 1)[0]
        require(session in origins and value['observed_monotonic_sec'] >= origins[session], 'Caption has no preceding source origin')
        return dict(value, native_session=session, session_role='current' if session == current else 'retained',
            original_source_origin_monotonic_sec=origins[session],
            original_source_elapsed_sec=value['observed_monotonic_sec']-origins[session])
    joined['changed_rows'] = [attribute(v) for v in joined['changed_rows']]
    joined['states'] = {k: attribute(v) for k, v in joined['states'].items()}
    for b in (viewport_summary, viewport['evidence'], source_receipt, case_binding): keep(b)
    for source in sources[:index+1]: require(segments(source['session']) == source['envelope']['journal'], 'Native segment set changed at join completion')
    for b in bindings.values(): verify(b)
    return dict(status='PASS_RESTART_NATIVE_WIDGET_PRIMARY_CONTENT_ONLY', **joined, mode=mode, viewport_index=index,
        current_session=current, native_reviews=native, people_sha256=fingerprint(people),
        viewport_review_sha256=fingerprint(viewport), native_segment_history_entries=count, evidence=list(bindings.values()),
        missing_raw_caption_revisions={n['session_id']: n['captions']['missing_raw_revision_ids'] for n in native},
        partial_only_utterances={n['session_id']: n['raw']['partial_only_utterance_ids'] for n in native},
        primary_caption_text_consistency_reviewed=True, retained_caption_native_content_joined=index == 1,
        roster_and_primary_settings_independently_admitted=False, source_delivery_independently_joined=False,
        application_owner_reviewed=False, complete_pair_lifecycle_reviewed=False, exact_consumed_event_attribution=False,
        source_to_widget_latency_qualified=False, continuous_exposure_measured=False, physical_scanout_measured=False,
        actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False)
