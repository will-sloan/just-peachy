"""Explicit B36 paced C-volume closure; README_S6C_PACED_B36_FAST_V2.md."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,math,os,re,sys,traceback,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
STAGING=HERE.parent/'staging/s6c/20260910T123540Z'
PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
SCHEMA='s6c-historical-paced-b36-fast.v2'
SHARED_SHA='579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299'
RECOVERY_SHA='750e96751662d6da33309004a131984f14d6893e0f70e8ca73d8dc6b5265d66d'
PARENT=PAYLOAD/'paced_controls/b36_fast_v1/MANIFEST.json'
PARENT_SHA='3f1ebec0b5af205b2d215988c692fd510171b52d0114c48110e2142a2563038c'

def require(value,message):
 if not value:raise ValueError(message)
def load_pinned(name,sha):
 p=HERE/name;require(hashlib.sha256(p.read_bytes()).hexdigest()==sha,'Held helper changed: '+name)
 spec=importlib.util.spec_from_file_location('_b36_release_'+name.removesuffix('.py'),p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m
F=load_pinned('s6c_historical_fast_observer_v1.py',SHARED_SHA)
R=load_pinned('s6c_external_lease_recovery_v1.py',RECOVERY_SHA)

def roots(kind,name):
 require(kind=='b36' and isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}',name) and name.endswith('_fast_v2'),'Explicit B36 fast_v2 namespace required')
 return REPORT/'paced_controls'/name,PAYLOAD/'paced_controls'/name
def parent_binding():
 b=F.bind(PARENT);require(b['sha256']==PARENT_SHA,'Exact prior unstarted fast preparation');return b
def archival_policy():
 return dict(schema='s6c-b36-same-volume-lease-policy.v1',lease_path=str(REPORT/'PACED_QUIET_OWNER.json'),archive_root=str(REPORT/'paced_controls'),archive_layout='NAMESPACE/invocations/ORIGINAL_G_INVOCATION_ID/PRESERVED_ORIGINAL_QUIET_LEASE.json',receipt_name='LEASE_RELEASE.json',original_G_archive_created=False,release_source=F.bind(R.RELEASE_SOURCE),release_source_sha256=R.RELEASE_SHA,scope='Current new coordinator performs exact same-volume archival after all40 original native cells and children close; original G archive is intentionally absent.')
def context():
 # Compile an isolated copy of existing adapter definitions; no old globals change.
 ns=dict(vars(F));ns['VARIANTS']=copy.deepcopy(F.VARIANTS);ns['VARIANTS']['b36'].update(wrapper=Path(__file__).name,readme='README_S6C_PACED_B36_FAST_V2.md',schema=SCHEMA)
 nodes=[copy.deepcopy(n) for n in ast.parse(Path(F.__file__).read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
 exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(F.__file__),'exec'),ns)
 ns['roots']=roots
 original_sources=ns['source_bindings']
 def sources(kind):
  rows=original_sources(kind)+[F.bind(R.__file__),F.bind(HERE/'README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md'),F.bind(R.RELEASE_SOURCE),F.bind(HERE/'README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md')]
  require(F.bind(R.__file__)['sha256']==RECOVERY_SHA and F.bind(R.RELEASE_SOURCE)['sha256']==R.RELEASE_SHA,'Exact reviewed release dependencies')
  return list({b['path']:b for b in rows}.values())
 ns['source_bindings']=sources
 original_projection=ns['projection']
 def projection(kind,old,ob,name,created):
  value=original_projection(kind,old,ob,name,created);value.pop('manifest_key')
  value.update(previous_fast_preparation=parent_binding(),lease_archival_policy=archival_policy())
  value['manifest_key']=F.digest(value);return value
 ns['projection']=projection
 original_adapt=ns['adapt']
 def adapt(kind):
  api=original_adapt(kind);run_ns=api.run.__globals__
  # The shared adapter already made the reviewed timer/schema substitutions.
  base=ast.parse((HERE/F.VARIANTS['b36']['parent']).read_bytes())
  node=next(n for n in base.body if isinstance(n,ast.FunctionDef) and n.name=='run')
  class Timer(ast.NodeTransformer):
   def visit_Assign(self,n):
    if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='lastbeat' and isinstance(n.value,ast.Name) and n.value.id=='elapsed':
     return ast.copy_location(ast.Assign(targets=n.targets,value=ast.parse('time.monotonic()-t0',mode='eval').body),n)
    return self.generic_visit(n)
  node=Timer().visit(node);changes=[]
  class Archive(ast.NodeTransformer):
   def visit_Expr(self,n):
    wanted=ast.parse("lock.rename(invocation/'QUIET_OWNER_CLOSED.json')").body[0]
    if ast.dump(n)==ast.dump(wanted):
     changes.append(True);return ast.copy_location(ast.parse('archive_finished_lease(lock,invocation,plan,args,me)').body[0],n)
    return self.generic_visit(n)
  node=Archive().visit(node);require(len(changes)==1,'Exactly one original final archival call')
  run_ns['archive_finished_lease']=archive_finished_lease
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(HERE/F.VARIANTS['b36']['parent']),'exec'),run_ns)
  api.run=run_ns['run'];api._release_run_ast=node
  return api
 ns['adapt']=adapt
 return types.SimpleNamespace(**ns)

def admit_plan(reader,binding):
 # Deliberately metadata-only. Original runtime admission still checks all assets.
 p,pb=reader.read(binding['path'],binding);c=context();expected,eb=c.lineage('b36',binding['path'])
 require(pb==eb and p==expected,'Exact new manifest lineage')
 return p,pb

def prepare(args):
 prior,pb=F.read_bound(PARENT);require(pb==parent_binding(),'Prior fast manifest binding')
 require(Path(args.source_manifest).resolve()==PARENT.resolve() and args.source_sha256==PARENT_SHA,'Explicit prior preparation required')
 F.lineage('b36',PARENT)
 require(not (Path(prior['output_root'])/'jobs').exists() and not (Path(prior['output_root'])/'invocations').exists(),'Prior B36 native namespace must remain unstarted')
 c=context();original=c.original_plan('b36',prior['original_prepared_manifest']);r,p=roots('b36',args.namespace)
 require(not r.exists() and not p.exists(),'Fresh B36 metadata namespace')
 value=c.projection('b36',original,prior['original_prepared_manifest'],args.namespace,F.utc())
 require(value['jobs']==prior['jobs'] and len(value['jobs'])==40,'Exact40 original native job objects')
 p.mkdir(parents=True);r.mkdir(parents=True);mb=F.save(p/'MANIFEST.json',value);c.lineage('b36',mb['path'])
 return F.save(r/'PREPARATION.json',dict(status='PREPARED_METADATA_ONLY_NO_MODELS',manifest=mb,previous_fast_preparation=pb,requested=40,source_sec=value['total_audio_sec'],native_jobs_exact=True,lease_archival_policy=value['lease_archival_policy'],sources=c.source_bindings('b36'),models=0,native_sessions=0,scope='New explicit coordinator/schema/namespace/archive policy only; original40 job objects/settings/input bindings exact. No PCM/model hashing or native launch in prepare.'))

def child_closure(reader,plan,pb):
 output=Path(plan['output_root']);records=[];owners=[]
 require(len(plan['jobs'])==40 and len({j['job_id'] for j in plan['jobs']})==40,'Exact40 unique jobs')
 for j in plan['jobs']:
  path=output/'jobs'/j['job_id']/'COMPLETE.json';cell,cb=reader.read(path)
  require(cell['status']=='COMPLETE' and cell['job_key']==j['job_key'] and cell['all_owned_processes_closed'] is True and cell['owned_processes'],'Original native cell closure')
  records.append(dict(job_id=j['job_id'],completion=cb));owners.extend(cell['owned_processes'])
 return records,owners

def scan_counters(rows):
 # Same finite three-root relationships as held V7, without importing inventory.
 require(isinstance(rows,dict) and rows,'Actual observer scan counters required')
 allowed={str(Path(p).resolve()) for p in (REPORT,STAGING,PAYLOAD)}
 require({str(Path(p).resolve()) for p in rows}==allowed,'Exact three resource roots required')
 for r in rows.values():
  for k in ('calls','successful','failed'):require(type(r[k]) is int and r[k]>=0,'Integer scan counter required')
  require(r['calls']==r['successful']+r['failed'] and r['successful']>0 and type(r['last_bytes']) is int and r['last_bytes']>=0,'Actual admitted scan counter relationship')
  for k in ('total_wall_sec','total_cpu_sec','max_wall_sec'):require(type(r[k]) in (float,int) and math.isfinite(r[k]) and r[k]>=0,'Finite measured scan clock required')

def archive_finished_lease(lock,invocation,plan,args,me):
 croot,_=roots('b36',Path(plan['output_root']).name);target=croot/'invocations'/invocation.name
 target.mkdir(parents=True,exist_ok=False);owner=dict(pid=me.pid,creation_time=me.create_time(),argv=me.cmdline());pb=F.bind(args.manifest)
 result=None;error=None;lb=None;completion_binding=None;rows=[];observations=[]
 try:
  require(lock==REPORT/'PACED_QUIET_OWNER.json' and invocation.parent==Path(plan['output_root'])/'invocations','Exact original paths')
  lease,lb=R.read_bound(lock);R.same_owner(lease,owner);require(lease['manifest']==pb,'Exact active coordinator lease')
  expected=[str(R.EDGE),'-B',str(Path(__file__).resolve()),'run','--manifest',str(Path(args.manifest).resolve()),'--quiet-admission',str(Path(args.quiet_admission).resolve())]
  require(owner['argv']==expected,'Exact new coordinator command')
  completion,completion_binding=R.read_bound(invocation/'COMPLETION.json')
  require(completion['status']=='COMPLETE' and completion['requested']==completion['completed']==40 and completion['error'] is None and completion['manifest']==pb,'Only completed40 closure releases automatically')
  rows,children=child_closure(F.Reader(),plan,pb);observations=R.all_closed(children)
  require(not (invocation/'QUIET_OWNER_CLOSED.json').exists(),'No legacy G archive may be fabricated')
  archive=target/'PRESERVED_ORIGINAL_QUIET_LEASE.json';R.same_volume(lock,archive)
  R.verify(pb);result=R.release_function()(lock,archive,lb)
  require(result['status']=='RELEASED','Same-volume release failed or unverified')
 except BaseException:
  error=traceback.format_exc();raise
 finally:
  F.save(target/'LEASE_RELEASE.json',dict(schema='s6c-b36-paced-lease-release.v1',status='RELEASED' if error is None and result and result['status']=='RELEASED' else 'RETAINED_OR_RELEASE_UNVERIFIED',created_utc=F.utc(),owner=owner,manifest=pb,original_completion=completion_binding,original_invocation=str(invocation),source_lease=lb,lease_release=result,error=error,original_G_archive_created=False,completed_cells=rows,current_child_observations=observations,wrapper=F.bind(__file__),policy=plan['lease_archival_policy'],scope='Current explicitly registered B36 V2 coordinator; exact C-side lease archive. Coordinator can still be exiting; independent current owner checks remain required.'))

def admit_complete_batch(reader,binding,inspect=R.state):
 plan,pb=admit_plan(reader,binding);output=Path(plan['output_root']);croot,_=roots('b36',output.name)
 require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active quiet lease blocks closed-batch admission')
 invs=list((output/'invocations').iterdir());require(len(invs)==1 and invs[0].is_dir(),'One exact original invocation')
 inv=invs[0];launch,lb=reader.read(inv/'LAUNCH.json');owner={k:launch[k] for k in ('pid','creation_time')}
 R.all_closed([owner],inspect);require(launch['status']=='STARTED' and launch['manifest']==pb and launch['coordinator']==F.bind(__file__) and launch['native_driver']==plan['driver'],'Exact new coordinator launch')
 quiet,_=reader.read(launch['quiet_admission']['path'],launch['quiet_admission']);require(quiet['status']=='AUTHORIZED_FOR_QUIET_PACED' and quiet['manifest_sha256']==pb['sha256'] and quiet['all_other_model_hil_work_stopped'] is True and quiet['all_heavy_analysis_stopped'] is True,'Original exact quiet authorization')
 complete,cb=reader.read(inv/'COMPLETION.json');require(complete['status']=='COMPLETE' and complete['requested']==complete['completed']==40 and complete['error'] is None and complete['manifest']==pb,'Exact40 original completion')
 release,rb=reader.read(croot/'invocations'/inv.name/'LEASE_RELEASE.json')
 require(release['schema']=='s6c-b36-paced-lease-release.v1' and release['status']=='RELEASED' and release['error'] is None and release['manifest']==pb and release['original_completion']==cb and release['wrapper']==F.bind(__file__) and release['policy']==plan['lease_archival_policy'],'Explicit successful C release receipt')
 R.same_owner(release['owner'],owner)
 require(release['original_invocation']==str(inv) and release['original_G_archive_created'] is False and not (inv/'QUIET_OWNER_CLOSED.json').exists(),'Original G archive remains absent')
 r=release['lease_release'];expected_archive=croot/'invocations'/inv.name/'PRESERVED_ORIGINAL_QUIET_LEASE.json'
 require(r['status']=='RELEASED' and r['released'] is True and r['error'] is None and r['source']==release['source_lease'] and Path(r['source']['path'])==REPORT/'PACED_QUIET_OWNER.json' and Path(r['requested_archive'])==expected_archive and r['archived_binding']=={**r['source'],'path':str(expected_archive)},'Exact source/archive byte lineage')
 lease,archive_binding=reader.read(expected_archive,r['archived_binding']);R.same_owner(lease,owner);require(lease['manifest']==pb,'Archived original lease identity')
 rows,children=child_closure(reader,plan,pb);require(rows==release['completed_cells'],'Exact40 receipt references')
 require([R.finite_owner(x['owner']) for x in release['current_child_observations']]==[R.finite_owner(x) for x in children] and all(x['observation']==dict(alive=False,error=None) for x in release['current_child_observations']),'Exact original released child observations')
 current=R.all_closed(children,inspect)
 scans=list((croot/'observer_invocations').glob('*/SCANNER_OUTCOME.json'));require(len(scans)==1,'One actual observer exit')
 scan,sb=reader.read(scans[0]);R.same_owner(scan['owner'],owner)
 require(scan['schema']=='s6c-historical-fast-observer-outcome.v1' and type(scan['coordinator_pid']) is int and scan['coordinator_pid']==owner['pid'],'Exact historical observer schema/coordinator PID')
 scan_counters(scan['storage_scans'])
 sources=context().source_bindings('b36')
 require(scan['status']=='COMPLETE' and scan['error'] is None and scan['manifest']==pb and scan['entry']=='run' and scan['wrapper']==F.bind(__file__) and scan['sources_before']==scan['sources_after']==sources and scan['sources_unchanged'] is True,'Exact successful observer exit sources')
 require(scan['owner']==release['owner'] and scan['owner']['argv']==[str(R.EDGE),'-B',str(Path(__file__).resolve()),'run','--manifest',pb['path'],'--quiet-admission',launch['quiet_admission']['path']],'Exact coordinator argv throughout')
 return dict(status='B36_NATIVE_BATCH_COMPLETE_WITH_EXPLICIT_C_ARCHIVE',manifest=pb,cells=40,owner=release['owner'],launch=lb,completion=cb,lease_release=rb,archived_lease=archive_binding,observer_exit=sb,completed_cells=rows,current_child_observations=current,scope='Original native COMPLETE metadata and explicit V2 current-coordinator C archive; scientific payload analysis remains separate.')

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['prepare','run']);p.add_argument('--source-manifest');p.add_argument('--source-sha256');p.add_argument('--namespace');p.add_argument('--manifest',type=Path);p.add_argument('--quiet-admission',type=Path);a=p.parse_args()
 for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
 os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
 if a.action=='prepare':value=prepare(a)
 else:
  require(a.manifest is not None and a.quiet_admission is not None,'Exact run manifest/quiet authority required');value=context().execute('b36',a)
 print(json.dumps(value,indent=2))
if __name__=='__main__':main()
