"""Package explicitly selected, remotely backed-up reports. README_REVIEWED_HANDOFF_V2.md."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess
import zipfile

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
ROOT=HERE.parents[3]
PREFIX='research/nvidia_nemo_comparison/20260924_campaign/'
REMOTE='https://github.com/will-sloan/just-peachy.git'
BRANCH='refs/heads/codex/n1-foundation-20260924'


def require(value,message):
    if not value:raise ValueError(message)


def digest(data):return hashlib.sha256(data).hexdigest()


def encoded(value):return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()


def relative(name):
    require(isinstance(name,str) and name and '\\' not in name and ':' not in name and '\0' not in name,'Unsafe path')
    p=PurePosixPath(name)
    require(not p.is_absolute() and all(x not in ('','.','..') for x in name.split('/')),'Path escapes campaign')
    require(name not in ('GITHUB_BACKUP_RECEIPT.json','HANDOFF_MANIFEST.json'),'Generated receipt name reserved')
    require(p.suffix in ('.md','.json','.csv','.py','.cmd','.ps1','.sh','.txt','.lock'),'Disallowed file type')
    return p


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,timeout=45)


def collect(names,reader):
    require(isinstance(names,list) and 27<=len(names)<=57 and len(set(names))==len(names),'Expected 27–57 unique selected files')
    result={}
    for name in names:
        relative(name);data=reader(name)
        require(isinstance(data,bytes) and 0<len(data)<=2*1024**2,'Selected file empty or oversized')
        result[name]=data
    require(sum(map(len,result.values()))<=18*1024**2,'Uncompressed selection exceeds cap')
    return result


def build(selection,status,output,receipt):
    require(not output.exists() and not receipt.exists(),'Fresh archive and receipt required')
    local=(ROOT.parent/'local/n5').resolve()
    require(output.resolve().is_relative_to(local) and receipt.resolve().is_relative_to(local),'Private N5 destinations required')
    require(output.resolve()!=receipt.resolve() and output.suffix=='.zip','Distinct ZIP and receipt paths required')
    require(git('remote','get-url','origin').decode().strip()==REMOTE,'Unexpected authorized remote')
    head=git('rev-parse','HEAD').decode().strip()
    require(git('symbolic-ref','HEAD').decode().strip()==BRANCH,'Unexpected branch')
    remote=git('ls-remote','origin',BRANCH).decode().strip();require(remote.split()==[head,BRANCH],'Remote branch does not match HEAD')
    spec=json.loads(selection.read_text(encoding='utf-8-sig'));state=json.loads(status.read_text(encoding='utf-8-sig'))
    require(spec['current_status']==status.relative_to(CAMPAIGN).as_posix(),'Selected status differs from explicit selection')
    require(state.get('completed') is False and state['N4']['accepted_new_release_profiles']==0,'This builder is for the partial checkpoint only')
    names=list(spec['files'])+[selection.relative_to(CAMPAIGN).as_posix(),status.relative_to(CAMPAIGN).as_posix()]
    def read(name):
        path=CAMPAIGN/name;resolved=path.resolve(strict=True)
        require(resolved.is_relative_to(CAMPAIGN.resolve()) and not path.is_symlink(),'Unsafe filesystem path')
        data=path.read_bytes();require(data==git('show',head+':'+PREFIX+name),'File differs from remotely backed-up commit')
        return data
    files=collect(names,read)
    backup=dict(status='REMOTE_BRANCH_VERIFIED_FOR_ALL_SELECTED_BYTES',checked_utc=datetime.now(timezone.utc).isoformat(),
        remote=REMOTE,ref=BRANCH,commit=head,remote_observation=remote,selected_files=len(files),
        exclusions=['Model weights','Audio','Voiceprints','Personal profiles','Raw private transcripts','Full raw run logs'],
        repository_visibility_changed=False,main_merged=False,force_push=False,CM5_tested=False)
    files['GITHUB_BACKUP_RECEIPT.json']=encoded(backup)
    manifest=dict(status='PARTIAL_CAMPAIGN_CHECKPOINT_NOT_COMPLETED_N5',created_utc=backup['checked_utc'],source_commit=head,
        latest_status=status.relative_to(CAMPAIGN).as_posix(),
        files=[dict(path=n,bytes=len(d),sha256=digest(d)) for n,d in sorted(files.items())],
        scope='Analysis-first reports and selected small reproducibility tools; deployable bundles remain separate.',
        private_audio=False,model_weights=False,CM5_tested=False)
    files['HANDOFF_MANIFEST.json']=encoded(manifest)
    require(30<=len(files)<=60,'Final file-count cap exceeded')
    output.parent.mkdir(parents=True,exist_ok=True);receipt.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,data in sorted(files.items()):z.writestr(name,data)
    require(output.stat().st_size<=20*1024**2,'Compressed handoff exceeds 20 MiB')
    with zipfile.ZipFile(output) as z:
        require(set(z.namelist())==set(files),'ZIP file set differs')
        for name,data in files.items():require(z.read(name)==data,'ZIP readback mismatch')
    value=dict(status=manifest['status'],archive=str(output.resolve()),sha256=digest(output.read_bytes()),bytes=output.stat().st_size,
        files=len(files),source_commit=head,remote=REMOTE,ref=BRANCH,readback='ALL_MEMBERS_MATCH',
        below_10_MiB_target=output.stat().st_size<=10*1024**2,selection_sha256=digest(selection.read_bytes()),
        status_sha256=digest(status.read_bytes()),N5_complete=False,CM5_tested=False)
    with receipt.open('xb') as stream:stream.write(encoded(value))
    print(json.dumps(value))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('selection','status','output','receipt'):p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args();build(a.selection.resolve(),a.status.resolve(),a.output.resolve(),a.receipt.resolve())
