"""Exact cross-route post-closure analysis; README_S6C_PACED_CROSS_ANALYSIS_V1.md."""
from pathlib import Path
from copy import deepcopy
import argparse,ast,hashlib,importlib,json,types
import s6c_paced_analysis_v1 as core

HERE=Path(__file__).resolve().parent
CORE_SHA='936b5973091d677b4eb24847e7e3e2d84df614340d3984f10ff31283096b880a'
INVENTORY_SHA='9109a38c9f62ad6aca11a4e60ef57eb9e8712bb43dde10b08d485d03a068921f'
COORDINATOR_SHA='0989758d797b5308573d5546114cb170b2b0b4e7e50a0fc507698c571f7992d3'
REVIEW_SHA='b3239c8f7dbfca31d896e5002d2ec6589a833edfacf362fa42a05d19e57feb4d'
SCHEMA='jp_s6c_paced_cross_route_analysis.v1'
ROUTES={'C085':('O0','O1'),'C086':('O1','O0')}
PINS={'s6c_paced_analysis_v1.py':CORE_SHA,'s6c_execution_inventory_v6.py':INVENTORY_SHA,'s6c_paced_cross_routes_v1.py':COORDINATOR_SHA}
for name,sha in PINS.items():
 if core.file_binding(HERE/name)['sha256']!=sha:raise ValueError('Held cross analysis dependency differs: '+name)
if Path(core.__file__).resolve()!=HERE/'s6c_paced_analysis_v1.py':raise ValueError('Canonical converter import differs')
inventory=importlib.import_module('s6c_execution_inventory_v6')
if Path(inventory.__file__).resolve()!=HERE/'s6c_execution_inventory_v6.py':raise ValueError('Inventory V6 import origin differs')

def require(value,message):
 if not value:raise ValueError(message)

def validate_scope(plan):
 require(plan['schema']==inventory.CROSS and plan['candidates']==['C085','C086'] and plan['requested']==len(plan['jobs'])==40,'Only exact reviewed40 cross cells admitted')
 require(plan['panel_mode']=='cross16_plus4','Cross16+4 selection required')
 for j in plan['jobs']:
  require((j['asr_tap'],j['identity_tap'])==ROUTES[j['candidate_id']],'Cross route must preserve two distinct tap roles')
  require(j['gallery'] is None and j['profile_row']['profile']['identity']['mode']=='none','Registered cross profiles have no gallery')
 return plan

def admit_cross_plan(reader,b):
 # A strict wrapper on both prepare and run; a tampered analysis plan cannot
 # use V6 delegation to admit canonical/sentinel/long schemas under this label.
 plan,pb,spec=inventory.admit_plan(reader,b)
 validate_scope(plan)
 return plan,pb,spec

def inventory_module():
 return types.SimpleNamespace(base=inventory.base,CANONICAL=inventory.CROSS,
  admit_plan=admit_cross_plan,admit_complete_cell=inventory.admit_complete_cell,
  admit_paced_index=inventory.admit_paced_index,invocation_rows=inventory.invocation_rows)

def source_bindings():
 review=core.file_binding(core.REPORT/'independent_review/INVENTORY_V6_DESIGN_REVIEW_V1.json')
 require(review['sha256']==REVIEW_SHA,'Independent inventory review changed')
 rows=core.source_bindings()+inventory.source_bindings()+[
  core.file_binding(__file__),core.file_binding(HERE/'README_S6C_PACED_CROSS_ANALYSIS_V1.md'),
  core.file_binding(HERE/'README_S6C_PACED_CROSS_ROUTES_V1.md'),review]
 result={}
 for b in rows:
  key=str(Path(b['path']).resolve()).casefold()
  require(key not in result or result[key]==b,'Conflicting exact source binding')
  result[key]=b
 return list(result.values())

