"""Observer-only AST, tiny-guard and closed-subtree checks; README_S6C_FAST_OBSERVER_CHECKS_V1.md."""
from __future__ import annotations
import argparse
import ast
from copy import deepcopy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
import s6c_long_native_epoch4_fast_v1 as L
import s6c_paced_epoch4_fast_v1 as P
OLD={'s6c_long_native_epoch4.py':'9c15795253b17722af6b56e8bc3eb524ce68665bfa2d5de2d95ef940f690ea9b',
     's6c_paced_epoch4.py':'b4b0dc48190654edbdcb6259cf2b8abc08d8675d49367863ff539f7eb54df8a3'}
EPOCH_SHA='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945'
CHECKS=[]
def check(name,condition):
    if not condition:raise AssertionError(name)
    CHECKS.append(name)
def reject(name,call,types=(ValueError,RuntimeError,PermissionError)):
    try:call()
    except types:check(name,True);return
    raise AssertionError(name+' was accepted')

def frozen_common():
    epoch,eb=L.read_bound(L.REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
    check('exact epoch4 metadata',eb['sha256']==EPOCH_SHA)
    matches=[b for b in epoch['execution_files'] if Path(b['path']).name=='s6c_common.py']
    check('one exact frozen common',len(matches)==1 and matches[0]['sha256']==L.PINS['s6c_common.py'])
    L.verify(matches[0])
    existing=os.environ.get('JP_S6C_SIM')
    if existing and Path(existing).resolve()!=L.SIM.resolve():raise ValueError('Conflicting SIM environment')
    os.environ['JP_S6C_SIM']=str(L.SIM)
    spec=importlib.util.spec_from_file_location('s6c_common',matches[0]['path'])
    module=importlib.util.module_from_spec(spec);sys.modules['s6c_common']=module;spec.loader.exec_module(module)
    return module,eb

def runtime_checks():
    common,eb=frozen_common();original=common.tree_bytes
    reject('installation requires explicit scope',lambda:L.install_observer_scanner(common))
    with tempfile.TemporaryDirectory(prefix='s6c_observer_only_') as temporary:
        root=Path(temporary);(root/'a').write_bytes(b'a'*7)
        with L.observer_scope() as records:
            L.install_observer_scanner(common);fast=common.tree_bytes
            check('same admitted resource globals',common.resources.__globals__['tree_bytes'] is fast and common.admit_work.__globals__ is common.__dict__)
            check('installed callable reads current tree',fast(root)==7)
            (root/'b').write_bytes(b'b'*5);check('next call sees new file',fast(root)==12)
            with L.observer_scope() as nested:
                L.install_observer_scanner(common);check('nested installation does not duplicate replacement',not nested and common.tree_bytes is fast)
            check('nested exit retains outer scanner',common.tree_bytes is fast)
        check('normal scanner restoration',common.tree_bytes is original and records[0]['restored'] and records[0]['protected_admission_unchanged'])
        try:
            with L.observer_scope() as exceptional:
                L.install_observer_scanner(common);raise LookupError('injected')
        except LookupError:pass
        check('exception scanner restoration',common.tree_bytes is original and exceptional[0]['restored'])
        with patch.object(common,'REPORT',root):
            with L.observer_scope():reject('wrong resource root rejected',lambda:L.install_observer_scanner(common))
        with patch.object(L,'FAST_SCAN_SHA','0'*64):
            reject('changed scanner source pin rejected',L.observer_policy)
        with patch.object(L,'FAST_SCAN_README_SHA','0'*64):
            reject('changed scanner README pin rejected',L.observer_policy)
        with patch.object(common,'__file__',str(SCRIPTS/'s6c_admission_fast_v1.py')):
            with L.observer_scope():reject('wrong common source rejected',lambda:L.install_observer_scanner(common))
        with patch.object(common,'resources',lambda:None):
            with L.observer_scope():reject('foreign resources globals rejected',lambda:L.install_observer_scanner(common))
        with patch.dict(sys.modules,{'s6c_common':object()}):
            reject('wrong common import identity rejected',lambda:L.load_observer_scanner(common))
        with patch.object(common,'tree_bytes',lambda path:0):
            with L.observer_scope():reject('foreign original scanner rejected',lambda:L.install_observer_scanner(common))
        try:
            with L.observer_scope() as tampered:
                L.install_observer_scanner(common);common.tree_bytes=lambda p:0
        except RuntimeError:pass
        else:raise AssertionError('mutated installation not rejected')
        check('tampered scanner still restored',common.tree_bytes is original and tampered[0]['restored'])
        calls=[]
        @L.observer_entry
        def tiny_entry():
            L.install_observer_scanner(common);check('decorated entry installed',common.tree_bytes is not original)
            return {'tiny':True}
        with patch.object(L,'write_observer_record',side_effect=lambda fn,args,result,records,error:calls.append((result,deepcopy([r.get('restored') for r in records]),error))):
            value=tiny_entry()
        check('entry records after restoration',value=={'tiny':True} and calls==[({'tiny':True},[True],None)] and common.tree_bytes is original)
        @L.observer_entry
        def failed_entry():
            L.install_observer_scanner(common);raise LookupError('injected entry error')
        with patch.object(L,'write_observer_record',side_effect=lambda fn,args,result,records,error:calls.append((result,[r.get('restored') for r in records],error))):
            try:failed_entry()
            except LookupError:pass
            else:raise AssertionError('entry error lost')
        check('failed entry restoration is separate from native outcome',common.tree_bytes is original and calls[-1][0] is None and calls[-1][1]==[True] and 'LookupError' in calls[-1][2])
        fast=L.load_observer_scanner(common)
        with patch.object(fast.os,'scandir',side_effect=PermissionError('injected')):
            reject('unreadable scan fails closed',lambda:fast.tree_bytes(root))
    check('original common callable retained after all guards',common.tree_bytes is original)
    return common,eb

def normalized(node):
    node=deepcopy(node)
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
        node.decorator_list=[d for d in node.decorator_list if ast.unparse(d) not in ('observer_entry','L.observer_entry')]
    return ast.dump(node,include_attributes=False)

def timer_normalized(node,kind):
    node=deepcopy(node);replaced=0
    for part in ast.walk(node):
        if isinstance(part,ast.Assign) and len(part.targets)==1 and isinstance(part.targets[0],ast.Name) and part.targets[0].id=='last_full':
            text=ast.unparse(part.value)
            expected='time.monotonic()' if kind=='long' else 'time.monotonic() - cell_started'
            if text==expected:
                part.value=ast.Name(id='now' if kind=='long' else 'elapsed',ctx=ast.Load());replaced+=1
    check('one authorized completion timer '+kind,replaced==1)
    return normalized(node)

def timer_checks():
    from types import SimpleNamespace
    for path,kind in ((SCRIPTS/'s6c_long_native_epoch4_fast_v1.py','long'),(SCRIPTS/'s6c_paced_epoch4_fast_v1.py','paced')):
        tree=ast.parse(path.read_text(encoding='utf-8-sig'));run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        expected='time.monotonic()' if kind=='long' else 'time.monotonic() - cell_started'
        assignment=next(n for n in ast.walk(run) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='last_full' and ast.unparse(n.value)==expected)
        env=dict(time=SimpleNamespace(monotonic=lambda:60.),cell_started=0.,now=20.,elapsed=20.)
        exec(compile(ast.Module(body=[assignment],type_ignores=[]),str(path),'exec'),env)
        check('timer uses actual scan finish '+kind,env['last_full']==60.)
        if kind=='long':
            due=next(n.value for n in ast.walk(run) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='full' for t in n.targets) and 'last_full' in ast.unparse(n.value))
        else:
            due=next(n.test for n in ast.walk(run) if isinstance(n,ast.If) and ast.unparse(n.test)=='elapsed - last_full >= 20')
        for current,wanted in ((60.,False),(79.999,False),(80.,True)):
            env.update(now=current,elapsed=current,full=False)
            check('20s completion interval '+kind+':'+str(current),eval(compile(ast.Expression(due),str(path),'eval'),env) is wanted)
        if kind=='long':
            env.update(now=60.,full=True)
            check('mandatory long full scan remains immediate',eval(compile(ast.Expression(due),str(path),'eval'),env) is True)

