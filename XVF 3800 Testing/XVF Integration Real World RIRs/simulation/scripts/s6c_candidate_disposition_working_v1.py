"""Working proposal only; see README_S6C_CANDIDATE_DISPOSITION_WORKING_V1.md."""
from __future__ import annotations
import argparse,csv,hashlib,io,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
REGISTRY_SHA='924f8b35950ba053c636687766ff579b6310b89c2a3cab0befbdf267871d0734'
ORIGINAL_SHA='5b7df31673cc1a5b5beb32fa7703dcdaa8ac46eefbe5446a0d018547bcdbfe76'
SUPPORT_SHA='e33667f01216763ddc05decf9b99eaef28462ebccbe341c66f103f59613d6c2c'
NATIVE_BATCHES={
 'recipes_scan_v2':('ROOT_COMPLETION_REVIEW.json','cfe8b178fc96ca6f6d33e4c3ae264b3a3a3dae74dbcc45c1d96bb366af7d66cf',1680),
 'full_N01_scan_v1':('ROOT_COMPLETION_REVIEW.json','2878dcec4e29ef427802f0751658f5733d82e7263b6a4defbfdf785b4042ddd2',480),
 'epoch4_gate6_scan_v2':('ROOT_COMPLETION_REVIEW.json','8e8f67f5129efc2c5a1b4c2d8e6c878f59fc93b3987fecab5abb034b6134218b',192),
 'enrollment_scan_v1':('ROOT_COMPLETION_REVIEW.json','0c8dea4a4e5dfe0e8d02a5420d1a21595f7f1d71b67aa5042e8857f65b019e65',336),
 'common_duration_native_scan_v1':('ROOT_COMPLETION_REVIEW.json','92ee6183ff7d9708cc04dbd15fa476460ea5a75d947c1ceb392e4301d473ded5',72),
 'split_cross_only_scan_v2':('ROOT_COMPLETION_REVIEW.json','1845c22d19a5c6e4d287348f44a6a0bce8eca510c7cb1ead13de9e7d6852d074',112),
 'epoch6_endpoint_advice_scan_v1':('EXECUTOR_COMPLETION_REVIEW.json','f7bf01346d40cfd8110303cbf3f13129eaea032d25ae3679a20d2138d2005f18',224),
 'epoch5_cadence_floor_scan_v1':('EXECUTOR_COMPLETION_REVIEW.json','f7bdc95e66e51ded48364306d06cc187db21450c2c023fba39599ffc5e6f8339',448),
 'full_N03_scan_v1':('EXECUTOR_COMPLETION_REVIEW.json','d26e35453ed679782496a799aead370d04ed5d403858650b6f1cc5d13223036e',480),
}
EVIDENCE={
 'foundation':'FOUNDATION_AUDIT_INDEPENDENT_COMPONENT_REVIEW_V1.json',
 'n00':'independent_review/n00_screen_v2/INTERPRETATION.md',
 'family_native':'family_gate6_native_results_v1/FAMILY_NATIVE_REVIEW_RECEIPT.json',
 'family_review':'independent_review/FAMILY_RESULTS_COMPONENT_REVIEW_V1.json',
 'anonymous_full':'full_n01_anonymous_core_v3/INTERPRETATION_V1.md',
 'anonymous_review':'full_anonymous_component_review_v1/RESULT.json',
 'followup_full':'full_n01_followups_comparisons_v1/INTERPRETATION_V1.md',
 'followup_panel':'fresh_followup_comparisons_v1/INTERPRETATION.md',
 'asr_panel':'asr_recipe_comparisons_v1/INTERPRETATION.md',
 'component_panel':'n08_n09_n10_panel_core_v3/INTERPRETATION.md',
 'n03_full':'full_n03_results_v1/INTERPRETATION_V1.md',
 'n03_review':'independent_review/N03_INTERPRETATION_COMPONENT_REVIEW_V1.json',
 'cadence':'cadence_audit_v1/INTERPRETATION.md',
 'cadence_floor':'cadence_floor_audit_v3/INTERPRETATION_V1.md',
 'cadence_pairs':'cadence_floor_comparisons_v1/INTERPRETATION_V1.md',
 'cadence_review':'independent_review/CADENCE_FLOOR_COMPACT_REVIEW_V1.json',
 'endpoint':'endpoint_audit/actual_factorial_v1/INTERPRETATION_V1.md',
 'endpoint_pairs':'endpoint_factorial_comparisons_v1/INTERPRETATION_V1.md',
 'enrollment':'enrollment/ENROLLMENT_COMPLETION.json',
 'gallery_native':'gallery_native_integration_review_v1/RESULT.json',
 'common_native':'common_native_integration_review_v1/RESULT.json',
 'naming_full':'full_naming_component_review_v2/RESULT.json',
 'common_duration':'full_common_duration_results_v2/INTERPRETATION_V1.md',
 'name_episodes':'live_name_episode_interpretation_v1/INTERPRETATION.md',
 'timing_sensitivity':'native_timing_diagnosis_v1/INTERPRETATION_V2.md',
 'branch_proof':'independent_review/GALLERY_BRANCH_PROOF_REVIEW_V1.json',
 'chronological':'long_session/v1/CHRONOLOGICAL_LIFECYCLE_SUMMARY_V1.json',
 'cue_physical':'C2_EVIDENCE_SUMMARY_V1.json',
 'nominal_scope':'design/FOLLOWUP_METADATA_CLARIFICATION_V1.json',
 'aliases':'design/SPLIT_ALIAS_DISPOSITION_V1.json',
 'recipe_guide':'handoff_drafts/RECIPE_IDENTIFIER_GUIDE.md',
}

