"""One exact externally reviewed lease recovery; README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md."""
from __future__ import annotations
import argparse,ast,hashlib,json,math,os,re,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
import psutil

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
EDGE=HERE.parent.parents[2]/'.edge-speech-env/python.exe'
DEADLINE=datetime(2026,9,13,11,35,40,tzinfo=timezone.utc)
AUDIT_PATH=REPORT/'runtime_failure_review/CONTROLS_FAST_V1_ARCHIVE_FAILURE_OWNER_AUDIT_V1.json'
AUDIT_SHA='74a60af5483852cae05ac156c7c251a4890b684d737e080b22be01080c2ea914'
SCANNER_PATH=REPORT/'paced_controls/controls_fast_v1/observer_invocations/00b920723e3e45ff8865cbd3eb574cc6/SCANNER_OUTCOME.json'
SCANNER_SHA='99cb60a62e8bdbfc2b2e9666fa368604395b4f3e0837cf56e20535efa7614591'
LEASE_SHA='9dfcfa166cecad8b4edfaf1b64f867f3485de18c8d7a8cf7c9cb8e6563ca44f3'
RELEASE_SOURCE=HERE/'s6c_long_native_epoch4_fast_v2.py'
RELEASE_SHA='079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67'

def require(v,m):
 if not v:raise ValueError(m)
def utc():return datetime.now(timezone.utc).isoformat()
def bind(p,raw=None):
 p=Path(p).resolve();raw=p.read_bytes() if raw is None else raw
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read_bound(p,expected=None):
 p=Path(p).resolve();require(p.stat().st_size<=2**20,'Bounded metadata only');raw=p.read_bytes();require(len(raw)<=2**20,'Metadata size cap');b=bind(p,raw)
 if expected is not None:require(b==expected,'Exact metadata binding differs')
 return json.loads(raw.decode('utf-8-sig')),b
def verify(expected):read_bound(expected['path'],expected)
def save(p,v):
 p=Path(p);raw=(json.dumps(v,indent=2,allow_nan=False)+'\n').encode();p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return bind(p,raw)
def finite_owner(o):
 require(type(o['pid']) is int and o['pid']>0 and type(o['creation_time']) in (int,float) and math.isfinite(o['creation_time']) and o['creation_time']>0,'Exact finite process identity required')
 return o['pid'],o['creation_time']
def same_owner(a,b):require(finite_owner(a)==finite_owner(b),'Owner identity differs')
def state(o):
 finite_owner(o)
 try:
  p=psutil.Process(o['pid']);return dict(alive=p.create_time()==o['creation_time'] and p.is_running(),error=None)
 except psutil.NoSuchProcess:return dict(alive=False,error=None)
 except (psutil.Error,OSError) as exc:return dict(alive=None,error=repr(exc))
def all_closed(owners,inspect=state):
 rows=[dict(owner=o,observation=inspect(o)) for o in owners]
 require(rows and all(r['observation']['alive'] is False and r['observation'].get('error') is None for r in rows),'Live or unverified original owner; lease retained')
 return rows
def release_function():
 raw=RELEASE_SOURCE.read_bytes();require(hashlib.sha256(raw).hexdigest()==RELEASE_SHA,'Reviewed release source changed')
 node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='release_lease')
 ns=dict(Path=Path,verify=verify,read_bound=read_bound,traceback=traceback)
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(RELEASE_SOURCE),'exec'),ns)
 return ns['release_lease']
def same_volume(lock,target):
 lock=Path(lock);target=Path(target)
 require(lock.is_absolute() and target.is_absolute() and lock.resolve()==lock and target.resolve()==target,'Absolute unaliased paths required')
 require(lock.drive.casefold()==target.drive.casefold() and lock.stat().st_dev==target.parent.stat().st_dev,'Lease archive must be on exact source volume')
 require(not target.exists(),'Fresh archive target required')
