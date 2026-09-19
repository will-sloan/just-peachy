"""Small dispatcher closure/launch fixtures; README_S6C_PACED_DISPATCH_V1.md."""
import argparse,ast,json,tempfile,types
from pathlib import Path
from unittest.mock import patch
import s6c_paced_dispatch_v1 as D

def fixture(root,historical=False):
 report=root/'report';batch=root/'batch';inv=batch/'invocations/one';inv.mkdir(parents=True)
 name='s6c_paced_controls_fast_v1.py' if historical else 's6c_paced_epoch4_fast_v2.py';helper=D.binding(D.HERE/name)
 mb=dict(path=str(batch/'MANIFEST.json'),bytes=2,sha256='0'*64);qb=dict(path=str(root/'quiet.json'),bytes=2,sha256='1'*64)
 owner=dict(pid=101,creation_time=1.,argv=['explicit','run']);job=dict(job_id='j1',job_key='key',report_root=str(batch/'jobs/j1'))
 plan=dict(jobs=[job]);item=dict(helper=helper,manifest=mb,cells=1,output_root=str(batch))
 child=dict(pid=102,creation_time=2.);cb=D.save(batch/'jobs/j1/COMPLETE.json',dict(status='COMPLETE',job_key='key',all_owned_processes_closed=True,owned_processes=[child]))
 launch=dict(status='STARTED',manifest=mb,quiet_admission=qb)
 launch.update(dict(pid=owner['pid'],creation_time=owner['creation_time'],coordinator=helper) if historical else dict(owner=owner))
 lb=D.save(inv/'LAUNCH.json',launch);lease=dict(pid=owner['pid'],creation_time=owner['creation_time'],manifest=mb)
 done=dict(status='COMPLETE',manifest=mb,completed=1,requested=1,error=None)
 if historical:
  D.save(inv/'COMPLETION.json',done);D.save(inv/'QUIET_OWNER_CLOSED.json',lease)
 else:
  lease.update(kind=D.WRAPPERS[name][3],launch=lb);rb=D.save(inv/'QUIET_LEASE_RELEASED.json',lease)
  done.update(owner=owner,cleanup_errors=[],remaining_owned=[],rows=[dict(job_id='j1',status='COMPLETE',completion=cb)])
  db=D.save(inv/'OUTCOME.json',done);D.save(inv/'CLOSURE.json',dict(owner=owner,status='QUIET_LEASE_RELEASED',manifest=mb,outcome=db,lease_release=dict(status='RELEASED',released=True,error=None,archived_binding=rb,source={**rb,'path':str(report/'PACED_QUIET_OWNER.json')},requested_archive=rb['path'])))
 return report,batch,inv,item,plan,owner,qb

def run(output):
 output.mkdir(parents=True,exist_ok=False);names=[]
 def ck(n,v=True):assert v,n;names.append(n)
 def reject(n,f):
  try:f()
  except (ValueError,KeyError,TypeError,OSError):ck(n);return
  raise AssertionError(n)
 for historical in (False,True):
  for fault in (None,'partial','wrong_count','wrong_manifest','wrong_owner','live_child','unknown_parent','lease_present'):
   with tempfile.TemporaryDirectory(prefix='s6c_dispatch_') as tmp:
    report,batch,inv,item,plan,owner,qb=fixture(Path(tmp),historical)
    path=inv/('COMPLETION.json' if historical else 'OUTCOME.json')
    if fault in ('partial','wrong_count','wrong_manifest'):
     d,_=D.read(path);d.update({'status':'PARTIAL'} if fault=='partial' else {'completed':0} if fault=='wrong_count' else {'manifest':{}});path.write_text(json.dumps(d),encoding='utf-8')
     # Rebind the canonical outer link so tests reach semantic status/count guards.
     if not historical:
      p=inv/'CLOSURE.json';c,_=D.read(p);c['outcome']=D.binding(path);p.write_text(json.dumps(c),encoding='utf-8')
    if fault=='wrong_owner':owner=dict(owner,creation_time=3.)
    if fault=='lease_present':D.save(report/'PACED_QUIET_OWNER.json',{})
    def inspect(o):return dict(alive=None if fault=='unknown_parent' else True if fault=='live_child' and o['pid']==102 else False)
    with patch.object(D,'REPORT',report):
     call=lambda:D.completion(item,plan,owner,qb,inspect)
     if fault:reject(str(historical)+'_'+fault,call)
     else:ck(str(historical)+'_original_complete_schema',call()['cells']==1)
 with tempfile.TemporaryDirectory(prefix='s6c_dispatch_spawn_') as tmp:
  folder=Path(tmp);fake=types.SimpleNamespace(pid=303,poll=lambda:None)
  def unavailable(pid):
   ck('spawn_written_before_identity_query',(folder/'SPAWNED_PROCESS.json').exists());raise OSError('injected identity unavailable')
  try:D.launch(['exact'],folder,popen=lambda *a,**kw:fake,process=unavailable)
  except OSError as e:ck('successful_handle_retained_on_identity_failure',e.dispatch_child is fake and e.dispatch_owner is None)
  else:raise AssertionError('Fault not raised')
  d,_=D.read(folder/'LAUNCH_FAILURE.json');ck('unknown_spawn_not_complete',d['pid']==303 and d['owner'] is None and d['returncode'] is None)
 ck('exact_EDGE_path',D.canonical(D.EDGE)==D.canonical('C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'))
 for name,(sha,schema,_,_) in D.WRAPPERS.items():
  ck('held_'+name,D.binding(D.HERE/name)['sha256']==sha)
  if name.endswith('_fast_v2.py'):
   t=ast.parse((D.HERE/name).read_bytes());actual=next(n.value.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(a,ast.Name) and a.id=='SCHEMA' for a in n.targets));ck('original_schema_'+name,schema==actual)
 ck('continuous_not_whitelisted',all('long_' not in n for n in D.WRAPPERS))
 source=(D.HERE/'s6c_paced_dispatch_v1.py').read_text();ck('no_process_kill_or_lease_delete',not any(x in source for x in ('.kill(','.terminate(','.unlink(','.rmdir(')))
 return D.save(output/'SOURCE_CHECKS.json',dict(schema='s6c-paced-dispatch-checks.v1',status='PASS_SOURCE_AND_SYNTHETIC_ONLY',checks=len(names),names=names,sources=[D.binding(D.HERE/'s6c_paced_dispatch_v1.py'),D.binding(__file__),D.binding(D.HERE/'README_S6C_PACED_DISPATCH_V1.md'),*[D.binding(D.HERE/n) for n in D.WRAPPERS]],actual_queue_created=False,actual_dispatcher_runs=0,native_calls=0,scope='Tiny synthetic original-schema completion and injected Popen identity failure. No real subprocess, queue, runtime metadata, model/audio/assets or storage scans.'))

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);print(json.dumps(run(p.parse_args().output),indent=2))
if __name__=='__main__':main()
