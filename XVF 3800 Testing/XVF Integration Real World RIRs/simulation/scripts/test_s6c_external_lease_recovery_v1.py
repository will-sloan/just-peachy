"""Private recovery guards; README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md."""
import argparse,ast,copy,json,tempfile,traceback,types
from pathlib import Path
from unittest.mock import patch
import s6c_external_lease_recovery_v1 as R

def fixture(root):
 manifest_binding=dict(path=str(root/'MANIFEST.json'),bytes=2,sha256='a'*64)
 quiet_binding=dict(path=str(root/'quiet.json'),bytes=2,sha256='b'*64)
 main=dict(pid=101,creation_time=1.,argv=['exact','original'])
 dispatcher=dict(pid=102,creation_time=2.)
 jobs=[dict(job_id=f'j{i}',job_key=f'key{i}') for i in range(80)]
 rows=[dict(job_id=j['job_id'],completion=dict(path=str(root/'jobs'/j['job_id']/'COMPLETE.json'),bytes=2,sha256='c'*64),owners=[dict(owner=dict(pid=1000+i*2+k,creation_time=3.+i*2+k),observation=dict(alive=False,error=None)) for k in range(2)]) for i,j in enumerate(jobs)]
 audit=dict(schema='s6c-historical-archive-failure-owner-audit.v1',status='COMPLETE_GRID_AND_OWNERS_CLOSED_ARCHIVE_FAILED',requested=80,completed_cells=80,owned_observations=160,archival_performed=False,lease_removed=False,manifest=manifest_binding,quiet_admission=quiet_binding,original_owner=main,rows=rows,owner_observation=dict(alive=False,error=None),dispatcher_observation=dict(alive=False,error=None))
 manifest=dict(jobs=jobs,output_root=str(root));launch=dict(**main,manifest=manifest_binding,quiet_admission=quiet_binding);completion=dict(status='COMPLETE',completed=80,requested=80,error=None,manifest=manifest_binding)
 lease=dict(pid=101,creation_time=1.,manifest=manifest_binding);quiet=dict(manifest_sha256=manifest_binding['sha256'])
 dispatch=dict(status='STOPPED_REQUIRES_ROOT_REVIEW',active_item='controls_fast_v1',child_returncode=1,error='preserved archival failure',possible_child=main,owner=dispatcher)
 scanner=dict(status='FAILED',error="OSError(18, 'The system cannot move the file to a different disk drive')",sources_unchanged=True,manifest=manifest_binding,owner=main)
 return [audit,manifest,launch,completion,lease,quiet,dispatch,scanner]

