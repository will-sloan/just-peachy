"""Actual model enrollment-worker route proof using an existing fixture, no capture. See README_NOISE.md."""
import argparse,hashlib,json,os,queue,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(name,'1')
import numpy as np
import soundfile as sf
from app.controller import Controller
from app.paths import default_models_root,sha256
from app.enrollment_quality import EnrollmentQuality
from app.enrollment_progress import ReadProgress
from check_noise_native import enhance

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--wav',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);c=Controller(args.output/'data',default_models_root());start=time.perf_counter();rows=[]
    try:
        raw,rate=sf.read(args.wav,dtype='float32');assert rate==16000 and raw.ndim==1
        c.models.enrollment_models(c.config);helper=c.models.enhancement_model(c.config);expected,_=enhance(helper,raw)
        for route in ('bypass','asr','identity','both'):
            c._enroll_enhancement_route=route;c._enroll_enhancer=None if route=='bypass' else c.models.enhancement_model(c.config)
            c.enrollment={};c._enroll_script_enabled=True;c._enroll_audio=[];c._quality_queue=queue.Queue()
            c._quality=EnrollmentQuality(c.models.speakers,c.config,None)
            _,stream=c.models.acquire(c.config,caption_only=True);c._enroll_read=ReadProgress(stream,'',token_timing=True)
            fed=[];original=c._update_enrollment_read
            def capture(samples=None,final=False):
                if samples is not None:fed.append(samples.copy())
                original(samples,final)
            c._update_enrollment_read=capture
            for offset in range(0,len(raw),160000):c._quality_queue.put((offset,raw[offset:offset+160000]))
            c._quality_queue.put(None);c._quality_loop();c._quality_queue.join();c._update_enrollment_read=original
            assert not c.enrollment.get('gaps'),c.enrollment
            identity=expected if route in ('identity','both') else raw;asr=expected if route in ('asr','both') else raw
            q,v=c._quality.result();assert q['can_save']
            assert np.array_equal(np.concatenate(fed),asr) and np.array_equal(np.concatenate(c._enroll_audio),identity)
            assert q['source_sha256']==hashlib.sha256(identity.astype('<f4').tobytes()).hexdigest()
            rows.append(dict(route=route,quality_audio_samples=len(identity),asr_audio_samples=len(asr),exact_branch_bytes=True,
                usable_sec=q['usable_s'],quality_sha256=q['source_sha256'],asr_text=[r['raw_asr_text'] for r in c.enrollment['script_estimate']['utterances']]))
        report=dict(status='PASS',scope='Actual Controller quality worker and real native models; prerecorded corpus, no unattended user enrollment',
            rows=rows,elapsed_sec=time.perf_counter()-start,source_sha256=sha256(args.wav),
            code_sha256={p.relative_to(ROOT).as_posix():sha256(p) for p in (Path(__file__),ROOT/'app/controller.py',ROOT/'app/enhancement.py')})
        (args.output/'ENROLLMENT_NOISE_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
    finally:
        # Fixture worker has already drained; no capture owner or enrollment state.
        c._enroll_enhancer=None;c.enrollment={};c.close();c.commands.join();c.worker.join(10)

if __name__=='__main__':main()
