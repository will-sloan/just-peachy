"""Independent tiny checks; README_S6C_EXTERNAL_RECOVERY_COMPONENT_V1.md."""
import argparse,ast,copy,json,tempfile,traceback
from pathlib import Path
import s6c_external_lease_recovery_v1 as R
import test_s6c_external_lease_recovery_v1 as T

def run(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 expected={'s6c_external_lease_recovery_v1.py':'750e96751662d6da33309004a131984f14d6893e0f70e8ca73d8dc6b5265d66d','README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md':'173468aa9df79fbbf2a3b28877aeb1ffe4053c21e244b16598c227ee0db74fea','test_s6c_external_lease_recovery_v1.py':'dc18d548c0c38c7667c24bba12d161af96af674223b756c8108fabb49f07d8c2'}
 sources=[R.bind(R.HERE/n) for n in expected]
 assert all(b['sha256']==expected[Path(b['path']).name] for b in sources)
 reproduced=T.run(out/'reproduced');rd=json.loads(Path(reproduced['path']).read_bytes());assert rd['checks']==28
 checks=[]
 def check(n,v):
  assert v,n;checks.append(n)
 def bad(n,f):
  try:f()
  except (ValueError,KeyError,TypeError):checks.append(n);return
  raise AssertionError(n)
 with tempfile.TemporaryDirectory(prefix='s6c_independent_external_release_') as tmp:
  root=Path(tmp).resolve();values=T.fixture(root)
  for name,mutation in [('wrong_possible_child',lambda x:x[6]['possible_child'].update(creation_time=999.)),('wrong_original_argv',lambda x:x[7].update(owner=dict(x[7]['owner'],argv=['other']))),('wrong_cell_namespace',lambda x:x[0]['rows'][0]['completion'].update(path=str(root/'other.json')))]:
   altered=copy.deepcopy(values);mutation(altered);bad(name,lambda:R.validate_chain(*altered))
  bad('numeric_zero_is_not_observed_closed',lambda:R.all_closed([values[2]],lambda o:dict(alive=0,error=None)))
  fn=R.release_function();ns=dict(fn.__globals__);read=ns['read_bound']
  import types
  isolated=types.FunctionType(fn.__code__,ns);lock=root/'lock.json';archive=root/'archive.json';binding=R.save(lock,{'owner':'private'})
  def reject_archive(path,expected=None):
   if Path(path)==archive:raise ValueError('injected archive verification fault')
   return read(path,expected)
  ns['read_bound']=reject_archive;r=isolated(lock,archive,binding)
  check('renamed_but_unverified_is_not_success',r['released'] is True and r['status']=='RELEASED_BINDING_UNVERIFIED' and r['error'] and not lock.exists() and archive.exists())
  check('unverified_archive_preserves_original_bytes',R.bind(archive)['sha256']==binding['sha256'])
  check('release_globals_not_mutated',fn.__globals__['read_bound'] is R.read_bound)
 tree=ast.parse(Path(R.__file__).read_bytes());recover=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='recover')
 calls=[ast.unparse(x) for x in ast.walk(recover) if isinstance(x,ast.Call)]
 check('exact_c_side_archive_target',"out / 'PRESERVED_ORIGINAL_QUIET_LEASE.json'" in ast.unparse(recover))
 check('fresh_owner_check_precedes_release',ast.unparse(recover).rfind('observed = all_closed(owners)')<ast.unparse(recover).index('result = release(lock, archive, lb)'))
 check('no_subprocess_or_payload_entry',not any(any(t in x for t in ('Popen(','.native(','.worker(','.unlink(','.copy(')) for x in calls))
 receipt=dict(schema='s6c-external-recovery-independent-review.v1',status='PASS_SOURCE_AND_PRIVATE_FIXTURES_ONLY',source_review='Entire helper and README read; exact original80-grid/162-owner authority, C same-volume archive, original G absence, and explicit failure preservation inspected.',owner_checks=28,independent_checks=len(checks),names=checks,reproduced=reproduced,sources=sources+[R.bind(__file__),R.bind(R.HERE/'README_S6C_EXTERNAL_RECOVERY_COMPONENT_V1.md'),R.bind(R.RELEASE_SOURCE)],actual_lease_reads=0,actual_recoveries=0,native_calls=0,limitations=['Root must supply exact unexpired source-bound authority.','Recovery exit must be observed separately.','Post-rename publication failure requires root inspection; no automatic retry or fabricated original closure.','V7 still requires a separately reviewed explicit recovery overlay.'])
 return R.save(out/'REVIEW_RECEIPT.json',receipt)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
