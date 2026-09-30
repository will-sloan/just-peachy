"""Native real-source bridge tests; README_LIVE_SOURCE_BRIDGE_V1.md."""
import hashlib
import json
from pathlib import Path
import time
from isolated_source_transport_v2 import IsolatedSource,SourceFault


CASES = [('drain_after_stop',[480]*6,16,True,'O0',None),
         ('stop_pending',[480]*96,128,False,'O0',None),
         ('callback_fault',[480]*12,16,False,'O0','LIVE_SOURCE_GAP'),
         ('raw_ring_overflow',[480]*5,4,False,'O0','LIVE_SOURCE_GAP'),
         ('oversized_callback',[480]*4,8,False,'O0','LIVE_SOURCE_GAP'),
         ('restore_mismatch',[480]*6,8,True,'O0','SOURCE_CLOSE_FAILED'),
         ('cancel_empty',[],4,False,'O0',None),
         ('short_tail',[480,3],4,True,'O0',None),
         ('tap_o1',[480]*6,8,True,'O1',None)]


def run(root,a):
    results=[]
    for index,(name,frames,capacity,prestop,tap,expected_fault) in enumerate(CASES):
        d=root/name;d.mkdir()
        cfg=dict(case=name,source_module='live_source_bridge_fixture_v1',source_factory='create',
                 source_wav=a['source_wav'],prototype=a['prototype'],case_directory=str(d),
                 frames=frames,capacity=capacity,prestop=prestop,tap=tap,epoch=index+1,backpressure_seconds=1)
        with (d/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
        src=IsolatedSource(d/'CONFIG.json');fault=None;count=0;began=time.monotonic()
        if name=='cancel_empty':src.stop()
        try:
            with (d/'AUDIO.f32').open('xb') as output,(d/'TRACE.jsonl').open('x') as trace:
                while src.terminal is None:
                    assert time.monotonic()-began<15
                    block=src.read(.02)
                    if block is None:continue
                    offset,audio,metadata,published,received=block
                    assert metadata['model_start_sample']==offset and metadata['epoch']==index+1
                    output.write(audio)
                    trace.write(json.dumps(dict(sequence=count,offset=offset,samples=len(audio)//4,
                        audio_sha256=hashlib.sha256(audio).hexdigest(),metadata=metadata,
                        published_ns=published,received_ns=received),separators=(',',':'))+'\n')
                    count+=1
                    if name=='stop_pending' and src.offset>=160 and not src.stop_sent:src.stop()
        except SourceFault as exc:fault=dict(code=exc.code,detail=exc.detail)
        finally:src.close()
        assert (fault['code'] if fault else None)==expected_fault,(name,fault)
        assert not src.forced_close and src.proc.returncode==(1 if expected_fault else 0)
        setup=json.loads((d/'RAW_SETUP.json').read_text());close=json.loads((d/'BRIDGE_CLOSE.json').read_text())
        accepted=sum(setup['accepted_frames'])
        assert src.offset==accepted//3 and close['bridge_native_frames']==accepted
        assert close['final_status']['pending_raw_blocks']==0 and close['stream_closed'] and close['lease_released']
        assert json.loads((d/'CLEANUP_CALLS.json').read_text())==['route_restore_with_clock_and_lease','stream_stop','stream_close']
        row=dict(case=name,accepted_native_frames=accepted,accepted_model_samples=src.offset,blocks=count,
                 audio_sha256=src.digest.hexdigest(),expected_fault=expected_fault,observed_fault=fault,
                 terminal=src.terminal,process_exit=src.proc.returncode,forced_close=src.forced_close,
                 elapsed_seconds=time.monotonic()-began,final_status=close['final_status'],original_stop_status=close['original_stop_status'])
        with (d/'CASE_RESULT.json').open('x') as f:json.dump(row,f,indent=2)
        results.append(row)
    return dict(status='COLLECTED_NATIVE_REAL_SOURCE_FAKE_CALLBACK_IPC_ONLY',cases=results,
                capture=False,models_loaded=False,hardware_startup_qualified=False,physical_restoration_qualified=False,
                combined_B01_qualified=False)
