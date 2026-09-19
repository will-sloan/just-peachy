"""Admit four cadence labels through unchanged V3; README_TEST_S6C_CADENCE_SCORER_ADMISSION.md."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import ast,json
import s6c_analysis_v3 as core
import s6c_scoring_extensions as ext

SPECS=[
 ('design/COMMON_ROSTER_DURATION_AMENDMENT_V1.json','b8d25fc00366242bd38bb1e56f16cd30dd1aa78262b8a1eda9e2a2fe4068671d'),
 ('design/FRESH_EVIDENCE_FOLLOWUP_AMENDMENT_V1.json','b899191bccf897689b5ea543b05367f2b62d60fb481e7e2f3255246a7afe2b75'),
 ('design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json','69046b327908410cc7d291c23b7d77205f7cdacd7ca19ac03caf52307ed5d9d5')]

def run():
 checks=[]
 def ok(v,s):
  if not v:raise AssertionError(s)
  checks.append(s)
 before=[core.bind(core.SIM/'scripts'/n) for n in core.CODES]
 old,oldb=core.registered_candidates(SPECS[:2],234);new,bindings=core.registered_candidates(SPECS,238)
 ok(len(new)==238 and new[:234]==old,'exact234 old definitions preserved')
 expected={'C191':('C071',.5),'C192':('C082',.5),'C193':('C071',2.),'C194':('C082',2.)}
 ok({x['candidate_id'] for x in new[234:]}==set(expected),'only four admitted extra labels')
 registryb=core.bind(core.REPORT/'EFFECTIVE_PROFILE_REGISTRY_V6.json','da953b22bb267296f6017f89afa0589b75a54b4e0488c63b598d094d3b56cd7f')
 registry=core.verified(registryb);profiles={(r['candidate_id'],r['asr_tap'],r['identity_tap']):r for r in registry['profiles']}
 definitions={d['candidate_id']:d for d in new}
 for cid,(parent,floor) in expected.items():
  d=definitions[cid];ok(d['parent']==parent and d['settings']['embedding_override']=={'voice_observation_floor_sec':floor},cid+' declaration parent and sole embedding override')
  for tap in ('O0','O1'):
   p=deepcopy(profiles[cid,tap,tap]['profile']);base=profiles[parent,tap,tap]['profile']
   ok(p['embedding']['voice_observation_floor_sec']==floor,cid+tap+' actual floor')
   p['embedding']['voice_observation_floor_sec']=base['embedding']['voice_observation_floor_sec'];p['profile_id']=base['profile_id']
   ok(p==base,cid+tap+' exact parent metric definition')
   ok(profiles[cid,tap,tap]['gallery_condition']=='NONE',cid+tap+' no naming extension required')
 base,baseb=core.registered_candidates();docs=[core.verified(ext.explicit_binding(*s)) for s in SPECS]
 for label,mutate,count in [
  ('count mismatch',lambda d:None,239),
  ('duplicate label',lambda d:d[-1]['candidates'].__setitem__(0,deepcopy(d[0]['candidates'][0])),238),
  ('unknown parent',lambda d:d[-1]['candidates'][0].__setitem__('parent','MISSING'),238),
  ('wrong original design',lambda d:d[-1].__setitem__('parent_design',{}),238),
  ('changed setting without digest',lambda d:d[-1]['candidates'][0]['settings']['embedding_override'].__setitem__('voice_observation_floor_sec',99.),238)]:
  values=deepcopy(docs);mutate(values)
  try:ext.append_candidates(base,baseb[0],values,count)
  except ValueError:checks.append('reject '+label)
  else:raise AssertionError('Admitted '+label)
 fixtures=core.fixtures();ok(fixtures['status']=='PASS','original24 bounded fixtures pass unchanged')
 after=[core.bind(core.SIM/'scripts'/n) for n in core.CODES];ok(before==after,'all V3 scoring dependency bytes unchanged')
 result=dict(status='PASS_UNCHANGED_V3_EXPLICIT_238_ADMISSION',created_utc=datetime.now(timezone.utc).isoformat(),checks=checks,core_fixtures=fixtures,
  registered_labels=238,added_labels=list(expected),registered_routes=len(registry['profiles']),registry=registryb,registry_sources=bindings,
  sources=after+[core.bind(__file__),core.bind(Path(__file__).with_name('README_TEST_S6C_CADENCE_SCORER_ADMISSION.md'))],
  scope='No metric version or code change. Exact existing V3 append-only declaration contract admits all238 labels. Four no-gallery configurations require core scoring only. Earlier234-label scores stay in their exact namespaces; future238-admitted scores include the extra declaration binding in cache identity. No score/model/hardware execution.',
  command_registry_arguments=[item for pair in SPECS for item in ('--registry-extension',*pair)]+['--expected-candidates','238'])
 target=core.REPORT/'independent_review/CADENCE_SCORER_ADMISSION_V1.json'
 core.save(target,result);return core.bind(target)
if __name__=='__main__':print(json.dumps(run(),indent=2))
