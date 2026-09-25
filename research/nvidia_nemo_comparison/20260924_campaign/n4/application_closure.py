"""Read-only source, worker and persisted closure checks. README_APPLICATION_CLOSURE.md."""
from copy import deepcopy
import importlib
from pathlib import Path
import time

from common import audio_only, bind, load, verify

HANDLES = {'_event_handle', '_transcript_handle', '_readable_transcript_handle'}
ARCHIVE_MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_a1'


def require(value, reason):
    if not value: raise ValueError('Application closure: '+reason)


def closed_worker(row, name):
    require(isinstance(row, dict), name+' worker missing')
    require(row.get('closed') is True and row.get('thread_alive') is False, name+' owner not closed')
    require(row.get('error') is None and row.get('depth') == 0, name+' error or undrained queue')
    require(type(row.get('accepted')) is int and type(row.get('completed')) is int
        and 0 <= row['accepted'] == row['completed'], name+' accepted/completed mismatch')
    if 'overflow' in row: require(row['overflow'] == 0, name+' overflow')


def validate_persisted(finalization, consumer, expected_samples):
    """Validate the final checkpoint and consumer receipt, never early summary.

    Full event publication equals journal work; coalesced obsolete partials
    remain explicit and must reconcile to the actual consumer's census.
    """
    require(type(expected_samples) is int and expected_samples > 0, 'positive expected samples required')
    require(finalization.get('schema_version') == 'edge-session-finalization.v3', 'wrong finalization schema')
    require(finalization.get('state') == 'COMPLETED' and finalization.get('finalization_error') is None,
        'pipeline did not finalize successfully')
    require(finalization.get('live_lanes_at_finalization') == [], 'live lanes remain')
    require(finalization.get('resident_bundle_lease_retained') is False
        and finalization.get('resident_bundle_reuse_allowed') is True, 'resident lease not released')
    require(finalization.get('event_and_transcript_handles_closed') is True, 'native handles not closed')
    handles = finalization.get('handle_close_results', {})
    require(set(handles) == HANDLES, 'incomplete native handle census')
    for name, row in handles.items():
        require(row.get('closed') is True and row.get('error') is None and row.get('was_opened') is True,
            'missing/failed handle: '+name)
    for key in ('source_samples', 'identity_samples'):
        require(type(finalization.get(key)) is int and finalization[key] == expected_samples, key+' mismatch')
    require(consumer.get('full_event_consumer_drained') is True and consumer.get('state') == 'COMPLETED',
        'consumer did not fully drain a completed session')
    queues = consumer.get('queues', {}); inbox = queues.get('event_consumer', {})
    require(inbox.get('depth') == 0, 'consumer queue not empty')
    for key in ('consumed', 'coalesced_obsolete_ui_partials'):
        require(type(inbox.get(key)) is int and inbox[key] >= 0, 'invalid inbox '+key)
    for name in ('journal', 'punctuation', 'policy'): closed_worker(queues.get(name), name)
    published = queues['journal']['accepted']
    require(published > 0 and published == inbox['consumed']+inbox['coalesced_obsolete_ui_partials'],
        'journal/publication and consumed/coalesced events disagree')
    return dict(status='PASS_PERSISTED_FINALIZATION_AND_CONSUMER', published=published,
        consumed=inbox['consumed'], coalesced_obsolete_ui_partials=inbox['coalesced_obsolete_ui_partials'],
        source_samples=expected_samples, identity_samples=expected_samples,
        current_source_and_worker_objects_observed=False, full_application_acceptance=False)


def persisted(session, expected_samples):
    paths = [Path(session)/name for name in ('session_finalization_v3.json','s6d_consumer_closure.json')]
    require(all(p.is_file() and p.stat().st_size <= 256*1024 for p in paths), 'missing/oversize terminal receipts')
    bindings = [bind(p) for p in paths]
    result = validate_persisted(load(paths[0]), load(paths[1]), expected_samples)
    return dict(result=result, finalization=bindings[0], consumer=bindings[1])


def thread_state(thread):
    if thread is None: return dict(present=False, started=False, alive=None)
    return dict(present=True, started=thread.ident is not None, alive=thread.is_alive(),
        name=thread.name, ident=thread.ident, native_id=getattr(thread, 'native_id', None))


def journal_state(journal):
    from app.buffers import MemoryJournal
    if journal is None: return dict(present=False)
    return dict(present=True, actual_MemoryJournal=type(journal) is MemoryJournal,
        sample_rate=getattr(journal, 'sample_rate', None), committed_samples=getattr(journal, 'committed_samples', None),
        finished=getattr(journal, 'finished', None), fatal_error=getattr(journal, 'fatal_error', None),
        overrun_reads=getattr(journal, 'overrun_reads', None), capacity=getattr(journal, 'capacity', None))


def capture_engine(engine, consumer, clock, job):
    """Inspect retained owners after drain; do not stop, join, close or load.

    Retain engine and consumer references before Controller.close clears them.
    Caller must separately close the Controller and inspect its joined archive.
    Missing observations remain missing and cannot be converted to zero/success.
    """
    from app.pipeline import FileSource
    audio_only(job); source = getattr(engine, '_source', None)
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
    observed = dict(schema='n4-application-engine-closure-v1', observed_monotonic_sec=time.perf_counter(),
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
    try: observed['persisted'] = persisted(engine.session_dir, job['frames'])
    except Exception as exc: observed['persisted_error'] = str(exc)
    return observed


def validate_engine(observed):
    require(observed.get('schema') == 'n4-application-engine-closure-v1', 'wrong engine closure schema')
    job = audio_only(observed['job']); expected = job['frames']; source = observed['source']
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
    return dict(status='PASS_SOURCE_JOURNAL_AND_ENGINE_CLOSURE', source_samples=expected,
        published=checked['published'], consumed=checked['consumed'],
        coalesced_obsolete_ui_partials=checked['coalesced_obsolete_ui_partials'],
        source_to_widget_latency_qualified=False, full_application_acceptance=False)


def capture_archive(controller, engine):
    return importlib.import_module(ARCHIVE_MODULE).archive_integrity_receipt(controller, engine)


def validate_complete(observed, archive):
    engine = validate_engine(observed)
    importlib.import_module(ARCHIVE_MODULE).validate_archive_integrity(archive, observed['job']['frames'])
    require(archive['persisted']['audio_enabled'] is False and archive['persisted']['recorded_samples'] == 0,
        'primary application run must not make a new audio archive')
    epoch = load(archive['epoch']['path'])
    require(Path(epoch['native_session_path']).resolve() == Path(observed['session']).resolve(), 'archive belongs to a different engine session')
    return dict(status='PASS_SOURCE_WORKERS_CONSUMER_AND_ARCHIVE_CLOSURE', engine=engine,
        archive_epoch=archive['epoch'], source_to_widget_latency_qualified=False,
        model_accuracy_qualified=False, controlled_resources_qualified=False, integrated_N4_cells=0)
