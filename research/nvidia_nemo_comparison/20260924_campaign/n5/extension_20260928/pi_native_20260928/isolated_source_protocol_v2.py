"""Native model-free IPC cases; README_ISOLATED_SOURCE_V2.md."""
from array import array
import hashlib
import json
from pathlib import Path
import time
import wave
from isolated_source_transport_v2 import IsolatedSource, SourceFault, MAX_BLOCKS, MAX_BYTES


def run(root, admission):
    with wave.open(admission['source_wav'], 'rb') as wav:
        samples = array('h', wav.readframes(wav.getnframes()))
    expected = array('f', (x/32768 for x in samples)).tobytes()
    cases = [('full',715127,None),('repeat',715127,None),('empty',0,None),('tail',1281,None),
             ('paced_parent_stall',32000,None),('stop',715127,None),
             ('backpressure',715127,'BACKPRESSURE_TIMEOUT'),('source_fault',715127,'INPUT_STATUS_GAP'),
             ('discontinuity',715127,'SOURCE_DISCONTINUITY'),('malformed_bytes',715127,'MALFORMED_AUDIO_BYTES'),
             ('metadata_quota',715127,'METADATA_QUOTA'),('startup_failure',715127,'FIXTURE_STARTUP_FAILURE'),
             ('child_abrupt',715127,'CHILD_EOF_WITHOUT_TERMINAL')]
    results = []
    for index,(name,limit,expected_fault) in enumerate(cases):
        d = root/name
        d.mkdir()
        cfg = dict(case=name,source_module='isolated_source_fixture_v2',source_factory='create',
                   source_wav=admission['source_wav'],limit_samples=limit,epoch=index+1,
                   block_samples=160,backpressure_seconds=.12 if name=='backpressure' else 1,
                   paced=name=='paced_parent_stall')
        with (d/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
        src = IsolatedSource(d/'CONFIG.json')
        fault = None
        began = time.monotonic_ns()
        stalled = False
        trace_count = 0
        read_ns = max_gap_ns = 0
        prior_read = None
        try:
            with (d/'TRACE.jsonl').open('x') as log:
                while src.terminal is None:
                    if time.monotonic_ns()-began > 15_000_000_000:
                        raise AssertionError('case deadline exceeded')
                    if name=='backpressure' and not stalled:
                        # Wait until the child is initialized, then deliberately withhold ACKs.
                        while not (d/'CHILD_READY.json').exists():
                            assert time.monotonic_ns()-began<5_000_000_000
                            time.sleep(.002)
                        time.sleep(.4)
                        stalled = True
                    before = time.monotonic_ns()
                    block = src.read(.02)
                    read_ns += time.monotonic_ns()-before
                    if block is None:continue
                    offset,audio,meta,published,received = block
                    assert audio == expected[offset*4:offset*4+len(audio)]
                    assert meta['model_start_sample']==offset and meta['native_start_frame']==offset*3
                    assert meta['native_frames']==len(audio)//4*3 and meta['epoch']==index+1
                    assert meta['source_read_monotonic_ns']<=published<=received
                    if prior_read is not None:max_gap_ns=max(max_gap_ns,meta['source_read_monotonic_ns']-prior_read)
                    prior_read=meta['source_read_monotonic_ns']
                    row=dict(sequence=trace_count,offset=offset,samples=len(audio)//4,audio_sha256=hashlib.sha256(audio).hexdigest(),metadata=meta,published_ns=published,received_ns=received)
                    log.write(json.dumps(row,separators=(',',':'))+'\n')
                    trace_count+=1
                    if name=='paced_parent_stall' and src.offset>=3200 and not stalled:
                        # Deliberate parent Python work; child remains a separate process.
                        until=time.monotonic()+.2
                        while time.monotonic()<until:sum(range(200))
                        stalled=True
                    if name=='stop' and src.offset>=3200 and not src.stop_sent:src.stop()
        except SourceFault as exc:
            fault = dict(code=exc.code,detail=exc.detail)
        finally:
            src.close()
        assert (fault['code'] if fault else None)==expected_fault,(name,fault)
        assert not src.forced_close and src.proc.poll() is not None
        if name=='child_abrupt':assert src.proc.returncode==7 and src.terminal is None
        else:
            assert src.proc.returncode==(1 if fault else 0)
            assert src.terminal['high_blocks']<=MAX_BLOCKS and src.terminal['high_bytes']<=MAX_BYTES
            assert src.terminal['sent_samples']==src.offset
        if name in ['full','repeat','empty','tail','paced_parent_stall']:assert src.offset==limit
        if name=='stop':assert 3200<=src.offset<715127 and src.terminal['stopped']
        assert src.digest.hexdigest()==hashlib.sha256(expected[:src.offset*4]).hexdigest()
        try:src.read(0)
        except SourceFault as exc:assert exc.code=='READ_AFTER_CLOSE'
        else:raise AssertionError('post-close read accepted')
        result=dict(case=name,accepted_samples=src.offset,blocks=trace_count,audio_sha256=src.digest.hexdigest(),
                    expected_fault=expected_fault,observed_fault=fault,terminal=src.terminal,
                    process_exit=src.proc.returncode,forced_close=src.forced_close,elapsed_ns=time.monotonic_ns()-began,
                    read_wait_ns=read_ns,max_source_read_gap_ns=max_gap_ns,socket_bytes=src.socket_bytes,
                    post_close_rejected=True)
        with (d/'CASE_RESULT.json').open('x') as f:json.dump(result,f,indent=2)
        results.append(result)
    assert results[0]['audio_sha256']==results[1]['audio_sha256']
    return dict(status='COLLECTED_NATIVE_ISOLATED_SOURCE_FIXTURE_ONLY',cases=results,
                capture=False,models_loaded=False,application_integrated=False,live_fault_repaired=False)
