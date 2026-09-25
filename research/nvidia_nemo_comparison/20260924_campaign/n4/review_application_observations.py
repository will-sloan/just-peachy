"""Join a stopped cell's independent observations. README_APPLICATION_OBSERVATION_REVIEW.md."""
from pathlib import Path

from application_closure_v2 import validate_complete
from application_resources import PHASES
from common import bind, fingerprint, load, verify
from mode_galleries import backend_contract
from paced_child_admission import assert_plain_path
from review_application_transport import finite, record, review_cell as review_transport
from review_resource_evidence import review as review_resources
from review_scoring_bank import require
from review_viewport_evidence import review as review_viewport
from viewport_ledger_v2 import read_row


def prepared_context(payload, prepared):
    """Reconstruct declared backend/gallery/frontend joins, without loading models."""
    for b in (payload['source_receipt'],payload['catalog'],payload['gallery_preparation']): verify(b)
    source=load(payload['source_receipt']['path']); catalog=load(payload['catalog']['path'])
    prototype=Path(source['prototype']); ui=dict(path=str((prototype/'app/ui.py').resolve()),**source['files']['app/ui.py'])
    verify(ui); require(prepared['source']==ui,'Prepared frontend is not the bound source')
    require(bind(prototype/'config/backends.json')==payload['catalog'],'Source catalog differs')
    contract=backend_contract(catalog,payload['contract']['backend_key'],payload['contract']['mode'])
    require(contract==payload['contract']==prepared['contract'],'Prepared backend contract differs')
    row=next(r for r in catalog['backends'] if r['key']==contract['backend_key'])
    require(row['manifest_id']=='sha256:'+fingerprint(row['composition']),'Backend composition manifest digest differs')
    require(prepared['backend_id']==row['manifest_id'],'Prepared backend ID differs from catalog')
    galleries=load(payload['gallery_preparation']['path'])
    require(galleries['status']=='PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY' and galleries['catalog']==payload['catalog'],
        'Prepared gallery catalog differs')
    condition=galleries['encoders'][contract['encoder']]['conditions'][contract['gallery_condition']]['condition']
    require(prepared['gallery_condition']==condition and prepared['selected_ids']==[], 'Primary open gallery condition or selection differs')
    return dict(frontend=ui,backend_id=row['manifest_id'],engine=contract['engine'],gallery_condition_sha256=fingerprint(condition))


