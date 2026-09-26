"""Independent stopped restart transport review. README_RESTART_REVIEW.md."""
from pathlib import Path

from common import bind, fingerprint, verify
from metric_process import exact_process
from paced_child_admission import assert_plain_path, digest, validate_permit, validate_lease
from paced_slot import competitors, key, MAX_CELL_BYTES
from restart_application_child import closed_result, control
from restart_application_runner import check_child_result, COLLECTED, MAXIMUM_CHILD_SECONDS
from restart_application_plan import APPLICATION_POLICY
from restart_pair_evidence import review_pair
from review_application_transport import MAX_JSON, finite, record, validate_lifetime
from review_scoring_bank import require


def review_cell(folder, *, payload, plan_sha256, coordinator, code, parent_code,
                executable, coordinator_argv, state, checkpoint=None):
    """Caller reconstructs the qualified plan/manifests; this API cannot admit a run."""
    folder=Path(folder).absolute();root=folder.parent.resolve(strict=True)
    folder=assert_plain_path(folder,root);planned=control(payload);key(coordinator)
    require(exact_process(coordinator) is None,'Review requires a stopped panel coordinator')
    require(digest(plan_sha256),'Reconstructed plan digest missing')
    require(type(code) is list and 0<len(code)<=128 and len({b['path'] for b in code})==len(code), 'Child code census differs')
    require(type(parent_code) is list and len(parent_code)>=len(code)
        and len({b['path'] for b in parent_code})==len(parent_code)
        and all(b in parent_code for b in code),'Parent and child manifests differ')
    for b in [executable,*parent_code]:verify(b)
    scripts=[b for b in code if Path(b['path']).name=='restart_application_child.py']
    require(len(scripts)==1,'Exactly one bound fixed restart child required');script=scripts[0]
    bindings=[]
    def read(relative):
        if checkpoint:checkpoint()
        b,value=record(folder/relative,root);bindings.append(b);return b,value
    input_binding,actual_input=read('transport/INPUT.json')
    require(fingerprint(actual_input)==fingerprint(payload),'Input differs from reconstructed restart cell')
    _,permit=read('transport/PERMIT.json')
    validate_permit(permit,nonce=permit['nonce'],application=permit['application'],parent=coordinator,desktop=permit['desktop'])
    require(permit['plan_sha256']==plan_sha256 and permit['code']==code and permit['input']==input_binding,
        'Permit plan, child code or input differs')
    require(Path(permit['state']).resolve()==Path(state).resolve() and Path(permit['output']).resolve()==folder/'application',
        'Permit state or application output differs')
    require(permit['coordinator_argv_sha256']==fingerprint(coordinator_argv),'Coordinator command differs')
    argv=[executable['path'],'-B',script['path'],'--permit',str(folder/'transport/PERMIT.json'),'--nonce',permit['nonce']]
    require(permit['application_argv_sha256']==fingerprint(argv),'Fixed child command differs')
    lifetime_binding,lifetime=read('transport/LIFETIME.json')
    process_review=validate_lifetime(lifetime,owner=permit['application'],executable=executable,script=script,
        argv_sha256=fingerprint(argv),desktop=permit['desktop'],cpu=4)
    _,lease=read('transport/LEASE.json')
    validate_lease(lease,permit,fingerprint(permit),now_monotonic=lease['issued_monotonic'],previous_sequence=0)
    require(process_review['suspended_at']<=lease['issued_monotonic']<=process_review['closed_at'],'Final lease outside lifetime')
    cancel=assert_plain_path(folder/'transport/CANCEL',root)
    require(cancel.is_file() and cancel.stat().st_size==0,'Parent cleanup cancellation marker missing');bindings.append(bind(cancel))
    child_binding,child=read('transport/CHILD_RESULT.json')
    check_child_result(child,owner=permit['application'],input_binding=input_binding,payload=payload,application=folder/'application')
    cell_binding,cell=read('application/RESULT.json');closed_result(cell,folder/'application')
    _,prepared=read('application/PREPARED.json')
    require(prepared['status']=='PREPARED_NO_SOURCE_OR_MODELS_STARTED' and prepared['desktop']==permit['desktop']
        and prepared['contract']==payload['contract'] and prepared['job']==payload['job']
        and prepared['runtimes']==payload['runtimes'] and prepared['gallery_preparation']==payload['gallery_preparation']
        and prepared['logical_client']==[480,800] and prepared['active_height_px']==184
        and prepared['no_auto_start'] is True and prepared['integrated_N4_cells']==0,'Prepared application identity or geometry differs')
    collected_binding,collected=read('COLLECTED.json')
    require(collected['status']==COLLECTED and collected['cell_id']==payload['cell_id'] and collected['input']==input_binding
        and collected['child_result']==child_binding and collected['lifetime']==lifetime_binding
        and collected['lifetime_review']==process_review and collected['restart_control']==planned
        and collected['application_policy']==APPLICATION_POLICY
        and collected['parent_code_sha256']==fingerprint(parent_code) and collected['child_code_sha256']==fingerprint(code)
        and collected['actual_restart_qualified'] is False and collected['independent_complete_transport_reviewed'] is False
        and type(collected['integrated_N4_cells']) is int and collected['integrated_N4_cells']==0
        and collected['N4_accepted'] is False,'Collected receipt joins or scope differ')
    monitoring=collected['monitoring']
    require(type(monitoring['renewals']) is int and monitoring['renewals']>0 and monitoring['renewals']==lease['sequence']
        and finite(monitoring['elapsed_seconds']) and 0<monitoring['elapsed_seconds']<=MAXIMUM_CHILD_SECONDS,
        'Parent monitoring and final lease census differ')
    slot=collected['slot_admission']
    require(slot['coordinator']==coordinator and slot['supervised_run']==permit['supervised_run']
        and slot['cpu_affinity']==[4] and slot['gpu'] is False and slot['source_execution_authorized'] is False
        and type(slot['reservation_bytes']) is int and 0<slot['reservation_bytes']<=MAX_CELL_BYTES,'Slot admission differs')
    census=slot['census'];allowed=[coordinator,permit['supervisor']]
    require(not competitors(census,allowed) and len(census['rows'])==2
        and {key(r) for r in census['rows']}=={key(r) for r in allowed},'Initial slot census is uncertain or incomplete')
    rows={key(r):r for r in census['rows']}
    require(all(r['affinity']==[14] for r in rows.values())
        and rows[key(coordinator)]['parent_pid']==permit['supervisor']['pid']
        and rows[key(coordinator)]['argv_sha256']==permit['coordinator_argv_sha256']
        and Path(rows[key(coordinator)]['executable']).resolve()==Path(executable['path']).resolve(),'Coordinator admission observation differs')
    inventory=slot['inventory']
    require(inventory['errors']==[] and type(inventory['total_logical_bytes']) is int and inventory['total_logical_bytes']>=0
        and inventory['total_logical_bytes']+6*1024**3+slot['reservation_bytes']<=50*1024**3,'Recorded shared allowance exceeded')
    _,parent=read('PARENT_CLOSURE.json')
    require(parent['error'] is None and parent['cleanup_error'] is None and parent['lifecycle']==lifetime
        and parent['actual_restart_qualified'] is False and parent['integrated_N4_cells']==0
        and parent['N4_accepted'] is False,'Parent closure failed or lifetime changed')
    require(parent['slot_release']==dict(status='APPLICATION_SLOT_RELEASED',coordinator=coordinator,application=permit['application'],
        child_cleanup_performed_by_guard=False,source_execution_authorized=False),'Parent slot was not released for this application')
    pair_binding,saved_pair=read('PAIR_EVIDENCE_REVIEW.json')
    require(collected['pair_evidence_review']==pair_binding,'Collected pair evidence binding differs')
    pair=review_pair(folder/'application',payload=payload,application_owner=permit['application'],checkpoint=checkpoint)
    require(pair['status']=='PASS_COMPLETE_RESTART_PAIR_EVIDENCE_JOINS_ONLY' and pair['cell_id']==payload['cell_id']
        and pair['application_owner']==permit['application'] and pair['cell_result']==cell_binding and pair['control']==planned
        and pair['actual_restart_qualified'] is False and pair['N4_accepted'] is False and pair['integrated_N4_cells']==0
        and fingerprint(pair)==fingerprint(saved_pair),'Independently reread pair differs from collection')
    all_bindings={}
    for b in bindings+pair['evidence']:
        require(b['path'] not in all_bindings or all_bindings[b['path']]==b,'Evidence changed across transport and pair review')
        all_bindings[b['path']]=b
    for b in list(all_bindings.values())+[executable,*parent_code]:verify(b)
    require(exact_process(coordinator) is None and exact_process(permit['application']) is None,'Reviewed owner became active')
    return dict(status='PASS_RESTART_TRANSPORT_AND_PAIR_JOINS_ONLY',cell_id=payload['cell_id'],collected=collected_binding,
        evidence=list(all_bindings.values()),application=permit['application'],coordinator=coordinator,supervisor=permit['supervisor'],
        supervised_run=permit['supervised_run'],process_review=process_review,final_lease_sequence=lease['sequence'],
        pair_evidence=pair_binding,pair_review=pair,full_lease_history_available=False,complete_process_history_available=False,
        viewport_rows_reviewed=False,resource_samples_reviewed=False,actual_restart_qualified=False,
        source_to_widget_latency_qualified=False,controlled_resources_qualified=False,integrated_N4_cells=0,N4_accepted=False,
        limitations=['Caller must reconstruct the qualified plan and exact complete run population.',
            'Recorded historical admission is joined, not rerun; only the terminal lease is retained.',
            'Job accounting includes unsampled assignments; complete process history remains unavailable.',
            'Recorded shared-object joins do not add an independent object identity instrument.',
            'Viewport rows, naming, resource samples and timing still require interpretation.'])
