"""Explicit stopped-prefix closure derivative; README_RESTART_SESSION.md.

All earlier qualified helpers remain unchanged. Full planned job and delivered
prefix are distinct. This validates one released session, not a restart pair.
"""
from copy import deepcopy
import importlib
from pathlib import Path
import time
from common import audio_only, fingerprint, load, verify
from application_closure import (ARCHIVE_MODULE, require, persisted, validate_persisted,
                                 thread_state, journal_state, closed_worker)
from restart_source_capture import JOIN_KEYS, POLICY, validate_request
from source_delivery import finite


def validate_clock_join(observed):
    clock = observed.get('controller_clock') or {}; started = clock.get('source_started') or {}
    payload = started.get('event_payload') or {}; job = observed['job']; session = Path(observed['session']).name
    require(clock.get('publication_session') == session and payload.get('session_id') == session, 'source clock session differs')
    require(isinstance(payload.get('path'), str) and Path(payload['path']).resolve() == Path(job['audio_path']).resolve(),
        'source clock file differs')
    require(payload.get('mode') == 'file' and payload.get('pacing') == 'absolute'
        and payload.get('start_sample') == 0 and payload.get('gain') == 1., 'source clock delivery route differs')
    origin = payload.get('source_epoch_monotonic_sec')
    require(type(origin) in (int,float) and origin > 0
        and origin == clock.get('source_epoch_monotonic_sec') == started.get('source_epoch_monotonic_sec'),
        'source origin differs or is missing')
    require(clock.get('errors') == 0 and clock.get('event_counts',{}).get('source_started') == 1,
        'source clock has errors or ambiguous starts')
    census = observed['publication_census']
    require(clock.get('event_count') == census['consumed']
        and clock.get('last_publication_sequence') == census['published']
        and clock.get('missing_publication_sequences') == census['coalesced_obsolete_ui_partials'],
        'source clock and final event census differ')


def capture_engine(engine, consumer, clock, job, release, capture):
    """Inspect retained owners after drain; do not stop, join, close or load.

    Retain engine and consumer references before Controller.stop clears them.
    Controller remains open. Inspect its joined archive separately.
    Original job frames remain unchanged; delivered_frames is an explicit prefix.
    Missing observations remain missing and cannot be converted to zero/success.
    """
    from app.pipeline import FileSource
    verify(capture)
    audio_only(job); source = getattr(engine, '_source', None)
    expected = getattr(source, 'sent', None)
    journals = {name:getattr(engine, name, None) for name in ('_input_journal','_journal','_identity_journal')}
    source_journal = getattr(source, 'journal', None)
    source_row = dict(present=source is not None, actual_FileSource=type(source) is FileSource,
        path=str(getattr(source, 'path', '')) if source is not None else None,
        start_sample=getattr(source, 'start_sample', None), sent=getattr(source, 'sent', None),
        thread=thread_state(getattr(source, 'thread', None)), journal=journal_state(source_journal))
    threads = {'source':getattr(source, 'thread', None), 'consumer':consumer,
        'finalization':getattr(engine, '_finalization_thread', None)}
    for i, thread in enumerate(getattr(engine, '_threads', [])): threads['lane_'+str(i)] = thread
    workers = {}
    for name, worker in (('journal',getattr(engine,'_s6d_writer',None)),
                        ('punctuation',getattr(engine,'_s6d_punctuation',None)),
                        ('policy',getattr(getattr(engine,'_scheduler',None),'worker',None)),
                        ('trace',getattr(engine,'_s7_trace',None))):
        workers[name] = worker.snapshot() if worker is not None else None
        threads[name] = getattr(worker, 'thread', None)
    texts = []
    for i, writer in enumerate(getattr(engine, 'text_writers', [])):
        threads['text_'+str(i)] = writer.thread
        texts.append(dict(closed=writer.closed, error=writer.error, accepted=writer.accepted,
            completed=writer.completed, depth=writer.queue.qsize(), thread_alive=writer.thread.is_alive(),
            sink_closed=writer.sink.closed))
    telemetry = engine.telemetry()
    observed = dict(schema='n4-released-session-engine-closure-v1', delivered_frames=expected,
        release_capture=capture, session_owner_join=dict(
            same_engine=getattr(clock,'engine',None) is engine is release.engine,
            same_controller=getattr(clock,'controller',None) is release.controller,
            retained_consumer_exited=consumer is not None and consumer is release.consumer and not consumer.is_alive(),
            capture_finished=release.finished), observed_monotonic_sec=time.perf_counter(),
        job=deepcopy(job), engine_class=type(engine).__name__, session=str(engine.session_dir) if engine.session_dir else None,
        state=engine.state, finalization_error=str(engine._finalization_error) if engine._finalization_error else None,
        enhancement_route=engine.enhancement_route, enhancement_router_present=engine.enhancement_router is not None,
        source=source_row, journals={k:journal_state(v) for k,v in journals.items()},
        bypass_journals_are_source_journal=source_journal is not None and all(v is source_journal for v in journals.values()),
        threads={k:thread_state(v) for k,v in threads.items()}, workers=workers, text_writers=texts,
        asr_cursor_sec=telemetry.get('asr_cursor_sec'), n3_input_samples=telemetry.get('n3_input_samples'),
        controller_clock=clock.snapshot() if clock is not None else None,
        publication_census=None, publication_census_error=None, persisted=None, persisted_error=None)
    try: observed['publication_census'] = clock.reconcile_inbox() if clock is not None else None
    except Exception as exc: observed['publication_census_error'] = str(exc)
    try: observed['persisted'] = persisted(engine.session_dir, expected)
    except Exception as exc: observed['persisted_error'] = str(exc)
    return observed


