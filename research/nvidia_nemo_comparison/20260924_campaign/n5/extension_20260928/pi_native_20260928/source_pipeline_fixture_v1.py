"""Invoke original source.start with fake PortAudio/control; README_SOURCE_PIPELINE_V1.md."""
import json
import time
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import wave


def create(cfg):
    assert cfg['capture'] is False and cfg['source_factory']=='create'
    prototype=Path(cfg['prototype']);sys.path[:0]=[str(prototype),str(prototype/'vendor')]
    import numpy as np
    from app import live_audio as L
    from live_source_bridge_v2 import LiveSourceBridge
    directory=Path(cfg['case_directory']);calls=[];source=None
    def record():
        with (directory/'STARTUP_CALLS.json').open('x') as f:json.dump(calls,f)
    class Abort(Exception):pass
    class Flags:
        def __init__(self,bits):
            self._flags=bits
            for i,name in enumerate(('input_underflow','input_overflow','output_underflow','output_overflow','priming_output')):setattr(self,name,bool(bits&(1<<i)))
        def __bool__(self):return bool(self._flags)
    class Stream:
        def __init__(self,**kw):
            assert kw['device']==7 and kw['channels']==2 and kw['samplerate']==48000 and kw['blocksize']==480
            self.callback=kw['callback'];self.closed=False;self.active=False;self.latency=.001;self.samplerate=48000
            calls.append('construct_input_stream')
        def start(self):
            self.active=True;calls.append('stream_start')
            self.callback(np.zeros((480,2),np.float32),480,SimpleNamespace(inputBufferAdcTime=1.,currentTime=1.01),Flags(0))
        def stop(self):calls.append('stream_stop');self.active=False
        def close(self):calls.append('stream_close');self.closed=True
    class Control:
        def __init__(self,config):self.receipts=[];calls.append('construct_control')
        def diagnostic_values(self):return {}
    class Route:
        def __init__(self,control,config):pass
        def apply(self):
            assert source.stream.active and source.lease.handle is not None;calls.append('route_apply_with_clock_and_lease')
            if cfg['case']=='start_failure':raise L.LiveAudioError('INJECTED_ROUTE_START_FAILURE')
            return {'fixture':True,'tap':'O0'}
        def restore(self):
            assert source.stream.active and source.lease.handle is not None;calls.append('route_restore_with_clock_and_lease')
            return {'AEC_ASROUTONOFF':'MISMATCH' if cfg['case']=='restore_failure' else 'RESTORED'}
    class Beam:
        def __init__(self,*args,**kwargs):pass
        def start(self):calls.append('beam_start')
        def stop(self,timeout):calls.append('beam_stop');return True
    def mark(name):calls.append(name)
    fake=SimpleNamespace(CallbackAbort=Abort,InputStream=Stream,
        _terminate=lambda:mark('pa_terminate'),_initialize=lambda:mark('pa_initialize'),
        query_hostapis=lambda:[{'name':'ALSA'}],query_devices=lambda:[dict(index=7,name='XMOS_FAKE_ONLY (hw:7,1)',hostapi=0,max_input_channels=8)],
        check_input_settings=lambda **kw:mark('check_input_settings'))
    assert 'sounddevice' not in sys.modules
    sys.modules['sounddevice']=fake
    sys.modules['app.beam_diagnostics']=SimpleNamespace(BeamDiagnostics=Beam)
    L.HostControl=Control;L.LiveRoute=Route
    config=L.LiveConfig(host_executable='/not-executed',lease_path=str(directory/'fake-device.lock'),hostapi='ALSA',endpoint_name='XMOS_FAKE_ONLY (hw:7,1)',control_protocol='i2c',reserve_seconds=2)
    source=L.XVFLiveSource(config)
    try:metadata=source.start(consent=True)
    except Exception:
        receipt=source.stop()
        with (directory/'SOURCE_START_FAILURE.json').open('x') as f:json.dump(receipt,f,indent=2)
        record();raise
    if cfg['case']=='timing_failure':metadata['stream_start_perf_counter_ns']+=10_000_000_000
    temporary=directory/'SOURCE_START.pending'
    with temporary.open('x') as f:json.dump(metadata,f,indent=2)
    os.replace(temporary,directory/'SOURCE_START.json')
    with wave.open(cfg['source_wav'],'rb') as wav:pcm=np.frombuffer(wav.readframes(15360),dtype='<i2').astype(np.float32)/32768
    audio=np.repeat(pcm,3);blocks=0 if cfg['case']=='empty_stop' else (6 if cfg['case']=='callback_fault' else 96)
    origin=time.monotonic()
    for i in range(blocks):
        time.sleep(max(0.,origin+(i+1)*.01-time.monotonic()))
        mono=audio[i*480:(i+1)*480]
        source._callback(np.stack((mono,-mono),axis=1),480,SimpleNamespace(inputBufferAdcTime=10+i*.01,currentTime=10.02+i*.01),Flags(0))
    if cfg['case']=='callback_fault':
        try:source._callback(np.zeros((480,2),np.float32),480,SimpleNamespace(inputBufferAdcTime=11.,currentTime=11.02),Flags(2))
        except Abort:pass
        else:raise AssertionError('Expected callback fault')
    with (directory/'RAW_SETUP.json').open('x') as f:json.dump(dict(blocks=blocks,native_frames=blocks*480,status=source.status(),capture=False),f,indent=2)
    bridge=LiveSourceBridge(source,L.LiveGap,directory);close=bridge.close
    def finish():
        try:return close()
        finally:
            assert sys.modules['sounddevice'] is fake and 'scipy' not in sys.modules
            record()
    bridge.close=finish
    return bridge
