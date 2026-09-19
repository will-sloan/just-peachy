"""One-event external closure admission; README_S6C_CONTROLS_RECOVERY_INVENTORY_V1.md."""
from __future__ import annotations
import argparse,hashlib,importlib,json,types
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
V7_SHA='fc23ff6650a34c927211d142e61b9dcf7afe7ee07e832c51573ae2da0dc3c7a3'
AUDIT=REPORT/'runtime_failure_review/CONTROLS_FAST_V1_ARCHIVE_FAILURE_OWNER_AUDIT_V1.json'
AUDIT_SHA='74a60af5483852cae05ac156c7c251a4890b684d737e080b22be01080c2ea914'
MANIFEST_SHA='8fb281fe4788e549cfb294bdcfb6adf326144cfeefbb1d09c76cf22f7b26c044'
SCANNER_SHA='99cb60a62e8bdbfc2b2e9666fa368604395b4f3e0837cf56e20535efa7614591'
LEASE_SHA='9dfcfa166cecad8b4edfaf1b64f867f3485de18c8d7a8cf7c9cb8e6563ca44f3'
RELEASE_SHA='079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67'
RECOVERY_SHA='750e96751662d6da33309004a131984f14d6893e0f70e8ca73d8dc6b5265d66d'
RECOVERY_README_SHA='173468aa9df79fbbf2a3b28877aeb1ffe4053c21e244b16598c227ee0db74fea'
ERROR="OSError(18, 'The system cannot move the file to a different disk drive')"

def require(v,m):
 if not v:raise ValueError(m)

def binding(path):
 p=Path(path).resolve();require(p.stat().st_size<=2**20,'Bounded source/metadata only');raw=p.read_bytes();require(len(raw)<=2**20,'Input grew beyond cap')
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def load_v7():
 require(binding(HERE/'s6c_execution_inventory_v7.py')['sha256']==V7_SHA,'Held V7 changed')
 v=importlib.import_module('s6c_execution_inventory_v7');require(Path(v.__file__).resolve()==HERE/'s6c_execution_inventory_v7.py','V7 import origin');v.verify_sources();return v

def clone(fn,ns):
 f=types.FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__);f.__kwdefaults__=fn.__kwdefaults__;return f

def owner_key(v,o):
 v.v4.owner(o);return o['pid'],o['creation_time']

def closed_set(v,rows,expected):
 require(len(rows)==len(expected)==162,'Exactly162 original owner observations')
 require(Counter(owner_key(v,r['owner']) for r in rows)==Counter(owner_key(v,o) for o in expected),'Exact original owner set')
 require(all(r['observation']==dict(alive=False,error=None) for r in rows),'Recovery owner observations unresolved')

