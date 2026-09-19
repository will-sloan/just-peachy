"""Explicit immutable additive scorer inputs. README_S6C_SCORING_EXTENSIONS.md."""
from copy import deepcopy
from pathlib import Path
import s6c_analysis_v2 as base

def explicit_binding(path,sha):
 if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('Explicit lowercase SHA256 required')
 p=Path(path)
 return base.bind(p if p.is_absolute() else base.REPORT/p,sha)

def append_candidates(rows,parent_binding,docs,expected_count):
 if type(expected_count) is not int or not 184<=expected_count<=240:raise ValueError('Explicit registered count184..240 required')
 result=deepcopy(rows);seen={r['candidate_id'] for r in rows}
 for doc in docs:
  if doc.get('parent_design')!=parent_binding:raise ValueError('Extension changes original design authority')
  additions=doc.get('candidates')
  if not isinstance(additions,list) or not additions:raise ValueError('Nonempty additive candidates required')
  ids=[r['candidate_id'] for r in additions]
  if len(ids)!=len(set(ids)) or seen.intersection(ids):raise ValueError('Duplicate/replaced registered candidate')
  for r in additions:
   if r.get('parent') is not None and r['parent'] not in seen:set_pending=True
   else:set_pending=False
   if set_pending:raise ValueError('Parent must exist before this additive amendment')
   if 'settings' in r and r.get('settings_sha256')!=base.digest(r['settings']):raise ValueError('Candidate settings digest differs')
  result.extend(deepcopy(additions));seen.update(ids)
 if len(result)!=expected_count:raise ValueError('Explicit candidate count differs from admitted declarations')
 return result

def registry(specs=(),expected_count=184):
 rows,bindings=base.registered_candidates();extra=[];docs=[]
 for path,sha in specs:
  b=explicit_binding(path,sha)
  if b in bindings+extra:raise ValueError('Repeated registry extension input')
  d=base.verified(b)
  if not str(d.get('status','')).startswith('REGISTERED_'):raise ValueError('Registered amendment required')
  if 'parent_registry' in d:base.verified(d['parent_registry'])
  docs.append(d);extra.append(b)
 return append_candidates(rows,bindings[0],docs,expected_count),bindings+extra

def map_key(row):return row['gallery_condition'],row['enrollment_tier'],row.get('case_id')
def append_map(base_binding,original,docs,canonical_cases):
 result=deepcopy(original);seen={map_key(r) for r in original['rows']}
 if len(seen)!=len(original['rows']):raise ValueError('Original map has duplicate assignment keys')
 for doc in docs:
  if doc.get('status')!='COMPLETE' or doc.get('runtime_input') is not False or doc.get('original_scorer_map')!=base_binding:raise ValueError('Completed evaluator-only extension with exact original map required')
  if doc.get('people')!=original['people']:raise ValueError('Extension changes frozen metadata identities')
  if doc.get('Q_occurrences')!=777 or set(doc.get('canonical_case_ids',[]))!=set(canonical_cases) or len(doc.get('canonical_case_ids',[]))!=240:raise ValueError('Extension changes canonical Q/cases')
  rows=doc.get('rows')
  if not isinstance(rows,list) or not rows:raise ValueError('Nonempty additive gallery rows required')
  keys=[map_key(r) for r in rows]
  if len(keys)!=len(set(keys)) or seen.intersection(keys):raise ValueError('Gallery extension duplicates/replaces assignment key')
  for row in rows:
   if row.get('case_id') is not None and row['case_id'] not in canonical_cases:raise ValueError('Noncanonical gallery case')
   profiles=row['profiles'];ids=[p['metadata_identity'] for p in profiles]
   if len(ids)!=len(set(ids)) or set(ids)!=set(row['available_identities']) or len(row['available_identities'])!=len(set(row['available_identities'])):raise ValueError('Available people differ from exact profiles')
   if not set(ids)<=set(row['intended_identities'])<=set(original['people']):raise ValueError('Unexpected intended/available person')
   if set(row['unavailable_identities'])!=set(row['intended_identities'])-set(ids):raise ValueError('Unavailable roster partition differs')
   for field in ('display_name','profile_id'):
    if len({p[field] for p in profiles})!=len(profiles):raise ValueError('Ambiguous native profile/name')
   if row['loaded_count']!=len(profiles):raise ValueError('Declared loaded count differs')
   for p in profiles:
    if p['display_name']!=original['people'][p['metadata_identity']]['display_name']:raise ValueError('Changed pseudonym mapping')
  result['rows'].extend(deepcopy(rows));seen.update(keys)
 return result

