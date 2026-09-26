"""Fabricated delivery evidence only; README_APPLICATION_TRANSPORT_REVIEW_V3.md.

No audio/model/application execution. These values cannot establish production
admission; callers supply explicitly synthetic transport/owner facts.
"""
from copy import deepcopy
import json
from pathlib import Path

from common import bind, fingerprint, freeze, load
from application_delivery import review_files
from paced_panel_plan_v3 import APPLICATION_POLICY
from source_delivery import CHUNK, FORMAT, RECORD, summarize


def rewrite(path,value):
    path.write_text(json.dumps(value,allow_nan=False),encoding='utf-8')


def rebind_delivery(folder,payload):
    """Refresh only fabricated fixture receipts after deliberate test mutation."""
    app=folder/'application';source=load(payload['source_receipt']['path']);prototype=Path(source['prototype'])
    files=[dict(path=str((prototype/name).resolve()),**source['files'][name])
        for name in ('app/pipeline.py','app/buffers.py')]
    rebuilt=review_files(app,payload['job'],payload['contract'],files)
    cell=load(app/'RESULT.json');cell.update(application_variant=APPLICATION_POLICY['variant'],
        delivery_policy=deepcopy(APPLICATION_POLICY['delivery']),delivery_capture=bind(app/'delivery/CAPTURE.json'),delivery_join=rebuilt)
    rewrite(app/'RESULT.json',cell)
    rewrite(folder/'SOURCE_DELIVERY_ENVELOPE.json',dict(schema='n4-cell-source-delivery-envelope-v1',
        cell_id=payload['cell_id'],job_sha256=fingerprint(payload['job']),contract_sha256=fingerprint(payload['contract']),
        application_policy=deepcopy(APPLICATION_POLICY),source_receipt=payload['source_receipt'],cell_result=bind(app/'RESULT.json'),
        review=rebuilt,independent_parent_read=True,integrated_N4_cells=0,N4_accepted=False))
    child_path=folder/'transport/CHILD_RESULT.json'
    if child_path.exists():
        child=load(child_path);child['cell_result']=bind(app/'RESULT.json');rewrite(child_path,child)
    collected_path=folder/'COLLECTED.json'
    if collected_path.exists():
        collected=load(collected_path);collected.update(source_delivery_envelope=bind(folder/'SOURCE_DELIVERY_ENVELOPE.json'),
            child_result=bind(child_path),application_policy=deepcopy(APPLICATION_POLICY));rewrite(collected_path,collected)


def add_delivery(folder,payload):
    """Add explicit synthetic constant-lateness append records to fixture facts."""
    app=folder/'application';observed=load(app/'ENGINE_CLOSURE.json');job=payload['job'];frames=job['frames']
    if 'controller_clock' not in observed:
        event=dict(path=job['audio_path'],session_id=Path(observed['session']).name,mode='file',pacing='absolute',
            start_sample=0,gain=1.,source_epoch_monotonic_sec=100.)
        clock=dict(publication_session=event['session_id'],source_epoch_monotonic_sec=100.,
            source_started=dict(event_payload=event,source_epoch_monotonic_sec=100.),errors=0,
            event_counts=dict(source_started=1),event_count=6,last_publication_sequence=6,missing_publication_sequences=0)
        observed.update(controller_clock=clock,source_clock_owner_join=dict(same_engine=True,consumer_retained=True),
            publication_census=dict(consumed=6,published=6,coalesced_obsolete_ui_partials=0),
            source=dict(actual_FileSource=True,path=job['audio_path'],start_sample=0,sent=frames,
                journal=dict(committed_samples=frames),thread=dict(present=True,started=True,alive=False)))
        rewrite(app/'ENGINE_CLOSURE.json',observed);freeze(app/'SOURCE_CLOCK.json',clock)
    origin=observed['controller_clock']['source_epoch_monotonic_sec'];raw=bytearray()
    for start in range(0,frames,CHUNK):
        count=min(CHUNK,frames-start);at=origin+(start+count)/16000+.002
        raw.extend(RECORD.pack(start,count,start+count,at,at+.001,0))
    raw=bytes(raw);summary=summarize(raw,origin=origin,frames=frames,sent=frames,committed=frames)
    observation=dict(schema='n4-source-delivery-v1',status='OBSERVED_FULL_SOURCE_DELIVERY_REQUIRES_REVIEW',
        test_seams_used=False,errors={},job_fingerprint=fingerprint(job),expected_frames=frames,sample_rate_hz=16000,
        chunk_samples=CHUNK,trace_format=FORMAT,trace_bytes=len(raw),trace_capacity_bytes=len(raw),
        source_origin_perf_counter=origin,source_sent=frames,journal_committed=frames,source_thread_exited=True,
        journal_finished=True,journal_had_fatal_error=False,source_fatal_seen=False,source_start_events=1,
        audio_copied_or_transformed=False,source_pacer_changed=False,source_stop_requested_by_observer=False,
        actual_application_integration_qualified=False,timing_or_continuity_accepted=False,observer_cost_not_subtracted=True,
        summary=summary,append_attempts=summary['records'])
    freeze(app/'delivery/OBSERVATION.json',observation);(app/'delivery/TRACE.bin').write_bytes(raw)
    source=load(payload['source_receipt']['path']);prototype=Path(source['prototype'])
    files=[dict(path=str((prototype/name).resolve()),**source['files'][name])
        for name in ('app/pipeline.py','app/buffers.py')]
    freeze(app/'delivery/CAPTURE.json',dict(schema='n4-application-delivery-capture-v1',
        status='COLLECTED_APPLICATION_DELIVERY_REQUIRES_REVIEW',policy=APPLICATION_POLICY['delivery'],
        job_fingerprint=fingerprint(job),contract_fingerprint=fingerprint(payload['contract']),source_files=files,
        test_seams_used=False,launch_attempts=1,installed=True,launch_hook_restored=True,original_start_raised=False,errors=[],
        owner_join=dict(same_retained_engine=True,same_source=True,same_journal=True,controller_closed=True,controller_worker_exited=True),
        observation=bind(app/'delivery/OBSERVATION.json'),trace=bind(app/'delivery/TRACE.bin')))
    rebind_delivery(folder,payload)
