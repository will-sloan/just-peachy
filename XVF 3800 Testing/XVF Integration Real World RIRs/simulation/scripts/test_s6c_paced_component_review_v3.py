"""Independent paced V3 source review; README_TEST_S6C_PACED_COMPONENT_REVIEW_V3.md."""
from copy import deepcopy
from datetime import datetime,timezone
import ast,hashlib,json,math
from pathlib import Path
import sys
import s6c_paced_epoch4 as paced

SIM=Path(__file__).resolve().parents[1];REPORT=SIM/'reports/S6C/20260910T123540Z'
RECEIPT=REPORT/'paced_candidates/SOURCE_CHECKS_V3.json'
SHA='1116d9899b2172681d1625158d3d82d64399e1f132225b7a600b0d2b51e85c6c'

def bind(path):
 p=Path(path);raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def run():
 raw=RECEIPT.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;receipt=json.loads(raw);checks=[]
 def ok(v,label):
  if not v:raise AssertionError(label)
  checks.append(label)
 def reject(call,label):
  try:call()
  except (ValueError,KeyError,TypeError):checks.append(label)
  else:raise AssertionError('Unexpectedly admitted '+label)
 for b in receipt['sources']:
  a=bind(b['path']);ok(all(a[k]==b[k] for k in ('sha256','bytes')),'held source '+Path(b['path']).name)
 for row in receipt['preserved_previous_sources']:
  a=bind(row['snapshot']['path']);ok(all(a[k]==row['original'][k]==row['snapshot'][k] for k in ('sha256','bytes')),'exact preserved V2 '+Path(a['path']).name)
 previous=next(r['snapshot']['path'] for r in receipt['preserved_previous_sources'] if Path(r['snapshot']['path']).name=='s6c_paced_epoch4.py')
 old=ast.parse(Path(previous).read_bytes());new=ast.parse(Path(paced.__file__).read_bytes())
 def fn(tree,name):return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
 for name in ['load_native','source_bindings','namespace_roots','panel','validate_source_rows','verify_pcm','source_record','candidate_routes','grid','quiet','worker','terminate_owned','phase_observations','progress']:
  ok(fn(old,name)==fn(new,name),'unchanged V2 function '+name)
 pure=paced.checks();ok(pure==receipt['checks'] and pure['checks']==72,'all72 actual pure guards reproduce')
 panelraw=Path(receipt['panel']['path']).read_bytes();ok(hashlib.sha256(panelraw).hexdigest()==receipt['panel']['sha256'],'exact proposal bytes')
 panel=json.loads(panelraw);gate=paced.selected_panel(panel,'gate6_diagnostic',['C071','C082']);jobs=paced.grid(['C071','C082'],gate)
 ok(len(jobs)==len(set(jobs))==24,'24 unique original-policy gate cells')
 ok({r[1] for r in jobs}==set(panel['family_native_gate_case_ids']) and {r[3] for r in jobs}=={1},'exact six proposal cases no repeats')
 ok({(r[0],r[2]) for r in jobs}=={(p,t) for p in ('C071','C082') for t in ('O0','O1')},'both original profiles and taps')
 full=paced.selected_panel(panel,'full16_plus4',['C071','C082'])
 ok(len(paced.grid(['C071','C082'],full))==80 and full['case_ids']==panel['case_ids'] and full['repeated_case_ids']==panel['repeated_case_ids'],'default full16+4 unchanged')
 bad=deepcopy(panel);bad['family_native_gate_case_ids'][0]='foreign';reject(lambda:paced.selected_panel(bad,'gate6_diagnostic',['C071','C082']),'gate cannot substitute case')
 for candidates in (['C191','C192'],['C082','C071'],['C071','C082','C065']):reject(lambda:paced.selected_panel(panel,'gate6_diagnostic',candidates),'gate cannot substitute profile/order/count')
 for field,bad in [('pid',True),('pid',0),('creation_time',True),('creation_time',float('nan')),('creation_time',float('inf'))]:
  owner=dict(pid=12345,creation_time=123.);owner[field]=bad;reject(lambda:paced.valid_owner(owner),'reject nonfinite/boolean owner '+field)
 for state in (True,None,0,1,'False'):
  called=[];release=lambda *args:called.append(1)
  r=paced.release_after_closure(None,None,None,[dict(alive=state)],release)
  ok(r['status']=='RETAINED_OWNED_CLOSURE_UNVERIFIED' and not called,'unverified owned child retains lease '+repr(state))
 rows=paced.owned_states({12345:10.},lambda *_:0);ok(rows[0]['alive'] is None,'nonboolean process observation remains unknown')
 verified=receipt['verified_canonical_sources'];bycase={r['case_id']:r for r in verified}
 ok(len(bycase)==len(verified)==16 and set(bycase)==set(panel['case_ids']),'receipt covers exact16 canonical pairs')
 ok(all(r['source_offset_samples']==r['inserted_gap_samples']==0 and r['adapter_gain']==1 and r['no_new_gain'] is True for r in verified),'no trim/offset/gap/gain in source metadata')
 ok(sum(bycase[j[1]]['duration_samples'] for j in jobs)==17163048,'gate actual source samples17163048')
 ok(sum(bycase[j[1]]['duration_samples'] for j in jobs)/16000==1072.6905,'gate1072.6905 source seconds')
 for b in receipt['sources']:
  ok(bind(b['path'])==b,'source unchanged after fixtures '+Path(b['path']).name)
 ok(RECEIPT.read_bytes()==raw,'source admission receipt unchanged')
 result=dict(status='PASS_BOUNDED_PACED_V3_COMPONENT_REVIEW',created_utc=datetime.now(timezone.utc).isoformat(),checks=checks,
  actual_pure_checks=pure,source_admission=bind(RECEIPT),source_bindings=receipt['sources'],gate_cells=24,gate_source_sec=1072.6905,
  scope='Source/metadata/temporary synthetic fixture review only. No preparation/native/model/hardware call and no second canonical PCM/asset scan. The exact source receipt carries those prior source validations.',
  findings_resolved=['Completed reuse re-admits current job/source/profile/epoch, exact original launch/admission/outcome/native/artifact/finalization chain, sampled owner closure and deterministic measured fields.',
   'Original positive finite coordinator wall is retained from the bound completion rather than reconstructed from nested clocks.',
   'Any live, unavailable or nonboolean owned-state observation retains the quiet lease after cleanup; outer PID exit remains independently checked.',
   'New gate6 mode admits only original C071/C082 on exact six proposal cases and both taps; full16+4 is unchanged.'],
  limitations=['A prepared gate manifest still needs its own exact source/job/owner admission and subsequent quiet authorization; this review starts no cells.',
   'OS/process metadata sampling and full scans can create gaps; observed values are not continuous maxima.',
   'The original native body retains generic long-composition prose. Canonical single-scene source/CELL_RESULT records define the actual input domain; no new long-session evidence is implied.',
   'Fresh process/model per cell measures cold per-cell execution, distinct from the continuous resident long run. Model startup/native/drain/outer-wall scopes remain nested and separate.'],
  reviewer=bind(__file__),readme=bind(Path(__file__).with_name('README_TEST_S6C_PACED_COMPONENT_REVIEW_V3.md')))
 out=REPORT/'independent_review/PACED_COMPONENT_REVIEW_V3.json'
 with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(dict(status=result['status'],checks=len(checks),receipt=bind(out))))

if __name__=='__main__':run()
