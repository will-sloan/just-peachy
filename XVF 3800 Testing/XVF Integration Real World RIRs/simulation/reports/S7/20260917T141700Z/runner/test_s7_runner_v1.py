"""Bounded inherited-protocol S7 fixtures; shared README_S7_RUNNER_V1.md."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
import s7_runner_v1 as R
SIM=Path(__file__).resolve().parents[4]
BASE=SIM/'reports/S6D/20260913T195357Z/runner/source_epoch_payload_v5/s6d_runner_v1.py'
FIXTURE=SIM/'scripts/s6d_runner_fixtures_v1.py'
def run(output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(R.S7_REPORT_ROOT/'runner'):
        raise ValueError('Fresh private fixture namespace required')
    output.mkdir(parents=True)
    assert R.binding(BASE)['sha256']==R.BASE_SOURCE_SHA256
    assert R.binding(FIXTURE)['sha256']=='81d6138ef427c762d2b969ff6ef2e7abacff9a5533e109481db2604ad101735c'
    sys.path.insert(0,str(SIM/'scripts'))
    loader=importlib.util.spec_from_file_location('s7_private_inherited_fixtures',FIXTURE)
    F=importlib.util.module_from_spec(loader);loader.loader.exec_module(F);F.runner=R
    checks=[]
    def yes(name,test):
        assert test;checks.append(name)
    def no(name,fn):
        F.rejected(fn);checks.append(name)
    def commit(q,a,args):
        a['approved_job_sha256']=[R.digest(j) for j in q['jobs']]
        R.save(args[0],q);qh=R.binding(args[0])['sha256'];a['queue_sha256']=qh;R.save(args[1],a)
        return (args[0],args[1],qh,R.binding(args[1])['sha256'],args[4])
    def case(name,modes=('normal',)):
        q,a,args=F.make_case(output,name,modes=modes)
        q['schema']='s7_approved_job_queue_v1';a['schema']='s7_queue_approval_v1'
        for j in q['jobs']:j['source_bindings'].append(R.binding(SIM/'scripts/s6d_runner_v1.py'))
        return q,a,commit(q,a,args)
    # Every original function/class is unchanged except the declared admission
    # functions and two human-readable stage-name literals.
    def nodes(path):
        return {n.name:n for n in ast.parse(Path(path).read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    before,after=nodes(BASE),nodes(R.__file__)
    class Labels(ast.NodeTransformer):
        def visit_Constant(self,n):
            if isinstance(n.value,str):n.value=n.value.replace('aggregate S7 PASS','aggregate S6D PASS').replace('broader S7 scope','broader S6D scope')
            return n
    for name,n in before.items():
        if name in ('validate_queue','validate_payload_ceiling'):continue
        yes('inherited_AST_'+name,ast.dump(n,include_attributes=False)==ast.dump(Labels().visit(after[name]),include_attributes=False))
    health=dict(alive=True,exit_code=None,heartbeat_valid=True,heartbeat_age=1,progress_age=1,elapsed=1,heartbeat_stale=30,stall_after=60,timeout=100,completion_ok=False)
    yes('stale_heartbeat_is_not_dead',R.classify(**{**health,'heartbeat_age':40})[0]=='WAIT')
    yes('progress_stall_distinct',R.classify(**{**health,'progress_age':61})[0]=='REVIEW_FAILURE')
    yes('failed_unit_no_success',R.classify(**{**health,'alive':False,'exit_code':3,'completion_ok':True})[0]=='REVIEW_FAILURE')
    yes('zero_exit_missing_receipt',R.classify(**{**health,'alive':False,'exit_code':0})[0]=='REPORT_BLOCKED')
    yes('pid_creation_mismatch',not R.process_matches(os.getpid(),R.psutil.Process().create_time()+1))
    q,a,args=case('resume')
    first=R.Supervisor(*args,test_interval=.03).run()
    second=R.Supervisor(*args,test_interval=.03).run()
    launches=Path(q['jobs'][0]['completion_path']).with_name('child_launch_count.txt').read_text().splitlines()
    yes('actual_tiny_child_and_resume',first['action']==second['action']=='FINISH' and len(launches)==1)
    yes('resume_request_bound',R.load(args[4]/'RESUME_REQUEST.json')['queue']==R.binding(args[0]))
    result_path=Path(q['jobs'][0]['expected_artifacts'][0]['path']);R.save(result_path,{'scientific_predicate':'FAIL','fixture_only':True})
    tamper=R.Supervisor(*args,test_interval=.03).run()
    yes('completed_hash_tamper_blocks_no_relaunch',tamper['action']=='REPORT_BLOCKED' and len(Path(q['jobs'][0]['completion_path']).with_name('child_launch_count.txt').read_text().splitlines())==1)
    q,a,args=case('failed',('failed',))
    failed=R.Supervisor(*args,test_interval=.03).run()
    yes('actual_failed_child_stops',failed['action']=='REVIEW_FAILURE')
    q,a,args=case('admission')
    q['fixture_only']=False;q['run_id']='20260917T141700Z';a['run_id']=q['run_id']
    q['campaign']={'started_utc':R.CAMPAIGN_STARTED_UTC,'deadline_utc':'2026-09-20T14:17:00Z','closeout_reserve_s':3600}
    q['payload_policy']={'new_payload_roots':[str(R.S7_REPORT_ROOT),str(R.S7_PAYLOAD_ROOT)],'max_new_payload_bytes':40*1024**3}
    q['disk_policy']=[{'path':'C:/','minimum_free_bytes':50*1024**3},{'path':'G:/','minimum_free_bytes':75*1024**3}]
    a['allowed_output_roots']=[str(R.S7_REPORT_ROOT),str(R.S7_PAYLOAD_ROOT)];args=commit(q,a,args)
    yes('production_literal_admission',R.validate_queue(q,a,args[2]))
    yes('fixed_work_cutoff',R.work_deadline(q)==R.timestamp('2026-09-20T13:17:00Z'))
    for name,change in [
        ('reset_start',lambda x:x['campaign'].update(started_utc='2026-09-18T14:17:00Z')),
        ('extended_deadline',lambda x:x['campaign'].update(deadline_utc='2026-09-20T14:17:01Z')),
        ('weak_reserve',lambda x:x['campaign'].update(closeout_reserve_s=3599)),
        ('boolean_reserve',lambda x:x['campaign'].update(closeout_reserve_s=True)),
        ('payload80',lambda x:x['payload_policy'].update(max_new_payload_bytes=80*1024**3)),
        ('subset_census',lambda x:x['payload_policy'].update(new_payload_roots=[str(R.S7_REPORT_ROOT)])),
        ('weak_disk',lambda x:x['disk_policy'][0].update(minimum_free_bytes=49*1024**3)),
        ('hardware',lambda x:x['jobs'][0].update(kind='hardware')),
        ('inline_eval',lambda x:x['jobs'][0]['argv'].append('-c')),
        ('output_escape',lambda x:x['jobs'][0].update(completion_path=str(R.S7_REPORT_ROOT.parent/'escape.json'))),
        ('source_tamper',lambda x:x['jobs'][0]['source_bindings'][0].update(sha256='0'*64))]:
        changed=copy.deepcopy(q);approved=copy.deepcopy(a);change(changed);approved['approved_job_sha256']=[R.digest(j) for j in changed['jobs']]
        no(name,lambda:R.validate_queue(changed,approved,args[2]))
    supervisor=R.Supervisor(*args)
    with patch.object(R.time,'time',return_value=R.work_deadline(q)-1),patch.object(R.subprocess,'Popen') as popen:
        cutoff=supervisor.run_job(q['jobs'][0]);yes('deadline_prevents_spawn',cutoff['action']=='REPORT_BLOCKED' and not popen.called)
    supervisor.payload_census.close()
    spec={'run_id':q['run_id'],'owner_thread_id':'fixture_root','owner_session_id':'fixture_session','authorization_ref':'ROOT_AUTHORIZED_TINY_METADATA_ONLY_TEST_NO_LAUNCH','jobs':q['jobs']}
    prepared=R.prepare_queue(spec,output/'builder')
    yes('builder_binds_without_launch',prepared['jobs_launched']==0 and prepared['queue']['sha256']==R.binding(output/'builder/QUEUE.json')['sha256'])
    no('builder_fresh_namespace',lambda:R.prepare_queue(spec,output/'builder'))
    report={'status':'PASS_SOURCE_AND_BOUNDED_MODEL_FREE_FIXTURES','checks':len(checks),'passed':checks,
        'runner':R.binding(R.__file__),'readme':R.binding(Path(__file__).with_name('README_S7_RUNNER_V1.md')),
        'tests':R.binding(__file__),'base':R.binding(BASE),'inherited_fixture_source':R.binding(FIXTURE),
        'scope':'Two tiny Python protocol children; no production jobs/models/hardware/power changes. Source equivalence reuses all unchanged supervisor/owner/stop/census methods. Actual S7 census not run; production admission tested read-only, cutoff Popen mocked.'}
    R.save(output/'SOURCE_CHECKS.json',report,exclusive=True);print(json.dumps(R.binding(output/'SOURCE_CHECKS.json')))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
