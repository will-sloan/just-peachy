"""Version 2 supervisor bookkeeping; future resume only. README_S45_EXECUTE.md."""
import argparse, ctypes, subprocess
from s45_common import *

def step(name,script,args=None):
    assert name=='package' or not (REPORT/'UNRESOLVED_SUPERVISOR_CHILD.json').exists(),'Unresolved owned child blocks further work'
    command=[str(BASE_PYTHON),str(SIM/'scripts'/script),*(args or [])]
    folder=REPORT/'supervisor';folder.mkdir(exist_ok=True)
    invocation=name+'_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
    start=time.monotonic();started_utc=now();child=None;script_binding=None
    receipt_path=folder/(invocation+'.json');log_path=folder/(invocation+'.log')
    try:
        script_binding=bind(SIM/'scripts'/script)
        save(receipt_path,{'status':'STARTED','started_utc':started_utc,'argv':command,'script':script_binding,'child_launched':False})
        with log_path.open('w',encoding='utf-8') as log:
            child=subprocess.Popen(command,cwd=SIM/'scripts',env=single_thread_env(),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            save(REPORT/'supervisor_process.json',{'stage':name,'pid':child.pid,'started_utc':started_utc,'scope':'Only this explicitly spawned stage'})
            while child.poll() is None:
                if not launch_allowed() and name in ['capture','h2_outputs','h2_dry']:
                    save(REPORT/'STOP_REQUEST.json',{'reason':'Supervisor launch cutoff; finish current bounded work and restore','utc':now()})
                print(json.dumps({'stage':name,'stage_elapsed_s':time.monotonic()-start,'run_elapsed_s':elapsed_s(),'deadline_remaining_s':remaining_s(),'ssd':storage()}),flush=True)
                time.sleep(20)
        result={'status':'PASS' if child.returncode==0 else 'FAILED','exit_code':child.returncode,'started_utc':started_utc,'ended_utc':now(),'elapsed_s':time.monotonic()-start,'argv':command,'script':script_binding,'log':bind(log_path),'log_complete':True,'child_launched':True,'owned_process_pid':child.pid,'exit_confirmed':True}
        save(receipt_path,result)
        save(folder/(name+'.json'),{'latest_invocation':bind(receipt_path),'status':result['status']})
        save(REPORT/'supervisor_process.json',{'stage':name,'pid':None,'closed_utc':now(),'exit_code':child.returncode,'exit_confirmed':True})
        return child.returncode==0
    except BaseException as exc:
        # All launch/status/monitor/export failures share this path. Cleanup
        # targets only the child returned by this invocation's Popen call.
        cleanup_errors=[];exit_code=None
        def persist(path,value):
            try:save(path,value);return True
            except BaseException as write_exc:
                cleanup_errors.append({'operation':'save','path':str(path),'error':repr(write_exc)})
                return False
        if child is not None:
            try:exit_code=child.poll()
            except BaseException as poll_exc:cleanup_errors.append({'operation':'poll','error':repr(poll_exc)})
            if exit_code is None:
                persist(REPORT/'STOP_REQUEST.json',{'reason':'Supervisor exception requests owned stage finite cleanup','utc':now()})
                try:exit_code=child.wait(timeout=300)
                except BaseException as wait_exc:
                    cleanup_errors.append({'operation':'wait','error':repr(wait_exc)})
                    # A timeout can race an actual exit. Only a confirmed code
                    # permits closing the PID; absence remains unresolved.
                    try:exit_code=child.poll()
                    except BaseException as poll_exc:cleanup_errors.append({'operation':'poll_after_wait','error':repr(poll_exc)})
        unresolved=child is not None and exit_code is None
        status='UNVERIFIED_ACTIVE_CHILD' if unresolved else 'FAILED_NO_CHILD' if child is None else 'FAILED'
        if unresolved:
            marker={'stage':name,'pid':child.pid,'invocation':invocation,'status':'UNVERIFIED_ACTIVE_CHILD','utc':now(),'requires_explicit_resolution':True}
            marker_path=REPORT/'UNRESOLVED_SUPERVISOR_CHILD.json'
            if marker_path.exists():
                # Checkpoint packaging may itself fail while an earlier owned
                # child is unresolved. Retain both identities for resolution.
                try:
                    previous=read(marker_path)
                    previous.setdefault('additional_unresolved_children',[]).append(marker)
                    marker=previous
                except BaseException as marker_exc:
                    cleanup_errors.append({'operation':'read_previous_unresolved_marker','error':repr(marker_exc)})
                    marker['prior_marker_unreadable']=True
                    # An unreadable earlier marker is evidence too; leave its
                    # bytes intact and record this child beside its invocation.
                    marker_path=folder/(invocation+'.unresolved.json')
            persist(marker_path,marker)
            persist(REPORT/'supervisor_process.json',{'stage':name,'pid':child.pid,'status':status,'utc':now(),'exit_confirmed':False})
        else:
            persist(REPORT/'supervisor_process.json',{'stage':name,'pid':None,'closed_utc':now(),'status':status,'exit_code':exit_code,'exit_confirmed':child is not None,'child_launched':child is not None})
        log_binding=None
        if log_path.exists() and not unresolved:
            try:log_binding=bind(log_path)
            except BaseException as log_exc:cleanup_errors.append({'operation':'bind_log','error':repr(log_exc)})
        result={'status':status,'error':repr(exc),'exit_code':exit_code,'started_utc':started_utc,'ended_utc':now(),'elapsed_s':time.monotonic()-start,'argv':command,'script':script_binding,'log':log_binding,'log_path':str(log_path),'log_complete':not unresolved and log_binding is not None,'child_launched':child is not None,'owned_process_pid':child.pid if child is not None else None,'exit_confirmed':child is not None and not unresolved,'cleanup_errors':cleanup_errors}
        if persist(receipt_path,result):
            try:persist(folder/(name+'.json'),{'latest_invocation':bind(receipt_path),'status':status})
            except BaseException as receipt_exc:cleanup_errors.append({'operation':'bind_failure_receipt','error':repr(receipt_exc)})
        raise

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
