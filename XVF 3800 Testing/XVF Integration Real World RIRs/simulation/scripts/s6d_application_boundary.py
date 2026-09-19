"""Replay the bound adverse C105 pair and arrival overlays. See README_S6D_APPLICATION.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

SIM=Path(__file__).resolve().parents[1]
REPO=SIM.parents[2]
APP=REPO/'Software Validation from Datasets/Evaluation Tool/app'
sys.path.insert(0,str(APP))
from edge_speech_pipeline.research_profiles_v3 import ResearchProfileV3
from edge_speech_pipeline.research_profiles import JsonSpatialProvider
from edge_speech_pipeline.research_identity_v3 import ResearchGallery
from edge_speech_pipeline.research_s6d import S6DSettings, build_s6d_scheduler
from s6c_replay import scheduler_inputs


def binding(path):
    path=Path(path); raw=path.read_bytes()
    return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}


def verified(b):
    actual=binding(b['path'])
    if actual['sha256']!=b['sha256'] or actual['bytes']!=b['bytes']:
        raise ValueError('Bound source changed: '+b['path'])
    raw=Path(b['path']).read_bytes()
    return json.loads(gzip.decompress(raw) if b['path'].endswith('.gz') else raw)


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    root=SIM/'reports/S6C/20260910T123540Z'
    authority=json.loads((root/'independent_review/NATIVE_TIMING_ROOT_REVIEW_V1.json').read_text())
    diagnosis=verified(authority['diagnosis'])
    bindings=diagnosis['source_bindings']
    preds=[b for b in bindings if '/C105/' in b['path'].replace('\\','/') and b['path'].endswith('O0_O0.json.gz')]
    if len(preds)!=2:
        raise ValueError('Expected exact cached/native C105 pair')
    rows=[];all_sources=[]
    for pred_binding in preds:
        pred=verified(pred_binding)
        receipt=verified(pred['identity']['source'])
        evidence=verified(receipt['evidence'])
        verified_vector=binding(receipt['vectors']['path'])
        if verified_vector!=receipt['vectors']:
            raise ValueError('Vector archive binding changed')
        vectors=np.load(receipt['vectors']['path'],allow_pickle=False)['vectors']
        profile=ResearchProfileV3.from_dict(pred['identity']['profile'])
        gallery_binding=pred['identity']['gallery'];gallery_data=verified(gallery_binding)
        gallery=ResearchGallery(gallery_binding['path'],gallery_data['backend_sha256'])
        telemetry=pred['identity']['telemetry'];verified(telemetry) if not telemetry['path'].endswith('.jsonl') else None
        if binding(telemetry['path'])!=telemetry:
            raise ValueError('Telemetry binding changed')
        all_sources.extend([pred_binding,pred['identity']['source'],receipt['evidence'],receipt['vectors'],gallery_binding,telemetry])
        inputs=scheduler_inputs(evidence,vectors)
        mature=next(x for x in inputs if x['event_id']=='embedding:00000016')
        variants=['observed'] if 'policy_predictions' in pred_binding['path'] else ['observed','asr_before_1ms','exact_tie','asr_after_1ms']
        for variant in variants:
            modified=deepcopy(inputs)
            asr=next(x for x in modified if x['event_id']=='asr:00000016')
            if variant!='observed':
                asr['available_at_sec']=mature['available_at_sec']+{'asr_before_1ms':-.001,'exact_tie':0.,'asr_after_1ms':.001}[variant]
            modified.sort(key=lambda r:(r['available_at_sec'],{'segmentation':0,'embedding':1,'asr':2}[r['kind']],r['event_id']))
            for repair in (False,True):
                settings=S6DSettings(text_delivery=False,boundary_repair=repair)
                scheduler=build_s6d_scheduler(profile,gallery,JsonSpatialProvider(telemetry['path']),None,settings)
                started=time.perf_counter();records=[]
                for ready,group in itertools.groupby(modified,key=lambda r:r['available_at_sec']):
                    for item in group:
                        records.extend(scheduler.push(item,'asr' if item['kind']=='asr' else 'speaker'))
                    records.extend(scheduler.advance({'asr':math.nextafter(ready,math.inf),'speaker':math.nextafter(ready,math.inf)}))
                records.extend(scheduler.finish())
                finals=[r for r in scheduler.snapshot()['utterances'] if r.get('is_final')]
                raw=[r['text'] for r in finals]
                original=[r['text'] for r in pred['final_transcripts_latest']]
                if raw!=original:
                    raise AssertionError('Label-only boundary repair changed raw words')
                rows.append({'source':'cached' if 'policy_predictions' in pred_binding['path'] else 'native','variant':variant,
                    'boundary_repair':repair,'asr_minus_mature_sec':asr['available_at_sec']-mature['available_at_sec'],
                    'raw_words_identical':True,'first_final_labels':[r['first_final_label'] for r in finals],
                    'latest_labels':[r['latest_label'] for r in finals],
                    'known_profile_ids':[r.get('latest_known_profile_id') for r in finals],
                    'revision_counts':[r['revision_count'] for r in finals],
                    'revisions':[r for r in records if r['event_type']=='transcript_label_revision' and r.get('revision_scope')=='s6d_bounded_active_text'],
                    'gallery_queries':scheduler.identity_resolver.query_calls,'elapsed_sec':time.perf_counter()-started})
    result={'schema':'s6d-application-boundary.v1','status':'COMPLETE_REPLAY_ONLY','neural_calls':0,'cases':1,
        'historical_failure':'C105 S45_08_07 O0 original cp 1->21 / 41 words; see bound original score authority',
        'scope':'Exact observed pair plus evaluator scheduling overlays, not new native/GUI/physical timing; cp not recomputed here',
        'settings':S6DSettings(text_delivery=False).receipt(),'sources':all_sources,'rows':rows,
        'helper':binding(__file__),'application_source':binding(APP/'edge_speech_pipeline/research_s6d.py')}
    (output/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'output':str(output/'RESULT.json'),
        'rows':[{k:r[k] for k in ('source','variant','boundary_repair','latest_labels','raw_words_identical')} for r in rows]},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
