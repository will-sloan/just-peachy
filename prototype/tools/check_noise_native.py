"""Small frozen task10 native comparison; no microphone/playback. See README_NOISE.md."""
import argparse,hashlib,json,os,re,sys,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'1')
import numpy as np
import soundfile as sf
import psutil
from app.paths import default_models_root,sha256
from app.pipeline import ResidentModels
from app.controller import Controller
from app.enhancement import DpdfStream,identity_binding,specification
from app.enrollment_progress import ReadProgress
from app.enrollment_quality import EnrollmentQuality
from app.people import PersonalStore
from app.sessions import records
from check_native_people import ROUTE

def words(text):return re.findall(r"[^\W_]+(?:['’][^\W_]+)*",text.casefold())
def edits(reference,hypothesis):
    """Unit-cost word Levenshtein; ties prefer substitution, then deletion."""
    a,b=words(reference),words(hypothesis);d=[[(j,0,0,j) for j in range(len(b)+1)]]
    for i,x in enumerate(a,1):
        row=[(i,0,i,0)]
        for j,y in enumerate(b,1):
            if x==y:row.append(d[i-1][j-1]);continue
            old=d[i-1][j-1];sub=(old[0]+1,old[1]+1,old[2],old[3])
            old=d[i-1][j];delete=(old[0]+1,old[1],old[2]+1,old[3])
            old=row[j-1];insert=(old[0]+1,old[1],old[2],old[3]+1)
            row.append(min((sub,delete,insert),key=lambda v:v[0]))
        d.append(row)
    error,s,de,ins=d[-1][-1]
    return dict(reference_words=len(a),hypothesis_words=len(b),S=s,D=de,I=ins,WER=error/len(a) if a else None,
                false_words=ins if not a else None,normalization='casefold, word/apostrophe tokens; punctuation ignored')

