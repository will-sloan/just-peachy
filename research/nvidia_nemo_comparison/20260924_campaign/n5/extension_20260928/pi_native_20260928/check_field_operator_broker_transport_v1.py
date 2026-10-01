"""Changed bounded host transport checks; README_FIELD_OPERATOR_BROKER_TRANSPORT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
sys.dont_write_bytecode=True

CHILD="""import psutil
psutil.Process().cpu_affinity([14])
import sys,json,time
from pathlib import Path
me=psutil.Process()
Path(sys.argv[1]).open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
if sys.argv[2]=='echo':
 raw=sys.stdin.buffer.read();sys.stdout.buffer.write(raw);sys.stderr.buffer.write(b'checked');sys.stdout.flush()
elif sys.argv[2]=='overflow':
 sys.stdout.buffer.write(b'x'*4096);sys.stdout.flush()
elif sys.argv[2]=='deadline':
 time.sleep(.5)
"""
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--expires-utc',required=True);a=p.parse_args()
    a.output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (a.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    expiry=datetime.fromisoformat(a.expires_utc)
    if not 5<(expiry-datetime.now(timezone.utc)).total_seconds()<=600:raise ValueError('Fresh bounded host check')
    from field_operator_broker_host_v2 import process_phase
    rows=[]
    for name,maximum,timeout,payload in (('echo',32768,5,bytes(range(256))*80),('overflow',128,5,None),('deadline',128,.05,None)):
        if datetime.now(timezone.utc)>=expiry:raise TimeoutError('Check scope')
        path=a.output/(name+'-OWNER.json')
        value=process_phase([sys.executable,'-B','-c',CHILD,str(path),name],payload=payload,maximum=maximum,timeout=timeout)
        observed=json.loads(path.read_bytes())
        try:created=psutil.Process(observed['pid']).create_time()
        except psutil.NoSuchProcess:created=None
        assert created is None or abs(created-observed['create_time'])>.001
        assert value['ssh_reaped'] and value['readers_joined']
        if name=='echo':
            assert value['stdout']==payload and value['stderr']==b'checked' and value['returncode']==0 and value['fault'] is None
        elif name=='overflow':
            assert value['overflow'] and value['fault'] is not None and len(value['stdout'])==128
        else:assert value['fault'] is not None and 'deadline' in value['fault']
        rows.append(dict(case=name,owner=observed,exact_dead=True,
            **{k:v for k,v in value.items() if k not in ('stdout','stderr')},
            stdout_bytes=len(value['stdout']),stderr_bytes=len(value['stderr'])))
    result=dict(status='PASS_CHANGED_HOST_TRANSPORT_ONLY',cases=rows,positive=1,rejections=2,
        native_execution=False,model_or_capture=False,kernel_quota=False,
        completed_utc=datetime.now(timezone.utc).isoformat())
    raw=json.dumps(result).encode()
    assert len(raw)<16384 and datetime.now(timezone.utc)<expiry
    (a.output/'RESULT.json').open('xb').write(raw)
    print(json.dumps(dict(status=result['status'],positive=1,rejections=2)))
if __name__=='__main__':main()
