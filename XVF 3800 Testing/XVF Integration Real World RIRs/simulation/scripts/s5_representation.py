"""S5 fixed oracle-window embedding diagnostic. See README_S5_REPRESENTATION.md."""
from __future__ import annotations
import argparse
import collections
import dataclasses
import hashlib
import io
import itertools
import json
import math
import os
from pathlib import Path
import sys
import threading
import time

RATE = 16000
WINDOW = 8000
SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S5/20260909T130308Z'
OUT = REPORT / 'representation'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
BANK_SHA = '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
REPO = SIM.parents[2]
H2 = REPO / 'Software Validation from Datasets/Evaluation Tool'
POLICY = {
    'schema': 'jp_s5_oracle_selection_v1', 'window_samples': WINDOW, 'sample_rate': RATE,
    'maximum_windows_per_participant_scene': 4, 'maximum_paired_windows': 1000,
    'activity': 'Existing source-energy active ranges, already shifted by retained RIR800 samples; require actual ranges, never whole-file fallback',
    'margin': 'Trim each active interval by ceil((0.020 + maximum saved output lag spread seconds)*16000); saved spread is not calibrated timing certainty',
    'isolation': 'Exclude every other utterance full convolution envelope expanded by the same margin; require complete all-speaker references',
    'window_position': 'Center of the longest remaining contiguous interval; tie earliest; one candidate per whole utterance',
    'selection': 'Round-robin corpus-qualified speaker IDs over hash-ordered candidates; globally unique source PCM and source ID; max4 participant/scene, max1000 paired windows',
    'genuine': 'Disjoint selected windows per corpus-qualified identity, different source PCM, source ID and normalized prompt; prefer matching room/family/quality/RIR before deterministic hash',
    'impostor': 'One per genuine anchor, different same-corpus identity, same quality as genuine second window; minimize reuse then condition mismatch then fixed hash; unique unordered pairs',
    'labels': 'Corpus-qualified source identity only; no biometric verification or pretraining-exposure claim',
    'scope': 'Oracle-window representation distribution, not online tracking/naming/DER; no threshold tuning or feedback',
}


def stamp():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def binding(path, expected=None):
    p = Path(path).resolve(); before = p.stat(); h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns): raise ValueError('Changed input: '+str(p))
    if expected and h.hexdigest() != expected: raise ValueError('Hash mismatch: '+str(p))
    return {'path': str(p), 'sha256': h.hexdigest(), 'bytes': after.st_size}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(temp, p)


class Guard:
    def __init__(self, scenes):
        self.scenes = {s['case_id']: s for s in scenes}; self.access = collections.Counter(); self.denied = []
        self.cache = {}; self.inputs = {}
    def require(self, case_id, operation):
        s = self.scenes.get(case_id)
        if not s or s.get('split') != 'development' or s.get('task_scoring_allowed') is not True:
            self.denied.append({'case_id':case_id,'operation':operation})
            raise PermissionError('Development allowlist refused BEFORE access: '+case_id)
        self.access[(case_id, operation)] += 1
        return s
    def path(self, case_id, b, operation):
        self.require(case_id, operation)
        p = Path(b['path']); st = p.stat(); key = (str(p.resolve()), st.st_size, st.st_mtime_ns, b['sha256'])
        if key not in self.cache:
            actual = binding(p, b['sha256'])
            if b.get('bytes', actual['bytes']) != actual['bytes']: raise ValueError('Byte mismatch')
            self.cache[key] = actual; self.inputs[actual['path']] = actual
        return p
    def json(self, case_id, b):
        return read(self.path(case_id, b, 'timing_metadata'))
    def receipt(self):
        return {'reserve_model_accesses':0,'reserve_audio_accesses':0,'reserve_performance_accesses':0,
                'scope':'This diagnostic application guard; not an OS access audit',
                'permitted_calls':[{'case_id':k[0],'operation':k[1],'count':v} for k,v in sorted(self.access.items())],
                'denied_before_access':self.denied,'verified_inputs':list(self.inputs.values())}


def union(ranges):
    out=[]
    for a,b in sorted(ranges):
        if b <= a: continue
        if out and a <= out[-1][1]: out[-1][1]=max(out[-1][1], b)
        else: out.append([a,b])
    return out


