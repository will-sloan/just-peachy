"""Partition closed restart observations. See README_RESTART_OBSERVATIONS.md."""
from pathlib import Path

from application_resources import FIELDS
from common import bind, fingerprint, load, verify
from metric_process import exact_process
from paced_child_admission import assert_plain_path
from restart_pair_evidence import review_pair
from review_application_observations import prepared_context, final_span_census
from review_application_transport import record, finite
from review_resource_evidence import review as review_resources, MAX_LINE, MAX_RECORDS
from review_scoring_bank import require
from review_viewport_evidence import review as review_viewport, decode, MAX_OBSERVATIONS
from viewport_ledger_v2 import MAX_RECORD_BYTES, MAX_SPANS, MAX_ROWS

HERE = Path(__file__).resolve().parent
OWN = ('review_restart_observations.py', 'test_restart_observations.py',
       'probe_restart_observations.py', 'README_RESTART_OBSERVATIONS.md')


def code_bindings():
    bindings = {}
    for name, status in (
        ('RESTART_REVIEW_CHECK_V1.json', 'PASS_RESTART_REVIEW_DEVELOPMENT_ONLY'),
        ('APPLICATION_OBSERVATION_REVIEW_CHECK_V1.json', 'PASS_APPLICATION_OBSERVATION_REVIEW_DEVELOPMENT_ONLY')):
        qb, q = record(HERE/name, HERE)
        require(q['status'] == status, 'Prior observation qualification differs')
        verify(q['private_receipt']); receipt = load(q['private_receipt']['path'])
        admission = receipt['admission']; verify(admission)
        if 'private_admission' in q: require(q['private_admission'] == admission, 'Prior admission binding differs')
        require(exact_process(load(admission['path'])['owner']) is None, 'Prior probe still active')
        for b in [qb]+q['code']:
            verify(b)
            require(b['path'] not in bindings or bindings[b['path']] == b, 'Conflicting observation dependency')
            bindings[b['path']] = b
    for name in OWN:
        b = bind(HERE/name); bindings[b['path']] = b
    return [b for _, b in sorted(bindings.items())]


def session_windows(sessions):
    require(type(sessions) is list and len(sessions) == 2, 'Two released sessions required')
    windows = []
    for index, row in enumerate(sessions):
        start, end = row['source_origin_monotonic_sec'], row['completed_monotonic_sec']
        name = Path(row['native_session']).name
        require(type(row['index']) is int and row['index'] == index and name and '/' not in name
                and finite(start) and finite(end) and 0 < start < end, 'Invalid session window')
        require(not windows or windows[-1]['end'] < start and windows[-1]['session'] != name,
                'Restart session windows overlap or reuse an identity')
        windows.append(dict(index=index, session=name, start=start, end=end))
    return windows