def require(value,message):
 if not value:raise ValueError(message)

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class Reader:
 def __init__(self):self.sources={}
 def raw(self,path,expected=None,sha=None):
  path=Path(path).resolve();require(path.stat().st_size<=32*1024*1024,'Bounded metadata source')
  raw=path.read_bytes();b=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if expected is not None:require(b=={k:expected[k] for k in ('path','bytes','sha256')},'Changed source '+str(path))
  if sha is not None:require(b['sha256']==sha,'Changed pinned source '+str(path))
  self.sources[str(path)]=b;return raw,b
 def doc(self,path,expected=None,sha=None):
  raw,b=self.raw(path,expected,sha);return json.loads(raw),b

def condition_key(row):
 profile=dict(row['profile']);profile.pop('profile_id')
 return digest(dict(profile=profile,cue_condition=row['cue_condition'],gallery_condition=row['gallery_condition'],enrollment_tier=row['enrollment_tier']))

def validate_native_rows(result,total,legal_routes):
 require(result['status']=='COMPLETE' and result['requested']==result['completed']==total,'Complete native batch')
 require(result['error'] is None and result['worker_pool_joined'] is True,'Native join/no error')
 rows=result['rows'];require(len(rows)==total,'Native row count')
 require(len({r['job_key'] for r in rows})==total,'Unique declared native keys')
 require(len({(r['candidate_id'],r['case_id'],r['asr_tap'],r['identity_tap']) for r in rows})==total,'Unique native routes/cases')
 for r in rows:
  require(r['status'] in ('COMPLETE','COMPLETE_REUSED'),'Unsuccessful native row')
  require((r['candidate_id'],r['asr_tap'],r['identity_tap']) in legal_routes,'Undeclared native route')
  require(set(('path','bytes','sha256'))<=r['receipt'].keys(),'Missing native receipt identity')
 return rows