def subtract(ranges, blockers):
    out=[]
    for a,b in union(ranges):
        for x,y in union(blockers):
            if y<=a or x>=b: continue
            if x>a: out.append([a,min(x,b)])
            a=max(a,y)
            if a>=b: break
        if a<b: out.append([a,b])
    return out


def candidate_interval(seg, other_segments, margin):
    lo,hi=seg['source_start_sample']+800,seg['source_stop_sample']+800
    active=union(seg.get('activity_ranges_samples_estimated') or [])
    if any(a<lo or b>hi for a,b in active): raise ValueError('Source activity outside file support')
    trimmed=[[a+margin,b-margin] for a,b in active if b-a>=WINDOW+2*margin]
    blocked=[[o['source_start_sample']-margin,o['convolution_stop_sample']+margin]
             for o in other_segments if o['kind']=='utterance']
    eligible=[(a,b) for a,b in subtract(trimmed,blocked) if b-a>=WINDOW]
    if not eligible: return None
    a,b=min(eligible,key=lambda p:(-(p[1]-p[0]),p[0]))
    start=a+(b-a-WINDOW)//2
    return [start,start+WINDOW]


def choose_windows(candidates, maximum=1000):
    queues=collections.defaultdict(list)
    for w in candidates: queues[w['speaker_key']].append(w)
    for key in queues: queues[key].sort(key=lambda w:digest([w['case_id'],w['segment_index'],w['source_id']]))
    used_pcm=set(); used_sources=set(); counts=collections.Counter(); selected=[]
    while queues and len(selected)<maximum:
        for identity in sorted(list(queues)):
            while queues[identity]:
                w=queues[identity].pop(0); group=(w['case_id'],w['participant_id'])
                if w['source_pcm_sha256'] in used_pcm or w['source_id'] in used_sources or counts[group]>=4: continue
                w=dict(w);w['window_id']=f'W{len(selected)+1:04d}'; selected.append(w)
                used_pcm.add(w['source_pcm_sha256']);used_sources.add(w['source_id']);counts[group]+=1
                break
            if not queues[identity]: del queues[identity]
            if len(selected)>=maximum: break
    return selected


def condition_distance(a,b):
    return sum(a.get(k)!=b.get(k) for k in ('room_table','family_id','quality_partition','rir_id','relative_source_db','noise_ids'))


def comparisons(windows):
    byid=collections.defaultdict(list)
    for w in windows: byid[w['speaker_key']].append(w)
    genuine=[]; unused=[]
    for identity,group in sorted(byid.items()):
        pending=sorted(group,key=lambda w:digest(['genuine',w['window_id']]))
        while pending:
            a=pending.pop(0)
            options=[b for b in pending if b['source_id']!=a['source_id'] and b['source_pcm_sha256']!=a['source_pcm_sha256'] and b['prompt_group']!=a['prompt_group']]
            if not options: unused.append(a['window_id']);continue
            b=min(options,key=lambda b:(condition_distance(a,b),digest([a['window_id'],b['window_id']])))
            pending.remove(b);genuine.append({'kind':'genuine','left':a['window_id'],'right':b['window_id']})
    lookup={w['window_id']:w for w in windows};impostors=[];loads=collections.Counter();used=set();gaps=[]
    for g in genuine:
        a,b=lookup[g['left']],lookup[g['right']]
        options=[w for w in windows if w['speaker_key']!=a['speaker_key'] and w['dataset']==b['dataset']
                 and w['quality_partition']==b['quality_partition'] and w['prompt_group']!=a['prompt_group']
                 and w['source_pcm_sha256']!=a['source_pcm_sha256'] and tuple(sorted((a['window_id'],w['window_id']))) not in used]
        if not options: gaps.append({'genuine_left':g['left'],'genuine_right':g['right'],'reason':'no_same_corpus_quality_different_identity'});continue
        c=min(options,key=lambda w:(loads[w['window_id']],condition_distance(b,w),digest([a['window_id'],w['window_id']])))
        key=tuple(sorted((a['window_id'],c['window_id'])));used.add(key);loads[c['window_id']]+=1
        g['balanced_pair_id']=f'B{len(impostors)+1:04d}'
        impostors.append({'kind':'impostor','left':a['window_id'],'right':c['window_id'],'balanced_pair_id':g['balanced_pair_id']})
    trials=genuine+impostors
    for i,t in enumerate(trials): t['comparison_id']=f'C{i+1:04d}'
    return trials,{'unpaired_windows':unused,'unmatched_impostor_gaps':gaps,'maximum_impostor_endpoint_reuse':max(loads.values(),default=0),
                   'genuine_count':len(genuine),'impostor_count':len(impostors)}


