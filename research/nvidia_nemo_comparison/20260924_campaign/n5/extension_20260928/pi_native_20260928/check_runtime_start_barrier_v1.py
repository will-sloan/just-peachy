"""Changed STARTED publication regression; README_RUNTIME_START_BARRIER_CHECK_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os,stat,time
from pathlib import Path
from datetime import datetime,timezone

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('bundle','scope','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    def put(n,v):
        with (a.output/n).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
    put('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    scope=json.loads(a.scope.read_bytes())
    assert datetime.now(timezone.utc)<datetime.fromisoformat(scope['expires_utc'])
    assert sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())+65536<scope['maximum_bytes']
    from field_runtime_start_barrier_v1 import derive
    packed,review=derive(a.bundle.read_bytes());value=json.loads(packed)
    native=base64.b64decode(value['files']['code/field_operator_broker_common_v1.py']).decode()
    node=next(n for n in ast.parse(native).body if isinstance(n,ast.FunctionDef) and n.name=='runtime_started')
    directory=a.output/'synthetic-runtime';target=directory/'recordings/recording-01';target.mkdir(parents=True)
    primary=target/'STARTED.json';pending=target/'STARTED.json.pending'
    gate=dict(pid=20,start_ticks=200,boot_id='00000000-0000-0000-0000-000000000001')
    worker=dict(pid=30,start_ticks=300,boot_id=gate['boot_id'])
    binding=dict(root=str(directory),slot='recording-01',policy_sha256='a'*64,manager_owner=dict(pid=10,start_ticks=100))
    broker=a.output/'synthetic-broker';broker.mkdir()
    row=dict(policy_sha256='a'*64,slot='recordings/recording-01',owner=worker,gate_owner=gate,
       binding=dict(source=str(broker),policy_sha256='b'*64),unit=dict(MainPID='30',ActiveState='active'))
    counts=dict(check=0,read=0)
    def read(path,cap=65536):
        if Path(path)==broker/'broker/CONFIG.json':return dict(runtime=binding)
        s=path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>cap:raise ValueError('Real bounded unique file required')
        counts['read']+=1
        assert not pending.exists()
        return json.loads(path.read_bytes())
    env=dict(Path=Path,time=time,read=read,ticks=lambda pid:{10:100,20:200,30:300}.get(pid),file_pin=lambda p:dict(sha256='b'*64))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-changed-runtime-started>','exec'),env)
    fn=env['runtime_started']
    pending.write_text(json.dumps(row));os.link(pending,primary)
    assert primary.stat().st_nlink==2
    def check():
        counts['check']+=1
        if counts['check']==3:pending.unlink()
    assert fn(broker,{},gate,worker,check)==row and counts==dict(check=3,read=1)
    rejects=[]
    for case in ('oversized','third-link','manager-dead','wrong-binding'):
        folder=a.output/case;folder.mkdir();p=folder/'STARTED.json'
        # Fresh fixture roots for each negative boundary, without changing the positive evidence.
        original_root=binding['root'];original_slot=binding['slot']
        rec=folder/'recordings/recording-01';rec.mkdir(parents=True)
        binding['root']=str(folder);p=rec/'STARTED.json'
        bad=dict(row)
        if case=='wrong-binding':bad['policy_sha256']='c'*64
        p.write_bytes(b'x'*16385 if case=='oversized' else json.dumps(bad).encode())
        if case=='third-link':os.link(p,folder/'link1');os.link(p,folder/'link2')
        if case=='manager-dead':env['ticks']=lambda pid:None
        try:fn(broker,{},gate,worker,lambda:None)
        except (ValueError,RuntimeError):rejects.append(case)
        else:raise AssertionError('Expected changed boundary rejection: '+case)
        finally:
            binding['root']=original_root;binding['slot']=original_slot
            env['ticks']=lambda pid:{10:100,20:200,30:300}.get(pid)
    assert len(rejects)==4
    put('RESULT.json',dict(status='PASS_CHANGED_HOST_STARTED_PUBLICATION_BARRIER',positive_groups=1,rejects=rejects,
        source_review=review,native_executed=False,synthetic_identities=True,actual_windows_hardlink=True))
    print(json.dumps(dict(status='PASS_CHANGED_HOST_STARTED_PUBLICATION_BARRIER',positive_groups=1,rejects=len(rejects))))
if __name__=='__main__':main()