def disposition(pid,row):
 if pid.startswith('B'):
  return ('PRESERVE_HISTORICAL_CONTROL','Original S6B scope and settings remain intact; no S6C efficacy or physical-run count is inferred.',
          'Current S6C source-paced/continuous operating evidence remains pending; historical44 are retained, not reranked here.', ['foundation'])
 n=int(pid[1:])
 if n in (83,84):return ('PRESERVE_DECLARED_ALIAS_UNEXECUTED','Exact one-route C065 alias; own scored support stays absent and no native execution is credited.', 'No independent experiment or support propagation; use explicit alias mapping only.',['aliases'])
 recipe=row['recipe_id'];mode=row['profile']['tracker']['mode']
 if n<=64 or n in (108,109,131,132,133,134,135,136,137,138):
  text='N00 uses historical native evidence with new v3 clean-fraction/commit semantics; admission starvation confounds broad family conclusions.'
  refs=['foundation','n00'];gap='Fresh-input applicability and operative native branch/neighborhood coverage cannot be inferred from cached scores. No broad accuracy rejection.'
  if n in (1,2):text+=' Source-chronological lifecycle contrast exists for these exact IDs, distinct from new native inference.';refs+=['chronological']
  if n in (35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54):text+=' Retain all null seeds and evaluator-only nominal controls.';refs+=['cue_physical','nominal_scope']
  if 55<=n<=64:text+=' Preserve the registered conditional/multiple-boundary parameter interpretation; do not claim every field was independently active.'
  if 131<=n<=138:text+=' Lower clean-fraction admission is a diagnostic; zero clean support still earns zero clean duration and commitment remains positive.'
  return ('KEEP_ADMISSION_LIMITED_DIAGNOSTIC',text,gap,refs)
 if n in (65,79,117,118,119,120,121,122):
  return ('FULL_STRUCTURAL_TRADEOFF_PENDING_OPERATING_SELECTION','Full-bank anonymous comparison retained; distinct source-support/return/label objectives do not establish a universal winner.',
          'Paced and continuous operating retention pending. Equal observed metrics do not make distinct structural settings aliases.', ['anonymous_full','anonymous_review','family_native','family_review','followup_full'])
 if n==67:return ('FULL_CONDITIONAL_LATER_LABEL_TRADEOFF','Full N03 improves later cp while early-label, return and Unknown behavior worsen; exact raw words unchanged.',
                    'Operating retention remains conditional; source costs are not paced latency or an isolated speed claim.', ['n03_full','n03_review'])
 if n in (72,74,76):return ('PANEL_TRADEOFF_FULL_CONFIRMATION_PENDING','Exact '+recipe+' recipe has panel native/scored evidence; retain fixed registered comparison.',
                           'Full '+recipe+' closure/scoring and paced selection remain pending in this snapshot.', ['component_panel','asr_panel','recipe_guide'])
 if n in (71,82,191,192,193,194):return ('NATIVE_CADENCE_DIAGNOSTIC_PENDING_PACE','Actual released-context/debt admission evidence and numerical floor neighbors are retained; direct cue-trigger count was zero in the accelerated audit.',
             'Do not infer no indirect cue effect, target-voice attribution, or source-paced behavior from equal calls/aged context. Paced C071/C082 diagnostic remains pending.', ['cadence','cadence_floor','cadence_pairs','cadence_review'])
 if n in (85,86):return ('FIXED_SPLIT_ROUTE_FULL_CONFIRMATION_PENDING','One explicit asymmetric route per ID; source support uses the declared identity tap once.',
                        'Full fixed-route closure/scoring and paced40-cell comparison pending; no per-scene tap selection.', ['aliases','recipe_guide'])
 if n in (66,68,69,70,73,75,77,78,80,81):
  text='Exact '+recipe+' component or interaction remains panel-scoped; preserve words, support and measured native-source cost distinctions.'
  if n==69:text+=' Gate-only evidence has an admission-limited negative result, not a universal failure of the idea.'
  if n in (70,81):text+=' A small difference requires checking actual guard opportunities; do not label a validated field inactive from aggregate similarity.'
  return ('KEEP_PANEL_COMPONENT_TRADEOFF',text,'No broad dominance/failure conclusion; per-ID native status below is independent of compatible cached source availability.', ['component_panel','asr_panel','recipe_guide'])
 if 87<=n<=107 or 110<=n<=116:
  full=n in (88,91,105,106,111,114)
  tag='FULL_NAMING_CONDITIONAL_PENDING_PACE' if full else 'PANEL_NAMING_CONDITIONAL'
  condition=row['gallery_condition'];text='Actual native enrollment templates and explicit '+condition+' roster/tier are conditional on available E material; assigned, confirmed and stable names remain distinct.'
  if 110<=n<=116:text+=' C-only fitted thresholds are retained as a tradeoff; extra correct naming can accompany extra wrong-known exposure.'
  if 96<=n<=101:text+=' Scene/setup participant selection is an explicit experimental input, not autonomous discovery of unknown people.'
  if 102<=n<=104:text+=' Wrong-selection/visitor condition is a falsifying stress control, not an operating recommendation.'
  if n in (105,106,107):text+=' This is a real-cue naming companion, not an empty gallery.'
  return (tag,text,'Native6 integration is a distinct scope from cached/full-bank scores. Arrival-sensitive exports and source/device-domain enrollment gaps remain; no universal calibration winner.', ['enrollment','gallery_native','naming_full','name_episodes','timing_sensitivity','branch_proof'])
 if 123<=n<=130:return ('PANEL_STRUCTURAL_MECHANISM_PENDING_BROADER_COVERAGE','Six-scene native mechanism summary and broader cached panel support are separate. Exact mode: '+mode+'.',
        'No full-bank dominance or general failure claim. Pending/hold/reconciliation counters do not prove every promotion/split/merge branch activated; absent branch is not accuracy failure.', ['family_native','family_review','followup_panel'])
 if n in (139,140):return ('PANEL_SHORT_MATURE_COUPLING_DIAGNOSTIC','Registered short-versus-mature prototype-update coupling remains a matched panel diagnostic.',
                         'Native execution under this exact child and broader operating utility must be separately established; no inherited native count.', ['followup_panel','recipe_guide'])
 if 141<=n<=146:return ('FULL_MATCHED_ROSTER_DURATION_CONDITIONAL','Each fixed roster has14 eligible people (9 CMU+5 HiFi),28 disjoint combined. Estimated duration, whole-clip material, window count and templates change together.',
                 'Not a duration-only/device-domain intervention. C143/C146 reuse corresponding30s native gallery content but alter intended-roster evaluation scope; no score alias collapse.', ['enrollment','common_native','common_duration','naming_full','name_episodes'])
 if 147<=n<=166:return ('FULL_ALL_SEEDS_DIAGNOSTIC' if n<=158 else 'PANEL_ALL_SEEDS_DIAGNOSTIC',
        'Retain every declared seed and nominal control; no best-seed operating selection. Nominal geometry is explicitly evaluator-derived/oracle-like, not deployable sensor evidence.',
        'Pooled cue advantage is conditional and room/family heterogeneous. Panel-only families do not inherit full-bank evidence.', ['followup_full' if n<=158 else 'followup_panel','cue_physical','nominal_scope'])
 if 167<=n<=182:return ('FULL_COMMITMENT_NEIGHBORHOOD_TRADEOFF' if n<=174 else 'PANEL_COMMITMENT_NEIGHBORHOOD',
        'Registered1.0 to0.75 second unique-clean commitment change retains two disjoint observations; actual lifecycle activation differs from label quality.',
        'No general replacement of1.0second default from these outcomes; panel-only child does not inherit parent native6 or full scope.', ['followup_full' if n<=174 else 'followup_panel'])
 if 183<=n<=190:return ('FULL_CAPACITY_OPPORTUNITY_LIMITED_CONTROL','Full short-scene capacity companions have maximum13 live anonymous tracks and zero blocked clean duration; retain all bounds as controls.',
        'Inactive capacity opportunity does not establish memory/runtime equivalence or persistent-session capacity; continuous evidence is separately required.', ['followup_full','chronological'])
 if n in (195,196):return ('PANEL_ENDPOINT_FACTORIAL_WORD_TRADEOFF','Native full-profile-plus-cue2x2 interaction has actual advisor/reset/word evidence; default advisory thresholds are preserved.',
        'More accepted advice does not imply net equal extra resets or lexical benefit. Full-bank/operating retention and actual paced cost remain unestablished.', ['endpoint','endpoint_pairs'])
 raise ValueError('Unclassified ID '+pid)

