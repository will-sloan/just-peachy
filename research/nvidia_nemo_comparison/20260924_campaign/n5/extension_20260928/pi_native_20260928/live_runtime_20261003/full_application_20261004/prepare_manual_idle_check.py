"""Prepare a narrow manual-lifetime idle check. See README_MANUAL_IDLE_CHECK.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def main():
    here=Path(__file__).resolve().parent
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    out=private/'audit-preparation'/('manual-idle-source-'+uuid.uuid4().hex);out.mkdir()
    me=psutil.Process();started=time.time()
    def write(name,raw):
        with (out/name).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        assert (out/name).read_bytes()==raw
    def put(name,value):write(name,json.dumps(value,sort_keys=True,allow_nan=False).encode())
    put('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=600,maximum_bytes=2*1024**2,native_action=False))
    raw=(here.parent/'launch_production_idle_action_v2.py').read_bytes()
    tree=ast.parse(raw)
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTROL_SOURCE' for t in n.targets))
    control=ast.literal_eval(assignment.value)
    old="receipt['runtime_max_seconds']!=7200"
    new="receipt['runtime_max_seconds'] is not None or receipt.get('deadline_monotonic') is not None\n            or receipt.get('lifetime_policy')!='manual_stop_storage_guarded'"
    assert control.count(old)==1
    changed=control.replace(old,new).replace('Actual standard production7200-second nested unit differs','Actual manual-Stop guarded production unit differs')
    compile(changed,'<manual-stop-idle-control>','exec')
    text=raw.decode();lines=text.splitlines(keepends=True)
    assert assignment.end_lineno==assignment.lineno
    lines[assignment.lineno-1]='CONTROL_SOURCE = '+repr(changed)+'\n'
    result=''.join(lines).encode();compile(result,'<manual-stop-idle-action>','exec')
    before={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    after={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(result).body if isinstance(n,ast.FunctionDef)}
    assert before==after
    for name,value in [('ORIGINAL.py',raw),('CONTROL_ORIGINAL.py',control.encode()),('CONTROL_CHANGED.py',changed.encode()),('ACTION.py',result),('ACTION.restore.py',result),('README.md',(here/'README_MANUAL_IDLE_CHECK.md').read_bytes()),('PREPARER.py',Path(__file__).read_bytes())]:write(name,value)
    target=here/'launch_manual_idle_action.py'
    with target.open('xb') as stream:stream.write(result);stream.flush();os.fsync(stream.fileno())
    assert target.read_bytes()==result
    assert sum(p.stat().st_size for p in out.iterdir())<2*1024**2 and time.time()-started<600
    put('SOURCE_CLOSED.json',dict(independent_restore=True,original_sha256=hashlib.sha256(raw).hexdigest(),new_sha256=hashlib.sha256(result).hexdigest(),native_action=False,outer_functions_unchanged=True,closed_unix=time.time()))
    print(json.dumps(dict(status='PASS',output=str(out),target=str(target))))


if __name__=='__main__':main()
