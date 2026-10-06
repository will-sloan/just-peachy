"""Changed metadata-fault cleanup checks only; see README_METADATA_CLEANUP.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
ROOT = PRIVATE/'audit-preparation'/('metadata-cleanup-check-'+uuid.uuid4().hex)
ROOT.mkdir()
me = psutil.Process()

def save(name, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(raw)>32768:
        raise ValueError('Compact check receipt exceeds 32 KiB')
    with (ROOT/name).open('xb') as output:
        assert output.write(raw)==len(raw)
        output.flush();os.fsync(output.fileno())

save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
save('HOST_SCOPE.json',dict(issued_unix=time.time(),expires_unix=time.time()+120,
    maximum_bytes=1048576,native_actions=False))
pins={}
for name in ('installed_engine.py','worker.py','check_metadata_cleanup.py','README_METADATA_CLEANUP.md'):
    raw=(HERE/name).read_bytes()
    for suffix in ('backup','restore'):
        target=ROOT/(name+'.'+suffix)
        with target.open('xb') as output:
            assert output.write(raw)==len(raw)
            output.flush();os.fsync(output.fileno())
        assert target.read_bytes()==raw
    pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
save('SOURCE_CLOSED.json',dict(files=pins,independent_restores=True))

tree=ast.parse((HERE/'installed_engine.py').read_bytes())
klass=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='InstalledSession')
close=next(node for node in klass.body if isinstance(node,ast.FunctionDef) and node.name=='close')
space={'threading':threading,'hashlib':hashlib,
    'encoded':lambda value:json.dumps(value,sort_keys=True,allow_nan=False).encode()}
exec(compile(ast.Module(body=[close],type_ignores=[]),'<actual-installed-session-close>','exec'),space)

class CapacityError(RuntimeError):
    pass

class Target:
    def __init__(self,calls,name,error=None):self.calls,self.name,self.error=calls,name,error
    def close(self):
        self.calls.append(self.name)
        if self.error:raise self.error
    stop=close

class Trace(Target):
    closed=False
    def record(self,*args,**kwargs):
        self.calls.append('trace_record')
        raise CapacityError('cleanup event denied')
    def close(self):self.calls.append('trace_close');self.closed=True

def fixture(engine=None,source_error=None):
    calls=[]
    item=types.SimpleNamespace(engine=engine,source=Target(calls,'source',source_error),
        models=Target(calls,'models'),attribution_writer=Target(calls,'attribution'),
        model_memory=Trace(calls,'trace'),spatial_archive=types.SimpleNamespace(close_archive=lambda:calls.append('archive')),
        failure='original CapacityError',stop_event=threading.Event(),policy=types.SimpleNamespace(cleanup_seconds=.2),
        spool=types.SimpleNamespace(session_id='fixture',store=types.SimpleNamespace(write_terminal_event=lambda *a:None)),
        _close_optional=lambda:calls.append('optional'),_close_motion=lambda:calls.append('motion'),
        _close_saved_spatial=lambda:calls.append('saved_lease'),fail=lambda reason:calls.append('fail'))
    return item,calls

groups=[]
item,calls=fixture(source_error=CapacityError('source closure receipt denied'))
try:space['close'](item)
except RuntimeError as error:
    assert 'source closure receipt denied' in str(error) and 'cleanup event denied' in str(error)
else:raise AssertionError('Cleanup fault hidden')
assert calls==['source','optional','archive','motion','models','attribution','saved_lease','trace_record','trace_close']
assert item.stop_event.is_set() and item.model_memory.closed and item.failure=='original CapacityError'
groups.append('source_receipt_and_trace_fault_do_not_skip_resources')

calls=[]
engine=types.SimpleNamespace(_finalization_thread=None,_session_dir=Path('fixture'),_threads=[],
    state='FAILED',_journal=types.SimpleNamespace(finish=lambda reason:(_ for _ in ()).throw(CapacityError('prelaunch journal denied'))),
    text_writers=[],wait_for_completion=lambda timeout:None)
engine._watch_session=lambda:calls.append('installed_watch')
item,cleanup=fixture(engine=engine)
try:space['close'](item)
except RuntimeError as error:assert 'prelaunch journal denied' in str(error)
else:raise AssertionError('Prelaunch journal fault hidden')
assert calls==['installed_watch'] and 'models' in cleanup and not item.cleanup_receipt['model_lanes_owned']
groups.append('prelaunch_journal_fault_still_finalizes')

class LiveThread:
    name='native_still_owned'
    def is_alive(self):return True
    def join(self,timeout):pass
live=LiveThread()
engine=types.SimpleNamespace(_finalization_thread=live,_session_dir=Path('fixture'),
    _threads=[live],state='FAILED',text_writers=[])
item,calls=fixture(engine=engine)
try:space['close'](item)
except RuntimeError as error:assert 'Model ownership retained' in str(error)
else:raise AssertionError('Live native lane hidden')
assert 'models' not in calls and 'attribution' in calls and 'saved_lease' in calls and 'trace_close' in calls
assert item.cleanup_receipt['model_lanes_owned'] is True
groups.append('live_lane_retains_model_other_cleanup_continues')

worker_tree=ast.parse((HERE/'worker.py').read_bytes())
run=next(node for node in worker_tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_owned_session')
published=[]
module=types.ModuleType('runtime_support')
module.publish=lambda path,value:published.append(value)
sys.modules['runtime_support']=module
space={'threading':threading}
exec(compile(ast.Module(body=[run],type_ignores=[]),'<actual-worker-run-owned-session>','exec'),space)
with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    root=Path(directory);work=root/'work';work.mkdir()
    calls=[]
    session=types.SimpleNamespace(work=work,stop_event=threading.Event(),
        run=lambda:(_ for _ in ()).throw(CapacityError('first metadata exhaustion')),
        fail=lambda reason:calls.append('fail'),
        close=lambda:(_ for _ in ()).throw(CapacityError('secondary trace denied')),
        cleanup_receipt=dict(attempted=True,completed=['source_stop_join','models'],physical_process_closed=False))
    store=types.SimpleNamespace(close=lambda:calls.append('store_closed'),register_artifact=lambda *a,**k:None)
    spool=types.SimpleNamespace(session_id='fixture',directory=root,processed_samples=42,
        fail=lambda reason:calls.append('spool_failed'),stop=lambda **kw:calls.append('unexpected_success'))
    assert space['run_owned_session'](store,spool,session,root)==1
    result=published[-1]
    assert 'first metadata exhaustion' in result['failure'] and 'secondary trace denied' in result['failure']
    assert result['post_stop_choice_pending'] is False and result['logical_cleanup_complete'] is False
    assert result['cleanup_attempted'] is True and result['cleanup']['completed']==['source_stop_join','models']
    assert result['result'] is None and result['source_facts']['processed_samples']==42
    assert result['source_facts']['source_start_observed'] is True
    assert result['source_facts']['physical_start_packet_observed'] is False
    assert calls[-1]=='store_closed' and 'unexpected_success' not in calls
    groups.append('worker_failure_independent_cleanup_and_actual_sample_facts')
    module.publish=lambda *args:(_ for _ in ()).throw(CapacityError('result publication denied'))
    try:space['run_owned_session'](store,spool,session,root)
    except CapacityError as error:assert str(error)=='result publication denied'
    else:raise AssertionError('Result publication fault hidden')
    assert calls[-1]=='store_closed'
    groups.append('result_publication_fault_still_closes_store')

assert sum(path.stat().st_size for path in ROOT.rglob('*') if path.is_file())<1048576
save('RESULT.json',dict(status='PASS',groups=groups,group_count=len(groups),native_actions=False,
    models_loaded=False,capture_started=False,scope='actual changed functions with controlled metadata faults'))
print(json.dumps(dict(status='PASS',groups=len(groups),output=str(ROOT),owner=dict(pid=me.pid,create_time=me.create_time()))))
