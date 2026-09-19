"""Independent one-pair clock/path review. README_TEST_S6C_NATIVE_TIMING_ROOT_REVIEW.md."""
from pathlib import Path
import argparse,gzip,hashlib,json,math
from datetime import datetime,timezone

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6C/20260910T123540Z'
EXPECTED='e9c17810b25452eb7d41df236424a11bbfde9b653062412526776cefefb96e56'

def main(args):
 cache={};reads=[]
 def raw(b):
  p=Path(b['path']);key=str(p.resolve())
  if key not in cache:cache[key]=p.read_bytes()
  data=cache[key]
  assert len(data)==b['bytes'] and hashlib.sha256(data).hexdigest()==b['sha256']
  if b not in reads:reads.append(b)
  return data
 def bind(p):
  data=p.read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 def obj(b):
  data=raw(b);return json.loads(gzip.decompress(data) if str(b['path']).endswith('.gz') else data)
 b=bind(R/'native_timing_diagnosis_v1/RESULT.json');assert b['sha256']==EXPECTED;result=obj(b)
 for source in result['source_bindings']:raw(source)
 assert result['status']=='COMPLETE_BOUNDED_DIAGNOSIS' and result['key']==['C105','O0','O0','S45_08_07']
 epoch=obj(bind(R/'EPOCH2_EXECUTION_MANIFEST.json'))
 for source in result['source_bindings']:
  if Path(source['path']).name in ('research_scheduler.py','research_scheduler_v3.py'):
   assert source in epoch['execution_files']
 authority=obj(result['source_bindings'][0])
 pair=next(r for r in authority['native_chains'] if r['key']==result['key'])
 cached,native=[obj(pair[k]) for k in ('cached_prediction','prediction')]
 cr,nr=[obj(p['identity']['source']) for p in (cached,native)]
 ce,ne=[obj(x['evidence']) for x in (cr,nr)]
 assert raw(cr['vectors'])==raw(nr['vectors'])
 assert cached['identity']['profile']==native['identity']['profile']
 assert all(cached['identity'][k]==native['identity'][k] for k in ('gallery','telemetry','cue_condition','enrollment_tier'))
 assert len(cached['decisions'])==len(native['decisions'])==39
 assert [[d.get(k) for k in result['discrete_choice_fields']] for d in cached['decisions']]==[[d.get(k) for k in result['discrete_choice_fields']] for d in native['decisions']]
 observed=[]
 for prediction,evidence in ((cached,ce),(native,ne)):
  emb={r['event_id']:r for r in evidence['embedding_observations']}
  asr={r['event_id']:r for r in evidence['asr_observations']}
  mature=emb['embedding:00000016'];speech=asr['asr:00000016']
  assert mature['source_end_sec']==9. and speech['source_end_sec']==9.1
  observed.append(mature['available_at_sec']-speech['available_at_sec'])
 assert math.isclose(observed[0],-.0241741,abs_tol=1e-8)
 assert math.isclose(observed[1],.0011398,abs_tol=1e-8)
 latest={r['input_event_id']:r for r in native['transcript_events'] if r['event_type'] in ('transcript_partial','transcript_final')}
 assert latest['asr:00000016']['speaker']=='Speaker_4'
 assert next(r for r in cached['transcript_events'] if r.get('input_event_id')=='asr:00000016')['speaker']=='Speaker_2'
 final=next(r for r in native['transcript_events'] if r['event_type']=='transcript_final')
 mature=next(r for r in ne['embedding_observations'] if r['event_id']=='embedding:00000016')
 profile=native['identity']['profile']['scheduler']
 assert mature['available_at_sec']-final['first_display_time']>profile['revision_horizon_sec']==2.
 assert final['available_at_sec']-mature['source_end_sec']>profile['evidence_expiry_sec']==.75
 assert final['speaker']=='Speaker_4' and final['attribution_reason']=='finalization retains prior utterance label'
 events=[json.loads(line) for line in raw(nr['events']).splitlines() if line.strip()]
 partial=next(i for i,e in enumerate(events) if e['event_type']=='transcript_partial' and e['payload'].get('input_event_id')=='asr:00000016')
 decision=next(i for i,e in enumerate(events) if e['event_type']=='speaker_decision' and e['payload'].get('input_event_id')=='embedding:00000016')
 assert partial<decision and (partial+1,decision+1)==(878,879)
 payload=dict(status='PASS_BOUNDED_INDEPENDENT_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),
  diagnosis=b,helper=bind(Path(__file__)),readme=bind(Path(__file__).with_name('README_TEST_S6C_NATIVE_TIMING_ROOT_REVIEW.md')),
  source_bindings=reads,checks=['Exact declared source bytes and frozen scheduler membership',
   'Actual cached/native same policy, gallery and telemetry','Exact vector archive bytes and39 discrete choice records',
   'Independent mature-minus-ASR sign crossing arithmetic','Actual native partial then mature decision at lines878/879',
   'Beyond2s first-display horizon and .75s final evidence expiry with retained provisional label'],
  observed_mature_minus_asr_sec=observed,neural_calls=0,policy_replays=0,
  scope='One observed pair; supports the logged scheduler path, not general incidence or the machine-level cause of compute-duration changes.')
 if args.output:
  with args.output.open('x',encoding='utf-8') as f:json.dump(payload,f,indent=2,allow_nan=False);f.write('\n')
  print(json.dumps(bind(args.output)))
 else:print(json.dumps({k:v for k,v in payload.items() if k!='source_bindings'},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);main(p.parse_args())
