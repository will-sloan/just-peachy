"""Delivery-cell GUI/archive/resource joins. README_APPLICATION_CELL_REVIEW_V3.md."""
from pathlib import Path

from application_closure_v2 import validate_complete
from common import bind, fingerprint, load, verify
from paced_child_admission import assert_plain_path
from paced_panel_plan_v3 import APPLICATION_POLICY
from review_application_transport_v3 import record
from review_application_observations import prepared_context, validate_clock_and_phases, final_span_census
from review_resource_evidence import review as review_resources
from review_scoring_bank import require
from review_viewport_evidence import review as review_viewport


def review_observations(folder,*,payload,application_owner,checkpoint=None):
    """Independent closed observations; caller still must admit transport/plan."""
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
    closure=validate_complete(observed,archive)
    require(fingerprint(result['closure'])==fingerprint(closure),'Stored cell closure differs from independent reconstruction')
    require(result['status']==APPLICATION_POLICY['success_status'] and result['errors']==[] and result['callback_errors']==[]
        and result['controller_closed'] is True and result['controller_worker_exited'] is True,'Application cell has late errors')
    require(all(r['application_variant']==APPLICATION_POLICY['variant'] and r['delivery_policy']==APPLICATION_POLICY['delivery']
        for r in (prepared,result)),'Observation reader requires the delivery application policy')
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
    return dict(status='PASS_V2_DELIVERY_APPLICATION_OBSERVATION_JOINS_ONLY',cell_result=result_binding,evidence=evidence,
        context=context,closure=closure,resource_review=resource_review,viewport_review=viewport_review,phase_intervals=intervals,
        final_span_census=counts,source_and_viewport_origin_joined=True,recorded_source_closure_verified=True,
        delivery_trace_requires_independent_transport_review=True,native_publication_content_reviewed=False,
        accuracy_qualified=False,source_to_widget_latency_qualified=False,controlled_resources_qualified=False,
        physical_scanout_measured=False,deployment_tier='UNKNOWN',actual_continuity_test=False,
        stop_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False)