def gallery_map(original_binding,original,specs,canonical_cases):
 docs=[];bindings=[]
 for map_path,map_sha,completion_path,completion_sha in specs:
  mb=explicit_binding(map_path,map_sha);cb=explicit_binding(completion_path,completion_sha)
  doc=base.verified(mb);done=base.verified(cb)
  if done.get('status')!='COMPLETE' or mb not in done.get('outputs',[]) or done.get('plan')!=doc.get('plan'):raise ValueError('Extension lacks exact completed material binding')
  plan=base.verified(doc['plan'])
  if original_binding not in plan.get('bindings',[]):raise ValueError('Extension plan does not bind original evaluator map')
  if not done.get('all240_Q_cases_retained') or not plan.get('keep_all_Q_and_empty_cases'):raise ValueError('Extension silently drops Q/empty cases')
  for row in doc['rows']:
   manifest=base.verified(row['manifest'])
   mp={(p['profile_id'],p['display_name']) for p in manifest['profiles']}
   if mp!={(p['profile_id'],p['display_name']) for p in row['profiles']} or len(manifest['profiles'])!=row['loaded_count']:raise ValueError('Scorer/native profile roster differs')
   for p in manifest['profiles']:
    for key in ('metadata','vector'):base.bind(p[key]['path'],p[key]['sha256'])
  docs.append(doc);bindings.append(dict(scorer_map=mb,completion=cb,plan=doc['plan']))
 return append_map(original_binding,original,docs,canonical_cases),bindings

def fixture_checks():
 rows=[dict(candidate_id='B%03d'%i,parent=None) for i in range(184)];b=dict(path='original',sha256='x',bytes=1)
 doc=dict(parent_design=b,candidates=[dict(candidate_id='Cnew',parent='B000',settings={},settings_sha256=base.digest({}))])
 assert len(append_candidates(rows,b,[doc],185))==185
 checks=['explicit additive candidate admitted']
 for bad in [dict(doc,parent_design={}),dict(doc,candidates=doc['candidates']*2),dict(doc,candidates=[dict(doc['candidates'][0],parent='missing')]),dict(doc,candidates=[dict(doc['candidates'][0],candidate_id='B001')]),dict(doc,candidates=[dict(doc['candidates'][0],settings_sha256='bad')])]:
  try:append_candidates(rows,b,[bad],185)
  except ValueError:checks.append('registry tamper rejected')
  else:raise AssertionError('Registry tamper admitted')
 try:append_candidates(rows,b,[doc],186)
 except ValueError:checks.append('declared count mismatch rejected')
 else:raise AssertionError('Count mismatch admitted')
 people={'a':dict(display_name='Research A')};original=dict(people=people,rows=[])
 cases=['case'+str(i) for i in range(240)]
 row=dict(gallery_condition='NEW',enrollment_tier=5,case_id=None,profiles=[dict(metadata_identity='a',profile_id='p',display_name='Research A')],available_identities=['a'],intended_identities=['a'],unavailable_identities=[],loaded_count=1)
 extension=dict(status='COMPLETE',runtime_input=False,original_scorer_map=b,people=people,Q_occurrences=777,canonical_case_ids=cases,rows=[row])
 assert len(append_map(b,original,[extension],cases)['rows'])==1;checks.append('exact additive evaluator map admitted')
 for bad in [dict(extension,original_scorer_map={}),dict(extension,runtime_input=True),dict(extension,canonical_case_ids=cases[:-1]),dict(extension,people={}),dict(extension,rows=[dict(row,unavailable_identities=['a'])]),dict(extension,rows=[dict(row,profiles=[dict(row['profiles'][0],display_name='wrong')])])]:
  try:append_map(b,original,[bad],cases)
  except ValueError:checks.append('map authority/partition tamper rejected')
  else:raise AssertionError('Map tamper admitted')
 try:append_map(b,original,[extension,extension],cases)
 except ValueError:checks.append('duplicate map replacement rejected')
 else:raise AssertionError('Duplicate map admitted')
 return dict(status='PASS',checks=checks)

