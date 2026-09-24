"""Native real-audio replay, empty input and forced-endpoint conformance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prototype','audio-manifest','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--binding',type=Path)
    p.add_argument('--reference-model',type=Path)
    p.add_argument('--reference-source',type=Path)
    p.add_argument('--cpu',type=int,choices=[4,14],default=4)
    args=p.parse_args()
    if args.output.exists():raise ValueError('Fresh conformance output required')
    args.output.mkdir(parents=True)
    import psutil
    process=psutil.Process();process.cpu_affinity([args.cpu])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    sys.path[:0]=[str(args.prototype/'vendor'),str(args.prototype)]
    import numpy as np
    import soundfile as sf
    from edge_speech_pipeline.n3_asr_native import NativeRecognizer,sha
    binding=json.loads(args.binding.read_text()) if args.binding else None
    manifest=json.loads(args.audio_manifest.read_text())
    job=next(row for row in manifest['jobs'] if row['job_id'].endswith('S45_08_07_O0'))
    if sha(job['audio_path'])!=job['audio_sha256']:raise ValueError('Audio changed')
    audio,rate=sf.read(job['audio_path'],dtype='float32')
    if rate!=16000 or audio.ndim!=1 or len(audio)!=job['frames'] or job['gain']!=1:raise ValueError('Audio admission mismatch')
    result=dict(schema='just-peachy.n3.native-conformance.v1',status='RUNNING',binding_sha256=sha(args.binding) if binding else None,
        audio_sha256=job['audio_sha256'],variant=binding['variant'] if binding else 'A1',cases=[],scope='saved audio and zero/short protocol fixtures; no new acoustic bank')
    owner=None
    try:
        if binding:
            owner=NativeRecognizer(binding)
        else:
            if not args.reference_model or not args.reference_source:raise ValueError('A1 exact model/source required')
            from reference_asr import ReferenceRecognizer
            owner=ReferenceRecognizer('A1',args.reference_model,args.reference_source)
            result['reference_model_sha256']=sha(args.reference_model)
        cases=[('empty',audio[:0],None),('one_sample',audio[:1],None),
                ('short_tail',audio[:1281],None),('silence',np.zeros(48000,np.float32),None),
                ('continuous',audio,None),('continuous_repeat',audio,None)]
        if binding:cases += [('forced_inside_paragraph',audio,round(12.34*16000)),('forced_repeat',audio,round(12.34*16000))]
        else:result['manual_endpoint']='UNAVAILABLE_IN_OFFICIAL_A1_SERVICE; predicted EOU and explicit tail retained'
        for label,wave,force in cases:
            stream=owner.stream();rows=[];cursor=0;forced=False;started=time.perf_counter()
            cpu_start=sum(process.cpu_times()[:2]);peak=process.memory_info().rss
            try:
                while cursor<len(wave):
                    end=min(cursor+1280,len(wave))
                    if force is not None and not forced:end=min(end,force)
                    rows.extend(stream.feed(wave[cursor:end]));cursor=end
                    if force is not None and cursor==force and not forced:
                        rows.extend(stream.force_endpoint());forced=True
                    peak=max(peak,process.memory_info().rss)
                rows.extend(stream.finish_events())
                if stream.finish_events():raise AssertionError('Non-idempotent finish')
                if stream.input_samples!=len(wave):raise AssertionError('Sample accounting failed')
                finals=[r['raw_text'] for r in rows if r['final']]
                if label=='empty' and any(text.strip() for text in finals):raise AssertionError('Empty input fabricated speech')
                events=args.output/(label+'.jsonl')
                events.write_text(''.join(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n' for row in rows),encoding='utf-8')
                result['cases'].append(dict(case=label,samples=len(wave),forced_input_sample=force,
                    elapsed_seconds=time.perf_counter()-started,cpu_seconds=sum(process.cpu_times()[:2])-cpu_start,
                    peak_sampled_rss_bytes=peak,final_text_sha256=hashlib.sha256(json.dumps(finals).encode()).hexdigest(),
                    final_count=len(finals),output_words=sum(len(t.split()) for t in finals),
                    events_sha256=sha(events),status='PASS'))
            finally:stream.close()
        rows={r['case']:r for r in result['cases']}
        pairs=[('continuous','continuous_repeat')]+([('forced_inside_paragraph','forced_repeat')] if binding else [])
        for left,right in pairs:
            if rows[left]['final_text_sha256']!=rows[right]['final_text_sha256']:
                raise AssertionError('Fresh same-window replay was not deterministic: '+left)
        result['status']='COMPLETE'
    except Exception as exc:
        result.update(status='FAILED',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if owner is not None:owner.close()
        (args.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
