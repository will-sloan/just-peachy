"""Exercise real callback with fake PortAudio status; README_CALLBACK_FAULT_V1.md."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import json,resource,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,)*2)
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1048576,1048576)
    assert sorted(os.sched_getaffinity(0))==[2,3]
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
    for row in a['files']:assert sha(Path(row['path']))==row['sha256']
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=a['boot_id'],admission_sha256=sha(root/'ADMISSION.json'))
    with (root/'OWNER.json').open('x') as f:json.dump(owner,f)
    source=Path(a['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
    import numpy as np
    from app.live_audio import XVFLiveSource,LiveConfig
    from callback_fault_details_v1 import detailed_source_class
    class Abort(Exception):pass
    class Flags:
        def __init__(self,bits):
            self._flags=bits
            for i,key in enumerate(('input_underflow','input_overflow','output_underflow','output_overflow','priming_output')):
                setattr(self,key,bool(bits & (1<<i)))
        def __bool__(self):return bool(self._flags)
    cls=detailed_source_class(XVFLiveSource)
    def fresh(kind=cls):
        s=kind(LiveConfig(host_executable='/not-opened',lease_path='/not-acquired'),sd_module=SimpleNamespace(CallbackAbort=Abort))
        s._capacity=4;s._route_ready=True
        s._ring=np.zeros((4,480,2),np.float32)
        for name in ('_frames','_native_start','_clock','_perf_clock'):setattr(s,name,np.zeros(4,np.int64))
        for name in ('_adc','_callback_current_time'):setattr(s,name,np.zeros(4,np.float64))
        return s
    clock=SimpleNamespace(inputBufferAdcTime=123.,currentTime=123.01)
    audio=np.arange(960,dtype=np.float32).reshape(480,2)
    cases=[]
    original=fresh(XVFLiveSource);wrapped=fresh()
    original._callback(audio,480,clock,Flags(0));wrapped._callback(audio,480,clock,Flags(0))
    assert np.array_equal(original._ring,wrapped._ring) and original._native_frames==wrapped._native_frames==480
    assert wrapped.status()['callback_fault_detail'] is None
    cases.append('normal_samples_and_counters_unchanged')
    for name,bits,frames,full in [('input_overflow',2,480,False),('input_underflow',1,480,False),('other_status_flags',28,480,False),('raw_ring_overflow',0,480,True),('oversized_callback',0,960,False)]:
        original=fresh(XVFLiveSource);wrapped=fresh()
        if full:original._write_seq=wrapped._write_seq=4
        for s in [original,wrapped]:
            try:s._callback(audio,frames,clock,Flags(bits));raise AssertionError('Expected unchanged abort')
            except Abort:pass
        d=wrapped.status()['callback_fault_detail']
        assert original._fault==wrapped._fault and original._dropped_frames==wrapped._dropped_frames==frames
        assert d['raw_status_bits']==bits and d['rejected_callback_frames']==frames and d['upstream_lost_frames'] is None and d['loss_extent']=='UNKNOWN'
        assert [d[k] for k in ('input_underflow','input_overflow','output_underflow','output_overflow','priming_output')]==[bool(bits&(1<<i)) for i in range(5)]
        assert d['input_buffer_adc_time_seconds']==123. and d['callback_current_time_seconds']==123.01
        cases.append(name)
    s=fresh();s._route_ready=False;s._callback(audio,480,clock,Flags(2))
    assert s._priming_frames==480 and s._priming_status_events==1 and s.status()['callback_fault_detail'] is None
    cases.append('priming_behavior_unchanged')
    s=fresh()
    try:s._callback(np.zeros((3,3)),480,clock,Flags(0));raise AssertionError('Expected shape error')
    except ValueError:pass
    assert s.status()['callback_fault_detail'] is None
    cases.append('unrelated_exception_not_masked')
    assert 'sounddevice' not in sys.modules and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    with (root/'RESULT.json').open('x') as f:json.dump(dict(status='COLLECTED_NATIVE_CALLBACK_FAULT_DETAILS_ONLY',owner=owner,cases=cases,count=len(cases),capture=False,models_loaded=False,stream_constructed=False,integrated=False,actual_status_from_failed_trial_recovered=False,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),f,indent=2)


if __name__=='__main__':main()
