"""Native application integration protocol; README_APP_BOUNDED_ARTIFACTS_V1.md."""
import hashlib
import importlib.util
import json
import time
import wave
from pathlib import Path
import sys
import numpy as np


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def run_protocol(root, admission):
    from prepare_app_artifacts_v1 import prepare
    prototype=root/'prototype'
    manifest=prepare(admission['prototype'],prototype,root)
    sys.path[:0]=[str(prototype),str(prototype/'vendor')]
    from app.pipeline import PrototypeEngine
    from app.sessions import SessionStore, encoded, recover_index
    from app.app_bounded_artifacts_v1 import ArtifactAsyncText, compact_records
    result=dict(integrated_writer_reader=True,capture=False,models_loaded=False,callback_repaired=False,derivative_files=manifest)
    # Actual engine factory, actual bounded queue/writer, all original event fields.
    engine=PrototypeEngine.__new__(PrototypeEngine);engine.writer_delay=0;engine.text_writers=[]
    path=root/'engine'/'events.jsonl';path.parent.mkdir()
    writer=engine._open_journal_text(path);begin=time.perf_counter()
    for line in Path(admission['journals'][0]['path']).open():
        writer.write(line)
        # Model-free deterministic backpressure; not a live throughput claim.
        writer.queue.join();writer.flush()
    writer.close()
    assert isinstance(writer,ArtifactAsyncText) and not writer.thread.is_alive()
    assert writer.accepted==writer.completed==2628 and writer.pending_bytes==0
    result['engine_writer']=dict(seconds=time.perf_counter()-begin,accepted=writer.accepted,completed=writer.completed,**writer.sink.metrics())
    for old,new in zip(Path(admission['journals'][0]['path']).open(),compact_records(path),strict=True):assert json.loads(old)==new
    # Actual archive queue writes and SessionStore reopening, with exact PCM master.
    store=SessionStore(root/'data',dict(quota_mib=48,draft_limit=10,free_floor_mib=5120))
    identifier=store.new(audio=True,consent=True,title='Private retained-input integration')
    archive=store.begin(identifier,dict(conversation_id=identifier,enhancement=dict(route='bypass',asr_stream='input',identity_stream='input')))
    for line in Path(admission['journals'][1]['path']).open('rb'):
        assert archive.offer('events',line)
        archive.queue.join()
        assert not archive.error,archive.error
    with wave.open(admission['source_wav'],'rb') as src:
        raw=src.readframes(src.getnframes())
    samples=np.frombuffer(raw,'<i2').astype(np.float32)/32768
    for off in range(0,len(samples),3200):
        archive.audio_block(off,samples[off:off+3200]);archive.queue.join()
        assert not archive.error,archive.error
    receipt=store.ended(identifier,archive)
    assert receipt['closed'] and not receipt['archive_error'] and receipt['queue_items']==receipt['queue_bytes']==0
    assert receipt['recorded_samples']==receipt['source_samples']==715127
    folder=archive.path
    assert (folder/'model_input.f32le').read_bytes()==samples.astype('<f4').tobytes()
    with wave.open(str(folder/'model_input.wav'),'rb') as got:assert got.readframes(715127)==raw and got.getnframes()==715127
    rows=store.rows(identifier);assert rows
    assert store.rows(identifier,3)==rows[-3:]
    store.save(identifier)
    reopened=SessionStore(root/'data',dict(quota_mib=48,free_floor_mib=5120))
    assert reopened.rows(identifier)==rows
    assert np.array_equal(reopened.audio_slice(identifier,folder.name,0,16000),samples[:16000])
    reopened.export(identifier,root/'text-export.zip',include_audio=False,consent=True)
    # Real legacy reader on a fresh small fixture, never opens original for mutation.
    legacy_id=store.new(audio=False,title='Legacy reader control')
    legacy=store.begin(legacy_id,dict(conversation_id=legacy_id));store.ended(legacy_id,legacy)
    # Change only this newly generated control to a legacy fixture and recover its real index.
    captions={};formats={}
    for line in Path(admission['journals'][1]['path']).open():
        event=json.loads(line);kind=event.get('kind')
        if kind not in ('s6d_display','prototype_formatted_text'):continue
        value=event['payload'];key=value.get('caption_key') or str(value.get('utterance_id'))
        (captions if kind=='s6d_display' else formats)[key]=event
    legacy_path=root/'legacy-control';legacy_path.mkdir()
    events=legacy_path/'events.jsonl'
    with events.open('xb') as out:
        for event in list(captions.values())+list(formats.values()):out.write(encoded(event))
    recover_index(legacy_path)
    # Use a separate legacy conversation fixture instead of rewriting a closed epoch.
    import shutil,uuid
    eid=uuid.uuid4().hex;newpath=store.folder(legacy_id)/'epochs'/eid
    shutil.copytree(legacy_path,newpath)
    (newpath/'epoch.json').write_text(json.dumps(dict(state='CLOSED',closed=True,audio_enabled=False)))
    store.update(legacy_id,epochs=store.metadata(legacy_id)['epochs']+[eid])
    old_rows=store.rows(legacy_id)
    def norm(items):
        return [{k:v for k,v in row.items() if k not in ('archive_epoch_id','archive_conversation_id')} for row in items]
    assert norm(rows)==norm(old_rows)
    # Actual app partial archive path: rejects oversized offered record, closes and reopens retained prefix.
    partial_id=store.new(audio=False,title='Explicit partial control')
    partial=store.begin(partial_id,dict(conversation_id=partial_id))
    event=next(iter(captions.values()))
    assert partial.offer('events',encoded(event));partial.queue.join()
    assert not partial.offer('events',b'x'*(4*1024**2+1))
    p_receipt=store.ended(partial_id,partial)
    assert p_receipt['archive_error'] and p_receipt['closed']
    assert len(store.rows(partial_id))==1
    # Actual queued event byte cap produces visible error and retained prefix/footer.
    failed=ArtifactAsyncText(root/'limited-events.jsonl',byte_limit=1024)
    for _ in range(30):
        try:failed.write(json.dumps(dict(kind='bound',payload='x'*220)));failed.queue.join();failed.flush()
        except RuntimeError:break
    else:raise AssertionError('Actual async cap did not fail')
    try:failed.close()
    except RuntimeError:pass
    else:raise AssertionError('Async failure hidden at close')
    assert not failed.thread.is_alive() and failed.sink.closed and failed.sink.bytes<=1024
    assert failed.sink.status=='BYTE_LIMIT'
    (root/'ROWS.json').write_text(json.dumps(rows,ensure_ascii=False))
    result.update(status='NATIVE_APP_ARTIFACT_INTEGRATION_REVIEW_REQUIRED',conversation_id=identifier,epoch=folder.name,
        rows=len(rows),row_digest=digest(norm(rows)),legacy_row_digest=digest(norm(old_rows)),archive=receipt,
        pcm_frames=715127,partial_archive=p_receipt,async_limit=failed.sink.metrics(),all_workers_closed=True,
        event_journal=str(path.relative_to(root)),archive_path=str(folder.relative_to(root)),numerical_models_run=False)
    return result