def run(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=False);checks=[]
 def ck(n,v=True):
  if not v:raise AssertionError(n)
  checks.append(n)
 def bad(n,fn,kind=ValueError):
  try:fn()
  except kind:ck(n)
  else:raise AssertionError(n)
 release=R.release_function()
 raw=R.RELEASE_SOURCE.read_bytes();node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='release_lease')
 ns=dict(Path=Path,verify=R.verify,read_bound=R.read_bound,traceback=traceback)
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(R.RELEASE_SOURCE),'exec'),ns)
 ck('exact_reviewed_release_code',release.__code__.co_code==ns['release_lease'].__code__.co_code and release.__code__.co_consts==ns['release_lease'].__code__.co_consts)
 with tempfile.TemporaryDirectory(prefix='s6c_external_lease_fixture_') as tmp:
  root=Path(tmp).resolve();values=fixture(root);jobs,owners=R.validate_chain(*values);ck('exact80_grid_162finiteowners',len(jobs)==80 and len(owners)==162)
  faults=[
   ('incomplete_count',lambda v:v[3].update(completed=79)),
   ('native_error',lambda v:v[3].update(error='error')),
   ('wrong_manifest',lambda v:v[4].update(manifest={})),
   ('wrong_lease_owner',lambda v:v[4].update(creation_time=99.)),
   ('wrong_quiet',lambda v:v[5].update(manifest_sha256='wrong')),
   ('wrong_failure',lambda v:v[7].update(error='different failure')),
   ('forged_scanner_success',lambda v:v[7].update(status='COMPLETE')),
   ('changed_observer_sources',lambda v:v[7].update(sources_unchanged=False)),
   ('missing_original_failure',lambda v:v[6].update(child_returncode=0)),
   ('duplicate_grid',lambda v:v[0]['rows'].__setitem__(1,copy.deepcopy(v[0]['rows'][0]))),
   ('missing_child_observation',lambda v:v[0]['rows'][0]['owners'].pop()),
   ('unverified_past_owner',lambda v:v[0]['rows'][0]['owners'][0].update(observation=dict(alive=None,error='unavailable')))]
  for name,mutate in faults:
   v=copy.deepcopy(values);mutate(v);bad(name,lambda v=v:R.validate_chain(*v))
  ck('fresh_closed_owner_observations',len(R.all_closed(owners,lambda o:dict(alive=False,error=None)))==162)
  for alive in (True,None):bad('reject_fresh_owner_'+str(alive),lambda alive=alive:R.all_closed(owners,lambda o:dict(alive=alive,error=None)))
  bad('reject_inspection_error',lambda:R.all_closed(owners,lambda o:dict(alive=False,error='denied')))
  for owner in (dict(pid=True,creation_time=1.),dict(pid=1,creation_time=float('nan')),dict(pid=0,creation_time=1.)):bad('reject_invalid_owner_'+repr(owner),lambda owner=owner:R.finite_owner(owner))
  lock=root/'PACED_QUIET_OWNER.json';archive=root/'external_archive.json';original_g=root/'not_written_original_G_archive.json'
  expected=R.save(lock,values[4]);R.same_volume(lock,archive);r=release(lock,archive,expected)
  ck('private_same_volume_exact_byte_release',r['status']=='RELEASED' and r['released'] is True and r['error'] is None and not lock.exists() and r['archived_binding']==R.bind(archive) and not original_g.exists())
  expected=R.save(lock,values[4]);bad('archive_collision',lambda:R.same_volume(lock,archive))
  second=root/'another_archive.json';r=release(lock,second,dict(expected,sha256='0'*64));ck('wrong_lease_bytes_retained',r['status']=='RELEASE_FAILED' and not r['released'] and lock.exists() and not second.exists())
  with patch.object(Path,'rename',side_effect=OSError(18,'cross-device synthetic')):
   r=release(lock,second,expected)
  ck('rename_failure_preserves_lease',r['status']=='RELEASE_FAILED' and not r['released'] and lock.exists() and not second.exists())
  original_stat=Path.stat
  def devices(p,*a,**k):
   value=original_stat(p,*a,**k)
   if p==lock:return types.SimpleNamespace(st_dev=value.st_dev+1)
   return value
  with patch.object(Path,'stat',devices):
   bad('cross_device_rejected_before_rename',lambda:R.same_volume(lock,second))
  ck('still_exact_original_lease_after_all_failures',R.bind(lock)==expected)
 # Run was not called; AST confirms no direct deletion/copy/kill implementation.
 source=Path(R.__file__).read_text(encoding='utf-8')
 ck('no_direct_delete_copy_or_native_entry',not any(x in source for x in ('.unlink(','.remove(','.kill(','.terminate(','.Popen(','.native(','.worker(')))
 return R.save(output/'SOURCE_CHECKS.json',dict(schema='s6c-external-lease-recovery-checks.v1',status='PASS_SOURCE_AND_PRIVATE_FIXTURES_ONLY',checks=len(checks),names=checks,sources=[R.bind(R.__file__),R.bind(__file__),R.bind(R.HERE/'README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md'),R.bind(R.RELEASE_SOURCE)],actual_recoveries=0,native_calls=0,scope='Only private tempfile lease mutation. Actual original lease,80cell files,root audit and process identities not read or modified by tests. Original source-only AST loaded without module execution.'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))