def tests():
 base=dict(profile={'profile_id':'X','x':1},cue_condition='OFF',gallery_condition='NONE',enrollment_tier=None)
 same={**base,'profile':{'profile_id':'Y','x':1}}
 require(condition_key(base)==condition_key(same),'Only ID ignored')
 for changed in ({**base,'cue_condition':'NULL11'},{**base,'gallery_condition':'A'},{**base,'enrollment_tier':15},{**base,'profile':{'profile_id':'Y','x':2}}):require(condition_key(base)!=condition_key(changed),'Condition retained')
 sample=dict(candidate_id='C065',case_id='A',asr_tap='O0',identity_tap='O0',job_key='k',status='COMPLETE',receipt={'path':'p','bytes':1,'sha256':'x'})
 result=dict(status='COMPLETE',requested=1,completed=1,error=None,worker_pool_joined=True,rows=[sample]);legal={('C065','O0','O0')}
 require(validate_native_rows(result,1,legal)==[sample],'Native explicit admission')
 for changed in ({**result,'worker_pool_joined':False},{**result,'error':'x'},{**result,'rows':[{**sample,'status':'FAILED'}]},{**result,'rows':[{**sample,'identity_tap':'O1'}]}):
  try:validate_native_rows(changed,1,legal)
  except ValueError:pass
  else:raise AssertionError('Bad native state accepted')
 require(disposition('C083',{})[0]=='PRESERVE_DECLARED_ALIAS_UNEXECUTED','Alias remains unexecuted')
 require(disposition('B39',{})[0]=='PRESERVE_HISTORICAL_CONTROL','Historical preserved')
 return dict(status='PASS',checks=12,scope='Pure condition/alias/native failure guards; no source execution or metric inference.')