def validate_clock_and_phases(payload, prepared, observed, clock, snapshot, resource, viewport, viewport_result):
    """Cross-clock joins use only this application's perf_counter observations."""
    require(observed['job']==payload['job'] and observed['engine_class']==payload['contract']['engine'],
        'Source closure belongs to a different job or backend engine')
    require(fingerprint(clock)==fingerprint(observed['controller_clock']), 'Terminal and closure source clocks differ')
    require(clock['schema']=='n4-consumer-source-clock-v1' and clock['source_event_clock_available'] is True
        and clock['installed'] is True and clock['errors']==0 and clock['violations']==[]
        and clock['violations_truncated'] is False, 'Source clock unavailable, detached early or failed')
    for field in ('actual_source_delivery_verified','full_event_consumer_closure_verified','source_to_widget_latency_qualified'):
        require(clock[field] is False,'Clock collector improperly asserted acceptance')
    require(snapshot['state']=='STOPPED' and snapshot['error'] is None and snapshot['saved_audio_only'] is True
        and snapshot['backend_id']==prepared['backend_id'] and snapshot['epoch']==clock['epoch']
        and snapshot['mode']==payload['contract']['mode'] and snapshot['recipe']=='balanced'
        and snapshot['tap']==payload['job']['tap'] and snapshot['selected_ids']==[] and snapshot['strict'] is False
        and snapshot['pending_actions']==0, 'Final Controller state differs from the prepared primary cell')
    settings=snapshot['settings']
    require(not settings.get('text_assistance',False) and not settings.get('text_aware_references',False)
        and snapshot['reference_comparison'] is None,'Primary assistance/reference comparison changed')
    require(resource['gpu_visibility_environment']=='-1','Child GPU environment differs from CPU-only launcher')
    marks=resource['phase_marks'];require([r['phase'] for r in marks]==list(PHASES),'Application lifecycle phase census differs')
    times={r['phase']:r['monotonic_sec'] for r in marks}
    origin=clock['source_epoch_monotonic_sec']; captured=observed['observed_monotonic_sec']
    require(finite(origin) and times['starting']<=origin<=times['draining']
        and finite(captured) and times['draining']<=captured<=times['closed'], 'Source/closure clocks escape lifecycle phases')
    require(viewport['source_origin_monotonic_sec']==origin and viewport['observations_with_source_clock']>0,
        'Viewport and actual source origins differ or are absent')
    require(times['gallery_ready']<=viewport['first_observed_monotonic_sec']<=viewport['last_observed_monotonic_sec']
        <=times['bootstrap']+resource['elapsed_sec'], 'Viewport observations escape the application resource interval')
    require(viewport['last_observed_monotonic_sec']>=captured,'Final viewport observation predates closed engine capture')
    require(viewport['all_present_panes_have_geometry_counters'] is True,'Viewport lacks actual geometry counter fields')
    require(viewport_result['status']=='RECORDED_RENDER_AND_TIMER_OBSERVATIONS' and viewport_result['failure'] is None
        and viewport_result['timer_cancelled'] is True and viewport_result['samples']==viewport['observations'],
        'Viewport observer failed, remains open or has a different sample census')
    for field in ('render_calls','periodic_calls','deferred_context'):
        require(type(viewport_result[field]) is int and viewport_result[field]>=0,'Invalid viewport callback census')
    require(viewport_result['render_calls']>0 and viewport_result['periodic_calls']>0
        and viewport_result['periodic_calls']<viewport['observations'], 'Actual render/timer observations missing')
    for field in ('actual_source_delivery_verified','source_to_widget_latency_qualified','physical_scanout_measured'):
        require(viewport_result[field] is False,'Viewport collector improperly asserted acceptance')
    require(viewport_result['integrated_N4_cells']==0,'Viewport collector counted accepted N4 cells')
    return dict(source_origin_monotonic_sec=origin,marked_startup_to_source_seconds=origin-times['starting'],
        source_to_draining_seconds=times['draining']-origin,source_audio_seconds=payload['job']['frames']/16000,
        draining_to_closed_seconds=times['closed']-times['draining'],
        interpretation='Phase intervals and same-process clock joins; no pacing-error subtraction or latency acceptance')


def final_span_census(snapshot, summary, log_path, *, checkpoint=None):
    """Join final Controller metadata to latest observed rows, preserving missing visibility."""
    rows=snapshot['rows'];require(type(rows) is list and len(rows)<=512,'Final Controller row census exceeds bound')
    row_ids=set();spans=set();final_spans=set();invisible=0;without_final=0;cache={}
    for row in rows:
        if checkpoint:checkpoint()
        rid=str(row['id']);require(rid not in row_ids,'Duplicate final Controller row');row_ids.add(rid)
        ids=[str(v) for v in row.get('span_ids') or [rid]]
        require(ids and len(ids)==len(set(ids)) and not spans.intersection(ids),'Duplicate final Controller span')
        spans.update(ids);require(len(spans)<=8192,'Final span census exceeds bound')
        fields=dict(row_id=rid,caption_key=row.get('caption_key'),span_ids=ids,final=bool(row.get('final')),
            raw_asr_text=row.get('raw_asr_text'),source_start_sec=row.get('source_start_sec'),source_end_sec=row.get('source_end_sec'),
            timing_kind=row.get('timing_kind'),speaker_revision=row.get('speaker_revision'),verified_profile_id=row.get('profile_id'),
            display_profile_id=row.get('display_profile_id'),naming_state=row.get('naming_state'),identity_assignment=row.get('identity_assignment'))
        for sid in ids:
            require(sid in summary['spans'],'Final Controller span missing from viewport ledger')
            state=summary['spans'][sid];ref=state['latest']['row_ref'];digest=fingerprint(ref)
            if digest not in cache:cache[digest]=read_row(log_path,ref)
            seen=cache[digest]
            require(not seen.get('removed_from_controller',False) and all(fingerprint(seen.get(k))==fingerprint(v) for k,v in fields.items()),
                'Latest viewport metadata differs from final Controller row')
            invisible+=int(state['first_visible'] is None)
            if row.get('final'):
                final_spans.add(sid);without_final+=int(state['first_final_visible'] is None)
    return dict(final_rows=len(rows),final_snapshot_spans=len(spans),finalized_spans=len(final_spans),
        final_snapshot_spans_never_observed_visible=invisible,finalized_spans_without_final_visibility=without_final,
        historical_spans=len(summary['spans']),final_span_ids_sha256=fingerprint(sorted(spans)),
        caption_strings_independently_scored=False,names_independently_scored=False,
        scope='Final Controller/viewport metadata consistency; offscreen and never-visible spans remain denominators')


