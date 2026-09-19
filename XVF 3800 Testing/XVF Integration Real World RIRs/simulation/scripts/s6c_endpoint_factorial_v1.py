"""Final exact tracking/endpoint2x2; README_S6C_ENDPOINT_FACTORIAL_V1.md."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,sys,time
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z'
BASE_SHA='da953b22bb267296f6017f89afa0589b75a54b4e0488c63b598d094d3b56cd7f'
EPOCH_SHA='676ead81afe85b5557494bd851e67f34799106a45976e8f7fa6e2e5900989cbc'
ADDITIONS=[('C195','C065','endpoint_only'),('C196','C079','both')]

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def bind(path):
 p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path,sha=None):
 p=Path(path).resolve();raw=p.read_bytes();b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 if sha is not None and b['sha256']!=sha:raise ValueError('Changed source '+str(p))
 return json.loads(raw),b
def save(path,v):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write((json.dumps(v,indent=2,allow_nan=False)+'\n').encode());f.flush();os.fsync(f.fileno())
 return bind(p)

def api():
 epoch,eb=read(REPORT/'EPOCH5_EXECUTION_MANIFEST.json',EPOCH_SHA);root=Path(epoch['root'])/'app'
 files=[b for b in epoch['execution_files'] if root in Path(b['path']).parents]
 if len(files)!=29:raise ValueError('Exact original29 APP files required')
 for b in files:
  if bind(b['path'])!=b:raise ValueError('Frozen APP changed')
 if 'edge_speech_pipeline' in sys.modules:raise ValueError('APP preloaded')
 sys.path.insert(0,str(root))
 from edge_speech_pipeline.research_profiles import ResearchProfile,EndpointAdvisorV2,DeliveredSpatialObservation
 return ResearchProfile,EndpointAdvisorV2,DeliveredSpatialObservation,epoch,eb,files

def change(parent,cid,mode,Profile):
 value=deepcopy(parent['profile']);value['profile_id']=cid+'_'+parent['asr_tap']+'_'+parent['identity_tap'];value['xvf']['mode']=mode
 profile=Profile.from_dict(value)
 if profile.to_dict()!=value:raise ValueError('Profile validation changed undeclared settings')
 original=deepcopy(value);original['profile_id']=parent['profile']['profile_id'];original['xvf']['mode']=parent['profile']['xvf']['mode']
 if original!=parent['profile'] or bool(value['tracker']['cues_enabled'])!=(mode=='both'):raise ValueError('Only exact endpoint routing/profile ID may change')
 return profile

def runtime_reset_fixture(profile,Advisor,Observation,epoch,native_at_one):
 """Execute exact frozen ASR loop with tiny synthetic journal and stub decoder."""
 import numpy as np
 root=Path(epoch['root'])/'app/edge_speech_pipeline';tree=ast.parse((root/'runtime.py').read_bytes())
 cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PipelineEngine');fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_asr_loop')
 ns={'__package__':'edge_speech_pipeline','np':np,'time':time,'SherpaStream':object}
 exec(compile(ast.Module(body=[fn],type_ignores=[]),str(root/'runtime.py'),'exec'),ns)
 class Journal:
  committed_samples=17607;finished=True;duration_sec=committed_samples/16000
  def read(self,cursor,size):return np.zeros(max(0,min(size,self.committed_samples-cursor)),dtype=np.float32)
 class Decoder:
  decode_ms=0.;utterance_index=0
  def __init__(self):self.blocks=[];self.resets=0
  def accept(self,block):self.blocks.append(len(block));return '',bool(native_at_one and sum(self.blocks)==16000)
  def reset_endpoint(self):self.resets+=1;self.utterance_index+=1;return ''
  def finish(self):return ''
 class Provider:
  def evidence(self,start,end):return Observation(20. if end<.2 else 120.,end,sequence=round(end*10),source_start_sec=start,source_end_sec=end)
 events=[];advances=[];failures=[]
 engine=SimpleNamespace(_journal=Journal(),config=SimpleNamespace(sample_rate=16000,journal_read_ms=100,input_gain=1.,partial_display_min_interval_sec=.1),
  _research_v2=True,_research_v3=True,_state='RUNNING',_research_profile=profile,_research_asr_available_sec=0.,_spatial_provider=Provider(),
  _started_monotonic=time.perf_counter(),_telemetry={},_scheduler=object(),_research_utterance_start_sec=0.,
  _emit=lambda kind,t,p:events.append(dict(kind=kind,time=t,payload=p)),_scheduler_advance=lambda *x:advances.append(x),
  _fail=lambda text:failures.append(text),_transcript_event=lambda *a,**k:None)
 decoder=Decoder();ns['_asr_loop'](engine,decoder)
 assert not failures and sum(decoder.blocks)==Journal.committed_samples and decoder.blocks[-1]==7
 assert engine._telemetry['asr_cursor_sec']==Journal.duration_sec and advances[-1][1]==float('inf')
 resets=[e for e in events if e['kind']=='research_asr_reset'];assert len(resets)==decoder.resets==1
 assert resets[0]['payload']['advisory_endpoint'] is True and resets[0]['payload']['native_endpoint']==native_at_one
 assert len([e for e in events if e['kind']=='research_asr_tail_dispatch'])==1 and len([e for e in events if e['kind']=='research_asr_drain'])==1
 return dict(native_and_advice_same_dispatch=native_at_one,resets=1,source_samples=Journal.committed_samples,tail_samples=7,synthetic_decoder=True,real_frozen_asr_loop=True)

def checks(base,Profile,Advisor,Observation,epoch):
 import math
 parent=next(r for r in base['profiles'] if r['candidate_id']=='C065' and r['asr_tap']=='O0');profile=change(parent,'FIXTURE','endpoint_only',Profile)
 rows=[];count=0
 def trace(stop,period=4.,bad=None,rms=0.):
  a=Advisor(profile);result=[]
  for i in range(1,round(stop*10)+1):
   t=i/10;angle=20. if i==1 else 120. if int((t-.2)/period)%2==0 else 20.
   o=Observation(angle,t,sequence=i,source_start_sec=max(0,t-.1),source_end_sec=t)
   if bad:o=bad(o,t,i)
   accepted=a.observe(o,t,rms,.1,0.);assert accepted==a.last_status['accepted'];result.append(dict(t=t,**a.last_status))
  return result
 ordinary=trace(3.);assert sum(r['accepted'] for r in ordinary)==1;count+=1
 cool=trace(8.,2.);assert any(r['reason']=='rate_limited' for r in cool);count+=1
 circuit=trace(90.)
 for reason in ('accepted','circuit_opened','circuit_open'):
  assert any(r['reason']==reason for r in circuit);count+=1
 assert any(r['accepted'] and r['t']>65 for r in circuit);count+=1
 rows.append(dict(case='positive/cooldown/circuit/recovery',ordinary=ordinary,cooldown=[r for r in cool if r['proposal']],circuit=[r for r in circuit if r['proposal']]))
 from dataclasses import replace
 invalids=[('missing',lambda o,t,i:None),('invalid_flag',lambda o,t,i:replace(o,valid=False)),('stale_delivery',lambda o,t,i:replace(o,available_at_sec=t-.5)),
  ('old_source_fresh_receipt',lambda o,t,i:replace(o,source_end_sec=0.)),('low_reliability',lambda o,t,i:replace(o,reliability=.1)),
  ('out_of_fold',lambda o,t,i:replace(o,angle_deg=181.)),('nonfinite_angle',lambda o,t,i:replace(o,angle_deg=float('nan'))),
  ('reused_sequence',lambda o,t,i:replace(o,sequence=1)),('reordered_sequence',lambda o,t,i:replace(o,sequence=100-i))]
 for name,mutate in invalids:
  rs=trace(3.,bad=mutate);assert not any(r['accepted'] for r in rs);count+=1;rows.append(dict(case=name,accepted=0))
 assert not any(r['accepted'] for r in trace(3.,rms=.1));count+=1
 # v3 routing validation rejects inconsistent tracking/endpoint semantics.
 for mode,enabled in [('endpoint_only',True),('both',False),('none',True)]:
  bad=deepcopy(profile.to_dict());bad['xvf']['mode']=mode;bad['tracker']['cues_enabled']=enabled
  try:Profile.from_dict(bad)
  except ValueError:count+=1
  else:raise AssertionError('Invalid routing admitted')
 runtime=[runtime_reset_fixture(profile,Advisor,Observation,epoch,flag) for flag in (False,True)];count+=2
 return dict(status='PASS_FROZEN_ADVISOR_AND_ASR_LOOP_MODEL_FREE',checks=count,rows=rows,runtime_dispatch_fixtures=runtime,
  scope='Actual frozen EndpointAdvisorV2 and ASR loop with synthetic observations/audio and stub decoder. No neural model; positive reachability does not predict activity/benefit on actual telemetry.')

def register():
 targets=[REPORT/'EFFECTIVE_PROFILE_REGISTRY_V7.json',REPORT/'design/ENDPOINT_ADVICE_FACTORIAL_V1.json',REPORT/'endpoint_factorial_v1/FUNCTIONAL_CHECKS.json']
 if any(p.exists() for p in targets):raise ValueError('No overwrite of endpoint registration')
 base,bb=read(REPORT/'EFFECTIVE_PROFILE_REGISTRY_V6.json',BASE_SHA);design,db=read(REPORT/'design/REGISTERED_DESIGN_V1.json')
 Profile,Advisor,Observation,epoch,eb,app=api();fixture=checks(base,Profile,Advisor,Observation,epoch)
 fb=save(targets[2],dict(**fixture,source=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_ENDPOINT_FACTORIAL_V1.md')),epoch=eb,app_bindings=app))
 definitions={c['candidate_id']:c for c in design['candidates']};adds=[];new=[]
 for cid,parent_id,mode in ADDITIONS:
  definition=deepcopy(definitions[parent_id]);definition.update(candidate_id=cid,parent=parent_id,title='N01 normalized joint '+mode,family='endpoint_advice_factorial',disposition='REGISTERED_MISSING_FACTORIAL_NOT_EXECUTED')
  definition['settings']['cue_condition']='REAL_ALIGNED_CUES';definition['settings']['xvf_override']={'mode':mode};definition['settings_sha256']=digest(definition['settings'])
  adds.append(definition)
  for tap in ('O0','O1'):
   parent=next(r for r in base['profiles'] if r['candidate_id']==parent_id and r['asr_tap']==r['identity_tap']==tap)
   p=change(parent,cid,mode,Profile);value=p.to_dict();pb=save(REPORT/'profiles'/cid/(tap+'_ASR_'+tap+'_ID.json'),value);row=deepcopy(parent)
   row.update(candidate_id=cid,parent=parent_id,family='endpoint_advice_factorial',cue_condition='REAL_ALIGNED_CUES',profile=value,profile_binding=pb,profile_digest=p.digest(),
    field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),neural_dependency='FULL_PROFILE_AND_CUES',
    effective_key=digest(dict(profile=value,cue='REAL_ALIGNED_CUES',gallery=row['gallery_condition'],tier=row['enrollment_tier'])))
   new.append(row)
 panel,panelb=read(REPORT/'design/REGISTERED_PANEL_V1.json');bank,bankb=read(SIM/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json')
 empty=[s['case_id'] for s in bank['scenes'] if s['all_speaker_reference_complete'] and s['transcript_valid'] and not any(x.get('kind')=='utterance' for x in s['segments'])]
 if len(empty)!=11 or not set(empty)<=set(panel['case_ids']):raise ValueError('All11 empty/music cases required in panel')
 amendment=dict(schema='jp_s6c_endpoint_advice_factorial.v1',status='REGISTERED_BEFORE_NEW_NATIVE_EXECUTION',created_utc=datetime.now(timezone.utc).isoformat(),
  parent_design=db,parent_registry=bb,candidates=adds,additional_configurations=2,total_registered_configurations=240,
  source=bind(__file__),functional_checks=fb,panel=panelb,bank=bankb,planned_native_cells=224,panel_cases=56,empty_music_case_ids=empty,
  exact_factorial={'C065':'tracking_off endpoint_off','C079':'tracking_on endpoint_off','C195':'tracking_off endpoint_on','C196':'tracking_on endpoint_on'},
  changes='Only executable profile_id and xvf.mode differ from each parent. C195 row cue_condition switches from CUES_OFF to REAL_ALIGNED_CUES for endpoint delivery only; its tracker remains cue-disabled. C196 retains tracking cues. All ASR/segmentation/evidence/punctuation/gain/threshold settings and weights remain exact.',
  chronology='Closes a missing implementation-factorial cell after previous S6C results. No parameters fitted to these new outcomes; not an untouched preregistration.',
  dependency='FULL_PROFILE_AND_CUES for both children; fresh actual full ASR+speaker native sessions. No N01-recipe-only ASR reuse, stitching or rescoring old words as new endpoint outputs.',
  compiler_scope='Dedicated additive compiler applies xvf_override to exact admitted parent profiles; legacy generic compiler does not build this extension.',
  planned_audit={'populations':'All56 paired cases with every11 strict-empty/music case; complete, incomplete target-only and empty insertion denominators separate.',
   'endpoint':'Count advisor proposals/accepted/no_proposal/rate_limited/circuit_opened/circuit_open; native-only/advice-only/both reset flags, actual reset calls and finalized empty/nonempty utterances. Accepted advice coincident with native endpoint is one reset and is not incremental advice-only benefit.',
   'words':'Compare actual first/last raw final words, per-utterance IDs, full concatenated words, deletion/insertion/substitution counts and cp first-display/first-final/latest. Endpoint boundaries can change lexical content; no label-only assumption.',
   'eof':'Verify paired full PCM, exact sample cursors, residual ASR tail and drain, finalization, failures separate from empty text. Advice is evaluated on full dispatch blocks; final short tail is decoded but does not receive an extra advice observation.',
   'costs':'Native model/API/full dispatch/advisor/reset/drain inclusive costs plus process startup/wall/CPU and observed queues; nested costs not added. Fullprofile+cue cache keys and physical session counts distinct from replay reuse.',
   'limits':'A positive synthetic fixture proves hook reachability only. Missing/stale/invalid telemetry must not force advice. No automatic benefit, phonetic latency or CM5 qualification.'},
  no_model_calls=True,no_hardware_calls=True)
 ab=save(targets[1],amendment)
 for row in new:row['endpoint_registration']=ab
 combined=deepcopy(base['profiles'])+new
 if combined[:384]!=base['profiles'] or len(combined)!=388 or len({r['candidate_id'] for r in combined})!=196:raise ValueError('Exact additive240-label registry required')
 registry=deepcopy(base);registry.update(profiles=combined,candidate_count=196,effective_route_count=388,parent_registry=bb,endpoint_registration=ab,source=bind(__file__))
 rb=save(targets[0],registry);print(json.dumps(dict(status='REGISTERED_VALIDATED_NOT_EXECUTED',registry=rb,amendment=ab,checks=fb,total_labels=240,new_native_cells=224)))

def jobs():
 import s6c_orchestrator_scan_v5 as overlay
 eb,spec,common,execution=overlay.load_native('epoch6');registry=common.verified(spec['effective_profile_registry'])
 if registry['candidate_count']!=196 or len(spec['profiles'])!=388:raise ValueError('Exact240-label registry required')
 profiles=[r for r in spec['profiles'] if r['candidate_id'] in {'C195','C196'}];cases=sorted(common.verified(spec['panel'])['case_ids'])
 if len(profiles)!=4 or len(cases)!=56:raise ValueError('Exact224 endpoint cells required')
 inputs={(r['case_id'],r['stream']):r for r in common.verified(spec['input_index'])['rows']};rows=[]
 for p in profiles:
  if p['neural_dependency']!='FULL_PROFILE_AND_CUES' or p['cue_condition']!='REAL_ALIGNED_CUES':raise ValueError('Full native profile/cue dependency mandatory')
  for cid in cases:
   job=execution.make_job(spec,p,cid,'endpoint_advice',False,'v1');execution.validate_job(spec,job,inputs,check_assets=False)
   if job['identity']['profile']!=p['profile'] or job['identity']['cue_condition']!='REAL_ALIGNED_CUES' or job['identity']['telemetry']!=inputs[cid,p['asr_tap']]['telemetry']:raise ValueError('Native job omitted full policy/cue/telemetry')
   rows.append(job)
 b=save(REPORT/'jobs/epoch6/endpoint_advice_v1.json',dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',stage='endpoint_advice',epoch='epoch6',attempt='v1',
  jobs=rows,requested=224,case_ids=cases,candidate_ids=['C195','C196'],profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in profiles],
  execution_manifest=eb,builder_source=bind(__file__),endpoint_registration=registry['endpoint_registration'],created_utc=datetime.now(timezone.utc).isoformat()))
 print(json.dumps(dict(status='PREPARED_NO_MODELS_STARTED',jobs=224,manifest=b)))

if __name__=='__main__':
 p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('action',choices=['register','jobs']);a=p.parse_args()
 for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
 sys.dont_write_bytecode=True;globals()[a.action]()
