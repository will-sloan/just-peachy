"""Serial original paced runners; README_S6C_PACED_DISPATCH_V1.md."""
from __future__ import annotations
import argparse,hashlib,json,math,os,re,subprocess,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import psutil

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parents[2]
EDGE=REPO/'.edge-speech-env/python.exe'
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
DEADLINE=datetime(2026,9,13,11,35,40,tzinfo=timezone.utc)
WRAPPERS={
 's6c_paced_epoch4_fast_v2.py':('a8776724003fa2a642575892327b7c3e88eaddf29606881b302b05157c12b270','s6c-canonical-paired-paced.v1','paced_candidates','S6C_CANONICAL_PACED_EPOCH4'),
 's6c_paced_arrival_sentinel_fast_v2.py':('d456f9423fe365a330eac0b5b7b372ae12731c49b7b37ab530b3ad707c2c091a','s6c-paced-arrival-sentinel.v1','paced_arrival_sentinel','S6C_PACED_ARRIVAL_SENTINEL'),
 's6c_paced_cross_routes_fast_v2.py':('db4b7db3db45a4685b693dfab3b24cf38e321fee9a5fd56606ae1f3f5852fd5f','s6c-cross-route-paired-paced.v1','paced_cross_routes','S6C_CROSS_ROUTE_PACED_EPOCH4'),
 's6c_paced_controls_fast_v1.py':('49313592295cfd544c8b1c21e029b78a288ea6e2aa05d8419c1581b8c95af32a','s6c-historical-paced-controls-fast.v1','paced_controls',None),
 's6c_paced_b36_fast_v1.py':('a92ec01f3df563274c8a4ce6694844c921fa3c58039cf9e34c270aea57e546fb','s6c-historical-paced-b36-fast.v1','paced_controls',None)}

def require(value,message):
 if not value:raise ValueError(message)

def utc():return datetime.now(timezone.utc).isoformat()
def canonical(p):return os.path.normcase(str(Path(p).resolve()))
def dt(value):
 d=datetime.fromisoformat(value.replace('Z','+00:00'));require(d.tzinfo is not None,'Aware UTC deadline required');return d.astimezone(timezone.utc)
def finite_owner(o):return type(o.get('pid')) is int and o['pid']>0 and type(o.get('creation_time')) in (int,float) and math.isfinite(o['creation_time']) and o['creation_time']>0
def same_owner(a,b):require(finite_owner(a) and finite_owner(b) and (a['pid'],a['creation_time'])==(b['pid'],b['creation_time']),'Exact finite owner identity required')
def binding(path,raw=None):
 p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw;return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path,expected=None):
 p=Path(path);require(p.is_absolute(),'Absolute metadata path required');require(p.stat().st_size<=8*2**20,'Bounded metadata document required');raw=p.read_bytes();require(len(raw)<=8*2**20,'Metadata grew beyond cap');b=binding(p,raw)
 if expected is not None:require(b==expected,'Exact metadata buffer binding differs')
 return json.loads(raw),b
def save(path,value,replace=False):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
 if replace:
  t=p.with_name(p.name+'.tmp');require(not t.exists(),'Preserved heartbeat temporary file');t.write_bytes(raw);os.replace(t,p)
 else:
  with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return binding(p,raw)
def state(o):
 if not finite_owner(o):return dict(alive=None,error='CREATION_IDENTITY_UNVERIFIED')
 try:
  p=psutil.Process(o['pid']);return dict(alive=p.create_time()==o['creation_time'] and p.is_running(),error=None)
 except psutil.NoSuchProcess:return dict(alive=False,error=None)
 except (psutil.Error,OSError) as e:return dict(alive=None,error=repr(e))