def distributions(rows):
    keys=('dataset','quality_partition','speaker_key','room_table','family_id','orientation','obstructed','relative_source_db','role','whole_clip_bin')
    return {k:dict(sorted(collections.Counter(str(w.get(k)) for w in rows).items())) for k in keys}


def source_lookup(bank):
    inputs=[];sources={}
    for k in ('sources_binding','legacy_development_sources_binding'):
        b=bank[k];inputs.append(binding(b['path'],b['sha256']));d=read(b['path'])
        for s in d['sources']:
            if s['source_id'] in sources: raise ValueError('Duplicate source metadata')
            sources[s['source_id']]=s
    return sources,inputs


def prepare():
    if (OUT/'WINDOW_PLAN.json').exists(): raise FileExistsError('Frozen WINDOW_PLAN already exists; preserve it and use --validate-plan')
    bank_binding=binding(BANK,BANK_SHA);bank=read(BANK);guard=Guard(bank['scenes'])
    job_binding=binding(REPORT/'JOB_MANIFEST.json');jobs=read(job_binding['path']);contract_binding=binding(REPORT/'execution_contract.json')
    contract=read(contract_binding['path']);protocol_binding=binding(contract['scoring_protocol']['path'],contract['scoring_protocol']['sha256'])
    protocol=read(protocol_binding['path']);assert protocol['optional_representation']['window_s']==.5
    assert protocol['optional_representation']['maximum_paired_windows']==1000
    bycase=collections.defaultdict(dict)
    for j in jobs['jobs']:
        guard.require(j['case_id'],'job_metadata')
        if j['identity']['contract_sha256']!=digest(contract): raise ValueError('Job contract mismatch')
        if j['stream'] in bycase[j['case_id']]: raise ValueError('Duplicate job')
        bycase[j['case_id']][j['stream']]=j
    if len(bycase)!=180 or any(set(v)!={'O0','O1'} for v in bycase.values()): raise ValueError('Require180 paired development jobs')
    sources,source_bindings=source_lookup(bank);candidates=[];exclusions=[];timing=[]
    for cid,pair in sorted(bycase.items()):
        scene=guard.require(cid,'window_selection')
        if not scene['all_speaker_reference_complete']:
            exclusions.append({'case_id':cid,'reason':'incomplete_ambient_speech_reference'});continue
        if any(j['level_gate']=='QUARANTINED' for j in pair.values()):
            exclusions.append({'case_id':cid,'reason':'frozen_gross_level_quarantine'});continue
        capture=guard.json(cid,pair['O0']['input_provenance']['case_result'])
        audio=guard.json(cid,pair['O0']['analysis_provenance']['audio_metrics'])
        if capture['case_id']!=cid or audio['case_id']!=cid: raise ValueError('Timing case mismatch')
        if pair['O0']['analysis_provenance']['audio_metrics']!=pair['O1']['analysis_provenance']['audio_metrics']: raise ValueError('Different paired timing input')
        offset=capture['payload']['capture_minus_source_offset_samples'];mappings={};spreads=[]
        for out,j in pair.items():
            lag=audio['streams'][out].get('relative_delay_median_samples')
            spread=audio.get('output_alignment',{}).get(out,{}).get('uncertainty_s')
            if offset is None or lag is None or spread is None or not math.isfinite(spread) or spread<0: break
            exact=int(offset+lag)
            if abs((j['alignment']['alignment_offset_s']-.05)*RATE-exact)>1e-5: raise ValueError('Job saved mapping disagrees')
            mappings[out]={'source_with_rir_to_output_offset_samples':exact,'saved_lag_spread_s':spread,
                           'raw_audio':j['raw_audio'],'gain':j['gain'],'job_key':j['job_key']}
            spreads.append(spread)
        if set(mappings)!={'O0','O1'}:
            exclusions.append({'case_id':cid,'reason':'missing_or_invalid_saved_mapping_or_spread'});continue
        margin=math.ceil((.02+max(spreads))*RATE)
        timing.append({'case_id':cid,'margin_samples':margin,'mappings':mappings})
        for index,seg in enumerate(scene['segments']):
            if seg['kind']!='utterance': continue
            s=sources[seg['source_id']]
            if s['split']!='development' or s['usage']!='probe' or s['identity']!=seg['speaker_key']: raise PermissionError('Non-development probe identity')
            if not seg['whole_clip'] or not seg.get('activity_ranges_samples_estimated'):
                exclusions.append({'case_id':cid,'segment_index':index,'reason':'no_whole_clip_estimated_activity'});continue
            interval=candidate_interval(seg,[o for n,o in enumerate(scene['segments']) if n!=index],margin)
            if interval is None:
                exclusions.append({'case_id':cid,'segment_index':index,'source_id':seg['source_id'],'reason':'no_halfsecond_after_active_boundary_and_other_utterance_envelope_exclusion'});continue
            duration=(seg['source_stop_sample']-seg['source_start_sample'])/RATE
            candidates.append({'case_id':cid,'segment_index':index,'speaker_key':seg['speaker_key'],'participant_id':seg['participant_id'],
                'source_id':seg['source_id'],'source_pcm_sha256':s['decoded_pcm_sha256'],'source_binding':s['source_binding'],
                'prompt_group':s['prompt_group'],'parent_book':s.get('parent_book'),'dataset':seg['dataset'],'quality_partition':seg['quality_partition'],
                'room_table':scene['receiver_configuration']['room_table'],'family_id':scene['family_id'],'orientation':scene['receiver_configuration']['orientation'],'obstructed':scene['receiver_configuration']['obstructed'],
                'relative_source_db':seg['relative_source_db'],'role':seg['role'],'rir_id':seg['rir_id'],
                'noise_ids':sorted({x['source_id'] for x in scene['segments'] if x['kind']=='real_noise'}),
                'whole_clip_duration_s':duration,'whole_clip_bin':'<1s' if duration<1 else '1-<2s' if duration<2 else '>=2s',
                'reference_interval_with_rir_samples':interval,'source_relative_interval_samples':[x-seg['source_start_sample']-800+seg['source_crop_samples'][0] for x in interval],
                'margin_samples':margin,'outputs':{o:{**m,'interval_samples':[x+m['source_with_rir_to_output_offset_samples'] for x in interval]} for o,m in mappings.items()}})
    selected=choose_windows(candidates);trials,pairing=comparisons(selected)
    plan={'schema':'jp_s5_representation_window_plan_v1','status':'FROZEN_BEFORE_EMBEDDINGS_AND_COSINES','frozen_utc':stamp(),
          'contract_semantic_sha256':digest(contract),'contract_hash_scope':'job identity uses sorted compact parsed-JSON hash; input binding uses actual file bytes',
          'policy':POLICY,'policy_sha256':digest(POLICY),'input_bindings':[bank_binding,job_binding,contract_binding,protocol_binding]+source_bindings,
          'code_binding':binding(__file__),'README_binding':binding(Path(__file__).with_name('README_S5_REPRESENTATION.md')),
          'selection_uses_output_waveforms':False,'selection_uses_cosines':False,'selection_uses_saved_output_timing_only':True,
          'windows':selected,'comparisons':trials,'pairing':pairing,'candidate_count':len(candidates),'selected_count':len(selected),
          'maximum_paired_windows':1000,'candidate_distributions':distributions(candidates),'selected_distributions':distributions(selected),
          'exclusions':exclusions,'timing':timing,'access':guard.receipt(),
          'scope':'No waveform/model/prediction opens in preparation. Corpus-qualified identities; no actual online identity or threshold performance.',
          'limitations':['Estimated activity and lag spread are not phonetic ground truth','Repeated source clips removed globally, so conditions are not balanced or a causal RIR experiment',
                        'Genuine pairs and impostor anchors share windows; no independent-window or population confidence claim',
                        'Oracle speech selection bypasses online speech/embedding eligibility gates without changing the representation backend']}
    plan['plan_sha256']=digest(plan)
    save(OUT/'WINDOW_PLAN.json',plan)
    print(json.dumps({'status':plan['status'],'candidates':len(candidates),'selected':len(selected),'speakers':len(plan['selected_distributions']['speaker_key']),**pairing},default=str))
    return plan


