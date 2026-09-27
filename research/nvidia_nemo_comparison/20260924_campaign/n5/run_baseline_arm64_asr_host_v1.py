"""Supervised bounded paired baseline ASR owner; README_BASELINE_ARM64_ASR_V1.md."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin,identity,exact_process
from private_application_process_v3 import PrivateApplicationProcess
from baseline_arm64_asr_review_v1 import require,review


def linux(path):
    p=Path(path).resolve();return '/mnt/'+p.drive[0].lower()+'/'+p.as_posix()[3:]


def run(precheck,output):
    own=identity(pin());local=HERE.parents[4]/'local';a=load(precheck);now=datetime.now(timezone.utc)
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'),'Fresh N5 output required')
    require(a['scope']=='BASELINE_ASR_WINDOWS_ARM64_COMPONENT_PARITY_ONLY','Wrong scope')
    require(0<=(now-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<120,'Admission stale')
    require(now<datetime.fromisoformat(a['expires_utc'])<datetime(2026,9,28,2,48,19,tzinfo=timezone.utc),'Cutoff differs')
    require((datetime.fromisoformat(a['expires_utc'])-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<=1800
        and a['allocation_bytes']==128*1024**2,'Allocation differs')
    for b in a['code']+[a['audio'],a['wheel'],a['census'],a['prior_tool_inputs']]+[r['asset'] for r in a['models']]:verify(b)
    require(all(exact_process(o) is None for o in a['closed_prior_owners']),'Prior owner active')
    for _ in range(50):
        worker=load(local/'supervision/worker.json')
        if worker.get('child_pid')==own['pid'] and worker.get('child_create_time')==own['create_time']:break
        time.sleep(.1)
    require(worker.get('child_pid')==own['pid'] and worker.get('child_create_time')==own['create_time'],'Not exact supervised child')
    require(exact_process({k:worker[k] for k in ('pid','create_time')}) is not None,'Supervisor absent')
    require(load(local/'supervision/worker_spec.json')['argv']==__import__('psutil').Process().cmdline(),'Worker argv differs')
    output.mkdir();a.update(owner=own,supervisor=worker,precheck=bind(precheck));freeze(output/'ADMISSION.json',a)
    error=None;wsl=None;wsl_owner=None;reference=None
    def limits():
        require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Allocation expired')
        require(not (output/'CANCEL').exists(),'Stage cancelled')
        require(all(shutil.disk_usage(d+':/').free>gib*1024**3 for d,gib in [('C',50),('G',75)]),'Drive reserve breached')
        require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<a['allocation_bytes'],'Output allocation exceeded')
    try:
        with PrivateApplicationProcess(output/'reference-lifetime',executable_binding=bind(sys.executable),
                script_binding=bind(HERE/'baseline_asr_reference_v1.py'),cpu=4,
                arguments=['--admission',str(output/'ADMISSION.json'),'--output',str(output/'reference')]) as process:
            process.spawn_suspended()
            process.resume(lambda who,**values:freeze(output/'REFERENCE_OWNER.json',dict(owner=who,**values)))
            began=time.monotonic()
            while not process.root_exited():
                limits();require(time.monotonic()-began<180,'Windows reference deadline');time.sleep(1)
        require(process.receipt['root_exit_code']==0 and not process.receipt['forced'],'Windows reference failed')
        reference=review(output/'reference/events.jsonl',a['frames'])
        a['reference_events']=bind(output/'reference/events.jsonl');a['reference_result']=bind(output/'reference/RESULT.json')
        freeze(output/'LINUX_ADMISSION.json',a)
        argv=['wsl.exe','-d','Ubuntu','--','timeout','--signal=TERM','--kill-after=10s','1450s',
            'python3','-B',linux(HERE/'run_baseline_arm64_asr_v1.py'),'--admission',linux(output/'LINUX_ADMISSION.json'),'--output',linux(output/'linux')]
        with (output/'wsl.stdout').open('xb') as out,(output/'wsl.stderr').open('xb') as err:
            wsl=subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            wsl_owner=identity(__import__('psutil').Process(wsl.pid));freeze(output/'WSL_OWNER.json',dict(owner=wsl_owner,argv=argv))
            began=time.monotonic()
            while wsl.poll() is None:
                limits();require(time.monotonic()-began<1470,'WSL timeout did not close');time.sleep(2)
        require(wsl.returncode==0 and load(output/'linux/RESULT.json')['status']=='PASS_EMULATED_BASELINE_ASR_COMPONENT_PARITY_ONLY','ARM64 component failed; preserve receipts')
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    finally:
        if wsl is not None and wsl.poll() is None:
            if not (output/'CANCEL').exists():(output/'CANCEL').write_text(str(error),encoding='utf-8')
            try:wsl.wait(timeout=15)
            except subprocess.TimeoutExpired:
                wsl.terminate();wsl.wait(timeout=5);error=str(error)+'; Linux group closure unverified'
    freeze(output/'RESULT.json',dict(status='PASS_PAIRED_BASELINE_ASR_COMPONENT_ONLY' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),owner=own,wsl_owner=wsl_owner,error=error,
        admission=bind(output/'ADMISSION.json'),reference_passed=reference is not None,
        linux_result=bind(output/'linux/RESULT.json') if (output/'linux/RESULT.json').exists() else None,
        GUI_validated=False,CM5_tested=False,N5_complete=False))
    return int(error is not None)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--precheck',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.precheck,a.output))