def run(output):
 out=REPORT/'candidate_disposition'/output;require(not out.exists(),'Fresh working namespace required')
 reader=Reader();registry,rb=reader.doc(REPORT/'EFFECTIVE_PROFILE_REGISTRY_V7.json',sha=REGISTRY_SHA)
 original_raw,ob=reader.raw(REPORT/'CANDIDATE_COVERAGE_AND_DISPOSITION.csv',sha=ORIGINAL_SHA)
 original=list(csv.DictReader(io.StringIO(original_raw.decode('utf-8-sig'))));original_by={r['candidate_id']:r for r in original}
 require(len(original)==len(original_by)==160,'Original160 distinct rows')
 support,sb=reader.doc(REPORT/'candidate_support/working_v2/RECEIPT.json',sha=SUPPORT_SHA)
 require(support['status']=='COMPLETE_EXPLICIT_SUPPORT_SNAPSHOT' and support['whole_study_complete'] is False,'Working support only')
 def bound_output(name):
  rows=[b for b in support['outputs'] if Path(b['path']).name==name];require(len(rows)==1,'Unique support output');return rows[0]
 cb=bound_output('CANDIDATE_SUPPORT_WORKING.csv');raw,_=reader.raw(cb['path'],cb)
 support_rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));support_by={r['candidate_id']:r for r in support_rows}
 ab=bound_output('AUTHORITY_ROUTE_SUPPORT.json');authorities,_=reader.doc(ab['path'],ab)
 crows=defaultdict(list)
 for r in registry['profiles']:crows[r['candidate_id']].append(r)
 require(len(crows)==196 and len(registry['profiles'])==388,'196 C labels388 routes')
 require(set(crows)=={f'C{i:03}' for i in range(1,197)},'Actual C IDs')
 bids={r['candidate_id'] for r in original if r['candidate_id'].startswith('B')}
 require(len(bids)==44 and set(support_by)==set(crows)|bids and len(support_rows)==240,'Exact240 identifiers')
 legal={(r['candidate_id'],r['asr_tap'],r['identity_tap']) for r in registry['profiles']}
 require(len(legal)==388,'Unique C routes')
 evidence={}
 for key,path in EVIDENCE.items():
  _,binding=reader.raw(REPORT/path);evidence[key]=binding
 # The original snapshot is deliberately not rewritten. This one later complete
 # score authority is added explicitly, not by scanning for whatever now exists.
 n03,n03b=reader.doc(REPORT/'full_n03_native_core_v3/ANALYSIS_RECEIPT.json',sha='10d38193dfa630bc06dd15d582f1d9086493ce104cc5b45535be01844e238517')
 require((n03['status'],n03['scored'],n03['unscored'])==('COMPLETE_REQUESTED_INDEX',480,0),'Supplemental N03 completion')
 coverage=next(b for b in n03['tables'] if Path(b['path']).name=='COVERAGE.csv');raw,_=reader.raw(coverage['path'],coverage)
 coverage_rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 require(len(coverage_rows)==480,'480 supplemental coverage rows')
 for tap in ('O0','O1'):
  rows=[r for r in coverage_rows if r['stream']==tap]
  require(len(rows)==240 and all(r['profile_id']=='C067' and r['identity_tap']==tap and r['status']=='SCORED' for r in rows),'Supplemental exact N03 route')
  authorities.append(dict(candidate_id='C067',asr_tap=tap,identity_tap=tap,source_id='full_n03_native_core_v3_ADDITIVE',
   scope_label='Exact closed full N03 core added after working_v2 support snapshot',execution_scope='POLICY_REPLAY_OVER_NATIVE_EVIDENCE',repetition=0,
   analysis_authority=n03b,route_rows=240,status_counts={'SCORED':240},scored_cases=[r['case_id'] for r in rows],full_bank_in_this_authority=True,coverage_binding=coverage))
 byid=defaultdict(list)
 for a in authorities:byid[a['candidate_id']].append(a)
 native=defaultdict(list);native_evidence=[]
 for batch,(filename,sha,count) in NATIVE_BATCHES.items():
  review,b=reader.doc(REPORT/'orchestration'/batch/filename,sha=sha)
  require(review['status'].startswith('PASS_COMPLETE_'),'Exact completed native review')
  if 'owner_alive' in review:require(review['owner_alive'] is False,'Recorded owner closure')
  else:require(review['externally_verified_process_identities'] and all(r['alive'] is False for r in review['externally_verified_process_identities']),'Recorded all-owner closure')
  rbinding=[x for x in review['bindings'] if Path(x['path']).name.endswith('_RESULTS.json')]
  require(len(rbinding)==1,'One native completed results source')
  results,result_binding=reader.doc(rbinding[0]['path'],rbinding[0]);rows=validate_native_rows(results,count,legal)
  closure_binding=[x for x in review['bindings'] if Path(x['path']).name=='CLOSURE.json'];require(len(closure_binding)==1,'Exact outer closure')
  closure,clb=reader.doc(closure_binding[0]['path'],closure_binding[0])
  require(closure['failure'] is None and not closure['remaining_owned_children'],'Closed outer native invocation')
  admission,adb=reader.doc(closure['admission']['path'],closure['admission'])
  require(admission['jobs']==results['jobs'],'Completed original manifest identity')
  batch_record=dict(batch=batch,closure_review=b,outer_closure=clb,admission=adb,native_results=result_binding,
    manifest_transitive_binding=results['jobs'],logical_rows=count,new_rows=sum(r['status']=='COMPLETE' for r in rows),reused_rows=sum(r['status']=='COMPLETE_REUSED' for r in rows))
  native_evidence.append(batch_record)
  groups=defaultdict(list)
  for row in rows:groups[(row['candidate_id'],row['asr_tap'],row['identity_tap'])].append(row)
  for (pid,at,it),group in groups.items():native[pid].append(dict(batch=batch,asr_tap=at,identity_tap=it,logical_cells=len(group),case_ids=sorted(r['case_id'] for r in group),
       completed_rows=sum(r['status']=='COMPLETE' for r in group),reused_rows=sum(r['status']=='COMPLETE_REUSED' for r in group),review=b))
 family,_=reader.doc(evidence['family_native']['path'],evidence['family_native'])
 family_by=defaultdict(list)
 for row in family['summary']:family_by[row['profile_id']].append(row)
 equivalence=defaultdict(list)
 for row in registry['profiles']:equivalence[condition_key(row)].append((row['candidate_id'],row['asr_tap'],row['identity_tap']))
 alias_groups=[group for group in equivalence.values() if len(group)>1]
 require(sorted(sorted(x[0] for x in group) for group in alias_groups)==[['C065','C083'],['C065','C084']],'Only exact executable-condition aliases')
 rows=[];route_bindings=[]
 for pid in sorted(support_by):
  sr=support_by[pid];actual=crows.get(pid,[]);row=actual[0] if actual else {}
  proposed,note,gap,refs=disposition(pid,row)
  conditions=[]
  for r in actual:
   profile=r['profile'];condition=dict(asr_tap=r['asr_tap'],identity_tap=r['identity_tap'],recipe_id=r['recipe_id'],
    cue_condition=r['cue_condition'],gallery_condition=r['gallery_condition'],enrollment_tier=r['enrollment_tier'],
    profile_id=profile['profile_id'],row_sha256=digest(r),profile_sha256=digest(profile),effective_key=r['effective_key'],
    neural_dependency=r['neural_dependency'],executable_condition_sha256=condition_key(r))
   conditions.append(condition);route_bindings.append(dict(candidate_id=pid,**condition))
  summaries=[]
  for a in byid[pid]:summaries.append({k:a[k] for k in ('source_id','asr_tap','identity_tap','execution_scope','repetition','analysis_authority','route_rows','status_counts','full_bank_in_this_authority')})
  score_scopes=[]
  for at,it in json.loads(sr['registered_routes']):
   selected=[a for a in byid[pid] if a['asr_tap']==at and a['identity_tap']==it]
   union=set(c for a in selected for c in a['scored_cases'])
   score_scopes.append(dict(asr_tap=at,identity_tap=it,case_union_count=len(union),full_bank_authorities=[a['source_id'] for a in selected if a['full_bank_in_this_authority']]))
  if pid in ('C083','C084'):require(not byid[pid] and not native[pid],'Aliases receive no propagated authority')
  original_row=original_by.get(pid)
  rows.append(dict(candidate_id=pid,origin=sr['origin'],family=sr['family'],registered_parent=sr['parent'],recipe_id=sr['recipe_id'],
   registered_title=original_row['title'] if original_row else '',registered_routes=sr['registered_routes'],
   original_registration_row_json=json.dumps(original_row,sort_keys=True,ensure_ascii=False) if original_row else '',
   original_registration_row_sha256=digest(original_row) if original_row else '',original_registration_disposition=original_row['disposition'] if original_row else 'ADDITIVE_AFTER_ORIGINAL_160',
   exact_route_settings_provenance_json=json.dumps(conditions,separators=(',',':')),original_support_snapshot=sb['sha256'],
   scored_scope_json=json.dumps(score_scopes,separators=(',',':')),scored_authorities_json=json.dumps(summaries,separators=(',',':')),
   native_integration_status='ESTABLISHED_IN_EXPLICIT_CLOSED_BATCH_METADATA' if native[pid] else 'PENDING_OR_UNVERIFIED',
   native_batch_scope_json=json.dumps(native[pid],separators=(',',':')),physical_inference_count='',
   native_scope_limit='Closed metadata logical cells, including reused rows; not an additive physical count. Old/model/audio/event payloads are transitively bound and not reaudited here.',
   family_native_mechanism_summary_json=json.dumps(family_by[pid],separators=(',',':')),
   evidence_references_json=json.dumps({key:evidence[key] for key in refs},separators=(',',':')),
   proposed_working_disposition=proposed,supported_interpretation=note,remaining_empirical_gaps=gap,
   final_scientific_selection='PENDING',final_operating_retention='PENDING',paced_long_status='PENDING_OR_UNVERIFIED_IN_THIS_PROPOSAL'))
 require(len(rows)==240 and {r['candidate_id'] for r in rows}==set(support_by),'Exactly240 output rows')
 for row in rows:
  if row['candidate_id'] in original_by:require(json.loads(row['original_registration_row_json'])==original_by[row['candidate_id']],'Original full row preserved')
  require(row['physical_inference_count']=='' and row['final_scientific_selection']=='PENDING','No count/selection fabrication')
 reader.raw(Path(__file__));reader.raw(Path(__file__).with_name('README_S6C_CANDIDATE_DISPOSITION_WORKING_V1.md'))
 out.mkdir(parents=True)
 def publish(name,raw):
  path=out/name
  with path.open('xb') as f:f.write(raw)
  return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 def pubjson(name,value):return publish(name,(json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode())
 outputs=[publish('ORIGINAL_REGISTRATION_SNAPSHOT.csv',original_raw)]
 buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 outputs.append(publish('CANDIDATE_DISPOSITION_PROPOSAL.csv',buf.getvalue().encode('utf-8')))
 outputs.append(pubjson('REGISTERED_ROUTE_SETTINGS_PROVENANCE.json',dict(registry=rb,routes=route_bindings,aliases=alias_groups)))
 outputs.append(pubjson('SCORING_AND_NATIVE_AUTHORITIES.json',dict(scoring_authorities=authorities,native_batches=native_evidence,evidence_catalog=evidence)))
 lines=['# Working disposition proposal: all240 registered IDs','',
  'This is a working scientific coverage/disposition proposal, not final selection, operating retention, campaign completion, pruning or a new configuration. All44 historical B controls and196 C labels remain. The original160-row CSV is preserved byte-for-byte alongside this proposal; each original row, settings string, digest and disposition is copied unchanged into the expanded CSV. Eighty additive C117–C196 labels are appended using exact final V7 route/profile provenance. No old file is edited.','',
  'The input support working_v2 snapshot is preserved; the only later scoring addition is the explicitly bound completed full N03 core. A case union is coverage, not a pooled score or native count. A full authority means one exact authority independently covers240 cases; aliases never inherit scores. The CSV retains every named scoring authority and its original scope. C083/C084 remain declared one-route C065 aliases with no separate scored/native credit. C143/C146 are30s gallery-content anchors whose intended-roster scopes differ from C089/C092; their experiments are not collapsed. Equal observed C065/C119 metrics do not make their settings aliases.','',
  'Native scope is established separately from exact closed batch metadata: review → closed original invocation → exact admission/manifest identity → completed logical row list. Per-ID rows contain each batch and exact case/route membership. Reused references and overlapping batches must not be summed as physical attempts; physical_inference_count is deliberately blank. Model/audio/event payloads and job manifests are transitively bound by those existing closures and are not reread. No candidate receives six-scene native credit from scoring alone. For absent native evidence, PENDING_OR_UNVERIFIED means unestablished in this proposal, not proven unexecuted. Historical44 retain their immutable prior source authority; their native bodies are not recounted here.','',
  'All final scientific/operating and paced/long decisions remain pending. Full N08/N10, N12 and fixed cross-route confirmation were still awaiting completed score evidence at this snapshot. The known prepared source-paced and continuous plans are not labeled executed. Registry labels, executable recipe N00–N14 and similarly numbered planning ideas are distinct. Endpoint advice and uncertainty scheduling require their full native dependencies; N01 recipe equality alone never proves compatible evidence.','',
  'Evidence notes: N00 old-gate policy retains the new v3 clean-fraction/commit confound. Fixture reachability is not empirical error incidence. Family native counters show particular operations, not universal activation of every promotion/split/merge path. Panel-only conditions are not rejected through a broad dominance claim. Seeded nulls and evaluator-derived nominal geometry remain diagnostics. Gallery availability, C-only calibration, scene/setup roster selection, same-person14/14 common-duration controls and source/device-domain limitations stay explicit.','',
  'Current full-bank aggregate populations differ by metric: complete203 scenes/6016 cp words/693 turns/292 returns, separate incomplete26 scenes/84 turns/32 returns, and11 strict-empty scenes. This proposal does not recompute or pool those results. Actual480 input views include nonuniform source durations; no uniform45second bank is assumed.','',
  '## Evidence catalog','']
 for key,b in evidence.items():lines.append(f"- **{key}**: `{Path(b['path']).relative_to(REPORT)}`; SHA256 `{b['sha256']}`.")
 lines+=['','## Per-ID working decisions','', '| ID | Family / recipe | Scored support by route | Native scope | Working proposal and remaining gap |','|---|---|---|---|---|']
 for row in rows:
  scopes=json.loads(row['scored_scope_json']);score='; '.join(f"{s['asr_tap']}/{s['identity_tap']}: union{s['case_union_count']}, full authorities{len(s['full_bank_authorities'])}" for s in scopes)
  ns=json.loads(row['native_batch_scope_json']);native_text='; '.join(f"{n['batch']} {n['asr_tap']}/{n['identity_tap']}:{n['logical_cells']}" for n in ns) if ns else 'PENDING_OR_UNVERIFIED'
  text=row['proposed_working_disposition']+'. '+row['supported_interpretation']+' Gap: '+row['remaining_empirical_gaps']
  lines.append('| '+ ' | '.join(x.replace('|','/') for x in (row['candidate_id'],row['family']+' / '+row['recipe_id'],score,native_text,text))+' |')
 outputs.append(publish('WORKING_DISPOSITION.md',('\n'.join(lines)+'\n').encode()))
 receipt=dict(schema='s6c.working_candidate_disposition.v1',status='COMPLETE_WORKING_PROPOSAL_ONLY',created_utc=datetime.now(timezone.utc).isoformat(),
  final_selection=False,whole_study_complete=False,candidate_count=240,historical_count=44,new_c_count=196,original_rows_preserved=160,additive_rows=80,
  original_registration=ob,registry=rb,support_snapshot=sb,explicit_later_score_authority=n03b,tests=tests(),
  disposition_counts=dict(Counter(r['proposed_working_disposition'] for r in rows)),
  native_status_counts=dict(Counter(r['native_integration_status'] for r in rows)),sources=list(reader.sources.values()),outputs=outputs,
  source_scope='Explicit compact metadata, summary and interpretation bytes only. No discovery of current native outcomes, raw logs, predictions, PCM, model runs, scoring or physical recount.')
 binding=pubjson('RECEIPT.json',receipt);print(json.dumps(binding,indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--test',action='store_true');parser.add_argument('--output-subdir',default='working_v1');args=parser.parse_args()
 if args.test:print(json.dumps(tests(),indent=2))
 else:
  require(Path(args.output_subdir).name==args.output_subdir and args.output_subdir not in ('','.','..'),'Contained named output')
  run(args.output_subdir)
