"""Admit one fresh pre-Pi Windows lifecycle check. See README_RESTART.md."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
N5=HERE.parent
sys.path.insert(0,str(N5.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import identity, pin, exact_process
from paced_slot import process_census, competitors
from window_guard import window, snapshot


def prepare(name,backend):
    import psutil
    own=identity(pin());w=window();local=N5.parents[4]/'local'
    if not re.fullmatch(r'[a-z0-9-]+',name):raise ValueError('Simple fresh run name required')
    base=local/'n5/prepi-20260928';base.mkdir(exist_ok=True)
    output=base/name;pre=base/(name+'-precheck')
    if output.exists() or pre.exists():raise FileExistsError('Fresh run and precheck required')
    a=load(local/'n5/d1-anonymous-lifecycle-parent-v4/ADMISSION.json')
    source=bind(local/'releases/prepi-shutdown-v1/DERIVATIVE.json');d=load(source['path'])
    release=Path(d['prototype']);files=[]
    for relative,row in d['files'].items():
        b=dict(path=str(release/relative),**row);verify(b);files.append(b)
    for b in a['assets']+[a['audio'],a['acceptance'],a['accepted_source_receipt']]+a['runtime_configs']:verify(b)
    parent=d['parent_source_receipt'];verify(parent)
    if load(parent['path'])['parent_source_receipt']!=a['accepted_source_receipt']:
        raise ValueError('Accepted source ancestry differs')
    cap=128*1024**2
    observed=snapshot(local,cap)
    census=process_census(local.parent)
    if competitors(census,[own,identity(psutil.Process().parent())]):
        raise RuntimeError('Competing numerical/helper process exists')
    worker=load(local/'supervision/worker.json')
    closed=[{k:worker[k] for k in ('pid','create_time')}]
    if worker.get('child_pid'):
        closed.append(dict(pid=worker['child_pid'],create_time=worker['child_create_time']))
    if any(exact_process(o) is not None for o in closed):raise RuntimeError('Prior owner still exists')
    now=datetime.now(timezone.utc);expires=now+timedelta(seconds=600)
    if expires>=datetime.fromisoformat(w['checkpoint_utc']):raise TimeoutError('Insufficient time before checkpoint')
    pre.mkdir();freeze(pre/'CENSUS.json',observed)
    code=a['code']+[bind(HERE/f) for f in ('restart_lifecycle_v1.py','prepare_restart_v1.py','window_guard.py',
        'prepare_shutdown_v1.py','session_shutdown_v1.py','test_late_shutdown_v1.py','test_window_guard.py','README_RESTART.md','build_restart_harness_v1.py','README.md','WINDOW.json')]
    code=list({b['path']:b for b in code}.values())
    for b in code:verify(b)
    for key in ('owner','precheck','supervisor'):a.pop(key,None)
    a.update(scope='PREPI_WINDOWS_RESTART_V1',window=bind(HERE/'WINDOW.json'),
        admitted_utc=now.isoformat(),expires_utc=expires.isoformat(),code=code,
        release=str(release),release_files=files,source_receipt=source,
        parent_source_receipt=parent,reference_inputs=[],backend_key=backend,
        arm='parent',mode='anonymous_conversation',census=bind(pre/'CENSUS.json'),
        budget=observed['calculation'],process_census=census,closed_prior_owners=closed,
        data=str(output/'data'),output_cap_bytes=cap,new_window_scope=True)
    freeze(pre/'CHECK.json',a)
    spec=base/(name+'-worker.json')
    freeze(spec,dict(argv=[sys.executable,'-B',str(HERE/'restart_lifecycle_v1.py'),
        '--precheck',str(pre/'CHECK.json'),'--output',str(output)],cwd=str(HERE)))
    sys.path.insert(0,str(N5.parent/'supervision'))
    import supervisor
    started=supervisor.start(local/'supervision',spec)
    freeze(pre/'STARTED.json',dict(check=bind(pre/'CHECK.json'),worker_spec=bind(spec),supervisor=started))
    print(dict(status='STARTED_NOT_ACCEPTED',output=str(output),supervisor=started))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--backend',choices=['nemotron_hybrid','nemotron_600m'],required=True)
    args=p.parse_args();prepare(args.name,args.backend)
