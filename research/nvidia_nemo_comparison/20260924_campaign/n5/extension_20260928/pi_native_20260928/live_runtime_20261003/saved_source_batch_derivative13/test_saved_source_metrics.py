"""Host-only source proofs; direct invocation owns CPU14 before project reads."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path
Q = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OUTPUT = Q / ('presets-preparation-batch13-checks-'+uuid.uuid4().hex)
OUTPUT.mkdir()
with (OUTPUT/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())
import ast
import hashlib
import sys
import threading
import time
import types
import unittest
import wave
import numpy as np
HERE = Path(__file__).resolve().parent
BASE = Path(json.loads((HERE/'BASE.json').read_text())['base_package'])
sys.path[:0] = [str(HERE),str(BASE)]
from runtime_support import digest
from saved_source_metrics import SavedSourceMetrics, validate_batch_samples
from developer_replay import RepeatedSavedSource
import saved_replay
node = next(n for n in ast.parse((HERE/'installed_engine.py').read_text()).body
            if isinstance(n,ast.ClassDef) and n.name=='SavedSource')
namespace=dict(Path=Path,time=time,threading=threading,wave=wave,digest=digest)
exec(compile(ast.Module(body=[node],type_ignores=[]),'SavedSource-under-test','exec'),namespace)
SavedSource=namespace['SavedSource']

class Clock:
    def __init__(self):self.value=17.0
    def __call__(self):return self.value
class Stop:
    def __init__(self,clock):self.clock=clock;self.stopped=False
    def is_set(self):return self.stopped
    def set(self):self.stopped=True
    def wait(self,seconds):self.clock.value+=seconds;return self.stopped
class Policy:
    maximum_session_seconds=3600
    developer_soak=True
    def __init__(self,maximum):self.maximum=maximum
    def maximum_samples(self):return self.maximum
class Journal:
    def __init__(self,clock,stop=None,stop_after=None,fail_after=None):
        self.clock=clock;self.stop=stop;self.stop_after=stop_after;self.fail_after=fail_after
        self.sha=hashlib.sha256();self.samples=0;self.calls=0;self.maximum=0;self.finishes=[]
    def append(self,array):
        if self.fail_after is not None and self.calls==self.fail_after:raise OSError('synthetic append failure')
        self.clock.value+=.001
        self.sha.update(array.astype('<f4',copy=False).tobytes());self.samples+=len(array)
        self.calls+=1;self.maximum=max(self.maximum,len(array))
        if self.stop_after==self.calls:self.stop.set()
    def finish(self,error):self.finishes.append(error)

def wave_file(name,frames):
    path=OUTPUT/name
    samples=((np.arange(frames,dtype=np.int64)*7919)%65536-32768).astype('<i2')
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(samples.tobytes())
    return path,samples.astype(np.float32)/32768.

class Proofs(unittest.TestCase):
    def test_exact_wav_tail_and_batch_equivalence(self):
        path,audio=wave_file('synthetic-tail.wav',715127)
        expected=hashlib.sha256(audio.astype('<f4').tobytes()).hexdigest()
        counts=[]
        for batch in (320,1600):
            clock=Clock();stop=Stop(clock);journal=Journal(clock);events=[]
            source=SavedSource(journal,path,lambda k,v:events.append((k,v)),Policy(len(audio)),stop,append_batch_samples=batch,clock=clock)
            source._run()
            self.assertIsNone(source.error);self.assertEqual(source.sent,len(audio));self.assertEqual(journal.sha.hexdigest(),expected)
            self.assertEqual(journal.finishes,[None]);self.assertTrue(source.done.is_set());self.assertLessEqual(journal.maximum,batch)
            metrics=events[-1][1]['saved_source_metrics'];self.assertEqual(metrics['committed_source_samples'],len(audio));self.assertEqual(metrics['append_calls'],journal.calls)
            progress=[v for k,v in events if k=='saved_source_progress'];self.assertLessEqual(len(progress),46)
            counts.append(journal.calls)
        self.assertEqual(counts,[2235,447])
    def test_continuous_3600_seconds_repeat_without_reset(self):
        path,audio=wave_file('synthetic-repeat.wav',715127)
        target=57600000;clock=Clock();stop=Stop(clock);journal=Journal(clock);events=[]
        source=RepeatedSavedSource(journal,path,lambda k,v:events.append((k,v)),Policy(target),stop,
            repeat_input_seconds=3600,expected_sha256=digest(path),clock=clock)
        source._run();expected=hashlib.sha256();left=target
        while left:
            count=min(left,len(audio));expected.update(audio[:count].astype('<f4').tobytes());left-=count
        self.assertIsNone(source.error);self.assertEqual(source.sent,target);self.assertEqual(journal.samples,target)
        self.assertEqual(journal.sha.hexdigest(),expected.hexdigest());self.assertEqual(journal.finishes,[None]);self.assertLessEqual(journal.maximum,1600)
        origins={v['source_epoch_monotonic_sec'] for k,v in events if k in ('source_started','source_repeat_boundary')}
        self.assertEqual(len(origins),1)
        boundaries=[v for k,v in events if k=='source_repeat_boundary']
        self.assertEqual([v['logical_start_sample'] for v in boundaries],list(range(len(audio),target,len(audio))))
        self.assertTrue(all(v['models_reset'] is False for v in boundaries))
    def test_stop_and_append_failure_preserve_prefix(self):
        path,audio=wave_file('synthetic-stop.wav',4901)
        for fail in (False,True):
            clock=Clock();stop=Stop(clock);journal=Journal(clock,stop,stop_after=None if fail else 2,fail_after=2 if fail else None);events=[]
            source=SavedSource(journal,path,lambda k,v:events.append((k,v)),Policy(len(audio)),stop,clock=clock)
            source._run();self.assertEqual(source.sent,3200);self.assertEqual(journal.samples,3200)
            self.assertEqual(journal.sha.hexdigest(),hashlib.sha256(audio[:3200].astype('<f4').tobytes()).hexdigest())
            self.assertEqual(source.error is not None,fail);self.assertEqual(len(journal.finishes),1);self.assertTrue(source.done.is_set())
            self.assertEqual(events[-1][1]['saved_source_metrics']['append_failures'],int(fail))
    def test_kept_float_exact_segments_and_lease_release(self):
        audio=np.linspace(-.95,.95,4911,dtype='<f4');parts=(1703,3201,7);rows=[];cursor=0
        folder=OUTPUT/'kept';folder.mkdir();(folder/'work').mkdir()
        for index,count in enumerate(parts):
            name=f'{index}.f32';(folder/name).write_bytes(audio[cursor:cursor+count].tobytes())
            rows.append(dict(idx=index,start_sample=cursor,samples=count,data_name=name));cursor+=count
        metadata=dict(processed_samples=len(audio),status='kept',spec={'sample_rate':16000})
        class Lease:
            closed=False
            def close(self):self.closed=True
        class Store:
            owner={'store_id':'synthetic-only'}
            def __init__(self,*a,**k):self.lease=Lease();self.closed=False
            def _session_lease(self,*a,**k):return self.lease
            def read(self,*a):return metadata
            def processed_segment_page(self,*a,after):return [r for r in rows if r['idx']>after]
            def _audio_path(self,session,name):return folder/name
            def close(self):self.closed=True
        previous=saved_replay.SessionStore;saved_replay.SessionStore=Store
        try:
            clock=Clock();stop=Stop(clock);journal=Journal(clock);events=[]
            journal.spool=types.SimpleNamespace(directory=folder,spec={},store=types.SimpleNamespace(_capacity=lambda n:None))
            source=saved_replay.SavedSessionSource(journal,folder,'synthetic',lambda k,v:events.append((k,v)),Policy(len(audio)),stop,clock=clock)
            lease=source.lease;source._run()
            self.assertIsNone(source.error);self.assertEqual(journal.samples,len(audio));self.assertEqual(journal.sha.hexdigest(),hashlib.sha256(audio.tobytes()).hexdigest())
            self.assertEqual(journal.calls,6);self.assertLessEqual(journal.maximum,1600);self.assertTrue(lease.closed);self.assertTrue(source.store.closed)
            self.assertTrue(events[-1][1]['complete_recording']);self.assertTrue(source.done.is_set())
        finally:saved_replay.SessionStore=previous
    def test_bounds_and_lag_denominator(self):
        for value in (True,0,319,321,1601,3200,1600.0):
            with self.assertRaises(ValueError):validate_batch_samples(value)
        clock=Clock();events=[];metrics=SavedSourceMetrics(clock(),lambda k,v:events.append(v),1600,clock=clock)
        journal=Journal(clock);clock.value+=2.;metrics.append(journal,np.zeros(1600,dtype=np.float32),1600);metrics.progress()
        snapshot=metrics.snapshot();self.assertAlmostEqual(snapshot['append_seconds'],.001)
        self.assertAlmostEqual(snapshot['source_wall_lag_seconds'],1.901);self.assertEqual(snapshot['source_seconds'],.1)
        self.assertEqual(len(events),1)
        with self.assertRaises(ValueError):metrics.append(journal,np.zeros(1601),3201)
        self.assertEqual(journal.calls,1)
    def test_non_source_engine_ast_unchanged(self):
        def retained(path):
            return [ast.dump(n) for n in ast.parse(path.read_text()).body
                    if not(isinstance(n,ast.ClassDef) and n.name=='SavedSource')]
        self.assertEqual(retained(BASE/'installed_engine.py'),retained(HERE/'installed_engine.py'))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Proofs))
    receipt=dict(native_executed=False,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        success=result.wasSuccessful(),synthetic_exact_source_only=True,output=str(OUTPUT),
        files={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in
        ('installed_engine.py','developer_replay.py','saved_replay.py','saved_source_metrics.py',Path(__file__).name)})
    (OUTPUT/'RESULT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2))
    print(json.dumps(receipt));sys.exit(0 if result.wasSuccessful() else 1)
