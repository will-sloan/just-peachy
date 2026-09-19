"""Focused file-only N6g C12 admission checks; README_S6D_C12_ROOT_ADMIT_CHECKS_V2.md."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

CANONICAL_SIM=Path(r'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation')

def main(source_root,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    source=Path(source_root).resolve()/'s6d_C12_root_admit_v2.py'
    spec=importlib.util.spec_from_file_location('C12_checks_target',source);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
    oldR=M.R;M.SIM=CANONICAL_SIM;M.R=CANONICAL_SIM/'reports/S6D/20260913T195357Z'
    M.PINS={k:(M.R/p.relative_to(oldR),sha) for k,(p,sha) in M.PINS.items()}
    M.Q=M.R/'runner/beam_C_queue_proposed_v3';M.H2_SCRIPT=CANONICAL_SIM.parents[2]/'Software Validation from Datasets/Evaluation Tool/scripts/maintain_h2_storage.py'
    source_before=M.bound(source);readme_before=M.bound(source.with_name('README_S6D_C12_ROOT_ADMIT_V2.md'))
    tests=[]
    def run(name,fn):
        try:fn();tests.append(dict(name=name,status='PASS'))
        except BaseException as e:tests.append(dict(name=name,status='FAIL',error=repr(e)))
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Adverse input accepted')
    # This single bounded intake reads the pinned small metadata/source graph only.
    C=M.input_context()
    oldq=C['old_queue'];oldap=M.read(C['parent']['bindings']['approval_proposal']['path']);oldm=M.read(C['parent']['bindings']['manifest']['path'])
    newm=C['manifest'];fr=C['freeze'];extras=C['queue']['source_adoption_guards']
    def remap(oq=None,oa=None,om=None,nm=None,pairs=None,extra=None):
        return M.transform(copy.deepcopy(oq or oldq),copy.deepcopy(oa or oldap),copy.deepcopy(om or oldm),copy.deepcopy(nm or newm),fr['manifest'],fr['runner'],copy.deepcopy(fr['source_files'] if pairs is None else pairs),copy.deepcopy(extras if extra is None else extra))
    def exact_transform():
        q,ap=remap();assert len(q['jobs'])==12 and not ap['approved_job_sha256'];assert q['payload_policy']==oldq['payload_policy'];assert q['campaign']==oldq['campaign'];assert q['disk_policy']==oldq['disk_policy'];assert q['runner_sha256']==oldq['runner_sha256']
        assert q['jobs']==C['queue']['jobs'] and ap==C['approval']
        for a,b in zip(q['jobs'],oldq['jobs']):
            changed={'argv','cwd','heartbeat_path','completion_path','stop_request_path','source_bindings','expected_artifacts'}
            assert {k:v for k,v in a.items() if k not in changed}=={k:v for k,v in b.items() if k not in changed}
            assert a['argv'][1]==fr['runner']['path'];assert all(x in a['source_bindings'] for x in extras)
    run('exact12_remap_original_limits_and_each_required_guard',exact_transform)
    def predicates():
        for old,new,job in zip(oldq['jobs'],C['queue']['jobs'],newm['jobs']):
            assert len(old['expected_artifacts'])==len(new['expected_artifacts'])==3
            for a,b in zip(old['expected_artifacts'],new['expected_artifacts']):
                assert a['format']==b['format'] and a['min_bytes']==b['min_bytes']
                for key,v in a['expected_fields'].items():
                    n=b['expected_fields'][key]
                    if key=='manifest.sha256':assert n==fr['manifest']['sha256']
                    elif key=='helper.sha256':assert n==fr['runner']['sha256']
                    elif key=='completion_audit.path':assert n==str(Path(job['output'])/'FULL_MULTISTREAM_AUDIT.json')
                    else:assert n==v,(key,v,n)
            assert len({x['path'] for x in new['source_bindings']})==len(new['source_bindings'])
    run('all36_artifacts_preserve_full_three_journal_and_semantic_predicates',predicates)
    def wrong_science():
        n=copy.deepcopy(newm);n['jobs'][-1]['mode']='auto';reject(lambda:remap(nm=n))
    run('changed_last_scientific_cell_rejected',wrong_science)
    def wrong_population():
        n=copy.deepcopy(newm);n['jobs'].pop();reject(lambda:remap(nm=n))
    run('eleven_cell_population_rejected',wrong_population)
    def wrong_argv():
        q=copy.deepcopy(oldq);q['jobs'][0]['argv'].insert(1,'-B');a=copy.deepcopy(oldap);a['proposed_job_sha256']=[M.digest(j) for j in q['jobs']];reject(lambda:remap(oq=q,oa=a))
    run('incompatible_script_position_rejected',wrong_argv)
    def approved_parent():
        a=copy.deepcopy(oldap);a['approved_job_sha256']=[a['proposed_job_sha256'][0]];reject(lambda:remap(oa=a))
    run('already_approved_parent_proposal_rejected',approved_parent)
    run('missing_corrected_application_guard_rejected',lambda:reject(lambda:remap(pairs=fr['source_files'][:-1])))
    def conflicted_extra():
        b=copy.deepcopy(extras[-1]);b['sha256']='0'*64;reject(lambda:remap(extra=extras+[b]))
    run('conflicting_required_source_guard_rejected',conflicted_extra)
    def wrong_evidence():
        a=copy.deepcopy(oldm);b=copy.deepcopy(newm);a['support']['evidence']['sha256']=b['support']['evidence']['sha256']='0'*64;reject(lambda:remap(om=a,nm=b))
    run('matching_but_non_bb1_support_rejected',wrong_evidence)
    def widened_cap():
        q=copy.deepcopy(oldq);q['payload_policy']['max_new_payload_bytes']=80*2**30;reject(lambda:remap(oq=q))
    run('unrelated80GiB_migration_rejected',widened_cap)
    record=C['values']['failure_closure'];checkpoint=M.verify(record['checkpoint']);closure=M.verify(record['supervisor_closure']);lock=M.verify(record['closed_lock'])
    known=M.closure_decision(record,checkpoint,closure,lock)
    run('actual_saved_failed_zero_credit_owner_closure',lambda: M.require(len(known)==2,'Two original instances'))
    for key in ('keep_awake','payload_census_closure'):
        def bad_closure(k=key):
            c=copy.deepcopy(closure);c[k]['restored' if k=='keep_awake' else 'closed']=False;reject(lambda:M.closure_decision(record,checkpoint,c,lock))
        run('unclosed_'+key+'_rejected',bad_closure)
    def historical_finish():
        c=copy.deepcopy(checkpoint);c['status']='FINISH';reject(lambda:M.closure_decision(record,c,closure,lock))
    run('historical_failure_not_relabelled_FINISH',historical_finish)
    def historical_credit():
        r=copy.deepcopy(record);r['accepted']=1;reject(lambda:M.closure_decision(r,checkpoint,closure,lock))
    run('failed_old_attempt_credit_rejected',historical_credit)
    current={'pid':900001,'creation_time':123456.0}
    own=dict(pid=current['pid'],creation_time=current['creation_time'],name='python.exe',argv=['python.exe',str(source)])
    def inventory(*rows,complete=True):return dict(complete=complete,errors=[] if complete else ['enumeration failure'],rows=[own,*rows])
    def proc(name,args,pid=900002,creation=123450.):return dict(pid=pid,creation_time=creation,name=name,argv=args)
    run('complete_idle_fixture_inventory_accepts',lambda:M.allocation_decision(inventory(),current,known))
    run('exact_H2_script_only_retained',lambda:M.allocation_decision(inventory(proc('python.exe',['python.exe',str(M.H2_SCRIPT),'--unchanged'])),current,known))
    run('physical_control_dotnet_overlap_rejected',lambda:reject(lambda:M.allocation_decision(inventory(proc('dotnet.exe',['dotnet.exe','S6DQueuedTelemetry.dll'])),current,known)))
    run('other_NN_supervisor_python_rejected',lambda:reject(lambda:M.allocation_decision(inventory(proc('python.exe',['python.exe','another.py'])),current,known)))
    run('incomplete_inventory_rejected',lambda:reject(lambda:M.allocation_decision(inventory(complete=False),current,known)))
    run('unreadable_interpreter_rejected',lambda:reject(lambda:M.allocation_decision(inventory(proc('powershell.exe',None)),current,known)))
    run('same_old_PID_and_creation_rejected',lambda:reject(lambda:M.allocation_decision(inventory(proc('native.exe',['native.exe'],known[0]['pid'],known[0]['creation_time'])),current,known)))
    run('provably_reused_old_PID_allowed',lambda:M.allocation_decision(inventory(proc('benign.exe',['benign.exe'],known[0]['pid'],known[0]['creation_time']+10)),current,known))
    run('unknown_reused_old_PID_creation_rejected',lambda:reject(lambda:M.allocation_decision(inventory(proc('benign.exe',['benign.exe'],known[0]['pid'],float('nan'))),current,known)))
    def real_validator():
        s=importlib.util.spec_from_file_location('C12_real_V4_validator',C['runner']['path']);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        q=copy.deepcopy(C['queue']);a=copy.deepcopy(C['approval']);qh=M.digest(q);a['queue_sha256']=qh;a['approved_job_sha256']=[M.digest(j) for j in q['jobs']]
        assert m.validate_queue(q,a,qh) is True
    run('actual_V4_validator_accepts12_in_memory_rows_no_authority_written',real_validator)
    # Transaction probes use only a G fixture directory, fake runtime providers and
    # fake save() capture. Actual approval/admission is NEVER written or launched.
    def prepare_only():
        folder=output/'prepare_only'
        with patch.object(M,'Q',folder),patch.object(M,'input_context',return_value=copy.deepcopy(C)),patch.object(M,'fresh_outputs'),patch.object(M,'runtime_snapshot',side_effect=AssertionError('Prepare queried processes')),redirect_stdout(io.StringIO()):
            M.prepare()
        assert sorted(p.name for p in folder.iterdir())==['APPROVAL_PROPOSAL.json','PREPARATION.json','QUEUE.json']
        assert M.read(folder/'APPROVAL_PROPOSAL.json')['approved_job_sha256']==[]
        assert M.read(folder/'PREPARATION.json')['actual_approval_created'] is False
    run('actual_prepare_orchestration_writes_only_unapproved_metadata',prepare_only)
    def transaction(failure=None):
        folder=output/('transaction_'+(failure or 'success'));folder.mkdir()
        c=copy.deepcopy(C);writes=[]
        def capture(p,v):
            data=M.encoded(v);writes.append((Path(p).name,copy.deepcopy(v)));return dict(path=str(Path(p).resolve()),bytes=len(data),sha256=M.hashlib.sha256(data).hexdigest())
        with patch.object(M,'Q',folder),patch.object(M,'input_context',return_value=c),patch.object(M,'fresh_outputs'),redirect_stdout(io.StringIO()):
            qb=M.save(folder/'QUEUE.json',c['queue']);c['approval']['queue_sha256']=qb['sha256'];ab=M.save(folder/'APPROVAL_PROPOSAL.json',c['approval'])
            prep=copy.deepcopy(M.preparation_record(c,qb,ab))
            if failure=='scope':prep['scope']['selectors_enabled']=True
            pb=M.save(folder/'PREPARATION.json',prep)
            rv=dict(status='ROOT_ACCEPTED_EXACT_N6G_C12_QUEUE_FOR_ADMISSION',owner_thread_id=M.THREAD,run_id='20260913T195357Z',preparation=pb,queue=qb,source_adoption=c['refs']['source_adoption'],prior_runtime_closure=c['refs']['failure_closure'],allow_admission=True,physical_supervisor_overlap=False)
            rb=M.save(folder/'SYNTHETIC_REVIEW_NEVER_EXECUTE.json',rv)
            # Restore expected unfilled queue_hash from the real pure context.
            c['approval']['queue_sha256']=None
            fake=SimpleNamespace(validate_queue=lambda *args:M.require(failure!='runner','Synthetic final V4 rejection'))
            loader=SimpleNamespace(exec_module=lambda _:None)
            snapshot=inventory(proc('python.exe',['python.exe','foreign.py'])) if failure=='allocation' else inventory()
            original_bound=M.bound
            def observed(p):
                b=original_bound(p)
                if failure=='guard' and b['path']==c['queue']['jobs'][-1]['source_bindings'][0]['path']:b['sha256']='0'*64
                return b
            with patch.object(M,'runtime_snapshot',return_value=(snapshot,current)),patch.object(M.shutil,'disk_usage',return_value=SimpleNamespace(free=100*2**30)),patch.object(M.importlib.util,'spec_from_file_location',return_value=SimpleNamespace(loader=loader)),patch.object(M.importlib.util,'module_from_spec',return_value=fake),patch.object(M,'save',side_effect=capture),patch.object(M,'bound',side_effect=observed):
                if failure:reject(lambda:M.admit(rb['path'],rb['sha256']))
                else:M.admit(rb['path'],rb['sha256'])
            assert not (folder/'APPROVAL.json').exists() and not (folder/'ROOT_ADMISSION.json').exists()
            if failure:assert writes==[],writes
            else:
                assert [p for p,v in writes]==['ADMISSION_PREFLIGHT.json','ROOT_ADMISSION.json','APPROVAL.json']
                assert writes[1][1]['approval']['sha256']==M.hashlib.sha256(M.encoded(writes[2][1])).hexdigest()
                assert writes[2][1]['approved_job_sha256']==[M.digest(j) for j in C['queue']['jobs']]
    run('final_validation_failure_creates_no_authority_or_preflight',lambda:transaction('runner'))
    run('changed_descriptive_scope_rejected_before_authority',lambda:transaction('scope'))
    run('fresh_allocation_failure_creates_no_authority',lambda:transaction('allocation'))
    run('late_source_guard_failure_creates_no_authority',lambda:transaction('guard'))
    run('success_publishes_approval_last_with_exact_binding_in_memory',lambda:transaction())
    assert M.bound(source)==source_before and M.bound(source.with_name('README_S6D_C12_ROOT_ADMIT_V2.md'))==readme_before
    result=dict(status='PASS' if all(x['status']=='PASS' for x in tests) else 'FAIL',passed=sum(x['status']=='PASS' for x in tests),total=len(tests),tests=tests,source=source_before,readme=readme_before,fixture_source=M.bound(__file__),fixture_readme=M.bound(Path(__file__).with_name('README_S6D_C12_ROOT_ADMIT_CHECKS_V2.md')),inputs=C['refs'],per_job_guard_counts=[len(j['source_bindings']) for j in C['queue']['jobs']],actual_model_calls=0,actual_device_calls=0,actual_process_queries=0,production_prepare_calls=0,production_admit_calls=0,actual_approvals_written=0,limits='Source/metadata and synthetic transaction evidence only; no experiment readiness or scientific collection success inferred.')
    M.save(output/'RECEIPT.json',result)
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',required=True);p.add_argument('--output',required=True);a=p.parse_args();raise SystemExit(main(a.source_root,a.output))