def admit(queue_binding,authority_binding):
 q,qb=read(queue_binding['path'],queue_binding);a,ab=read(authority_binding['path'],authority_binding)
 require(q['schema']=='s6c-serial-paced-queue.v1' and q['status']=='REGISTERED_FINITE_QUEUE','Explicit registered queue required')
 require(re.fullmatch('[A-Za-z0-9_-]{1,64}',q['namespace']),'Simple fresh dispatcher namespace')
 require(a['schema']=='s6c-serial-paced-authority.v1' and a['status']=='AUTHORIZED_SERIAL_QUIET_PACED' and a['queue']==qb and a['dispatcher']==binding(__file__),'Exact root queue/dispatcher authority')
 require(a['all_other_model_hil_work_stopped'] is True and a['all_heavy_analysis_stopped'] is True,'Explicit quiet interval authority required')
 require(datetime.now(timezone.utc)<dt(a['expires_utc'])<=DEADLINE,'Root quiet deadline expired or beyond stage deadline')
 require(1<=len(q['items'])<=64 and len({x['item_id'] for x in q['items']})==len(q['items']),'Finite unique queue items')
 require(len({canonical(x['manifest']['path']) for x in q['items']})==len(q['items']),'Duplicate queued manifest')
 require(len({canonical(x['output_root']) for x in q['items']})==len(q['items']),'Duplicate queued output root')
 plans=[]
 for item in q['items']:
  require(re.fullmatch('[A-Za-z0-9_-]{1,64}',item['item_id']),'Simple item identifier')
  h=item['helper'];name=Path(h['path']).name;require(name in WRAPPERS,'Paced wrapper whitelist; continuous helpers excluded');sha,schema,family,kind=WRAPPERS[name]
  require(h==binding(HERE/name) and h['sha256']==sha,'Exact held wrapper binding')
  plan,pb=read(item['manifest']['path'],item['manifest']);require(plan['schema']==schema,'Original paced schema differs')
  root=Path(plan['report_root'] if kind else plan['output_root']);namespace=root.name
  require(canonical(root)==canonical(item['output_root']) and root==(REPORT if kind else PAYLOAD)/family/namespace,'Exact original output root')
  require(re.fullmatch('[A-Za-z0-9_-]{1,64}',namespace) and namespace.endswith('_fast_v2' if kind else '_fast_v1'),'Exact fresh wrapper namespace')
  require(Path(pb['path'])==root/'MANIFEST.json','Manifest is outside original output root')
  require(type(item['cells']) is int and item['cells']>0 and item['cells']==len(plan['jobs']),'Exact declared cell count')
  require(len({j['job_id'] for j in plan['jobs']})==item['cells'],'Unique original jobs')
  require(h in (plan['sources'] if kind else plan['fast_observer']['sources']),'Original prepared helper source binding')
  require(datetime.now(timezone.utc)<dt(plan['deadline_utc'])<=DEADLINE,'Manifest deadline expired or changed')
  plans.append(plan)
 return q,qb,a,ab,plans

