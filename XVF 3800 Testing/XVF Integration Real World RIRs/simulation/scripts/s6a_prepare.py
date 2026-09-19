"""Freeze S6A all-bank coverage, B0 jobs and pre-outcome screening panel. README_S6A.md."""
from __future__ import annotations
import collections
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET
from s6a_common import *
from s45_h2_run import load_alignment, verify_native_completion
from s4_h2_run import fixed_gain_copy
from s4_h2_analysis import normalize

def tags(scene):
    values={'family:'+scene['family_id'], 'population:'+population(scene), 'split:'+scene['split']}
    cfg=scene['receiver_configuration']
    values.update('receiver:'+k+'='+str(v) for k,v in cfg.items())
    for seg in scene['segments']:
        if seg['kind']=='utterance':
            values.update(['corpus:'+seg['dataset'],'quality:'+str(seg.get('quality_partition')),
                           'source_db:'+str(seg.get('relative_source_db',0))])
            seconds=(seg['source_stop_sample']-seg['source_start_sample'])/16000
            values.add('duration:'+('<1' if seconds<1 else '1-2' if seconds<2 else '>=2'))
        else: values.add('noise:'+seg.get('category','unknown'))
    return values

def panel(scenes):
    chosen=[]; covered=set()
    families=sorted({s['family_id'] for s in scenes})
    for round_index in range(3):
        for fam in families:
            options=[s for s in scenes if s['family_id']==fam and s['case_id'] not in chosen]
            options.sort(key=lambda s:(-len(tags(s)-covered),stable_hash({'seed':20260909,'case_id':s['case_id']})))
            selected=options[0];chosen.append(selected['case_id']);covered|=tags(selected)
    return {'case_ids':sorted(chosen),'count':len(chosen),'family_counts':dict(collections.Counter(s['family_id'] for s in scenes if s['case_id'] in chosen)),
            'covered_conditions':sorted(covered),'uncovered_available_conditions':sorted(set().union(*(tags(s) for s in scenes))-covered),
            'selection':'Three per family, greedy uncovered input-condition coverage, deterministic hash tie-break seed20260909; no new outcome read',
            'prior_knowledge':'S5 historical outcomes exist; selection algorithm reads scene metadata only',
            'scope':'Engineering screening, not held-out superiority evidence; every profile uses identical selected scenes and both taps', 'frozen_utc':now()}