def validate_plan(path=None):
    plan=read(path or OUT/'WINDOW_PLAN.json');copy=dict(plan);expected=copy.pop('plan_sha256')
    if digest(copy)!=expected or plan['policy_sha256']!=digest(POLICY): raise ValueError('Changed frozen plan/policy')
    for b in plan['input_bindings']: binding(b['path'],b['sha256'])
    binding(plan['code_binding']['path'],plan['code_binding']['sha256'])
    binding(plan['README_binding']['path'],plan['README_binding']['sha256'])
    bank=read(BANK);guard=Guard(bank['scenes']);seen=set();counts=collections.Counter()
    for w in plan['windows']:
        guard.require(w['case_id'],'validate_window')
        if w['source_pcm_sha256'] in seen: raise ValueError('Repeated source PCM')
        seen.add(w['source_pcm_sha256']);counts[(w['case_id'],w['participant_id'])]+=1
        for o in ('O0','O1'):
            a,b=w['outputs'][o]['interval_samples']
            if b-a!=WINDOW or a<0: raise ValueError('Invalid window bounds')
            if w['outputs'][o]['gain']!=({'O0':1.4125375446227544,'O1':1.0}[o]): raise ValueError('Recipe changed')
    if len(seen)>1000 or max(counts.values(),default=0)>4: raise ValueError('Plan cap exceeded')
    return plan,guard