def validate_chain(audit,manifest,launch,completion,lease,quiet,dispatch,scanner):
 require(audit['schema']=='s6c-historical-archive-failure-owner-audit.v1' and audit['status']=='COMPLETE_GRID_AND_OWNERS_CLOSED_ARCHIVE_FAILED','Exact failure-audit scope')
 require(audit['requested']==audit['completed_cells']==80 and audit['owned_observations']==160 and audit['archival_performed'] is False and audit['lease_removed'] is False,'Exact original80 audit')
 require(completion['status']=='COMPLETE' and completion['completed']==completion['requested']==80 and completion['error'] is None,'Original cells incomplete')
 require(lease['manifest']==launch['manifest']==completion['manifest']==audit['manifest'],'Manifest chain differs')
 same_owner(lease,launch);same_owner(launch,audit['original_owner'])
 require(launch['quiet_admission']==audit['quiet_admission'] and quiet['manifest_sha256']==audit['manifest']['sha256'],'Original quiet admission differs')
 require(dispatch['status']=='STOPPED_REQUIRES_ROOT_REVIEW' and dispatch['active_item']=='controls_fast_v1' and dispatch['child_returncode']==1 and dispatch['error'],'Original dispatcher failure must remain explicit')
 same_owner(dispatch['possible_child'],lease)
 require(scanner['status']=='FAILED' and scanner['error']=="OSError(18, 'The system cannot move the file to a different disk drive')" and scanner['sources_unchanged'] is True and scanner['manifest']==audit['manifest'],'Exact historical observer archival failure required')
 same_owner(scanner['owner'],lease)
 require(scanner['owner']['argv']==audit['original_owner']['argv'],'Observer command differs')
 require(audit['owner_observation']==dict(alive=False,error=None) and audit['dispatcher_observation']==dict(alive=False,error=None),'Original parent observations unresolved')
 jobs={j['job_id']:j for j in manifest['jobs']};rows=audit['rows']
 require(len(jobs)==len(manifest['jobs'])==len(rows)==80 and len({r['job_id'] for r in rows})==80 and {r['job_id'] for r in rows}==set(jobs),'Exact unique80 grid')
 owners=[audit['original_owner'],dispatch['owner']]
 for r in rows:
  require(r['completion']['path']==str(Path(manifest['output_root'])/'jobs'/r['job_id']/'COMPLETE.json'),'Exact completion path')
  require(r['owners'] and all(x['observation']==dict(alive=False,error=None) for x in r['owners']),'Historical child observation unresolved')
  owners.extend(x['owner'] for x in r['owners'])
 require(len(owners)==162,'Exact160 child observations plus2 parents')
 for owner in owners:finite_owner(owner)
 return jobs,owners

