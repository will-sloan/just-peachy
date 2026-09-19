"""Focused composite admission fixtures; README_S6D_NATIVE176_COMPOSITE_V2.md."""
import argparse,ast,importlib.util,json,sys,traceback
from copy import deepcopy
from pathlib import Path

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts and not out.exists();out.mkdir(parents=True);sys.path.insert(0,str(a.source_root))
    N=load(a.source_root/'s6d_native176_scoring_inputs_v2.py','composite_builder_checks');S=load(a.source_root/'s6d_native_correctness_composite_v2.py','composite_scorer_checks');cache=N.Cache();meta=N.metadata(cache);rows=[]
    def check(name,fn):
        try:fn();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected fail-closed rejection')
    c=meta['composite'];old=c['original'];oq=meta['data']['queue'];cp=meta['original_checkpoint'];lock=cache.verified(old['closed_lock']);closure=cache.verified(old['supervisor_closure']);launch=cache.verified(meta['original_launch_ref'])
    def actual_metadata():
        assert len(meta['contexts'])==176 and len(meta['execution_manifests'])==4
        assert len(N.stopped_closed(oq,old['queue'],cp,lock,closure,launch))==173
        assert N.launch_identity(launch)=={k:lock[k] for k in ('pid','creation_time')}
        assert N.selection_for(meta)[171]['execution_job_id'].endswith('_recover1')
    check('actual_pinned_composite_manifest_and_historical_launch_shape',actual_metadata)
    for name,mutation in [
        ('fabricated_old_FINISH',lambda x:x.update(status='FINISH',active=None)),
        ('missing_original_completion',lambda x:x['completed'].pop(next(iter(x['completed'])))),
        ('stopped_old_result_credited',lambda x:x['completed'].update({x['active']['job_id']:deepcopy(next(iter(x['completed'].values())))})),
        ('changed_failure_reason',lambda x:x.update(reason='other'))]:
        def adverse(mutation=mutation):v=deepcopy(cp);mutation(v);reject(lambda:N.stopped_closed(oq,old['queue'],v,lock,closure,launch))
        check(name+'_rejects',adverse)
    for field in ('running','pending','error','stale'):
        def adverse(field=field):
            v=deepcopy(closure);v['payload_census_closure']['snapshot'][field]={'running':True,'pending':True,'error':'failed','stale':False}[field]
            reject(lambda:N.stopped_closed(oq,old['queue'],cp,lock,v,launch))
        check('historical_census_'+field+'_preserved',adverse)
    def launch_forms():
        good=N.launch_identity(launch);assert N.launch_identity(good)==good
        reject(lambda:N.launch_identity(dict(good,creation_utc='2026-01-01T00:00:00Z')))
        reject(lambda:N.launch_identity(dict(pid=1,creation_utc='2026-01-01T00:00:00')))
    check('actual_UTC_numeric_launch_compatibility_conflicts_fail',launch_forms)
    def changed_original_row():
        v=deepcopy(c);v['rows'][0]['saved_checkpoint_record']['exit_code']=1;reject(lambda:N.composite_rows(v,oq,cp,meta['recovery_queue']))
    check('changed_original_saved_record_rejected',changed_original_row)
    def duplicate_mapping():
        v=deepcopy(c);v['rows'][-1]=deepcopy(v['rows'][0]);reject(lambda:N.composite_rows(v,oq,cp,meta['recovery_queue']))
    check('duplicate_or_omitted_scientific_mapping_rejected',duplicate_mapping)
    def recovery_closure():
        q=meta['recovery_queue'];ref=c['recovery_queue'];ids=[j['job_id'] for j in q['jobs']]
        checkpoint=dict(run_id=q['run_id'],queue_sha256=ref['sha256'],status='FINISH',active=None,completed={j:dict(status='DECLARED_ARTIFACTS_VERIFIED',exit_code=0,identity=dict(run_id=q['run_id'],job_id=j,child_run_id='fixture'+str(i),pid=100+i,creation_time=10.+i)) for i,j in enumerate(ids)})
        owned=dict(run_id=q['run_id'],queue_sha256=ref['sha256'],owner_nonce='a'*32,pid=90,creation_time=9.)
        close=dict(run_id=q['run_id'],result=dict(run_id=q['run_id'],action='FINISH',done=5,total=5),owner_lock='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT',hardware_restoration_unresolved=False,keep_awake=dict(requested=True,owned=True,restored=True,status='RESTORED'),payload_census_closure=dict(closed=True,snapshot=dict(running=False,has_complete=True,pending=False,error=None,violation_latched=False)))
        assert len(N.B.validate_closed(q,ref,checkpoint,owned,close,dict(pid=90,creation_time=9.)))==6
        for change in ('partial','blocked','live','wrong_id'):
            changed=deepcopy(checkpoint)
            if change=='partial':changed['completed'].pop(ids[-1])
            elif change=='blocked':changed['status']='REPORT_BLOCKED'
            elif change=='live':changed['active']=dict(job_id=ids[-1])
            else:changed['completed'][ids[-1]]['identity']['job_id']=ids[-1].removesuffix('_recover1')
            reject(lambda:N.B.validate_closed(q,ref,changed,owned,close,dict(pid=90,creation_time=9.)))
    check('fresh5_requires_own_FINISH_exact_execution_IDs_and_all_closed',recovery_closure)
    def approvals():
        approval=cache.verified(old['approval']);N.approval_exact(oq,old['queue'],approval)
        wrong=deepcopy(approval);wrong['approved_job_sha256'].pop();reject(lambda:N.approval_exact(oq,old['queue'],wrong))
        reject(lambda:N.approval_exact(meta['recovery_queue'],c['recovery_queue'],cache.verified(c['recovery_approval_proposal'])))
    check('actual_old_approval_and_held_new_proposal_distinguished',approvals)
    # These documents stay in memory. They represent no actual root/closure receipt.
    def ref(name):return dict(path='IN_MEMORY_FIXTURE_'+name,bytes=1,sha256='f'*64)
    cb=meta['composite_ref'];vb=ref('validation');ab=ref('admission');builder=cache.binding(N.__file__);selection=N.selection_for(meta)
    spec=dict(composite_execution=cb,closed_input_validation=vb,root_build_admission=ab,builder=builder,execution_selection=selection,execution_manifests=meta['execution_manifests'],jobs=[dict(job_id=row['job_id'],manifest=meta['contexts'][row['job_id']]['manifest_ref']) for row in meta['data']['prospective']['rows']],unavailable_jobs=[])
    admission=dict(schema='s6d-native176-scoring-build-admission.v2',status='ROOT_ACCEPTED_NATIVE176_COMPOSITE_CLOSED_INPUT_BUILDER_V2',owner_thread_id=N.B.ROOT_ID,allow_closed_input_construction=True,composite=cb,builder=builder)
    validation=dict(status='ALL176_COMPOSITE_CLOSED_INPUTS_VERIFIED',admission=ab,composite=cb,builder=builder,original_completed=171,recovery_completed=5,owner_exit=dict(status='ALL_RECORDED_INSTANCES_ABSENT'),execution_selection=selection,completion_validations=[dict(job_id=x['scientific_job_id'],execution_job_id=x['execution_job_id'],identity=dict(job_id=x['execution_job_id'])) for x in selection])
    docs={cb['path']:c,vb['path']:validation,ab['path']:admission,old['queue']['path']:oq}
    for context in meta['contexts'].values():docs[context['manifest_ref']['path']]=context['manifest']
    def selected(ss,dd):return S.composite_declarations(ss,reader=lambda b:deepcopy(dd[b['path']]))
    check('exact171_original_plus5_recovery_manifests_select_without_rewrite',lambda:assert_equal(len(selected(spec,docs)),176))
    for kind in ('missing_selection','duplicate_selection','old_failed_selected','foreign_manifest','omitted_item','extra_manifest_job','duplicate_manifest_job','omitted_completion_proof','wrong_execution_proof','root_unapproved'):
        def adverse(kind=kind):
            ss=deepcopy(spec);dd=deepcopy(docs)
            if kind=='missing_selection':ss['execution_selection'].pop();dd[vb['path']]['execution_selection']=ss['execution_selection']
            elif kind=='duplicate_selection':ss['execution_selection'][-1]=deepcopy(ss['execution_selection'][0]);dd[vb['path']]['execution_selection']=ss['execution_selection']
            elif kind=='old_failed_selected':
                row=ss['execution_selection'][171];row['manifest']=c['rows'][171]['original_manifest'];dd[vb['path']]['execution_selection']=ss['execution_selection']
                for item in ss['jobs']:
                    if item['job_id']==row['scientific_job_id']:item['manifest']=row['manifest']
            elif kind=='foreign_manifest':ss['execution_manifests'][0]=ref('foreign');dd[ss['execution_manifests'][0]['path']]=deepcopy(next(iter(docs.values())))
            elif kind=='omitted_item':ss['jobs'].pop()
            elif kind=='extra_manifest_job':dd[ss['execution_manifests'][0]['path']]['jobs'].append(dict(job_id='FOREIGN'))
            elif kind=='duplicate_manifest_job':
                jobs=dd[ss['execution_manifests'][0]['path']]['jobs'];jobs.append(deepcopy(jobs[0]))
            elif kind=='omitted_completion_proof':dd[vb['path']]['completion_validations'].pop()
            elif kind=='wrong_execution_proof':dd[vb['path']]['completion_validations'][-1]['execution_job_id']='FOREIGN'
            elif kind=='root_unapproved':dd[ab['path']]['allow_closed_input_construction']=False
            reject(lambda:selected(ss,dd))
        check('selector_'+kind+'_rejected',adverse)
    def immutable_science():
        prior=N.B.SIM/'scripts/s6d_native_correctness_v1.py';assert cache.binding(prior)['sha256']==N.B.PINS['scorer']
        oldtree=ast.parse(prior.read_text());newtree=ast.parse(Path(S.__file__).read_text());olddefs={n.name:n for n in oldtree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))};newdefs={n.name:n for n in newtree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        assert set(newdefs)==set(olddefs)|{'composite_declarations'}
        before=olddefs['run'];index=next(i for i,n in enumerate(before.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='declared' for t in n.targets));assert isinstance(before.body[index+1],ast.For)
        before.body[index:index+2]=ast.parse('declared=composite_declarations(spec)').body
        for name,node in olddefs.items():assert ast.dump(node,include_attributes=False)==ast.dump(newdefs[name],include_attributes=False),name
        assert cache.binding(N.PARENT)['sha256']=='e379a78c98c937e32549494da52cf1da68278a40ec67294885c1d4fe19299957'
    check('all4260_science_and_downstream_run_AST_unchanged_parent_cache_guard_pinned',immutable_science)
    result=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',tests=rows,passed=sum(x['status']=='PASS' for x in rows),total=len(rows),source_bindings=[cache.binding(a.source_root/name) for name in ('s6d_native176_scoring_inputs_v2.py','s6d_native_correctness_composite_v2.py','s6d_native176_composite_checks_v2.py','README_S6D_NATIVE176_COMPOSITE_V2.md')],composite=meta['composite_ref'],recovery_freeze=meta['recovery_freeze'],static_metadata_unique_paths=len(cache.entries),actual_saved_blocked_checkpoint_and_stopped_result_JSON_read=True,actual171_output_audits=False,fresh5_outputs_read=False,source_audio_journals_read=False,process_queries=0,models=0,devices=0,actual_scoring=False,actual_root_approval_or_queue_created=False,original_broad_suites_rerun=False)
    cache.unchanged();N.save(out/'RECEIPT.json',result);print(json.dumps(dict(status=result['status'],passed=result['passed'],total=result['total'],receipt=cache.binding(out/'RECEIPT.json'))));return 0 if result['status']=='PASS' else 1
def assert_equal(a,b):assert a==b,(a,b)
if __name__=='__main__':raise SystemExit(main())
