"""Small native archive budget fixtures; README_FIELD_ARCHIVE_BUDGET_V1.md."""
import json
import sys
import time
import types
from pathlib import Path
import field_dependencies_v2 as pins
from field_archive_budget_v1 import validate,digest,publish,DEFAULT


def run(root,a):
    pins.configure_output(root,a['target_output_max_bytes'])
    installed=Path(a['installed_release']);sys.path.insert(0,str(installed))
    from release_tools.runtime_lock import RuntimeLock
    derivation=json.loads((root/'ARCHIVE_BUDGET_DERIVATION_V1.json').read_text())
    assert pins.sha(installed/'app/sessions.py')==derivation['source_sha256']
    assert pins.sha(root/'archive_budget_v1/app/sessions.py')==derivation['derivative_sha256']
    package=types.ModuleType('app');package.__path__=[str(root/'archive_budget_v1/app'),str(installed/'app')];sys.modules['app']=package
    from app.sessions import EpochArchive,SessionStore,encoded
    from field_artifact_limits_v1 import load
    import numpy as np
    limits=load(installed/'config/artifact_limits.json',pins.sha(installed/'config/artifact_limits.json'))
    budget=validate(json.loads((root/'ARCHIVE_BUDGET_V1.json').read_text()));assert budget==DEFAULT
    cases=[]
    def save(name,**kw):
        v=dict(case=name,**kw);pins.exclusive(root/(name+'.json'),v);cases.append(v);return v
    def reject(name,fn):
        try:fn()
        except (ValueError,OSError,RuntimeError) as exc:save(name,rejected=True,error=type(exc).__name__+': '+str(exc))
        else:raise AssertionError('Missing rejection: '+name)
    bad=[dict(budget,metadata_input_bytes=True),dict(budget,metadata_input_bytes=16*1024**2+1),dict(budget,auxiliary_bytes=2*1024**2+1),dict(budget,control_file_bytes=65537),dict(budget,compact_index='sqlite'),dict(budget,extra=1),{k:v for k,v in budget.items() if k!='schema'}]
    for i,v in enumerate(bad):
        pins.exclusive(root/f'invalid-{i}.json',v)
        reject(f'invalid-{i}-rejection',lambda v=v:EpochArchive(root/f'must-not-publish-{i}',{},False,policy={'archive_budget':v}))
        assert not (root/f'must-not-publish-{i}').exists()
    policy=dict(archive_budget=budget,artifact_limits=limits,quota_mib=512,free_floor_mib=5120,record_bytes=65536)
    reject('oversized-initial',lambda:EpochArchive(root/'must-not-publish-control',{'synthetic':'x'*65536},False,policy=policy))
    reject('enhanced-unavailable',lambda:EpochArchive(root/'must-not-publish-enhanced',{'enhancement':{'route':'enhanced'}},False,policy=policy))
    assert not list(root.glob('must-not-publish*'))
    owner=RuntimeLock(root/'data','archive_budget_native_fixtures');raw=(root/'data/runtime.lock').read_bytes()
    def drained(archive):
        deadline=time.monotonic()+10
        while archive.queue.unfinished_tasks:
            if time.monotonic()>deadline:raise TimeoutError('Small fixture drain')
            time.sleep(.002)
    def receipt(archive,expected_error=None):
        snap=archive.close();meta=json.loads((archive.path/'epoch.json').read_text())
        assert not archive.thread.is_alive() and snap['closed'] and not snap['worker_alive']
        assert not snap['queue_bytes'] and not snap['queue_items']
        assert meta['worker_alive'] is False and meta['state']==('PARTIAL' if expected_error else 'CLOSED')
        assert (expected_error in str(snap['archive_error'])) if expected_error else snap['archive_error'] is None
        assert not (archive.path/'captions.sqlite').exists()
        auxiliary=sum((archive.path/n).stat().st_size for n in ['windows.jsonl','resources.jsonl','transforms.jsonl'] if (archive.path/n).exists())
        assert auxiliary==snap['auxiliary_bytes']<=archive.archive_budget['auxiliary_bytes']
        assert snap['metadata_bytes']<=archive.archive_budget['metadata_input_bytes']
        assert (archive.path/'epoch.json').stat().st_size<=archive.archive_budget['control_file_bytes']
        assert not list(archive.path.glob('.*.tmp'))
        return dict(snapshot=snap,accepted=archive.accepted,completed=archive.completed,metadata_sha256=pins.sha(archive.path/'epoch.json'),auxiliary_bytes=auxiliary)
    try:
        # Changed compact/no-index path: real store, one synthetic caption, tiny generated PCM, saved/reopened rows.
        store=SessionStore(root/'data',policy=policy);identifier=store.new(audio=True,consent=True,title='Synthetic budget fixture')
        archive=store.begin(identifier,{'synthetic_no_capture':True})
        try:
            archive.audio_block(0,np.zeros(160,dtype=np.float32))
            event=dict(kind='s6d_display',payload=dict(session_id='synthetic',caption_key='c1',utterance_id='u1',text='synthetic fixture',source_start_sec=0.,source_end_sec=.01))
            assert archive.offer('events',encoded(event));drained(archive)
            store.ended(identifier,archive);store.save(identifier)
            rows=store.rows(identifier);assert len(rows)==1 and rows[0]['text']=='synthetic fixture' and rows[0]['source_end_sample']==160
            save('compact-store-reopen',**receipt(archive),rows=1,generated_samples=160)
            path=store.folder(identifier)/'conversation.json';old=path.read_bytes()
            reject('conversation-control',lambda:store.update(identifier,synthetic='x'*65536))
            assert path.read_bytes()==old and not list(path.parent.glob('.*.tmp'))
        finally:
            if archive.thread.is_alive():archive.close()
        # Aux cap is a combined bound, independent of raw event accounting and journal compression.
        for name,small,kind,data,expected in [
            ('auxiliary',dict(budget,auxiliary_bytes=1024),'windows',b'x'*1025,'ARCHIVE_AUXILIARY_BYTE_LIMIT'),
            ('metadata',dict(budget,metadata_input_bytes=1024),'events',encoded(dict(kind='synthetic',payload='x'*1200)),'ARCHIVE_QUOTA_REACHED')]:
            archive=EpochArchive(root/(name+'-archive'),{'synthetic_no_capture':True},False,policy=dict(policy,archive_budget=small),delay_once=.05)
            try:
                # Wait for initial resource accounting, then queue a rejected block and its following tail.
                deadline=time.monotonic()+5
                while archive.auxiliary_bytes==0 and not archive.error:
                    assert time.monotonic()<deadline;time.sleep(.002)
                assert archive.error is None,archive.error
                assert archive.offer(kind,data);assert archive.offer('windows',b'tail')
                drained(archive);r=receipt(archive,expected)
                assert r['accepted']==2 and r['completed']==0
                again=archive.close();assert again['archive_error']==r['snapshot']['archive_error']
                save(name+'-failure',**r,repeat_close_preserves_error=True)
            finally:
                if archive.thread.is_alive():archive.close()
        # Exact serialized prewrite gate retains old control bytes and leaves no temporary files.
        control=root/'bounded-control.json';publish(control,{'v':1},16384);before=control.read_bytes()
        reject('control-prewrite',lambda:publish(control,{'v':'x'*16384},16384))
        assert control.read_bytes()==before and not list(root.glob('.bounded-control.json.*.tmp'))
        assert (root/'data/runtime.lock').read_bytes()==raw
    finally:owner.close()
    assert 'sounddevice' not in sys.modules and 'sherpa_onnx' not in sys.modules
    assert not (root/'data/runtime.lock').exists()
    pins.exclusive(root/'LEASE_CLOSED.json',dict(released=True,token=owner.token))
    return dict(status='PASS_NATIVE_SMALL_ARCHIVE_BUDGET_BOUNDARIES_ONLY',cases=cases,budget=budget,budget_sha256=digest(budget),
        capture=False,models=False,GUI=False,synthetic_audio_samples=160,full_maximum_files_exercised=False,
        physical_epoch_ceiling_bytes=limits['conversation_journal_bytes']+6*limits['pcm_max_frames']+44+budget['auxiliary_bytes']+2*budget['control_file_bytes'],
        original_release_unchanged=True,installed_integration=False,ownership_closed=True)
