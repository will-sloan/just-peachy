"""Independent model-free admission review; see README_TEST_S6C_CADENCE_NEIGHBORHOOD_REVIEW.md."""
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
 'EFFECTIVE_PROFILE_REGISTRY_V5.json':'15e7b1e2b4ca93d0f8c1cf3c47fa46456396e1263145ae1b3c453e8a4a35b5ab',
 'EFFECTIVE_PROFILE_REGISTRY_V6.json':'da953b22bb267296f6017f89afa0589b75a54b4e0488c63b598d094d3b56cd7f',
 'design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json':'69046b327908410cc7d291c23b7d77205f7cdacd7ca19ac03caf52307ed5d9d5',
 'cadence_neighborhood_v1/DUE_LEDGER_CHECKS.json':'1e6dfd08e782b878f1b2347c61b70d57e524b6866a17ecdf6661ecb0799ab6f3',
 'EPOCH5_EXECUTION_MANIFEST.json':'676ead81afe85b5557494bd851e67f34799106a45976e8f7fa6e2e5900989cbc',
 'jobs/epoch5/cadence_floor_v1.json':'a2f507e1de71aa619a7c7a7511905df7cd0d14ba86af71313638a14e37f4c09a',
 'orchestration/epoch5_cadence_floor_scan_v1/ADMISSION.json':'a72e03110ef67038e05c9b16ea8e3eb4df7ad9d32d2178da68b077e37ff53c7f',
 'orchestration_review/ORCHESTRATOR_SCAN_FIXTURES_v4_epoch5_ready.json':'2948c5999ba6f597abbef26749395530fc9f7d195bc430a5fa80f5a5e6a1ac79'}
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
 old=docs['EFFECTIVE_PROFILE_REGISTRY_V5.json'];new=docs['EFFECTIVE_PROFILE_REGISTRY_V6.json'];am=docs['design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json'];ep=docs['EPOCH5_EXECUTION_MANIFEST.json'];jobs=docs['jobs/epoch5/cadence_floor_v1.json'];ad=docs['orchestration/epoch5_cadence_floor_scan_v1/ADMISSION.json']
 check(new['profiles'][:376]==old['profiles'],'original376 rows unchanged')
 check(len(new['profiles'])==384 and new['candidate_count']==194 and am['total_registered_configurations']==238,'breadth')
 expected={'C191':('C071',.5),'C192':('C082',.5),'C193':('C071',2.),'C194':('C082',2.)}
 lookup={(r['candidate_id'],r['asr_tap'],r['identity_tap']):r for r in new['profiles']}
 check(len(lookup)==384,'unique routes')
 definitions={c['candidate_id']:c for c in am['candidates']}
 for cid,(parent,floor) in expected.items():
  check(definitions[cid]['parent']==parent and definitions[cid]['settings']['embedding_override']=={'voice_observation_floor_sec':floor},'definition exact change')
  for tap in ('O0','O1'):
   row=lookup[cid,tap,tap];prior=lookup[parent,tap,tap];p=deepcopy(row['profile'])
   check(p['embedding']['voice_observation_floor_sec']==floor,'actual new floor')
   p['profile_id']=prior['profile']['profile_id'];p['embedding']['voice_observation_floor_sec']=1.
   check(p==prior['profile'],'only floor and ID differ')
   check(row['cue_condition']==prior['cue_condition'] and row['neural_dependency']=='FULL_PROFILE_AND_CUES' and row['gallery_condition']=='NONE','native exact dependency')
   check(verify(row['profile_binding'])==row['profile'],'profile bytes')
 check(ep['profiles']==new['profiles'] and verify(ep['effective_profile_registry'])==new,'epoch exact registry')
 check(ep['execution_digest']==digest({k:ep[k] for k in ('execution_files','assets','versions','state_policy')}),'epoch digest')
 for older in ('EPOCH2_EXECUTION_MANIFEST.json','EPOCH4_EXECUTION_MANIFEST.json'):
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
 check(len(want)==448 and len(panel['case_ids'])==56,'registered grid')
 check(jobs['requested']==448 and len(jobs['jobs'])==448 and set(jobs['case_ids'])==set(panel['case_ids']),'job count and source scene population')
 check({(j['candidate_id'],j['case_id'],j['asr_tap'],j['identity_tap']) for j in jobs['jobs']}==want,'actual grid exact')
 check(len({j['job_key'] for j in jobs['jobs']})==448,'unique exact native keys')
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
  target=Path('G:/Just_Peachy_S6C/20260910T123540Z/epoch5/cadence_floor')/j['candidate_id']/j['case_id']/(j['asr_tap']+'_'+j['identity_tap'])/'v1'
  check(Path(j['folder']).resolve()==target.resolve(),'exact new output namespace')
  check(j['recipe_id']=='N07','actual native recipe')
 check(verify(ad['jobs'])==jobs and verify(ad['native_epoch'])==ep and ad['workers']==4,'prepared coordinator binding')
 for b in ad['sources']:check(file_binding(b['path'])==b,'coordinator source binding')
 f3=functions(SIM/'scripts/s6c_orchestrator_scan_v3.py');f4=functions(SIM/'scripts/s6c_orchestrator_scan_v4.py')
 stable=('compatible_native','invocation_dirs','closed_identity','prior_invocations','validate_manifest','validate_name','prepare','run')
 for name in stable:check(f3[name]==f4[name],'unchanged coordinator '+name)
 # Reproduce owner's actual pure admission fixture against checked epoch4 APP.
 sys.path.insert(0,str(SIM/'scripts'));import s6c_cadence_neighborhood_v1 as builder
 Profile,Admission,_,_=builder.api();result=builder.due_checks(old,Profile,Admission)
 check(result['checks']==27 and result['status']=='PASS_ACTUAL_ADMISSION_POLICY_MODEL_FREE','real due-ledger fixtures')
 check(json.loads(json.dumps(result['rows']))==docs['cadence_neighborhood_v1/DUE_LEDGER_CHECKS.json']['rows'],'actual due boundary JSON output reproducibility')
 for r in new['profiles'][376:]:
  p=Profile.from_dict(r['profile']);check(p.digest()==r['profile_digest'] and p.to_dict()==r['profile'],'real schema digest')
 receipt=dict(status='PASS_BOUNDED_PRE_EXECUTION_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),checks=checks,owner_due_fixture_checks=27,
  scope='Exact four definitions/eight profiles, preserved376 registry routes, all448 prepared native cells, all29 APP source identities and whole native/common parity, unchanged coordinator core paths, actual model-free due-ledger reproduction. No model construction, runtime launch, audio or model rehash, current resource/quiet-state admission or empirical outcome claim.',
  semantic_limits=['Global accepted waveform acknowledges all due ledger entries; no debtor voice is selected or proven.','Original1s parents and every56-case/two-tap cell remain; floor effects require actual native contexts.','Prepared metadata admission is separate from the later live resource/process/native byte checks.'],
  sources=list({b['path']:b for b in sources}.values()),source=file_binding(__file__),readme=file_binding(Path(__file__).with_name('README_TEST_S6C_CADENCE_NEIGHBORHOOD_REVIEW.md')))
 out=REPORT/'independent_review/CADENCE_NEIGHBORHOOD_ADMISSION_REVIEW_V1.json'
 with out.open('xb') as f:f.write((json.dumps(receipt,indent=2,allow_nan=False)+'\n').encode())
 print(json.dumps(dict(status=receipt['status'],checks=checks,receipt=file_binding(out)),indent=2))

if __name__=='__main__':
 sys.dont_write_bytecode=True
 for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
 main()
