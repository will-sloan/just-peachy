"""Changed manager startup and EOF checks; README_FIELD_RUNTIME_STARTUP_CHECK_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,json,os,time
from pathlib import Path,PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir()
    me=psutil.Process()
    (args.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(
        pid=me.pid,create_time=me.create_time(),affinity=[14])),encoding='utf-8')
    from field_runtime_capsule_v2 import COMMON
    node=next(n for n in ast.parse(COMMON).body if isinstance(n,ast.FunctionDef) and n.name=='runtime_units')
    boot='11111111-2222-3333-4444-555555555555'
    config=dict(runtime=dict(root='/fixture/field-runtime-v1',slot='recording-01',
        manager_unit='jp-field-runtime-v1.service',slice='jpfieldfieldruntimev1.slice',
        manager_owner=dict(pid=100,start_ticks=1000,boot_id=boot)))
    broker_unit='jp-field-operator-sessions-v20.service'
    state={}
    class FixturePath(PurePosixPath):
        def exists(self):return state['owner_exists']
    def fixture_read(path,cap):
        if str(path).endswith('RESERVED.json'):return dict(operation=dict(root='/fixture/field-operator-sessions-v20'))
        return dict(pid=state.get('owner_pid',200),start_ticks=2000,boot_id=boot)
    namespace=dict(Path=FixturePath,read=fixture_read,
        identity=lambda:dict(pid=state['self_pid'],start_ticks=state['self_pid']*10,boot_id=boot),
        ticks=lambda pid: {100:1000,200:2000,300:3000}.get(pid))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-capsule-runtime-units>','exec'),namespace)
    check=namespace['runtime_units']
    def run(command,**kwargs):
        assert kwargs==dict(capture_output=True,timeout=5)
        if 'list-units' in command:
            text='\n'.join(state['units'])+'\n'
        else:
            name=command[3]
            if name==config['runtime']['manager_unit']:
                row=dict(MainPID='100',ActiveState='active',LimitAS='134217728',LimitSTACK='1048576',
                    LimitFSIZE='33554432',TasksMax='64',Slice=config['runtime']['slice'],RuntimeMaxUSec='1d')
                row.update(state.get('manager_patch',{}))
            elif name==config['runtime']['slice']:
                row=dict(CPUQuotaPerSecUSec='2s',TasksMax='64',AllowedCPUs='2-3',ActiveState='active')
                row.update(state.get('slice_patch',{}))
            elif name==broker_unit:
                row=dict(MainPID='200',Slice=config['runtime']['slice'],ActiveState='active')
                row.update(state.get('broker_patch',{}))
            else:raise AssertionError(command)
            text='\n'.join(k+'='+v for k,v in row.items())+'\n'
        return SimpleNamespace(returncode=0,stdout=text.encode(),stderr=b'')
    base=dict(units=[config['runtime']['manager_unit']],owner_exists=False,self_pid=300)
    positives=[];rejects=[]
    def reset(**changes):state.clear();state.update(base);state.update(changes)
    def reject(name,changes):
        reset(**changes)
        try:check(config)
        except (ValueError,RuntimeError):rejects.append(name)
        else:raise AssertionError('Accepted '+name)
    with patch('subprocess.run',run):
        reset();check(config);positives.append('manager plus pre-stage helper')
        reset(units=base['units']+[broker_unit],self_pid=200);check(config);positives.append('broker before OWNER publication')
        reset(units=base['units']+[broker_unit],owner_exists=True);check(config);positives.append('broker after OWNER publication')
        reject('foreign early MainPID',dict(units=base['units']+[broker_unit],self_pid=300))
        reject('unexpected active unit',dict(units=base['units']+['jp-other.service']))
        reject('manager memory envelope',dict(manager_patch={'LimitAS':'268435456'}))
        reject('manager wrong owner',dict(manager_patch={'MainPID':'101'}))
        reject('aggregate CPU removed',dict(slice_patch={'CPUQuotaPerSecUSec':'infinity'}))
        reject('aggregate task overflow',dict(slice_patch={'TasksMax':'65'}))
        reject('foreign broker slice',dict(units=base['units']+[broker_unit],owner_exists=True,broker_patch={'Slice':'app.slice'}))
        reject('stale published broker owner',dict(units=base['units']+[broker_unit],owner_exists=True,owner_pid=999))
    # Extract the actual new poll method without importing Linux-only manager code.
    source=(Path(__file__).parent/'field_runtime_manager_v1.py').read_bytes()
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Manager')
    poll=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='poll')
    scope=dict(time=time,Path=Path,strict=json.loads,ticks=lambda pid:None)
    exec(compile(ast.Module(body=[poll],type_ignores=[]),'<actual-manager-poll>','exec'),scope)
    class Pipe:
        def __init__(self):self.rows=[];self.closed=False
        def read(self,n):return self.rows.pop(0) if self.rows else None
        def close(self):self.closed=True
    stdout=Pipe();stderr=Pipe();writes=[];copies=[]
    process=SimpleNamespace(stdout=stdout,stderr=stderr,poll=lambda:0,wait=lambda timeout:0)
    journal=SimpleNamespace(_publish=lambda *args:writes.append(args),
        accept_local_backup=lambda *args:copies.append(args))
    instance=SimpleNamespace(proc=process,phase='copy',phase_start=time.monotonic(),stdout_eof=False,
        stderr_eof=False,buffer=b'',error_bytes=b'',child_owner=dict(pid=200,start_ticks=2000,boot_id=boot),
        result=None,helper_slot='launch-04',journal=journal,operation=dict(slot='recording-01'),
        refresh=lambda:None)
    scope['poll'](instance)
    assert not writes and not copies and instance.proc is process
    stdout.rows=[json.dumps(dict(type='RESULT',phase='copy',value=dict(fixture=True))).encode()+b'\n',b'']
    stderr.rows=[b'']
    scope['poll'](instance)
    assert len(writes)==1 and len(copies)==1 and stdout.closed and stderr.closed and instance.proc is None
    positives.append('process exit cannot precede complete stdout stderr EOF consumption')
    result=dict(status='PASS_CHANGED_RUNTIME_STARTUP_ORDERING_AND_EOF',positives=positives,rejects=rejects,
        native_executed=False,synthetic_native_owners_units_and_copy_callback=True,
        actual_extracted_functions=True,actual_project_graph_not_executed=True)
    raw=(json.dumps(result,indent=2)+'\n').encode()
    with (args.output/'RESULT.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    assert (args.output/'RESULT.json').read_bytes()==raw
    print(json.dumps(dict(status=result['status'],positives=len(positives),rejects=len(rejects))))


if __name__=='__main__':main()