def prepare():
    if (REPORT/'JOB_MANIFEST.json').exists():
        row=read(REPORT/'PREPARATION_RECEIPT.json')
        for key in ('jobs','contract','panel','coverage_csv'):bind(row[key]['path'],row[key]['sha256'])
        print(json.dumps({'status':'ALREADY_PREPARED','jobs':480}));return
    REPORT.mkdir(parents=True,exist_ok=True); PAYLOAD.mkdir(parents=True,exist_ok=True)
    resource=resources(True)
    import psutil
    save(REPORT/'RESOURCE_PREFLIGHT.json',{**resource,'cpu_physical':psutil.cpu_count(logical=False),'cpu_logical':psutil.cpu_count(),
        'memory_total_bytes':psutil.virtual_memory().total,'baseline_workers':1,'research_max_independent_workers':6,'inner_numeric_threads':1})
    m=manifest();scenes={s['case_id']:s for s in m['scenes']};guard=AllBankGuard(m['scenes'],'prepare')
    counts=dict(collections.Counter(population(s) for s in scenes.values()))
    assert counts=={'primary_nonoverlap':156,'overlap_complete':47,'ambient_incomplete':26,'strict_empty':11},counts
    save(REPORT/'PROBE_PANEL.json',panel(m['scenes']))
    workbook=bind(WORKBOOK)
    with zipfile.ZipFile(WORKBOOK) as z:doc=ET.fromstring(z.read('word/document.xml'))
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paras=[''.join(t.text or '' for t in p.iter(ns+'t')) for p in doc.iter(ns+'p')]
    (REPORT/'WORKBOOK_CONTEXT.txt').write_text('\n'.join(paras),encoding='utf-8')
    baseline=read(S5/'execution_contract.json')['baseline']
    copied=read(REPORT/'RUN_MANIFEST_INITIAL.json')['baseline_snapshot']
    byname={Path(r['path']).name:r for r in copied}
    for b in baseline['source_identities']:
        name=Path(b['path']).name
        if name in byname:assert byname[name]['sha256']==b['sha256']
    for row in copied:bind(row['snapshot'],row['sha256'])
    for row in baseline['scientific_config']['assets']:bind(row['path'],row['sha256'])
    policy=read(PRIOR/'OUTPUT_LEVEL_POLICY.json');assert policy['fixed_host_gain']==GAINS
    accepted=read(PRIOR/'ACCEPTED_CAPTURES.json');assert accepted['scene_manifest']['sha256']==MANIFEST_SHA
    selected={r['case_id']:r for r in accepted['accepted']};assert set(selected)==set(scenes)
    protocol={'schema':'jp_s6a_protocol_v1','source_metrics':bind(S5/'SCORING_PROTOCOL.json'),'authorized_scenes':240,'outputs':480,
        'historical_split_counts':dict(collections.Counter(s['split'] for s in scenes.values())),'populations':counts,
        'source_reference_instances_expected':777,'fixed_gain':GAINS,'normalization':normalize.__module__+'.normalize',
        'coverage':'All references and failures remain; ambient speech untranscribed, strict empty WER undefined',
        'selection_scope':'All240 exploratory engineering; no independent synthetic holdout claim',
        'baseline_reuse':'Exact weights/config/code/provider/audio/gain and complete native journals; current research app separate',
        'probe_panel':bind(REPORT/'PROBE_PANEL.json'),'component_probe_scope':'screening only; retained all240 confirmation deferred S6B/C',
        'deadline_utc':DEADLINE.isoformat(),'launch_cutoff_utc':LAUNCH_CUTOFF.isoformat(),'prepared_utc':now()}
    save(REPORT/'SCORING_PROTOCOL.json',protocol)
    contract={'schema':'jp_s6a_baseline_contract_v1','baseline':baseline,'snapshot':copied,'scene_manifest':bind(BANK/'SCENE_MANIFEST.json'),
        'accepted_selection':bind(PRIOR/'ACCEPTED_CAPTURES.json'),'protocol':bind(REPORT/'SCORING_PROTOCOL.json'),'workbook':workbook,
        'scope_authority':bind(PACK/'USER_SCOPE_OVERRIDE_V4.json'),'baseline_path_rebinding_only':True,
        'code':[bind(Path(__file__)),bind(Path(__file__).with_name('s6a_common.py')),bind(Path(__file__).with_name('s6a_baseline_entry.py')),bind(Path(__file__).with_name('s6a_baseline.py'))]}
    save(REPORT/'execution_contract.json',contract)
    rows=[];source_bindings={};jobs=[];reused=0
    with Progress('PREPARATION',240) as progress:
        for cid in sorted(scenes):
            scene=guard.require(cid,'input_reference_validation');sel=selected[cid]
            assert sel['audio_valid'] and sel['telemetry_valid']
            capbind=bind(sel['case_result']['path'],sel['case_result']['sha256']);capture=read(capbind['path']);folder=Path(sel['folder'])
            assert capture['status']==capture['audio_integrity_status']==capture['telemetry_status']=='PASS'
            assert capture['final_recipe_capture'] and capture['recipe']==policy['hardware_recipe']
            assert capture['input_scene_sha256']==scene['canonical_audio']['sha256']==sel['input_scene_sha256']
            for idx,seg in enumerate(scene['segments']):
                if seg['kind']!='utterance':continue
                src=m['selected_sources'][seg['source_id']]
                assert src['identity']==seg['speaker_key'] and src['transcript']==seg['transcript']
                assert src['transcript_sha256']==seg['transcript_sha256']
                assert normalize(seg['transcript'])==seg['transcript_normalized'] and seg['transcript_normalized']
                assert seg['whole_clip'] and seg['source_crop_samples']==[0,src['samples']]
                assert seg['source_stop_sample']-seg['source_start_sample']==src['samples']
                assert 0<=seg['source_start_sample']<seg['source_stop_sample']<=round(scene['duration_s']*16000)
                if src['source_id'] not in source_bindings:
                    source_bindings[src['source_id']]={k:bind(src[k]['path'],src[k]['sha256']) for k in ('source_binding','decoded_16k_binding','native_metadata_binding') if src.get(k)}
                rows.append({'case_id':cid,'historical_split':scene['split'],'population':population(scene),'segment_index':idx,
                    'source_id':seg['source_id'],'speaker_key':seg['speaker_key'],'corpus':seg['dataset'],'quality_partition':seg.get('quality_partition'),
                    'original_text':seg['transcript'],'normalized_text':seg['transcript_normalized'],'transcript_sha256':seg['transcript_sha256'],
                    'source_audio_sha256':src['source_binding']['sha256'],'source_start_sample':seg['source_start_sample'],
                    'source_stop_sample':seg['source_stop_sample'],'word_count':len(seg['transcript_normalized'].split()),'status':'VERIFIED_NATIVE_REFERENCE'})
            selection_record={k:sel[k] for k in ('case_id','folder','input_scene_sha256','code_key','split','audio_valid','telemetry_valid','task_scoring_allowed')}
            for out in ('O0','O1'):
                raw=bind(folder/(out+'.wav'),capture['output_audio'][out]['sha256'])
                if scene['split']=='development':
                    alignment,ab,eb,gate=load_alignment(None,cid,out,{'folder':folder,'capture':capture,'case_result_binding':capbind})
                else:
                    from s6a_alignment import analyze, alignment_for
                    audio,ab=analyze(folder,scene)
                    alignment=alignment_for({cid:audio['output_alignment']},cid,out,capture);eb=None
                    historical=read(folder/'s45_analysis_receipt.json')
                    bind(historical['audio_metrics']['path'],historical['audio_metrics']['sha256'])
                    gate=historical['task_use_by_output'][out]
                identity={'contract_sha256':stable_hash(contract),'case_id':cid,'stream':out,'raw_audio_sha256':raw['sha256'],
                    'gain_scalar':GAINS[out],'input_case_result_sha256':capbind['sha256'],'scene_reference_sha256':stable_hash(scene)}
                job={'case_id':cid,'stream':out,'population':population(scene),'identity':identity,'job_key':stable_hash(identity),
                    'raw_audio':raw,'gain':GAINS[out],'alignment':alignment,'level_gate':gate,
                    'input_provenance':{'case_result':capbind,'accepted_record':selection_record},'analysis_provenance':{'audio_metrics':ab,'alignment_mapping':eb},
                    'report_dir':str(REPORT/'h2'/cid/out),'payload_root':str(PAYLOAD/'h2'/cid/out),'reuse':None}
                oldpath=S5/'h2'/cid/out/'run_receipt.json'
                if oldpath.exists():
                    native,nb,chain=native_receipt(oldpath)
                    assert native['raw_audio']==raw and native['adapter']['gain_scalar']==GAINS[out]
                    assert native['initial_profile_files']==0 and native['labels_or_transcripts_sent_to_model'] is False
                    assert native['model_success_has_internal_asset_validation'] and native['exit_code']==0
                    for field in ('metrics_binding','events_binding','session_summary_binding'):bind(native[field]['path'],native[field]['sha256'])
                    adapter=native['adapter']['output_binding'];bind(adapter['path'],adapter['sha256'])
                    fixed_gain_copy(raw['path'],adapter['path'],GAINS[out])
                    completion=verify_native_completion(Path(native['session_dir']),Path(adapter['path']))
                    job['reuse']={'receipt':nb,'chain':chain,'native_completion_reverified':completion};reused+=1
                    save(Path(job['report_dir'])/'run_receipt.json',{'status':'COMPLETE','job_key':job['job_key'],'identity':identity,'case_id':cid,'stream':out,
                         'reused_receipt':nb,'reuse_chain':chain,'audio_duration_s':native['adapter']['duration_s'],'new_model_invocations':0,'verified_utc':now()})
                jobs.append(job)
            progress.done+=1;progress.detail={'references_verified':len(rows),'native_outputs_reused':reused}
    assert len(rows)==777 and len(jobs)==480 and reused==360,(len(rows),len(jobs),reused)
    path=REPORT/'TRANSCRIPT_COVERAGE.csv'
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save(REPORT/'TRANSCRIPT_COVERAGE_RECEIPT.json',{'status':'PASS','scheduled_instances':len(rows),'unique_sources':len(source_bindings),
        'populations':counts,'all_scene_count':240,'intentionally_empty_scene_count':11,'incomplete_environmental_scene_count':26,
        'coverage_csv':bind(path),'source_bindings':source_bindings,'normalized_source_text_preserved':True,'unknown_ambient_filled':False,
        'timing':'Whole-clip schedule and numerical activity estimates; no exact phonetic word timings'})
    save(REPORT/'JOB_MANIFEST.json',{'schema':'jp_s6a_jobs_v1','created_utc':now(),'case_ids':sorted(scenes),'jobs':jobs,
        'requested':480,'compatible_reuse':360,'new_planned':120,'expected_population':counts,'contract':bind(REPORT/'execution_contract.json')})
    save(REPORT/'PREPARATION_RECEIPT.json',{'status':'READY','utc':now(),'jobs':bind(REPORT/'JOB_MANIFEST.json'),
        'contract':bind(REPORT/'execution_contract.json'),'panel':bind(REPORT/'PROBE_PANEL.json'),'coverage_csv':bind(path),
        'pack_files':[bind(p) for p in sorted(PACK.rglob('*')) if p.is_file()],'workbook':workbook})
    guard.flush();print(json.dumps({'status':'READY','outputs':480,'reuse':360,'new':120,'references':777,'populations':counts}),flush=True)

if __name__=='__main__':prepare()
