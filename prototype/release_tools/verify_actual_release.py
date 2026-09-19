"""Build/stage actual source and execute bounded relocation checks without a microphone."""
from __future__ import annotations
import argparse
import difflib
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
from release import activate,build,digest,healthcheck,inspect_archive,now,rollback,stage,verify_assets,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('source','output','root','models','wav','evidence'):
        p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--version',required=True)
    p.add_argument('--baseline-archive',type=Path)
    p.add_argument('--receipt-name',default='ACTUAL_RELEASE_RESULTS.json')
    p.add_argument('--focused-contracts',action='store_true')
    a=p.parse_args();a.evidence.mkdir(parents=True,exist_ok=True)
    receipt=build(a.source,a.output,a.version)
    archive=Path(receipt['archive']);manifest=inspect_archive(archive)
    staged=stage(archive,a.root,receipt['sha256']);release=Path(staged['path'])
    assets=verify_assets(release,a.models)
    delta=None
    if a.baseline_archive:
        baseline=inspect_archive(a.baseline_archive)
        old={r['path']:r for r in baseline['files']};new={r['path']:r for r in manifest['files']}
        changes=[dict(path=name,before=old.get(name),after=new.get(name)) for name in sorted(set(old)|set(new))
                 if old.get(name)!=new.get(name)]
        runtime_changes=[r for r in changes if r['path'].endswith('.py') and (r['path']=='main.py' or r['path'].startswith(('app/','vendor/')))]
        chunks=[]
        with zipfile.ZipFile(a.baseline_archive) as prior,zipfile.ZipFile(archive) as current:
            for row in runtime_changes:
                name=row['path'];before=prior.read(name).decode('utf-8').splitlines(keepends=True) if name in old else []
                after=current.read(name).decode('utf-8').splitlines(keepends=True) if name in new else []
                chunks.extend(difflib.unified_diff(before,after,fromfile=baseline['version']+'/'+name,tofile=a.version+'/'+name))
        patch=a.evidence/'RC_TO_FINAL.patch';patch.write_text(''.join(chunks),encoding='utf-8')
        delta=dict(baseline_version=baseline['version'],baseline_archive=str(a.baseline_archive),baseline_sha256=digest(a.baseline_archive),
            changed_payload_files=changes,changed_runtime_files=[r['path'] for r in runtime_changes],
            runtime_patch=dict(path=str(patch),sha256=digest(patch),bytes=patch.stat().st_size),
            unchanged_runtime_count=sum(1 for name in old if name in new and old[name]==new[name] and name.endswith('.py') and (name=='main.py' or name.startswith(('app/','vendor/')))))
    installer_data=a.root/'Installer synthetic data'
    activate(a.root,installer_data,a.version)
    sentinel=installer_data/'people'/'SYNTHETIC_PRIVATE_SENTINEL.txt'
    sentinel.parent.mkdir();sentinel.write_bytes(b'SYNTHETIC fixture: rollback must preserve these bytes.\n')
    sentinel_hash=digest(sentinel)
    # Rollback exercise changes only release metadata/version. Every application
    # payload byte remains exactly the original archive; this is not a new app.
    fixture_version=a.version+'-rollback-fixture'
    fixture_archive=a.output/f'just-peachy-{fixture_version}.zip'
    fixture_manifest=deepcopy(manifest);fixture_manifest['version']=fixture_version
    fixture_manifest['fixture_notice']='Installer rollback metadata fixture; application payload identical to '+a.version
    with zipfile.ZipFile(archive) as src,zipfile.ZipFile(fixture_archive,'x',zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            dst.writestr(name,json.dumps(fixture_manifest,indent=2)+'\n' if name=='RELEASE_MANIFEST.json' else src.read(name))
    stage(fixture_archive,a.root,digest(fixture_archive))
    activate(a.root,installer_data,fixture_version)
    rolled=rollback(a.root,installer_data)
    if rolled['version']!=a.version or digest(sentinel)!=sentinel_hash:raise RuntimeError('Rollback altered code selection/private fixture')
    health=healthcheck(a.root,installer_data,check_imports=True)
    checks=[]

    def run(name,command,data,env=None,timeout=150):
        started=time.monotonic()
        result=subprocess.run(command,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        (a.evidence/(name+'.txt')).write_text(result.stdout+result.stderr,encoding='utf-8')
        closed=Path(data)/'last_application.json'
        row=dict(name=name,exit_code=result.returncode,elapsed_s=time.monotonic()-started,
            application_lock_released=not (Path(data)/'runtime.lock').exists(),closure_receipt=str(closed),
            closure_recorded=closed.is_file(),command=[str(x) for x in command])
        if closed.is_file():
            closure=json.loads(closed.read_text(encoding='utf-8'))
            row['microphone_open_at_close']=closure['microphone_open']
        row['status']='PASS' if result.returncode==0 and row['application_lock_released'] and row['closure_recorded'] and not row.get('microphone_open_at_close',True) else 'FAIL'
        checks.append(row)
        if row['status']!='PASS':raise RuntimeError(f'{name} failed: {result.stderr[-1500:]}')

    native_data=a.root/'Relocated native test data'
    result_path=a.evidence/'RELOCATED_C105_RESULT.json'
    run('relocated_native_C105', [sys.executable,str(release/'main.py'),'file','--wav',str(a.wav),
        '--data-root',str(native_data),'--models',str(a.models),'--mode','caption_only','--recipe','fast','--tap','O0','--result',str(result_path)],native_data)
    native=json.loads(result_path.read_text(encoding='utf-8'))
    if not native['rows'] or native['error'] or native['metrics'].get('model_cache',{}).get('asr_loads')!=1:
        raise RuntimeError('Relocated native inference did not produce an error-free caption result with one ASR load')
    # Only these child launcher checks see this external, disclosed test hook.
    hook=a.root/'Launcher test hook';hook.mkdir()
    (hook/'sitecustomize.py').write_text('''import tkinter as tk\n_original_init=tk.Tk.__init__\n_original_loop=tk.Tk.mainloop\ndef init(self,*a,**k):\n _original_init(self,*a,**k);self.withdraw()\ndef loop(self,*a,**k):\n self.withdraw()\n self.after(1000,lambda:self.tk.call(self.protocol("WM_DELETE_WINDOW"))))\n return _original_loop(self,*a,**k)\ntk.Tk.__init__=init\ntk.Tk.mainloop=loop\n'''.replace('))))',')))'),encoding='utf-8')
    (hook/'README.md').write_text('External launcher-test hook only. Python imports sitecustomize through a child-only PYTHONPATH; it withdraws Tk and invokes the normal WM_DELETE_WINDOW close callback after one second. No Start/microphone/model action is invoked. Not included in the release. Reproduce via verify_actual_release.py; normal launches do not set this path.\n',encoding='utf-8')
    env=os.environ.copy();env.update(PYTHONPATH=str(hook),JUST_PEACHY_PYTHON=sys.executable,JUST_PEACHY_MODELS=str(a.models))
    ps_data=a.root/'PowerShell launcher test data'
    run('actual_powershell_launcher', ['powershell.exe','-NoProfile','-File',str(release/'Start-Prototype.ps1'),'-Python',sys.executable,
        '-DataRoot',str(ps_data),'-Models',str(a.models)],ps_data,env)
    cmd_data=a.root/'CMD launcher test data';env['JUST_PEACHY_DATA']=str(cmd_data)
    run('actual_cmd_launcher', ['cmd.exe','/d','/c',str(release/'Start-Prototype.cmd')],cmd_data,env)
    contracts=None
    if a.focused_contracts:
        contract_output=a.evidence/'RELOCATED_CONTRACT_RESULTS.json'
        completed=subprocess.run([sys.executable,str(Path(__file__).with_name('run_relocated_contracts.py')),
            '--release',str(release),'--tests',str(a.source/'tests'),'--harness',str(a.root/'Relocated contract sources'),
            '--output',str(contract_output)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        (a.evidence/'relocated_contracts.txt').write_text(completed.stdout+completed.stderr,encoding='utf-8')
        if completed.returncode:raise RuntimeError('Relocated focused contracts failed; see relocated_contracts.txt')
        contracts=json.loads(contract_output.read_text(encoding='utf-8'))
    summary=dict(schema='just-peachy.actual-release-check.v1',completed_utc=now(),status='PASS',build=receipt,
        stage=staged,models_verified=assets,models_copied=False,rollback=rolled,
        rollback_fixture=dict(version=fixture_version,sha256=digest(fixture_archive),application_bytes_unchanged=True,synthetic_private_sentinel_preserved=True),
        healthcheck=health,checks=checks,native_result=dict(path=str(result_path),rows=len(native['rows']),state=native['state'],model_cache=native['metrics'].get('model_cache')),
        launcher_check='Actual PS and CMD launchers, GUI startup/normal-close with an external process-only hidden-Tk test hook; no pixel/live proof claimed.',
        rc_to_final_delta=delta,relocated_focused_contracts=contracts,
        no_microphone=True,no_remote_host=True,cm5='CM5_HARDWARE_NOT_TESTED')
    write_json(a.evidence/a.receipt_name,summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
