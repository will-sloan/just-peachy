"""Independent recovery ownership/aggregate wiring probes; see companion README."""
import argparse
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def chain():
    ids=dict(run_id=H.RUN,job_id='J',child_run_id='child')
    argv=['C:/fixture/venv/Scripts/python.exe','C:/fixture/recovery.py','--recovery-plan','P','--authorization','A']
    launch=dict(ids,pid=10,creation_time=100.,argv=argv,launch_state='LAUNCHED')
    worker=dict(pid=11,parent_pid=10,creation_time=100.04,executable='C:/fixture/base/python.exe',argv=['C:/fixture/base/python.exe']+argv[1:])
    launcher=dict(pid=10,parent_pid=9,creation_time=100.,executable=argv[0],argv=argv)
    supervisor=dict(pid=9,parent_pid=8,creation_time=90.,executable='C:/fixture/base/python.exe',argv=['runner.py'])
    contract=dict(argv=argv,launcher=dict(path=argv[0]),worker_executable=dict(path=worker['executable']),supervisor_creation_time=90.)
    return deepcopy((launch,worker,launcher,supervisor,contract,ids))


class Tests(unittest.TestCase):
    def test_realistic_declared_chain_positive_control(self):
        out=H.validate_chain(*chain());self.assertEqual((out['pid'],out['worker_identity']['pid']),(10,11))

    def test_nonfinite_launch_creation_rejected(self):
        for value in (float('nan'),float('inf')):
            args=chain();args[0]['creation_time']=value
            with self.subTest(value=str(value)),self.assertRaises(ValueError):H.validate_chain(*args)

    def test_nonfinite_contract_supervisor_creation_rejected(self):
        args=chain();args[4]['supervisor_creation_time']=float('nan')
        with self.assertRaises(ValueError):H.validate_chain(*args)

    def owner(self):
        launch,worker,launcher,supervisor,contract,ids=chain();o=H.Ownership.__new__(H.Ownership)
        o.launch=launch;o.worker=worker;o.launcher=launcher;o.supervisor=supervisor;o.chain_contract=contract;o.ids=ids
        o.launch_binding={};o.m=SimpleNamespace(verify=lambda b:None);o.last_check=0.
        return o,{x['pid']:x for x in (worker,launcher,supervisor)}

    def test_worker_pid_reuse_rejected_during_health(self):
        owner,rows=self.owner();rows=deepcopy(rows);rows[11]['creation_time']+=1
        with patch.object(H,'process_snapshot',lambda pid:rows[pid]),self.assertRaisesRegex(ValueError,'PID was reused'):owner.check(force=True)

    def test_launcher_exit_fails_closed_without_descendant_search(self):
        owner,rows=self.owner();calls=[]
        def snapshot(pid):
            calls.append(pid)
            if pid==10:raise H.psutil.NoSuchProcess(pid)
            return rows[pid]
        with patch.object(H,'process_snapshot',snapshot),self.assertRaises(H.psutil.NoSuchProcess):owner.check(force=True)
        self.assertEqual(calls,[11,10])

    def test_exact_original_aggregate_api_arguments_reused(self):
        def calls(path):
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            body=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
            names={'tables','dependency_plan','paired_comparisons','paired_adverse','cp_uncertainty'};found={}
            for node in ast.walk(body):
                if not isinstance(node,ast.Call):continue
                name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
                if name in names:
                    signature=ast.dump(ast.Tuple(elts=node.args+[ast.Tuple(elts=[ast.Constant(k.arg),k.value],ctx=ast.Load()) for k in node.keywords],ctx=ast.Load()),include_attributes=False)
                    found.setdefault(name,[]).append(signature)
            return found
        original=calls(ADAPTER);recovery=calls(HELPER)
        self.assertEqual(set(original),{'tables','dependency_plan','paired_comparisons','paired_adverse','cp_uncertainty'})
        self.assertEqual(recovery,original)

    def test_no_new_analyze_or_original_execute_invocation(self):
        tree=ast.parse(HELPER.read_text(encoding='utf-8-sig'))
        forbidden=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {'analyze','execute','run','registered_candidates'}:
                forbidden.append(ast.unparse(node.func))
        self.assertEqual(forbidden,[])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--helper',type=Path,required=True);p.add_argument('--adapter',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();HELPER=a.helper.resolve();ADAPTER=a.adapter.resolve();OUT=a.output.resolve()
    if OUT.drive.upper()!='G:':raise ValueError('Fresh G output required')
    OUT.mkdir(parents=True,exist_ok=False);H=load(HELPER,'independent_recovery')
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    import hashlib
    def bind(path):
        p=Path(path).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    receipt=dict(status='PASS' if r.wasSuccessful() else 'CHANGES_REQUIRED',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),helper=bind(HELPER),adapter=bind(ADAPTER),fixture=bind(__file__),log=bind(OUT/'TESTS.log'),process_launches=0,scorer_calls=0,models=0,ui_calls=0,devices=0)
    (OUT/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt));raise SystemExit(not r.wasSuccessful())
