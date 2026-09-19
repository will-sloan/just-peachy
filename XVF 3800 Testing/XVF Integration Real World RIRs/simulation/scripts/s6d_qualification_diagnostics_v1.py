"""File-only common-lag diagnostics; README_S6D_PHYSICAL_PREPARATION.md."""
from __future__ import annotations
import hashlib
import numpy as np
from scipy.signal import correlate,correlation_lags


def stream_fingerprints(samples):
    x=np.asarray(samples)
    if x.ndim!=2 or x.shape[1]!=6 or not np.isfinite(x).all():raise ValueError('Finite decoded six-channel samples required')
    return dict(frames=len(x),channels=[dict(index=i,float32_pcm_sha256=hashlib.sha256(np.asarray(x[:,i],dtype='<f4').tobytes()).hexdigest(),
        nonzero_samples=int(np.count_nonzero(x[:,i])),peak_abs=float(np.max(np.abs(x[:,i]))) if len(x) else None) for i in range(6)],
        exact_equal_pairs=[[i,j] for i in range(6) for j in range(i+1,6) if np.array_equal(x[:,i],x[:,j])],
        interpretation='Identical processed streams can be genuine; duplicates require tagged/configuration evidence to identify routing faults')


def pair_diagnostics(first,second,max_lag_samples=16000):
    """A single descriptive lag for repeated first-four MAIN/SCAN streams.

    No resampling, gain fit, independent beam warp, or modified output audio.
    Correlation is descriptive; label/beam identity is not an input.
    """
    a=np.asarray(first,dtype=np.float64);b=np.asarray(second,dtype=np.float64)
    fa=stream_fingerprints(a);fb=stream_fingerprints(b)
    if len(a)<64 or len(b)<64 or max_lag_samples<0:raise ValueError('At least64 frames and nonnegative lag bound required')
    lags=correlation_lags(len(b),len(a));mask=np.abs(lags)<=max_lag_samples;score=np.zeros(int(mask.sum()));active=[]
    for i in range(4):
        norm=float(np.linalg.norm(a[:,i])*np.linalg.norm(b[:,i]))
        if norm>0:score+=correlate(b[:,i],a[:,i],method='fft')[mask]/norm;active.append(i)
    if not active:return dict(status='UNIDENTIFIABLE_SILENT_OR_NO_COMMON_ACTIVE_CHANNEL',common_offset_samples=None,first=fa,second=fb,channels=[],audio_modified=False)
    lag=int(lags[mask][np.argmax(score)]);a0=max(0,-lag);b0=max(0,lag);length=min(len(a)-a0,len(b)-b0);rows=[]
    for i in range(4):
        aa=a[a0:a0+length,i];bb=b[b0:b0+length,i];an=float(np.linalg.norm(aa));bn=float(np.linalg.norm(bb))
        rows.append(dict(index=i,compared_samples=length,cosine_correlation=float(np.dot(aa,bb)/(an*bn)) if an and bn else None,
            second_over_first_rms_db=float(20*np.log10(bn/an)) if an and bn else None,
            status='DESCRIPTIVE' if an and bn else 'UNIDENTIFIABLE_ZERO_STREAM'))
    flags=[]
    if abs(lag)==max_lag_samples:flags.append('LAG_SEARCH_BOUNDARY_REQUIRES_REVIEW')
    if any(r['cosine_correlation'] is not None and r['cosine_correlation']<.90 for r in rows):flags.append('COMMON_STREAM_CORRELATION_BELOW_0_90')
    if any(r['second_over_first_rms_db'] is not None and abs(r['second_over_first_rms_db'])>3 for r in rows):flags.append('COMMON_STREAM_LEVEL_DIFFERENCE_OVER_3DB')
    return dict(status='DESCRIPTIVE_REVIEW_FLAGS' if flags else 'DESCRIPTIVE_NO_PREDECLARED_FLAG',common_offset_samples=lag,
        active_alignment_channels=active,channels=rows,review_flags=flags,first=fa,second=fb,audio_modified=False,
        inference_limit='Different physical passes can have different DSP state; correlation does not prove identity or absence of observer effects')


def tail_support(expected_source,decoded,lag_samples,source_origin=16000):
    """Declared source support versus captured extent at a measured common lag.

    This exact-extent test does not prove a processed beam retained speech; its
    lag must come from qualified evidence, never a guessed processing delay.
    """
    source=np.asarray(expected_source);capture=np.asarray(decoded)
    support=np.flatnonzero(np.any(source!=0,axis=1))
    if lag_samples is None:return dict(status='UNKNOWN_LATENCY',all_nonzero_source_extent_captured=None)
    if not len(support):return dict(status='UNIDENTIFIABLE_ALL_ZERO_SOURCE',all_nonzero_source_extent_captured=None)
    begin=int(source_origin+support[0]+lag_samples);end=int(source_origin+support[-1]+lag_samples)
    passed=begin>=0 and end<len(capture)
    return dict(status='PASS_EXTENT_ONLY' if passed else 'FAIL_SOURCE_EXTENT',first_nonzero_capture_frame=begin,last_nonzero_capture_frame=end,
        captured_frames=len(capture),post_support_margin_samples=len(capture)-end-1,all_nonzero_source_extent_captured=passed,
        processed_payload_recovery_claim=False)
