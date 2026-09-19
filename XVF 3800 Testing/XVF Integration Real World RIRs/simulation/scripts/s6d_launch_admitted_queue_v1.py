"""Launch one root-admitted literal queue after fresh validation; see README."""
import argparse,datetime,hashlib,json,os,subprocess,time
from pathlib import Path
import psutil
SIM=Path(__file__).resolve().parents[1];EDGE=SIM.parents[2]/'.edge-speech-env/python.exe'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def verify(b):
    p=Path(b['path']);data=p.read_bytes()
    if len(data)!=b['bytes'] or hashlib.sha256(data).hexdigest()!=b['sha256']:raise ValueError('Changed admitted binding '+str(p))
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--review-receipt',type=Path,required=True);a=ap.parse_args()
    receipt=read(a.review_receipt);directory=a.review_receipt.parent
    for k in ('queue','approval','runner'):verify(receipt[k])
    if list(directory.glob('ROOT_LAUNCH*.json')):raise ValueError('Existing launch must be preserved; never launch concurrently')
    queue=read(receipt['queue']['path'])
    if queue.get('owner_thread_id')!='01a0812d-3ff0-7ed0-a06c-4df61b62a459' or queue.get('owner_session_id')!=queue.get('owner_thread_id') or queue.get('fixture_only') is not False:raise ValueError('Exact actual root-owned queue required')
    if not EDGE.exists():raise ValueError('Original edge interpreter required')
    argv=[str(EDGE),'-B',receipt['runner']['path'],'--queue',receipt['queue']['path'],'--approval',receipt['approval']['path'],'--queue-sha256',receipt['queue']['sha256'],'--approval-sha256',receipt['approval']['sha256'],'--state-dir',str(directory/'state')]
    validate_log=directory/'LAUNCH_VALIDATE_ONLY.log'
    with validate_log.open('x',encoding='utf-8') as f:
        check=subprocess.run(argv+['--validate-only'],cwd=SIM,stdout=f,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    if check.returncode:raise ValueError('Runner validate-only failed; inspect '+str(validate_log))
    if len(queue['jobs'])==1 and queue['jobs'][0]['kind']=='hardware':
        child=queue['jobs'][0]['argv']
        def arg(name):return child[child.index(name)+1]
        owner_cmd=[child[0],'-B',arg('--owner'),'check-plan','--plan',arg('--plan'),'--authorization',arg('--authorization')]
        with (directory/'LAUNCH_OWNER_CHECK_PLAN.log').open('x',encoding='utf-8') as f:
            check=subprocess.run(owner_cmd,cwd=SIM,stdout=f,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        if check.returncode:raise ValueError('Owner plan validation failed without launch')
    argv+=['--keep-awake'];started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (directory/'SUPERVISOR.stdout.log').open('xb') as out,(directory/'SUPERVISOR.stderr.log').open('xb') as err:
        proc=subprocess.Popen(argv,cwd=SIM,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    launch=dict(status='SUPERVISOR_LAUNCHED',utc=started,pid=proc.pid,creation_time=psutil.Process(proc.pid).create_time(),argv=argv,root_review_receipt=str(a.review_receipt),queue=receipt['queue'],approval=receipt['approval'],runner=receipt['runner'],launcher_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),automatic_model_resume_installed=False)
    save(directory/'ROOT_LAUNCH_V1.json',launch)
    ps='& '+' '.join("'"+x.replace("'","''")+"'" for x in argv);cmd=subprocess.list2cmdline(argv)
    text=f'''# Actual admitted S6D queue execution

Purpose: execute only the exact root-reviewed literal queue in QUEUE.json. Inputs are the hash-bound queue, approval, source graph and root review receipt. Outputs are per-job declared artifacts and state/HEALTH.jsonl, CHECKPOINT.json, owner/closure evidence and stdout/stderr logs. This launch is already in progress or historical; never run a second copy or overwrite receipts.

Launched {started}; supervisor PID{proc.pid}. The runner validates all source/config bindings and resource/deadline limits before child admission. Every hardware child is additionally checked with the owner's read-only check-plan action. Hardware is never terminated: cooperative STOP and actual restoration are mandatory. Offline worker ownership is explicit in its bound protocol. Existing job limits define completion; a queue FINISH is not automatically overallS6D completion.

Local code logs health every15s and checkpoint opportunities at the queue workload's10/30-minute policy. These files do not invoke Codex automatically. Keep-awake is restored on supervisor close; explicit desktop sleep is still possible. C50GiB/G75GiB, payload40GiB,480physical attempts/21600s and the original campaign deadline apply.

Exact historical command, PowerShell:

```powershell
{ps}
```

Anaconda Prompt / CMD (explicit interpreter, no activation):

```bat
{cmd}
```

The actual queue and its root authorization define scientific inputs, outputs, counts and exclusions. See simulation/scripts/README_S6D_LAUNCH_ADMITTED_QUEUE_V1.md for this launcher. Preserve failures and review actual closed artifacts before admitting dependent stages.
'''
    (directory/'README_RUN.md').write_text(text,encoding='utf-8')
    print(json.dumps(dict(status=launch['status'],pid=proc.pid,utc=started,queue=receipt['queue']['path'])))
if __name__=='__main__':main()
