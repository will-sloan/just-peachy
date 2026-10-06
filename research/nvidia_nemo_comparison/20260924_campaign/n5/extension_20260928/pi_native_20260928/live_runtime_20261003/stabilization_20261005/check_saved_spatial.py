"""Bounded host-only recorded clock/gap check; README_SAVED_SPATIAL.md."""
import argparse
import ast
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import types


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(process, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recording-directory', type=Path)
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir()
    started = time.time()
    def write(name, value):
        raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
        if len(raw) > 65536:
            raise ValueError('Compact check receipt bound')
        with (output/name).open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short check receipt')
            stream.flush(); os.fsync(stream.fileno())
    write('REGISTERED_OWNER.json', dict(schema='just-peachy.host-registered-owner.v1',
        pid=os.getpid(), cpu=14, affinity_mask=1<<14, creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000))
    write('HOST_SCOPE.json', dict(issued_unix=started, maximum_seconds=600,
        maximum_bytes=8*1024**2, native_action=False, private_audio_read=False))
    sys.dont_write_bytecode = True
    here = Path(__file__).resolve().parent
    sources = [here/name for name in ('saved_spatial.py', 'check_saved_spatial.py', 'README_SAVED_SPATIAL.md')]
    n = here.parent
    base = n.parent/'mounted_imu_20261002/runtime/live_spatial.py'
    seats = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/production-backup-08-reconcile-01/payload/root-05/app/seats.py')
    geometry = Path('G:/Just_Peachy_N1/20260924_campaign/worktree/prototype/app/inertial_geometry.py')
    beam = seats.with_name('beam_diagnostics.py')
    sources += [base, seats, geometry, beam]
    pins = []
    for number, source in enumerate(sources):
        raw = source.read_bytes()
        for folder in ('source-backup', 'source-restore'):
            (output/folder).mkdir(exist_ok=True)
            target = output/folder/('%02d-' % number+source.name)
            shutil.copyfile(source, target)
            if target.read_bytes() != raw:
                raise ValueError('Independent source restoration differs')
        if source.suffix == '.py':
            compile(raw, str(source), 'exec')
        pins.append(dict(path=str(source), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    write('SOURCE_CLOSED.json', dict(files=pins, independent_restores=True, closed_unix=time.time()))

    # Execute retained pure geometry/provider classes, excluding inference and
    # hardware imports. The DeliveredSpatialObservation shape is a typed fixture.
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class Observation:
        angle_deg: object
        available_at_sec: float
        energy: object
        reliability: float
        valid: bool
        sequence: int
    def extract(path, names):
        tree = ast.parse(path.read_bytes())
        nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        if {node.name for node in nodes} != set(names):
            raise ValueError('Retained pure source shape changed')
        return ast.Module(body=nodes, type_ignores=[])
    geometry_module = types.ModuleType('app.inertial_geometry')
    geometry_module.math = math
    exec(compile(extract(geometry, ('horizontal_candidates',)), str(geometry), 'exec'), geometry_module.__dict__)
    beam_scope = dict(math=math)
    exec(compile(extract(beam, ('native_angle_degrees',)), str(beam), 'exec'), beam_scope)
    from collections import deque, OrderedDict
    from copy import deepcopy
    import threading
    live_module = types.ModuleType('app.live_spatial')
    live_module.__dict__.update(dict(deque=deque, OrderedDict=OrderedDict, deepcopy=deepcopy,
        math=math, threading=threading, time=time, DeliveredSpatialObservation=Observation,
        FIELD_COUNTS={'AEC_AZIMUTH_VALUES':4,'AEC_SPENERGY_VALUES':4,'AUDIO_MGR_SELECTED_AZIMUTHS':2},
        native_angle_degrees=beam_scope['native_angle_degrees'], BEAMS=[],
        ANGLE='AEC_AZIMUTH_VALUES',ENERGY='AEC_SPENERGY_VALUES',SELECTED='AUDIO_MGR_SELECTED_AZIMUTHS',
        RECEIPT_LIMIT=.25,DISPLAY_LIMIT=.75))
    exec(compile(extract(base, ('motion_reference','LiveSpatialProvider')), str(base), 'exec'), live_module.__dict__)
    seats_module = types.ModuleType('app.seats')
    seats_module.__dict__.update(live_module.__dict__)
    seats_module.__dict__.update(dict(DEFAULT_TOLERANCE=25., MAPPING='retained fixture mapping'))
    import uuid
    seats_module.uuid = uuid
    exec(compile(extract(seats, ('validate_layout','collisions','StubMotionService','SeatSession','SeatSpatialProvider')),
                 str(seats), 'exec'), seats_module.__dict__)
    sys.modules['app'] = types.ModuleType('app')
    sys.modules['app.live_spatial'] = live_module
    sys.modules['app.seats'] = seats_module
    sys.modules['app.inertial_geometry'] = geometry_module

    store_module = types.ModuleType('storage')
    class Lease:
        def close(self): pass
    class Store:
        def __init__(self, root, read_only):
            if read_only is not True: raise ValueError('Read-only check')
            self.root = Path(root)
        def _session_lease(self, session_id, shared):
            if shared is not True: raise ValueError('Shared check')
            return Lease()
        def read(self, session_id):
            return dict(status='kept',processed_samples=3200,
                spec=dict(sample_rate=16000,metadata_reserve_bytes=1024**2))
        def _artifacts(self, session_id):
            for path in sorted((self.root/'work').rglob('*')):
                if path.is_file():
                    yield dict(path=path.relative_to(self.root).as_posix(),role='fixture',bytes=path.stat().st_size)
        def _artifact_path(self, session_id, name): return self.root/name
        def close(self): pass
    store_module.SessionStore = Store
    sys.modules['storage'] = store_module
    sys.path.insert(0, str(here))
    from saved_spatial import SavedSpatialViews, _Timeline, SCHEMA, RecordedMotion
    def row(kind, **values):
        return dict(schema=SCHEMA, kind=kind, source_epoch_monotonic_sec=100.,
            model_sample_rate=16000, audio_callback_monotonic_sec=None, model_sample_end=None,
            alignment='fixture', **values)
    def pose(at, generation=1, valid=True):
        return row('bmi270_pose', at=at,yaw_deg=0.,valid=valid,state='STATIONARY',
            reason='synthetic',drift_allowance_deg=2.,axis_xy=[1.,0.],
            frame_generation=generation,unsafe_generation=0,
            absolute_heading_available=False,absolute_translation_available=False)
    fixture = output/'fixture'
    orientation = [row('source_origin'), dict(pose(99.99, valid=False),axis_xy=None),
        pose(100.07), pose(100.095),
        dict(row('audio_clock_anchor'),model_start_sample=0,model_sample_end=1600,audio_callback_monotonic_sec=100.1),
        pose(100.18), pose(100.195),
        dict(row('audio_clock_anchor'),model_start_sample=1600,model_sample_end=3200,audio_callback_monotonic_sec=100.2),
        dict(row('audio_end_bound'),model_sample_end=3200,audio_callback_monotonic_sec=100.2)]
    commands = [('AEC_AZIMUTH_VALUES',[math.pi/2]*4),('AEC_SPENERGY_VALUES',[1.,0.,0.,1.]),
                ('AUDIO_MGR_SELECTED_AZIMUTHS',[math.pi/2,math.pi/2])]
    beam_rows = [row('xvf_observation',command=command,values=values,
        control_started_monotonic_sec=100.071+number*.005,
        control_completed_monotonic_sec=100.073+number*.005) for number,(command,values) in enumerate(commands)]
    def logs(root, prefix, rows):
        path = root/prefix
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = b''.join(json.dumps(value,sort_keys=True,allow_nan=False).encode()+b'\n' for value in rows)
        path.with_name(path.name+'.000000').write_bytes(raw)
        path.with_name(path.name+'.index.json').write_text(json.dumps(dict(segment_count=1,
            segment_pattern=path.name+'.%06d',accepted_bytes=len(raw),completed_bytes=len(raw),
            error=None,refusal=None,complete=True)))
    logs(fixture,'work/motion/orientation.jsonl',orientation)
    logs(fixture,'work/spatial/beam_angles.jsonl',beam_rows)
    tracker = types.SimpleNamespace(direction_max_age_sec=.75,minimum_spatial_reliability=.25,
        position_decay_sec=5.,location_learning_rate=.2,max_tracks=8,direction_match_deg=25.)
    provider = SavedSpatialViews(fixture, '0'*32, tracker)
    provider.bind_origin(10000.)
    provider.advance_samples(1600)
    cue = provider.evidence_for_window(0., .1, .1)
    assert cue is not None and abs(cue.angle_deg-90.) < 1e-6
    assert cue.available_at_sec == .1 and provider.replayed_beams == 3
    provider.advance_samples(3200)
    assert provider.evidence_for_window(0., .1, .1) is not None
    assert provider.evidence_for_window(0., .1, 21.3) is None
    assert provider.current_clock < 101. and provider.motion.snapshot()['hardware_opened'] is False
    assert provider.queries == 3
    positive = provider.receipt()
    provider.close()
    rejected = []
    def reject(name, function):
        try: function()
        except (ValueError, OSError): rejected.append(name)
        else: raise AssertionError('Expected rejection: '+name)
    reject('plain/missing session clock logs', lambda:SavedSpatialViews(output/'absent','0'*32,tracker))
    reject('future source cursor',lambda:provider.advance_samples(3201))
    # Each fault gets its own immutable fixture; no mutation retry.
    cases = [('anchor_gap',[dict(value,model_start_sample=1) if value['kind']=='audio_clock_anchor' and value['model_start_sample']==0 else value for value in orientation]),
        ('mixed_epoch',[dict(value,source_epoch_monotonic_sec=101.) if value['kind']=='audio_end_bound' else value for value in orientation]),
        ('missing_final_bound',[value for value in orientation if value['kind']!='audio_end_bound']),
        ('bool_pose_generation',[dict(value,frame_generation=True) if value['kind']=='bmi270_pose' else value for value in orientation])]
    for name, rows in cases:
        root = output/name
        logs(root,'work/motion/orientation.jsonl',rows)
        logs(root,'work/spatial/beam_angles.jsonl',beam_rows)
        reject(name,lambda root=root:SavedSpatialViews(root,'0'*32,tracker))
    gap = output/'reference-gap'
    rows = [dict(value,frame_generation=2) if value['kind']=='bmi270_pose' and value['at']>100.15 else value for value in orientation]
    logs(gap,'work/motion/orientation.jsonl',rows)
    logs(gap,'work/spatial/beam_angles.jsonl',beam_rows)
    provider = SavedSpatialViews(gap,'0'*32,tracker)
    provider.advance_samples(1600)
    provider.advance_samples(3200)
    assert provider.reference_losses == 1 and provider.evidence(0.,.1) is None
    provider.motion.at = 101.
    assert provider.motion.transform(90.,100.1) == (None,0.)
    provider.close()
    actual = None
    if args.recording_directory is not None:
        directory = args.recording_directory.resolve(strict=True)
        class Actual(Store):
            def _artifact_path(self, session_id, name): return directory/name
        actual_store = Actual(directory,True)
        artifacts = {path.relative_to(directory).as_posix():dict(bytes=path.stat().st_size)
            for folder in ('work/motion','work/spatial') for path in (directory/folder).iterdir() if path.is_file()}
        timelines = [_Timeline(actual_store,'0'*32,prefix,artifacts,128*1024**2)
            for prefix in ('work/motion/orientation.jsonl','work/spatial/beam_angles.jsonl')]
        assert timelines[0].origin == timelines[1].origin and timelines[0].end > 0
        for timeline in timelines: timeline.verify_closed()
        actual = dict(scope='actual closed schema/clock/hash only; fixture artifact catalogue, no runtime playback',
            processed_final_anchor=timelines[0].end,timelines=[timeline.receipt() for timeline in timelines])
    used = sum(path.stat().st_size for path in output.rglob('*') if path.is_file())
    assert used < 8*1024**2 and time.time()-started < 600
    write('RESULT.json',dict(status='PASS_CHANGED_HOST_SAVED_SPATIAL_CLOCK_GAPS',
        positive_groups=3,rejections=rejected,clock_alignment=positive,
        actual_recorded_schema=actual,native_runtime_tested=False,private_audio_read=False,
        elapsed_seconds=time.time()-started,used_bytes=used))
    write('EXIT_INTENT.json',dict(pid=os.getpid(),creation_filetime=stamps[0].value,
        natural_completion_intended=True,physical_death_claim=False))
    print(json.dumps(dict(status='PASS_CHANGED_HOST_SAVED_SPATIAL_CLOCK_GAPS',output=str(output))))


if __name__ == '__main__':
    main()
