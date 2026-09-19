"""Freeze all240 source supports and score verified baseline480. README_S6A.md."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import os
import time
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
from s6a_common import *
import s6a_support_metrics as support
from s6a_text_metrics import score_scene
from s45_h2_run import verify_native_completion
from s4_h2_run import fixed_gain_copy

def freeze(workers=4):
    m=manifest();scenes={s['case_id']:s for s in m['scenes']};guard=AllBankGuard(m['scenes'],'source_support')
    jobs=read(REPORT/'JOB_MANIFEST.json')['jobs'];bycase={j['case_id']:j for j in jobs if j['stream']=='O0'}
    bind(m['noise_binding']['path'],m['noise_binding']['sha256']);noise=read(m['noise_binding']['path'])
    codes=[bind(__file__),bind(support.__file__)]
    def one(cid):
        scene=scenes[cid];job=bycase[cid];guard.require(scene,'freeze_source_support')
        capture=guard.read_json(scene,job['input_provenance']['case_result'])
        audio=guard.read_json(scene,job['analysis_provenance']['audio_metrics'])
        value=support.freeze_scene_support(scene,capture,audio,noise,guard)
        path=REPORT/'support/source'/(cid+'.json')
        record={'support':value,'provenance':{'scene_manifest':bind(BANK/'SCENE_MANIFEST.json'),
            'capture':job['input_provenance']['case_result'],'audio':job['analysis_provenance']['audio_metrics'],'codes':codes}}
        if path.exists():assert read(path)==record,'Frozen source support mismatch'
        else:save(path,record)
        return {'case_id':cid,'support':bind(path),'noise_events':len(value['noise_events']),'output_mapping_available':{o:value['output_mappings'][o]['source_with_rir_to_output_offset_samples'] is not None for o in ('O0','O1')}}
    rows=[]
    with Progress('SOURCE_SUPPORT',240) as progress,concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(one,sorted(scenes)):rows.append(row);progress.done+=1
    save(REPORT/'support/FROZEN_SUPPORT_INDEX.json',{'status':'COMPLETE','count':240,'scenes':rows,'real_noise_scene_count':sum(r['noise_events']>0 for r in rows),
        'policy':support.POLICY,'policy_sha256':stable_hash(support.POLICY),'codes':codes,'scene_manifest':bind(BANK/'SCENE_MANIFEST.json')})
    guard.flush()

def score(workers=4,require_complete=False):
    m=manifest();scenes={s['case_id']:s for s in m['scenes']};guard=AllBankGuard(m['scenes'],'baseline_score')
    guard.protocol=bind(REPORT/'SCORING_PROTOCOL.json')['sha256']
    jobs=read(REPORT/'JOB_MANIFEST.json')['jobs'];sources={r['case_id']:r for r in read(REPORT/'support/FROZEN_SUPPORT_INDEX.json')['scenes']}
    codes=[bind(__file__),bind(support.__file__),bind(Path(__file__).with_name('s6a_text_metrics.py'))]
    def one(job):
        cid,out=job['case_id'],job['stream'];scene=guard.require(cid,'native_score')
        rp=Path(job['report_dir'])/'run_receipt.json'
        if not rp.exists() or read(rp).get('status')!='COMPLETE':return {'case_id':cid,'stream':out,'status':'PENDING_OR_FAILED'}
        wrapper=read(rp);assert wrapper['job_key']==job['job_key'] and wrapper['identity']==job['identity']
        native,nb,chain=native_receipt(rp)
        assert native['raw_audio']==job['raw_audio'] and native['adapter']['gain_scalar']==job['gain']
        for field in ('metrics_binding','events_binding','session_summary_binding'):bind(native[field]['path'],native[field]['sha256'])
        ab=native['adapter']['output_binding'];bind(ab['path'],ab['sha256']);bind(job['raw_audio']['path'],job['raw_audio']['sha256'])
        fixed_gain_copy(job['raw_audio']['path'],ab['path'],job['gain'])
        completion=verify_native_completion(Path(native['session_dir']),Path(ab['path']))
        summary=read(native['session_summary_binding']['path'])
        for key in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
            assert key in summary['telemetry'] and summary['telemetry'][key]==0
        identity={'job_key':job['job_key'],'native':nb,'source_support':sources[cid]['support'],'codes':codes}
        path=REPORT/'baseline_metrics'/cid/(out+'.json')
        if path.exists():
            result=read(path);assert result['analysis_identity']==identity
            return {'case_id':cid,'stream':out,'status':'COMPLETE_REUSED_SCORE','result':bind(path)}
        metrics=read(native['metrics_binding']['path']);events=[json.loads(line) for line in Path(native['events_binding']['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
        text=score_scene(scene,metrics,events,allowed_ids=guard.allowed,duration_s=native['adapter']['duration_s'])
        source=guard.read_json(scene,sources[cid]['support'])['support']
        sm=support.analyze_bound_output(scene,source,out,native,guard)
        parity=None
        oldpath=S5/'text_metrics'/cid/(out+'.json')
        if oldpath.exists():
            old=read(oldpath)
            for field in ('text','overlap_mimo','attributed_cpwer','reference_utterances','reference_speakers','population'):
                assert old[field]==text[field],('S5 score parity',cid,out,field)
            parity='EXACT_S5_NUMERIC_AND_POPULATION_PARITY'
        result={'analysis_identity':identity,'case_id':cid,'stream':out,'historical_split':scene['split'],'population':population(scene),
            'text_metrics':text,'support_metrics':sm,'native_completion':completion,'prior_s5_parity':parity,
            'raw_audio':job['raw_audio'],'gain':job['gain'],'native_receipt':nb,'fresh_s6_native':not bool(job['reuse']),
            'model_wall_s':native.get('model_wall_s'),'adapter':native['adapter']}
        save(path,result);return {'case_id':cid,'stream':out,'status':'COMPLETE','result':bind(path),'s5_parity':parity}
    rows=[];started=time.monotonic()
    with Progress('BASELINE_SCORING',480) as progress,concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(one,jobs):
            rows.append(row);progress.done+=1
            progress.detail={'scored':sum(r['status'].startswith('COMPLETE') for r in rows),'pending':sum(r['status']=='PENDING_OR_FAILED' for r in rows)}
    n=sum(r['status'].startswith('COMPLETE') for r in rows)
    save(REPORT/'BASELINE_SCORE_RECEIPT.json',{'status':'COMPLETE' if n==480 else 'PARTIAL','utc':now(),'requested':480,'complete':n,
        'rows':rows,'workers':workers,'codes':codes,'elapsed_s':time.monotonic()-started,'scope':'S5 numeric scoring definitions on all240, independent source-based supports'})
    guard.flush()
    if require_complete:assert n==480,'Incomplete baseline scoring'

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['freeze','score','all']);parser.add_argument('--workers',type=int,default=4);parser.add_argument('--require-complete',action='store_true')
    args=parser.parse_args();assert 1<=args.workers<=6
    if args.mode in ('freeze','all'):freeze(args.workers)
    if args.mode in ('score','all'):score(args.workers,args.require_complete)