def validate_engine(observed):
    require(observed.get('schema') == 'n4-released-session-engine-closure-v1', 'wrong engine closure schema')
    job = audio_only(observed['job']); expected = observed['delivered_frames']; source = observed['source']
    verify(observed['release_capture']); capture = load(observed['release_capture']['path'])
    validate_request(capture.get('request'), job, capture.get('intent'), expected)
    require(capture.get('schema') == 'n4-released-session-delivery-v1' and capture.get('policy') == POLICY
        and capture.get('job_fingerprint') == fingerprint(job), 'release job/schema differs')
    require(capture.get('status') == 'COLLECTED_RELEASED_SESSION_DELIVERY_REQUIRES_REVIEW'
        and capture.get('test_seams_used') is False and capture.get('errors') == [], 'release capture is not clean')
    require(set(capture.get('owner_join',{})) == JOIN_KEYS
        and all(v is True for v in capture['owner_join'].values()), 'Controller session owners not released')
    require(observed.get('session_owner_join') == dict(same_engine=True, same_controller=True, retained_consumer_exited=True, capture_finished=True),
        'retained source clock/consumer differs')
    validate_clock_join(observed)
    require(observed['controller_clock'].get('epoch') == capture['request']['epoch'], 'released epoch differs')
    require(finite(observed.get('observed_monotonic_sec'))
        and observed['observed_monotonic_sec'] >= capture['request']['returned_monotonic_sec'], 'closure precedes stop request')
    require(observed['state'] == 'COMPLETED' and observed['finalization_error'] is None, 'late pipeline/trace failure')
    require(observed['enhancement_route'] == 'bypass' and not observed['enhancement_router_present'], 'primary bypass route changed')
    require(source.get('actual_FileSource') is True, 'no actual saved FileSource')
    require(Path(source['path']).resolve() == Path(job['audio_path']).resolve()
        and source['start_sample'] == 0, 'source path or offset differs')
    require(type(source['sent']) is int and source['sent'] == expected, 'source delivery count differs')
    require(observed['bypass_journals_are_source_journal'] is True, 'bypass journal ownership differs')
    require(set(observed['journals']) == {'_input_journal','_journal','_identity_journal'}, 'journal census missing')
    for name, journal in [('source',source['journal']), *observed['journals'].items()]:
        require(journal.get('actual_MemoryJournal') is True and journal.get('sample_rate') == 16000, name+' journal missing/wrong type')
        require(type(journal.get('committed_samples')) is int and journal['committed_samples'] == expected, name+' sample count differs')
        require(journal['finished'] is True and journal['fatal_error'] is None and journal['overrun_reads'] == 0,
            name+' journal not successfully closed')
    required = {'source','consumer','finalization','journal','punctuation','policy','trace'}
    require(required <= set(observed['threads']), 'owner census missing')
    for name, thread in observed['threads'].items():
        require(thread['present'] is True and thread['started'] is True and thread['alive'] is False, name+' owner absent/unstarted/alive')
    lane_names = {v.get('name') for k,v in observed['threads'].items() if k.startswith('lane_')}
    require({'edge-asr','edge-speaker'} <= lane_names, 'both model lane owners required')
    require(set(observed['workers']) == {'journal','punctuation','policy','trace'}, 'worker census missing')
    for name, row in observed['workers'].items(): closed_worker(row, name)
    require(len(observed['text_writers']) == 3, 'all three actual native text writers required')
    for i, row in enumerate(observed['text_writers']):
        closed_worker(row, 'text_'+str(i)); require(row['sink_closed'] is True, 'text sink not closed')
    cursor = observed['asr_cursor_sec']
    require(type(cursor) in (int,float) and abs(cursor*16000-expected) < .5, 'ASR did not drain all delivered samples')
    if observed['engine_class'] == 'N3IdentityEngine':
        require(type(observed['n3_input_samples']) is int and observed['n3_input_samples'] == expected, 'native ASR input count differs')
    clock = observed['controller_clock']; census = observed['publication_census']
    require(isinstance(clock,dict) and clock.get('source_event_clock_available') is True, 'source origin not observed')
    require(observed['publication_census_error'] is None and isinstance(census,dict)
        and census.get('status') == 'PASS_ACTUAL_EVENT_INBOX_CENSUS', 'event inbox not reconciled')
    require(observed['persisted_error'] is None and observed['persisted'] is not None, 'terminal receipts unavailable')
    terminal = observed['persisted']
    for b in (terminal['finalization'], terminal['consumer']): verify(b)
    require(Path(terminal['finalization']['path']).parent.resolve() == Path(observed['session']).resolve()
        and Path(terminal['consumer']['path']).parent.resolve() == Path(observed['session']).resolve(), 'foreign terminal session')
    checked = validate_persisted(load(terminal['finalization']['path']), load(terminal['consumer']['path']), expected)
    require(checked == terminal['result'], 'persisted review changed')
    for name in ('published','consumed','coalesced_obsolete_ui_partials'):
        require(census[name] == checked[name], 'observed/persisted '+name+' mismatch')
    require(observed['workers']['journal']['accepted'] == checked['published'], 'observed publication writer mismatch')
    return dict(status='PASS_RELEASED_PREFIX_JOURNAL_AND_ENGINE_CLOSURE', planned_frames=job['frames'],
        intent=capture['intent'], same_controller_restart_qualified=False, source_samples=expected,
        published=checked['published'], consumed=checked['consumed'],
        coalesced_obsolete_ui_partials=checked['coalesced_obsolete_ui_partials'],
        source_to_widget_latency_qualified=False, full_application_acceptance=False)


def capture_archive(controller, engine):
    return importlib.import_module(ARCHIVE_MODULE).archive_integrity_receipt(controller, engine)


def validate_complete(observed, archive):
    engine = validate_engine(observed)
    importlib.import_module(ARCHIVE_MODULE).validate_archive_integrity(archive, observed['delivered_frames'])
    require(archive['persisted']['audio_enabled'] is False and archive['persisted']['recorded_samples'] == 0,
        'primary application run must not make a new audio archive')
    epoch = load(archive['epoch']['path'])
    require(Path(epoch['native_session_path']).resolve() == Path(observed['session']).resolve(), 'archive belongs to a different engine session')
    return dict(status='PASS_RELEASED_PREFIX_WORKERS_CONSUMER_AND_ARCHIVE_CLOSURE', same_controller_restart_qualified=False, engine=engine,
        archive_epoch=archive['epoch'], source_to_widget_latency_qualified=False,
        model_accuracy_qualified=False, controlled_resources_qualified=False, integrated_N4_cells=0)