def completion(item,plan,owner,quiet_binding,inspect=state):
 """Original coordinator/cell metadata only; not V7 or scientific acceptance."""
 require(inspect(owner)['alive'] is False,'Batch parent still live or unknown')
 require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Shared quiet lease still present')
 root=Path(item['output_root']);folders=list((root/'invocations').iterdir());require(len(folders)==1 and folders[0].is_dir(),'One fresh original invocation required');folder=folders[0]
 launch,lb=read(folder/'LAUNCH.json');same_owner(owner,launch.get('owner',launch));require(launch['manifest']==item['manifest'] and launch['quiet_admission']==quiet_binding,'Invocation manifest/quiet authority differs')
 kind=WRAPPERS[Path(item['helper']['path']).name][3];refs=[lb];jobs={j['job_id']:j for j in plan['jobs']}
 if kind:
  require(launch['owner']['argv']==owner['argv'],'Original coordinator argv differs')
  done,db=read(folder/'OUTCOME.json');closed,cb=read(folder/'CLOSURE.json');refs.extend([db,cb]);same_owner(owner,done['owner']);same_owner(owner,closed['owner'])
  require(done['error'] is None and not done['cleanup_errors'] and all(x['alive'] is False for x in done['remaining_owned']),'Partial/error/unknown owned closure')
  require(closed['status']=='QUIET_LEASE_RELEASED' and closed['manifest']==item['manifest'] and closed['outcome']==db,'Exact released outcome chain')
  release=closed['lease_release'];require(release['status']=='RELEASED' and release['released'] is True and release['error'] is None,'Quiet release not verified')
  lease,rb=read(folder/'QUIET_LEASE_RELEASED.json',release['archived_binding']);refs.append(rb)
  require(release['source']=={**rb,'path':str(REPORT/'PACED_QUIET_OWNER.json')} and canonical(release['requested_archive'])==canonical(rb['path']),'Original lease byte/archive lineage')
  require(lease['kind']==kind and lease['launch']==lb,'Original quiet lease kind/launch')
  rows=done['rows'];require(len(rows)==item['cells'] and {r['job_id'] for r in rows}==set(jobs),'Exact completed job grid')
  for row in rows:require(row['status'] in ('COMPLETE','COMPLETE_REUSED') and Path(row['completion']['path'])==Path(jobs[row['job_id']]['report_root'])/'COMPLETE.json','Exact completion reference')
  completed_bindings={r['job_id']:r['completion'] for r in rows}
 else:
  require(launch['coordinator']==item['helper'],'Historical original coordinator binding differs')
  done,db=read(folder/'COMPLETION.json');lease,rb=read(folder/'QUIET_OWNER_CLOSED.json');refs.extend([db,rb]);require(done['error'] is None,'Historical partial/error')
  completed_bindings={jid:None for jid in jobs}
 require(done['status']=='COMPLETE' and done['manifest']==item['manifest'] and type(done['requested']) is int and type(done['completed']) is int and done['requested']==done['completed']==item['cells'],'Original complete counts/status differ')
 same_owner(owner,lease);require(lease['manifest']==item['manifest'],'Archived lease manifest differs')
 owners=[]
 for jid,j in jobs.items():
  path=(Path(j['report_root']) if kind else root/'jobs'/jid)/'COMPLETE.json';cell,cb=read(path,completed_bindings[jid]);refs.append(cb)
  require(cell['status']=='COMPLETE' and cell['job_key']==j['job_key'] and cell['all_owned_processes_closed'] is True and cell['owned_processes'],'Original per-cell completion/owner proof')
  for o in cell['owned_processes']:
   require(finite_owner(o),'Unverified original native owner');observed=inspect(o);require(observed['alive'] is False,'Native child live or unknown');owners.append(dict(owner=o,observation=observed))
 return dict(status='ORIGINAL_BATCH_COMPLETE_AND_OWNERS_CLOSED',manifest=item['manifest'],cells=item['cells'],invocation=str(folder),bindings=refs,owners=owners,scope='Dispatcher transition proof only; V7 admission, native source/tail parity and scientific analysis remain separate.')

