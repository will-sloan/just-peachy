"""Changed export and observation-clock checks only. See README.md."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import threading
import time
import types
import uuid
import zipfile
from collections import deque

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')
BASE = PRIVATE/'full-application-package-d4ad7be181614b56bc2dc49aaa483bf2/package'


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
    output = PRIVATE/('session-package-check-'+uuid.uuid4().hex)
    output.mkdir()
    started = time.time()
    def write(name, value):
        raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
        if len(raw) > 65536: raise ValueError('Compact receipt bound')
        (output/name).write_bytes(raw)
    write('REGISTERED_OWNER.json', dict(schema='just-peachy.host-registered-owner.v1',
        pid=os.getpid(), cpu=14, affinity_mask=1<<14, creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000))
    write('HOST_SCOPE.json', dict(issued_unix=started, maximum_seconds=600,
        maximum_bytes=8*1024**2, native_action=False, synthetic_audio_and_sensor_rows=True))
    sources = []
    for name in ('check_session_package_v2.py','storage.py','spatial_archive.py','runtime_ui_channel.py','README.md'):
        raw = (HERE/name).read_bytes()
        for folder in ('source-backup','source-restore'):
            (output/folder).mkdir(exist_ok=True)
            shutil.copyfile(HERE/name, output/folder/name)
            assert (output/folder/name).read_bytes() == raw
        compile(raw, str(HERE/name), 'exec') if name.endswith('.py') else None
        sources.append(dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    write('SOURCE_CLOSED.json', dict(files=sources, independent_restores=True, closed_unix=time.time()))
    sys.path[:0] = [str(HERE), str(BASE)]
    from storage import SessionStore, StoragePolicy
    from runtime_support import DiskBudget
    from spatial_archive import ArchivedSpatialViews
    store = SessionStore(output/'sessions', StoragePolicy(reserve_fraction=0))
    spool = store.begin(dict(sample_rate=16000, mode='processed', duration_seconds=1,
        metadata_reserve_bytes=1024**2, title='Synthetic export regression'))
    sid = spool.session_id
    samples = struct.pack('<160f', *([0.125]*160))
    spool.append_processed(0, samples)
    store.write_caption(sid, 'utterance', 0, 160, 'Hello', speaker='Speaker 1', provisional=True,
        provenance=dict(source='synthetic regression', mode='anonymous_conversation'))
    store.write_caption(sid, 'utterance', 0, 160, 'Hello there', speaker='Unknown', provisional=False,
        provenance=dict(source='synthetic regression', mode='enrolled_names'))
    spool.stop()
    store.keep(sid)
    archive_path = store.export([sid], output/'synthetic-session.zip')
    with zipfile.ZipFile(archive_path) as archive:
        caption = json.loads(archive.read(sid+'/captions.jsonl'))
        events = [json.loads(row) for row in archive.read(sid+'/events.jsonl').splitlines()]
        transcript = archive.read(sid+'/transcript.txt').decode()
        assert caption['revision'] == 2 and caption['text'] == 'Hello there'
        revisions = [row['payload']['revision'] for row in events if row['event_type']=='caption_revision']
        assert revisions == [1,2]
        assert transcript == '[0.000–0.010] Unknown: Hello there\n'
        segments = [json.loads(row) for row in archive.read(sid+'/segments.jsonl').splitlines()]
        assert len(segments) == 1 and segments[0]['samples'] == 160
        assert archive.read(sid+'/'+segments[0]['data_name']) == samples
    store.close()

    class Provider:
        motion = None
        def bind_origin(self, origin): self.origin = origin
        def receive(self, *args): pass
        def advance_audio(self, block): pass
    errors = []
    worker = types.SimpleNamespace(lock=threading.RLock(), motion=types.SimpleNamespace(history=deque([
        dict(at=10.005, frame_generation=0, quaternion=[1,0,0,0], yaw_deg=0., trustworthy=True),
        dict(at=10.01, frame_generation=1, quaternion=[1,0,0,0], yaw_deg=1., trustworthy=False)])))
    spatial_root = output/'sensor-fixture'; spatial_root.mkdir()
    archive = ArchivedSpatialViews(Provider(), Provider(), worker, spatial_root,
        DiskBudget(1024**2), errors.append)
    archive.bind_origin(10.)
    archive.receive('DOA', [42., .9], 10.001, 10.012)
    archive.advance_audio(types.SimpleNamespace(callback_perf_counter_ns=10020000000,
        model_start_sample=0, audio=range(160)))
    archive.receive('DOA', [43.], 10.03, 10.04)
    worker.motion.history = deque([dict(at=10.5, frame_generation=1)])
    try:
        archive.advance_audio(types.SimpleNamespace(callback_perf_counter_ns=10600000000,
            model_start_sample=160, audio=range(160)))
    except RuntimeError as exc:
        assert 'history advanced' in str(exc)
    else:
        raise AssertionError('History overrun must preserve a fault and Stop')
    archive.close_archive()
    beams = [json.loads(row) for path in sorted((spatial_root/'spatial').glob('*.jsonl.[0-9]*')) for row in path.read_bytes().splitlines()]
    poses = [json.loads(row) for path in sorted((spatial_root/'motion').glob('*.jsonl.[0-9]*')) for row in path.read_bytes().splitlines()]
    assert beams[0]['values'] == [42.,.9] and beams[0]['model_sample_end'] == 160
    assert beams[0]['audio_callback_monotonic_sec'] >= beams[0]['control_completed_monotonic_sec']
    assert any(row['kind']=='reference_changed' for row in poses)
    assert sum(row['kind']=='bmi270_pose' for row in poses)==2
    assert all(row.get('absolute_translation_available') is False for row in poses if row['kind']=='bmi270_pose')
    assert errors
    for writer in (archive.beams, archive.poses):
        assert not writer.thread.is_alive()
        assert writer.metrics()['error'] is None
    bytes_used = sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    assert bytes_used < 8*1024**2 and time.time()-started < 600
    write('RESULT.json', dict(status='PASS', checks=['nonempty_transcript_export','all_caption_revisions',
        'exact_float32_replay','beam_audio_callback_alignment','pose_reference_changes','motion_gap_reject'],
        bytes_before_result=bytes_used, native_action=False, audio_and_sensor_rows='SYNTHETIC',
        linux_durability_qualified=False, closed_unix=time.time()))
    print(json.dumps(dict(output=str(output), status='PASS')))


if __name__ == '__main__': main()