def ast_report():
    report=[]
    allowed={
      's6c_long_native_epoch4.py':{'output_roots','worker_command','load_sources','validate_plan','prepare','admit','run','checks','source_checks'},
      's6c_paced_epoch4.py':{'source_bindings','load_native','namespace_roots','prepare','admit','run','source_checks'}}
    for oldname,sha in OLD.items():
        oldpath=SCRIPTS/oldname;newpath=SCRIPTS/oldname.replace('.py','_fast_v1.py')
        check('original source preserved '+oldname,L.bind(oldpath)['sha256']==sha)
        before=ast.parse(oldpath.read_text(encoding='utf-8-sig'));after=ast.parse(newpath.read_text(encoding='utf-8-sig'))
        oldf={n.name:n for n in before.body if isinstance(n,ast.FunctionDef)}
        newf={n.name:n for n in after.body if isinstance(n,ast.FunctionDef)}
        check('all original function names preserved '+oldname,set(oldf)<=set(newf))
        equal=[];changed=[]
        for name,node in oldf.items():
            if normalized(node)==normalized(newf[name]):equal.append(name)
            else:
                check('declared observer/source-only changed function '+oldname+':'+name,name in allowed[oldname])
                changed.append(dict(function=name,before=ast.unparse(node),after=ast.unparse(newf[name])))
        for name in ('run',):
            check('original native caller body except one authorized timer '+oldname+':'+name,normalized(oldf[name])==timer_normalized(newf[name],'paced' if oldname=='s6c_paced_epoch4.py' else 'long'))
        if oldname=='s6c_paced_epoch4.py':
            check('exact original fresh native worker body',normalized(oldf['worker'])==normalized(newf['worker']))
            check('fresh worker uses explicit current script argv',"str(Path(__file__).resolve())" in ast.unparse(newf['run']))
            entries=('prepare','run','worker','source_checks')
            for name in entries:check('canonical explicit entry decorator '+name,any(ast.unparse(x)=='L.observer_entry' for x in newf[name].decorator_list))
            check('canonical load installs scanner in each process',any(isinstance(n,ast.Call) and ast.unparse(n.func)=='L.install_observer_scanner' for n in ast.walk(newf['load_native'])))
        else:
            for name in ('prepare','run','source_checks'):check('continuous explicit entry decorator '+name,any(ast.unparse(x)=='observer_entry' for x in newf[name].decorator_list))
        report.append(dict(original=L.bind(oldpath),new=L.bind(newpath),exact_functions=equal,changed_functions=changed,added_functions=sorted(set(newf)-set(oldf))))
    # Constant statement values remain exact except explicitly admitted utility import/source/README pins.
    check('canonical schema and limits unchanged',P.SCHEMA=='s6c-canonical-paired-paced.v1' and P.MAX_RUN_SEC==28800 and P.CELL_RESERVE==512*2**20)
    check('continuous limits unchanged',L.MAX_WALL_SEC==7200 and L.PENDING_BYTES==4*2**30 and L.ALLOWED_OVERRIDES==('load_composition','admit_work','process_sample'))
    check('fresh canonical namespace same directory family',P.namespace_roots('test_fast_v1')==(L.REPORT/'paced_candidates/test_fast_v1',L.PAYLOAD/'paced_candidates/test_fast_v1'))
    check('fresh continuous namespace same directory family',L.output_roots('epoch4_test_fast_v1')==(L.REPORT/'long_session/epoch4_test_fast_v1',L.PAYLOAD/'long_session/epoch4_test_fast_v1'))
    reject('old canonical namespace rejected',lambda:P.namespace_roots('old_v1'))
    reject('old continuous namespace rejected',lambda:L.output_roots('epoch4_old_v1'))
    for name in ('s6c_paced_epoch4_fast_v1.py','s6c_long_native_epoch4_fast_v1.py','s6c_paced_controls_fast_v1.py','s6c_paced_b36_fast_v1.py','s6c_long_b36_fast_v1.py'):
        check('new active argv recognized '+name,L.worker_command(['python.exe',name,'run']))
    return report

