"""Independent model-free historical parity review; see paired README."""
from __future__ import annotations
import argparse,hashlib,importlib,json,math,tempfile
from copy import deepcopy
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
EXPECTED='7230d48b94ecdea4ab592f0c783b53d779a2f1b4b1cd3abadd06226ec5dc59f9'

def run(output):
    source=HERE/'s6c_historical_paced_analysis_v1.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==EXPECTED
    a=importlib.import_module(source.stem);inv=a.inventory()
    with tempfile.TemporaryDirectory(prefix='s6c_hist_independent_') as td:
        reader=inv.base.MetadataReader(td)
        plan,pb,spec=inv.admit_plan(reader,a.binding(inv.base.PAYLOAD/'paced_controls/b36_v1/MANIFEST.json'))
        code=a.Reader();raw,extract=a.authority_code(plan,spec,code,'research');api=a.pure_adapters(raw,extract)
        job=next(j for j in plan['jobs'] if j['profile_id']=='B36')
        classes=a.research_classes(spec);profile=classes[0].from_dict(job['profile'])
        vector=np.zeros(192,np.float32);vector[0]=1.
        embedding=dict(kind='embedding',event_id='embedding:00000001',source_start_sec=0.,source_end_sec=.5,available_at_sec=.51,vector=vector.tolist(),speech=True,overlap=False)
        segmentation=dict(kind='segmentation',event_id='seg:00000001',source_start_sec=0.,source_end_sec=.5,available_at_sec=.51,speech=True,overlap=False)
        partial=dict(kind='asr',event_id='asr:00000001',utterance_id='1',text='hello',final=False,source_start_sec=0.,source_end_sec=.6,available_at_sec=.62)
        final=dict(kind='asr',event_id='asr:00000002',utterance_id='1',text='hello world',final=True,source_start_sec=0.,source_end_sec=1.,available_at_sec=1.02)
        settings=profile.scheduler
        scheduler=classes[3](classes[2](profile.tracker),spatial_provider=None,cues_enabled=profile.tracker.cues_enabled,
            revision_horizon_sec=settings.revision_horizon_sec,evidence_expiry_sec=settings.evidence_expiry_sec,max_pending_events=settings.max_pending_events,
            max_events=settings.max_events,max_utterances=settings.max_utterances,max_revisions_per_utterance=settings.max_revisions_per_utterance)
        emitted=[]
        def take(value):emitted.extend(value)
        take(scheduler.push(segmentation,lane='speaker'));take(scheduler.push(embedding,lane='speaker'))
        take(scheduler.advance({'speaker':.5,'asr':.5}));take(scheduler.push(partial,lane='asr'))
        take(scheduler.advance({'asr':.6}));take(scheduler.advance({'speaker':.75}));take(scheduler.advance({'asr':.7}))
        take(scheduler.push(final,lane='asr'));take(scheduler.advance({'speaker':1.,'asr':1.}))
        take(scheduler.advance({'speaker':float('inf')}));take(scheduler.advance({'asr':float('inf')}));take(scheduler.finish())
        events=[dict(event_type='research_embedding',payload={**{k:v for k,v in embedding.items() if k not in ('kind','vector','event_id')},'normalized_embedding':vector.tolist(),'evidence_event_id':embedding['event_id']}),
            dict(event_type='research_segmentation',payload=segmentation),dict(event_type='research_asr_observation',payload=partial),dict(event_type='research_asr_observation',payload=final)]
        events += [dict(event_type=r['event_type'],payload=deepcopy(r)) for r in emitted]
        summary=dict(telemetry=dict(scheduler=scheduler.snapshot()))
        vv,ff,ss,aa,cc=api['extract_events'](events)
        expected=api['run_scheduler'](profile,None,dict(features=ff,segmentation=ss,asr_observations=aa,costs=cc),vv,classes)
        native_transcript=[r for r in emitted if r['event_type'].startswith('transcript_')]
        expected_transcript=expected['transcript_events']
        differences=[]
        def compare(left,right,path=''):
            if isinstance(left,dict) and isinstance(right,dict):
                for k in sorted(set(left)|set(right)):
                    if k not in left or k not in right:differences.append(dict(path=path+'/'+k,left=left.get(k),right=right.get(k)))
                    else:compare(left[k],right[k],path+'/'+k)
            elif isinstance(left,list) and isinstance(right,list) and len(left)==len(right):
                for i,(l,r) in enumerate(zip(left,right)):compare(l,r,path+'/'+str(i))
            elif left!=right:differences.append(dict(path=path,left=left,right=right))
        compare(a.logical(native_transcript),a.logical(expected_transcript))
        try:
            a.research_prediction(events,summary,job,api,classes)
            parity=dict(status='PASS')
        except ValueError as exc:parity=dict(status='REJECTED_SYNTHETIC_NATIVE_ROUNDTRIP',error=str(exc))
        assert expected['decisions']==[r['decision'] for r in emitted if r['event_type']=='speaker_decision']
        assert a.logical(expected['snapshot']['scheduler']['utterances'])==a.logical(summary['telemetry']['scheduler']['utterances'])
        assert differences and all(d['path'].endswith(('/release_watermark_lower_bound_sec','/release_after_all_lanes_closed')) for d in differences)
        assert parity['status']=='REJECTED_SYNTHETIC_NATIVE_ROUNDTRIP'
        result=dict(status='SOURCE_FINDING_REPRODUCED',source=a.binding(source),readme=a.binding(HERE/'README_S6C_HISTORICAL_PACED_ANALYSIS_V1.md'),review_source=a.binding(__file__),
            review_readme=a.binding(HERE/'README_TEST_S6C_HISTORICAL_PACED_COMPONENT_V1.md'),manifest=pb,code_sources=code.sources,metadata_sources=[x['source'] for x in reader.sources],
            synthetic_inputs=[segmentation,embedding,partial,final],native_transcript=native_transcript,replayed_transcript=expected_transcript,parity=parity,differences_after_current_exclusions=differences,
            exact_decisions=True,exact_final_utterances=True,model_calls=0,actual_native_cells_read=0,pcm_reads=0,
            finding='Strict transcript parity includes release-watermark fields that differ between real source-cursor lane sealing and immediate modeled-availability replay. The original tracker/utterance outcome is exact in this fixture. This does not establish an actual paced-data failure or license dropping causal availability/support fields.')
        return a.save(output,result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();print(json.dumps(run(args.output)))
