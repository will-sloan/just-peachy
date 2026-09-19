"""Bounded post-freeze supervisor and failure closeout. README_S45_EXECUTE.md."""
import argparse, ctypes, subprocess
from s45_common import *

def step(name,script,args=None):
    assert name=='package' or not (REPORT/'UNRESOLVED_SUPERVISOR_CHILD.json').exists(),'Unresolved owned child blocks further work'
    command=[str(BASE_PYTHON),str(SIM/'scripts'/script),*(args or [])]
    folder=REPORT/'supervisor';folder.mkdir(exist_ok=True)
    invocation=name+'_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
    start=time.monotonic();child=None
    save(folder/(invocation+'.json'),{'status':'STARTED','started_utc':now(),'argv':command,'script':bind(SIM/'scripts'/script)})
    with (folder/(invocation+'.log')).open('w',encoding='utf-8') as log:
        child=subprocess.Popen(command,cwd=SIM/'scripts',env=single_thread_env(),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        save(REPORT/'supervisor_process.json',{'stage':name,'pid':child.pid,'started_utc':now(),'scope':'Only this explicitly spawned stage'})
        try:
            while child.poll() is None:
                if not launch_allowed() and name in ['capture','h2_outputs','h2_dry']:
                    save(REPORT/'STOP_REQUEST.json',{'reason':'Supervisor launch cutoff; finish current bounded work and restore','utc':now()})
                print(json.dumps({'stage':name,'stage_elapsed_s':time.monotonic()-start,'run_elapsed_s':elapsed_s(),'deadline_remaining_s':remaining_s(),'ssd':storage()}),flush=True)
                time.sleep(20)
        except BaseException:
            if child.poll() is None:
                save(REPORT/'STOP_REQUEST.json',{'reason':'Supervisor exception requests owned stage finite cleanup','utc':now()})
                try:child.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    save(REPORT/'supervisor_process.json',{'stage':name,'pid':child.pid,'status':'UNVERIFIED_ACTIVE_CHILD','utc':now()})
                    save(REPORT/'UNRESOLVED_SUPERVISOR_CHILD.json',{'stage':name,'pid':child.pid,'invocation':invocation,'status':'UNVERIFIED_ACTIVE_CHILD','utc':now(),'requires_explicit_resolution':True})
            raise
    result={'status':'PASS' if child.returncode==0 else 'FAILED','exit_code':child.returncode,'ended_utc':now(),'elapsed_s':time.monotonic()-start,'argv':command,'script':bind(SIM/'scripts'/script),'log':bind(folder/(invocation+'.log'))}
    save(folder/(invocation+'.json'),result)
    save(folder/(name+'.json'),{'latest_invocation':bind(folder/(invocation+'.json')),'status':result['status']})
    save(REPORT/'supervisor_process.json',{'stage':name,'pid':None,'closed_utc':now(),'exit_code':child.returncode})
    return child.returncode==0

def main():
    assert (SIM/'scripts/s45_package.py').exists(),'Failure packager must exist before capture'
    assert read(BANK/'SCENE_MANIFEST.json')['validation']['status']=='PASS'
    keep=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001);assert keep
    errors=[]
    try:
        if launch_allowed(180):
            if not step('capture','s45_campaign.py'):errors.append('capture')
        else:errors.append('capture_not_launched_time_budget')
        from s45_campaign import selected_snapshot,validate_restorations
        selected_snapshot(read(BANK/'SCENE_MANIFEST.json'))
        validate_restorations()
        if not step('capture_analysis','s45_capture_analysis.py'):errors.append('capture_analysis')
        if not step('prepare_h2_plans','s45_h2_run.py',['--prepare-plans']):errors.append('h2_plan')
        accepted={r['case_id'] for r in read(REPORT/'ACCEPTED_CAPTURES.json')['accepted']}
        sentinels=[cid for cid in read(REPORT/'SENTINEL_PLAN.json')['scene_ids'] if cid in accepted]
        if sentinels and 'capture_analysis' not in errors and 'h2_plan' not in errors and launch_allowed(600):
            save(REPORT/'H2_RELEASE.json',{'status':'AUTHORIZED_OFFLINE_H2','authorized_utc':now(),'basis':'User-authorized bounded S4.5; final frozen inputs, restored hardware and protected development sentinel selection','allow_during_physical_capture':False,'maximum_output_jobs':48,'maximum_dry_jobs':24,'reserve_jobs':0,'supervisor_code':bind(Path(__file__))})
            if step('validate_h2','s45_h2_run.py',['--kind','outputs','--cases',*sentinels,'--validate-only']):
                if not step('h2_outputs','s45_h2_run.py',['--kind','outputs','--cases',*sentinels]):errors.append('h2_outputs')
            else:errors.append('h2_validation')
            if launch_allowed(600) and 'h2_validation' not in errors and 'h2_outputs' not in errors:
                if not step('h2_dry','s45_h2_run.py',['--kind','dry']):errors.append('h2_dry')
        else:errors.append('h2_not_launched_inputs_or_budget')
    except BaseException as exc:
        errors.append(repr(exc));save(REPORT/'supervisor_error.json',{'utc':now(),'error':repr(exc)})
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(keep)
        save(REPORT/'supervisor_keep_awake.json',{'active':False,'prior_state_restored':True,'prior_flags':keep,'released_utc':now()})
        save(REPORT/'supervisor_receipt.json',{'ended_utc':now(),'elapsed_s':elapsed_s(),'errors':errors,'stopped_after':'S4.5','training_launched':False})
        for name,script in [('coverage','s45_coverage.py'),('results','s45_results.py')]:
            if (SIM/'scripts'/script).exists() and not (REPORT/'UNRESOLVED_SUPERVISOR_CHILD.json').exists():
                try:
                    if not step(name,script):errors.append(name)
                except BaseException as exc:errors.append(name+': '+repr(exc))
        save(REPORT/'supervisor_receipt.json',{'ended_utc':now(),'elapsed_s':elapsed_s(),'errors':errors,'stopped_after':'S4.5','training_launched':False})
        try:
            if not step('package','s45_package.py'):errors.append('package')
        except BaseException as exc:errors.append('package: '+repr(exc))
        closed={'status':'ACTIVE_CHILD_UNVERIFIED' if (REPORT/'UNRESOLVED_SUPERVISOR_CHILD.json').exists() else 'SUPERVISOR_CLOSED','errors':errors,'report':str(REPORT),'ended_utc':now(),'package_errors_persisted_separately_to_keep_packaged_primary_receipt_immutable':True}
        save(REPORT/'supervisor_postpackage_receipt.json',closed)
        print(json.dumps(closed,indent=2))

if __name__=='__main__':main()