def partition_viewport(summary_binding, *, sessions, index, registry=None, checkpoint=None):
    """Caption-key session attribution, not independent native caption semantics.

    Reconstruct the unchanged ledger first. Inspect every changed row, including
    rows no longer in the terminal snapshot. Preserve first visibility in each
    ledger separately; a retained caption is never a new-session acquisition.
    """
    windows = session_windows(sessions)
    require(type(index) is int and index in (0, 1), 'Invalid viewport session index')
    rebuilt = review_viewport(summary_binding, checkpoint=checkpoint)
    current = windows[index]; known = {w['session']: w for w in windows[:index+1]}
    require(rebuilt['source_origin_monotonic_sec'] == current['start']
            and rebuilt['observations_with_source_clock'] > 0, 'Viewport/source origin differs')
    require(rebuilt['last_observed_monotonic_sec'] <= current['end']
            and (index == 0 or rebuilt['first_observed_monotonic_sec'] >= windows[0]['end']),
            'Viewport escaped its released session interval')
    registry = registry if registry is not None else dict(rows={}, spans={})
    seen = {}; rows = set(); records = 0; updates = 0; total = 0
    with Path(rebuilt['evidence']['path']).open('rb') as stream:
        while True:
            if checkpoint: checkpoint()
            line = stream.readline(MAX_RECORD_BYTES+1)
            if not line: break
            records += 1; total += len(line)
            require(records <= MAX_OBSERVATIONS and len(line) <= MAX_RECORD_BYTES and line.endswith(b'\n'),
                    'Viewport reread exceeds bounds')
            value = decode(line); metadata = value['metadata']; at = metadata['observed_monotonic_sec']
            for change in value['changes']:
                if change['kind'] != 'row': continue
                row = change['row']; key = row.get('caption_key')
                require(type(key) is str and 0 < len(key) <= 512 and '/' in key, 'Caption key has no session')
                session, suffix = key.split('/', 1)
                require(session in known and suffix, 'Foreign or future caption session')
                origin = known[session]['start']
                require(at >= origin and (session != current['session'] or
                        metadata['source_origin_monotonic_sec'] == origin), 'Caption predates its actual source clock')
                for field, identifiers, limit in (('rows', [row['row_id']], 2*MAX_SPANS),
                                                 ('spans', row['span_ids'], 2*MAX_SPANS)):
                    for identifier in identifiers:
                        require(identifier not in registry[field] or registry[field][identifier] == (session, key),
                                'Row/span identity reassigned across captions or sessions')
                        registry[field][identifier] = (session, key)
                    require(len(registry[field]) <= limit, 'Cross-session identity census exceeds bound')
                rows.add(row['row_id']); updates += 1
                for span in row['span_ids']:
                    item = seen.setdefault(span, dict(session=session, caption_key_sha256=fingerprint(key),
                        role='current' if session == current['session'] else 'retained',
                        first_visible_in_this_ledger=None, first_final_visible_in_this_ledger=None))
                    observation = dict(observed_monotonic_sec=at,
                        original_source_elapsed_sec=at-origin,
                        current_ledger_source_elapsed_sec=metadata['source_elapsed_sec'])
                    if row['caption_visible'] and item['first_visible_in_this_ledger'] is None:
                        item['first_visible_in_this_ledger'] = observation
                    if row['caption_visible'] and row['final'] and item['first_final_visible_in_this_ledger'] is None:
                        item['first_final_visible_in_this_ledger'] = observation
    require(records == rebuilt['observations'] and total == rebuilt['evidence']['bytes'], 'Viewport reread census changed')
    # An unchanged row can become final/visible only through a recorded change;
    # metadata-only samples therefore do not create new first-visibility facts.
    verify(summary_binding); verify(rebuilt['evidence'])
    return dict(status='PASS_RESTART_VIEWPORT_SESSION_ATTRIBUTION_ONLY', reconstruction=rebuilt,
        session=current['session'], row_versions=updates, distinct_rows=len(rows), spans=seen,
        current_spans=sum(s['role'] == 'current' for s in seen.values()),
        retained_spans=sum(s['role'] == 'retained' for s in seen.values()),
        native_caption_payloads_joined=False, cross_restart_visibility_continuous=False,
        source_to_widget_latency_qualified=False, integrated_N4_cells=0)


def partition_resources(result_binding, *, sessions, expected_owner, checkpoint=None):
    """Only samples wholly inside a source-to-release window are attributed."""
    windows = session_windows(sessions)
    rebuilt = review_resources(result_binding, expected_owner=expected_owner, require_all_phases=True)
    result = load(result_binding['path']); marks = {r['phase']: r['monotonic_sec'] for r in result['phase_marks']}
    require(result['gpu_visibility_environment'] == '-1', 'CPU-only resource environment differs')
    require(marks['starting'] <= windows[0]['start'] <= marks['running'] < windows[0]['end']
            < windows[1]['start'] <= marks['draining'] <= windows[1]['end'] <= marks['closed'],
            'Restart source/release windows escape pair lifecycle phases')
    groups = {str(i): dict(samples=0, complete_samples=0, first=None, last=None, peaks={}) for i in range(2)}
    outside = crossing = samples = records = total = 0
    with Path(rebuilt['evidence']['path']).open('rb') as stream:
        while True:
            if checkpoint: checkpoint()
            line = stream.readline(MAX_LINE+1)
            if not line: break
            records += 1; total += len(line)
            require(records <= MAX_RECORDS and len(line) <= MAX_LINE and line.endswith(b'\n'), 'Resource reread exceeds bounds')
            row = decode(line)  # Also rejects duplicate keys/nonfinite JSON.
            if row['kind'] != 'sample': continue
            samples += 1; start = row['began_monotonic_sec']; end = row['ended_monotonic_sec']
            matches = [w for w in windows if w['start'] <= start <= end <= w['end']]
            if not matches:
                if any(start < w['end'] and end > w['start'] for w in windows): crossing += 1
                else: outside += 1
                continue
            require(len(matches) == 1, 'Resource sample counted in both sessions')
            group = groups[str(matches[0]['index'])]; group['samples'] += 1
            if not row['tree']['complete']: continue
            group['complete_samples'] += 1
            entry = dict(start=start, end=end, **{f: row['tree'].get(f) for f in FIELDS})
            if group['first'] is None: group['first'] = entry
            group['last'] = entry
            for field in FIELDS:
                value = entry[field]
                if value is not None: group['peaks'][field] = max(group['peaks'].get(field, 0), value)
    require(records == rebuilt['raw_records'] and total == rebuilt['evidence']['bytes']
            and samples == rebuilt['reconstructed']['samples'] == outside+crossing+sum(g['samples'] for g in groups.values()),
            'Resource partition census differs')
    verify(result_binding); verify(rebuilt['evidence'])
    return dict(status='PASS_RESTART_RESOURCE_WINDOW_ATTRIBUTION_ONLY', reconstruction=rebuilt,
        windows=windows, session_samples=groups, outside_samples=outside, boundary_crossing_samples=crossing,
        both_sessions_have_complete_samples=all(g['complete_samples'] > 0 for g in groups.values()),
        controlled_whole_stack_qualified=False, target_qualified=False, deployment_tier='UNKNOWN', integrated_N4_cells=0,
        interpretation='Pair process point samples, including session drain; no per-model cost, peak guarantee or leak diagnosis')


