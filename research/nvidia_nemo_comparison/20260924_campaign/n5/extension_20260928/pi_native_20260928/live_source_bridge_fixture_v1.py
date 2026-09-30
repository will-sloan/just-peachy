"""Real callback/read/stop with fake hardware; README_LIVE_SOURCE_BRIDGE_V1.md."""
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import wave


def create(cfg):
    prototype = Path(cfg['prototype'])
    sys.path[:0] = [str(prototype), str(prototype/'vendor')]
    import numpy as np
    from app import live_audio as L
    from live_source_bridge_v1 import LiveSourceBridge
    assert L.XVFLiveSource.__name__ == 'DetailedSource'
    assert 'sounddevice' not in sys.modules and 'scipy' not in sys.modules
    directory = Path(cfg['case_directory'])
    calls = []
    class Abort(Exception):pass
    class Flags:
        def __init__(self, bits):
            self._flags = bits
            for i,name in enumerate(('input_underflow','input_overflow','output_underflow','output_overflow','priming_output')):
                setattr(self,name,bool(bits & (1<<i)))
        def __bool__(self):return bool(self._flags)
    config = L.LiveConfig(host_executable='/not-opened',lease_path=str(directory/'fake-device.lock'),
                          hostapi='ALSA',endpoint_name='FAKE_NOT_OPENED',control_protocol='i2c',tap=cfg['tap'])
    source = L.XVFLiveSource(config,sd_module=SimpleNamespace(CallbackAbort=Abort))
    class Stream:
        active=True
        closed=False
        def stop(self):
            calls.append('stream_stop');self.active=False
        def close(self):
            calls.append('stream_close');self.closed=True
    class Route:
        def restore(self):
            assert source.stream.active and source.lease.handle is not None
            calls.append('route_restore_with_clock_and_lease')
            return {'AEC_ASROUTONOFF':'MISMATCH' if cfg['case']=='restore_mismatch' else 'RESTORED'}
    source.stream = Stream()
    source.route = Route()
    source.control = SimpleNamespace(receipts=[])
    source.lease = L.DeviceLease(config.lease_path).acquire()
    source.metadata = {'fixture':True,'stream_opened':False,'defaults_before':L.endpoint_snapshot()}
    source._capacity = cfg['capacity']
    source._ring = np.zeros((source._capacity,480,2),np.float32)
    for name in ('_frames','_native_start','_clock','_perf_clock'):
        setattr(source,name,np.zeros(source._capacity,np.int64))
    for name in ('_adc','_callback_current_time'):
        setattr(source,name,np.zeros(source._capacity,np.float64))
    source._converter = L.StreamingDecimator()
    source._gain = np.float32(10**(3/20) if config.tap=='O0' else 1)
    source._started = source._route_ready = True
    source._started_ns = time.monotonic_ns()
    source._capture_epoch = cfg['epoch']
    with wave.open(cfg['source_wav'],'rb') as wav:
        samples = np.frombuffer(wav.readframes(20000),dtype='<i2').astype(np.float32)/32768
    native = np.repeat(samples,3)
    accepted = []
    origin = 0
    for frames in cfg['frames']:
        x = native[origin:origin+frames]
        audio = np.stack((x,-x),axis=1)
        clock = SimpleNamespace(inputBufferAdcTime=100+origin/48000,currentTime=100.032+origin/48000)
        try:
            source._callback(audio,frames,clock,Flags(0))
            accepted.append(frames);origin+=frames
        except Abort:
            assert cfg['case']=='raw_ring_overflow'
            break
    if cfg['case'] in ('callback_fault','oversized_callback'):
        frames = 480 if cfg['case']=='callback_fault' else 960
        try:
            source._callback(np.zeros((frames,2),np.float32),frames,
                             SimpleNamespace(inputBufferAdcTime=123.,currentTime=123.032),
                             Flags(2 if cfg['case']=='callback_fault' else 0))
        except Abort:pass
        else:raise AssertionError('Expected unchanged real callback abort')
    with (directory/'RAW_SETUP.json').open('x') as f:
        json.dump(dict(accepted_frames=accepted,initial_status=source.status(),tap=cfg['tap'],
                       source_kind='REAL_SOURCE_WITH_FAKE_CALLBACK_STREAM_ROUTE',capture=False),f,indent=2)
    bridge = LiveSourceBridge(source,L.LiveGap,directory)
    original_close = bridge.close
    def close():
        try:return original_close()
        finally:
            assert 'sounddevice' not in sys.modules and 'scipy' not in sys.modules
            with (directory/'CLEANUP_CALLS.json').open('x') as f:json.dump(calls,f)
    bridge.close = close
    if cfg['prestop']:bridge.stop()
    return bridge
