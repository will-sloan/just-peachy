"""Check recording across a stalled audio consumer. See README.md."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import types
import uuid
from collections import deque


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(process, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(process, *(ctypes.byref(v) for v in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    sys.dont_write_bytecode = True
    here = Path(__file__).resolve().parent
    private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')
    output = private/('spatial-stream-check-'+uuid.uuid4().hex)
    output.mkdir()
    started = time.time()
    def write(name, value):
        raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
        if len(raw)>65536: raise ValueError('Compact receipt bound')
        with (output/name).open('xb') as stream:
            if stream.write(raw)!=len(raw): raise OSError('Short receipt')
            stream.flush(); os.fsync(stream.fileno())
    write('REGISTERED_OWNER.json', dict(schema='just-peachy.host-registered-owner.v1',
        pid=os.getpid(), cpu=14, affinity_mask=1<<14, creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000))
    write('HOST_SCOPE.json', dict(issued_unix=started, maximum_seconds=600,
        maximum_bytes=8*1024**2, native_action=False, sensor_rows='SYNTHETIC'))
    sources = []
    for name in ('check_spatial_archive_v1.py','spatial_archive.py','runtime_ui_channel.py','README.md'):
        raw = (here/name).read_bytes()
        for folder in ('source-backup','source-restore'):
            (output/folder).mkdir(exist_ok=True)
            shutil.copyfile(here/name, output/folder/name)
            assert (output/folder/name).read_bytes()==raw
        if name.endswith('.py'): compile(raw,str(here/name),'exec')
        sources.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    write('SOURCE_CLOSED.json',dict(files=sources,independent_restores=True,closed_unix=time.time()))
    base = private/'full-application-package-d4ad7be181614b56bc2dc49aaa483bf2/package'
    sys.path[:0] = [str(here),str(base)]
    from spatial_archive import ArchivedSpatialViews
    from runtime_support import DiskBudget
    class Provider:
        motion = None
        def bind_origin(self, value): pass
        def receive(self, *args): pass
        def advance_audio(self, block): pass
    class Motion:
        def __init__(self):
            self.history=deque(maxlen=4); self.calls=0
        def update(self, at, frame):
            self.calls+=1
            self.history.append(dict(at=at,frame_generation=frame,yaw_deg=at,
                quaternion=[1.,0.,0.,0.],trustworthy=True))
            return self.calls
    worker=types.SimpleNamespace(lock=threading.RLock(),motion=Motion())
    original=worker.motion.update
    errors=[]
    root=output/'stream';root.mkdir()
    archive=ArchivedSpatialViews(Provider(),Provider(),worker,root,DiskBudget(1024**2),errors.append)
    archive.bind_origin(10.)
    # Twenty sensor updates exceed the four-row history while the audio consumer
    # does not run at all. Every row must already be queued for durable recording.
    for index in range(20):
        with worker.lock:
            assert worker.motion.update(10.+index*.02,0 if index<10 else 1)==index+1
    archive.receive('DOA',[42.,.9],10.4,10.41)
    archive.advance_audio(types.SimpleNamespace(callback_perf_counter_ns=10500000000,
        model_start_sample=0,audio=range(160)))
    assert not errors and archive.last_pose==10.38 and worker.motion.calls==20
    # A real discontinuity in the same frame must still reject and stop.
    worker.motion.history=deque([dict(at=12.,frame_generation=1)],maxlen=4)
    try:
        archive.advance_audio(types.SimpleNamespace(callback_perf_counter_ns=12010000000,
            model_start_sample=160,audio=range(160)))
    except RuntimeError as exc:
        assert 'history advanced' in str(exc)
    else: raise AssertionError('Missing sensor history was silently accepted')
    try: archive.close_archive()
    except RuntimeError as exc: assert 'history advanced' in str(exc)
    assert archive.closed and worker.motion.update==original and len(errors)==1
    poses=[json.loads(row) for path in sorted((root/'motion').glob('*.jsonl.[0-9]*')) for row in path.read_bytes().splitlines()]
    beams=[json.loads(row) for path in sorted((root/'spatial').glob('*.jsonl.[0-9]*')) for row in path.read_bytes().splitlines()]
    frames=[row for row in poses if row['kind']=='bmi270_pose']
    assert len(frames)==20 and [row['at'] for row in frames]==[10.+i*.02 for i in range(20)]
    assert all(row['audio_callback_monotonic_sec'] is None and row['model_sample_end'] is None for row in frames)
    assert sum(row['kind']=='reference_changed' for row in poses)==1
    anchors=[row for row in poses if row['kind']=='audio_clock_anchor']
    assert len(anchors)==1 and anchors[0]['audio_callback_monotonic_sec']==10.5 and anchors[0]['model_sample_end']==160
    assert len(beams)==1 and beams[0]['control_completed_monotonic_sec']==10.41 and beams[0]['values']==[42.,.9]
    for writer in (archive.beams,archive.poses):
        assert not writer.thread.is_alive() and writer.metrics()['error'] is None
    total=sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    assert total<8*1024**2 and time.time()-started<600
    write('RESULT.json',dict(status='PASS',bytes_before_result=total,checks=[
        'all_20_pose_rows_with_audio_consumer_stalled','retained_update_returns_and_call_count',
        'original_update_restored_after_fault','reference_change','exact_audio_clock_anchor',
        'beam_control_clock_preserved','real_history_loss_rejected','all_writers_joined'],
        native_action=False,sensor_accuracy_qualified=False))
    print(json.dumps(dict(status='PASS',output=str(output))))


if __name__=='__main__':main()
