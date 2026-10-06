"""Focused pure adapter checks; no hardware/model/audio calls. See README_SEAT_BACKENDS.md."""
import ctypes
import json
import os
import sys
import time


def main():
    if os.name != 'nt' or len(sys.argv) != 3 or sys.argv[1] != '--output':
        raise SystemExit('Use the documented Windows CPU14 host command and a fresh --output directory')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p]*4
    process = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(process, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    created, exited, system, user = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(process, *(ctypes.byref(v) for v in (created, exited, system, user))):
        raise ctypes.WinError(ctypes.get_last_error())
    output = os.path.abspath(sys.argv[2])
    os.mkdir(output)
    owner = dict(pid=os.getpid(), create_time=created.value/10000000-11644473600,
                 cpu=[14], scope='pure changed seat adapter check; no native/model/audio/GUI')
    with open(os.path.join(output, 'REGISTERED_OWNER.json'), 'x', encoding='utf-8') as stream:
        json.dump(owner, stream, sort_keys=True)
    # Early owner and affinity exist before any project source is read.
    import hashlib
    import importlib.util
    from pathlib import Path
    import shutil
    from types import SimpleNamespace
    for volume, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
        if shutil.disk_usage(volume).free < floor:
            raise ValueError('Host free-space floor failed')
    root = Path(__file__).resolve().parent
    files = [root/name for name in ('seat_backend.py', 'check_seat_backend.py', 'README_SEAT_BACKENDS.md')]
    backup, restored = Path(output)/'source-backup', Path(output)/'source-restore'
    backup.mkdir(); restored.mkdir()
    pins = []
    for source in files:
        raw = source.read_bytes()
        if len(raw) > 128*1024:
            raise ValueError('Source bound failed')
        copied, restore = backup/source.name, restored/source.name
        copied.write_bytes(raw)
        restore.write_bytes(copied.read_bytes())
        if restore.read_bytes() != raw:
            raise ValueError('Independent source restore differs')
        pins.append(dict(name=source.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    with open(Path(output)/'SOURCE_CLOSED.json', 'x', encoding='utf-8') as stream:
        json.dump(dict(source_pins=pins, independent_restores=True, deadline_seconds=60,
                       allocation_bytes=1048576, closed_before_import=True), stream, sort_keys=True)
    spec = importlib.util.spec_from_file_location('seat_backend_changed_check', root/'seat_backend.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

    class Seats:
        def __init__(self, angle=45, second=None):
            self.rows = [dict(person_id='a', angle_deg=angle, tolerance_deg=10)]
            if second is not None:
                self.rows.append(dict(person_id='b', angle_deg=second, tolerance_deg=10))
            self.valid, self.revision, self.released = True, 1, {}
        def snapshot(self):
            return dict(rows=self.rows, valid=self.valid, revision=self.revision, released=self.released,
                        strength='soft', session_id='fixture-seat', reason='fixture_anchor')
        def release(self, ids, reason):
            self.released.update({value:reason for value in ids})

    class Provider:
        def __init__(self, angle=45): self.angle=angle; self.clocks=[]
        def seat_evidence(self, start, end, available):
            self.clocks.append((start, end, available))
            return (None if self.angle is None else SimpleNamespace(angle_deg=self.angle, reliability=1)), dict(valid=self.angle is not None, reason='fixture_direction')

    class Voice:
        def __init__(self, gallery=None, accepted=False): self.gallery=gallery; self.calls=0; self.accepted=accepted
        def resolve(self, decision, event):
            self.calls += 1
            return dict(decision, identity=dict(verified=self.accepted, naming_state='confirmed' if self.accepted else 'unknown',
                known_profile_id='a' if self.accepted else None, known_name='Ada' if self.accepted else None,
                current_scores=[dict(profile_id='a', cosine=.9), dict(profile_id='b', cosine=.1)]), identity_compute_sec=0)
        def snapshot(self): return dict(calls=self.calls)
        def sync_tracks(self, active, now): pass

    def gallery(encoder='titanet'):
        namespace=dict(model_sha256='a'*64, preprocessing='fixture-titanet', dimension=192, normalization='L2',
                       onnx_sha256='b'*64, frontend_sha256='c'*64)
        if encoder=='redimnet':
            namespace=dict(model_sha256='d'*64, preprocessing='mono-float32-16k-redimnet2-native-l2-v1', dimension=192, normalization='L2')
        gate=dict(status='CALIBRATED', namespace=namespace, schema='just-peachy.n2.calibrated-gate.v1',
            fit_role='C', query_domain='fixture-query', profile_ids=['a','b'], score_threshold=.8, margin_threshold=.2)
        gate['gate_sha256']=module._sha(gate)
        return SimpleNamespace(namespace=namespace, calibration=gate, ids=['a','b'], gallery_id='fixture-gallery',
            receipt=dict(loader='N2Gallery actual runtime cosine', expected_query_domain='fixture-query', backend_sha256=namespace['model_sha256']))

    event=dict(event_id='embedding-1', source_start_sec=0., source_end_sec=1., available_at_sec=1.,
               vector=[1.]+[0.]*191, speech=True, overlap=False, clean_intervals=[[0.,1.]])
    decision=dict(tracker_id='actual-fixture-session:nemotron-slot-0', anonymous_label='Speaker 1')
    names=dict(a='Ada', b='Bea')
    checks=[]
    def record(name, passed):
        if not passed: raise AssertionError(name)
        checks.append(name)
    # Explicit direction assumptions do not query even an incompatible/unavailable gallery.
    for diarizer in ('pyannote','nemotron'):
        for encoder in ('redimnet','titanet'):
            if (diarizer, encoder)==('pyannote','redimnet'):continue
            voice=Voice(); provider=Provider()
            resolver=module.BackendSeatResolver(voice, seats=Seats(), names=names, provider=provider,
                diarizer=diarizer, embedding=encoder, direction_only=True)
            value=resolver.resolve(decision,event)
            record(diarizer+'/'+encoder+'/direction-assumption', value['known_profile_id']=='a' and
                value['identity']['verified'] is False and value['prototype_assignment']=='seat_assumed' and voice.calls==0)
    provider=Provider(); delayed=dict(event, available_at_sec=22.)
    resolver=module.BackendSeatResolver(None, seats=Seats(), names=names, provider=provider,
        diarizer='nemotron', embedding='titanet', direction_only=True)
    value=resolver.resolve(decision,delayed)
    record('D1 historical source clock retains actual 21 second delay', provider.clocks==[(0.,1.,1.)] and
        value['identity']['seat']['model_delay_from_source_sec']==21 and value['identity']['seat']['current_position_claim'] is False)
    caption=resolver.annotate_caption(dict(known_profile_id='a', evidence_ids=['embedding-1'], naming_state='confirmed'))
    record('caption keeps marked assumption', caption['prototype_assignment']=='seat_assumed' and not caption['seat_identity_verified'])
    resolver.seats.valid=False
    record('anchor invalidation removes inherited assumption', resolver.annotate_caption(caption)['naming_state']=='invalidated')
    for label, changed in [('overlap',dict(event,overlap=True)), ('not-speech',dict(event,speech=False)),
        ('empty-clean',dict(event,clean_intervals=[])), ('bad-vector',dict(event,vector=[0.]*192)),
        ('bool-source-clock',dict(event,source_end_sec=True)), ('future-source',dict(event,source_end_sec=2.)),
        ('nan-vector',dict(event,vector=[float('nan')]+[0.]*191))]:
        instance=module.BackendSeatResolver(None,seats=Seats(),names=names,provider=Provider(),
            diarizer='nemotron',embedding='titanet',direction_only=True)
        record('reject '+label, instance.resolve(decision,changed)['known_profile_id'] is None)
    for label, seats, provider in [('overlapping seats',Seats(second=50),Provider()),
        ('outside seats',Seats(),Provider(90)), ('missing direction',Seats(),Provider(None))]:
        instance=module.BackendSeatResolver(None,seats=seats,names=names,provider=provider,
            diarizer='nemotron',embedding='redimnet',direction_only=True)
        record('reject '+label, instance.resolve(decision,event)['known_profile_id'] is None)
    calibrated=gallery()
    resolver=module.BackendSeatResolver(Voice(calibrated,True),seats=Seats(second=90),names=names,provider=Provider(90),
        diarizer='pyannote',embedding='titanet')
    value=resolver.resolve(decision,event)
    record('own calibrated voice conflict releases spatial trust', value['known_profile_id']=='a' and
        set(resolver.seats.released)=={'a','b'} and value['identity']['seat']['voice_only_fallback'])
    calibrated.calibration['score_threshold']=.7  # Exact gate hash no longer matches.
    record('tampered gate never produces accepted name', resolver.resolve(decision,event)['known_profile_id'] is None)
    uncal=SimpleNamespace(calibration=dict(status='UNCALIBRATED_PERSONAL_DOMAIN'),receipt={},ids=['a'],namespace=None)
    resolver=module.BackendSeatResolver(Voice(uncal,True),seats=Seats(),names=names,provider=Provider(),
        diarizer='nemotron',embedding='titanet')
    record('uncalibrated Tita stays Unknown despite mocked voice confirmation', resolver.resolve(decision,event)['known_profile_id'] is None)
    record('ReDim calibrated namespace cannot become Tita calibration', not module.calibration_receipt(gallery('redimnet'),'titanet')['calibrated'])
    record('distinct track domains', module.track_domain('pyannote','titanet') != module.track_domain('nemotron','titanet'))
    captured=[]
    marker=object()
    def legacy(*args, **kwargs):captured.append((args,kwargs));return marker
    record('original Pyannote ReDim C088 factory preserved', module.make_resolver(
        SimpleNamespace(diarizer='pyannote',embedding='redimnet'),'assigned_hybrid',legacy_factory=legacy,
        settings='original-settings',gallery='original-gallery',seats='original-seats',names=names,
        provider='original-provider',tracker_config='original-tracker',clock=None) is marker and
        captured[0][0]==('original-settings','original-gallery'))
    report=dict(status='PASS_CHANGED_PURE_SEAT_ADAPTER',checks=checks,count=len(checks),
        source_pins=pins, synthetic_gallery_and_provider=True, native_tested=False, model_loaded=False,
        audio_started=False, source_backups_restored=True, no_C088_threshold_transfer=True)
    with open(Path(output)/'RESULT.json','x',encoding='utf-8') as stream:json.dump(report,stream,sort_keys=True)
    if sum(path.stat().st_size for path in Path(output).rglob('*') if path.is_file())>1048576:
        raise ValueError('Fixed 1 MiB total output allocation exceeded')
    print(json.dumps(dict(status=report['status'],checks=report['count'],native_tested=False)))


if __name__=='__main__':
    main()
