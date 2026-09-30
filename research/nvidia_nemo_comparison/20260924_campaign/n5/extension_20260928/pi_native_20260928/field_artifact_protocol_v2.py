"""Native no-capture writer/archive boundary; README_FIELD_ARTIFACT_LIMITS_V2.md."""
import hashlib
import json
import sys
import time
import types
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def run(root, admission):
    import numpy as np
    from field_artifact_limits_v1 import load, validate, resolved, digest, planned_bytes
    limits = load(root/'ARTIFACT_LIMITS_V1.json', admission['artifact_config_file_sha256'])
    derivation = json.loads((root/'ARTIFACT_DERIVATION_V1.json').read_text())
    assert digest(limits) == derivation['artifact_limits_sha256']
    assert planned_bytes(limits) == 46034476
    installed = Path(admission['installed_release'])
    for name, row in derivation['files'].items():
        assert sha(installed/'app'/name) == row['source_sha256']
        assert sha(root/'artifact_limits_v1/app'/name) == row['derivative_sha256']
    package = types.ModuleType('app')
    package.__path__ = [str(root/'artifact_limits_v1/app'), str(installed/'app')]
    sys.modules['app'] = package
    sys.path.insert(0, str(installed))  # Exact installed release_tools namespace; app remains the explicit overlay.
    from app.bounded_live_artifacts_v1 import CompactJournal, PCM16Writer
    from app.app_bounded_artifacts_v1 import ArtifactAsyncText, compact_records
    from app.sessions import EpochArchive
    assert 'sounddevice' not in sys.modules and 'sherpa_onnx' not in sys.modules
    cases = []
    def save_case(name, value):
        row = dict(name=name, **value)
        with (root/(name+'.json')).open('x') as f: json.dump(row, f, indent=2)
        cases.append(row)
    def reject(name, function):
        try: function()
        except (ValueError, RuntimeError) as exc:
            save_case(name, dict(rejected=True, error=type(exc).__name__+': '+str(exc)))
        else: raise AssertionError('Expected rejection: '+name)
    def drained(writer):
        deadline = time.monotonic()+20
        while writer.queue.unfinished_tasks:
            if time.monotonic() >= deadline: raise TimeoutError('Synthetic writer did not drain')
            time.sleep(.002)
    # Fresh malformed configurations are retained separately, without publication.
    invalid = [dict(limits, native_journal_bytes=16*1024**2+1),
               dict(limits, conversation_journal_bytes=1023), dict(limits, pcm_max_frames=2080001),
               dict(limits, pcm_max_frames=True), dict(limits, sample_rate=True),
               dict(limits, schema='unknown'), dict(limits, unexpected=1),
               {k:v for k,v in limits.items() if k!='pcm_max_frames'}]
    for i, config in enumerate(invalid):
        fixture = root/f'invalid-contract-{i}.json'
        fixture.write_text(json.dumps(config))
        reject(f'contract-{i}', lambda config=config: validate(config))
    reject('wrong-config-hash', lambda: load(root/'ARTIFACT_LIMITS_V1.json', '0'*64))
    reject('legacy-journal-ceiling', lambda: CompactJournal(root/'must-not-exist-journal', 8*1024**2+1))
    reject('legacy-pcm-ceiling', lambda: PCM16Writer(root/'must-not-exist-pcm', 960001))
    reject('native-role-ceiling', lambda: ArtifactAsyncText(root/'must-not-exist-native', byte_limit=16*1024**2+1, artifact_limits=limits))
    reject('invalid-before-archive-publication', lambda: EpochArchive(root/'must-not-exist-archive', {}, False, policy={'artifact_limits':invalid[0]}))
    assert not list(root.glob('must-not-exist*'))
    # Actual native asynchronous adapter exceeds the old 8MiB ceiling.
    native = ArtifactAsyncText(root/'native-events.jsonl', artifact_limits=limits)
    try:
        for index in range(272):
            native.write(json.dumps(dict(kind='synthetic_boundary', index=index, payload='x'*32768)))
            drained(native)
        native.close()
    finally:
        if not native.closed: native.close()
    receipt = native.closure_receipt()
    assert receipt['clean'] and receipt['physical_sink_closed'] and receipt['accepted']==receipt['completed']==272
    assert 8*1024**2 < (root/'native-events.jsonl').stat().st_size < 16*1024**2
    assert sum(1 for _ in compact_records(root/'native-events.jsonl', artifact_limits=limits)) == 272
    reject('legacy-reader-ceiling', lambda: next(compact_records(root/'native-events.jsonl')))
    save_case('native-extended', receipt)
    # Actual EpochArchive, not a replacement PCM implementation. Synthetic samples only.
    policy = dict(artifact_limits=limits, quota_mib=512, free_floor_mib=5120,
                  audio_epoch_mib=16, metadata_epoch_mib=16, record_bytes=1024**2)
    archive = EpochArchive(root/'extended-archive', dict(synthetic_no_capture=True), True,
                           policy=policy, budget_bytes=24*1024**2)
    try:
        for start in range(0, 2080000, 16000):
            x = ((np.arange(start, start+16000, dtype=np.int32)%257)-128).astype(np.float32)/256
            archive.audio_block(start, x)
            assert archive.offer('events', (json.dumps(dict(kind='synthetic_boundary', index=start))+'\n').encode())
            drained(archive)
            assert archive.error is None, archive.error
        archive.close()
    finally:
        if archive.thread.is_alive(): archive.close()
    meta = json.loads((archive.path/'epoch.json').read_text())
    assert meta['state']=='CLOSED' and not meta['worker_alive'] and meta['closed']
    assert meta['source_samples']==meta['recorded_samples']==2080000
    assert meta['accepted_items']==meta['completed_items']==260
    assert not meta['archive_error'] and not meta['queue_items'] and not meta['queue_bytes']
    assert meta['artifact_limits_sha256']==digest(limits)
    save_case('archive-extended', meta)
    # Explicit byte failure retains every accepted/completed count and closed handle.
    small = dict(limits, native_journal_bytes=2048)
    failed = ArtifactAsyncText(root/'native-byte-failure.jsonl', artifact_limits=small, delay_once=.05)
    for index in range(4): failed.write(json.dumps(dict(kind='synthetic_failure', index=index, payload='x'*700)))
    reject('native-failed-close', failed.close)
    before = failed.closure_receipt()
    reject('native-repeated-failed-close', failed.close)
    assert failed.closure_receipt()==before and not before['clean'] and before['physical_sink_closed']
    assert before['accepted']==4 and before['completed']<4 and not before['worker_alive']
    assert before['pending_bytes']==0 and before['queue_items']==0
    save_case('native-byte-failure-closure', before)
    # Conversation byte failure: retain an exact accepted audio prefix and partial status.
    small = dict(limits, conversation_journal_bytes=1024)
    partial = EpochArchive(root/'archive-byte-failure', dict(synthetic_no_capture=True), True,
                           policy=dict(policy, artifact_limits=small))
    partial.audio_block(0, np.zeros(160, dtype=np.float32));drained(partial)
    for index in range(3):
        partial.offer('events', json.dumps(dict(kind='synthetic_failure', index=index, payload='x'*600)).encode())
    partial.close()
    meta = json.loads((partial.path/'epoch.json').read_text())
    assert meta['state']=='PARTIAL' and 'BYTE_LIMIT' in meta['archive_error']
    assert not meta['worker_alive'] and meta['closed'] and not meta['queue_items'] and not meta['queue_bytes']
    assert meta['accepted_items']>meta['completed_items'] and meta['recorded_samples']==160
    save_case('archive-byte-failure-closure', meta)
    # Frame failure is all-or-nothing for a block; retain unarchived source accounting.
    tiny = dict(limits, pcm_max_frames=320)
    partial = EpochArchive(root/'archive-frame-failure', dict(synthetic_no_capture=True), True,
                           policy=dict(policy, artifact_limits=tiny))
    partial.audio_block(0, np.zeros(160, dtype=np.float32));drained(partial)
    partial.audio_block(160, np.zeros(320, dtype=np.float32));partial.close()
    meta = json.loads((partial.path/'epoch.json').read_text())
    assert meta['state']=='PARTIAL' and 'FRAME_LIMIT' in meta['archive_error']
    assert meta['source_samples']==480 and meta['recorded_samples']==160
    assert meta['accepted_items']==2 and meta['completed_items']==1 and not meta['worker_alive']
    assert meta['artifact_metrics']['audio']['status']=='FRAME_LIMIT'
    save_case('archive-frame-failure-closure', meta)
    assert all(sha(installed/x)==h for x,h in admission['installed_files'].items())
    assert not any(t.name in ('bounded-event-journal','proto-session-archive') for t in __import__('threading').enumerate())
    assert 'sounddevice' not in sys.modules and 'sherpa_onnx' not in sys.modules
    return dict(status='PASS_EXPLICIT_ARTIFACT_WRITERS_AND_JOINED_PARTIAL_FINALIZATION',
                cases=len(cases), rejected=sum(bool(x.get('rejected')) for x in cases),
                native=receipt, extended_archive_samples=2080000, original_release_unchanged=True,
                models_loaded=False, capture=False, gui=False, synthetic=True,
                pipeline_wiring='prepared_only_not_imported_or_executed', installed_entry='NOT_QUALIFIED',
                config_sha256=digest(limits), planned_artifact_maximum_bytes=planned_bytes(limits))
