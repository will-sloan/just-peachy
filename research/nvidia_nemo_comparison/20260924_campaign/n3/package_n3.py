"""Package only hash-bound, accepted N3 analysis; README_PACKAGE.md."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package(root, listing, git_receipt, output, receipt):
    root=root.resolve();acceptance=load(root/'N3_ACCEPTANCE.json')
    checks=load(root/'FINAL_CHECKS.json');backup=load(git_receipt)
    if acceptance['status']!='ACCEPTED_N3_OFFLINE_COMPONENT_SCOPE' or checks['status']!='PASS':
        raise ValueError('Reviewed N3 acceptance and final checks required')
    if (backup['status']!='REMOTE_REF_VERIFIED' or backup['commit']!=backup['remote_commit']
            or backup['tag']!=acceptance['release_tag'] or backup['remote_tag_commit']!=backup['commit']):
        raise ValueError('Exact accepted source tag must be verified remotely')
    names=load(listing)
    if not isinstance(names,list) or not 30<=len(names)<=59 or len({n.casefold() for n in names})!=len(names):
        raise ValueError('Need 30–59 unique reviewed analysis files')
    members=[]
    for name in names:
        rel=PurePosixPath(name);path=(root/name).resolve(strict=True)
        if (rel.is_absolute() or rel.as_posix()!=name or '\\' in name or
                any(p in ('.','..') or ':' in p for p in rel.parts) or not path.is_relative_to(root)
                or path.suffix not in ('.md','.json','.txt') or not path.is_file()
                or name.casefold()=='package_contents.json' or path.stat().st_size>2*2**20):
            raise ValueError('Unsafe, oversized or non-analysis package member')
        row=dict(path=name,sha256=sha(path),bytes=path.stat().st_size)
        if name!='N3_ACCEPTANCE.json' and acceptance['analysis_files'].get(name)!={k:row[k] for k in ['sha256','bytes']}:
            raise ValueError('Accepted analysis changed: '+name)
        members.append(row)
    if output.exists() or receipt.exists():raise ValueError('Use fresh ZIP/receipt paths')
    output.parent.mkdir(parents=True,exist_ok=True);receipt.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for row in members:archive.write(root/row['path'],row['path'])
        archive.writestr('PACKAGE_CONTENTS.json',json.dumps(dict(schema='n3-analysis-package-v1',files=members,
            accepted_git_commit=backup['commit'],release_tag=backup['tag'],
            scope='reviewed analysis only; no audio, raw transcripts, vectors, profiles, models or binaries'),indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('Archive CRC check failed')
        for row in members:
            if hashlib.sha256(archive.read(row['path'])).hexdigest()!=row['sha256']:
                raise ValueError('Archive byte verification failed')
    size=output.stat().st_size
    result=dict(status='PASS' if size<=20*2**20 else 'FAILED_SIZE_LIMIT',path=str(output),sha256=sha(output),
        bytes=size,files=len(members)+1,target_10mib_met=size<=10*2**20,
        accepted_git_commit=backup['commit'],release_tag=backup['tag'])
    with receipt.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    if result['status']!='PASS':raise ValueError('Failed oversized artifact preserved')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    for field in ['file-list','git-receipt','output','receipt']:parser.add_argument('--'+field,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.root,args.file_list,args.git_receipt,args.output,args.receipt)))
