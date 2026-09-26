"""Independent two-session receipt composition. See README_RESTART_PAIR_EVIDENCE.md."""
from pathlib import Path

from common import bind, fingerprint, verify
from metric_process import exact_process
from paced_child_admission import assert_plain_path
from restart_application_child import closed_result, control
from restart_application_cell import POLICY as CELL_POLICY
from restart_archive import validate_complete
from restart_native_journal import inspect, require_complete
from restart_source_capture import validate_delivery
from review_application_transport import finite, record
from review_scoring_bank import require
from source_delivery import CHUNK, RECORD

LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local/n4')
OWN = ('restart_pair_evidence.py', 'test_restart_pair_evidence.py',
       'probe_restart_pair_evidence.py', 'README_RESTART_PAIR_EVIDENCE.md')
HERE = Path(__file__).resolve().parent
QUALIFICATIONS = {
    'RESTART_CHILD_CHECK_V1.json': 'PASS_RESTART_CHILD_DEVELOPMENT_ONLY',
    'RESTART_NATIVE_CHECK_V1.json': 'PASS_RELEASED_NATIVE_REVIEW_DEVELOPMENT_ONLY',
}


def code_bindings():
    """Parent-only union; the qualified child keeps its unchanged 122 records."""
    result = {}
    for name, status in QUALIFICATIONS.items():
        qb, q = record(HERE/name, HERE)
        require(q['status'] == status, 'Restart evidence prerequisite differs')
        for b in [qb, *q['code']]:
            verify(b)
            require(b['path'] not in result or result[b['path']] == b, 'Conflicting review dependency')
            result[b['path']] = b
    for name in OWN:
        b = bind(HERE/name); result[b['path']] = b
    return [b for _, b in sorted(result.items())]


def join_session(row, capture, observed, clock, delivery, closure, native, *, job, contract, index, epoch):
    """Compare independently reconstructed readers without altering their facts."""
    intent = ('mid_file_stop', 'completed_release')[index]
    require(row['status'] == 'COLLECTED_RESTART_SESSION_REQUIRES_REVIEW'
        and type(row['index']) is int and row['index'] == index and row['intent'] == intent
        and row['job'] == observed['job'] == job and observed['engine_class'] == contract['engine'],
        'Session identity, full job or engine differs')
    require(type(epoch) is int and epoch > 0 and type(row['controller_epoch']) is int
        and row['controller_epoch'] == capture['request']['epoch'] == clock['epoch'] == epoch,
        'Session epoch differs')
    require(row['actual_restart_qualified'] is False and type(row['integrated_N4_cells']) is int
        and row['integrated_N4_cells'] == 0, 'Session collection cannot grant acceptance')
    require(row['native_session'] == observed['session']
        and clock == observed['controller_clock'], 'Native session or persisted source clock differs')
    require(delivery['status'] == 'PASS_RELEASED_SESSION_DELIVERY_ONLY'
        and delivery['intent'] == capture['intent'] == intent
        and row['delivery_join'] == delivery and row['closure'] == closure,
        'Child and independently reconstructed release reviews differ')
    sent = delivery['delivered_frames']; require(type(sent) is int and sent > 0, 'Invalid delivered count')
    require(closure['status'] == 'PASS_RELEASED_SESSION_ENGINE_AND_OPEN_CONTROLLER_ARCHIVE'
        and closure['controller_still_open'] is True and closure['same_controller_restart_qualified'] is False,
        'Released engine/archive closure required')
    require((0 < sent < job['frames'] and sent % CHUNK == 0) if index == 0 else sent == job['frames'],
        'Wrong partial/full source coverage')
    require(sent == observed['delivered_frames'] == observed['source']['sent']
        == closure['engine']['source_samples'] == native['delivered_audio_frames']
        == delivery['summary']['successful_samples'], 'Delivered source census differs')
    require(native['planned_audio_frames'] == delivery['planned_frames'] == job['frames']
        and native['job_fingerprint'] == fingerprint(job) and native['intent'] == intent,
        'Native or delivery reader changed the full planned source')
    require_complete(native)
    terminal = {Path(b['path']).name: b for b in native['terminal']}
    require(len(native['terminal']) == len(terminal) == 2 and terminal == {
        'session_finalization_v3.json': observed['persisted']['finalization'],
        's6d_consumer_closure.json': observed['persisted']['consumer']}, 'Terminal engine/native bindings differ')
    source = native['source_start']; event = clock['source_started']['event_payload']
    origin = delivery['source_origin_perf_counter']
    require(finite(origin) and 0 < origin == source['source_epoch_monotonic_sec']
        == clock['source_epoch_monotonic_sec'], 'Source trace/native/consumer origins differ')
    require(source['sequence'] == event['publication_sequence']
        and source['publication_monotonic_sec'] == event['publication_monotonic_sec']
        and event['publication_source_cursor_sec'] == 0, 'Source-start publication differs')
    census = observed['publication_census']
    require(native['expected_events'] == native['retained_events'] == census['published']
        == clock['last_publication_sequence'] and clock['event_count'] == census['consumed']
        and clock['missing_publication_sequences'] == census['coalesced_obsolete_ui_partials'],
        'Native/consumer event census differs')
    last_append = origin + delivery['summary']['last_append_return_after_origin_seconds']
    completed = row['completed_monotonic_sec']; captured = observed['observed_monotonic_sec']
    require(all(finite(v) and v > 0 for v in (last_append, completed, captured))
        and last_append <= captured <= completed
        and native['completion_publication_monotonic_sec'] <= captured,
        'Session closure precedes delivery or native completion')
    return dict(index=index, intent=intent, epoch=epoch, native_session=observed['session'],
        delivered_frames=sent, source_origin_monotonic_sec=origin, completed_monotonic_sec=completed,
        last_append_monotonic_sec=last_append, native_events=native['retained_events'])


