"""Independent model-free admission review; see README_TEST_S6C_ENDPOINT_ADMISSION_REVIEW.md."""
from __future__ import annotations
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
EXPECTED={
 'EFFECTIVE_PROFILE_REGISTRY_V6.json':'da953b22bb267296f6017f89afa0589b75a54b4e0488c63b598d094d3b56cd7f',
 'EFFECTIVE_PROFILE_REGISTRY_V7.json':'924f8b35950ba053c636687766ff579b6310b89c2a3cab0befbdf267871d0734',
 'design/ENDPOINT_ADVICE_FACTORIAL_V1.json':'f44ecb1960585420956ab34aab2dfa43126e48742372cf9e801503e0de30da91',
 'endpoint_factorial_v1/FUNCTIONAL_CHECKS.json':'905c0bf9ea00aef0eb570c879b8061a07a40550bc5e35a123c65c6d5faa2e0f2',
 'endpoint_factorial_v1/DEPENDENCY_CHECKS.json':'a147f59cddc0e7e6cea7a031cfa8f2197f185a51ef6fd277f8525da3e8b1ee0a',
 'EPOCH6_EXECUTION_MANIFEST.json':'e7c6e91ed9ceaecc587789d96e24ca5ab0f458711a1e604adff71856f3fad934',
 'jobs/epoch6/endpoint_advice_v1.json':'2deb3bbd3bd3801a282b8da90adc7ea99a7bb807db3119afde8c6f888cd338a8',
 'orchestration/epoch6_endpoint_advice_scan_v1/ADMISSION.json':'e9798a1d73d20aa5d259bcb2b87a5e722dbe45edc11342a4707dd3798f36afdc',
 'orchestration_review/ORCHESTRATOR_SCAN_FIXTURES_v5_epoch6_ready.json':'152bb04c6afd8311078f990cdd1075295be25875456d904aa929992f8d239080'}
sources=[];checks=0
def check(value,label):
 global checks
 if not value:raise AssertionError(label)
 checks+=1
def read(path,expected=None):
 p=Path(path).resolve();raw=p.read_bytes();b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 if expected:check(b['sha256']==expected,'pinned source '+str(p))
 sources.append(b);return json.loads(raw),b
def verify(b):
 value,actual=read(b['path'],b['sha256']);check(actual==b,'whole binding');return value