def review_observations(application, *, payload, application_owner, checkpoint=None):
    """Internal independent composition. Supervised transport/selected plan remain separate."""
    pair = review_pair(application, payload=payload, application_owner=application_owner, checkpoint=checkpoint)
    application = Path(application).resolve(strict=True); bindings = {b['path']: b for b in pair['evidence']}
    def keep(b):
        require(b['path'] not in bindings or bindings[b['path']] == b, 'Observation changed after pair review')
        bindings[b['path']] = b
    def read(path):
        b, value = record(path, application); keep(b); return b, value
    _, prepared = read(application/'PREPARED.json'); context = prepared_context(payload, prepared)
    rb, resources = read(application/'resources/RESULT.json')
    resource_review = partition_resources(rb, sessions=pair['sessions'], expected_owner=application_owner, checkpoint=checkpoint)
    keep(resource_review['reconstruction']['evidence']); registry = dict(rows={}, spans={}); reviews = []
    for index, name in enumerate(('01', '02')):
        folder = application/'sessions'/name; _, row = read(folder/'RESULT.json')
        _, snapshot = read(folder/'CONTROLLER_SNAPSHOT.json'); _, observed = read(folder/'ENGINE_CLOSURE.json')
        vp = application/'viewport' if index == 0 else folder/'viewport'
        _, result = read(vp/'RESULT.json'); sb, summary = read(vp/'SUMMARY.json')
        require(row['viewport'] == bind(vp/'RESULT.json') and result['ledger'] == sb, 'Viewport binding differs')
        log = assert_plain_path(summary['log']['path'], vp)
        require(log == vp/'OBSERVATIONS.jsonl', 'Foreign viewport observation log')
        value = partition_viewport(sb, sessions=pair['sessions'], index=index, registry=registry, checkpoint=checkpoint)
        vr = value['reconstruction']; keep(vr['evidence'])
        require(snapshot['state'] == 'STOPPED' and snapshot['error'] is None and snapshot['saved_audio_only'] is True
                and snapshot['epoch'] == pair['sessions'][index]['epoch'] and snapshot['backend_id'] == prepared['backend_id']
                and snapshot['mode'] == payload['contract']['mode'] and snapshot['tap'] == payload['job']['tap']
                and snapshot['recipe'] == 'balanced' and snapshot['selected_ids'] == [] and snapshot['strict'] is False
                and snapshot['pending_actions'] == 0 and snapshot['reference_comparison'] is None
                and not snapshot['settings'].get('text_assistance', False)
                and not snapshot['settings'].get('text_aware_references', False), 'Released Controller configuration differs')
        require(result['samples'] == vr['observations'] and vr['all_present_panes_have_geometry_counters'] is True
                and resources['phase_marks'][2]['monotonic_sec'] <= vr['first_observed_monotonic_sec']
                and observed['observed_monotonic_sec'] <= vr['last_observed_monotonic_sec'], 'Viewport geometry or interval differs')
        for field in ('render_calls', 'periodic_calls', 'deferred_context'):
            require(type(result[field]) is int and result[field] >= 0, 'Invalid viewport callback census')
        require(result['render_calls'] > 0 and 0 < result['periodic_calls'] < vr['observations'], 'Render/timer observations missing')
        value['final_span_census'] = final_span_census(snapshot, summary, log, checkpoint=checkpoint)
        reviews.append(value)
    for b in bindings.values(): verify(b)
    require(exact_process(application_owner) is None, 'Application became active during review')
    return dict(status='PASS_RESTART_OBSERVATION_ATTRIBUTION_ONLY', pair_review=pair, context=context,
        viewport_reviews=reviews, resource_review=resource_review, evidence=list(bindings.values()),
        viewport_rows_reviewed=True, resource_samples_reviewed=True, native_caption_payloads_joined=False,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
        complete_selected_population_reviewed=False, actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False)
