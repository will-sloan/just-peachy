"""Live unit-property receipt; README_FIELD_STORAGE_REPAIR_V1.md."""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess


def record_envelope(root, owner, limits):
    signal.alarm(290)
    names=['LoadState','ActiveState','MainPID','LimitAS','LimitSTACK','CPUQuotaPerSecUSec',
           'TasksMax','RuntimeMaxUSec','TimeoutStopUSec','LimitFSIZE','ControlGroup']
    args=['systemctl','--user','show','jp-'+root.name+'.service']
    for name in names:args+=['-p',name]
    fields=dict(x.split('=',1) for x in subprocess.check_output(args,text=True).splitlines() if '=' in x)
    assert fields['LoadState']=='loaded' and fields['ActiveState']=='active' and int(fields['MainPID'])==os.getpid()
    assert resource.getrlimit(resource.RLIMIT_AS)==(768*1024**2,)*2
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1024**2,)*2
    assert sorted(os.sched_getaffinity(0))==[2,3]
    assert int(fields['LimitAS'])==768*1024**2 and int(fields['LimitSTACK'])==1024**2
    assert fields['TasksMax']=='64' and fields['RuntimeMaxUSec']=='5min' and fields['TimeoutStopUSec']=='1min'
    assert int(fields['LimitFSIZE'])==32*1024**2
    quota,period=(Path('/sys/fs/cgroup')/fields['ControlGroup'].lstrip('/')/'cpu.max').read_text().split()
    assert int(quota)/int(period)==2
    from field_metadata_budget_v2 import control_write
    control_write(root,'LIVE_ENVELOPE.json',dict(owner=owner,properties=fields,cpu_max=[quota,period],affinity=[2,3],
                  address_space=list(resource.getrlimit(resource.RLIMIT_AS)),stack=list(resource.getrlimit(resource.RLIMIT_STACK))),limits)