def file_binding(path):
 p=Path(path).resolve();raw=p.read_bytes();b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());sources.append(b);return b
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def functions(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(path).read_text(encoding='utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def main():
 global checks
 docs={k:read(REPORT/k,v)[0] for k,v in EXPECTED.items()}
 old=docs['EFFECTIVE_PROFILE_REGISTRY_V6.json'];new=docs['EFFECTIVE_PROFILE_REGISTRY_V7.json'];am=docs['design/ENDPOINT_ADVICE_FACTORIAL_V1.json'];ep=docs['EPOCH6_EXECUTION_MANIFEST.json'];jobs=docs['jobs/epoch6/endpoint_advice_v1.json'];ad=docs['orchestration/epoch6_endpoint_advice_scan_v1/ADMISSION.json']
 check(new['profiles'][:384]==old['profiles'],'original384 rows unchanged')
 check(len(new['profiles'])==388 and new['candidate_count']==196 and am['total_registered_configurations']==240,'breadth')
 expected={'C195':('C065','endpoint_only'),'C196':('C079','both')}
 lookup={(r['candidate_id'],r['asr_tap'],r['identity_tap']):r for r in new['profiles']}
 check(len(lookup)==388,'unique routes')
 definitions={c['candidate_id']:c for c in am['candidates']}
 for cid,(parent,mode) in expected.items():
  check(definitions[cid]['parent']==parent and definitions[cid]['settings']['xvf_override']=={'mode':mode},'definition exact change')
  check(definitions[cid]['settings']['cue_condition']=='REAL_ALIGNED_CUES','endpoint source real')
  for tap in ('O0','O1'):
   row=lookup[cid,tap,tap];prior=lookup[parent,tap,tap];p=deepcopy(row['profile'])
   check(p['xvf']['mode']==mode and p['tracker']['cues_enabled']==(cid=='C196'),'actual independent routing')
   p['profile_id']=prior['profile']['profile_id'];p['xvf']['mode']=prior['profile']['xvf']['mode']
   check(p==prior['profile'],'only xvf routing and ID differ')
   check(row['cue_condition']=='REAL_ALIGNED_CUES' and row['neural_dependency']=='FULL_PROFILE_AND_CUES' and row['gallery_condition']=='NONE','fresh native full dependency')
   check(verify(row['profile_binding'])==row['profile'],'profile bytes')
 check(ep['profiles']==new['profiles'] and verify(ep['effective_profile_registry'])==new,'epoch exact registry')
 check(ep['execution_digest']==digest({k:ep[k] for k in ('execution_files','assets','versions','state_policy')}),'epoch digest')
 for older in ('EPOCH2_EXECUTION_MANIFEST.json','EPOCH5_EXECUTION_MANIFEST.json'):
  other,_=read(REPORT/older)
  for key in ('assets','versions','python','input_index','scene_manifest','state_policy'):check(ep[key]==other[key],'native authority '+key)
  def appmap(e):
   root=Path(e['root'])/'app';return {str(Path(b['path']).relative_to(root)):(b['bytes'],b['sha256']) for b in e['execution_files'] if root in Path(b['path']).parents}
  check(len(appmap(ep))==29 and appmap(ep)==appmap(other),'all29 APP byte declarations')
  for name in ('s6c_execution.py','s6c_common.py'):
   a=[b for b in ep['execution_files'] if Path(b['path']).name==name];b=[b for b in other['execution_files'] if Path(b['path']).name==name]
   check(len(a)==len(b)==1 and (a[0]['bytes'],a[0]['sha256'])==(b[0]['bytes'],b[0]['sha256']),'whole frozen module '+name)
 # Hash only small frozen Python modules; bulk model/audio authorities remain
 # declared dependencies that the existing native run revalidates before use.
 for b in ep['execution_files']:
  check(file_binding(b['path'])==b,'frozen execution source bytes')
 panel=verify(ep['panel']);inputs=verify(ep['input_index']);inp={(r['case_id'],r['stream']):r for r in inputs['rows']}
 want={(cid,case,t,t) for cid in expected for case in panel['case_ids'] for t in ('O0','O1')}
 check(len(want)==224 and len(panel['case_ids'])==56,'registered grid')
 check(jobs['requested']==224 and len(jobs['jobs'])==224 and set(jobs['case_ids'])==set(panel['case_ids']),'job count and source scene population')
 check({(j['candidate_id'],j['case_id'],j['asr_tap'],j['identity_tap']) for j in jobs['jobs']}==want,'actual grid exact')
 check(len({j['job_key'] for j in jobs['jobs']})==224,'unique exact native keys')
 for j in jobs['jobs']:
  r=lookup[j['candidate_id'],j['asr_tap'],j['identity_tap']];a=inp[j['case_id'],j['asr_tap']]
  check(j['profile']==r['profile']==j['identity']['profile'],'job effective profile')
  check(j['asr_audio']==a['audio']==j['identity_audio'],'same-tap input once-gained binding')
  check(j['asr_pcm_sha256']==a['audio_pcm_sha256']==j['identity_pcm_sha256'] and j['duration_sec']==a['duration_sec'],'whole PCM/duration declaration')
  cue=None if r['cue_condition']=='CUES_OFF' else a['telemetry']
  check(j['telemetry']==cue and j['gallery'] is None and not j['realtime'],'cue/gallery/nonpaced')
  identity=dict(schema='jp_s6c_native_job.v1',execution_digest=ep['execution_digest'],profile=r['profile'],cue_condition=r['cue_condition'],gallery_condition='NONE',enrollment_tier=None,
   asr_audio=a['audio'],identity_audio=a['audio'],telemetry=cue,gallery=None,gain={'O0':'historical +3dB already applied once','O1':'unity','adapter':1.},origin='same canonical capture sample-zero pair; no per-utterance alignment',realtime=False,fresh_state=True,inner_threads=1,provider='CPUExecutionProvider/cpu')
  check(j['identity']==identity and j['job_key']==digest(identity),'independent full job identity')
  target=Path('G:/Just_Peachy_S6C/20260910T123540Z/epoch6/endpoint_advice')/j['candidate_id']/j['case_id']/(j['asr_tap']+'_'+j['identity_tap'])/'v1'
  check(Path(j['folder']).resolve()==target.resolve(),'exact new output namespace')
  check(j['recipe_id']=='N01','actual native recipe')
 check(verify(ad['jobs'])==jobs and verify(ad['native_epoch'])==ep and ad['workers']==4,'prepared coordinator binding')
 for b in ad['sources']:check(file_binding(b['path'])==b,'coordinator source binding')
 f3=functions(SIM/'scripts/s6c_orchestrator_scan_v4.py');f4=functions(SIM/'scripts/s6c_orchestrator_scan_v5.py')
 stable=('compatible_native','invocation_dirs','closed_identity','prior_invocations','validate_manifest','validate_name','prepare','run')
 for name in stable:
  if name=='run':
   check(f3[name].count('Prepared V3 admission required')==1 and f4[name].count('Prepared V5 admission required')==1,'only declared coordinator version error text')
   check(f3[name].replace('Prepared V3 admission required','Prepared V5 admission required')==f4[name],'coordinator run otherwise AST exact')
  else:check(f3[name]==f4[name],'unchanged coordinator '+name)
 # Independently reproduce actual frozen advisor and original ASR-loop fixtures.
 sys.path.insert(0,str(SIM/'scripts'));import s6c_endpoint_factorial_v1 as builder
 Profile,Advisor,Observation,fixture_epoch,_,_=builder.api()
 result=builder.checks(old,Profile,Advisor,Observation,fixture_epoch)
 owner=docs['endpoint_factorial_v1/FUNCTIONAL_CHECKS.json']
 check(result['status']=='PASS_FROZEN_ADVISOR_AND_ASR_LOOP_MODEL_FREE','actual frozen functional status')
 check(result['checks']==owner['checks'] and result['rows']==owner['rows'] and result['runtime_dispatch_fixtures']==owner['runtime_dispatch_fixtures'],'whole independent reproduced fixture output')
 for r in new['profiles'][384:]:
  p=Profile.from_dict(r['profile']);check(p.digest()==r['profile_digest'] and p.to_dict()==r['profile'],'real schema digest')
 check(len(am['empty_music_case_ids'])==11 and set(am['empty_music_case_ids'])<=set(panel['case_ids']),'all11 source empty cases')
 # Exact live matrix source must retain the full endpoint profile as source key.
 matrix=functions(SIM/'scripts/s6c_policy_matrix_v4.py')
 check('exogenous_key' in matrix,'actual matrix dependency function available')
 import s6c_policy_matrix_v4 as policy
 for r in new['profiles'][384:]:
  check(policy.exogenous_key(r['profile'])==digest(dict(full=r['profile'])),'endpoint exogenous key is full actual profile')
  altered=deepcopy(r['profile']);altered['tracker']['commit_evidence_sec']+=.01
  check(policy.exogenous_key(altered)!=policy.exogenous_key(r['profile']),'tracker change alters endpoint source key')
 receipt=dict(status='PASS_BOUNDED_PRE_EXECUTION_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),checks=checks,owner_functional_fixture_checks=result['checks'],
  scope='Exact two definitions/four profiles, preserved384 registry routes, all224 prepared native cells, all29 APP source identities and whole native/common parity, unchanged coordinator core paths, actual frozen advisor/ASR-loop fixture reproduction. No model construction, runtime launch, audio or model rehash, current resource/quiet-state admission or empirical outcome claim.',
  semantic_limits=['Two missing endpoint-advice modes complete the explicit none/tracking/endpoint/both factorial; full ASR+speaker execution is required because endpoint advice can change words and boundaries.','Advice accepted on a dispatch that also has a native endpoint is not a second reset or incremental advice-only success.','Synthetic fixture reachability does not assert real telemetry activation or benefit.','The nominal recipe_id N01 is insufficient for source reuse: exact full profile, cue, telemetry, audio and gallery dependency remains mandatory.','Prepared metadata admission is separate from later resource/process/native byte admission.'],
  sources=list({b['path']:b for b in sources}.values()),source=file_binding(__file__),readme=file_binding(Path(__file__).with_name('README_TEST_S6C_ENDPOINT_ADMISSION_REVIEW.md')))
 out=REPORT/'independent_review/ENDPOINT_FACTORIAL_ADMISSION_REVIEW_V1.json'
 with out.open('xb') as f:f.write((json.dumps(receipt,indent=2,allow_nan=False)+'\n').encode())
 print(json.dumps(dict(status=receipt['status'],checks=checks,receipt=file_binding(out)),indent=2))

if __name__=='__main__':
 sys.dont_write_bytecode=True
 for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
 main()