def make_adapter():
 raw=Path(core.__file__).read_bytes();require(hashlib.sha256(raw).hexdigest()==CORE_SHA,'Core source changed before AST read')
 source=ast.parse(raw);names={'safe_output','prepare','run'}
 nodes=[deepcopy(n) for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names]
 require(len(nodes)==3,'Exact three canonical orchestration functions required')
 changes=[];before={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in nodes}
 for n in nodes:
  for x in ast.walk(n):
   if isinstance(x,ast.Constant) and x.value=='paced_analysis':x.value='paced_cross_analysis';changes.append(n.name)
 require(sorted(changes)==['run','safe_output'],'Only the two output namespace literals may change')
 ns={**vars(core),'SCHEMA':SCHEMA,'inventory_module':inventory_module,'source_bindings':source_bindings}
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(__file__),'exec'),ns)
 return types.SimpleNamespace(**{n:ns[n] for n in names}),dict(original_function_ast=before,adapted_function_ast={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in nodes},changed_literals=['paced_analysis -> paced_cross_analysis in safe_output and run'])
adapter,ADAPTATION=make_adapter()

def checks():
 inherited=core.checks();require(len(inherited['checks'])==34,'Held canonical pure check count differs')
 checked=[]
 def ok(name,condition):require(condition,name);checked.append(name)
 def bad(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):checked.append(name);return
  raise AssertionError('Expected rejection: '+name)
 ok('separate output namespace',adapter.safe_output('unexecuted_cross_fixture')==core.REPORT/'paced_cross_analysis/unexecuted_cross_fixture')
 ok('original canonical namespace unchanged',core.safe_output('unexecuted_canonical_fixture')==core.REPORT/'paced_analysis/unexecuted_canonical_fixture')
 ok('canonical schema and V4 inventory unchanged',core.SCHEMA=='jp_s6c_paced_observation_analysis.v1' and core.inventory_module().CANONICAL=='s6c-canonical-paired-paced.v1')
 ok('strict cross schema',inventory_module().CANONICAL=='s6c-cross-route-paired-paced.v1')
 for name in ('convert_closed_cell','native_prediction','paced_name_observations','name_context','closed_coordinators','load_frozen_modules','trajectory_observations','active_context_observations'):
  ok('exact held transformation '+name,adapter.run.__globals__[name] is getattr(core,name))
 ok('private metadata hook not original globals',adapter.run.__globals__['inventory_module'] is inventory_module and core.run.__globals__['inventory_module'] is core.inventory_module)
 plan=dict(schema=inventory.CROSS,candidates=['C085','C086'],requested=40,panel_mode='cross16_plus4',jobs=[])
 for rep,cases in ((1,range(16)),(2,range(4))):
  for case in cases:
   for cid in ('C085','C086'):
    a,i=ROUTES[cid];plan['jobs'].append(dict(candidate_id=cid,asr_tap=a,identity_tap=i,repetition=rep,case_id=str(case),gallery=None,profile_row=dict(profile=dict(identity=dict(mode='none')))))
 ok('exact synthetic40 asymmetric cells',validate_scope(plan) is plan)
 for mode in ('schema','candidate_order','identity_tap','extra_repeat','gallery'):
  value=deepcopy(plan)
  if mode=='schema':value['schema']='s6c-canonical-paired-paced.v1'
  if mode=='candidate_order':value['candidates'].reverse()
  if mode=='identity_tap':value['jobs'][0]['identity_tap']='O0'
  if mode=='extra_repeat':value['jobs'].append(deepcopy(value['jobs'][0]))
  if mode=='gallery':value['jobs'][0]['gallery']={}
  bad('reject scope '+mode,lambda value=value:validate_scope(value))
 # Exercise unchanged native_prediction metadata projection using injected pure
 # schema stubs. No frozen policy or native models are invoked.
 route_proofs=[]
 class Profile:
  @staticmethod
  def from_dict(p):return types.SimpleNamespace(value=deepcopy(p))
 class Reader:
  def __init__(self,source):self.source=source
  def json(self,b):return self.source
 def forbidden(*args,**kwargs):raise AssertionError('Unexpected provider/gallery use')
 for cid,(asr,identity) in ROUTES.items():
  source=dict(duration_sec=2.,audio=dict(O0=dict(path='asr-or-id0.wav'),O1=dict(path='asr-or-id1.wav')),telemetry=None)
  row=dict(profile=dict(input=dict(asr_tap=asr,identity_tap=identity)),cue_condition='CUES_OFF',gallery_condition='NONE',enrollment_tier=None,recipe_id='N01')
  job=dict(candidate_id=cid,asr_tap=asr,identity_tap=identity,case_id='synthetic',repetition=1,profile_row=row,gallery=None,source=dict(path='synthetic-source'))
  state=dict(decisions=[],transcript_events=[],identity_events=[],snapshot=dict(scheduler=dict(utterances=[])))
  calls=[]
  def policy(p,provider,evidence,vectors,gallery):
   calls.append((deepcopy(p.value),provider,gallery));return deepcopy(state)
  mods={'s6c_execution':types.SimpleNamespace(extract=lambda events:([1.],[],[],[],[],{})),
        's6c_replay':types.SimpleNamespace(run_policy=policy),
        's6c_native_replay_v3':types.SimpleNamespace(differences=lambda actual,expected,*a,**k:[] if actual==expected else ['difference'])}
  summary=dict(state='COMPLETED',telemetry=dict(scheduler=dict(closed=True,pending_events=0,utterances=[]),audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0))
  value,parity=core.native_prediction([],summary,job,dict(path='synthetic-native'),dict(execution_digest='synthetic',epoch='epoch4'),mods,(Profile,forbidden,forbidden),Reader(source),{})
  ok(cid+' unchanged metadata projection retains asymmetric roles',value['stream']==asr and value['identity_tap']==identity and value['identity']['profile']==row['profile'] and calls==[(row['profile'],None,None)] and parity['status']=='PASS')
  # Exercise the original name-observation support lookup without the name API.
  supports={('synthetic','O0'):dict(support=dict(path='support0')),('synthetic','O1'):dict(support=dict(path='support1'))}
  expected=supports['synthetic',identity]['support'];selected=[]
  class SupportReader:
   def json(self,b):selected.append(b);return dict(support=dict(identity_tap=identity))
  def validate_support(scene,support):require(support==dict(identity_tap=identity),'Support mapping changed')
  def analyze(events,v,support,gallery,q,admission,finalization):
   require(admission['identity_tap']==identity and admission['asr_tap']==asr,'Name admission routes differ')
   return dict(synthetic_support_tap=support['identity_tap'])
  module=types.SimpleNamespace(names=types.SimpleNamespace(validate_support=validate_support,gallery_for=lambda v,m:dict(manifest=None)),analyze=analyze)
  context=dict(inputrows=supports,scenes={'synthetic':{}},module=module,scoremap={},q={},bindings={})
  chain=dict(job=job,cell=dict(source_kind='CANONICAL_SINGLE_SCENE_PAIR',source_offset_samples=0,inserted_gap_samples=0,status='COMPLETE'),native=dict(status='COMPLETE'),cell_binding={},native_binding={},complete_binding={},artifacts=[dict(path='events.jsonl'),dict(path='session_finalization_v3.json')])
  value['final_transcripts_latest']=[]
  result=core.paced_name_observations([],value,chain,{},SupportReader(),context)
  ok(cid+' identity support chosen once without ASR substitution',selected==[expected] and result['synthetic_support_tap']==identity)
  route_proofs.append(dict(candidate_id=cid,asr_tap=asr,identity_tap=identity,support_binding=expected,scope='Pure injected schema projection, not a native/policy/name-scoring result'))
 return dict(status='PASS_SOURCE_ONLY_CROSS_ANALYSIS',checks=checked,check_count=len(checked),inherited_checks=inherited,
  source_bindings=source_bindings(),adaptation=ADAPTATION,synthetic_route_proofs=route_proofs,
  new_neural_calls=0,actual_policy_replays=0,actual_native_cells=0,actual_manifests_prepared=0,actual_payloads_read=0,
  scope='Exact canonical transformations unchanged; strict V6 cross schema and fixed C085/C086 asymmetric routes. Source and injected pure metadata fixtures only. Native integration and actual score results remain pending.')

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);sub=p.add_subparsers(dest='action',required=True)
 c=sub.add_parser('checks');c.add_argument('--output',type=Path,required=True)
 a=sub.add_parser('prepare');a.add_argument('--manifest',required=True,type=Path);a.add_argument('--index',required=True,type=Path);a.add_argument('--namespace',required=True)
 a=sub.add_parser('run');a.add_argument('--plan',required=True,type=Path)
 args=p.parse_args()
 if args.action=='checks':
  require(not args.output.exists(),'Preserve prior checks');return core.save_json(args.output,checks())
 return adapter.prepare(args) if args.action=='prepare' else adapter.run(args)
if __name__=='__main__':print(json.dumps(main(),indent=2,allow_nan=False))