def review_observations(folder, *, payload, application_owner, checkpoint=None):
    """Internal evidence join, not proof of a qualified production plan or slot."""
    folder=Path(folder).absolute();root=folder.parent.resolve(strict=True);folder=assert_plain_path(folder,root)
    evidence=[]
    def read(relative):
        b,value=record(folder/relative,root);evidence.append(b);return b,value
    _,prepared=read('PREPARED.json');context=prepared_context(payload,prepared)
    result_binding,result=read('RESULT.json');_,observed=read('ENGINE_CLOSURE.json');_,archive=read('ARCHIVE_INTEGRITY.json')
    _,clock=read('SOURCE_CLOCK.json');_,snapshot=read('FINAL_SNAPSHOT.json')
    session=assert_plain_path(observed['session'],folder/'data/sessions')
    require(session.parent==folder/'data/sessions','Engine session is outside this cell data root')
    assert_plain_path(archive['epoch']['path'],folder/'data/conversations')
    # Existing closure validator rechecks terminal files and archive counters.
    closure=validate_complete(observed,archive)
    require(fingerprint(result['closure'])==fingerprint(closure),'Stored cell closure differs from independent reconstruction')
    require(result['status']=='CELL_CLOSED_REQUIRES_REVIEW' and result['errors']==[] and result['callback_errors']==[]
        and result['controller_closed'] is True and result['controller_worker_exited'] is True,'Application cell has late errors')
    resource_binding,resource=read('resources/RESULT.json')
    require(result['resources']==resource_binding,'Application resource receipt was swapped')
    resource_review=review_resources(resource_binding,expected_owner=application_owner,require_all_phases=True)
    _,viewport_result=read('viewport/RESULT.json')
    summary_path=assert_plain_path(folder/'viewport/SUMMARY.json',root);summary_binding=bind(summary_path)
    require(viewport_result['ledger']==summary_binding,'Viewport result/ledger binding differs')
    viewport_review=review_viewport(summary_binding,checkpoint=checkpoint);summary=load(summary_path)
    intervals=validate_clock_and_phases(payload,prepared,observed,clock,snapshot,resource,viewport_review,viewport_result)
    counts=final_span_census(snapshot,summary,Path(viewport_review['evidence']['path']),checkpoint=checkpoint)
    for b in evidence+[summary_binding,resource_review['evidence'],viewport_review['evidence']]:verify(b)
    return dict(status='PASS_APPLICATION_OBSERVATION_JOINS_ONLY',cell_result=result_binding,evidence=evidence,
        context=context,closure=closure,resource_review=resource_review,viewport_review=viewport_review,phase_intervals=intervals,
        final_span_census=counts,source_and_viewport_origin_joined=True,recorded_source_closure_verified=True,
        native_publication_content_reviewed=False,accuracy_qualified=False,source_to_widget_latency_qualified=False,
        controlled_resources_qualified=False,physical_scanout_measured=False,deployment_tier='UNKNOWN',
        actual_continuity_test=False,stop_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False)


def review_collected_cell(folder, *, checkpoint=None, **expected):
    """Compose both independent checks; expectations must come from reviewed plan."""
    transport=review_transport(folder,**expected)
    observations=review_observations(Path(folder)/'application',payload=expected['payload'],application_owner=transport['application'],checkpoint=checkpoint)
    return dict(status='PASS_APPLICATION_CELL_EVIDENCE_JOINS_ONLY',transport=transport,observations=observations,
        complete_panel_reviewed=False,integrated_N4_cells=0,N4_accepted=False)
