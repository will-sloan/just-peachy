"""Native startup/facade lifecycle without device I/O; README_SOURCE_STARTUP_V1.md."""
from dataclasses import asdict
import hashlib,json,time
from isolated_live_facade_v1 import IsolatedLiveFacade
from isolated_source_transport_v2 import SourceFault


def run(root,a):
    cases=[]
    for name,expected in [('stop_pending',None),('empty_stop',None),('callback_fault','LIVE_SOURCE_GAP'),('restore_failure','SOURCE_CLOSE_FAILED'),('start_failure','LiveAudioError')]:
        d=root/name;d.mkdir()
        cfg=dict(case=name,source_module='source_startup_fixture_v1',source_factory='create',capture=False,
                 prototype=a['prototype'],source_wav=a['source_wav'],case_directory=str(d),backpressure_seconds=1)
        with (d/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
        facade=IsolatedLiveFacade(d/'CONFIG.json',a['prototype']);fault=None;invalid=0;count=0
        try:facade.read(0)
        except SourceFault as e:assert e.code=='FACADE_READ_STATE';invalid+=1
        try:
            metadata=facade.start()
            assert metadata['endpoint']['name']=='XMOS_FAKE_ONLY (hw:7,1)' and metadata['actual_stream_rate']==48000
            try:facade.start()
            except SourceFault as e:assert e.code=='FACADE_START_STATE';invalid+=1
            try:facade.finalize()
            except SourceFault as e:assert e.code=='FACADE_NOT_DRAINED';invalid+=1
            if name=='empty_stop':facade.request_stop()
            began=time.monotonic()
            with (d/'AUDIO.f32').open('xb') as audio,(d/'TRACE.jsonl').open('x') as trace:
                while facade.terminal is None:
                    assert time.monotonic()-began<10
                    item=facade.read(.02)
                    if item is None:continue
                    block,ipc=item;raw=block.audio.astype('<f4',copy=False).tobytes();audio.write(raw)
                    meta=asdict(block);del meta['audio'];trace.write(json.dumps(dict(metadata=meta,ipc=ipc,audio_sha256=hashlib.sha256(raw).hexdigest(),samples=len(block.audio)))+'\n')
                    count+=1
                    if name in ('stop_pending','restore_failure') and count==3:facade.request_stop()
        except SourceFault as exc:fault=dict(code=exc.code,detail=exc.detail)
        assert (fault['code'] if fault else None)==expected,(name,fault)
        assert facade.terminal is not None
        final=facade.finalize()
        assert final['child_exit']==int(expected is not None) and not final['forced_close']
        for action in [lambda:facade.read(0),facade.request_stop,facade.finalize]:
            try:action()
            except SourceFault:invalid+=1
            else:raise AssertionError('Closed facade accepted action')
        expected_samples=0 if name in ('empty_stop','start_failure') else (960 if name=='callback_fault' else 15360)
        assert facade.delivered==expected_samples
        row=dict(case=name,observed_fault=fault,expected_fault=expected,blocks=count,invalid_calls_rejected=invalid,
                 delivered_samples=facade.delivered,native_frames=facade.native_frames,final=final)
        with (d/'CASE_RESULT.json').open('x') as f:json.dump(row,f,indent=2)
        cases.append(row)
    return dict(status='COLLECTED_NATIVE_SOURCE_STARTUP_FACADE_FAKE_HARDWARE_ONLY',cases=cases,capture=False,
                models_loaded=False,hardware_startup_qualified=False,controller_integrated=False,live_B01_qualified=False)
