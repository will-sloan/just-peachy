"""Admit final endpoint labels through unchanged V3; README_TEST_S6C_ENDPOINT_SCORER_ADMISSION.md."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import ast,json
import s6c_analysis_v3 as core
import s6c_scoring_extensions as ext

SPECS=[
 ('design/COMMON_ROSTER_DURATION_AMENDMENT_V1.json','b8d25fc00366242bd38bb1e56f16cd30dd1aa78262b8a1eda9e2a2fe4068671d'),
 ('design/FRESH_EVIDENCE_FOLLOWUP_AMENDMENT_V1.json','b899191bccf897689b5ea543b05367f2b62d60fb481e7e2f3255246a7afe2b75'),
 ('design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json','69046b327908410cc7d291c23b7d77205f7cdacd7ca19ac03caf52307ed5d9d5'),
 ('design/ENDPOINT_ADVICE_FACTORIAL_V1.json','f44ecb1960585420956ab34aab2dfa43126e48742372cf9e801503e0de30da91')]

def run():
 checks=[]
 def ok(v,s):
  if not v:raise AssertionError(s)
  checks.append(s)
 before=[core.bind(core.SIM/'scripts'/n) for n in core.CODES]
 old,oldb=core.registered_candidates(SPECS[:3],238);new,bindings=core.registered_candidates(SPECS,240)
 ok(len(new)==240 and new[:238]==old,'exact238 old definitions preserved')
 expected={'C195':('C065','endpoint_only'),'C196':('C079','both')}
 ok({x['candidate_id'] for x in new[238:]}==set(expected),'only two admitted extra labels')
 registryb=core.bind(core.REPORT/'EFFECTIVE_PROFILE_REGISTRY_V7.json','924f8b35950ba053c636687766ff579b6310b89c2a3cab0befbdf267871d0734')
 registry=core.verified(registryb);profiles={(r['candidate_id'],r['asr_tap'],r['identity_tap']):r for r in registry['profiles']}
 definitions={d['candidate_id']:d for d in new}
 for cid,(parent,mode) in expected.items():
  d=definitions[cid];ok(d['parent']==parent and d['settings']['xvf_override']=={'mode':mode},cid+' declaration parent and sole endpoint-routing override')
  for tap in ('O0','O1'):
   p=deepcopy(profiles[cid,tap,tap]['profile']);base=profiles[parent,tap,tap]['profile']
   ok(p['xvf']['mode']==mode,cid+tap+' actual endpoint route')
   p['xvf']['mode']=base['xvf']['mode'];p['profile_id']=base['profile_id']
   ok(p==base,cid+tap+' exact parent metric definition')
   ok(profiles[cid,tap,tap]['gallery_condition']=='NONE',cid+tap+' no naming extension required')
 base,baseb=core.registered_candidates();docs=[core.verified(ext.explicit_binding(*s)) for s in SPECS]
 for label,mutate,count in [
  ('count mismatch',lambda d:None,239),
  ('duplicate label',lambda d:d[-1]['candidates'].__setitem__(0,deepcopy(d[0]['candidates'][0])),240),
  ('unknown parent',lambda d:d[-1]['candidates'][0].__setitem__('parent','MISSING'),240),
  ('wrong original design',lambda d:d[-1].__setitem__('parent_design',{}),240),
  ('changed setting without digest',lambda d:d[-1]['candidates'][0]['settings']['xvf_override'].__setitem__('mode','none'),240)]:
  values=deepcopy(docs);mutate(values)
  try:ext.append_candidates(base,baseb[0],values,count)
  except ValueError:checks.append('reject '+label)
  else:raise AssertionError('Admitted '+label)
 fixtures=core.fixtures();ok(fixtures['status']=='PASS','original24 bounded fixtures pass unchanged')
 after=[core.bind(core.SIM/'scripts'/n) for n in core.CODES];ok(before==after,'all V3 scoring dependency bytes unchanged')
 result=dict(status='PASS_UNCHANGED_V3_EXPLICIT_240_ADMISSION',created_utc=datetime.now(timezone.utc).isoformat(),checks=checks,core_fixtures=fixtures,
  registered_labels=240,added_labels=list(expected),registered_routes=len(registry['profiles']),registry=registryb,registry_sources=bindings,
  sources=after+[core.bind(__file__),core.bind(Path(__file__).with_name('README_TEST_S6C_ENDPOINT_SCORER_ADMISSION.md'))],
  scope='No metric version or code change. Exact existing V3 append-only declaration contract admits all240 labels. Two no-gallery configurations require core scoring only. Earlier234/238-label scores stay in their exact namespaces; future240-admitted scores include the extra declaration binding in cache identity. No score/model/hardware execution.',
  command_registry_arguments=[item for pair in SPECS for item in ('--registry-extension',*pair)]+['--expected-candidates','240'])
 target=core.REPORT/'independent_review/ENDPOINT_SCORER_ADMISSION_V1.json'
 core.save(target,result);return core.bind(target)
if __name__=='__main__':print(json.dumps(run(),indent=2))
