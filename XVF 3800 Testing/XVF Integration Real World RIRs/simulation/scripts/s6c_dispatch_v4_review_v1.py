"""Independent dispatcher V4 source/private-proof checks; README_S6C_DISPATCH_V4_REVIEW_V1.md."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,tempfile,types
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
V3_SHA='3815b657dd777fad3ca10a9bd7957a6fdaa4d1b5e6bf69a7be499764425bbbd2'
V4_SHA='d0b97ad8035855d4a389d4b4dbd9a85c0625da84e027685b435d1b7d613825da'
B36_SHA='130255266206ddb95c917ad5825328782dbeedafa9656814024c1ed1d32e0892'

def bind(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def run(output):
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);checks=[]
 def ck(name,value=True):
  if not value:raise AssertionError(name)
  checks.append(name)
 def bad(name,fn):
  try:fn()
  except (ValueError,KeyError,OSError):ck(name)
  else:raise AssertionError(name)
 old=HERE/'s6c_paced_dispatch_v3.py';new=HERE/'s6c_paced_dispatch_v4.py'
 ck('exact_V3_source',bind(old)['sha256']==V3_SHA);ck('exact_V4_source',bind(new)['sha256']==V4_SHA)
 original=old.read_text();reversed_source=new.read_text()
 def replace_once(a,b):
  nonlocal reversed_source
  ck('unique_reverse_'+str(len(checks)),reversed_source.count(a)==1);reversed_source=reversed_source.replace(a,b)
 start=reversed_source.index("B36_NAME='s6c_paced_b36_fast_v2.py'")
 end=reversed_source.index('def require(value,message):',start)
 reversed_source=reversed_source[:start]+reversed_source[end:]
 replace_once('README_S6C_PACED_DISPATCH_V4.md','README_S6C_PACED_DISPATCH_V3.md') if reversed_source.count('README_S6C_PACED_DISPATCH_V4.md')==1 else None
 # The docstring and run receipt intentionally name the new maintained README.
 ck('exact_two_README_references',reversed_source.count('README_S6C_PACED_DISPATCH_V4.md')==2)
 reversed_source=reversed_source.replace('README_S6C_PACED_DISPATCH_V4.md','README_S6C_PACED_DISPATCH_V3.md')
 replace_once('import argparse,importlib.util,hashlib','import argparse,hashlib')
 replace_once("namespace.endswith('_fast_v2' if kind or name==B36_NAME else '_fast_v1')","namespace.endswith('_fast_v2' if kind else '_fast_v1')")
 replace_once("  if name==B36_NAME:\n   exact_plan,exact_binding=b36_module().admit_plan(B36Reader(),pb);require(exact_plan==plan and exact_binding==pb,'Explicit B36 V2 exact preparation lineage')\n",'')
 replace_once(" if Path(item['helper']['path']).name==B36_NAME:return b36_completion(item,plan,owner,quiet_binding,inspect)\n",'')
 ck('whole_module_AST_exact_after_explicit_B36_delta',ast.dump(ast.parse(reversed_source))==ast.dump(ast.parse(original)))
 spec=importlib.util.spec_from_file_location('_review_dispatch_v4',new);D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)
 ck('exact_B36_pin',D.B36_SHA==B36_SHA and bind(HERE/D.B36_NAME)['sha256']==B36_SHA)
 actual_helper=D.b36_module();ck('actual_metadata_helper_import_only',actual_helper.SCHEMA==D.WRAPPERS[D.B36_NAME][1])
 with tempfile.TemporaryDirectory(prefix='s6c_dispatch_v4_review_') as temp:
  root=Path(temp).resolve();quiet=dict(path=str(root/'quiet.json'),bytes=1,sha256='q')
  pb=dict(path=str(root/'manifest.json'),bytes=1,sha256='m');helper=bind(HERE/D.B36_NAME)
  plan=dict(jobs=[dict(job_id=str(i)) for i in range(40)])
  item=dict(manifest=pb,cells=40,helper=helper)
  owner=dict(pid=123,creation_time=456.,argv=[str(D.EDGE),'-B',helper['path'],'run','--manifest',pb['path'],'--quiet-admission',quiet['path']])
  launch_path=root/'invocations/one/LAUNCH.json';launch_path.parent.mkdir(parents=True)
  launch=dict(quiet_admission=quiet,coordinator=helper);launch_path.write_text(json.dumps(launch));lb=bind(launch_path)
  reference=dict(path=str(root/'fixture.json'),bytes=0,sha256='fixture')
  proof=dict(status='B36_NATIVE_BATCH_COMPLETE_WITH_EXPLICIT_C_ARCHIVE',manifest=pb,cells=40,owner=owner,launch=lb,completion=reference,lease_release=reference,archived_lease=reference,observer_exit=reference,completed_cells=[dict(completion=reference) for _ in range(40)],current_child_observations=[])
  calls=[]
  def fake_batch(reader,binding,inspect):
   calls.append(binding);ck('same_inspector_forwarded',inspect is closed);return copy.deepcopy(current_proof)
  def closed(o):return dict(alive=False,error=None)
  fake=types.SimpleNamespace(admit_plan=lambda reader,binding:(copy.deepcopy(current_plan),current_pb),admit_complete_batch=fake_batch)
  current_plan=plan;current_pb=pb;current_proof=proof
  with patch.object(D,'b36_module',return_value=fake),patch.object(D,'REPORT',root/'report'):
   good=D.completion(item,plan,owner,quiet,inspect=closed)
   ck('explicit_success_proof',good['status']=='ORIGINAL_BATCH_COMPLETE_AND_OWNERS_CLOSED' and good['cells']==40 and len(good['bindings'])==45 and good['explicit_b36_v2_admission']==proof)
   for label,mutate in [('status',lambda p:p.update(status='FAILED')),('manifest',lambda p:p.update(manifest={**pb,'sha256':'other'})),('count',lambda p:p.update(cells=39)),('owner_pid',lambda p:p['owner'].update(pid=124)),('owner_creation',lambda p:p['owner'].update(creation_time=457.)),('owner_argv',lambda p:p['owner'].update(argv=['other']))]:
    current_proof=copy.deepcopy(proof);mutate(current_proof)
    bad('reject_proof_'+label,lambda:D.completion(item,plan,owner,quiet,inspect=closed))
   current_proof=proof
   bad('reject_dispatcher_quiet_mismatch',lambda:D.completion(item,plan,owner,{**quiet,'sha256':'other'},inspect=closed))
   bad('reject_current_live_parent',lambda:D.completion(item,plan,owner,quiet,inspect=lambda o:dict(alive=True,error=None)))
   bad('reject_current_unknown_parent',lambda:D.completion(item,plan,owner,quiet,inspect=lambda o:dict(alive=None,error='unverified')))
   current_plan={'changed':True};bad('reject_changed_plan',lambda:D.completion(item,plan,owner,quiet,inspect=closed));current_plan=plan
   current_pb={**pb,'sha256':'other'};bad('reject_changed_plan_binding',lambda:D.completion(item,plan,owner,quiet,inspect=closed));current_pb=pb
   bad('reject_declared_grid_count',lambda:D.completion({**item,'cells':39},plan,owner,quiet,inspect=closed))
   changed_launch={**launch,'coordinator':{**helper,'sha256':'other'}};launch_path.write_text(json.dumps(changed_launch));current_proof=copy.deepcopy(proof);current_proof['launch']=bind(launch_path)
   bad('reject_launch_helper_mismatch',lambda:D.completion(item,plan,owner,quiet,inspect=closed))
   launch_path.write_text(json.dumps(launch));current_proof=copy.deepcopy(proof);current_proof['launch']=bind(launch_path)
   (D.REPORT).mkdir();(D.REPORT/'PACED_QUIET_OWNER.json').write_text('{}')
   bad('reject_active_lease',lambda:D.completion(item,plan,owner,quiet,inspect=closed))
 ck('held_source_unchanged',bind(new)['sha256']==V4_SHA and bind(HERE/D.B36_NAME)['sha256']==B36_SHA)
 result=dict(status='PASS_SOURCE_AND_PRIVATE_METADATA_ONLY',checks=len(checks),names=checks,sources=[bind(old),bind(new),bind(HERE/'README_S6C_PACED_DISPATCH_V4.md'),bind(HERE/D.B36_NAME),bind(__file__),bind(HERE/'README_S6C_DISPATCH_V4_REVIEW_V1.md')],runtime_launches=0,actual_completion_reads=0,scope='Whole-module reverse AST equals held V3; explicit B36 branch delegates reviewed batch authority. Tiny proof mutations only, no actual queue/admission/runtime calls or model/storage scans.')
 path=output/'REVIEW_RECEIPT.json';path.write_text(json.dumps(result,indent=2)+'\n');return bind(path)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(run(p.parse_args().output),indent=2))