def join_pair(pair, sessions, *, owner, initial_epoch, planned_control, session_bindings):
    require(pair['schema'] == 'n4-same-controller-restart-observation-v1', 'Wrong pair observation')
    for name in ('same_controller', 'same_ui', 'same_tk_root', 'same_command_worker', 'same_model_store',
                 'distinct_engines_sources_journals_consumers_clocks_viewports', 'source_jobs_unchanged',
                 'second_origin_after_first_release', 'controller_still_open'):
        require(pair.get(name) is True, 'Pair owner/lifecycle observation failed: '+name)
    require(type(initial_epoch) is int and initial_epoch >= 0 and type(pair['initial_epoch']) is int
        and pair['initial_epoch'] == initial_epoch, 'Initial Controller epoch differs')
    require(pair['process_owner'] == owner and pair['session_receipts'] == session_bindings,
        'Pair process or session receipts differ')
    require(pair['actual_restart_qualified'] is False and type(pair['integrated_N4_cells']) is int
        and pair['integrated_N4_cells'] == 0, 'Pair collection cannot grant acceptance')
    require(len(sessions) == 2 and [r['index'] for r in sessions] == [0, 1], 'Exactly two ordered sessions required')
    require(pair['consecutive_epochs'] == [r['epoch'] for r in sessions] == [initial_epoch+1, initial_epoch+2]
        and all(type(v) is int for v in pair['consecutive_epochs'])
        and pair['source_start_samples'] == [0, 0] and all(type(v) is int for v in pair['source_start_samples']),
        'Pair epochs or zero source offsets differ')
    native = [r['native_session'] for r in sessions]
    require(pair['native_sessions'] == native and len(set(native)) == 2, 'Native session reuse or mismatch')
    require(type(pair['planned_stop_after_samples']) is int
        and pair['planned_stop_after_samples'] == planned_control['stop_after_samples'], 'Pair stop policy differs')
    require(sessions[0]['delivered_frames'] >= planned_control['stop_after_samples'], 'Stopped before admitted threshold')
    require(sessions[1]['source_origin_monotonic_sec'] > sessions[0]['completed_monotonic_sec'],
        'Second session began before first release completed')
    return dict(status='PASS_RECORDED_SAME_CONTROLLER_PAIR_JOINS_ONLY', sessions=2,
        first_delivered_frames=sessions[0]['delivered_frames'], second_delivered_frames=sessions[1]['delivered_frames'],
        independent_object_identity_instrumentation=False, actual_restart_qualified=False)


