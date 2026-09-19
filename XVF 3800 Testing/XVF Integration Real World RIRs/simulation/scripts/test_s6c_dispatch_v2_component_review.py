"""Independent heartbeat delta review; README_S6C_DISPATCH_V2_COMPONENT_REVIEW.md."""
import argparse, ast, hashlib, json, tempfile, types
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import s6c_paced_dispatch_v2 as D
import test_s6c_paced_dispatch_v2 as T

SHA='a327cd602c043acbeec3b08857ed0b257f96126e5e0f184ddd40c6c1b5ce3251'

def run(output):
    output.mkdir(parents=True,exist_ok=False);checks=[]
    def ck(label,value):
        if not value:raise AssertionError(label)
        checks.append(label)
    ck('exact_held_production_source',D.binding(D.__file__)['sha256']==SHA)
    owner=T.run(output/'reproduced_owner_checks');owner_doc=json.loads(Path(owner['path']).read_bytes())
    ck('all31_owner_checks_reproduced',owner_doc['checks']==31 and owner_doc['status']=='PASS_SOURCE_AND_PRIVATE_FIXTURES_ONLY')
    # Independent whole-module oracle: reverse the exact one retry branch,
    # remove the four newly introduced definitions, normalize README only.
    old=ast.parse((D.HERE/'s6c_paced_dispatch_v1.py').read_bytes());new=ast.parse(Path(D.__file__).read_bytes())
    save=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='save')
    branch=next(n for n in save.body if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='replace')
    conditional=branch.body[-1]
    ck('exact_heartbeat_only_branch',isinstance(conditional,ast.If) and ast.unparse(conditional.test)=="p.name == 'HEARTBEAT.json'" and ast.unparse(conditional.body[0])=='replace_heartbeat(t, p)' and ast.unparse(conditional.orelse[0])=='os.replace(t, p)')
    branch.body[-1]=conditional.orelse[0]
    new.body=[n for n in new.body if not (isinstance(n,ast.FunctionDef) and n.name=='replace_heartbeat') and not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('HEARTBEAT_REPLACE_RETRY_SEC','HEARTBEAT_REPLACE_RETRY_INTERVAL_SEC','HEARTBEAT_REPLACE_MAX_ATTEMPTS') for t in n.targets))]
    class Text(ast.NodeTransformer):
        def visit_Constant(self,n):
            if isinstance(n.value,str):n.value=n.value.replace('README_S6C_PACED_DISPATCH_V2.md','README_S6C_PACED_DISPATCH_V1.md')
            return n
    ck('entire_original_module_ast_restored',ast.dump(Text().visit(new))==ast.dump(old))
    # Private globals avoid touching real os/time or original module objects.
    with tempfile.TemporaryDirectory(prefix='s6c_dispatch_review_') as tmp:
        root=Path(tmp);target=root/'HEARTBEAT.json';temporary=root/'HEARTBEAT.json.tmp'
        real_replace=D.os.replace;clock=[0.];attempts=[];waits=[];errors=[]
        value={'sequence':1};expected=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
        def replacement(a,b):
            attempts.append((a,b,a.read_bytes(),target.read_bytes()))
            if len(attempts)==1:
                value['sequence']=999
                exc=PermissionError('first transient');exc.winerror=5;errors.append(exc);raise exc
            real_replace(a,b)
        def sleep(n):waits.append(n);clock[0]+=n
        ns=dict(D.__dict__);ns['os']=types.SimpleNamespace(replace=replacement,fsync=D.os.fsync)
        ns['time']=types.SimpleNamespace(monotonic=lambda:clock[0],sleep=sleep)
        for name in ('replace_heartbeat','save'):
            f=getattr(D,name);ns[name]=types.FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)
        target.write_bytes(b'old complete heartbeat');b=ns['save'](target,value,replace=True)
        ck('serialized_payload_unchanged_when_input_mutates_between_attempts',len(attempts)==2 and all(x[2]==expected for x in attempts) and target.read_bytes()==expected and b['sha256']==hashlib.sha256(expected).hexdigest())
        ck('target_stays_old_until_atomic_success',all(x[3]==b'old complete heartbeat' for x in attempts) and not temporary.exists() and waits==[.05])
        # A late retry switches to a permanent failure: propagate exactly that
        # failure immediately, preserving the old target and original tmp.
        target.write_bytes(b'old');attempts.clear();waits.clear();clock[0]=0.;value={'sequence':1}
        permanent=OSError('disk full');permanent.winerror=112
        def mixed(a,b):
            attempts.append((a,b))
            if len(attempts)==1:raise errors[0]
            raise permanent
        ns['os'].replace=mixed
        try:ns['save'](target,value,replace=True)
        except OSError as exc:ck('permanent_after_transient_propagates_exactly',exc is permanent and len(attempts)==2 and waits==[.05] and target.read_bytes()==b'old' and temporary.read_bytes()==expected)
        else:raise AssertionError('Permanent error swallowed')
        temporary.unlink();attempts.clear();waits.clear();clock[0]=0.
        def deadline_fail(a,b):
            attempts.append((a,b));clock[0]=1.99;raise errors[0]
        ns['os'].replace=deadline_fail
        try:ns['save'](target,value,replace=True)
        except PermissionError as exc:ck('deadline_does_not_start_another_attempt',exc is errors[0] and len(attempts)==1 and len(waits)==1 and abs(waits[0]-.01)<1e-12 and clock[0]==2.)
        else:raise AssertionError('Deadline swallowed')
        ck('private_global_injection_never_changes_os_replace',D.os.replace is real_replace)
    return D.save(output/'REVIEW_RECEIPT.json',dict(schema='s6c-dispatch-v2-independent-review.v1',status='PASS_NARROW_SOURCE_REVIEW',independent_checks=len(checks),names=checks,reproduced_owner_checks=owner,owner_check_count=31,sources=[D.binding(D.__file__),D.binding(D.HERE/'README_S6C_PACED_DISPATCH_V2.md'),D.binding(T.__file__),D.binding(__file__),D.binding(D.HERE/'README_S6C_DISPATCH_V2_COMPONENT_REVIEW.md')],models=0,dispatcher_runs=0,scope='Exact original whole-module AST restored after removing only declared heartbeat retry and README delta. Private tiny files/fakes plus one reproduced private Windows sharing-handle test; no current heartbeat/coordinator/lease/queue/native or scientific reads. Bounded retry is not a guarantee of recovery from permanent access denial. Root must resolve original live coordinator before any new queue.'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
