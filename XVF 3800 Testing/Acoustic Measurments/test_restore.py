from pathlib import Path
import json, zipfile, hashlib, subprocess

stage = Path(__file__).resolve().parent
root = stage/'restore_test_v2'
root.mkdir(exist_ok=False)
payload = b'XVF lossless restoration fixture\x00\x01\xff'
digest = hashlib.sha256(payload).hexdigest()
with zipfile.ZipFile(root/'fixture.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('objects/'+digest,payload)
files = [{'path':p,'bytes':len(payload),'mtime_ns':1750000000000000000,'sha256':digest} for p in ['project/a.bin','project/nested/copy.bin']]
manifest = {'format':'XVF lossless deduplicated ZIP v1','files':files,'directories':['project/empty'],'logical_bytes':2*len(payload)}
(root/'manifest.json').write_text(json.dumps(manifest))
def run(dest, m='manifest.json'):
    return subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(stage/'Restore-XVF.ps1'),
        '-Destination',str(root/dest),'-ArchivePath',str(root/'fixture.zip'),'-ManifestPath',str(root/m)], capture_output=True, text=True,creationflags=subprocess.CREATE_NO_WINDOW)
good = run('restored')
assert good.returncode == 0, good.stdout+good.stderr
assert (root/'restored/project/a.bin').read_bytes() == payload
assert (root/'restored/project/nested/copy.bin').read_bytes() == payload
assert (root/'restored/project/empty').is_dir()
assert json.loads((root/'restored/RESTORE_VERIFICATION.json').read_text(encoding='utf-8-sig'))['verified_files'] == 2
assert run('restored').returncode != 0
manifest['files'][0]['path'] = 'project/../../escaped.bin'
(root/'bad_manifest.json').write_text(json.dumps(manifest))
bad = run('rejected', 'bad_manifest.json')
assert bad.returncode != 0 and not (root/'rejected').exists()
(stage/'RESTORE_TEST_RESULT.json').write_text(json.dumps({'status':'PASS','checks':['unique file extraction','duplicate restoration','exact bytes and SHA-256','empty directory preservation','existing destination rejection','traversal rejected before writes']},indent=2))
print('PASS: restoration, byte integrity, duplicate copies, empty directories, existing target protection and traversal rejection.')