def review_pair(application, *, payload, application_owner, checkpoint=None):
    """Read closed fixed paths. Caller separately validates supervised transport/lifetime."""
    application = assert_plain_path(application, LOCAL); planned = control(payload)
    require(application.name == 'application' and exact_process(application_owner) is None,
        'Review requires an exited exact application owner')
    bindings = {}
    def keep(b):
        require(b['path'] not in bindings or bindings[b['path']] == b, 'Evidence changed between reads')
        bindings[b['path']] = b
    def read(path, root=application):
        if checkpoint: checkpoint()
        b, value = record(path, root); keep(b); return b, value
    def linked(row, key, path):
        b, value = read(path); require(row[key] == b, 'Foreign fixed evidence binding: '+key); return value
    sb, source = read(Path(payload['source_receipt']['path']), Path(payload['source_receipt']['path']).parent)
    require(sb == payload['source_receipt'], 'Source receipt differs')
    source_files = [dict(path=str((Path(source['prototype'])/name).resolve()), **source['files'][name])
                    for name in ('app/pipeline.py', 'app/buffers.py')]
    for b in source_files: verify(b); keep(b)
    result_binding, result = read(application/'RESULT.json'); closed_result(result, application)
    require(result['policy'] == CELL_POLICY, 'Restart lifecycle policy differs')
    _, prepared = read(application/'RESTART_PREPARED.json')
    require(prepared['status'] == 'PREPARED_RESTART_PAIR_NO_SOURCE_STARTED' and prepared['policy'] == CELL_POLICY
        and prepared['job'] == payload['job'] and prepared['contract'] == payload['contract']
        and prepared['resources_owner'] == application_owner
        and prepared['actual_restart_qualified'] is False and prepared['integrated_N4_cells'] == 0,
        'Pair preparation or owner differs')
    base = linked(prepared, 'inherited_preparation', application/'PREPARED.json')
    require(base['status'] == 'PREPARED_NO_SOURCE_OR_MODELS_STARTED' and base['no_auto_start'] is True
        and base['job'] == payload['job'] and base['contract'] == payload['contract']
        and base['runtimes'] == payload['runtimes'] and base['gallery_preparation'] == payload['gallery_preparation']
        and base['logical_client'] == [480, 800] and base['active_height_px'] == 184, 'Inherited preparation differs')
    pair = linked(result, 'pair_observation', application/'PAIR_OBSERVATION.json')
    resources = linked(result, 'resources', application/'resources/RESULT.json')
    require(resources['status'] == 'OBSERVED_HOST_RESOURCES' and resources['error'] is None
        and resources['owner'] == application_owner and resources['observer_thread_exited'] is True,
        'Resource observer owner/closure differs')
    sessions = []; native_reviews = []; source_reviews = []
    for index, n in enumerate(('01', '02')):
        folder = application/'sessions'/n; rb, row = read(folder/'RESULT.json')
        require(result['sessions'][index] == rb, 'Session binding differs')
        capture = linked(row, 'delivery_capture', folder/'delivery/CAPTURE.json')
        value = linked(capture, 'observation', folder/'delivery/OBSERVATION.json')
        trace = assert_plain_path(folder/'delivery/TRACE.bin', application)
        require(trace.is_file() and 0 < trace.stat().st_size <= ((payload['job']['frames']+CHUNK-1)//CHUNK)*RECORD.size,
            'Raw source trace exceeds full-job bound')
        tb = bind(trace); keep(tb); raw = trace.read_bytes(); verify(tb)
        require(capture['trace'] == tb and capture['source_files'] == source_files, 'Foreign trace or source code')
        delivery = validate_delivery(value, raw, capture, payload['job'], payload['contract'])
        if index == 0:
            require(capture['request']['source_sent_before'] >= planned['stop_after_samples'],
                'Public stop requested before the planned threshold')
        observed = linked(row, 'engine_closure', folder/'ENGINE_CLOSURE.json')
        require(observed['release_capture'] == row['delivery_capture'], 'Engine uses another capture')
        archive = linked(row, 'archive', folder/'ARCHIVE_INTEGRITY.json')
        ep, _ = read(Path(archive['epoch']['path']), application/'data')
        require(ep == archive['epoch'], 'Archive epoch binding differs')
        clock = linked(row, 'source_clock', folder/'SOURCE_CLOCK.json')
        native_path = assert_plain_path(Path(observed['session']), application/'data/sessions')
        require(native_path.parent == application/'data/sessions', 'Native session must be a direct child')
        closure = validate_complete(observed, archive)
        native = inspect(native_path, job=payload['job'], delivered_frames=delivery['delivered_frames'],
                         intent=capture['intent'], checkpoint=checkpoint)
        for b in native['journal']+native['terminal']: keep(b)
        sessions.append(join_session(row, capture, observed, clock, delivery, closure, native,
            job=payload['job'], contract=payload['contract'], index=index, epoch=prepared['initial_epoch']+index+1))
        native_reviews.append(native); source_reviews.append(delivery)
        scope = linked(row, 'viewport_scope', folder/'VIEWPORT_SCOPE.json')
        require(scope == dict(schema='n4-restart-viewport-session-scope-v1', native_session=str(native_path),
            publication_session=native_path.name, controller_epoch=row['controller_epoch'],
            prior_native_sessions=[s['native_session'] for s in sessions[:-1]], prior_caption_history_retained=True,
            all_rows_have_current_source_clock=False, source_to_widget_latency_qualified=False,
            instruction='Match caption keys/publication sessions before interpreting each row; old history is not new-session output'),
            'Viewport session scope differs')
        vp = application/'viewport' if index == 0 else folder/'viewport'
        viewport = linked(row, 'viewport', vp/'RESULT.json')
        require(viewport['status'] == 'RECORDED_RENDER_AND_TIMER_OBSERVATIONS' and viewport['failure'] is None
            and viewport['timer_cancelled'] is True and viewport['source_to_widget_latency_qualified'] is False
            and viewport['integrated_N4_cells'] == 0, 'Viewport observation failed or claimed acceptance')
        linked(viewport, 'ledger', vp/'SUMMARY.json')
        linked(row, 'controller_snapshot', folder/'CONTROLLER_SNAPSHOT.json')
    joined = join_pair(pair, sessions, owner=application_owner, initial_epoch=prepared['initial_epoch'],
        planned_control=planned, session_bindings=result['sessions'])
    for b in bindings.values(): verify(b)
    require(exact_process(application_owner) is None, 'Application identity became live during review')
    return dict(status='PASS_COMPLETE_RESTART_PAIR_EVIDENCE_JOINS_ONLY', cell_id=payload['cell_id'],
        full_job_sha256=fingerprint(payload['job']), cell_result=result_binding, application_owner=application_owner,
        control=planned, pair_join=joined, sessions=sessions, native_reviews=native_reviews,
        source_reviews=source_reviews, evidence=list(bindings.values()),
        process_transport_reviewed=False, viewport_rows_reviewed=False, resource_samples_reviewed=False,
        complete_selected_panel_reviewed=False, actual_restart_qualified=False,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
        integrated_N4_cells=0, N4_accepted=False)
