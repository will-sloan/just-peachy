"""One immutable native/cache pair diagnosis; see README_S6C_NATIVE_TIMING_DIAGNOSIS.md."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json
import s6c_native_gallery_review as parent

R=parent.R
KEY=['C105','O0','O0','S45_08_07']
AUTH_SHA='332602ae80fd3239085f39e74f4234d903b59a9e6e481a358623efbb3212559c'
TIMING={'available_at_sec','modeled_available_at_sec','compute_finished_elapsed_sec','compute_ms','model_api_elapsed_ms','postprocess_compute_ms','asr_decode_ms'}
CHOICE=('evidence_id','anonymous_label','display_label','tracker_id','state','committed','joint_choice','reason','known_profile_id','naming_state','unique_evidence_sec','disjoint_evidence_count','prototype_version','lifecycle_counts')
TRANSCRIPT=('input_event_id','event_type','source_start_sec','source_end_sec','text','display_text','speaker','tracker_id','evidence_id','decision_id','attribution_reason','latest_known_profile_id','latest_naming_state')

def bind(path):
 data=Path(path).read_bytes()
 return dict(path=str(Path(path)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def strip_timing(x):
 if isinstance(x,dict):return {k:strip_timing(v) for k,v in x.items() if k not in TIMING}
 if isinstance(x,list):return [strip_timing(v) for v in x]
 return x

def differences(a,b,prefix=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [v for k in sorted(set(a)|set(b)) for v in differences(a.get(k),b.get(k),prefix+'.'+k)]
 return [] if a==b else [dict(field=prefix,cached=a,native=b)]

def aligned(a,b,field):
 def index(rows):
  result={}
  for x in rows:
   if x[field] in result:raise ValueError('Duplicate observation key')
   result[x[field]]=x
  return result
 aa,bb=index(a),index(b)
 if set(aa)!=set(bb):raise ValueError('Observation keys differ')
 return [(aa[k],bb[k]) for k in aa]

def brief(x,fields):return {k:x.get(k) for k in fields}

def tests():
 assert strip_timing({'x':1,'punctuation':{'compute_ms':2,'text':'a'}})=={'x':1,'punctuation':{'text':'a'}}
 assert strip_timing({'text':'a'})!=strip_timing({'text':'b'})
 assert differences({'p':1},{'p':2})==[dict(field='.p',cached=1,native=2)]
 assert aligned([{'id':'x'}],[{'id':'x'}],'id')==[({'id':'x'},{'id':'x'})]
 for a,b in [([{'id':'x'},{'id':'x'}],[{'id':'x'}]),([{'id':'x'}],[{'id':'y'}])]:
  try:aligned(a,b,'id')
  except ValueError:pass
  else:raise AssertionError('Invalid keys accepted')
 return dict(status='PASS',checks=6,model_calls=0,policy_replays=0)

def run():
 authority=bind(R/'gallery_native_integration_review_v1/RESULT.json')
 if authority['sha256']!=AUTH_SHA:raise ValueError('Changed upstream audit')
 audit=parent.obj(authority)
 chain=next(x for x in audit['native_chains'] if x['key']==KEY)
 predictions=[parent.obj(chain[k]) for k in ('cached_prediction','prediction')]
 receipts=[parent.obj(p['identity']['source']) for p in predictions]
 evidence=[parent.obj(r['evidence']) for r in receipts]
 sources=[authority,chain['cached_prediction'],chain['prediction']]
 for p,r in zip(predictions,receipts):
  sources.extend([p['identity']['source'],r['evidence'],r['vectors'],r['events']])
 if predictions[0]['identity']['profile']!=predictions[1]['identity']['profile']:raise ValueError('Policy mismatch')
 for k in ('telemetry','gallery','cue_condition','gallery_condition','enrollment_tier'):
  if predictions[0]['identity'][k]!=predictions[1]['identity'][k]:raise ValueError('Input condition mismatch')
 vector_equal=parent.raw(receipts[0]['vectors'])==parent.raw(receipts[1]['vectors'])
 lanes={}
 for lane in ('features','embedding_observations','segmentation','asr_observations'):
  identity='source_end_sec' if lane=='segmentation' else 'event_id'
  pairs=aligned(evidence[0][lane],evidence[1][lane],identity)
  lanes[lane]=dict(rows=len(pairs),alignment_key=identity,same_order=[x[identity] for x in evidence[0][lane]]==[x[identity] for x in evidence[1][lane]],
   non_timing_equal=sum(strip_timing(a)==strip_timing(b) for a,b in pairs),
   changed_top_level_fields=dict(Counter(k for a,b in pairs for k in set(a)|set(b) if a.get(k)!=b.get(k))))
 decision_pairs=aligned(predictions[0]['decisions'],predictions[1]['decisions'],'evidence_id')
 choice_changes=[dict(evidence_id=a['evidence_id'],differences=differences(brief(a,CHOICE),brief(b,CHOICE))) for a,b in decision_pairs if brief(a,CHOICE)!=brief(b,CHOICE)]
 transcript_pairs=aligned([r for r in predictions[0]['transcript_events'] if r['event_type'] in ('transcript_partial','transcript_final')],
  [r for r in predictions[1]['transcript_events'] if r['event_type'] in ('transcript_partial','transcript_final')],'input_event_id')
 transcript_changes=[dict(input_event_id=a['input_event_id'],cached=brief(a,TRANSCRIPT),native=brief(b,TRANSCRIPT)) for a,b in transcript_pairs if brief(a,TRANSCRIPT)!=brief(b,TRANSCRIPT)]
 clocks=[];log_rows=[]
 selected={'embedding:00000015','embedding:00000016','asr:00000016','asr:00000017'}
 for label,p,r,e in zip(('cached_source_C065','native_source_C105'),predictions,receipts,evidence):
  inputs=[*e['embedding_observations'],*e['asr_observations']]
  clock={x['event_id']:brief(x,('event_id','evidence_kind','source_start_sec','source_end_sec','available_at_sec')) for x in inputs if x['event_id'] in selected}
  final=next(x for x in p['transcript_events'] if x['event_type']=='transcript_final')
  horizon=p['identity']['profile']['scheduler']['revision_horizon_sec'];expiry=p['identity']['profile']['scheduler']['evidence_expiry_sec']
  clock.update(source_label=label,mature_minus_asr_sec=clock['embedding:00000016']['available_at_sec']-clock['asr:00000016']['available_at_sec'],
   mature_age_since_first_display_sec=clock['embedding:00000016']['available_at_sec']-final['first_display_time'],revision_horizon_sec=horizon,
   final_age_since_mature_source_end_sec=final['available_at_sec']-clock['embedding:00000016']['source_end_sec'],evidence_expiry_sec=expiry,
   first_final=brief(final,('event_id','input_event_id','available_at_sec','first_display_time','speaker','tracker_id','evidence_id','attribution_reason')))
  clocks.append(clock)
  raw=parent.raw(r['events'])
  for i,line in enumerate(raw.splitlines(),1):
   x=json.loads(line);q=x.get('payload',{})
   if q.get('input_event_id') in selected:
    log_rows.append(dict(source_label=label,line=i,event_type=x['event_type'],source_time_sec=x['source_time_sec'],wall_time_utc=x['wall_time_utc'],
     payload=brief(q,('event_id','input_event_id','available_at_sec','input_available_at_sec','release_watermark_lower_bound_sec','speaker','tracker_id','evidence_id','decision_id','attribution_reason'))))
 # Exact matched cue-off parent is read only to admit the proposed sentinel.
 off_chain=next(x for x in audit['native_chains'] if x['key']==['C088','O0','O0','S45_08_07'])
 off=parent.obj(off_chain['prediction']);sources.append(off_chain['prediction'])
 profile_diff=differences(off['identity']['profile'],predictions[1]['identity']['profile'])
 for name in ('research_scheduler.py','research_scheduler_v3.py'):
  sources.append(bind(R.parents[2]/'staging'/'s6c'/'20260910T123540Z'/'epoch2'/'app'/'edge_speech_pipeline'/name))
 result=dict(status='COMPLETE_BOUNDED_DIAGNOSIS',schema='s6c_native_timing_diagnosis.v1',key=KEY,source_bindings=sources,
  vectors_byte_equal=vector_equal,lanes=lanes,decision_rows=len(decision_pairs),discrete_choice_fields=list(CHOICE),discrete_choice_changes=choice_changes,
  transcript_rows=len(transcript_pairs),transcript_semantic_changes=transcript_changes,first_transcript_semantic_difference=transcript_changes[0] if transcript_changes else None,
  clocks=clocks,selected_actual_log_order=log_rows,sentinel_parent_diff=profile_diff,sentinel_source_seconds=predictions[1]['duration_sec']*12,
  scope=['One outcome-selected actual native/cache pair; no model or policy rerun.',
   'Cached C105 policy uses actual C065 frontend source; its original C065 native tracker is not a matched C105 policy result.',
   'Native emitted log order is recorded separately from modeled source availability; UTC timestamps are observer emission clocks, not GUI render timestamps.',
   'Only explicit measured timing keys are removed for neural-content equality; numeric cue reliability and all decision metadata remain unclaimed as bit-identical.',
   'Observed mature/ASR order crossing explains this scheduler path; the machine-level cause of measured duration differences is not established.',
   'Future sentinel: C088/C105, both taps, three repeats, separate exploratory namespace, all outcomes retained; no configuration change.'],
  pure_checks=tests(),model_calls=0,policy_replays=0,development_note='Initial unpublished run stopped before output creation because segmentation has no event_id; corrected to exact unique source_end_sec alignment before this run.')
 out=R/'native_timing_diagnosis_v1';out.mkdir(exist_ok=False)
 result['helper']=bind(__file__);result['readme']=bind(Path(__file__).with_name('README_S6C_NATIVE_TIMING_DIAGNOSIS.md'))
 path=out/'RESULT.json';path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 print(json.dumps(bind(path)))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
 print(json.dumps(tests())) if a.self_test else run()
