"""Focused no-device Start recovery checks; README_XVF_START_CONTINUATION.md."""
import ast
import ctypes
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import uuid


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 16384):
        raise ctypes.WinError(ctypes.get_last_error())
    clocks = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in clocks)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')/('xvf-start-continuation-check-'+uuid.uuid4().hex)
    root.mkdir()
    started, used = time.monotonic(), 0
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    def write(path, value):
        nonlocal used
        raw = value if isinstance(value, bytes) else encode(value)
        if used+len(raw) > 2*1024**2 or time.monotonic()-started > 600:
            raise ValueError('Finite2MiB/600s source and fixture allocation exceeded')
        for drive, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
            if shutil.disk_usage(drive).free < floor+len(raw):
                raise OSError('Host storage safety floor')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw) != len(raw): raise OSError('Short focused-check publication')
            stream.flush(); os.fsync(stream.fileno())
        used += len(raw)
        if path.read_bytes() != raw: raise OSError('Focused-check independent readback differs')
    owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
                 affinity_mask=16384, creation_filetime=clocks[0].value,
                 create_time=(clocks[0].value-116444736000000000)/10000000)
    write(root/'REGISTERED_OWNER.json', owner)
    write(root/'HOST_SCOPE.json', dict(maximum_bytes=2*1024**2, maximum_seconds=600, native_action=False))
    here = Path(__file__).parent
    sources = {}
    paths = (Path(__file__), here/'launcher.py', here/'README_XVF_START_CONTINUATION.md',
             here.parent/'ui_restore_20261004/xvf_readiness_helper.py',
             here.parent/'ui_restore_20261004/xvf_readiness.py',
             root.parent/'xvf-startup-source-before-f66bf12d571547d69f3e3c05ba32f5d9/launcher.py.backup',
             root.parent/'xvf-startup-source-before-f66bf12d571547d69f3e3c05ba32f5d9/xvf_readiness_helper.py.backup')
    for index, path in enumerate(paths):
        before = path.stat(); raw = path.read_bytes(); after = path.stat()
        if len(raw) > 131072 or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('Stable bounded source required before execution')
        for suffix in ('', '.backup', '.restore'):
            write(root/(str(index)+'-'+path.name+suffix), raw)
        sources[path.name] = raw
    write(root/'SOURCE_CLOSED.json', dict(independent_restores=True,
        source_sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}))
    old, new = ast.parse(sources['launcher.py.backup']), ast.parse(sources['launcher.py'])
    old_manager = next(node for node in old.body if isinstance(node, ast.ClassDef) and node.name == 'Manager')
    manager_node = next(node for node in new.body if isinstance(node, ast.ClassDef) and node.name == 'Manager')
    old_methods = {node.name: node for node in old_manager.body if isinstance(node, ast.FunctionDef)}
    new_methods = {node.name: node for node in manager_node.body if isinstance(node, ast.FunctionDef)}
    changed = {name for name in old_methods if ast.dump(old_methods[name], include_attributes=False) != ast.dump(new_methods[name], include_attributes=False)}
    if changed != {'__init__', 'start', 'stop', 'poll', 'export_recordings', 'close'}:
        raise AssertionError('Unexpected retained Manager method change: '+repr(changed))
    if set(new_methods)-set(old_methods) != {'readiness_pending', '_readiness_fault', '_previous_readiness_fault', '_begin_readiness', '_poll_readiness'}:
        raise AssertionError('Unexpected Manager API additions')
    helper_old = ast.parse(sources['xvf_readiness_helper.py.backup'])
    helper_new = ast.parse(sources['xvf_readiness_helper.py'])
    for node in helper_new.body[:]:
        if isinstance(node, ast.Import) and len(node.names) == 1 and node.names[0].name == 'math': helper_new.body.remove(node)
    old_unit = next(node for node in helper_old.body if isinstance(node, ast.FunctionDef) and node.name == 'unit_checks')
    new_unit = next(node for node in helper_new.body if isinstance(node, ast.FunctionDef) and node.name == 'unit_checks')
    helper_new.body[helper_new.body.index(new_unit)] = old_unit
    if ast.dump(helper_new, include_attributes=False) != ast.dump(helper_old, include_attributes=False):
        raise AssertionError('Recovery helper changed outside unit_checks and math import')
    for name in ('launcher.py', 'xvf_readiness_helper.py'):
        compile(sources[name], '<backed-prepared:'+name+'>', 'exec')
    readiness = ModuleType('xvf_readiness')
    qualify = next(node for node in ast.parse(sources['xvf_readiness.py']).body if isinstance(node, ast.FunctionDef) and node.name == 'qualifying_fault')
    exec(compile(ast.Module(body=[qualify], type_ignores=[]), '<retained-exact-qualifier>', 'exec'), readiness.__dict__)
    # The separate exact-byte migration check owns the old unsent artifact case.
    readiness.preserved_unsent_manual_failure = lambda manager, closure: False
    synthetic_owner = dict(pid=21, start_ticks=4, boot_id='00000000-0000-0000-0000-000000000000')
    physical = dict(kind='CLOSED', stream_closed=True, lease_released=True, sent_samples=0,
        processed_acknowledgements=0, integrity=dict(route=None, restoration_ok=True), owner=synthetic_owner,
        receipt=dict(metadata=dict(stream_start_return_perf_counter_ns=3), commands=[
            dict(command='VERSION', exit_code=0, stdout='VERSION 3 2 1'),
            dict(command='BLD_MSG', exit_code=0, stdout='BLD_MSG intdev-lr48-lin-i2c'),
            dict(command='AEC_MIC_ARRAY_TYPE', exit_code=255, stderr='Resource could not respond')]),
        status=dict(converted_samples=0))
    result = dict(failure='Retained original AEC255', source_facts=dict(input_source='live',
                  owner=synthetic_owner, source_thread_joined=True, child_returncode=1, processed_samples=0))
    closure = dict(returncode=1, direct_child_reaped=True, stdout_reader_joined=True,
                   registered_owner=synthetic_owner, receipt_errors=[], output_error=None,
                   result=result, nested_source=dict(closed=True, owner=synthetic_owner, physical_receipt=physical))
    class Selection:
        input_source = 'live'
        provisional_correction = False
        embedding = 'redimnet'
        def __init__(self, **values): self.values = values or dict(input_source='live')
        def validate(self): return dict(self.values)
    class Policy:
        total_deadline_seconds = 100000
        def __init__(self, **values): self.values = values
        def validate(self): return dict(self.values)
    namespace = dict(os=os, Path=Path, threading=threading, time=time, uuid=uuid, subprocess=subprocess,
                     strict=json.loads, encoded=encode, digest=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
                     publish=lambda path, value, **options: write(path, value),
                     RuntimeSelection=Selection, SessionPolicy=Policy,
                     current_owner=lambda: synthetic_owner, owner_status=lambda owner:dict(closed=True),
                     kill_owned_unit=lambda *values:None)
    exec(compile(ast.Module(body=[manager_node], type_ignores=[]), '<backed-actual-Manager>', 'exec'), namespace)
    Manager = namespace['Manager']
    prior_modules = {}
    def install(name, **fields):
        prior_modules[name] = sys.modules.get(name)
        module = ModuleType(name); module.__dict__.update(fields); sys.modules[name] = module
    install('xvf_readiness', **readiness.__dict__)
    install('application_contract', validate=lambda value, selection: value, default=lambda embedding: {})
    install('developer_replay', validate_repeat=lambda *values: None, pin_repeat_input=lambda *values: None)
    install('release_authorization', authorize_session=lambda *values: {}, require_service_room=lambda *values: None)
    install('optional_refiner_dispatch', request_receipt=lambda *values: {})
    sys.modules['xvf_readiness'] = readiness
    positive_groups, rejects = 0, 0
    try:
        with tempfile.TemporaryDirectory(prefix='just-peachy-start-continuation-') as temporary:
            def fixture(label):
                base = Path(temporary)/label
                launch = base/'launches'/('a'*32); (launch/'worker').mkdir(parents=True)
                source = base/'recordings'/('b'*32)/'work/source'
                write(base/'CURRENT_LAUNCH.json', dict(launch_id='a'*32))
                write(launch/'REQUEST.json', dict(selection=dict(input_source='live')))
                write(launch/'HOST_CLOSURE.json', closure)
                write(launch/'worker/SESSION.json', dict(session_id='b'*32))
                write(launch/'worker/RESULT.json', result)
                write(launch/'worker/REGISTERED_OWNER.json', synthetic_owner)
                write(source/'SOURCE_CLOSE.json', physical)
                manager = object.__new__(Manager)
                for name, value in dict(process=None, closed=False, export_task=None, data_root=base,
                        launches=base/'launches', owner_dir=launch/'worker', run_dir=launch,
                        binding={'native_launch_enabled':True}, unit_ownership=None,
                        session_authorizer=None, service_room_check=None, reader_error=None,
                        last=closure, _readiness_thread=None, _readiness_done=threading.Event(),
                        _readiness_cancel=threading.Event(), _readiness_result=None, _readiness_error=None,
                        _readiness_origin=None, _start_context=dict(selection=dict(input_source='live'), policy={},
                            saved_path=None, saved_session_id=None, saved_store_root=None,
                            repeat_input_seconds=None, application={}),
                        _continuation_used=False, _resuming_start=False, readiness_notice='',
                        stop_requested=None, watchdog_requested=False, spatial_visible=False,
                        started=time.monotonic(), request=dict(policy={})).items(): setattr(manager, name, value)
                manager.owner_probe = lambda owner: dict(closed=True)
                manager.store = SimpleNamespace(_artifact_path=lambda sid, suffix: base/'recordings'/sid/suffix,
                                                close=lambda: setattr(manager, 'store_closed', True))
                manager.lease = SimpleNamespace(close=lambda: setattr(manager, 'lease_closed', True))
                return manager
            gate = threading.Event(); calls = []
            def recover(manager):
                calls.append(manager)
                if not gate.wait(2): raise TimeoutError('Focused recovery fixture deadline')
                return dict(status='PREVIOUS_READINESS_REUSED', audio_qualified=False)
            readiness.recover_previous_source = recover
            manager = fixture('normal-failure')
            manager.process = SimpleNamespace(poll=lambda:1, wait=lambda:1)
            manager.reader = SimpleNamespace(join=lambda timeout:None, is_alive=lambda:False)
            manager._nested_source = lambda directory: closure['nested_source']
            # The original close publication is absent until the actual poll path writes it.
            (manager.run_dir/'HOST_CLOSURE.json').unlink()
            if manager.poll() is not None or not manager.readiness_pending: raise AssertionError('First failure did not continue asynchronously')
            if manager.poll() is not None: raise AssertionError('Pending helper returned premature session completion')
            resumed = []
            manager.start = lambda *args, **kwargs: resumed.append((args, kwargs, manager._resuming_start))
            gate.set(); manager._readiness_thread.join(3)
            if manager.poll() is not None or len(resumed) != 1 or not resumed[0][2] or manager.readiness_pending:
                raise AssertionError('Joined helper did not request exactly one main-thread restart')
            if not manager._continuation_used: raise AssertionError('Continuation budget was replenished')
            positive_groups += 1
            gate.clear(); manager = fixture('previous-fault')
            # Exercise the real public Start path: previous-fault preflight also goes off-thread.
            manager.stop_requested = time.monotonic()-1
            manager.watchdog_requested = True
            manager.reader_error = 'previous closed-worker output error'
            manager.latest_health = manager.latest_diagnostic = manager.latest_spatial = {'old':True}
            manager.start(Selection(), Policy(), application={})
            if not manager.readiness_pending or manager.process is not None: raise AssertionError('Preflight helper blocked or started a worker')
            if (manager.stop_requested is not None or manager.watchdog_requested or manager.reader_error is not None
                    or any(value is not None for value in (manager.latest_health,manager.latest_diagnostic,manager.latest_spatial))):
                raise AssertionError('New user Start retained previous completed-worker transient state')
            resumed = []; manager.start = lambda *args, **kwargs: resumed.append(args)
            manager.stop(); gate.set(); manager._readiness_thread.join(3)
            decision = manager.poll()
            if resumed or decision['readiness_continuation']['cancelled'] is not True or manager.readiness_pending:
                raise AssertionError('Stop during preflight restarted capture')
            positive_groups += 1
            gate.clear(); manager = fixture('closing')
            manager._begin_readiness(closure)
            try: manager.close()
            except RuntimeError: pass
            else: raise AssertionError('Close released GUI while helper remained owned')
            if getattr(manager, 'store_closed', False) or getattr(manager, 'lease_closed', False):
                raise AssertionError('Pending helper lost manager lease')
            gate.set(); manager._readiness_thread.join(3); manager.poll(); manager.close()
            if not manager.closed: raise AssertionError('Closed helper prevented normal Exit')
            positive_groups += 1
            manager = fixture('eligibility')
            if not manager._readiness_fault(closure): raise AssertionError('Exact natural closed fault rejected')
            bad_closures = [dict(closure, returncode=-9), dict(closure, returncode=True),
                            dict(closure, stdout_reader_joined=False), dict(closure, output_error='overflow'),
                            dict(closure, receipt_errors=['missing']), dict(closure, direct_child_reaped=False)]
            for changed in bad_closures:
                if manager._readiness_fault(changed): raise AssertionError('Unsafe failed-worker continuation admitted')
                rejects += 1
            for key, value in (('sent_samples',1), ('sent_samples',True), ('processed_acknowledgements',1),
                               ('stream_closed',False), ('lease_released',False)):
                changed = dict(closure, nested_source=dict(closure['nested_source'], physical_receipt=dict(physical, **{key:value})))
                if manager._readiness_fault(changed): raise AssertionError('Nonempty/unclosed source admitted')
                rejects += 1
            manager.owner_probe = lambda owner: dict(closed=False)
            if manager._readiness_fault(closure): raise AssertionError('Live owner admitted')
            rejects += 1
            positive_groups += 1
            actual_unit = next(node for node in ast.parse(sources['xvf_readiness_helper.py']).body if isinstance(node,ast.FunctionDef) and node.name=='unit_checks')
            group = '/user.slice/test.scope'
            manual = dict(unit='test.service', owner=synthetic_owner, main_pid=21, invocation_id='abc',
                          control_group=group, runtime_max_seconds=None, deadline_monotonic=None,
                          idle_timeout_seconds=300, lifetime_policy='manual_stop_storage_guarded')
            props = dict(MainPID='21',InvocationID='abc',ControlGroup=group,ActiveState='active',
                         AllowedCPUs='2-3',CPUQuotaPerSecUSec='2s',TasksMax='64',RuntimeMaxUSec='infinity')
            class VirtualPath:
                def __init__(self, path): self.path = path
                def __truediv__(self, name): return VirtualPath(self.path+'/'+name)
                def read_text(self): return '0::'+group+'\n' if self.path=='/proc/self/cgroup' else str(os.getpid())+' 21'
            unit_namespace = dict(bounded=lambda path:encode(manual), strict=json.loads, hashlib=hashlib, re=re,
                                  time=time, math=math, os=os, Path=VirtualPath, owner_closed=lambda owner:False,
                                  subprocess=SimpleNamespace(run=lambda *args,**kwargs:SimpleNamespace(stdout='\n'.join(k+'='+v for k,v in props.items()))))
            exec(compile(ast.Module(body=[actual_unit],type_ignores=[]),'<actual-unit-policy-check>', 'exec'),unit_namespace)
            request = dict(unit_ownership='receipt',unit_ownership_sha256=hashlib.sha256(encode(manual)).hexdigest(),
                           unit='test.service', manager_owner=synthetic_owner)
            unit_namespace['unit_checks'](request)
            for key, value in (('deadline_monotonic',1), ('runtime_max_seconds',7200), ('idle_timeout_seconds',True),
                               ('lifetime_policy','unexpected')):
                changed = dict(manual,**{key:value}); unit_namespace['bounded']=lambda path, changed=changed:encode(changed)
                request['unit_ownership_sha256']=hashlib.sha256(encode(changed)).hexdigest()
                try: unit_namespace['unit_checks'](request)
                except ValueError: rejects += 1
                else: raise AssertionError('Malformed manual lifetime admitted')
            finite = dict(manual,lifetime_policy='finite_qualification')
            finite.update(runtime_max_seconds=600, deadline_monotonic=time.monotonic()+90)
            unit_namespace['bounded']=lambda path:encode(finite); props['RuntimeMaxUSec']='10min'
            request['unit_ownership_sha256']=hashlib.sha256(encode(finite)).hexdigest()
            unit_namespace['unit_checks'](request)
            props['RuntimeMaxUSec']='9min'
            try:unit_namespace['unit_checks'](request)
            except ValueError:rejects+=1
            else:raise AssertionError('Actual finite service lifetime drift admitted')
            props['RuntimeMaxUSec']='10min'
            for deadline in (None, True, time.monotonic()+30, float('inf')):
                changed=dict(finite,deadline_monotonic=deadline)
                raw=json.dumps(changed,sort_keys=True,separators=(',',':')).encode()
                unit_namespace['bounded']=lambda path,raw=raw:raw;request['unit_ownership_sha256']=hashlib.sha256(raw).hexdigest()
                try:unit_namespace['unit_checks'](request)
                except ValueError:rejects+=1
                else:raise AssertionError('Malformed/insufficient finite lifetime admitted')
            positive_groups += 1
    finally:
        for name, module in prior_modules.items():
            if module is None: sys.modules.pop(name,None)
            else: sys.modules[name]=module
    result = dict(status='PASS_CHANGED_HOST_START_CONTINUATION_ONLY',positive_groups=positive_groups,rejects=rejects,
                  fixture_owners_persisted=False,native_executed=False,raw_module_execution=False,
                  source_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()},bytes_written=used)
    write(root/'RESULT.json',result)
    print(str(root));print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