def recover(args):
 require(Path(sys.executable).resolve()==EDGE.resolve(),'Exact EDGE interpreter required')
 auth,ab=read_bound(Path(args.authority[0]).resolve());require(ab['sha256']==args.authority[1],'Explicit authority SHA differs')
 require(auth['schema']=='s6c-external-historical-lease-release-authority.v1' and auth['status']=='AUTHORIZED_EXACT_EXTERNAL_LEASE_ARCHIVE','Explicit root recovery authority required')
 require(auth['helper']==bind(__file__) and auth['readme']==bind(HERE/'README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md'),'Exact reviewed recovery source/docs required')
 expires=datetime.fromisoformat(auth['expires_utc'].replace('Z','+00:00'));require(expires.tzinfo is not None and datetime.now(timezone.utc)<expires<=DEADLINE,'Recovery authority time bound')
 namespace=auth['namespace'];require(re.fullmatch(r'[A-Za-z0-9_-]{1,64}',namespace),'Simple fresh recovery namespace')
 out=REPORT/'runtime_failure_review/external_lease_recovery'/namespace;require(not out.exists(),'No recovery retry or overwritten evidence')
 audit,ap=read_bound(AUDIT_PATH);require(ap['sha256']==AUDIT_SHA and auth['root_audit']==ap,'Exact independently bound root audit')
 scanner,sb=read_bound(SCANNER_PATH);require(sb['sha256']==SCANNER_SHA,'Original failed observer binding')
 inputs={k:read_bound(audit[k]['path'],audit[k])[0] for k in ('manifest','launch','completion','quiet_admission','failed_dispatcher')}
 lock=REPORT/'PACED_QUIET_OWNER.json';lease,lb=read_bound(lock,audit['preserved_active_lease']);require(lb['sha256']==LEASE_SHA,'Exact preserved active lease')
 original_archive=Path(audit['expected_archive']);require(original_archive==Path(audit['launch']['path']).with_name('QUIET_OWNER_CLOSED.json') and not original_archive.exists(),'Original absent archive must remain absent')
 jobs,owners=validate_chain(audit,inputs['manifest'],inputs['launch'],inputs['completion'],lease,inputs['quiet_admission'],inputs['failed_dispatcher'],scanner)
 # These are compact COMPLETE JSONs only; no declared native payloads are opened.
 for row in audit['rows']:
  cell,_=read_bound(row['completion']['path'],row['completion']);require(cell['status']=='COMPLETE' and cell['job_key']==jobs[row['job_id']]['job_key'] and cell['all_owned_processes_closed'] is True,'Exact original cell completion')
  require([finite_owner(o) for o in cell['owned_processes']]==[finite_owner(x['owner']) for x in row['owners']],'Original child identities changed')
 observed=all_closed(owners);release=release_function()
 out.mkdir(parents=True,exist_ok=False);archive=out/'PRESERVED_ORIGINAL_QUIET_LEASE.json';same_volume(lock,archive)
 me=psutil.Process();recovery_owner=dict(pid=me.pid,creation_time=me.create_time(),argv=me.cmdline())
 admission=save(out/'ADMISSION.json',dict(schema='s6c-external-lease-recovery-admission.v1',status='EXACT_OWNER_BOUND_RECOVERY_ADMITTED',created_utc=utc(),owner=recovery_owner,authority=ab,root_audit=ap,failed_observer=sb,source=bind(__file__),readme=bind(HERE/'README_S6C_EXTERNAL_LEASE_RECOVERY_V1.md'),release_source=bind(RELEASE_SOURCE),lease=lb,requested_archive=str(archive),original_missing_archive=str(original_archive),original_owners=observed,scope='External lease housekeeping only. Native80 complete; original coordinator/scanner failure is preserved.'))
 # Recheck immutable evidence, source and current owners immediately before rename.
 verify(ab);verify(ap);verify(sb)
 for k in ('manifest','launch','completion','quiet_admission','failed_dispatcher'):verify(audit[k])
 require(datetime.now(timezone.utc)<expires,'Recovery authority expired before mutation')
 require(not original_archive.exists(),'Original archive appeared during recovery')
 observed=all_closed(owners);same_volume(lock,archive);verify(lb);require(bind(RELEASE_SOURCE)['sha256']==RELEASE_SHA and auth['helper']==bind(__file__),'Release source changed')
 result=release(lock,archive,lb)
 rb=save(out/'RESULT.json',dict(schema='s6c-external-historical-lease-recovery.v1',status='EXTERNAL_ARCHIVE_RELEASED' if result['status']=='RELEASED' else 'EXTERNAL_ARCHIVE_FAILED_OR_UNVERIFIED',created_utc=utc(),owner=recovery_owner,admission=admission,authority=ab,root_audit=ap,failed_observer=sb,manifest=audit['manifest'],original_launch=audit['launch'],original_completion=audit['completion'],original_dispatcher_failure=audit['failed_dispatcher'],original_coordinator_exit_code=1,original_scanner_status='FAILED',original_missing_archive=str(original_archive),original_archive_created=False,lease_release=result,current_original_owner_observations=observed,models_started=0,native_sessions_started=0,scope='External same-volume rename of exact original bytes; not an original successful coordinator closure. V7/post-analysis requires an explicit separate recovery overlay; no scientific arithmetic or payload verified here.'))
 require(result['status']=='RELEASED','Recovery failed or archive binding unverified; preserve result and stop')
 return rb

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['recover']);p.add_argument('--authority',nargs=2,required=True,metavar=('PATH','SHA256'));print(json.dumps(recover(p.parse_args()),indent=2))