def validate_result_documents(v,result,rb,admission,ab,authority,audit,ap,lease,dispatch):
 """Pure cross-document guards; original bound audit is the finite authority."""
 require(result['schema']=='s6c-external-historical-lease-recovery.v1' and result['status']=='EXTERNAL_ARCHIVE_RELEASED','Successful explicit external recovery required')
 require(Path(rb['path']).parent==REPORT/'runtime_failure_review/external_lease_recovery'/authority['namespace'] and Path(rb['path']).name=='RESULT.json','Exact recovery result namespace')
 require(result['admission']==ab and Path(ab['path'])==Path(rb['path']).with_name('ADMISSION.json'),'Recovery admission link')
 require(admission['schema']=='s6c-external-lease-recovery-admission.v1' and admission['status']=='EXACT_OWNER_BOUND_RECOVERY_ADMITTED','Recovery admission status')
 require(authority['schema']=='s6c-external-historical-lease-release-authority.v1' and authority['status']=='AUTHORIZED_EXACT_EXTERNAL_LEASE_ARCHIVE','Root recovery authority')
 require(result['authority']==admission['authority'] and result['root_audit']==admission['root_audit']==authority['root_audit']==ap,'Root audit/authority chain')
 require(ap['sha256']==AUDIT_SHA and Path(ap['path'])==AUDIT,'One exact root audit only')
 require(result['manifest']==audit['manifest'] and result['manifest']['sha256']==MANIFEST_SHA,'Only exact controls80 manifest')
 require(result['original_launch']==audit['launch'] and result['original_completion']==audit['completion'] and result['original_dispatcher_failure']==audit['failed_dispatcher'],'Original failed invocation links')
 require(result['failed_observer']==admission['failed_observer'] and result['failed_observer']['sha256']==SCANNER_SHA,'Original failed observer retained')
 require(result['original_coordinator_exit_code']==1 and result['original_scanner_status']=='FAILED' and result['original_archive_created'] is False,'Original failure cannot become successful coordinator closure')
 require(result['models_started']==result['native_sessions_started']==0,'Housekeeping adds no native work')
 require(result['original_missing_archive']==admission['original_missing_archive']==audit['expected_archive'],'Original missing archive path')
 require(admission['source']==authority['helper'] and admission['source']['sha256']==RECOVERY_SHA and Path(admission['source']['path'])==HERE/'s6c_external_lease_recovery_v1.py','Exact reviewed recovery helper')
 require(admission['readme']==authority['readme'] and admission['readme']['sha256']==RECOVERY_README_SHA,'Exact reviewed recovery README')
 require(admission['release_source']['sha256']==RELEASE_SHA and Path(admission['release_source']['path'])==HERE/'s6c_long_native_epoch4_fast_v2.py','Exact original release function source')
 require(owner_key(v,result['owner'])==owner_key(v,admission['owner']),'Recovery owner differs')
 start=datetime.fromisoformat(admission['created_utc']);end=datetime.fromisoformat(result['created_utc']);expiry=datetime.fromisoformat(authority['expires_utc'].replace('Z','+00:00'))
 require(start.tzinfo is not None and end.tzinfo is not None and expiry.tzinfo is not None and start<=end and start<expiry,'Recovery admission time/authority differs')
 release=result['lease_release'];archive=release['archived_binding'];original=audit['preserved_active_lease']
 require(release['status']=='RELEASED' and release['released'] is True and release['error'] is None,'Verified released archive only')
 require(release['source']==admission['lease']==original and original['sha256']==LEASE_SHA,'Original lease binding')
 require(archive['sha256']==original['sha256'] and archive['bytes']==original['bytes']==258,'Original exact lease bytes preserved')
 require(Path(archive['path'])==Path(rb['path']).with_name('PRESERVED_ORIGINAL_QUIET_LEASE.json') and release['requested_archive']==admission['requested_archive']==archive['path'],'Same recovery namespace archive')
 require(Path(archive['path']).drive.casefold()==Path(original['path']).drive.casefold(),'Same-volume archive declaration')
 require(lease['manifest']==audit['manifest'] and owner_key(v,lease)==owner_key(v,audit['original_owner']),'Archived original owner/manifest differs')
 expected=[audit['original_owner'],dispatch['owner']]+[x['owner'] for row in audit['rows'] for x in row['owners']]
 closed_set(v,result['current_original_owner_observations'],expected);closed_set(v,admission['original_owners'],expected)
 return expected

