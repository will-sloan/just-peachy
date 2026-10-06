"""Changed constructor and recorded-source ordering check. See README_SEAT_BACKENDS.md."""
import ctypes
import json
import os
import sys


def main():
    if os.name != 'nt' or len(sys.argv) != 3 or sys.argv[1] != '--output':
        raise SystemExit('Use documented Windows CPU14 command and fresh --output')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.c_void_p]*4
    process = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(process, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    values = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    output = os.path.abspath(sys.argv[2]); os.mkdir(output)
    with open(os.path.join(output, 'REGISTERED_OWNER.json'), 'x', encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(), create_time=values[0].value/10000000-11644473600,
            cpu=[14], scope='changed seat hook and synthetic saved-source ordering; no hardware/model/GUI'), stream)
    sys.dont_write_bytecode = True
    import ast
    from copy import deepcopy
    import hashlib
    import importlib.util
    from pathlib import Path
    import shutil
    import struct
    import threading
    import time
    from types import ModuleType, SimpleNamespace
    started = time.monotonic()
    out = Path(output); root = Path(__file__).resolve().parent
    for volume, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
        if shutil.disk_usage(volume).free < floor:
            raise ValueError('Host free-space floor failed')
    base = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/full-application-package-e366bb9496184252bc36bd4576fd8c04/package')
    pipeline_path = Path('G:/Just_Peachy_N1/20260924_campaign/worktree/prototype/app/pipeline.py')
    sources = [root/name for name in ('seat_backend.py', 'installed_engine.py', 'saved_replay.py',
        'check_seat_integration.py', 'README_SEAT_BACKENDS.md', 'README_SAVED_REPLAY.md')]
    sources += [pipeline_path, base/'saved_source_metrics.py']
    backup, restore = out/'source-backup', out/'source-restore'; backup.mkdir(); restore.mkdir()
    pins = []
    for source in sources:
        raw = source.read_bytes()
        if len(raw) > 128*1024:
            raise ValueError('Source member bound')
        copied, restored = backup/source.name, restore/source.name
        copied.write_bytes(raw); restored.write_bytes(copied.read_bytes())
        if copied.read_bytes() != raw or restored.read_bytes() != raw:
            raise ValueError('Independent source restore differs')
        if source.suffix == '.py':
            compile(raw, str(source), 'exec')
        pins.append(dict(name=source.name, source=str(source), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    (out/'SOURCE_CLOSED.json').write_text(json.dumps(dict(source_pins=pins,
        independent_restores=True, closed_before_import=True, allocation_bytes=1048576), sort_keys=True), encoding='utf-8')
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
    adapter = load('seat_hook_check_adapter', root/'seat_backend.py')
    checks = []
    def reject(name, action):
        try: action()
        except ValueError: checks.append(name)
        else: raise AssertionError(name+' accepted')
    fixture = out/'pipeline_fixture.py'
    raw = b'''def SeatIdentityResolver(value):
    return ('legacy', value)
class Base:
    def begin(self):
        self.base_seen = True
class PrototypeEngine(Base):
    def begin(self, value=7):
        super().begin()
        self.resolver = SeatIdentityResolver(value)
        return self.resolver
'''
    fixture.write_bytes(raw)
    def fixture_module(name):
        module = ModuleType(name); module.__file__ = str(fixture)
        exec(compile(raw, str(fixture), 'exec'), module.__dict__); return module
    module = fixture_module('seat_hook_fixture'); before = fixture.read_bytes()
    original = module.PrototypeEngine.begin
    receipt = adapter.install_factory_hook(module, hashlib.sha256(raw).hexdigest())
    first = module.PrototypeEngine(); second = module.PrototypeEngine()
    second._seat_identity_factory = lambda value: ('selected', value)
    assert first.begin() == ('legacy',7) and second.begin(11) == ('selected',11)
    assert first.base_seen and second.base_seen and fixture.read_bytes() == before
    assert module.PrototypeEngine.begin.__closure__ is original.__closure__
    assert receipt['only_constructor_callee_changed'] and receipt['constructor_targets_changed'] == 1
    assert adapter.install_factory_hook(module, hashlib.sha256(raw).hexdigest()) == receipt
    checks.append('per_instance_factory_preserves_default_super_closure_and_disk_source')
    reject('wrong_manifest_hash', lambda:adapter.install_factory_hook(fixture_module('bad_pin'), '0'*64))
    drift = fixture_module('drift')
    exec('def altered(self, value=7):\n    return value\n', drift.__dict__)
    drift.PrototypeEngine.begin = drift.altered
    reject('loaded_method_source_drift', lambda:adapter.install_factory_hook(drift, hashlib.sha256(raw).hexdigest()))
    # Compile only the actual begin AST; do not import the real model/application graph.
    actual_raw = pipeline_path.read_bytes(); parsed = ast.parse(actual_raw)
    cls = next(item for item in parsed.body if isinstance(item, ast.ClassDef) and item.name=='PrototypeEngine')
    begin = next(item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name=='begin')
    container = deepcopy(cls); container.bases=[]; container.keywords=[]; container.decorator_list=[]; container.body=[begin]
    actual = ModuleType('actual_pipeline_ast_only'); actual.__file__=str(pipeline_path)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[container], type_ignores=[])), str(pipeline_path), 'exec'), actual.__dict__)
    actual_receipt = adapter.install_factory_hook(actual, hashlib.sha256(actual_raw).hexdigest())
    assert actual_receipt['only_constructor_callee_changed'] and actual_receipt['source_disk_changed'] is False
    checks.append('actual_pipeline_begin_ast_derivation_only_one_constructor_target')
    # Replay synthetic floats through the real changed source loop, with fixture
    # storage and a NumPy-shape stand-in. No microphone, model or media is read.
    events = []; audio_root=out/'fixture-store'; audio_root.mkdir()
    audio = struct.pack('<960f', *(index/10000 for index in range(960)))
    segment = audio_root/'segment.f32'; segment.write_bytes(audio)
    metadata = dict(status='kept', processed_samples=960, spec=dict(sample_rate=16000))
    class Lease:
        def close(self): events.append(('lease_close',))
    class Store:
        def __init__(self, directory, read_only):
            assert read_only is True
            self.root=Path(directory); self.owner=dict(store_id='synthetic'); self.closed=False
        def _session_lease(self, session_id, shared):
            assert session_id=='synthetic-session' and shared is True
            return Lease()
        def read(self, session_id): return deepcopy(metadata)
        def processed_segment_page(self, session_id, after=-1):
            return [dict(idx=0,start_sample=0,samples=960,data_name='segment.f32')] if after==-1 else []
        def _audio_path(self, session_id, name): return self.root/name
        def close(self): self.closed=True
    storage = ModuleType('storage'); storage.SessionStore=Store; storage.StorageError=type('StorageError',(ValueError,),{})
    sys.modules['storage']=storage
    metrics = load('saved_source_metrics', base/'saved_source_metrics.py'); sys.modules['saved_source_metrics']=metrics
    numpy = ModuleType('numpy')
    class Array(list):
        def copy(self): return Array(self)
    numpy.frombuffer=lambda value,dtype:Array(struct.unpack('<'+str(len(value)//4)+'f',value))
    sys.modules['numpy']=numpy
    replay=load('changed_saved_replay_fixture',root/'saved_replay.py')
    class Spatial:
        session_id='synthetic-session'; frames=960; closed=False
        store=SimpleNamespace(root=audio_root)
        metadata_sha256=hashlib.sha256(replay.encoded(metadata)).hexdigest()
        def advance_samples(self, end): events.append(('spatial',end))
    class Journal:
        def __init__(self, directory):
            (directory/'work').mkdir(parents=True)
            self.spool=SimpleNamespace(directory=directory,spec=dict(metadata_reserve_bytes=8*1024**2),
                store=SimpleNamespace(_capacity=lambda count:None)); self.raw=bytearray()
        def append(self, values):
            end=len(self.raw)//4+len(values)
            assert events[-1]==('spatial',end)
            events.append(('audio',end)); self.raw.extend(struct.pack('<'+str(len(values))+'f',*values))
        def finish(self,error): events.append(('finish',error))
    class Stop:
        def is_set(self): return False
        def wait(self,seconds): return False
    journal=Journal(out/'fixture-output')
    source=replay.SavedSessionSource(journal,audio_root,'synthetic-session',
        lambda kind,data:events.append(('callback',kind)),SimpleNamespace(maximum_samples=lambda:960),Stop(),
        append_batch_samples=320,clock=lambda:1000.,spatial=Spatial())
    source._run()
    assert source.error is None and source.sent==960 and source.done.is_set()
    assert bytes(journal.raw)==audio
    assert [item for item in events if item[0] in ('audio','spatial')]==[
        ('spatial',320),('audio',320),('spatial',640),('audio',640),('spatial',960),('audio',960)]
    assert source.store.closed and source.lease is None and ('finish',None) in events
    checks.append('actual_saved_source_loop_historical_before_exact_audio_and_natural_closure')
    bad_spatial=Spatial(); bad_spatial.metadata_sha256='0'*64
    reject('saved_spatial_metadata_pin_drift', lambda:replay.SavedSessionSource(
        Journal(out/'rejected-output'),audio_root,'synthetic-session',lambda*args:None,
        SimpleNamespace(maximum_samples=lambda:960),Stop(),spatial=bad_spatial))
    # Engine wiring order is reviewed without importing native/model dependencies.
    engine_tree=ast.parse((root/'installed_engine.py').read_bytes())
    methods={item.name:item for node in engine_tree.body if isinstance(node,ast.ClassDef) and node.name=='InstalledSession'
             for item in node.body if isinstance(item,ast.FunctionDef)}
    run=methods['run']; dumped=ast.dump(run,include_attributes=False)
    assert 'install_factory_hook' in dumped and '_seat_identity_factory' in dumped
    assert '_s7_observed_clock' in dumped and 'SavedSpatialViews' in dumped
    calls=[node for node in ast.walk(run) if isinstance(node,ast.Call)]
    waits=[node.lineno for node in calls if isinstance(node.func,ast.Attribute) and node.func.attr=='wait_for_completion']
    closes=[node.lineno for node in calls if isinstance(node.func,ast.Attribute) and node.func.attr=='_close_saved_spatial']
    assert waits and closes and max(waits)<max(closes)
    checks.append('engine_adapter_before_begin_and_historical_lease_after_model_drain_ast')
    for pin in pins:
        assert hashlib.sha256(Path(pin['source']).read_bytes()).hexdigest()==pin['sha256']
    if time.monotonic()-started>60 or sum(path.stat().st_size for path in out.rglob('*') if path.is_file())>1048576:
        raise ValueError('Focused host lifetime/output allocation exceeded')
    (out/'RESULT.json').write_text(json.dumps(dict(status='PASS_CHANGED_SEAT_FACTORY_AND_RECORDED_SOURCE_INTEGRATION',
        checks=checks,count=len(checks),synthetic_audio_samples=960,actual_pipeline_ast_only=True,
        native_runtime_tested=False,model_tested=False,hook=receipt,actual_source_hook=actual_receipt),sort_keys=True),encoding='utf-8')
    print(json.dumps(dict(status='PASS_CHANGED_SEAT_FACTORY_AND_RECORDED_SOURCE_INTEGRATION',checks=len(checks),output=output)))


if __name__ == '__main__':
    main()
