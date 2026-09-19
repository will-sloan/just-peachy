"""Source-bound S6C confirmation proposal. See README_S6C_CONFIRMATION_PLAN.md."""
from pathlib import Path
import json,hashlib,argparse
from datetime import datetime,timezone

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
CASES=('S45_01_16','S45_02_10','S45_03_01','S45_03_03','S45_03_19','S45_04_07',
'S45_05_05','S45_06_19','S45_07_13','S45_07_14','S45_08_14','S45_09_11',
'S45_10_10','S45_11_15','S45_12_11','S45_12_15')
REPEATS=('S45_03_03','S45_04_07','S45_06_19','S45_12_11')
GATES=('S45_02_10','S45_03_03','S45_04_07','S45_05_05','S45_06_19','S45_12_11')

def binding(path):
 p=Path(path).resolve();raw=p.read_bytes()
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')
def build():
 bank_path=SIM/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
 if binding(bank_path)['sha256']!='69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18':raise ValueError('Canonical bank changed')
 panel_path=REPORT/'design/REGISTERED_PANEL_V1.json';map_path=REPORT/'enrollment/SCORER_GALLERY_MAP.json'
 bank=read(bank_path);panel=read(panel_path);gallery=read(map_path)
 scenes={s['case_id']:s for s in bank['scenes']};short={s['case_id']:s for s in panel['rows']}
 if len(scenes)!=240 or len(CASES)!=len(set(CASES)) or not set(CASES)<=set(panel['case_ids']):raise ValueError('Invalid case population')
 rosters={r['gallery_condition']:set(r['available_identities']) for r in gallery['rows'] if r['case_id'] is None and r['enrollment_tier']==15 and r['gallery_condition'] in ('FIXED_ROTATION_A','FIXED_ROTATION_B')}
 rows=[]
 for cid in CASES:
  s=scenes[cid];people=set(s['cast'].values());utterances=[x for x in s['segments'] if x['kind']=='utterance']
  rows.append(dict(case_id=cid,family=s['family_id'],family_description=s['family'],duration_s=s['duration_s'],
   receiver=s['receiver_configuration'],corpora=sorted({x['dataset'] for x in utterances}),
   subsecond_turns=short[cid]['subsecond'],one_to_under2_turns=short[cid]['one_to_under2'],source_turns=len(utterances),
   noise_categories=sorted({x.get('category','UNSPECIFIED') for x in s['segments'] if x['kind']!='utterance'}),
   source_empty=not utterances,has_background_talker=any(x.get('role')=='background_talker' for x in utterances),
   evaluator_only_gallery_support={k:dict(available_known=sorted(people&v),not_available_in_gallery=sorted(people-v)) for k,v in rosters.items()},
   repeat_sensitive_case=cid in REPEATS,proposed_family_native_gate=cid in GATES))
 families=sorted({r['family'] for r in rows});rooms=sorted({r['receiver']['room_table'] for r in rows})
 if len(families)!=12 or len(rooms)!=5 or not all(set(REPEATS)<=set(CASES) for _ in [0]):raise ValueError('Required panel balance missing')
 if not all(any(r['evaluator_only_gallery_support'][k]['available_known'] for r in rows) and any(r['evaluator_only_gallery_support'][k]['not_available_in_gallery'] for r in rows) for k in rosters):raise ValueError('Known/stranger coverage missing')
 out=REPORT/'design/confirmation_plan_v1'
 plan=dict(schema='jp_s6c_paced_panel_proposal.v1',status='PROPOSED_NOT_EXECUTED',created_utc=datetime.now(timezone.utc).isoformat(),
  case_ids=list(CASES),count=len(CASES),streams=['O0','O1'],rows=rows,
  repeated_case_ids=list(REPEATS),repeat_scope='Both taps for these four cases; at least eight repeated profile/case/tap cells per profiled path.',
  family_native_gate_case_ids=list(GATES),family_native_gate_scope='Six varied cases, both taps, actual native/shared-policy export checks for each of eight fresh modes before empirical rejection; additional corpus/room coverage comes from full paced panel.',
  population=dict(families=families,rooms=rooms,subsecond_turns=sum(r['subsecond_turns'] for r in rows),one_to_under2_turns=sum(r['one_to_under2_turns'] for r in rows),source_empty_cases=sum(r['source_empty'] for r in rows)),
  selection='Exploratory metadata-balanced planning after earlier research outcomes; no score inputs were read by this builder. Panel is runtime confirmation, not all240 accuracy confirmation or an independent holdout.',
  limitations=['Short support counts are source-duration categories, not a promise all implementation-specific failure modes activate. Inspect actual runtime coverage and add a bounded missing failure case if needed.',
  'Metadata gallery support is evaluator-only; no name roster or correct speaker enters anonymous association. Different fixed rosters are separate sessions.','Concatenated prior captures cannot establish continuous hidden XVF state.'],
  sources=[binding(bank_path),binding(panel_path),binding(map_path),binding(__file__),binding(Path(__file__).with_name('README_S6C_CONFIRMATION_PLAN.md'))])
 save(out/'PACED_PANEL_PROPOSAL_V1.json',plan)
 return binding(out/'PACED_PANEL_PROPOSAL_V1.json')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.parse_args()
 print(json.dumps(build(),indent=2))

