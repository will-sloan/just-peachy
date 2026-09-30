"""Bounded 12-second isolated quiet route, deliberate consumer pause; README_SOURCE_QUIET_V1.md."""
from dataclasses import fields
import hashlib
import json
import time
from isolated_live_facade_v2 import IsolatedLiveFacade
from isolated_source_transport_v3 import SourceFault
from bounded_live_artifacts_v1 import PCM16Writer


def run(root, a):
    d = root/'quiet'; d.mkdir()
    cfg = dict(source_module='source_quiet_factory_v1', source_factory='create',
               capture=True, quiet_only=True, prototype=a['prototype'],
               case_directory=str(d), backpressure_seconds=1,
               authority=str(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'),
               alsa_config=str(root/'alsa_hw_only_v1.conf'), live_config=str(root/'LIVE_CONFIG_BACKUP.json'))
    with (d/'CONFIG.json').open('x') as f: json.dump(cfg, f, indent=2)
    facade = IsolatedLiveFacade(d/'CONFIG.json', a['prototype'])
    fault = None; count = 0; paused = False; stop_ns = None; pause = None
    pcm = PCM16Writer(d/'microphone.wav', max_frames=320000)
    began = time.monotonic()
    with (d/'AUDIO.f32').open('xb') as audio, (d/'TRACE.jsonl').open('x') as trace:
        def retain(item):
            nonlocal count
            if item is None: return
            block, ipc = item
            if facade.delivered > 320000: raise SourceFault('CAPTURE_FRAME_QUOTA')
            raw = block.audio.astype('<f4', copy=False).tobytes()
            pcm.write_float32(block.audio, source_start_frame=block.model_start_sample)
            audio.write(raw)
            meta = {f.name:getattr(block, f.name) for f in fields(block) if f.name != 'audio'}
            line = json.dumps(dict(metadata=meta, ipc=ipc, audio_sha256=hashlib.sha256(raw).hexdigest(), samples=len(block.audio)))+'\n'
            assert len(line.encode()) < 2048 and trace.tell()+len(line.encode()) < 4*1024**2
            trace.write(line); count += 1
        try:
            metadata = facade.start()
            assert metadata['actual_stream_rate'] == 48000
            deadline = time.monotonic()+20
            while facade.terminal is None:
                if time.monotonic()>deadline and stop_ns is None:
                    raise SourceFault('CAPTURE_WALL_BOUND')
                retain(facade.read(.02))
                if facade.delivered>=80000 and not paused:
                    pause_begin=time.monotonic_ns(); time.sleep(.2)
                    pause=dict(begin_ns=pause_begin,end_ns=time.monotonic_ns()); paused=True
                if facade.delivered>=192000 and stop_ns is None:
                    stop_ns=time.monotonic_ns(); facade.request_stop()
                if stop_ns and time.monotonic_ns()-stop_ns>45_000_000_000:
                    raise SourceFault('STOP_DRAIN_TIMEOUT')
        except Exception as exc:
            fault=dict(code=getattr(exc,'code',type(exc).__name__), detail=getattr(exc,'detail',{'message':str(exc)[:512]}))
        finally:
            if facade.transport is not None and facade.terminal is None:
                try:
                    facade.request_stop(); end=time.monotonic()+45
                    while facade.terminal is None and time.monotonic()<end:
                        retain(facade.read(.02))
                except Exception as exc:
                    fault=fault or dict(code=getattr(exc,'code',type(exc).__name__),detail={'message':str(exc)[:512]})
            pcm.close('SOURCE_FAILURE' if fault else 'COMPLETE')
    final = facade.finalize() if facade.terminal is not None else None
    if final is None:
        raise SourceFault('SOURCE_NO_TERMINAL',fault)
    result = dict(status='COLLECTED_ISOLATED_ACTUAL_QUIET_SOURCE_ONLY' if not fault else 'COLLECTED_ISOLATED_QUIET_FAILURE_ONLY',
                  capture=True,models_loaded=False,controller_integrated=False,live_B01_qualified=False,
                  fault=fault,blocks=count,delivered_samples=facade.delivered,native_frames=facade.native_frames,
                  final=final,consumer_pause=pause,stop_requested_ns=stop_ns,pcm=pcm.metrics(),protocol_seconds=time.monotonic()-began)
    if not fault:
        assert 192000<=facade.delivered<=320000 and final['child_exit']==0 and paused
    return result