def admit_recovery(v,reader,rb):
 require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active/preserved quiet lease blocks recovered admission')
 def read(b):return v.bound(reader,b)[0]
 result=read(rb);admission=read(result['admission']);authority=read(result['authority']);audit=read(result['root_audit']);dispatch=read(audit['failed_dispatcher'])
 lease=read(result['lease_release']['archived_binding'])
 expected=validate_result_documents(v,result,rb,admission,result['admission'],authority,audit,result['root_audit'],lease,dispatch)
 for b in (admission['source'],admission['readme'],admission['release_source']):require(binding(b['path'])==b,'Held recovery source binding changed')
 require(not Path(audit['expected_archive']).exists(),'Original G archive must remain absent')
 require(audit['schema']=='s6c-historical-archive-failure-owner-audit.v1' and audit['status']=='COMPLETE_GRID_AND_OWNERS_CLOSED_ARCHIVE_FAILED' and audit['completed_cells']==audit['requested']==80,'Original complete80 audit')
 plan,pb,spec=v.admit_plan(reader,audit['manifest']);require(v.kind_of(plan)=='controls' and len(plan['jobs'])==80,'Original controls grid')
 launch=read(audit['launch']);completion=read(audit['completion']);quiet=read(audit['quiet_admission']);scanner=read(result['failed_observer'])
 require(launch['manifest']==completion['manifest']==pb and launch['quiet_admission']==audit['quiet_admission'] and quiet['manifest_sha256']==pb['sha256'],'Original launch/quiet chain')
 require(owner_key(v,launch)==owner_key(v,audit['original_owner']),'Original coordinator')
 require(completion['status']=='COMPLETE' and completion['completed']==completion['requested']==80 and completion['error'] is None,'Original producer completion80')
 require(dispatch['status']=='STOPPED_REQUIRES_ROOT_REVIEW' and dispatch['active_item']=='controls_fast_v1' and dispatch['child_returncode']==1 and dispatch['error'] and owner_key(v,dispatch['possible_child'])==owner_key(v,launch),'Original failed dispatcher preserved')
 obs,ob=v.observer_exit(reader,plan,pb,audit['original_owner'],'run')
 require(obs==scanner and ob==result['failed_observer'] and obs['status']=='FAILED' and obs['error']==ERROR,'Only exact cross-volume final archive failure')
 _,argv=v.command_fields(obs['owner']['argv'],v.FAST['controls']['wrapper']);require(v.base.canonical(argv['--quiet-admission'])==v.base.canonical(audit['quiet_admission']['path']),'Original observer quiet command')
 jobs={j['job_id']:j for j in plan['jobs']};rows={r['job_id']:r for r in audit['rows']};require(len(jobs)==len(rows)==len(audit['rows'])==80 and jobs.keys()==rows.keys(),'Exact audited80 keys')
 for key,r in rows.items():
  cell=read(r['completion']);require(Path(r['completion']['path'])==Path(plan['output_root'])/'jobs'/key/'COMPLETE.json','Exact audited completion location')
  require(cell['status']=='COMPLETE' and cell['job_key']==jobs[key]['job_key'] and cell['all_owned_processes_closed'] is True,'Original cell completion')
  require([owner_key(v,o) for o in cell['owned_processes']]==[owner_key(v,x['owner']) for x in r['owners']],'Original cell owner set')
 owners=[dict(branch='EXTERNAL_RECOVERY_CURRENT_ORIGINAL_OWNER',pid=o['pid'],creation_time=o['creation_time'],process_state=v.process_state(o['pid'],o['creation_time']),source=rb) for o in expected]
 owner_key(v,result['owner']);owners.append(dict(branch='EXTERNAL_RECOVERY_HOUSEKEEPING_OWNER',pid=result['owner']['pid'],creation_time=result['owner']['creation_time'],process_state=v.process_state(result['owner']['pid'],result['owner']['creation_time']),source=rb))
 require(all(o['process_state']['alive'] is False for o in owners),'Original owner currently live/unverified')
 context=dict(result=result,binding=rb,audit=audit,plan=plan,manifest=pb,spec=spec,rows=rows,owners=owners)
 reader.controls_recovery_context=context;return context

