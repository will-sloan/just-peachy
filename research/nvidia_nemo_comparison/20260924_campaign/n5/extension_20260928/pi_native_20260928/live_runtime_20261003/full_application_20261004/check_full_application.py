"""Focused host restoration checks, without Pi access. See README.md."""
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types
import uuid


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 1<<14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    sys.dont_write_bytecode = True
    source = Path(__file__).resolve().parent
    private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')
    output = private/('full-application-check-'+uuid.uuid4().hex)
    output.mkdir()
    def write(name, value):
        (output/name).write_bytes(json.dumps(value, sort_keys=True, allow_nan=False).encode())
    write('REGISTERED_OWNER.json', dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(), cpu=14, affinity_mask=1<<14,
        creation_filetime=stamps[0].value, create_time=(stamps[0].value-116444736000000000)/10000000))
    started = time.time()
    write('HOST_SCOPE.json', dict(issued_unix=started, maximum_seconds=600,
        maximum_bytes=2*1024**2, native_action=False, purpose='changed full application regression checks'))
    files = []
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.suffix not in ('.py','.md'):
            raise ValueError('Only flat reviewed source/README inputs permitted')
        raw = path.read_bytes()
        for directory in ('source-backup', 'source-restore'):
            (output/directory).mkdir(exist_ok=True)
            shutil.copyfile(path, output/directory/path.name)
            if (output/directory/path.name).read_bytes()!=raw:
                raise OSError('Independent source restore differs')
        files.append(dict(path=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    write('SOURCE_BACKUP_AND_RESTORE.json', dict(files=files, closed_unix=time.time()))
    if sum(r['bytes'] for r in files)*2 > 1800*1024:
        raise ValueError('Source backup/restore allocation cannot fit host scope')
    compiled = []
    for path in source.glob('*.py'):
        compile(path.read_bytes(), str(path), 'exec')
        compiled.append(path.name)
    base = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/classic-package-repair-3b5aac854f7b454686eb770ffe218054/package')
    sys.path[:0] = [str(source), str(base)]
    from application_contract import MODES, default, validate, capacity_seconds
    from profiles import RuntimeSelection, SessionPolicy
    from storage import SessionStore, StoragePolicy
    from runtime_support import digest
    selection = RuntimeSelection()
    person = str(uuid.uuid4())
    accepts = 0
    rejects = 0
    for mode in MODES:
        intent = default('redimnet')
        intent['mode'] = mode
        if 'selected' in mode or mode=='assigned_hybrid':
            intent['selected_ids']=[person]
        if mode.startswith('assigned_'):
            intent['selected_ids']=[person]
            intent['seating']=dict(valid=True, rows=[dict(person_id=person,angle_deg=90,tolerance_deg=25)])
        validate(intent, selection, people=[person]); accepts+=1
    manual = SessionPolicy(maximum_session_seconds=7200, manual_stop=True)
    manual.validate()
    try: SessionPolicy(maximum_session_seconds=7200).validate()
    except ValueError: rejects+=1
    else: raise AssertionError('Normal finite old policy must not silently admit a soak')
    assert capacity_seconds(20*1024**3,5*1024**3,raw_bytes_per_second=256000)>300
    for bad in (dict(default('redimnet'), tap='O1'), dict(default('redimnet'), selected_ids=[True]),
            dict(default('redimnet'), strict=True), dict(default('redimnet'), extra=True)):
        try: validate(bad,selection)
        except (ValueError,TypeError): rejects+=1
        else: raise AssertionError('Malformed application intent accepted')
    for backend in (RuntimeSelection(diarizer='nemotron', nemotron_profile='chunk52'),
            RuntimeSelection(embedding='titanet'), RuntimeSelection(embedding='anonymous')):
        bad=dict(default(backend.embedding), mode='assigned_hybrid',selected_ids=[person],
            seating=dict(valid=True,rows=[dict(person_id=person,angle_deg=90,tolerance_deg=25)]))
        try: validate(bad, backend)
        except ValueError: rejects+=1
        else: raise AssertionError('Unbound seat resolver silently changed backend calibration')
    # Original caption-loop regression: use actual recovered source, pure imports,
    # synthetic file binding and synthetic speaker states; no model execution.
    original = Path('G:/Just_Peachy_N1/20260924_campaign/worktree/prototype')
    fixture = output/'projection-fixture'
    (fixture/'app').mkdir(parents=True)
    original_files = ('controller.py','mode_policy.py','casing.py','text_assistance.py')
    for name in original_files:
        shutil.copyfile(original/'app'/name, fixture/'app'/name)
    manifest=dict(files=[dict(path='app/'+name,sha256=digest(fixture/'app'/name)) for name in original_files])
    (fixture/'RELEASE_MANIFEST.json').write_text(json.dumps(manifest))
    app=types.ModuleType('app');app.__path__=[str(fixture/'app')];sys.modules['app']=app
    paths=types.ModuleType('app.paths');paths.read_json=lambda p:json.loads(Path(p).read_text());paths.atomic_json=lambda *a:None
    sys.modules['app.paths']=paths
    from retained_caption_projection import load
    project=load(dict(installed_release=str(fixture),installed_manifest_sha256=digest(fixture/'RELEASE_MANIFEST.json')))
    intent=default('redimnet')
    parts=[dict(segment_id='first',raw_text='hello',known_profile_id=person,naming_state='confirmed',
        anonymous_label='Speaker 1',ownership_state='supported_history',source_start_sec=0,source_end_sec=1,token_range=[0,1]),
        dict(segment_id='second',raw_text='there',naming_state='collecting',
            anonymous_label='Speaker 2',ownership_state='pending',source_start_sec=1,source_end_sec=2,token_range=[1,2])]
    row=dict(caption_key='u1',utterance_id='u1',text='hello there',segments=parts,source_start_sec=0,source_end_sec=2)
    result=project(row,intent,[dict(id=person,name='Synthetic person')])
    assert [r['label'] for r in result]==['Synthetic person','Speaker 2']
    assert [r['raw_asr_text'] for r in result]==['hello','there']
    intent['mode']='enrolled_names'
    assert project(row,intent,[dict(id=person,name='Synthetic person')])[1]['label']=='Unknown'
    # Actual storage semantics with synthetic non-media session metadata.
    store=SessionStore(output/'store-fixture',StoragePolicy(reserve_bytes=1,reserve_fraction=0))
    spec=dict(duration_seconds=1, sample_rate=16000,mode='processed',metadata_reserve_bytes=1024**2)
    spool=store.begin(spec)
    sid=spool.session_id
    spool.stop()
    store.keep(sid)
    store.rename(sid,'Synthetic renamed session')
    assert store.read(sid)['spec']['title']=='Synthetic renamed session'
    store.delete(sid,confirm=True)
    store.close()
    summary=dict(status='PASS_CHANGED_HOST_FULL_APPLICATION_CONTRACT_PROJECTION_STORAGE',
        compiled=compiled, application_modes_accepted=accepts, rejected_inputs=rejects,
        native_tested=False, gui_tested=False, enrollment_capture_tested=False,
        projection_source_sha256=digest(original/'app/controller.py'), finished_unix=time.time())
    write('RESULT.json',summary)
    if time.time()-started>600 or sum(p.stat().st_size for p in output.rglob('*') if p.is_file())>2*1024**2:
        raise RuntimeError('Host scope exceeded; retain all bytes and failed receipt')
    print(json.dumps(dict(output=str(output),result=summary)))


if __name__=='__main__':
    main()
