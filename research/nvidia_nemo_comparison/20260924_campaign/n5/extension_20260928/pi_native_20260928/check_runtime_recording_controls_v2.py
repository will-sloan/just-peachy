"""Focused optional-recording check; README_RUNTIME_RECORDING_CONTROLS_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,hashlib,json,sys,types,zipfile
from pathlib import Path
from datetime import datetime,timezone


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('private','installed','scope','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    (a.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    scope=json.loads(a.scope.read_bytes())
    assert datetime.now(timezone.utc)<datetime.fromisoformat(scope['expires_utc'])
    assert sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())+262144<scope['maximum_bytes']
    from field_runtime_recording_controls_v2 import derive,request
    assert request(False,False) is False and request(True,True) is True
    rejects=[]
    def reject(label,fn):
        try:fn()
        except (ValueError,KeyError,AssertionError):rejects.append(label)
        else:raise AssertionError('Required rejection '+label)
    for audio,consent in [(False,True),(True,False),(0,False),(True,1)]:
        reject('selection-'+repr((audio,consent)),lambda a=audio,c=consent:request(a,c))
    common=a.private/'field-runtime-v8-install/stage-backup/field-runtime-v8-profiles/COMMON_BUNDLE.json'
    raw=common.read_bytes();changed,review=derive(raw)
    files={n:base64.b64decode(b,validate=True) for n,b in json.loads(changed)['files'].items()}
    sys.path[:0]=[str(a.installed),str(a.installed/'vendor'),str(a.installed/'native')]
    module=types.ModuleType('checked_optional_transfer');module.__file__='<changed-transfer>'
    exec(compile(files['code/field_transfer_v2.py'],module.__file__,'exec'),module.__dict__)
    installed=(a.installed/'native/field_archive_v3.py').read_bytes()
    transfer=module.derive(installed,hashlib.sha256(installed).hexdigest())
    # The installed journal is a RAM ring even when its path has an audio suffix.
    from app.buffers import MemoryJournal
    import numpy as np
    memory_path=a.output/'must-not-exist.pcm16'
    journal=MemoryJournal(memory_path,reserve_sec=1);journal.append(np.zeros(160,dtype=np.float32));journal.finish()
    assert len(journal.read(0,160))==160 and not memory_path.exists()
    # Existing audio-off producer keeps sample clocks and offers no audio bytes.
    from app.sessions import EpochArchive
    archive=EpochArchive.__new__(EpochArchive);archive.audio=False;archive.source_samples=0
    archive.offer=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Audio offered while Off'))
    archive.fail=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Unexpected source failure'))
    archive._audio_block(0,np.zeros(160,dtype=np.float32));assert archive.source_samples==160
    original=next((a.private/'field-runtime-v8-offload-v5/tree/field-operator-sessions-v232/recordings/slot-01/data/conversations').iterdir())
    conversation=json.loads((original/'conversation.json').read_bytes())
    ep=conversation['epochs'][0];epoch=json.loads((original/'epochs'/ep/'epoch.json').read_bytes())
    conversation['audio_requested']=False;conversation['consent']['audio_storage']=False
    epoch.update(audio_enabled=False,master=None,listening_copy=None,audio_sha256=None,audio_bytes=0,
        recorded_samples=0,source_samples=160,audio_recording=False)
    def fixture(name,mutate=None,extra_audio=False,bad_footer=False):
        folder=a.output/name/conversation['id'];dest=folder/'epochs'/ep;dest.mkdir(parents=True)
        c=json.loads(json.dumps(conversation));e=json.loads(json.dumps(epoch))
        if mutate:mutate(c,e)
        (folder/'conversation.json').write_text(json.dumps(c))
        (dest/'epoch.json').write_text(json.dumps(e))
        (dest/'events.jsonl').write_text(json.dumps(dict(format='footer',count=0,status='SOURCE_FAILURE' if bad_footer else 'COMPLETE'))+'\n')
        for member in ('resources.jsonl','windows.jsonl'):(dest/member).write_bytes(b'')
        if extra_audio:(dest/'model_input.f32le').write_bytes(b'')
        return folder
    folder=fixture('off');result=transfer.validate_folder(folder,conversation['id'])
    assert result['epochs']=={ep:160} and result['raw_rows']==0
    members=transfer.regular_tree(folder);assert len(members)==5
    target=a.output/'off.zip'
    pins={n:dict(bytes=size,sha256=module.sha(folder/n)) for n,size in members.items()}
    with zipfile.ZipFile(target,'x',zipfile.ZIP_STORED) as z:
        z.writestr(transfer.MANIFEST,json.dumps(dict(schema=transfer.SCHEMA,identifier=conversation['id'],files=pins)))
        for name in pins:z.write(folder/name,name)
    verified=module.verify_zip(transfer,target,folder,conversation['id']);assert len(verified['files'])==5
    cases=[('consent-mismatch',lambda c,e:c['consent'].update(audio_storage=True)),
        ('audio-bool-type',lambda c,e:c.update(audio_requested=0)),
        ('recorded-audio',lambda c,e:e.update(recorded_samples=1)),
        ('audio-hash',lambda c,e:e.update(audio_sha256='0'*64)),
        ('source-bool',lambda c,e:e.update(source_samples=True)),
        ('source-overflow',lambda c,e:e.update(source_samples=2080001))]
    for name,mutate in cases:
        path=fixture(name,mutate);reject(name,lambda p=path:transfer.validate_folder(p,conversation['id']))
    for name,kwargs in [('unexpected-audio',dict(extra_audio=True)),('incomplete-events',dict(bad_footer=True))]:
        path=fixture(name,**kwargs);reject(name,lambda p=path:transfer.validate_folder(p,conversation['id']))
    assert common.read_bytes()==raw
    assert datetime.now(timezone.utc)<datetime.fromisoformat(scope['expires_utc'])
    assert sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())<scope['maximum_bytes']
    report=dict(status='PASS_CHANGED_OPTIONAL_RECORDING_HOST',positive_groups=3,rejects=rejects,derivation=review,
        fixture='SYNTHETIC audio-off metadata/empty complete event stream; existing installed decoder and RAM journal',
        audio_off_file_count=5,zip_members=6,native_executed=False,native_privacy_or_gui_proven=False)
    (a.output/'RESULT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(status=report['status'],positive_groups=3,rejects=len(rejects),bundle_sha256=review['bundle_sha256'])))


if __name__=='__main__':main()