def make_inventory(recovery_binding):
 """Private V7 namespace. No file/lease mutation; unrelated branches delegate."""
 v=load_v7();api=types.SimpleNamespace(**vars(v));rb=deepcopy(recovery_binding)
 def source_bindings():return v.source_bindings()+[binding(__file__),binding(HERE/'README_S6C_CONTROLS_RECOVERY_INVENTORY_V1.md'),rb]
 def attach(reader,b):
  result=v.admit_observer_index(reader,b);admit_recovery(v,reader,rb);return result
 def context(reader,plan,pb):
  require(hasattr(reader,'controls_recovery_context'),'Explicit recovered Reader context required');c=reader.controls_recovery_context
  require(c['binding']==rb and c['manifest']==pb and c['plan']==plan,'Recovered context/manifest differs')
  require(not (REPORT/'PACED_QUIET_OWNER.json').exists() and not Path(c['audit']['expected_archive']).exists(),'Unexpected quiet lease/original archive')
  return c
 def target(pb):return pb['sha256']==MANIFEST_SHA
 def invocation_rows(reader,plan,pb,*,observer_receipts=None):
  if not target(pb):return v.invocation_rows(reader,plan,pb,observer_receipts=observer_receipts)
  if observer_receipts is not None:v.attach_observer_receipts(reader,observer_receipts);admit_recovery(v,reader,rb)
  c=context(reader,plan,pb);records,owners=v.historical_api().invocation_rows(reader,plan,pb)
  require(len(records)==1 and records[0]['launch']==c['audit']['launch'] and records[0]['outcome']==c['audit']['completion'] and records[0]['closure'] is None,'One exact original failed-archive invocation only')
  r=records[0];r.update(original_closure=None,closure=c['result']['lease_release']['archived_binding'],closure_kind='EXTERNAL_ROOT_RECOVERY_EXACT_ORIGINAL_LEASE',external_recovery=rb,original_coordinator_exit_code=1,original_scanner_status='FAILED',observer_exit=c['result']['failed_observer'],observer_error=ERROR)
  # COMPLETE is the original producer's80-cell status, never an exit0 claim.
  require(r['status']=='COMPLETE' and r['reported_completed']==80,'Original complete producer required')
  # All162 were freshly checked when this Reader attached the recovery. Each
  # actual cell additionally checks its own native identities below. Recheck
  # the two original parents and recovery process at every invocation gate.
  current=c['owners'][:2]+c['owners'][-1:]
  require(all(v.process_state(o['pid'],o['creation_time'])['alive'] is False for o in owners+current),'Current recovered parent closure')
  owners+=deepcopy(c['owners'])
  return records,owners
 def collect_job(reader,job,plan,pb,spec,*,observer_receipts=None):
  if not target(pb):return v.collect_job(reader,job,plan,pb,spec,observer_receipts=observer_receipts)
  records,owners=invocation_rows(reader,plan,pb,observer_receipts=observer_receipts);v.ensure_invocations_closed(records,owners);c=context(reader,plan,pb)
  require(job in plan['jobs'] and job['job_id'] in c['rows'],'Only exact audited cells')
  row=v.historical_api().collect_job(reader,job,plan,pb,spec)
  require(row is not None and row['status']=='COMPLETE' and row['native_session_complete'] is True,'Actual historical native cell complete')
  require(all(v.process_state(o['pid'],o['creation_time'])['alive'] is False for o in row['recorded_owned_processes']),'Recorded native owner closure')
  require(c['rows'][job['job_id']]['completion'] in row['receipt_bindings'],'Exact original cell receipt retained')
  row['observer_admission']=dict(invocations=records,external_recovery=rb,original_observer_status='FAILED',original_coordinator_exit_code=1)
  row['closure_scope']='Actual native cell complete; original coordinator failed final C-to-G lease rename. Exact original lease externally archived under root authority; original failure remains bound.'
  return row
 def collect_paced_job(reader,job,plan,pb,spec):return collect_job(reader,job,plan,pb,spec)
 api.source_bindings=source_bindings;api.admit_observer_index=attach;api.invocation_rows=invocation_rows;api.collect_job=collect_job;api.collect_paced_job=collect_paced_job
 # Same original collect code, with only these metadata callbacks in private globals.
 ns={**v.collect.__globals__,**vars(api)};api.collect=clone(v.collect,ns)
 api.recovery_binding=rb;api.admit_recovery=lambda reader:admit_recovery(v,reader,rb)
 return api

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['admit']);p.add_argument('--recovery',nargs=2,required=True);p.add_argument('--observer-index',nargs=2,required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 v=load_v7();require(__import__('re').fullmatch(r'[A-Za-z0-9_-]{1,64}',a.namespace or ''),'Simple fresh namespace')
 out=REPORT/'runtime_failure_review/recovered_inventory_admission'/a.namespace;require(not out.exists(),'Preserve prior admission');out.mkdir(parents=True)
 reader=v.base.MetadataReader(out)
 def supplied(pair):
  _,b=reader.read(Path(pair[0]));require(b['sha256']==pair[1],'Explicit input SHA');return b
 rb=supplied(a.recovery);api=make_inventory(rb);api.admit_observer_index(reader,supplied(a.observer_index));c=reader.controls_recovery_context
 records,owners=api.invocation_rows(reader,c['plan'],c['manifest']);rows=[api.collect_job(reader,j,c['plan'],c['manifest'],c['spec']) for j in c['plan']['jobs']]
 result=dict(status='ADMITTED_COMPLETE_CELLS_EXTERNAL_ARCHIVE_ORIGINAL_COORDINATOR_FAILED',schema='s6c-controls-external-recovery-admission.v1',recovery=rb,manifest=c['manifest'],native_cells=len(rows),physical_counts_scope='One existing physical row per audited cell, no added native execution from recovery.',status_counts=dict(Counter(r['status'] for r in rows)),invocations=records,current_owner_observations=owners,sources=api.source_bindings(),metadata_sources=reader.sources,models=0)
 print(json.dumps(v.base.write_new(out/'RESULT.json',result),indent=2))

if __name__=='__main__':main()
