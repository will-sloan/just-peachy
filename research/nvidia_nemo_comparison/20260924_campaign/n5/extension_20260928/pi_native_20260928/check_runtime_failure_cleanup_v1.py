"""Check the changed failed-helper pipe cleanup; README_RUNTIME_FAILURE_CLEANUP_CHECK_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,json,os,subprocess,sys,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    me=psutil.Process()
    owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (a.output/'REGISTERED_OWNER.json').write_text(json.dumps(owner),encoding='utf-8')
    source=(Path(__file__).parent/'field_runtime_manager_v6.py').read_bytes()
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Manager')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='failure_poll')
    calls=[]
    namespace=dict(time=time,ticks=lambda pid:None)
    exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-cleanup-method>','exec'),namespace)
    class State:pass
    state=State();state.proc=subprocess.Popen([sys.executable,'-B','-c','import psutil;psutil.Process().cpu_affinity([14]);raise SystemExit(3)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    child=psutil.Process(state.proc.pid)
    child_owner=dict(pid=child.pid,create_time=child.create_time(),affinity=[14])
    (a.output/'CHILD_OWNER.json').write_text(json.dumps(child_owner),encoding='utf-8')
    proc=state.proc;assert proc.wait(timeout=10)==3
    proc.stdout.close()  # Actual already-closed stream from the prior failure path.
    state.error_bytes=b'';state.failure_output_discarded=0;state.failure_stop_time=time.monotonic()
    state.child_owner={'pid':proc.pid,'start_ticks':1,'boot_id':'synthetic'}
    state.helper_slot='launch-03';state.phase='gate';state.fault='synthetic failed helper'
    state.journal=State();state.journal._publish=lambda *args:calls.append(args)
    namespace['failure_poll'](state)
    assert state.proc is None and all(p.closed for p in (proc.stdin,proc.stdout,proc.stderr))
    assert [c[1] for c in calls]==['FAILURE','EXIT'] and calls[1][2]['returncode']==3
    try:alive=psutil.Process(child_owner['pid']).create_time()==child_owner['create_time']
    except psutil.NoSuchProcess:alive=False
    assert not alive
    result=dict(status='PASS_CHANGED_FAILED_HELPER_CLEANUP',positive_groups=1,child_exact_dead=True,child=child_owner,actual_closed_and_open_pipe_paths=True,native_ticks_and_journal_synthetic=True,native_executed=False)
    with (a.output/'RESULT.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
