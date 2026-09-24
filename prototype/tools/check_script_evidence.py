"""Bounded real-audio script/reference counterexamples. See README_SCRIPT_EVIDENCE.md."""
import argparse,hashlib,json,os,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(name,'1')
import numpy as np
import psutil
import soundfile as sf
from app.enrollment_quality import EnrollmentQuality
from app.enrollment_progress import ReadProgress
from app.script_evidence import build_evidence,preview
from app.paths import pipeline_config,default_models_root,sha256
from app.people import PersonalStore
from app.pipeline import ResidentModels
from check_native_people import ROUTE,native_query


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--corpus',type=Path,default=ROOT.parent/'Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    began=time.perf_counter();proc=psutil.Process();cpu=proc.cpu_times();rss=[proc.memory_info().rss]
    config=pipeline_config(args.output,default_models_root());models=ResidentModels();speaker=models.enrollment_models(config)
    hashes={a.component_id:a.sha256 for a in config.assets};store=PersonalStore(args.output/'people',hashes['redimnet2_b2_fp32'])
    report=dict(status='RUNNING',scope='Existing CMU public corpus; genuine frozen models, no mic/playback; small counterexamples not accuracy estimates',references=[],queries=[],pipeline_queries=[])
    report['execution_sha256']={str(p.relative_to(ROOT)):sha256(p) for p in (
        Path(__file__),ROOT/'app/script_evidence.py',ROOT/'app/enrollment_progress.py',ROOT/'app/enrollment_quality.py',
        ROOT/'app/people.py',ROOT/'app/pipeline.py',ROOT/'tests/check_native_people.py',ROOT/'config/assets.json')}
    documents={};audios={};qualities={};vectors={};estimates={};ids={}
    def load(speaker_code,index):
        root=args.corpus/f'cmu_us_{speaker_code}_arctic'
        path=root/'wav'/f'arctic_a{index:04d}.wav'
        transcript=dict(re.findall(r'\(\s+(\S+)\s+"([^"]*)"\s*\)',(root/'etc/txt.done.data').read_text()))[f'arctic_a{index:04d}']
        audio,rate=sf.read(path,dtype='float32');assert rate==16000 and audio.ndim==1
        q=EnrollmentQuality(speaker,config,None)
        for start in range(0,len(audio),160000):q.process(audio[start:start+160000])
        quality,vector=q.result(source_kind='offline_CMU_task09_fixture')
        return path,audio,transcript,quality,vector
    def decode(audio,script):
        _,stream=models.acquire(config,caption_only=True);reader=ReadProgress(stream,script,token_timing=True)
        reader.accept(audio);return reader.finish()
    for code in ('awb','bdl'):
        for index in (1,3):
            path,audio,script,q,v=load(code,index);assert q['can_save'],(code,index,q)
            estimate=decode(audio,script);document=build_evidence(audio,q,estimate,script,ROUTE,speaker,hashes)
            key=f'{code}_{index}';documents[key]=document;audios[key]=audio;qualities[key]=q;vectors[key]=v;estimates[key]=estimate
            q['script_evidence']=document
            person=store.save('CMU fixture '+code,v,q,ROUTE,person_id=ids.get(code));ids[code]=person['id']
            report['references'].append(dict(label=key,path=str(path),file_sha256=sha256(path),
                base_usable_sec=q['usable_s'],selected_sec=document['retained_unique_sec'],bank_count=len(document['bank']),
                estimated_coverage=document['coverage'],extra_embedding_calls=document['extra_embedding_calls'],extra_elapsed_sec=document['extra_elapsed_sec']))
            rss.append(proc.memory_info().rss)
    assert any(d['bank'] for d in documents.values()),'Native contexts unavailable; inspect evidence before claiming completion'
    gallery=store.gallery(ROUTE,alternate_advisory=True)
    threshold=json.loads((ROOT/'config/s7_profiles.json').read_text())['C088']['identity']['score_threshold']
    for code,index in [('awb',16),('bdl',16),('clb',1),('clb',16)]:
        path,audio,script,q,v=load(code,index);assert v is not None
        estimate=decode(audio,script)
        plain=store.gallery(ROUTE);before=plain.score(v);after=gallery.score(v);assert before==after
        comparison=gallery.last_alternate
        report['queries'].append(dict(label=f'{code}_{index}',source_sha256=sha256(path),fresh_not_in_reference=True,
            same_prompt_as_reference=index==1,expected_person_id=ids.get(code),ordinary_score=before,
            base_alternate=comparison,cosine_threshold_reference_only=threshold,decoded_text=estimate,
            caveat='Whole-query audio versus two reference contexts; no matched-content or calibrated phonetic score. Native pipeline decisions are separate.'))
        rss.append(proc.memory_info().rss)
    assert not {r['file_sha256'] for r in report['references']}&{q['source_sha256'] for q in report['queries']}
    # Same-person/same-phrase sanity is explicitly in-sample, not fresh accuracy.
    gallery.score(vectors['awb_1']);report['in_sample_same_person_same_text']=gallery.last_alternate
    # Intended-text counterexamples use exactly the same source/quality/ASR.
    base=documents['awb_1'];q=qualities['awb_1'];audio=audios['awb_1'];estimate=estimates['awb_1']
    edits={'wrong':'Seven purple turtles dance near distant Jupiter.',
           'skipped':' '.join(base['script']['text'].split()[::2]),
           'repeated':base['script']['text']+' '+base['script']['text']}
    report['script_counterexamples']={}
    for name,script in edits.items():
        doc=build_evidence(audio,q,estimate,script,ROUTE,speaker,hashes)
        assert doc['base_reference_retained_sec']==base['base_reference_retained_sec']
        report['script_counterexamples'][name]=dict(coverage=doc['coverage'],selected_sec=doc['retained_unique_sec'],base_unchanged=True)
    # Physical background/low-level tests: real waveforms, explicitly derived.
    other=audios['bdl_1'];background=audio.copy();length=min(len(audio),len(other));background[:length]=.5*audio[:length]+.5*other[:length]
    report['audio_counterexamples']={}
    for name,x in [('background_overlap',background),('low_level',audio*.01),('short_reply',audio[:6400])]:
        state=EnrollmentQuality(speaker,config,None);state.process(x);quality,vector=state.result(source_kind='derived_CMU_counterexample')
        doc=build_evidence(x,quality,decode(x,base['script']['text']),base['script']['text'],ROUTE,speaker,hashes)
        report['audio_counterexamples'][name]=dict(can_save=quality['can_save'],base_usable_sec=quality['usable_s'],bank_count=len(doc['bank']),selected_sec=doc['retained_unique_sec'],selection_does_not_override_base=True)
    # Actual unchanged C088 temporal naming, not just a threshold on one cosine.
    for code,index in [('awb',16),('clb',1)]:
        path=args.corpus/f'cmu_us_{code}_arctic/wav/arctic_a{index:04d}.wav'
        report['pipeline_queries'].append(native_query(f'{code}_{index}_fresh',path,config,models,store,alternate_advisory=True))
    # Three complete, distinct recordings give the unchanged temporal policy
    # enough opportunities for disjoint support. No short fragments are spliced
    # into references and this constructed QUERY is explicitly identified.
    paths=[args.corpus/f'cmu_us_awb_arctic/wav/arctic_a{n:04d}.wav' for n in (16,17,18)]
    assert not {sha256(p) for p in paths}&{r['file_sha256'] for r in report['references']}
    joined=args.output/'awb_fresh_three_full_recordings.wav'
    sf.write(joined,np.concatenate([sf.read(p,dtype='float32')[0] for p in paths]),16000,subtype='PCM_16')
    long_query=native_query('awb_fresh_three_full_recordings',joined,config,models,store,alternate_advisory=True)
    long_query['construction']='Concatenated COMPLETE distinct query recordings, original order; no silence added, gain or duration manipulation; no query used for reference'
    long_query['sources']=[dict(path=str(p),sha256=sha256(p)) for p in paths]
    report['pipeline_queries'].append(long_query)
    assert all(p['status']=='PASS' and p['actual_gallery_score_calls'] and p['last_alternate_comparison'] for p in report['pipeline_queries'])
    outsider=report['pipeline_queries'][1]
    assert not outsider['confirmed_profile_ids_in_final_rows'] and not any(d['known_profile_id'] for d in outsider['identity_decisions']), 'Impostor was named'
    known=ids['awb'] in long_query['confirmed_profile_ids_in_final_rows']
    report['known_acceptance']='PASS' if known else 'LIMITED_NO_CONFIRMED_NAME'
    report['impostor_unknown']='PASS'
    # Same actual query, resident gallery only; no inference in this comparison.
    import statistics
    plain=store.gallery(ROUTE);query=gallery.matrix[0].copy();costs={}
    for name,g in [('base',plain),('alternate_advisory',gallery)]:
        timings=[]
        for repeat in range(101):
            tick=time.perf_counter();g.score(query);timings.append(time.perf_counter()-tick)
        costs[name+'_median_us']=statistics.median(timings[1:])*1e6
    report['comparison_cost']=dict(costs,scope='100 resident dot-product queries per mode after one warmup; two people; no model inference or timing guarantee')
    report['model_loads']=dict(asr=models.asr_loads,speaker=models.speaker_loads,streams=models.streams)
    report['status']='PASS' if known else 'LIMITED';report['model_sha256']=hashes
    report['resource']=dict(elapsed_sec=time.perf_counter()-began,cpu_sec=proc.cpu_times().user+proc.cpu_times().system-cpu.user-cpu.system,peak_sampled_rss_bytes=max(rss+[proc.memory_info().rss]),measurement='Sampled process RSS, not sustained CM5/peak OS qualification')
    (args.output/'NATIVE_SCRIPT_CHECK.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (args.output/'PRIVATE_SCRIPT_EXAMPLE.json').write_text(json.dumps(base,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','references','audio_counterexamples','model_loads','resource')},indent=2))
    return 0 if report['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