def backend_contract(plan):
    """Validate frozen sources and config before importing native embedding backend."""
    if os.environ.get('EDGE_SPEECH_ASSET_ROOT'): raise ValueError('Ambient asset override')
    contract=read(REPORT/'execution_contract.json');baseline=contract['baseline'];source_checks=[]
    for b in baseline['source_identities']: source_checks.append(binding(b['path'],b['sha256']))
    if Path(sys.executable).resolve()!=Path(baseline['python']).resolve(): raise ValueError('Run embedding command with exact frozen H2 Python')
    sys.path.insert(0,str(H2))
    from app.edge_speech_pipeline.config import PipelineConfig
    config=PipelineConfig();actual=json.loads(json.dumps(dataclasses.asdict(config),default=str))
    actual.pop('session_root');actual.pop('profile_root')
    if actual!=baseline['scientific_config']: raise ValueError('Scientific config differs from frozen contract')
    if config.sample_rate!=RATE or config.embedding_window_sec!=.5 or config.speaker_threads!=2: raise ValueError('Embedding shape/thread contract')
    import importlib.metadata
    previous=read(baseline['baseline_manifest']['path']);versions={k:importlib.metadata.version(k) for k in ('numpy','scipy','soundfile','onnxruntime')}
    if any(v!=previous['versions'][k] for k,v in versions.items()): raise ValueError('Native representation environment version mismatch')
    from app.edge_speech_pipeline.models import SpeakerModels, _ort_session
    from app.edge_speech_pipeline.assets import validate_assets
    from app.edge_speech_pipeline.audio import AudioJournal
    asset=config.asset('redimnet2_b2_fp32');validate_assets([asset])
    # Use the native constructor's exact ReDim session settings and native embed method,
    # without loading an unused segmentation model or creating an H2/session/profile.
    model=SpeakerModels.__new__(SpeakerModels);model._redim=_ort_session(str(asset.path),config.speaker_threads)
    model._lock=threading.Lock();model.last_embed_ms=0.0
    if model._redim.get_providers()!=['CPUExecutionProvider']: raise ValueError('Provider changed')
    return model,AudioJournal,{'source_bindings':source_checks,'asset_binding':binding(asset.path,asset.sha256),'versions':versions,
             'provider':model._redim.get_providers(),'speaker_threads':config.speaker_threads,
             'native_methods':['SpeakerModels.embed','_ort_session','AudioJournal.append'],
             'session_or_enrollment_created':False,'segmentation_or_ASR_loaded':False}


def native_pcm16_window(raw, gain, journal_class):
    import numpy as np
    values=(np.asarray(raw,dtype=np.float32).astype(np.float64)*gain).astype(np.float32)
    if not np.isfinite(values).all() or np.max(np.abs(values))>1: raise ValueError('Gain-generated nonfinite/fullscale overflow')
    journal=journal_class.__new__(journal_class);journal._writer=io.BytesIO();journal._condition=threading.Condition()
    journal.finished=False;journal.committed_samples=0
    journal.append(values)
    pcm=journal._writer.getvalue()
    if len(pcm)!=WINDOW*2: raise ValueError('Incorrect native journal window length')
    return np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768.0,hashlib.sha256(pcm).hexdigest()


