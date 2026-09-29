"""Stateful FIR candidate; see README_LIVE_DECIMATOR_V1.md. No hardware access."""
import numpy as np

class NumpyDecimator:
    def __init__(self,taps):
        self.taps=np.asarray(taps,dtype=np.float64).copy()
        assert self.taps.shape==(97,) and np.isfinite(self.taps).all()
        self.history=np.zeros(96,dtype=np.float64)
        self.native_count=0
        self.delay_seconds=48/48000

    def convert(self,audio):
        values=np.asarray(audio,dtype=np.float64).reshape(-1)
        if not len(values):return np.empty(0,dtype=np.float32)
        combined=np.concatenate((self.history,values))
        filtered=np.convolve(combined,self.taps,mode='valid')
        self.history=combined[-96:].copy()
        offset=(-self.native_count)%3
        self.native_count+=len(values)
        return filtered[offset::3].astype(np.float32)
