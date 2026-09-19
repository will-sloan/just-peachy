from pathlib import Path
import json, subprocess, hashlib
stage=Path(__file__).resolve().parent
manifest=json.loads((stage/'RESTORE_MANIFEST.json').read_text())
selected=[manifest['files'][0],manifest['files'][-1]]
test_manifest={'format':manifest['format'],'files':selected,'directories':[],'logical_bytes':sum(r['bytes'] for r in selected)}
path=stage/'full_archive_reader_test_manifest.json'
path.write_text(json.dumps(test_manifest))
dest=stage/'full_archive_reader_test'
process=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(stage/'Restore-XVF.ps1'),
    '-Destination',str(dest),'-ArchivePath',str(stage/'XVF_DATA.zip'),'-ManifestPath',str(path)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
assert process.returncode==0,process.stdout+process.stderr
for r in selected:assert hashlib.sha256((dest/r['path']).read_bytes()).hexdigest()==r['sha256']
report=json.loads((stage/'RESTORE_TEST_RESULT.json').read_text())
report['checks'].append('Windows PowerShell/.NET extraction of first and last source objects from the complete production archive')
(stage/'RESTORE_TEST_RESULT.json').write_text(json.dumps(report,indent=2))
print('PASS: Windows restore tool reads and verifies objects from the complete production archive.')
