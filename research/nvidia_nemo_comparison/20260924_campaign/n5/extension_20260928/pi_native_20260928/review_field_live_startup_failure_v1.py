"""Missing packaged ALSA file, no capture; README_FIELD_LIVE_GUI_V2.md."""
import hashlib,io,json,psutil,subprocess,tarfile
from pathlib import Path,PurePosixPath
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main():
    psutil.Process().cpu_affinity([14]);run='field-live-gui-v1'
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import json,hashlib,fcntl,subprocess
from pathlib import Path
r=Path(ROOT);d=r/'field-live-gui-v1'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());dispatch=json.loads((d/'DISPATCH_RESULT.json').read_text())
assert dispatch['exit_code']==1 and not dispatch['log_overflow'] and not dispatch['memory_guard']
assert not (d/'RESULT.json').exists() and not (d/'data/source_receipts').exists() and not (d/'data/sessions').exists()
assert 'FileNotFoundError' in (d/'service.log').read_text() and 'config/alsa_hw_only_v1.conf' in (d/'service.log').read_text()
assert not (Path(a['installed_release'])/'config/alsa_hw_only_v1.conf').exists()
for row in a['files']:assert sha(Path(row['path']))==row['sha256']
for p in d.glob('*OWNER.json'):
 o=json.loads(p.read_text());assert ticks(o['pid'])!=o['start_ticks']
assert ticks(1013)==569 and ticks(1130)==607
for path,key in [('install/current.json','install_sha256'),('data/live_config.json','live_config_sha256')]:assert sha(Path.home()/'JustPeachy'/path)==a[key]
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
for p in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
env=json.loads((d/'LIVE_ENVELOPE.json').read_text());assert env['address_space']==[768*1024**2]*2 and env['stack']==[1048576]*2 and env['affinity']==[2,3]
assert not any(p.is_symlink() for p in d.rglob('*'))
files={p.relative_to(d).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in d.rglob('*') if p.is_file()}
print(json.dumps(dict(files=files,summary=dict(status='REVIEWED_INSTALLED_ALSA_PACKAGING_PRE_GUI_FAILURE_ONLY',exit_code=1,capture_opened=False,model_inference=False,GUI_opened=False,owners_closed=True,baseline_unchanged=True,leases_free=True,installed_files_unchanged=True,live_envelope=env,source_missing='config/alsa_hw_only_v1.conf'))))
''')
    out=PRIVATE/(run+'-evidence');backup=out/'target';backup.mkdir();seen=set()
    raw=subprocess.check_output(SSH+['tar -C '+REMOTE+'/'+run+' -cf - .'],timeout=60)
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
        for item in archive:
            if item.isdir():continue
            assert item.name.startswith('./');name=item.name[2:];p=PurePosixPath(name)
            assert item.isfile() and not p.is_absolute() and '..' not in p.parts and name in x['files'] and name not in seen
            data=archive.extractfile(item).read();v=x['files'][name]
            assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256']
            path=backup.joinpath(*p.parts);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as f:f.write(data)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==v['sha256'];seen.add(name)
    assert seen==set(x['files'])
    x['summary'].update(backup_files=len(seen),backup_bytes=sum(v['bytes'] for v in x['files'].values()),private_backup_verified=True)
    for name,value in [('REVIEW.json',x['summary']),('BACKUP.json',x['files'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in x['summary'].items() if k!='live_envelope'}))


if __name__=='__main__':main()
