"""Explicit-device listening after capture release. See README_SESSIONS.md."""
from __future__ import annotations
import threading
import numpy as np


def outputs():
    import sounddevice as sd
    apis=sd.query_hostapis()
    return [dict(index=i,name=d['name'],hostapi=apis[d['hostapi']]['name'],channels=d['max_output_channels'])
            for i,d in enumerate(sd.query_devices()) if d['max_output_channels']>0]


class SessionPlayback:
    def __init__(self,samples,device,*,backend=None):
        if backend is None:
            import sounddevice as backend
        self.backend=backend;self.device=dict(device);self.samples=np.asarray(samples,dtype=np.float32).reshape(-1)
        if not 0<len(self.samples)<=60*16000:raise ValueError('Listening is bounded to 60 seconds')
        current=backend.query_devices(device['index'],'output');api=backend.query_hostapis(current['hostapi'])['name']
        if current['name']!=device['name'] or api!=device['hostapi']:raise ValueError('Output device changed; select it again')
        backend.check_output_settings(device=device['index'],samplerate=16000,channels=1,dtype='float32')
        self.stop_event=threading.Event();self.error=None;self.frames_played=0;self.closed=False
        self.thread=threading.Thread(target=self._run,name='proto-session-listen',daemon=True);self.thread.start()

    def _run(self):
        try:
            with self.backend.OutputStream(device=self.device['index'],samplerate=16000,channels=1,dtype='float32',blocksize=1024) as stream:
                for start in range(0,len(self.samples),1024):
                    if self.stop_event.is_set():break
                    block=self.samples[start:start+1024].reshape(-1,1)
                    if stream.write(block):raise RuntimeError('Playback underflow; listening continuity was interrupted')
                    self.frames_played+=len(block)
        except Exception as exc:self.error=type(exc).__name__+': '+str(exc)
        finally:self.closed=True;self.samples=None

    def stop(self):
        self.stop_event.set();self.thread.join(5)
        if self.thread.is_alive():raise RuntimeError('Playback still owns an output; capture remains blocked')

    def snapshot(self):return dict(active=not self.closed,device=self.device,frames_played=self.frames_played,error=self.error)