def enhance(helper,x,chunks=(320,)):
    helper.reset();ys=[];position=0;availability=[];tick=time.perf_counter();i=0
    while position<len(x):
        count=chunks[i%len(chunks)];part=x[position:position+count];position+=len(part);i+=1
        y=helper.run(part)
        if len(y):availability.append(dict(source_received=position,output_end=sum(map(len,ys))+len(y),wall_sec=time.perf_counter()-tick))
        ys.append(y)
    tail=helper.flush();ys.append(tail);result=np.concatenate(ys)
    assert len(result)==len(x) and np.isfinite(result).all()
    return result,dict(input_samples=len(x),output_samples=len(result),flush_samples=len(tail),
        compute_sec=helper.compute_sec,max_call_sec=helper.max_call_sec,wall_sec=time.perf_counter()-tick,
        first_output=availability[0] if availability else None,
        buffering_samples=max((r['source_received']-r['output_end'] for r in availability),default=None))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--reuse-cases',type=Path,help='Reuse completed native clip/alignment evidence after checking unchanged runtime hashes; rerun integration only')
    p.add_argument('--corpus',type=Path,default=ROOT.parent/'Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    proc=psutil.Process();started=time.perf_counter();cpu0=proc.cpu_times();rss=[];sampling=threading.Event()
    def sample():
        while not sampling.wait(.05):rss.append(proc.memory_info().rss)
    sampler=threading.Thread(target=sample,daemon=True);sampler.start()
    report=dict(status='RUNNING',scope='Fixed small native cases, not accuracy validation or CM5 qualification',
        cases=[],reference_quality=[],pipeline=[],no_microphone=True,no_audible_playback=True,thresholds_unchanged=True)
    c=None
    def save():
        (args.output/'NATIVE_NOISE_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    try:
        c=Controller(args.output/'data',default_models_root());models=c.models;config=c.config
        models.enrollment_models(config);models.acquire(config,caption_only=True)
        before_rss=proc.memory_info().rss;load_cpu=proc.cpu_times();tick=time.perf_counter()
        helper=models.enhancement_model(config)
        report['helper_load']=dict(wall_sec=time.perf_counter()-tick,rss_increment_bytes=proc.memory_info().rss-before_rss,
            cpu_sec=proc.cpu_times().user+proc.cpu_times().system-load_cpu.user-load_cpu.system)
        report['model_hashes']={a.component_id:a.sha256 for a in config.assets};report['helper']=specification()
        def load(code,key):
            root=args.corpus/f'cmu_us_{code}_arctic';path=root/'wav'/(key+'.wav')
            refs=dict(re.findall(r'\(\s+(\S+)\s+"([^"]*)"\s*\)',(root/'etc/txt.done.data').read_text()))
            audio,rate=sf.read(path,dtype='float32');assert rate==16000 and audio.ndim==1
            return audio,refs[key],dict(path=str(path),sha256=sha256(path),key=key,speaker=code)
        def quality(x):
            q=EnrollmentQuality(models.speakers,config,None)
            for start in range(0,len(x),160000):q.process(x[start:start+160000])
            data,vector=q.result(source_kind='offline_public_corpus_task10')
            return data,vector
        def decode(x,ref):
            _,stream=models.acquire(config,caption_only=True);reader=ReadProgress(stream,ref)
            reader.accept(x);result=reader.finish()
            return ' '.join(r['raw_asr_text'] for r in result['utterances'])
        references={};ids={};reference_hashes=set()
        for code in ('awb','bdl'):
            refs=[load(code,'arctic_a0001'),load(code,'arctic_a0003')]
            x=np.concatenate([r[0] for r in refs]);reference_hashes.update(r[2]['sha256'] for r in refs)
            y,timing=enhance(helper,x)
            for branch,audio in (('input',x),('enhanced',y)):
                q,v=quality(audio);references[code,branch]=v
                report['reference_quality'].append(dict(speaker=code,branch=branch,quality=q,sources=[r[2] for r in refs]))
                if not q['can_save']:raise RuntimeError('Fixed native reference rejected by unchanged gate: '+code+'/'+branch)
                route=dict(ROUTE,**identity_binding('both' if branch=='enhanced' else 'bypass'))
                row=c.store.save('Fixture '+code,v,q,route,person_id=ids.get(code));ids[code]=row['id']
        clean,text,origin=load('awb','arctic_a0016');short,st,so=load('awb','arctic_a0005')
        neg,nt,no=load('awb','arctic_a0002');pro,pt,po=load('awb','arctic_a0030')
        stranger,xt,xo=load('clb','arctic_a0016')
        rng=np.random.default_rng(10);noise=rng.standard_normal(len(clean)).astype(np.float32)
        noise*=np.sqrt(np.mean(clean.astype(np.float64)**2)/np.mean(noise.astype(np.float64)**2)) # fixed 0dB SNR
        transient=clean.copy();transient[12000:12160]+=.25*np.hanning(160).astype(np.float32)
        other,ot,oo=load('bdl','arctic_a0016');overlap=np.zeros(max(len(clean),len(other)),np.float32)
        overlap[:len(clean)]+=.5*clean;overlap[:len(other)]+=.5*other
        t=np.arange(48000)/16000.;music=(.025*(np.sin(2*np.pi*220*t)+np.sin(2*np.pi*277.1826*t)+np.sin(2*np.pi*329.6276*t))*(.5+.5*np.sin(2*np.pi*2*t))).astype(np.float32)
        cases=[('clean',clean,text,origin,'awb'),('quiet_minus20dB',clean*.1,text,origin,'awb'),
            ('stationary_0dB_SNR',clean+noise,text,origin,'awb'),('transient_click',transient,text,origin,'awb'),
            ('overlap_equal_gain',overlap,None,dict(sources=[origin,oo],reference_texts=[text,ot]),None),
            ('instrumental_synthetic',music,'',dict(construction='Three fixed tones with 2Hz envelope; no speech. Narrow music control.'),None),
            ('silence',np.zeros(32000,np.float32),'',dict(construction='Exact digital silence,2s'),None),
            ('short_weak_consonants',short,st,so,'awb'),('negation',neg,nt,no,'awb'),('pronouns',pro,pt,po,'awb'),
            ('impostor',stranger,xt,xo,'clb')]
        index=ROOT.parent/'XVF 3800 Testing/XVF Integration Real World RIRs/simulation/listening/S45_all240_v1/SCENE_AUDIO_INDEX.json'
        scene=json.loads(index.read_text(encoding='utf-8'))['scenes'][0];binding=scene['streams']['O0']['prepared_pcm16'];path=Path(binding['path'])
        assert sha256(path)==binding['sha256']
        x,rate=sf.read(path,frames=160000,dtype='float32');assert rate==16000 and len(x)==160000
        seg=scene['turns'][0]
        assert max(b for a,b in seg['file_support'])<=160000<min(a for a,b in scene['turns'][1]['file_support'])
        cases.append(('post_XVF_O0_first10s',x,seg['transcript'],dict(source=binding,index_sha256=sha256(index),
            source_slice=[0,160000],gain='Existing prepared O0 +3dB retained exactly; no new gain',scope='Full first utterance; before second; fixed excerpt'),None))
        # Native state/alignment including non-hop tails, zero-length and reset.
        reused=None
        if args.reuse_cases:
            reused=json.loads(args.reuse_cases.read_text(encoding='utf-8'))
            for name,digest in reused['execution_sha256'].items():
                if not name.startswith('tools/'):assert sha256(ROOT/name)==digest,name
            assert [r['label'] for r in reused['cases']]==[r[0] for r in cases]
            assert [r['samples'] for r in reused['alignment']]==[0,1,159,160,161,319,320,321,16003]
            report['cases']=reused['cases'];report['alignment']=reused['alignment']
            report['reused_clip_evidence']=dict(path=str(args.reuse_cases.resolve()),sha256=sha256(args.reuse_cases),
                reason='Prior integration harness export naming failure; completed clip/alignment checks remain valid against identical runtime',resources=reused['resources'])
        else:report['alignment']=[]
        for n in (() if reused else (0,1,159,160,161,319,320,321,16003)):
            a=(rng.standard_normal(n)*.01).astype(np.float32)
            y,meta=enhance(helper,a);z,_=enhance(helper,a,(1,79,160,13,967))
            assert np.array_equal(y,z),(n,float(np.max(np.abs(y-z))))
            reset,_=enhance(helper,a);assert np.array_equal(y,reset)
            report['alignment'].append(dict(samples=n,exact_chunk_invariance=True,exact_reset=True,**{k:v for k,v in meta.items() if k!='input_samples'}))
        for label,x,ref,provenance,expected in ([] if reused else cases):
            if provenance.get('sha256'):assert provenance['sha256'] not in reference_hashes
            assert np.max(np.abs(x),initial=0)<1.,label+' generated clipping'
            y,timing=enhance(helper,x);row=dict(label=label,seconds=len(x)/16000,reference=ref,provenance=provenance,enhancer=timing,branches={})
            for branch,audio in (('input',x),('enhanced',y)):
                sf.write(args.output/(label+'_'+branch+'.wav'),audio,16000,subtype='FLOAT')
                tick=time.perf_counter();q,v=quality(audio);hyp=decode(audio,ref or '')
                matches={code:float(v@references[code,branch]) if v is not None else None for code in ('awb','bdl')}
                row['branches'][branch]=dict(audio_float_sha256=hashlib.sha256(audio.astype('<f4').tobytes()).hexdigest(),
                    decoded=hyp,edits=edits(ref,hyp) if ref is not None else None,
                    reference_validity='No ordered WER for simultaneous two-speaker mixture' if ref is None else 'Canonical full-clip text or declared empty control',
                    usable_sec=q['usable_s'],can_save_reference=q['can_save'],quality=q,voice_scores=matches,expected_speaker=expected,
                    score_scope='Quality-admitted whole-clip centroid cosine, not calibrated confidence or temporal naming',wall_sec=time.perf_counter()-tick)
            row['route_factorization']={route:dict(asr='enhanced' if route in ('asr','both') else 'input',identity='enhanced' if route in ('identity','both') else 'input') for route in ('bypass','asr','identity','both')}
            report['cases'].append(row);save()
        # Actual application routes, safe epochs, matching galleries, and archives.
        known=np.concatenate([load('awb',f'arctic_a{n:04d}')[0] for n in (16,17,18)])
        outsider=load('clb','arctic_a0001')[0]
        for name,audio in [('known',known),('outsider',outsider)]:sf.write(args.output/(name+'.wav'),audio,16000,subtype='PCM_16')
        c.switch(mode='enrolled_names',recipe='balanced',tap='O0');c.commands.join();assert not c.error,c.error
        for route in ('bypass','asr','identity','both'):
            c.noise_route(route);c.commands.join();assert not c.error,c.error
            c.route=lambda r=route:dict(ROUTE,**identity_binding(r)) # explicit isolated dry-fixture domain
            for name in ('known','outsider'):
                c.session_action('new',audio=True,consent=True,title='Task10 native '+route+' '+name);c.commands.join();assert not c.error,c.error
                identifier=c.conversation_id;tick=time.perf_counter();cpu_before=proc.cpu_times();rss_before=proc.memory_info().rss
                c.start_file(args.output/(name+'.wav'));c.commands.join();assert not c.error,c.error
                deadline=time.perf_counter()+60
                while c.state in ('STARTING','RUNNING','STOPPING') and time.perf_counter()<deadline:time.sleep(.05)
                assert c.state=='STOPPED' and not c.error,(c.state,c.error)
                engine=c.engine;assert engine.state=='COMPLETED'
                c.session_store.save(identifier)
                epoch=c.session_store.metadata(identifier)['epochs'][-1];folder=c.session_store.epoch(identifier,epoch)
                meta=json.loads((folder/'epoch.json').read_text(encoding='utf-8'));assert not meta['archive_error'],meta
                raw=np.fromfile(folder/'model_input.f32le',dtype='<f4');source=sf.read(args.output/(name+'.wav'),dtype='float32')[0]
                assert np.array_equal(raw,source)
                enhanced=np.fromfile(folder/'enhanced.f32le',dtype='<f4') if route!='bypass' else None
                if enhanced is not None:
                    assert len(enhanced)==len(raw) and engine.enhancement_router.active
                    # Worker has completed. This reset is safe and checks exact archived helper output.
                    expected_audio,_=enhance(helper,raw);assert np.array_equal(enhanced,expected_audio)
                windows=list(records(folder/'windows.jsonl'));assert any(w['kind']=='research_embedding' for w in windows)
                for w in windows:
                    stream=enhanced if w['audio_stream']=='enhanced' else raw
                    out=args.output/(route+'_'+name+'_'+w['window_id']+'.npy');c.session_store.export_window(identifier,epoch,w['window_id'],out)
                    expect=np.pad(stream[w['source_start_sample']:w['source_end_sample']],(w['left_padding_samples'],0))
                    assert np.array_equal(np.load(out),expect)
                rows=list(c.rows.values());parts=[p for r in rows for p in (r.get('segments') or [r])]
                def duration(part):
                    span=part.get('identity_target_span')
                    return max(0,span[1]-span[0]) if span else 0
                total=sum(duration(p) for p in parts)
                unknown=sum(duration(p) for p in parts if not p.get('known_profile_id'))
                confirmed=sorted({p['known_profile_id'] for p in parts if p.get('naming_state')=='confirmed' and p.get('known_profile_id')})
                cpu_now=proc.cpu_times()
                report['pipeline'].append(dict(route=route,query=name,engine_state=engine.state,archive=str(folder),
                    exact_streams_and_windows=True,windows=len(windows),gallery_calls=engine._research_gallery.query_count,
                    expected_uuid=ids['awb'] if name=='known' else None,confirmed_uuids=confirmed,
                    unknown_caption_duration_fraction=unknown/total if total else None,
                    coverage_scope='Duration of final caption segments, not word-aligned diarization error',
                    captions=[dict(text=r.get('text'),segments=r.get('segments')) for r in rows],
                    decisions=c.metrics.get('recent_identity_decisions'),coordinator=c.noise_snapshot(),
                    wall_sec=time.perf_counter()-tick,cpu_sec=cpu_now.user+cpu_now.system-cpu_before.user-cpu_before.system,
                    rss_before=rss_before,rss_after=proc.memory_info().rss))
                save()
        # Existing post-XVF samples through actual both-route application, unlabelled gallery.
        c.switch(mode='anonymous_conversation',recipe='balanced',tap='O0');c.commands.join();assert not c.error,c.error
        c.route=lambda:dict(tap='O0',sample_rate=16000,gain_policy='O0_host_plus3dB_once',waveform_domain='xvf_ua',preprocessing=ROUTE['preprocessing'],**identity_binding('both'))
        sf.write(args.output/'post_xvf_pcm16.wav',cases[-1][1],16000,subtype='PCM_16')
        c.start_file(args.output/'post_xvf_pcm16.wav');c.commands.join();assert not c.error,c.error
        deadline=time.perf_counter()+60
        while c.state in ('STARTING','RUNNING','STOPPING') and time.perf_counter()<deadline:time.sleep(.05)
        assert c.state=='STOPPED' and not c.error and c.engine.enhancement_router.active,(c.state,c.error)
        report['post_xvf_application']=dict(state=c.engine.state,gallery='anonymous, no dry-domain identity claim',rows=len(c.rows),
            raw_samples=c.engine._input_journal.raw.committed_samples,enhanced_samples=c.engine._input_journal.enhanced.committed_samples)
        report['model_loads']=dict(asr=models.asr_loads,speaker=models.speaker_loads,enhancer=models.enhancer_loads)
        report['status']='PASS_FUNCTIONAL';report['performance_claim']='None; report all successes and degradations, no tuning'
    except Exception as exc:
        import traceback
        report.update(status='FAIL',error=str(exc),traceback=traceback.format_exc());raise
    finally:
        if c is not None:
            c.close();c.commands.join();c.worker.join(15)
            report['controller_closed']=c.closed
        sampling.set();sampler.join(2);cpu_now=proc.cpu_times()
        report['resources']=dict(elapsed_sec=time.perf_counter()-started,cpu_sec=cpu_now.user+cpu_now.system-cpu0.user-cpu0.system,
            peak_sampled_rss_bytes=max(rss+[proc.memory_info().rss]),sampling_sec=.05,scope='Desktop process,not CM5')
        report['execution_sha256']={p.relative_to(ROOT).as_posix():sha256(p) for p in
            [Path(__file__)]+[q for d in ('app','config','vendor') for q in (ROOT/d).rglob('*') if q.suffix in ('.py','.json')]}
        save();print(json.dumps({k:report.get(k) for k in ('status','error','resources','helper_load','model_loads')}))

if __name__=='__main__':main()
