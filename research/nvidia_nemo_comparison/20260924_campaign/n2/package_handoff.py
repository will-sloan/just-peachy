"""Package completed N2 analysis from a reviewed allowlist. See README_PACKAGE.md."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import zipfile


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def package(root,listing,output,receipt):
    root=root.resolve();output=output.resolve();receipt=receipt.resolve()
    metrics=json.loads((root/'N2_METRICS.json').read_text())
    if metrics.get('status')!='COMPLETE' or not metrics.get('evidence'):
        raise ValueError('Completed N2 acceptance with evidence bindings is required')
    checks=json.loads((root/'evaluation/FINAL_CHECKS.json').read_text())
    if checks.get('status')!='PASS':raise ValueError('Final numerical/test/GUI checks have not passed')
    if metrics.get('github_backup')!='VERIFIED':raise ValueError('Final scoped backup must be verified')
    names=json.loads(listing.read_text())
    if not isinstance(names,list) or not 30<=len(names)<=59 or not all(isinstance(n,str) for n in names):
        raise ValueError('Use30–59 explicitly reviewed analysis files')
    if len({n.casefold() for n in names})!=len(names):raise ValueError('Duplicate archive member')
    members=[]
    for name in names:
        rel=PurePosixPath(name);path=(root/name).resolve(strict=True)
        if (rel.is_absolute() or rel.as_posix()!=name or '\\' in name or
                any(p in ('.','..') or ':' in p for p in rel.parts) or
                name.casefold()=='package_contents.json' or not path.is_relative_to(root) or
                not path.is_file() or path.suffix not in ('.md','.json','.txt')):
            raise ValueError('Unsafe or non-analysis member: '+name)
        if path.stat().st_size>2*1024**2:raise ValueError('Analysis member exceeds2MiB: '+name)
        row=dict(path=name,sha256=digest(path),bytes=path.stat().st_size)
        if name!='N2_METRICS.json' and metrics['evidence'].get(name)!={k:v for k,v in row.items() if k!='path'}:
            raise ValueError('Analysis changed or lacks acceptance binding: '+name)
        members.append(row)
    if output.exists() or receipt.exists():raise ValueError('Use fresh ZIP and receipt paths')
    output.parent.mkdir(parents=True,exist_ok=True);receipt.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for row in members:archive.write(root/row['path'],row['path'])
        archive.writestr('PACKAGE_CONTENTS.json',json.dumps(dict(schema='n2-analysis-package-v1',files=members,
            scope='Reviewed analysis only; no audio, model weights, voiceprints or full transcript/event dumps'),indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('Archive CRC verification failed')
        for row in members:
            if hashlib.sha256(archive.read(row['path'])).hexdigest()!=row['sha256']:raise ValueError('Archived content differs')
    size=output.stat().st_size
    result=dict(status='PASS' if size<=20*1024**2 else 'FAILED_SIZE_LIMIT',path=str(output),
                sha256=digest(output),bytes=size,files=len(members)+1,target_10mib_met=size<=10*1024**2)
    with receipt.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    if result['status']!='PASS':raise ValueError('Archive exceeds20MiB hard limit; retained failed artifact')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).parent)
    parser.add_argument('--file-list',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(package(args.root,args.file_list,args.output,args.receipt)))
