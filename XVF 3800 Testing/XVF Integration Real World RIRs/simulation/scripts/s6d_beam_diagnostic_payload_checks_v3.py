"""Focused future80 metadata checks; see README_S6D_BEAM_DIAGNOSTIC_V3.md."""
import argparse
import ast
from copy import deepcopy
from datetime import datetime,timezone
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts and not out.exists();out.mkdir(parents=True);sys.path.insert(0,str(a.source_root))
    N=module(a.source_root/'s6d_beam_native_run_diagnostic_v3.py','s6d_beam_native_run_diagnostic_v3');Q=module(a.source_root/'s6d_beam_queue_prepare_diagnostic_v3.py','diagnostic_payload_queue');R=Q.P.R
    parent=R/'application/beam_diagnostic_closure_v2/source';rows=[]
    def check(name,fn):
        try:fn();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def eq(a,b):assert a==b,(a,b)
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected fail-closed rejection')
    def node(path,name):return ast.dump(next(x for x in ast.parse(path.read_text()).body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name==name),include_attributes=False)
    def exact_wrapper():
        before=(parent/'s6d_beam_native_run_diagnostic_v2.py').read_text();after=(a.source_root/'s6d_beam_native_run_diagnostic_v3.py').read_text()
        expected=before.replace('Diagnostic-only dual-journal runner; see README_S6D_BEAM_DIAGNOSTIC_V2.md.','Diagnostic-only dual-journal runner with protocolV3; see README_S6D_BEAM_DIAGNOSTIC_V3.md.').replace('874d55b0449f5cb53d9b6bf476d7a8cf97d1022e1cffd5ef844f71af5f8c5084','bdb9896cc3cdfefe85ea1602b904373ceb24de0de52965b0a66b3c56ecd1fe12')
        eq(expected,after)
        for name in ['run','validate_multistream','validate_diagnostic_source','diagnostic_pair_proof']:
            eq(node(parent/'s6d_beam_native_run_diagnostic_v2.py',name),node(a.source_root/'s6d_beam_native_run_diagnostic_v3.py',name))
        eq(node(parent/'s6d_beam_queue_prepare_diagnostic_v2.py','diagnostic_expected_fields'),node(a.source_root/'s6d_beam_queue_prepare_diagnostic_v3.py','diagnostic_expected_fields'))
    check('wrapper_only_protocol_doc_change_all_dual_spool_runtime_and_predicates_unchanged',exact_wrapper)
    acceptance=N.bind(R/'runner/source_epoch_payload_v5/ROOT_SOURCE_ACCEPTANCE.json');accepted=N.verified(acceptance);wf=N.verified(accepted['wrapper_source_freeze']);exception=accepted['exception'];e=N.verified(exception)
    manifest=dict(payload_cap_exception=exception,payload_source_acceptance=acceptance,support=dict(runner=wf['runner'],protocol=wf['wrapper']),limits=dict(max_new_payload_gib=80))
    payload=Q.payload_sources(manifest)
    check('actual_exact_accepted_V5_V3_80_source_graph',lambda:eq(payload['guards'][:4],[exception,e['contract'],e['forecast'],e['prior_runner']]))
    for key in ['payload_cap_exception','payload_source_acceptance']:
        def missing(key=key):m=deepcopy(manifest);del m[key];reject(lambda:Q.payload_sources(m))
        check('missing_manifest_'+key,missing)
    for key in ['runner','protocol']:
        def foreign(key=key):m=deepcopy(manifest);m['support'][key]=dict(m['support'][key],sha256='0'*64);reject(lambda:Q.payload_sources(m))
        check('foreign_manifest_'+key,foreign)
    def oldcap():m=deepcopy(manifest);m['limits']['max_new_payload_gib']=40;reject(lambda:Q.payload_sources(m))
    check('manifest_must_declare_exact80',oldcap)
    runner=Path(payload['runner']['path']);tree=ast.parse(runner.read_text());names={'finite_number','timestamp','validate_payload_ceiling'};nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert len(nodes)==3
    def binding(path,sha=None):
        b=N.bind(path)
        if sha is not None:eq(b['sha256'],sha)
        return b
    ns=dict(Path=Path,math=math,datetime=datetime,timezone=timezone,CAMPAIGN_STARTED_UTC='2026-09-13T19:53:57+00:00',CLOSEOUT_MIN_SECONDS=2700,binding=binding,load=lambda path:json.loads(Path(path).read_text(encoding='utf-8-sig')))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(runner),'exec'),ns);validate=ns['validate_payload_ceiling'];now=ns['timestamp'](e['utc'])+1
    forecast=N.verified(e['forecast']);queue=dict(run_id='20260913T195357Z',owner_thread_id=e['owner_thread_id'],owner_session_id=e['owner_thread_id'],fixture_only=False,payload_policy=dict(max_new_payload_bytes=80*2**30,cap_exception=exception,new_payload_roots=forecast['census_roots']),campaign=dict(started_utc='2026-09-13T19:53:57Z',deadline_utc=e['hard_deadline_utc'],closeout_reserve_s=2700),disk_policy=[dict(path='C:/',minimum_free_bytes=50*2**30),dict(path='G:/',minimum_free_bytes=75*2**30)],jobs=[dict(kind='offline',source_bindings=deepcopy(payload['guards'])) for _ in range(2)])
    proposal=dict(payload_cap_exception=exception,approved_job_sha256=[])
    check('actual_V5_pure_gate_accepts_both_in_memory_guarded_jobs',lambda:validate(queue,proposal,now))
    for i,label in enumerate(['exception','contract','forecast','priorV4']):
        def missing_guard(i=i):q=deepcopy(queue);q['jobs'][1]['source_bindings'].pop(i);reject(lambda:validate(q,proposal,now))
        check('missing_second_job_'+label+'_guard_rejected',missing_guard)
    def changed_scope(kind):
        q=deepcopy(queue);ap=deepcopy(proposal)
        if kind=='approval':ap.pop('payload_cap_exception')
        elif kind=='roots':q['payload_policy']['new_payload_roots'].pop()
        elif kind=='hardware':q['jobs'][1]['kind']='hardware'
        elif kind=='cap':q['payload_policy']['max_new_payload_bytes']=81*2**30
        reject(lambda:validate(q,ap,now))
    for kind in ['approval','roots','hardware','cap']:check('changed_'+kind+'_rejected_by_existing_V5_gate',lambda kind=kind:changed_scope(kind))
    def prepare_ast():
        text=(a.source_root/'s6d_beam_queue_prepare_diagnostic_v3.py').read_text()
        assert "*payload['guards']" in text and "proposal['payload_cap_exception']=payload['exception']" in text and "max_new_payload_bytes=80*2**30,cap_exception=payload['exception']" in text
        assert 'approved_job_sha256=[]' in text
        # Nonbudget literal runtime controls remain exact inherited values.
        for fragment in ['timeout_s=960,stall_after_s=300,heartbeat_stale_s=45,stop_grace_s=75','allow_owned_termination=True','diagnostic_dual_journal_evidence_validated','affinity_verified\':[12,13,14,15]']:
            assert fragment in text
    check('preparation_inserts_each_guard_preserves_empty_approval_and_runtime_limits',prepare_ast)
    result=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',fixture_only=True,tests=rows,passed=sum(x['status']=='PASS' for x in rows),total=len(rows),sources=[N.bind(a.source_root/n) for n in ['s6d_beam_native_run_diagnostic_v3.py','s6d_beam_queue_prepare_diagnostic_v3.py','s6d_beam_diagnostic_payload_checks_v3.py','README_S6D_BEAM_DIAGNOSTIC_V3.md']],parent_independent_review=N.bind(Path('G:/Just_Peachy_S6D/20260913T195357Z/review_fixtures/beam_diagnostic_v2_independent/INDEPENDENT_REVIEW.json')),payload_sources=payload,pure_runner_functions=sorted(names),in_memory_fixture_time=now,production_manifests_or_queues_created=0,approval_files_created=0,actual_process_calls=0,models=0,audio=0,hardware=0,scope='Affected source/metadata checks only. Pure V5 functions extracted, no runner import or original dual-spool suite rerun. No in-memory fake authority written as production data.')
    N.save(out/'RECEIPT.json',result);print(json.dumps(result,indent=2));return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
