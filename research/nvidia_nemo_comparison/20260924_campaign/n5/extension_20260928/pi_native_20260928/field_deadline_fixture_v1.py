"""No-capture timeout fixture child; README_FIELD_CHILD_DEADLINE_V1.md."""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import field_child_deadline_v1 as deadlines

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)

def main(spec_path):
    root=spec_path.parent;spec=json.loads(spec_path.read_text());a=json.loads((root/'ADMISSION.json').read_text())
    assert spec['mode'] in ['normal','cooperative','stubborn']
    assert sorted(os.sched_getaffinity(0))==[2,3] and resource.getrlimit(resource.RLIMIT_AS)==(768*1024**2,)*2
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1024**2,)*2
    prefix=spec['mode'];owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    save(root/(prefix+'-OWNER.json'),owner)
    sys.path.insert(0,a['installed_release'])
    from release_tools.runtime_lock import RuntimeLock
    data=root/(prefix+'-data');data.mkdir()
    alarm=deadlines.ChildAlarm(spec['deadline'],a).arm();lease=None;result=dict(mode=prefix,deadline=spec['deadline'],owner=owner,models=False,capture=False)
    code=0
    try:
        lease=RuntimeLock(data,'deadline_fixture')
        save(root/(prefix+'-READY.json'),dict(owner=owner,lease_token=lease.token,deadline=spec['deadline'],armed_monotonic_ns=time.monotonic_ns(),affinity=sorted(os.sched_getaffinity(0)),address_space=list(resource.getrlimit(resource.RLIMIT_AS)),stack=list(resource.getrlimit(resource.RLIMIT_STACK))))
        if prefix=='stubborn':
            signal.signal(signal.SIGALRM,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN)
        if prefix=='normal':time.sleep(.02)
        else:
            while True:time.sleep(.025)
    except deadlines.DeadlineExpired as exc:
        result.update(expired=True,error=str(exc));code=124
    finally:
        if lease is not None:lease.close()
        result.update(lease_closed=not (data/'runtime.lock').exists(),finished_ns=time.monotonic_ns())
        save(root/(prefix+'-RESULT.json'),result)
        alarm.close()
    return code

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True)
    raise SystemExit(main(p.parse_args().spec))