def summarize(plan, vectors, records):
    import numpy as np
    lookup={w['window_id']:w for w in plan['windows']};scores=[];missing=[]
    for t in plan['comparisons']:
        if any((t[k],o) not in vectors for k in ('left','right') for o in ('O0','O1')):
            missing.append(t['comparison_id']);continue
        a,b=lookup[t['left']],lookup[t['right']]
        row={**t,'dataset':a['dataset'],'quality_partition':a['quality_partition'] if a['quality_partition']==b['quality_partition'] else 'MIXED',
             'family_id':a['family_id'] if a['family_id']==b['family_id'] else 'MIXED',
             'room_table':a['room_table'] if a['room_table']==b['room_table'] else 'MIXED',
             'same_rir':a['rir_id']==b['rir_id'],'same_identity':a['speaker_key']==b['speaker_key']}
        for o in ('O0','O1'): row[o]=float(np.dot(vectors[(t['left'],o)],vectors[(t['right'],o)]))
        row['O1_minus_O0']=row['O1']-row['O0'];scores.append(row)
    summaries=[]
    for stratum in ('ALL','dataset','quality_partition','family_id','room_table','same_rir'):
        groups=collections.defaultdict(list)
        for r in scores: groups[(r['kind'],'ALL' if stratum=='ALL' else str(r[stratum]))].append(r)
        for (kind,value),rows in sorted(groups.items()):
            s={'stratum':stratum,'value':value,'kind':kind,'paired_comparisons':len(rows)}
            for o in ('O0','O1','O1_minus_O0'):
                v=np.asarray([r[o] for r in rows]);s[o]={'mean':float(v.mean()),'median':float(np.median(v)),'p10':float(np.quantile(v,.1)),'p90':float(np.quantile(v,.9)),'min':float(v.min()),'max':float(v.max())}
            summaries.append(s)
    separation={}
    for o in ('O0','O1'):
        matched=collections.defaultdict(dict)
        for r in scores:
            if r.get('balanced_pair_id'): matched[r['balanced_pair_id']][r['kind']]=r[o]
        deltas=[v['genuine']-v['impostor'] for v in matched.values() if set(v)=={'genuine','impostor'}]
        separation[o]={'balanced_anchor_groups':len(deltas),'mean_genuine_minus_impostor':float(np.mean(deltas)) if deltas else None,
                       'median_genuine_minus_impostor':float(np.median(deltas)) if deltas else None}
    return {'schema':'jp_s5_representation_results_v1','status':'COMPLETE_WITH_LIMITATIONS' if not missing else 'PARTIAL_WITH_WINDOW_FAILURES',
            'window_plan_binding':binding(OUT/'WINDOW_PLAN.json'),'planned_paired_windows':len(plan['windows']),
            'completed_paired_windows':sum(all((w['window_id'],o) in vectors for o in ('O0','O1')) for w in plan['windows']),
            'planned_comparisons':len(plan['comparisons']),'complete_paired_comparisons':len(scores),'unavailable_comparison_ids':missing,
            'selected_distributions':plan['selected_distributions'],'pairing':plan['pairing'],'distributions':summaries,'balanced_separation':separation,
            'no_threshold_tuning':True,'not_online_identity_accuracy':True,'reserve_task_accesses':0,
            'limitations':plan['limitations']+['Source identity is corpus metadata; cross-corpus identity unknown','Cosine separation is descriptive; no confidence interval from reused anchors or correlated windows',
              'Oracle selection does not validate the online gate, clustering, memory or reconciliation; output and fixed host gain are one recipe'],
            'scores':scores,'window_status_counts':dict(collections.Counter(r['status'] for r in records))}


