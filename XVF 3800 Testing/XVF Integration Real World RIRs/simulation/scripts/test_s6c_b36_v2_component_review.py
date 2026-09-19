"""Independent source/closure checks; README_S6C_B36_V2_COMPONENT_REVIEW.md."""
from __future__ import annotations
import argparse,copy,hashlib,json,tempfile,types
from pathlib import Path
from unittest.mock import patch
import s6c_paced_b36_fast_v2 as B
import test_s6c_paced_b36_fast_v2 as T

def run(output,source_checks):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
 raw=Path(source_checks[0]).read_bytes();assert hashlib.sha256(raw).hexdigest()==source_checks[1];original=json.loads(raw)
 for b in original['sources']:
  if Path(b['path']).name in (Path(B.__file__).name,Path(T.__file__).name,'README_S6C_PACED_B36_FAST_V2.md'):assert B.F.bind(b['path'])==b
 reproduced=T.run(output/'reproduced');assert json.loads(Path(reproduced['path']).read_bytes())['checks']==original['checks']
 checks=[]
 def ok(n,v):assert v,n;checks.append(n)
 def bad(n,f):
  try:f()
  except (ValueError,KeyError,TypeError,OSError):checks.append(n);return
  raise AssertionError(n)
 c=B.context();api=c.adapt('b36');old=B.F.adapt('b36')
 ok('native_worker_driver_stays_original',api.run.__globals__['_original'].__file__==old.run.__globals__['_original'].__file__)
 prior,pb=B.F.read_bound(B.PARENT);original_plan,ob=B.F.read_bound(prior['original_prepared_manifest']['path'],prior['original_prepared_manifest'])
 projected=c.projection('b36',original_plan,ob,'review_fast_v2','2026-09-12T00:00:00Z')
 ok('forty_exact_original_jobs',projected['jobs']==prior['jobs'] and len(projected['jobs'])==40)
 ok('actual_B36_both_taps_only',{j['profile_id'] for j in projected['jobs']}=={'B36'} and {j['stream'] for j in projected['jobs']}=={'O0','O1'})
 ok('sixteen_cases_four_repeats',len({j['case_id'] for j in projected['jobs']})==16 and sum(j['repetition']==2 for j in projected['jobs'])==8)
 with tempfile.TemporaryDirectory(prefix='s6c_b36_independent_closure_') as tmp:
  root=Path(tmp).resolve();report=root/'report';payload=root/'payload'
  with patch.object(B,'REPORT',report),patch.object(B,'PAYLOAD',payload):
   croot,out=B.roots('b36','review_fast_v2');inv=out/'invocations/one';inv.mkdir(parents=True);report.mkdir()
   jobs=[dict(job_id=str(i),job_key=str(i)) for i in range(40)];plan=dict(output_root=str(out),jobs=jobs,driver={},lease_archival_policy=B.archival_policy())
   mb=B.F.save(out/'MANIFEST.json',plan);qb=B.F.save(root/'quiet.json',dict(status='AUTHORIZED_FOR_QUIET_PACED',manifest_sha256=mb['sha256'],all_other_model_hil_work_stopped=True,all_heavy_analysis_stopped=True))
   argv=[str(B.R.EDGE),'-B',str(Path(B.__file__).resolve()),'run','--manifest',mb['path'],'--quiet-admission',qb['path']];owner=dict(pid=777,creation_time=777.,argv=argv)
   B.F.save(inv/'LAUNCH.json',dict(status='STARTED',pid=777,creation_time=777.,manifest=mb,coordinator=B.F.bind(B.__file__),native_driver={},quiet_admission=qb))
   B.F.save(inv/'COMPLETION.json',dict(status='COMPLETE',completed=40,requested=40,error=None,manifest=mb))
   for j in jobs:B.F.save(out/'jobs'/j['job_id']/'COMPLETE.json',dict(status='COMPLETE',job_key=j['job_key'],all_owned_processes_closed=True,owned_processes=[dict(pid=1000+int(j['job_id']),creation_time=1000.+int(j['job_id']))]))
   lock=report/'PACED_QUIET_OWNER.json';B.F.save(lock,dict(pid=777,creation_time=777.,manifest=mb))
   with patch.object(B.R,'all_closed',lambda owners:[dict(owner=o,observation=dict(alive=False,error=None)) for o in owners]):
    B.archive_finished_lease(lock,inv,plan,types.SimpleNamespace(manifest=Path(mb['path']),quiet_admission=Path(qb['path'])),types.SimpleNamespace(pid=777,create_time=lambda:777.,cmdline=lambda:argv))
   source=c.source_bindings('b36')
   # Actual three-root scope is taken from the helper's source-bound constants.
   scan=dict(schema='s6c-historical-fast-observer-outcome.v1',status='COMPLETE',error=None,coordinator_pid=777,manifest=mb,entry='run',owner=owner,wrapper=B.F.bind(B.__file__),sources_before=source,sources_after=source,sources_unchanged=True)
   roots=[B.REPORT,B.STAGING,B.PAYLOAD]
   scan['storage_scans']={str(Path(p).resolve()):dict(calls=1,successful=1,failed=0,total_wall_sec=.1,total_cpu_sec=.05,max_wall_sec=.1,last_bytes=0,last_error=None) for p in roots}
   sp=croot/'observer_invocations/one/SCANNER_OUTCOME.json';B.F.save(sp,scan)
   rp=croot/'invocations/one/LEASE_RELEASE.json';release=json.loads(rp.read_bytes());closed=lambda o:dict(alive=False,error=None)
   with patch.object(B,'admit_plan',return_value=(plan,mb)):
    proof=B.admit_complete_batch(B.F.Reader(),mb,inspect=closed);ok('actual_C_archive_chain_fixture',proof['cells']==40 and not lock.exists() and not (inv/'QUIET_OWNER_CLOSED.json').exists())
    faults=[('wrong_original_completion',lambda d:d.update(original_completion={})),('wrong_release_owner',lambda d:d['owner'].update(creation_time=1.)),('unverified_archive',lambda d:d['lease_release'].update(status='RELEASED_BINDING_UNVERIFIED')),('changed_archive_hash',lambda d:d['lease_release']['archived_binding'].update(sha256='bad')),('missing_cell_reference',lambda d:d['completed_cells'].pop()),('missing_child_observation',lambda d:d['current_child_observations'].pop())]
    for name,mutation in faults:
     value=copy.deepcopy(release);mutation(value);rp.write_text(json.dumps(value));bad(name,lambda:B.admit_complete_batch(B.F.Reader(),mb,inspect=closed));rp.write_text(json.dumps(release))
    bad('current_child_access_denied',lambda:B.admit_complete_batch(B.F.Reader(),mb,inspect=lambda o:dict(alive=False,error='denied') if o['pid']>=1000 else closed(o)))
    quiet=json.loads(Path(qb['path']).read_bytes());Path(qb['path']).write_text(json.dumps(dict(quiet,manifest_sha256='wrong')));bad('quiet_buffer_changed',lambda:B.admit_complete_batch(B.F.Reader(),mb,inspect=closed))
 return B.F.save(output/'REVIEW_RECEIPT.json',dict(status='PASS_SOURCE_METADATA_PRIVATE_CLOSURE',original_checks=original['checks'],independent_checks=len(checks),names=checks,reproduced=reproduced,reviewed_source_checks=dict(path=str(Path(source_checks[0]).resolve()),bytes=len(raw),sha256=source_checks[1]),sources=[B.F.bind(B.__file__),B.F.bind(B.HERE/'README_S6C_PACED_B36_FAST_V2.md'),B.F.bind(__file__),B.F.bind(B.HERE/'README_S6C_B36_V2_COMPONENT_REVIEW.md')],actual_preparation=False,actual_native=False,scope='Full source/README and exact prior40-job metadata; finite private release/closure fixtures only. No real lease, native-cell payload, PCM/model read or launch. Batch closure proof remains separate from full native/scientific admission.'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-checks',nargs=2,required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(run(a.output,a.source_checks),indent=2))
