"""Focused, no-model startup checks; run only through run_host_xvf_fresh_start.py.

See README_XVF_FRESH_START.md for scope, inputs, receipts and prompt commands.
"""
import ast
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

HERE = Path(__file__).resolve().parent
BASE = Path(os.environ['JP_XVF_TEST_BASE'])
registration = Path(os.environ['JP_XVF_REGISTERED_OWNER'])
if not registration.is_file():
    raise RuntimeError('Registered host owner must precede fixture reads')
PIN = 'fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802'
if hashlib.sha256((BASE/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest() != PIN:
    raise ValueError('Exact immutable build34 fixture input required')
PINS = {
    'launcher.py': '9fcab95b695519161ea27a1400c8219a215edc1443eedb68f8cad0a1464c0df7',
    'xvf_readiness_helper.py': 'c3cf8219f7e751c5c1bb4c6fefb0297f69e9c612cf60d72948871015844ae0fa',
    'xvf_readiness.py': '81db0f81b95dbf76529c2c73f8c7b36b3afef7f9631b2656bfbf74f8eb267010',
}
for name, pin in PINS.items():
    if hashlib.sha256((BASE/name).read_bytes()).hexdigest() != pin:
        raise ValueError('Exact pinned startup source required: '+name)
OLD = {name: ast.parse((BASE/name).read_bytes()) for name in PINS}
NEW = {name: ast.parse((HERE/name).read_bytes()) for name in ('launcher.py', 'xvf_readiness_helper.py')}


def tree(value):
    return ast.dump(value, include_attributes=False)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def member(module, name, kind=ast.FunctionDef):
    return next(node for node in module.body if isinstance(node, kind) and node.name == name)


class SourceProof(unittest.TestCase):
    def test_launcher_exact_reverse_one_historical_block(self):
        old = OLD['launcher.py']; restored = deepcopy(NEW['launcher.py'])
        old_start = member(member(old, 'Manager', ast.ClassDef), 'start')
        new_start = member(member(restored, 'Manager', ast.ClassDef), 'start')
        old_gate = next(node for node in old_start.body if isinstance(node, ast.If)
                        and tree(node.test) == tree(ast.parse('not self._resuming_start', mode='eval').body))
        new_gate = next(node for node in new_start.body if isinstance(node, ast.If)
                        and tree(node.test) == tree(old_gate.test))
        historical = ast.parse("if selection.input_source == 'live':\n previous = self._previous_readiness_fault()\n if previous is not None:\n  self._begin_readiness(previous)\n  return\n").body[0]
        self.assertEqual(tree(old_gate.body[-1]), tree(historical))
        self.assertEqual([tree(node) for node in old_gate.body[:-1]], [tree(node) for node in new_gate.body])
        new_gate.body.append(deepcopy(old_gate.body[-1]))
        self.assertEqual(tree(restored), tree(old))

    def test_helper_exact_reverse_only_modern_receipt_admission(self):
        old = OLD['xvf_readiness_helper.py']; restored = deepcopy(NEW['xvf_readiness_helper.py'])
        original = member(old, 'unit_checks'); changed = member(restored, 'unit_checks')
        region = ast.parse("""extra = {'address_space', 'stack', 'qualification_kind', 'recording_model_scope'}
modern_gui = set(receipt) == keys | extra
if modern_gui:
    for name in ('address_space', 'stack'):
        value = receipt[name]
        if type(value) is not list or len(value) != 2 or any(type(item) is not int for item in value):
            raise ValueError('Exact actual integer model resource pairs required')
    if (receipt['address_space'] != [1024**3, 1024**3]
            or receipt['stack'] != [1024**2, 1024**2]
            or receipt['qualification_kind'] != 'gui'
            or receipt['recording_model_scope'] is not True
            or re.fullmatch(r'jp-v29-classic-ui-check-[0-9]{2}\\.service', request['unit']) is None):
        raise ValueError('Extended readiness scope is limited to the exact modern GUI envelope')
""").body
        begin = next(index for index, node in enumerate(changed.body)
                     if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                     and node.targets[0].id == 'extra')
        self.assertEqual([tree(node) for node in changed.body[begin:begin+3]], [tree(node) for node in region])
        del changed.body[begin:begin+3]
        finite = next(node for node in ast.walk(changed) if isinstance(node, ast.Assign)
                      and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'finite_schema')
        old_finite = next(node for node in ast.walk(original) if isinstance(node, ast.Assign)
                          and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'finite_schema')
        self.assertIsInstance(finite.value, ast.BoolOp)
        self.assertEqual(tree(finite.value.values[0]), tree(ast.Name(id='modern_gui', ctx=ast.Load())))
        self.assertEqual([tree(node) for node in finite.value.values[1:]], [tree(node) for node in old_finite.value.values])
        finite.value = deepcopy(old_finite.value)
        self.assertEqual(tree(restored), tree(old))

    def test_fault_sequence_and_single_send_code_unchanged(self):
        self.assertEqual(hashlib.sha256((BASE/'xvf_readiness.py').read_bytes()).hexdigest(), PINS['xvf_readiness.py'])
        self.assertFalse((HERE/'xvf_readiness.py').exists())
        original_main = member(OLD['xvf_readiness_helper.py'], 'native_main')
        self.assertEqual(tree(original_main), tree(member(NEW['xvf_readiness_helper.py'], 'native_main')))
        self.assertIn('maintenance_sends_attempted', ast.unparse(original_main))
        # This is source preservation, not a simulated firmware-reset quality claim.


OWNER = dict(pid=21, start_ticks=4, boot_id='00000000-0000-0000-0000-000000000000')
GROUP = '/user.slice/user-1000.slice/user@1000.service/app.slice/jp-v29-classic-ui-check-53.service'


class UnitChecks(unittest.TestCase):
    def setUp(self):
        self.receipt = dict(unit='jp-v29-classic-ui-check-53.service', owner=deepcopy(OWNER), main_pid=21,
                            invocation_id='a'*32, control_group=GROUP, runtime_max_seconds=600,
                            deadline_monotonic=200, idle_timeout_seconds=300)
        self.props = dict(MainPID='21', InvocationID='a'*32, ControlGroup=GROUP, ActiveState='active',
                          AllowedCPUs='2-3', CPUQuotaPerSecUSec='2s', TasksMax='64', RuntimeMaxUSec='10min')
        self.closed = False; self.pids = '21 '+str(os.getpid()); self.actual_group = GROUP
        self.calls = []
        test = self
        class VirtualPath:
            def __init__(self, path): self.path = path
            def __truediv__(self, child): return VirtualPath(self.path+'/'+child)
            def read_text(self):
                if self.path == '/proc/self/cgroup': return '0::'+test.actual_group+'\n'
                if self.path == '/sys/fs/cgroup'+GROUP+'/cgroup.procs': return test.pids
                raise AssertionError('Unexpected native-path fixture read')
        def shown(argv, **kwargs):
            self.calls.append((argv, kwargs))
            return SimpleNamespace(stdout='\n'.join(key+'='+value for key, value in self.props.items()))
        self.namespace = dict(bounded=lambda path: encode(self.receipt), strict=json.loads,
                              hashlib=hashlib, re=re, math=math, os=os, Path=VirtualPath,
                              owner_closed=lambda owner: self.closed or owner != OWNER,
                              time=SimpleNamespace(monotonic=lambda:100), subprocess=SimpleNamespace(run=shown))
        code = ast.Module(body=[deepcopy(member(NEW['xvf_readiness_helper.py'], 'unit_checks'))], type_ignores=[])
        exec(compile(ast.fix_missing_locations(code), '<actual35-unit-check>', 'exec'), self.namespace)

    def run_check(self):
        return self.namespace['unit_checks'](dict(unit_ownership='fixture-only',
            unit_ownership_sha256=hashlib.sha256(encode(self.receipt)).hexdigest(),
            unit=self.receipt['unit'], manager_owner=deepcopy(OWNER)))

    def modern(self):
        self.receipt.update(address_space=[1024**3,1024**3], stack=[1024**2,1024**2],
                            qualification_kind='gui', recording_model_scope=True)

    def test_legacy_finite(self):
        self.assertEqual(self.run_check(), self.props)
        self.assertEqual(self.calls[0][0][:4], ['systemctl','--user','show',self.receipt['unit']])
        self.assertEqual(self.calls[0][1]['timeout'], 3)

    def test_legacy_finite_lifetime_tag(self):
        self.receipt['lifetime_policy'] = 'finite_qualification'
        self.assertEqual(self.run_check(), self.props)

    def test_legacy_manual_strict(self):
        self.receipt.update(lifetime_policy='manual_stop_storage_guarded', runtime_max_seconds=None,
                            deadline_monotonic=None)
        self.props['RuntimeMaxUSec'] = 'infinity'
        self.assertEqual(self.run_check(), self.props)
        for key, value in (('idle_timeout_seconds',True), ('deadline_monotonic',200),
                           ('runtime_max_seconds',600), ('unknown',1)):
            original = deepcopy(self.receipt)
            self.receipt[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.run_check()
            self.receipt = original

    def test_exact_modern_gui(self):
        self.modern()
        self.assertEqual(self.run_check(), self.props)

    def test_modern_resource_types_and_actual_pairs(self):
        self.modern(); original = deepcopy(self.receipt)
        for key, value in (('address_space',[True,1024**3]), ('address_space',[1024.0**3,1024**3]),
                           ('address_space',(1024**3,1024**3)), ('address_space',[768*1024**2]*2),
                           ('address_space',[1024**3,2*1024**3]), ('stack',[1024**2,2*1024**2])):
            self.receipt = deepcopy(original); self.receipt[key] = value
            # Encode tuples as JSON arrays; direct shape is tested via the decoded receipt below.
            if type(value) is tuple:
                self.namespace['strict'] = lambda raw: dict(json.loads(raw), address_space=value)
            with self.subTest(key=key,value=value), self.assertRaises(ValueError): self.run_check()
            self.namespace['strict'] = json.loads

    def test_modern_scope_and_exact_fields(self):
        self.modern(); original = deepcopy(self.receipt)
        for key, value in (('qualification_kind','full_app_hour'), ('qualification_kind','raw_d1'),
                           ('recording_model_scope',1), ('recording_model_scope',False),
                           ('unit','unrelated.service'), ('unexpected',True),
                           ('lifetime_policy','finite_qualification')):
            self.receipt = deepcopy(original); self.receipt[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.run_check()

    def test_finite_lifetime_invalid_values_and_real_limit(self):
        self.modern(); original = deepcopy(self.receipt)
        for key, value in (('deadline_monotonic',True), ('deadline_monotonic',None),
                           ('deadline_monotonic',159.99), ('deadline_monotonic',float('inf')),
                           ('runtime_max_seconds',True), ('runtime_max_seconds',0),
                           ('runtime_max_seconds',float('nan'))):
            self.receipt = deepcopy(original); self.receipt[key] = value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError): self.run_check()
        self.receipt = original
        for value in ('infinity','9min','malformed'):
            self.props['RuntimeMaxUSec'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.run_check()

    def test_actual_owner_cpu_task_cgroup_gates(self):
        self.modern(); original_props = deepcopy(self.props)
        for key, value in (('MainPID','22'), ('InvocationID','b'*32), ('ControlGroup','/foreign'),
                           ('ActiveState','inactive'), ('AllowedCPUs','0-3'),
                           ('CPUQuotaPerSecUSec','4s'), ('TasksMax','128')):
            self.props = dict(original_props, **{key:value})
            with self.subTest(key=key), self.assertRaises(ValueError): self.run_check()
        self.props = original_props; self.closed = True
        with self.assertRaises(ValueError): self.run_check()
        self.closed = False; self.actual_group = '/foreign'
        with self.assertRaises(ValueError): self.run_check()
        self.actual_group = GROUP; self.pids += ' 999999'
        with self.assertRaises(RuntimeError): self.run_check()

    def test_receipt_hash_and_legacy_unknown_fields(self):
        self.namespace['bounded'] = lambda path: encode(dict(self.receipt, main_pid=22))
        with self.assertRaisesRegex(ValueError,'receipt changed'): self.run_check()
        self.namespace['bounded'] = lambda path: encode(self.receipt)
        self.receipt['unexpected'] = True
        with self.assertRaises(ValueError): self.run_check()


def fault_fixture():
    physical = dict(kind='CLOSED', stream_closed=True, lease_released=True, sent_samples=0,
        processed_acknowledgements=0, integrity=dict(route=None,restoration_ok=True), owner=deepcopy(OWNER),
        receipt=dict(metadata=dict(stream_start_return_perf_counter_ns=3),commands=[
            dict(command='VERSION',exit_code=0,stdout='VERSION 3 2 1'),
            dict(command='BLD_MSG',exit_code=0,stdout='BLD_MSG intdev-lr48-lin-i2c'),
            dict(command='AEC_MIC_ARRAY_TYPE',exit_code=255,stderr='Resource could not respond')]),
        status=dict(converted_samples=0))
    result = dict(failure='Synthetic closed startup fault',source_facts=dict(input_source='live',
        owner=deepcopy(OWNER), source_thread_joined=True, child_returncode=1, processed_samples=0))
    return dict(returncode=1,direct_child_reaped=True,stdout_reader_joined=True,registered_owner=deepcopy(OWNER),
        receipt_errors=[],output_error=None,result=result,nested_source=dict(closed=True,owner=deepcopy(OWNER),physical_receipt=physical))


class DeferredThread:
    def __init__(self, target, name, daemon):
        self.target,self.name,self.daemon=target,name,daemon
        self.started=False; self.finished=False
    def start(self): self.started=True
    def complete(self):
        if not self.started or self.finished: raise AssertionError('Deferred fixture ownership')
        self.target(); self.finished=True
    def join(self, timeout=None):
        if self.name=='xvf-start-readiness' and not self.finished: raise AssertionError('Unclosed fixture helper')
    def is_alive(self): return self.started and not self.finished and self.name=='xvf-start-readiness'


class Selection:
    provisional_correction=False
    embedding='redimnet'
    input_source='live'
    def __init__(self, **values): self.values=values or dict(input_source='live',embedding='redimnet',diarization='current_delayed')
    def validate(self): return dict(self.values)


class Policy:
    total_deadline_seconds=100000
    max_drain_seconds=600
    cleanup_seconds=60
    def __init__(self, **values): self.values=values
    def validate(self): return dict(self.values)


class ManagerFlow(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='just-peachy-xvf-fresh-host-')
        self.base=Path(self.temporary.name); self.addCleanup(self.temporary.cleanup)
        self.readiness=ModuleType('xvf_readiness')
        qualify=deepcopy(member(OLD['xvf_readiness.py'],'qualifying_fault'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[qualify],type_ignores=[])), '<unchanged-qualifier>','exec'),self.readiness.__dict__)
        self.recovery_calls=[]
        self.readiness.recover_previous_source=lambda manager:self.recovery_calls.append(manager) or dict(status='READINESS_VERIFIED',audio_qualified=False)
        self.namespace=dict(os=SimpleNamespace(name='posix',environ=os.environ,fsync=os.fsync),Path=Path,
            threading=SimpleNamespace(Thread=DeferredThread),time=time,uuid=uuid,subprocess=subprocess,
            strict=json.loads,encoded=encode,digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest(),
            publish=self.publish,current_owner=lambda:deepcopy(OWNER),RuntimeSelection=Selection,SessionPolicy=Policy,
            __file__=str(HERE/'launcher.py'))
        names={'start','readiness_pending','_readiness_fault','_begin_readiness','_poll_readiness','poll','stop'}
        original=member(NEW['launcher.py'],'Manager',ast.ClassDef)
        methods=[deepcopy(node) for node in original.body if isinstance(node,ast.FunctionDef) and node.name in names]
        self.assertEqual(len(methods),len(names))
        code=ast.Module(body=[ast.ClassDef(name='Manager',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
        exec(compile(ast.fix_missing_locations(code),'<actual35-control-methods>','exec'),self.namespace)
        modules={
            'xvf_readiness':self.readiness,
            'application_contract':SimpleNamespace(validate=lambda value,selection:value,default=lambda embedding:{}),
            'developer_replay':SimpleNamespace(validate_repeat=lambda *args:None,pin_repeat_input=lambda *args:None),
            'release_authorization':SimpleNamespace(authorize_session=lambda *args:{},require_service_room=lambda *args:None),
            'optional_refiner_dispatch':SimpleNamespace(request_receipt=lambda *args:{}),
        }
        self.module_patch=patch.dict(sys.modules,modules); self.module_patch.start(); self.addCleanup(self.module_patch.stop)
        self.manager=self.fixture()

    def publish(self,path,value,**options):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb' if options.get('replace') else 'xb') as stream: stream.write(encode(value))

    def fixture(self):
        launch=self.base/'launches'/('a'*32); (launch/'worker').mkdir(parents=True)
        source=self.base/'recordings'/('b'*32)/'work/source'
        closure=fault_fixture()
        self.publish(self.base/'CURRENT_LAUNCH.json',dict(launch_id='a'*32))
        self.publish(launch/'REQUEST.json',dict(selection=dict(input_source='live')))
        self.publish(launch/'HOST_CLOSURE.json',closure)
        self.publish(launch/'worker/SESSION.json',dict(session_id='b'*32))
        self.publish(launch/'worker/RESULT.json',closure['result'])
        self.publish(launch/'worker/REGISTERED_OWNER.json',OWNER)
        self.publish(source/'SOURCE_CLOSE.json',closure['nested_source']['physical_receipt'])
        manager=object.__new__(self.namespace['Manager'])
        fields=dict(process=None,closed=False,export_task=None,data_root=self.base,launches=self.base/'launches',
            owner_dir=launch/'worker',run_dir=launch,binding={'native_launch_enabled':True,'python':'fixture-only'},
            binding_path=launch/'REQUEST.json',unit='jp-v29-classic-ui-check-53.service',unit_ownership=None,
            session_authorizer=None,service_room_check=None,reader_error=None,last=closure,
            _readiness_thread=None,_readiness_done=threading.Event(),_readiness_cancel=threading.Event(),
            _readiness_result=None,_readiness_error=None,_readiness_origin=None,
            _start_context=dict(selection=Selection().validate(),policy={},saved_path=None,saved_session_id=None,
                saved_store_root=None,repeat_input_seconds=None,application={'mode':'selected_closed','selected_ids':['fixture']}),
            _continuation_used=False,_resuming_start=False,readiness_notice='',stop_requested=None,
            watchdog_requested=False,spatial_visible=False,started=time.monotonic(),request=dict(policy={}))
        for name,value in fields.items(): setattr(manager,name,value)
        manager.owner_probe=lambda owner:dict(closed=True)
        manager.store=SimpleNamespace(_artifact_path=lambda sid,suffix:self.base/'recordings'/sid/suffix)
        manager._check_previous_launch=lambda:None
        manager._previous_readiness_fault=lambda:(_ for _ in ()).throw(AssertionError('Historical recovery must not precede fresh source'))
        manager.process_factory=lambda *args,**kwargs:SimpleNamespace(pid=99,stdout=None)
        return manager

    def fresh_start(self):
        self.manager.start(Selection(),Policy(),application={'mode':'selected_closed','selected_ids':['fixture']})
        self.assertIsNotNone(self.manager.process)
        self.assertFalse(self.manager.readiness_pending)
        self.assertFalse(self.manager._continuation_used)
        self.assertEqual(self.recovery_calls,[])

    def arm_closed_fault(self):
        manager=self.manager
        manager.process=SimpleNamespace(poll=lambda:1,wait=lambda:1)
        manager.reader=SimpleNamespace(join=lambda timeout:None,is_alive=lambda:False)
        manager._nested_source=lambda directory:fault_fixture()['nested_source']
        # poll publishes the closure once after the fake direct child/reader have reaped.
        (manager.run_dir/'HOST_CLOSURE.json').unlink()

    def test_old_success_cannot_spend_fresh_start(self):
        old=self.base/'recovery'/'old-success.json'
        self.publish(old,dict(status='READINESS_VERIFIED',audio_qualified=False))
        before=old.read_bytes()
        self.manager._continuation_used=True
        self.fresh_start()
        self.assertEqual(old.read_bytes(),before)

    def test_old_no_send_failure_is_preserved_and_not_retried(self):
        old=self.base/'recovery'/'old-no-send.json'
        self.publish(old,dict(status='FAILED_PRESERVED',maintenance_sends=0,maintenance_sends_attempted=0))
        before=old.read_bytes()
        self.manager.stop_requested=time.monotonic()-1; self.manager.watchdog_requested=True
        self.manager.reader_error='old completed fault'
        self.fresh_start()
        self.assertEqual(old.read_bytes(),before)
        self.assertIsNone(self.manager.stop_requested); self.assertFalse(self.manager.watchdog_requested)

    def test_fresh_poll_recovery_same_context_once(self):
        self.arm_closed_fault(); manager=self.manager; context=deepcopy(manager._start_context)
        self.assertIsNone(manager.poll()); self.assertTrue(manager.readiness_pending)
        self.assertTrue(manager._continuation_used); self.assertIsNone(manager.poll())
        worker_requests=[]
        manager.start=lambda *args,**kwargs:worker_requests.append((args,kwargs,manager._resuming_start))
        manager._readiness_thread.complete()
        self.assertIsNone(manager.poll()); self.assertEqual(len(self.recovery_calls),1)
        self.assertEqual(len(worker_requests),1); self.assertTrue(worker_requests[0][2])
        self.assertEqual(worker_requests[0][0][0].validate(),context['selection'])
        self.assertEqual(worker_requests[0][0][1].validate(),context['policy'])
        self.assertEqual(worker_requests[0][1]['application'],context['application'])
        self.assertFalse(manager.readiness_pending); self.assertTrue(manager._continuation_used)
        with self.assertRaises(RuntimeError): manager._begin_readiness(fault_fixture())

    def test_stop_cancels_owned_continuation_without_worker_restart(self):
        self.arm_closed_fault(); manager=self.manager; manager.poll()
        manager.stop(); manager._readiness_thread.complete()
        result=manager.poll()
        self.assertTrue(result['readiness_continuation']['cancelled'])
        self.assertFalse(result['readiness_continuation']['fresh_worker_requested'])
        self.assertEqual(self.recovery_calls,[]); self.assertIsNone(manager.process)
        self.assertFalse(manager.readiness_pending)

    def test_helper_failure_does_not_retry_or_start_worker(self):
        self.readiness.recover_previous_source=lambda manager:(_ for _ in ()).throw(RuntimeError('Synthetic preserved no-send failure'))
        self.arm_closed_fault(); manager=self.manager; manager.poll(); manager._readiness_thread.complete()
        result=manager.poll()
        self.assertIsNotNone(result['readiness_continuation']['error'])
        self.assertFalse(result['readiness_continuation']['fresh_worker_requested'])
        self.assertIsNone(manager.process); self.assertTrue(manager._continuation_used)
        self.assertEqual(manager.poll(),result)
        with self.assertRaises(RuntimeError): manager._begin_readiness(fault_fixture())

    def test_zero_audio_exact_closed_owner_fault_gate(self):
        manager=self.manager; original=fault_fixture()
        self.assertTrue(manager._readiness_fault(original))
        mutations=[('returncode',-9),('returncode',True),('direct_child_reaped',False),
                   ('stdout_reader_joined',False),('output_error','overflow'),('receipt_errors',['missing'])]
        for key,value in mutations:
            changed=deepcopy(original); changed[key]=value
            with self.subTest(key=key,value=value): self.assertFalse(manager._readiness_fault(changed))
        for key,value in (('sent_samples',1),('sent_samples',True),('processed_acknowledgements',1),
                          ('stream_closed',False),('lease_released',False)):
            changed=deepcopy(original); changed['nested_source']['physical_receipt'][key]=value
            with self.subTest(key=key): self.assertFalse(manager._readiness_fault(changed))
        for key,value in (('processed_samples',1),('source_thread_joined',False),('child_returncode',-9),('input_source','saved')):
            changed=deepcopy(original); changed['result']['source_facts'][key]=value
            with self.subTest(key=key): self.assertFalse(manager._readiness_fault(changed))
        changed=deepcopy(original); changed['registered_owner']['boot_id']='11111111-1111-1111-1111-111111111111'
        self.assertFalse(manager._readiness_fault(changed))
        manager.owner_probe=lambda owner:dict(closed=False)
        self.assertFalse(manager._readiness_fault(original))

    def test_pointer_mismatch_has_no_helper_or_restart_intent(self):
        changed=fault_fixture(); changed['result']['failure']='Different current closure'
        with self.assertRaisesRegex(RuntimeError,'current closed failure'): self.manager._begin_readiness(changed)
        self.assertFalse(self.manager._continuation_used)
        self.assertFalse(self.manager.readiness_pending)
        self.assertEqual(list(self.manager.run_dir.glob('SOURCE_RESTART_INTENT_*')),[])