def closed_subtrees(common):
    fast=L.load_observer_scanner(common);result=[]
    for relative in ('independent_review/full_n12_component_v1','enrollment/common30_v1'):
        root=L.REPORT/relative
        check('closed subtree exists '+relative,root.is_dir())
        # Metadata only: no file content, raw PCM, model or native event is read.
        before=fast.scan_details(root);old=common.tree_bytes(root);after=fast.scan_details(root)
        check('closed subtree enumerated byte parity '+relative,before==after and old==before['bytes'])
        result.append(dict(path=str(root),original_bytes=old,fast_before=before,fast_after=after,scope='Already closed bounded directory metadata; not a full current namespace benchmark.'))
    return result

def main(args):
    if args.child:
        runtime_checks()
        print(json.dumps(dict(status='PASS_FRESH_PROCESS_OBSERVER_ONLY',checks=len(CHECKS),native_calls=0,model_calls=0)))
        return
    target=L.REPORT/'observer_fast_v1/SOURCE_CHECKS_V1.json'
    if target.exists():raise ValueError('Fresh source-check receipt required; preserve prior result')
    inherited_long=L.checks();inherited_paced=P.checks();report=ast_report();timer_checks();common,eb=runtime_checks();subtrees=closed_subtrees(common)
    child=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child'],capture_output=True,text=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    check('fresh observer process exited cleanly',child.returncode==0)
    child_result=json.loads(child.stdout);check('fresh observer process has no native calls',child_result['status']=='PASS_FRESH_PROCESS_OBSERVER_ONLY' and child_result['native_calls']==child_result['model_calls']==0)
    earlier=[]
    for relative,sha in (
        ('historical_fast_observers/HARDLINK_ENUMERATION_DIAGNOSIS_V1.json','9911828260d154109b1ca6191ada66aea53691ad828be646adfe8e27b887531c'),
        ('historical_fast_observers/FRESH_STAT_BENCHMARK_V1.json','30c1c2771f79ba55e50fc5cfc8e18c26db1da8a6123491da26af94cf300e2e71'),
        ('historical_fast_observers/SCANNER_AST_CONTINUITY_V1.json','39236b171feccf80120ace7280c877d680d89a6e79e6bdb94604080691981184'),
        ('historical_fast_observers/CHECKS_CONTROLS_V3.json','1490036aeacf81481f84cfd636264b870b456110e1d809a0008cdfed8c4c24e2')):
        b=L.bind(L.REPORT/relative);check('exact shared scanner evidence '+relative,b['sha256']==sha);earlier.append(b)
    preserved=[L.bind(L.STAGING/'observer_fast_v1'/name/'SOURCE_INDEX.json') for name in ('before_hardlink_stat_repair','before_scan_completion_timer')]
    for name,sha in OLD.items():check('original source still unchanged '+name,L.bind(SCRIPTS/name)['sha256']==sha)
    output=dict(schema='s6c.fast_observer_source_checks.v1',status='PASS_SOURCE_AND_TINY_GUARDS',created_utc=L.utc(),checks=CHECKS,check_count=len(CHECKS),
        inherited_long=inherited_long,inherited_canonical=inherited_paced,fresh_process=child_result,
        ast_delta=report,closed_subtrees=subtrees,epoch=eb,scanner_policy=L.observer_policy(),prior_reviewed_scanner_evidence=earlier,preserved_drafts=preserved,
        sources=[L.bind(SCRIPTS/name) for name in ('s6c_long_native_epoch4_fast_v1.py','README_S6C_LONG_NATIVE_EPOCH4_FAST_V1.md','s6c_paced_epoch4_fast_v1.py','README_S6C_PACED_EPOCH4_FAST_V1.md','test_s6c_fast_observer_v1.py','README_S6C_FAST_OBSERVER_CHECKS_V1.md')],
        model_calls=0,native_calls=0,actual_paced_cells=0,actual_long_sessions=0,
        scope='Original run bodies differ only by entry decorator and authorized completion-to-next-start periodic timer; original worker body exact. Tiny fixtures, actual frozen common import and two closed metadata subtrees only. No full original namespace scan, models, actual PCM, native logs, real preparation or execution.')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(output,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=output['status'],checks=len(CHECKS),receipt=L.bind(target)),indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);parser.add_argument('--child',action='store_true');main(parser.parse_args())
