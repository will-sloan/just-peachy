"""Independent V3 snapshot review; README_S6C_DISPATCH_V3_COMPONENT_REVIEW.md."""
import argparse, ast, io, json, tempfile, types
from copy import deepcopy
from pathlib import Path
import s6c_paced_dispatch_v3 as D
import test_s6c_paced_dispatch_v3 as T

PIN='3815b657dd777fad3ca10a9bd7957a6fdaa4d1b5e6bf69a7be499764425bbbd2'

def run(output):
    output.mkdir(parents=True,exist_ok=False);checks=[]
    def ck(label,value):
        if not value:raise AssertionError(label)
        checks.append(label)
    ck('held_source_exact',D.binding(D.__file__)['sha256']==PIN)
    original=T.run(output/'reproduced_owner_checks');report=json.loads(Path(original['path']).read_bytes())
    ck('43_new_delta_checks_reproduced',report['checks']==43)
    ck('real_windows_prior_file_lock_reproduced',report['observations']['real_windows_read_lock']['new_snapshots_created_while_prior_locked']==2 and report['observations']['real_windows_read_lock']['prior_snapshot_unchanged'] is True)
    old=ast.parse((D.HERE/'s6c_paced_dispatch_v2.py').read_bytes());new=ast.parse(Path(D.__file__).read_bytes())
    oldrun=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    newrun=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    oldcall=next(n for n in ast.walk(oldrun) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='save' and any(k.arg=='replace' for k in n.keywords))
    changes=[]
    class Reverse(ast.NodeTransformer):
        def visit_Constant(self,n):
            if isinstance(n.value,str):n.value=n.value.replace('README_S6C_PACED_DISPATCH_V3.md','README_S6C_PACED_DISPATCH_V2.md')
            return n
        def visit_Assign(self,n):
            if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='heartbeat_sequence':
                ck('single_counter_zero',ast.unparse(n)=='heartbeat_sequence = 0');changes.append('init');return None
            return self.generic_visit(n)
        def visit_AugAssign(self,n):
            if isinstance(n.target,ast.Name) and n.target.id=='heartbeat_sequence':
                ck('increment_exactly_one',ast.unparse(n)=='heartbeat_sequence += 1');changes.append('increment');return None
            return self.generic_visit(n)
        def visit_Call(self,n):
            if isinstance(n.func,ast.Name) and n.func.id=='save_heartbeat':
                ck('identical_heartbeat_payload',len(n.args)==3 and ast.dump(n.args[1])==ast.dump(oldcall.args[1]) and ast.unparse(n.args[0])=='out' and ast.unparse(n.args[2])=='heartbeat_sequence' and not n.keywords)
                changes.append('call');return deepcopy(oldcall)
            return self.generic_visit(n)
    new.body=[n for n in new.body if not (isinstance(n,ast.FunctionDef) and n.name=='save_heartbeat') and not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('HEARTBEAT_SNAPSHOT_LIMIT','HEARTBEAT_SNAPSHOT_MAX_BYTES','HEARTBEAT_SNAPSHOT_BLOCK_SIZE') for t in n.targets))]
    restored=Reverse().visit(new)
    ck('whole_original_module_restored',ast.dump(restored)==ast.dump(old) and changes==['init','increment','call'])
    with tempfile.TemporaryDirectory(prefix='s6c_dispatch_v3_review_') as tmp:
        root=Path(tmp)
        overhead=len((json.dumps({'x':''},indent=2,allow_nan=False)+'\n').encode())
        exact={'x':'a'*(D.HEARTBEAT_SNAPSHOT_MAX_BYTES-overhead)}
        b=D.save_heartbeat(root/'size_boundary',exact,20000)
        ck('exact16KiB_and_final_sequence_accepted',b['bytes']==16384 and Path(b['path']).parent.name=='019')
        try:D.save_heartbeat(root/'too_large',{'x':exact['x']+'a'},1)
        except ValueError:ck('one_byte_over_cap_no_tree',not (root/'too_large').exists())
        else:raise AssertionError('Oversize accepted')
        ck('absolute_payload_bound_exact',D.HEARTBEAT_SNAPSHOT_LIMIT*D.HEARTBEAT_SNAPSHOT_MAX_BYTES==327680000)
        # Execute the unchanged actual dispatcher run code in private globals.
        # Admission, processes and completion are synthetic; no Popen occurs.
        ns=dict(D.__dict__);ns['REPORT']=root/'report';calls=[]
        fake_binding=lambda p,raw=None:dict(path=str(Path(p).resolve()),bytes=1,sha256='a'*64)
        items=[dict(item_id='first' if i==0 else 'second',helper=fake_binding(root/'helper.py'),manifest=fake_binding(root/('manifest'+str(i)+'.json')),output_root=str(root/('native'+str(i))),cells=1) for i in range(2)]
        q=dict(namespace='synthetic_only',items=items);a=dict(expires_utc='2026-09-13T11:35:40Z');plans=[dict(deadline_utc=a['expires_utc']) for _ in items]
        owner=dict(pid=98765,creation_time=123.5,argv=['synthetic'])
        child=types.SimpleNamespace(pid=98765,returncode=None,poll=lambda:None)
        def launch(*args):calls.append('launch');return child,owner,io.StringIO()
        def forbidden(*args):calls.append('completion');raise AssertionError('Failed heartbeat must not admit completion')
        ns.update(binding=fake_binding,read=lambda p,expected=None:({},expected or fake_binding(p)),admit=lambda qb,ab:(q,qb,a,ab,plans),launch=launch,completion=forbidden,state=lambda o:dict(alive=True,error=None),psutil=types.SimpleNamespace(Process=lambda:types.SimpleNamespace(pid=87654,create_time=lambda:100.,cmdline=lambda:['synthetic dispatcher'])))
        failure=OSError('Injected fsync failure after heartbeat bytes were written')
        def failing_sync(fd):raise failure
        hb_globals=dict(D.__dict__);hb_globals['os']=types.SimpleNamespace(fsync=failing_sync)
        ns['save_heartbeat']=types.FunctionType(D.save_heartbeat.__code__,hb_globals,'save_heartbeat')
        runner=types.FunctionType(D.run.__code__,ns,'run')
        try:runner(types.SimpleNamespace(queue=[str(root/'queue.json'),'a'*64],authority=[str(root/'authority.json'),'a'*64]))
        except OSError as exc:ck('actual_run_propagates_snapshot_storage_failure',exc is failure)
        else:raise AssertionError('Injected failure suppressed')
        out=root/'report/serial_paced_dispatcher/synthetic_only'
        result=json.loads((out/'RESULT.json').read_bytes());snapshot=json.loads((out/'heartbeats/000/HEARTBEAT_00001.json').read_bytes())
        ck('failed_snapshot_does_not_complete_or_launch_next_batch',calls==['launch'] and result['status']=='STOPPED_REQUIRES_ROOT_REVIEW' and result['completed_batches']==result['completed_cells']==0 and result['completed']==[])
        ck('possible_live_child_preserved',result['possible_child']==owner and result['possible_child_pid']==98765 and result['child_returncode'] is None and result['child_observation']['alive'] is True)
        ck('readable_but_unfsynced_snapshot_not_completion',snapshot['status']=='RUNNING' and snapshot['completed_batches']==0 and not (out/'first/BATCH_TRANSITION.json').exists() and not (out/'second').exists())
        ck('private_run_no_mutable_heartbeat',not (out/'HEARTBEAT.json').exists() and not (out/'HEARTBEAT.json.tmp').exists())
        ck('original_run_globals_unchanged',D.run.__globals__['launch'] is D.launch and D.run.__globals__['save_heartbeat'] is D.save_heartbeat)
    return D.save(output/'REVIEW_RECEIPT.json',dict(schema='s6c-dispatch-v3-independent-review.v1',status='PASS_NARROW_SOURCE_REVIEW',independent_checks=len(checks),names=checks,reproduced_checks=original,reproduced_check_count=43,sources=[D.binding(D.__file__),D.binding(D.HERE/'README_S6C_PACED_DISPATCH_V3.md'),D.binding(T.__file__),D.binding(__file__),D.binding(D.HERE/'README_S6C_DISPATCH_V3_COMPONENT_REVIEW.md')],actual_dispatcher_launches=0,models=0,scope='V2 baseline retained. Whole original module AST restored after reversing only declared snapshot/README delta. Private actual run-code fault injection proves no completion/next launch and retained possible live child on persistence failure. Only temporary fixture files/Windows handle used; no actual queue, runtime heartbeat, owner/lease/native/audio/model/census reads.'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
