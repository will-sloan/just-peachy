"""External finite selected export from an unchanged package. README_NATIVE_EXPORT.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

DRIVER = r'''
import hashlib,json,os,resource,sys
from pathlib import Path
# The common wrapper registered actual OWNER before importing this entry.
out=Path(sys.argv[1]);package=Path(sys.argv[2]);session_id=sys.argv[3];data=Path(sys.argv[4])
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
from storage import SessionStore,StoragePolicy
binding=json.loads((package/'BINDING.json').read_bytes())
store=SessionStore(data,StoragePolicy(**binding.get('storage_policy',{})))
try:
 before=store.read(session_id)
 if before['status']!='kept':raise ValueError('Selected existing kept session required')
 path=store.export([session_id],out/'selected-recording.zip')
 with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
 size=path.stat().st_size
 if store.read(session_id)!=before:raise ValueError('Original selected recording metadata changed')
 value=dict(schema='just-peachy.native-selected-export.v1',status='EXPORTED',session_id=session_id,
  source_root=str(data),zip_path=str(path),zip_bytes=size,zip_sha256=sha,
  original_session_preserved=True,source_deleted=False,capture=False,models_loaded=False)
 raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 with (out/'EXPORT.json').open('xb') as f:
  if f.write(raw)!=len(raw):raise OSError('Short export receipt')
  f.flush();os.fsync(f.fileno())
 if (out/'EXPORT.json').read_bytes()!=raw:raise OSError('Export receipt readback')
finally:store.close()
'''


def export_wrapper(shared,settings):
    """Recognize only Store.export's two-name atomic publication transaction."""
    source=shared(settings)
    start="def bounded_output():\n total=count=0\n"
    if source.count(start)!=1:raise ValueError('Exact shared output-guard derivation boundary')
    source=source.replace(start,start+" archive_inodes=set()\n")
    boundary="   if path.is_symlink() or info.st_nlink!=1 or count>SETTINGS['budget'].get('maximum_files',256):raise ValueError('Output membership bound')\n   total+=info.st_size"
    replacement=r'''   archive=(path.parent==out and (name=='selected-recording.zip' or
    name.startswith('selected-recording.zip.part-') and len(name)==60 and all(c in '0123456789abcdef' for c in name[-32:])))
   if path.is_symlink() or count>SETTINGS['budget'].get('maximum_files',256):raise ValueError('Output membership bound')
   if info.st_nlink!=1:
    if not archive or info.st_nlink!=2:raise ValueError('Unrecognized output hardlink')
    peers=[]
    for candidate in out.iterdir():
     if candidate==path:continue
     if candidate.name=='selected-recording.zip' or (candidate.name.startswith('selected-recording.zip.part-') and len(candidate.name)==60 and all(c in '0123456789abcdef' for c in candidate.name[-32:])):
      try:other=candidate.lstat()
      except FileNotFoundError:continue
      if (other.st_dev,other.st_ino)==(info.st_dev,info.st_ino):peers.append(candidate)
    # Publication may have completed between lstat and this exact peer check.
    try:current=path.lstat()
    except FileNotFoundError:continue
    if len(peers)!=1 and current.st_nlink!=1:raise ValueError('Export publication peer differs')
   if archive:
    key=(info.st_dev,info.st_ino)
    if key in archive_inodes:continue
    archive_inodes.add(key)
   total+=info.st_size'''
    if source.count(boundary)!=1:raise ValueError('Exact shared member-guard derivation boundary')
    source=source.replace(boundary,replacement)
    compile(source,'<owned-selected-export-wrapper>','exec')
    return source