def launch(argv,folder,popen=subprocess.Popen,process=psutil.Process):
 """Successful Popen is recorded before creation-time lookup; no cleanup/kill."""
 log=(folder/'RUNNER_LOG.txt').open('xb');child=None;owner=None
 try:
  child=popen(argv,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  save(folder/'SPAWNED_PROCESS.json',dict(status='SPAWNED_CREATION_UNVERIFIED',pid=child.pid,creation_time=None,argv=argv,created_utc=utc()))
  p=process(child.pid);owner=dict(pid=child.pid,creation_time=p.create_time(),argv=argv);require(finite_owner(owner) and child.poll() is None and p.cmdline()==argv,'Finite live launched coordinator identity/argv')
  save(folder/'LAUNCH.json',dict(status='LAUNCHED',owner=owner,created_utc=utc()));return child,owner,log
 except BaseException as exc:
  exc.dispatch_child=child;exc.dispatch_owner=owner
  save(folder/'LAUNCH_FAILURE.json',dict(status='FAILED_OR_UNVERIFIED_LAUNCH',pid=child.pid if child else None,owner=owner,returncode=child.poll() if child else None,error=traceback.format_exc(),scope='No kill or lease removal. A successful Popen may still be alive; root must resolve before another dispatcher.'))
  log.close();raise

def run(args):
 require(canonical(sys.executable)==canonical(EDGE),'Exact EDGE interpreter required')
 def explicit(pair):d,b=read(Path(pair[0]).resolve());require(b['sha256']==pair[1],'Explicit authority SHA differs');return b
 qb=explicit(args.queue);ab=explicit(args.authority);q,qb,a,ab,plans=admit(qb,ab)
 out=REPORT/'serial_paced_dispatcher'/q['namespace'];out.mkdir(parents=True,exist_ok=False)
 me=psutil.Process();owner=dict(pid=me.pid,creation_time=me.create_time(),argv=me.cmdline());require(finite_owner(owner),'Dispatcher identity unavailable')
 save(out/'ADMISSION.json',dict(status='DISPATCHER_STARTED',owner=owner,queue=qb,authority=ab,source=binding(__file__),readme=binding(HERE/'README_S6C_PACED_DISPATCH_V1.md'),created_utc=utc()))
 completed=[];child=None;child_owner=None;log=None;error=None;started=time.monotonic();active=None
 try:
  for item,plan in zip(q['items'],plans):
   active=item['item_id'];folder=out/active;folder.mkdir();read(qb['path'],qb);read(ab['path'],ab);read(item['manifest']['path'],item['manifest']);require(binding(item['helper']['path'])==item['helper'],'Held helper changed before launch')
   require(not (REPORT/'PACED_QUIET_OWNER.json').exists() and not (REPORT/'STOP_REQUEST.json').exists(),'Quiet lease or stop request blocks next batch')
   require(not (Path(item['output_root'])/'invocations').exists(),'Prior invocation requires explicit root resolution; dispatcher does not resume')
   deadline=min(dt(plan['deadline_utc']),dt(a['expires_utc']),DEADLINE);require(datetime.now(timezone.utc)<deadline,'Quiet authority expired')
   quiet=save(folder/'QUIET_ADMISSION.json',dict(status='AUTHORIZED_FOR_QUIET_PACED',manifest_sha256=item['manifest']['sha256'],all_other_model_hil_work_stopped=True,all_heavy_analysis_stopped=True,expires_utc=deadline.isoformat(),root_authority=ab,queue=qb,dispatcher_owner=owner,item_id=active,created_utc=utc()))
   argv=[str(EDGE),'-B',item['helper']['path'],'run','--manifest',item['manifest']['path'],'--quiet-admission',quiet['path']]
   child,child_owner,log=launch(argv,folder)
   while child.poll() is None:
    observed=state(child_owner)
    if observed['alive'] is not True and child.poll() is not None:break
    require(observed['alive'] is True,'Running coordinator identity unknown or changed')
    save(out/'HEARTBEAT.json',dict(status='RUNNING',owner=owner,active_item=active,child=child_owner,child_observation=observed,completed_batches=len(completed),requested_batches=len(q['items']),completed_cells=sum(x['cells'] for x in completed),elapsed_sec=time.monotonic()-started,created_utc=utc()),replace=True)
    require(datetime.now(timezone.utc)<deadline and not (out/'STOP_REQUEST.json').exists() and not (REPORT/'STOP_REQUEST.json').exists(),'Dispatch deadline/stop; existing child may remain live')
    time.sleep(15)
   log.close();log=None;save(folder/'PARENT_EXIT.json',dict(owner=child_owner,returncode=child.returncode,observation=state(child_owner),created_utc=utc()))
   require(child.returncode==0,'Original runner returned an error; no next batch')
   proof=completion(item,plan,child_owner,quiet);proof['item_id']=active;save(folder/'BATCH_TRANSITION.json',proof);completed.append(proof);child=None;child_owner=None
 except BaseException as exc:
  child=getattr(exc,'dispatch_child',child);child_owner=getattr(exc,'dispatch_owner',child_owner);error=traceback.format_exc();raise
 finally:
  if log is not None:log.close()
  save(out/'RESULT.json',dict(schema='s6c-serial-paced-dispatch-result.v1',status='DISPATCH_QUEUE_COMPLETE' if error is None else 'STOPPED_REQUIRES_ROOT_REVIEW',owner=owner,queue=qb,authority=ab,completed_batches=len(completed),requested_batches=len(q['items']),completed_cells=sum(x['cells'] for x in completed),completed=completed,active_item=active,possible_child=child_owner,possible_child_pid=child.pid if child else None,child_returncode=child.poll() if child else None,child_observation=state(child_owner) if child_owner else None,error=error,ended_utc=utc(),elapsed_sec=time.monotonic()-started,scope='Serial launch/transition accounting only. No process was killed and no quiet lease removed. Dispatcher completion is separate from V7/scientific admission; interrupted child identity may remain live or unknown.'))
 return binding(out/'RESULT.json')

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['run']);p.add_argument('--queue',nargs=2,required=True,metavar=('PATH','SHA256'));p.add_argument('--authority',nargs=2,required=True,metavar=('PATH','SHA256'));print(json.dumps(run(p.parse_args()),indent=2))
if __name__=='__main__':main()
