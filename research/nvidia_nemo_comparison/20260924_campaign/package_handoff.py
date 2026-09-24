"""Build a small explicitly allowlisted analysis ZIP. See README.md."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import zipfile


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign',type=Path,default=Path(__file__).parent)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--file-list',type=Path)
    p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args();root=a.campaign.resolve()
    files=json.loads((a.file_list or root/'HANDOFF_FILES.json').read_text(encoding='utf-8'))
    if not isinstance(files,list) or not all(isinstance(name,str) for name in files):
        raise ValueError('Handoff allowlist must be a list of path strings')
    if not 30<=len(files)<=59:raise ValueError('Expected30–59 explicit files plus content manifest')
    if len({name.casefold() for name in files})!=len(files):raise ValueError('Duplicate handoff path')
    metrics=json.loads((root/'N1_METRICS.json').read_text(encoding='utf-8'))
    if metrics['status']!='COMPLETE':raise ValueError('N1 acceptance must be complete before packaging')
    if not metrics.get('evidence'):raise ValueError('N1 acceptance evidence bindings are missing')
    for name,entry in metrics['evidence'].items():
        path=(root/name).resolve(strict=True)
        if not path.is_relative_to(root) or path!=Path(entry['path']).resolve() or sha(path)!=entry['sha256'] or path.stat().st_size!=entry['bytes']:
            raise ValueError('Acceptance evidence changed after validation: '+name)
    index=[]
    for relative in files:
        canonical=PurePosixPath(relative)
        if canonical.is_absolute() or canonical.as_posix()!=relative or any(part in ('.','..') or ':' in part for part in canonical.parts) or '\\' in relative or relative.casefold()=='package_contents.json':
            raise ValueError('Noncanonical/reserved handoff member: '+relative)
        path=(root/relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in {'.md','.json','.csv','.py','.ps1','.cmd','.txt','.png'}:
            raise ValueError('Unsafe/non-analysis handoff member: '+relative)
        if path.stat().st_size>2*1024**2:raise ValueError('Individual payload too large: '+relative)
        index.append(dict(path=relative,sha256=sha(path),bytes=path.stat().st_size))
    contents=dict(schema='just-peachy.n1.handoff-package.v1',created_utc=datetime.now(timezone.utc).isoformat(),
        privacy='Explicit reviewed small files; no models, audio, private profiles or full transcript/event dumps',files=index)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for row in index:archive.write(root/row['path'],row['path'])
        archive.writestr('PACKAGE_CONTENTS.json',json.dumps(contents,indent=2)+'\n')
    with zipfile.ZipFile(a.output) as archive:
        if archive.testzip():raise RuntimeError('ZIP integrity failed')
        for row in index:
            if hashlib.sha256(archive.read(row['path'])).hexdigest()!=row['sha256']:raise RuntimeError('ZIP content changed')
    if a.output.stat().st_size>20*1024**2:raise ValueError('Handoff exceeds hard20MiB ceiling')
    receipt=dict(path=str(a.output.resolve()),sha256=sha(a.output),bytes=a.output.stat().st_size,
        files=len(index)+1,target_10mib_met=a.output.stat().st_size<=10*1024**2,integrity='PASS')
    a.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__':main()