def dispatch(p, baseline):
    if baseline.get('current_project_processes') or baseline.get('active_recorded_owners') or baseline.get('live_manager_owners'):
        raise ValueError('Fresh full existing source/owner closure required')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if p['boot_id']!=boot or not time.time()<p['expires_unix']<=time.time()+600:
        raise ValueError('Fresh exact boot admission required')
    package=Path(p['package'])
    campaign=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
    if package.parent!=campaign or re.fullmatch(r'field-runtime-v29-build-\d{2}',package.name) is None:
        raise ValueError('Explicit immutable source package required')
    raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=p['package_manifest_sha256']:
        raise ValueError('Pinned complete package required')
    manifest=json.loads(raw)
    entry=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
    helper_path=package/entry['path'];source=helper_path.read_bytes()
    if (helper_path.resolve(strict=True)!=helper_path or len(source)!=entry['bytes'] or
        hashlib.sha256(source).hexdigest()!=entry['sha256'] or len(source)>131072):
        raise ValueError('Exact immutable shared wrapper required')
    namespace=dict(__name__='verified_export_helper',__file__=str(helper_path))
    exec(compile(source,str(helper_path),'exec'),namespace)
    namespace['inventory'](package,p['package_manifest_sha256'])
    binding=json.loads((package/'BINDING.json').read_bytes())
    if binding['target']!=str(package):raise ValueError('Exact export package target required')
    label=p['label']
    if re.fullmatch(r'recording-export-\d{2}',label) is None or re.fullmatch(r'[0-9a-f]{32}',p['session_id']) is None:
        raise ValueError('Fresh export label and exact selected session ID required')
    if type(p['maximum_output_bytes']) is not int or not 16*1024**2<=p['maximum_output_bytes']<=256*1024**2:
        raise ValueError('Explicit full ZIP plus16MiB overhead reservation required, maximum256MiB')
    old_job=p['source_job'];source_root=Path(old_job['output_root'])
    if (re.fullmatch(r'gui-qualification-\d{2}',source_root.name) is None or
        old_job['unit']!='jp-v29-'+source_root.name+'.service' or
        old_job['package_manifest_sha256']!=p['package_manifest_sha256'] or
        Path(p['recordings_root'])!=source_root/'data/recordings'):
        raise ValueError('Exact closed GUI job recording root/package required')
    # Use the existing independently owned systemd helper, retaining its utility
    # receipts inside this action result instead of printing protocol frames.
    probe=namespace['load_pure'](package,'native_job_probe');utilities=[];probe.emit=utilities.append
    _,closed=probe.inspect(old_job)
    if not all(closed.get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty')):
        raise ValueError('Selected source job has not actually closed')
    if shutil.disk_usage(campaign).free<5*1024**3+p['maximum_output_bytes']:
        raise OSError('Native floor plus independent exported ZIP allocation unavailable')
    unit='jp-v29-'+label+'.service';out=campaign/'live-runtime-tests-20261003'/label
    old=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],capture_output=True,text=True,timeout=5)
    if old.stdout.strip()!='LoadState=not-found':raise ValueError('Fresh unique export unit required')
    if out.parent.resolve(strict=True)!=out.parent:raise ValueError('Canonical existing output parent required')
    out.mkdir()
    put=namespace['put'];sha=namespace['sha']
    settings=dict(output=str(out),package=str(package),unit=unit,boot_id=boot,expires_unix=p['expires_unix'],
        package_manifest_sha256=p['package_manifest_sha256'],scope_sha256=sha(package/'native_scope.py'),
        research_lock=str(campaign/'B05_PREVIEW_DISPATCH.lock'),kind='selected_export',template=None,
        budget=dict(maximum_output_bytes=p['maximum_output_bytes'],runtime_seconds=180,stop_seconds=30,
            file_limit_bytes=p['maximum_output_bytes']-8*1024**2),
        argv=[str(out/'export_driver.py'),str(out),str(package),p['session_id'],p['recordings_root']])
    wrapper=export_wrapper(namespace['wrapper_source'],settings).encode()
    for name,data in (('export_driver.py',DRIVER.encode()),('wrapper.py',wrapper)):
        with (out/name).open('xb') as stream:
            if stream.write(data)!=len(data):raise OSError('Short export preparation write')
            stream.flush();os.fsync(stream.fileno())
        if (out/name).read_bytes()!=data:raise OSError('Export preparation readback')
    put(out/'ADMISSION.json',dict(payload=p,closed_source=closed,source_probe_utilities=utilities,
        export_driver_sha256=hashlib.sha256(DRIVER.encode()).hexdigest(),wrapper_sha256=hashlib.sha256(wrapper).hexdigest(),
        native_reservation_bytes=p['maximum_output_bytes'],independent_host_reservation_bytes=p['maximum_output_bytes'],
        capture=False,models_loaded=False,source_package_modified=False))
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachySelectedExport',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec=180','--property=TimeoutStopSec=30','--property=KillMode=control-group',
        '--setenv=PYTHONDONTWRITEBYTECODE=1',binding['python'],'-B',str(out/'wrapper.py')]
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    put(out/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:raise RuntimeError('Selected export unit failed to launch')
    end=time.monotonic()+5
    while not (out/'OWNER.json').exists() and time.monotonic()<end:time.sleep(.05)
    owner=json.loads((out/'OWNER.json').read_bytes()) if (out/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],
        capture_output=True,text=True,timeout=5,check=True)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    job=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,owner=owner,
        invocation_id=props.get('InvocationID'),control_group=props.get('ControlGroup'),properties=props,
        output_root=str(out),maximum_output_bytes=p['maximum_output_bytes'],
        package_manifest_sha256=p['package_manifest_sha256'],issued_unix=time.time(),deadline_unix=time.time()+225)
    put(out/'JOB.json',job);return job


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
