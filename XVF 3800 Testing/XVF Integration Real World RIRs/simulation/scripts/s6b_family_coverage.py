"""Build evidence-qualified S6B family coverage; see README_S6B_FAMILY_COVERAGE.md.

This is a model-free reporting tool. It never creates or relabels predictions.
Implementation statements are a reviewed map to frozen executable entry points;
AST symbol checks locate those entry points, not prove mechanism effectiveness.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6B/20260909T230840Z'
FAMILIES={
 'F1':'Exact and matched voice-only controls',
 'F2':'Simple spatial rules',
 'F3':'Change-point and uncertainty approaches',
 'F4':'Probabilistic and temporal alternatives',
 'F5':'Robust identity state',
 'F6':'Pyannote and ReDim evidence',
 'F7':'ASR interactions',
 'F8':'Resource-adaptive operation',
}


def mechanism(mid,family,name,profiles,entry,signals,limit,count=True):
 return dict(mechanism_id=mid,family_id=family,mechanism=name,profiles=profiles.split(','),
             entry_points=entry.split(';'),activity_signals=signals.split(',') if signals else [],
             interpretation_limit=limit,counted_distinct_mechanism=count)


MECHANISMS=[
 mechanism('M01','F1','Original anonymous clustering and common-scheduler control','B00,B36','research_tracking_v2.py:S6BTracker.update','evidence_admit','B00 historical outputs have no S6B internal snapshot; B36 capacity256 matches legacy max27. Fixed-input decision-field parity and new480-output R0 span/anonymous-label parity are separate proofs; newly computed vectors are not generally bit-exact. Scheduler attribution may still differ.',False),
 mechanism('M02','F1','Voice/time unique and disjoint evidence commitment','B01','research_tracking_v2.py:_Track.admit;research_tracking_v2.py:S6BTracker.update','evidence_admit,track_commit','Two disjoint observations plus1s unique evidence; Unknown and capacity rejects remain visible.'),
 mechanism('M03','F1','One-person and all-Unknown adversarial controls','B37,B38','research_scheduler.py:CausalScheduler._asr','decisions','Explicit controls independent of embedding supply; excluded from distinct research mechanism count.',False),
 mechanism('M04','F2','Angle-dominant anonymous association with severe voice veto','B02','research_tracking_v2.py:S6BTracker._select','angle_voice_conflict_reject,cue_nonzero','Enabled but unavailable cue yields Unknown; only disabled-cue configuration is the exact voice parent. No enrolled seat identity.'),
 mechanism('M05','F2','Sustained direction-change qualification','B03','research_tracking_v2.py:S6BTracker._spatial','cue_positive,cue_nonzero','Persistence and observation continuity are distinct from packet freshness.'),
 mechanism('M06','F2','Expiring position memory','B04','research_tracking_v2.py:S6BTracker._location_scores','cue_nonzero','Position credit decays with age; true seat and person count are not inputs.'),
 mechanism('M07','F2','Reliability-scaled spatial fusion','B05','research_tracking_v2.py:S6BTracker._location_scores','cue_nonzero','Spatial credit operates among voice-compatible candidates; it cannot rescue a below-floor voice match.'),
 mechanism('M08','F2','Static spatial fusion','B06','research_tracking_v2.py:S6BTracker._location_scores','cue_nonzero','Static credit is a distinct reference weighting rule, not evidence that stable bearings are correct.'),
 mechanism('M09','F3','Accumulated angular innovation with drift and decay','B07','research_tracking_v2.py:S6BTracker._spatial','innovation_accumulate,innovation_change_proposal','Folded0..180 is linear; CUSUM-style proposals are heuristic and need voice compatibility.'),
 mechanism('M10','F3','Uncertain folded-bearing likelihood score','B08','research_tracking_v2.py:S6BTracker._location_scores','cue_nonzero','Gaussian-style folded uncertainty is heuristic, not calibrated probability; no independent-beam likelihood product.'),
 mechanism('M11','F3','Observable contradiction quarantine and revalidation','B32','research_tracking_v2.py:S6BTracker._sensor','sensor_contradiction,sensor_quarantine,sensor_recovery,sensor_stale_anchor_audit','N01 detects voice/location disagreement, not reference errors. Stale anchors can audit recovery without gaining association credit.'),
 mechanism('M12','F4','Bounded tempered hypothesis beam','B13,B14','research_tracking_v2.py:S6BTracker._bayes','bayes_hypothesis_update','Up to8 hypotheses/horizon8, Unknown alternative, hand-selected temperature; not calibrated posterior.'),
 mechanism('M13','F4','Duration-state continuity filter','B30','research_tracking_v2.py:S6BTracker._hsmm','hsmm_duration_update','HSMM-style duration bins8 and finite duration range; heuristic rather than trained generative HSMM.'),
 mechanism('M14','F4','Bounded joint acoustic-group assignment beam','B31','research_tracking_v2.py:S6BTracker._global','bounded_global_assignment','Up to4 recent acoustic groups and beam16; sequential groups may reuse identity. No simultaneous independent sources or one-to-one person constraint.'),
 mechanism('M15','F5','Slow voice/fast location and dormant reentry','B09,B10','research_tracking_v2.py:S6BTracker._threshold;research_tracking_v2.py:S6BTracker._prototype','track_dormant,track_reactivate','Dormant tracks require stronger voice reentry; cue-off parent remains same structural memory mode.'),
 mechanism('M16','F5','Bounded multiple voice prototypes','B11','research_tracking_v2.py:S6BTracker._prototype','prototype_slot_add','Maximum3 prototypes per track, finite track capacity; no automatic claim of improved invariance.'),
 mechanism('M17','F5','Prototype checkpoint and reversible rollback','B12','research_tracking_v2.py:S6BTracker._prototype','prototype_rollback_checkpoint,prototype_rollback,label_revision','Checkpoints and actual rollback are separate counts. Zero bank rollback means unexercised, not a demonstrated recovery benefit.'),
 mechanism('M18','F5','Disjoint escrow for cue-assisted prototype changes','B33','research_tracking_v2.py:S6BTracker._prototype','prototype_escrow_hold,prototype_escrow_release,prototype_escrow_reject,prototype_escrow_expire','N03 releases only on later disjoint compatible voice; pending/rejected short replies remain visible.'),
 mechanism('M19','F5','Bounded delayed graph association revisions','B15','research_tracking_v2.py:S6BTracker._graph;research_tracking_v2.py:S6BTracker._revise','delayed_graph_update,label_revision','Graph max8 nodes; forward revisions preserve first decision. Structural track merge/split is NOT_IMPLEMENTED.'),
 mechanism('M20','F6','Posterior versus hard segmentation policy and refresh stride','B01,B16,B17,B18,B19,B21,B29','models.py:powerset_posteriors;research_profiles.py:segmentation_gate;research_scheduler.py:EmbeddingAdmission.segmentation','admitted,rejected','Fixed10s neural graph; posterior wrapper/stride differ. Local powerset slots never become identities. B16/B17 are component bundles, not extra distinct mechanism counts.'),
 mechanism('M21','F6','Fractional/contiguous arrived clean-evidence admission','B18,B19,B20,B34','research_scheduler.py:EmbeddingAdmission.candidate','admitted,rejected','Unknown newer frame support counts unclean. Does not use an unsupported ReDim mask or trim source truth spans.'),
 mechanism('M22','F6','Contiguous short/long evidence with independent commitment','B18,B20,B18_C1,B20_C1','models.py:SpeakerModels.embed;research_tracking_v2.py:_Track.admit','admitted,track_commit','0.5s/1s windows crossed with1/2 disjoint commitment at fixed0.25s hop;1s unique duration still required.'),
 mechanism('M23','F6','Early short observation then long confirmation','B34','research_scheduler.py:EmbeddingAdmission.candidate','admitted','Real two-stage waveform support; .45s contiguous threshold repair retained separately from rejected .5s setting.'),
 mechanism('M24','F6','Full-window versus dispatch RMS with once-applied gain','B01,B26,B27,B35','research_scheduler.py:EmbeddingAdmission.candidate','admitted,rejected','New RMS support policy; lower gain is an explicitly different prepared input, not a profile gain multiplier.'),
 mechanism('M25','F7','Protected silence-confirmed endpoint advice','B23,B39','research_profiles.py:EndpointAdvisorV2.observe;models.py:SherpaStream.reset_endpoint','advisory_endpoint_resets,advisory_only_resets,coincident_native_and_advisory_resets,N04_rate_limited,N04_circuit_opened,N04_circuit_open','N04 rate/circuit breaker leaves native endpoints active. Accepted proposals may coincide with native resets.'),
 mechanism('M26','F7','Sherpa endpoint/dispatch and supported modified-beam comparison','B22,B28','models.py:SherpaStream.__init__;models.py:SherpaStream.accept','actual_asr_resets','B22 shortens native endpoint thresholds at50ms host dispatch; B28 restores thresholds and uses modified_beam_search paths2. These contrasts bundle settings; host reads are not encoder chunk length.'),
 mechanism('M27','F8','Global voice-observation floor with event cadence','B24,B25,B24_FREQUENT,B24_SPARSE','research_scheduler.py:EmbeddingAdmission.candidate;research_scheduler.py:EmbeddingAdmission.admitted','N05_debt_due,N05_debt_due_admitted,N05_sole_debt_shorter_cadence_admissions,sole_cue_shorter_cadence_admissions','N05 adaptation: global admitted observation age, not per-track unique-debt priority. Debt never bypasses RMS/purity/overlap gates.'),
 mechanism('M28','F8','Resident model lease with fresh scene state','B01,B16,B24,B28','models.py:ResidentModelBundle.acquire;models.py:ResidentModelBundle.release','native_jobs','Native job count proves processing, not reuse. Separate COMPONENT_NEURAL_SMOKE resident-repeat evidence and epoch worker lease/load receipts establish reuse; fresh scene state is separately checked.'),
 mechanism('M29','F8','Bounded causal watermark scheduler and revision budgets','B01,B15','research_scheduler.py:CausalScheduler._drain;research_scheduler.py:CausalScheduler._revise','transcript_reconciliation','N07 uses2s horizon plus4 reconciliations per utterance; node cap is not edit cap. Exhausted/over-age reconciliation skips the edit and retains the latest label; it does not force Unknown. Ongoing-display changes are separate.'),
]

CONTRASTS=[
 ('I01','Original/tuned components x cues','B01,B05,B16,B17','B01:B05,B16:B17,B01:B16,B05:B17','FACTORIAL_COMPONENT_BUNDLE','Cue-on uses adaptive mode; disabled-cue adaptive has exact voice-parent parity in validation. Component main effect is a bundle; interaction is selected-bank difference of differences.'),
 ('I02','Tracking-only/endpoint-only/both/none','B01,B05,B23,B39','B01:B05,B01:B23,B23:B39,B05:B39','FACTORIAL_ROUTING','Tracking-only reuses R0 words; endpoint branch has fresh Sherpa observations. Advisory-only versus coincident resets must remain separate.'),
 ('I03','Duration x disjoint commitment','B18,B20,B18_C1,B20_C1','B18:B20,B18_C1:B20_C1,B18:B18_C1,B20:B20_C1','MATCHED_FACTORIAL','Window0.5/1s x disjoint count2/1; unique duration1s and hop0.25s fixed. Diagnostic C1 cells are not extra method families.'),
 ('I04','Posterior versus hard at fixed coarse stride','B01,B29','B01:B29','ISOLATED_POLICY','Same gate-only purity and0.75s stride; posterior onset/offset are operative only in the posterior policy.'),
 ('I05','Posterior versus hard with fractional purity','B18,B21','B18:B21','ISOLATED_POLICY','Same0.5s stride and fractional evidence support; compare with I04 for policy/purity-stride context, not a full Cartesian design.'),
 ('I06','Segmentation stride with posterior gate-only purity','B19,B29','B29:B19','ISOLATED_STRIDE','Posterior and gate-only purity held fixed;0.75 to0.5s refresh stride.'),
 ('I07','Fractional versus gate-only evidence purity','B18,B19','B19:B18','ISOLATED_PURITY','Posterior and0.5s stride held fixed; fraction rule versus gate-only.'),
 ('I08','RMS support x gain','B01,B35,B26,B27','B01:B35,B26:B27,B01:B26,B35:B27','MATCHED_FACTORIAL','Full-window versus dispatch support crossed with historical/lower3dB once-applied input. Compare separately on O0/O1; unchanged nominal profile gain does not mean unchanged samples.'),
 ('I09','Frequent/sparse/event cadence','B24,B24_FREQUENT,B24_SPARSE','B24_FREQUENT:B24_SPARSE,B24_FREQUENT:B24,B24_SPARSE:B24','WORK_BUDGET_COMPARISON','Fixed window/purity, differing scheduling and debt enablement. Calls are observed, not constrained equal; no equal-work claim until cost/coverage comparison.'),
 ('I10','Cue scheduling plus tracking at event cadence','B24,B25','B24:B25','BUNDLED_CUE_INTERVENTION','Changes cadence_cues_enabled AND tracking mode/enable/route. Cannot attribute B25 difference to scheduling alone.'),
 ('I11','Location decay and dormant returns','B01,B04,B09,B10','B01:B04,B01:B09,B09:B10','CONDITION_STRATIFIED','Decay and dual memory are different mechanisms. Actual return/relocation/same-bearing/wrong-cue strata are scoring-only metadata; no true geometry enters prediction.'),
 ('I12','Modified beam with host dispatch','B01,B22,B28','B01:B28,B22:B28','BUNDLED_ASR_INTERVENTION','B28 vs B01 changes decoding/max paths and100to50ms dispatch. B28 vs B22 also restores native endpoint thresholds; it is not isolated decoder search.'),
 ('I13','Early-short then long evidence','B20,B34','B20:B34','EVIDENCE_BUNDLE','Changes evidence policy and contiguous purity rule/threshold; not merely adding an earlier call to unchanged purity.'),
 ('I14','N01 quarantine','B05,B32','B05:B32','ISOLATED_OPTION','Only sensor_quarantine_enabled; count contradictions/quarantine/recovery separately and retain Unknown coverage.'),
 ('I15','N03 update escrow','B05,B33','B05:B33','ISOLATED_OPTION','Only update_escrow_enabled; cue-assisted prototype changes await disjoint confirmation.'),
 ('I16','Bayesian cue-on/off parent','B13,B14','B13:B14','MATCHED_CUE_ROUTE','Same Bayesian state and bounds; missing current packet can retain earlier cue-conditioned history.'),
]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def binding(path,expected=None):
 p=Path(path).resolve();raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 if expected is not None and sha!=expected:raise ValueError('Binding mismatch: '+str(p))
 return dict(path=str(p),bytes=len(raw),sha256=sha)
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csv_write(path,rows):
 with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
  for row in rows:w.writerow({k:json.dumps(v,sort_keys=True,allow_nan=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
def flatten(value,prefix=''):
 result={}
 for k,v in value.items():
  key=prefix+'.'+k if prefix else k
  result.update(flatten(v,key)) if isinstance(v,dict) else result.update({key:v})
 return result
def symbol_locations(path):
 tree=ast.parse(Path(path).read_text(encoding='utf-8-sig'));result={}
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):result[n.name]=n.lineno
  if isinstance(n,ast.ClassDef):
   result[n.name]=n.lineno
   for m in n.body:
    if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)):result[n.name+'.'+m.name]=m.lineno
 return result


def profile_activity(audit,pids):
 rows=[r for r in audit['rows'] if r['profile_id'] in pids]
 tracker=Counter();native=Counter();cue=Counter();scopes=Counter();jobs=set();states=Counter()
 for r in rows:
  t=r['tracker']
  if t['status']=='PASS':
   tracker.update(t['all_actual_operations']);states.update(t['decision_states']);scopes.update(t['transcript_revision_scopes'])
   cue['cue_nonzero']+=t['nonzero_spatial_score_decisions'];cue['cue_positive']+=t['cue_effective_positive_credit'];cue['decisions']+=t['decision_count']
  if r.get('neural_job_key') in audit['unique_upstream_jobs']:jobs.add(r['neural_job_key'])
 for key in jobs:
  upstream=audit['unique_upstream_jobs'][key];native.update(upstream['counts'])
  native.update({'N04_'+k:v for k,v in upstream['N04_endpoint_reasons'].items()})
 combined=tracker+native+cue
 combined['native_jobs']=len(jobs);combined['transcript_reconciliation']=scopes['bounded_forward_reconciliation']
 return dict(observed_profiles=sorted({r['profile_id'] for r in rows}),outputs=len(rows),unique_native_jobs=len(jobs),counts=dict(combined),decision_states=dict(states),transcript_revision_scopes=dict(scopes))


def differences(registry,recipes,a,b):
 def values(pid):
  row=registry[pid];p=flatten(row['profile']);p.pop('profile_id',None)
  p['prepared_input.gain_variant']=recipes[row['recipe_id']]['gain_variant']
  return p
 x,y=values(a),values(b)
 return {k:{'from':x.get(k),'to':y.get(k)} for k in sorted(x.keys()|y.keys()) if x.get(k)!=y.get(k)}


def resident_witnesses(audit):
 """Read bounded early native events already hash-checked by the source audit."""
 jobs={}
 for row in audit['rows']:
  key=row.get('neural_job_key')
  if key in audit['unique_upstream_jobs']:jobs.setdefault(row['recipe_id'],set()).add(key)
 results=[]
 for recipe,keys in sorted(jobs.items()):
  observations=[]
  for key in sorted(keys)[:8]:
   source=audit['unique_upstream_jobs'][key]['native_events'];found=None
   with Path(source['path']).open(encoding='utf-8-sig') as handle:
    for _ in range(32):
     line=handle.readline()
     if not line:break
     event=json.loads(line)
     if event.get('event_type')=='research_resident_bundle':found=event['payload'];break
   if found is not None:observations.append(dict(neural_job_key=key,native_events=source,actual_bundle_event=found))
   if found and found.get('weights_reused') and found.get('fresh_asr_stream') and found.get('session_index',0)>1:break
  reuse=any(x['actual_bundle_event'].get('weights_reused') and x['actual_bundle_event'].get('fresh_asr_stream') and x['actual_bundle_event'].get('session_index',0)>1 for x in observations)
  results.append(dict(recipe_id=recipe,status='NATIVE_REUSE_WITNESS' if reuse else 'NO_REUSE_WITNESS_IN_BOUNDED_PREFIX_SAMPLE',observations=observations))
 return dict(schema='jp_s6b_resident_reuse_witness_v1',recipes=results,
  scope='Up to8 existing jobs/recipe and32 initial lines/job. Source audit verified full event hashes; this builder reads bounded prefixes. Session_index>1 plus weights_reused/fresh_asr_stream establishes an exercised repeated acquisition under the bound ResidentModelBundle implementation. It does not prove every session, equal loading costs or cross-host performance.')


def check():
 assert len(FAMILIES)==8 and {m['family_id'] for m in MECHANISMS}==set(FAMILIES)
 assert len({m['mechanism_id'] for m in MECHANISMS})==len(MECHANISMS)
 assert sum(m['counted_distinct_mechanism'] for m in MECHANISMS)>=12
 assert len(CONTRASTS)==len({x[0] for x in CONTRASTS})
 assert flatten({'a':{'b':2}})=={'a.b':2}
 return dict(status='PASS',checks=5,scope='Reporter schema/unique semantic-map IDs only; not proof of application behavior')


def build(args):
 check();report=args.report;spec_path=report/'EPOCH2_EXECUTION_MANIFEST.json';spec=read(spec_path)
 sources=[binding(spec_path),binding(__file__),binding(spec['effective_profile_registry']['path'],spec['effective_profile_registry']['sha256']),binding(args.audit)]
 audit=read(args.audit)
 if audit['status']!='PASS' or audit['execution_manifest']['sha256']!=sources[0]['sha256']:raise ValueError('Audit epoch/status mismatch')
 binding(audit['prediction_or_native_index']['path'],audit['prediction_or_native_index']['sha256'])
 if audit['mode']!='actual_main_predictions':raise ValueError('Coverage requires actual comparison predictions, not canonical pilot labels')
 registry={r['profile_id']:r for r in read(spec['effective_profile_registry']['path'])['profiles']}
 if {p for m in MECHANISMS for p in m['profiles']}!=set(registry):raise ValueError('Reviewed mechanism map does not cover the exact registered profile IDs')
 recipes={r['recipe_id']:r for r in spec['recipes']}
 app=Path(spec['root'])/'app/edge_speech_pipeline';expected={str(Path(r['path']).resolve()):r for r in spec['execution_files']}
 symbols={};code_bindings={}
 for name in ('research_tracking_v2.py','research_scheduler.py','models.py','research_profiles.py'):
  p=app/name;want=expected[str(p.resolve())];code_bindings[name]=binding(p,want['sha256']);symbols[name]=symbol_locations(p)
 sources.extend(code_bindings.values())
 receipts={}
 for name in ('tracking/TRACKER_CHECKS.json','COMPONENT_RUNTIME_FIXTURES.json','validation/ACTUAL_PILOT_VALIDATION_FINAL.json','validation/PILOT_INDEX_LINEAGE.json','COMPONENT_NEURAL_SMOKE.json','COMPONENT_NEURAL_REPAIR_B34.json'):
  p=report/name
  if p.exists():
   if read(p).get('status') not in ('PASS','COMPLETE'):raise ValueError('Supporting receipt is not passing/complete: '+name)
   receipts[name]=binding(p);sources.append(receipts[name])
 for name in ('tracking/TRACKER_CHECKS.json','COMPONENT_RUNTIME_FIXTURES.json','validation/ACTUAL_PILOT_VALIDATION_FINAL.json','validation/PILOT_INDEX_LINEAGE.json'):
  if name not in receipts:raise ValueError('Required fixture/validation receipt missing: '+name)
 r0_proof_path=report/'R0_ALL_FEATURE_PARITY.json';r0_proof=read(r0_proof_path)
 if r0_proof['status']!='PASS_SEMANTIC_WITH_NUMERICAL_DIFFERENCES':raise ValueError('Full R0 semantic/numerical proof status differs')
 sources.append(binding(r0_proof_path))
 ideas_path=SIM/'reports/S6A/20260909T202250Z/design/IDEA_REGISTRY_EXTENDED.json';sources.append(binding(ideas_path));ideas={r['id']:r for r in read(ideas_path)['items']}
 sources.append(binding(spec['challenge_panel']['path'],spec['challenge_panel']['sha256']))
 panel=read(spec['challenge_panel']['path']);expected_cells={(c,s) for c in panel['case_ids'] for s in panel['streams']};expected_outputs=len(expected_cells)
 actual_cells={pid:set() for pid in registry}
 for row in audit['rows']:
  pid=row['profile_id'];cell=(row['case_id'],row['stream'])
  if cell not in expected_cells:raise ValueError('This builder requires the declared challenge population; use a separate full-bank coverage contract')
  if cell in actual_cells[pid]:raise ValueError('Duplicate profile/case/tap audit row')
  actual_cells[pid].add(cell)
 reuse=resident_witnesses(audit)
 def population(pids):
  return {pid:dict(observed_outputs=len(actual_cells[pid]),expected_outputs=expected_outputs,
                  complete=actual_cells[pid]==expected_cells,missing_cells=sorted(expected_cells-actual_cells[pid])) for pid in pids}
 rows=[]
 for m in MECHANISMS:
  location=[]
  for entry in m['entry_points']:
   filename,symbol=entry.split(':');line=symbols[filename][symbol];location.append(dict(path=code_bindings[filename]['path'],sha256=code_bindings[filename]['sha256'],symbol=symbol,line=line))
  a=profile_activity(audit,m['profiles']);obs=a['observed_profiles'];missing=sorted(set(m['profiles'])-set(obs))
  signal={k:a['counts'].get(k,0) for k in m['activity_signals']} if obs else None
  activity='OBSERVED_ACTIVITY' if signal and any(signal.values()) else 'NO_OBSERVED_LISTED_ACTIVITY' if obs else 'PENDING_COMPONENT_RECIPE_AUDIT'
  if m['mechanism_id'] in ('M20','M24') and obs and set(obs)<={'B01'}:activity='PARTIALLY_OBSERVED_BASE_CONTROL_ONLY'
  if m['mechanism_id']=='M28' and obs:activity='NATIVE_PROCESSING_OBSERVED_REUSE_PROOF_SEPARATE_RECEIPT'
  if m['mechanism_id']=='M01':activity='B36_OBSERVED_B00_NOT_INSTRUMENTED' if 'B36' in obs else 'CONTROL_PARITY_SEPARATE_RECEIPT'
  rows.append(dict(family_id=m['family_id'],family=FAMILIES[m['family_id']],mechanism_id=m['mechanism_id'],mechanism=m['mechanism'],profiles=m['profiles'],
   counted_distinct_mechanism=m['counted_distinct_mechanism'],implementation_status='IMPLEMENTED_REVIEWED_EXECUTABLE_BRANCH',entry_points=location,
   fixture_evidence='TRACKER24_AND_COMPONENT17_CHECKS_PASS; scope per linked receipt, not a separate check for every row',
   observed_profiles=obs,pending_profiles=missing,profile_population=population(m['profiles']),audited_outputs=a['outputs'],expected_outputs_per_profile=expected_outputs,unique_upstream_jobs=a['unique_native_jobs'],
   bank_activity_status=activity,activity_signals=signal,decision_states=a['decision_states'],
   benefit_status='NOT_INFERRED_FROM_IMPLEMENTATION_OR_ACTIVITY; see paired score/resource analysis',interpretation_limit=m['interpretation_limit']))
 contrast_rows=[]
 for cid,title,pids,edges,kind,limit in CONTRASTS:
  pids=pids.split(',');pairs=[]
  for edge in edges.split(','):
   a,b=edge.split(':');delta=differences(registry,recipes,a,b)
   if not delta:raise ValueError('Alias contrast '+edge)
   pairs.append(dict(parent=a,candidate=b,same_neural_recipe=registry[a]['recipe_id']==registry[b]['recipe_id'],changed_fields=delta))
  a=profile_activity(audit,pids)
  contrast_rows.append(dict(contrast_id=cid,required_contrast=title,profiles=pids,design=kind,exact_effective_differences=pairs,
   observed_profiles=a['observed_profiles'],pending_profiles=sorted(set(pids)-set(a['observed_profiles'])),
   evidence_status='ALL_CELLS_OBSERVED' if all(actual_cells[p]==expected_cells for p in pids) else 'PARTIALLY_OBSERVED_PENDING_COMPONENT_RECIPES',profile_population=population(pids),
   expected_outputs_per_cell=expected_outputs,matched_population='Same fixed44 challenge scenes and both taps; compare within tap with complete-reference denominators where required',
   inference_limit=limit,benefit_status='WITHHELD_FROM_COVERAGE_REPORT'))
 ni={
  'N01':('IMPLEMENTED','B32','M11','Voice/location contradiction credit quarantine, later disjoint revalidation; no reference-angle oracle.','sensor_contradiction,sensor_quarantine,sensor_recovery'),
  'N02':('NOT_IMPLEMENTED','','','No cue-driven extra segmentation refresh/reliability-weighted trailing context API. Fixed-stride posterior comparison is not this method; omitted as a separate additional neural scheduling intervention. No domination evidence claimed.',''),
  'N03':('IMPLEMENTED','B33','M18','Disjoint later voice confirmation releases cue-assisted prototype update escrow; expiry/rejection remain explicit.','prototype_escrow_hold,prototype_escrow_release,prototype_escrow_reject,prototype_escrow_expire'),
  'N04':('IMPLEMENTED','B23,B39','M25','Silence-confirmed advice has minimum reset interval, per-minute budget and timed breaker. It does not identify false endpoints using truth.','advisory_endpoint_resets,advisory_only_resets,N04_rate_limited,N04_circuit_opened,N04_circuit_open'),
  'N05':('IMPLEMENTED_ADAPTATION','B24,B25','M27','Actual global time since admitted voice observation plus event cadence. Per-track unique-deficit queue, deficit ranking and track service quotas are NOT_IMPLEMENTED; do not claim complete original N05.','N05_debt_due,N05_debt_due_admitted,N05_sole_debt_shorter_cadence_admissions'),
  'N06':('NOT_IMPLEMENTED','','','No causal clipping/level-transition state freezes prototype updates. Gain/RMS experiments are distinct controls, not a substitute implementation. Deferred separate clipping detector/recovery policy; no dominance evidence claimed.',''),
  'N07':('IMPLEMENTED','B01,B15','M29','Scheduler limits reconciliation age and count per utterance, preserving first state. Exhausted/over-age reconciliation is skipped and retains the latest label; unlike the seed, it does not force unresolved attribution to Unknown. Ongoing display changes are outside the count. Tracker retained nodes alone would not implement this idea.','transcript_reconciliation,label_revision'),
  'N08':('NOT_IMPLEMENTED','','','No independently maintained committed audio-only shadow prototype/gallery. Cue-off parity from initial state and rollback checkpoints do not recover an uncontaminated parallel voice history. Additional shadow-association ownership not implemented; no duplicate/dominated claim.',''),
 }
 nrows=[]
 for nid,(status,pids,mid,limit,signals) in ni.items():
  pids=pids.split(',') if pids else [];a=profile_activity(audit,pids);sig={k:a['counts'].get(k,0) for k in signals.split(',')} if signals and a['observed_profiles'] else None
  state='NOT_APPLICABLE_NOT_IMPLEMENTED' if status=='NOT_IMPLEMENTED' else 'PENDING_COMPONENT_RECIPE_AUDIT' if not a['observed_profiles'] else 'OBSERVED_ACTIVITY' if sig and any(sig.values()) else 'NO_OBSERVED_LISTED_ACTIVITY'
  nrows.append(dict(idea_id=nid,title=ideas[nid]['title'],seed_state_change=ideas[nid]['equation_or_state_change'],implementation_status=status,mechanism_id=mid,profiles=pids,
   code_fixture_status='NOT_APPLICABLE' if status=='NOT_IMPLEMENTED' else 'FOCUSED_CHECKS_PASS; see linked receipts for scope',bank_activity_status=state,
   observed_profiles=a['observed_profiles'],pending_profiles=sorted(set(pids)-set(a['observed_profiles'])),audited_outputs=a['outputs'],activity_signals=sig,
   benefit_status='NOT_ESTABLISHED_BY_THIS_COVERAGE_MAP',implemented_scope_or_rejection_reason=limit))
 if sum(n['implementation_status']=='IMPLEMENTED' for n in nrows)<4:raise ValueError('Fewer than four complete N-idea implementations')
 out=args.output;out.mkdir(parents=True,exist_ok=True)
 source_identity={str(v['path']):v['sha256'] for v in sources}
 if (out/'COVERAGE_RECEIPT.json').exists() and read(out/'COVERAGE_RECEIPT.json')['source_identity']!=source_identity:raise ValueError('Use a new output namespace for changed inputs/code')
 csv_write(out/'METHOD_FAMILY_COVERAGE.csv',rows);csv_write(out/'MATCHED_INTERACTION_TABLE.csv',contrast_rows);csv_write(out/'N01_N08_IMPLEMENTATION_STATUS.csv',nrows)
 save(out/'RESIDENT_REUSE_EVIDENCE.json',reuse)
 summary=dict(schema='jp_s6b_executed_family_coverage_v1',status='PASS',created_utc=datetime.now(timezone.utc).isoformat(),
  audit_population_outputs=audit['audited_prediction_or_canonical_outputs'],audit_population_complete=audit['index_population_complete'],
  covered_required_families=len(FAMILIES),reviewed_distinct_research_mechanisms=sum(m['counted_distinct_mechanism'] for m in MECHANISMS),
  controls_excluded_from_mechanism_count=['M01','M03'],families=[dict(family_id=f,family=name,mechanisms=[r['mechanism_id'] for r in rows if r['family_id']==f],
   pending_profiles=sorted({p for r in rows if r['family_id']==f for p in r['pending_profiles']})) for f,name in FAMILIES.items()],
  exact_N_ideas_implemented=[n['idea_id'] for n in nrows if n['implementation_status']=='IMPLEMENTED'],
  adapted_N_ideas=[n['idea_id'] for n in nrows if n['implementation_status']=='IMPLEMENTED_ADAPTATION'],not_implemented_N_ideas=[n['idea_id'] for n in nrows if n['implementation_status']=='NOT_IMPLEMENTED'],
  expected_challenge_outputs_per_profile=expected_outputs,contrast_count=len(contrast_rows),source_bindings=sources,
  all_registered_profiles_mapped=sorted(registry),registered_profile_count=len(registry),
  resident_reuse_evidence=binding(out/'RESIDENT_REUSE_EVIDENCE.json'),
  full_bank_R0_feature_parity={k:r0_proof[k] for k in ('status','outputs','features','same_spans_outputs','bit_exact_vector_outputs','legacy_label_equal_outputs','legacy_label_differences','maximum_absolute_vector_difference','interpretation')},
  scope='Implementation map + actual frozen-APP event audit. No inference, fitted thresholds, ranking, benefit, equal-work or external generalization claims.',
  absent_extensions=['structural track merge/split','split ASR/embedding audio route','N02 cue-driven segmentation refresh','N05 per-track unique-deficit queue','N06 clipping transition freeze','N08 independent clean shadow prototype'])
 save(out/'FAMILY_COVERAGE_SUMMARY.json',summary)
 text=(f'# Executed family coverage\n\nThe selected audit contains {summary["audit_population_outputs"]:,} actual comparison outputs. All eight required families have reviewed executable implementations. The map identifies {summary["reviewed_distinct_research_mechanisms"]} distinct research mechanisms, excluding two control rows; it does not count profile aliases or fixture parsing as experimental results.\n\n'
  'METHOD_FAMILY_COVERAGE.csv records executable entry points, fixture scope, actual activity, pending profile populations and limits. MATCHED_INTERACTION_TABLE.csv contains exact effective-field differences, including prepared input gain, and exposes bundled interventions. N01_N08_IMPLEMENTATION_STATUS.csv distinguishes four complete ideas (N01/N03/N04/N07), the narrower N05 adaptation and three absent proposals.\n\n'
   'The selected population and any pending component recipes are explicit in each CSV row. Zero rollback/recovery is retained when it did not occur; code checks do not turn that into successful empirical recovery. Native job counts are deduplicated within each mechanism row, but rows overlap and must not be summed as distinct neural runs. Historical B00 internals are not instrumented.\n\n'
  'B24/B25 bundles cue-driven cadence with cue-driven association. B22/B28 bundles endpoint restoration with decoder search. Sparse/frequent/event comparisons report actual work and are not automatically equal-budget. The 0.5/1s duration x1/2-disjoint-count diagnostic holds0.25s cadence and1s unique evidence fixed. Segmentation policy/stride/purity is a fractional design with explicit matched edges.\n\n'
  'No benefit is inferred here. Read score, short-turn, wrong-merge/Unknown, return, latency and resource outcomes together. Full-bank shortlist and real-human/CM5 qualification are separate evidence boundaries. Rebuild under a new output namespace when the full prediction audit is available; exact commands are in README_S6B_FAMILY_COVERAGE.md.\n')
 text+='\nThe separate newly executed R0 proof covers480 outputs and15,649 vectors: all source spans and legacy anonymous labels match;10/480 vector arrays are bit-exact, with maximum absolute difference1.7136335372924805e-6. This is distinct from the64-output semantic pilot and fixed-input legacy tracker tests. B00/B36 transcript attribution can still differ through scheduler and expiry rules.\n'
 (out/'FAMILY_COVERAGE_HANDOFF.md').write_text(text,encoding='utf-8')
 artifacts=[binding(out/name) for name in ('METHOD_FAMILY_COVERAGE.csv','MATCHED_INTERACTION_TABLE.csv','N01_N08_IMPLEMENTATION_STATUS.csv','RESIDENT_REUSE_EVIDENCE.json','FAMILY_COVERAGE_SUMMARY.json','FAMILY_COVERAGE_HANDOFF.md')]
 save(out/'COVERAGE_RECEIPT.json',dict(status='PASS',source_identity=source_identity,artifacts=artifacts,builder_checks=check(),neural_calls=0,hardware_invocations=0))
 return dict(status='PASS',families=8,mechanisms=summary['reviewed_distinct_research_mechanisms'],N_complete=summary['exact_N_ideas_implemented'],outputs=summary['audit_population_outputs'],output=str(out))


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('check','build'));p.add_argument('--report',type=Path,default=REPORT)
 p.add_argument('--audit',type=Path,default=REPORT/'mechanisms/CHALLENGE_MECHANISM_AUDIT_FINAL.json');p.add_argument('--output',type=Path,default=REPORT/'coverage/challenge_final_v1')
 args=p.parse_args();print(json.dumps(check() if args.mode=='check' else build(args),indent=2))
if __name__=='__main__':main()