def execute():
    import numpy as np
    import soundfile as sf
    import psutil
    plan,guard=validate_plan()
    if (OUT/'RUN_RECEIPT.json').exists(): raise FileExistsError('Preserve prior representation execution; no automatic duplicate model invocation')
    if not plan['windows']:
        save(OUT/'RESULTS.json',{'status':'SKIPPED_NO_ELIGIBLE_STRICT_REFERENCE_WINDOWS','plan_binding':binding(OUT/'WINDOW_PLAN.json')});return
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'): os.environ[name]='1'
    from s5_common import resources, launch_allowed
    resources()
    if not launch_allowed(600): raise RuntimeError('Insufficient bounded launch window before cleanup cutoff')
    process=psutil.Process();started=time.monotonic();vectors={};records=[];model=None
    receipt={'status':'STARTED','started_utc':stamp(),'pid':os.getpid(),'process_creation_time':process.create_time(),
             'window_plan_binding':binding(OUT/'WINDOW_PLAN.json'),'model_invocations':0,'windows':[],'models_loaded':0,
             'maximum_sampled_rss_bytes':process.memory_info().rss,'reserve_task_accesses':0}
    save(OUT/'RUN_RECEIPT.json',receipt)
    try:
        model,journal_class,backend=backend_contract(plan);receipt['backend']=backend;receipt['models_loaded']=1
        for i,w in enumerate(plan['windows']):
            for output in ('O0','O1'):
                guard.require(w['case_id'],'embedding_window')
                item={'window_id':w['window_id'],'case_id':w['case_id'],'output':output,'status':'STARTED'}
                try:
                    if psutil.virtual_memory().available<8*2**30 or process.memory_info().rss>2*2**30: raise RuntimeError('Representation2GiB/OS8GiB memory budget')
                    p=guard.path(w['case_id'],w['outputs'][output]['raw_audio'],'output_audio')
                    a,b=w['outputs'][output]['interval_samples']
                    with sf.SoundFile(p) as f:
                        if f.samplerate!=RATE or f.channels!=1 or f.subtype!='PCM_24' or b>len(f): raise ValueError('Frozen raw format or interval unavailable')
                        f.seek(a);raw=f.read(WINDOW,dtype='float32')
                    waveform,pcm_sha=native_pcm16_window(raw,w['outputs'][output]['gain'],journal_class)
                    receipt['model_invocations']+=1
                    vector=model.embed(waveform)
                    if vector.ndim!=1 or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector),1,atol=1e-5): raise ValueError('Invalid native embedding')
                    vectors[(w['window_id'],output)]=vector
                    item.update(status='COMPLETE',native_pcm16_sha256=pcm_sha,window_rms_fs=float(np.sqrt(np.mean(waveform.astype(np.float64)**2))),
                                compute_ms=model.last_embed_ms,vector_dimension=len(vector),interval_samples=[a,b])
                except Exception as exc:
                    item.update(status='FAILED',error=repr(exc))
                    records.append(item)
                    raise  # Specific contract/model failure: preserve partial; never quietly choose replacement windows.
                records.append(item)
            receipt['maximum_sampled_rss_bytes']=max(receipt['maximum_sampled_rss_bytes'],process.memory_info().rss)
            if i%10==0 or i+1==len(plan['windows']):
                receipt.update(windows=records,completed_paired_windows=i+1,elapsed_s=time.monotonic()-started,updated_utc=stamp())
                save(OUT/'RUN_RECEIPT.json',receipt)
                print(json.dumps({'phase':'ORACLE_REPRESENTATION','paired_windows':i+1,'total':len(plan['windows']),'elapsed_s':receipt['elapsed_s'],'rss_bytes':receipt['maximum_sampled_rss_bytes']}),flush=True)
        result=summarize(plan,vectors,records)
        save(OUT/'RESULTS.json',result)
        # Vectors remain local, never packaged or provided to canonical H2.
        labels=[f'{wid}__{o}' for wid,o in sorted(vectors)]
        np.savez_compressed(OUT/'vectors_local_only.npz',labels=np.asarray(labels),vectors=np.stack([vectors[k] for k in sorted(vectors)]))
        receipt.update(status='COMPLETE',results_binding=binding(OUT/'RESULTS.json'),vectors_local_only_binding=binding(OUT/'vectors_local_only.npz'))
    except Exception as exc:
        receipt.update(status='FAILED_SPECIFIC_CONTRACT_OR_WINDOW',error=repr(exc))
        raise
    finally:
        receipt.update(windows=records,ended_utc=stamp(),elapsed_s=time.monotonic()-started,access=guard.receipt(),
                       session_or_enrollment_created=False,canonical_H2_state_modified=False,model_instance_released=True)
        del model
        save(OUT/'RUN_RECEIPT.json',receipt)
        save(OUT/'RESERVE_ACCESS.json',guard.receipt())


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true');g.add_argument('--validate-plan',action='store_true');g.add_argument('--run',action='store_true')
    a=p.parse_args()
    if a.prepare: prepare()
    elif a.validate_plan:
        plan,_=validate_plan();print(json.dumps({'status':'PASS_FROZEN_PLAN_BINDINGS','paired_windows':len(plan['windows'])}))
    else: execute()

if __name__=='__main__': main()
