"""Lossless content-addressed archive of a completed owned cell; README_EVIDENCE.md."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import zipfile
from common import load,bind,freeze,sha


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('Duplicate archive members')
        manifest=json.loads(archive.read('MANIFEST.json'))
        if len({r['relative_path'] for r in manifest['files']})!=len(manifest['files']):
            raise ValueError('Duplicate evidence paths in manifest')
        expected={'MANIFEST.json'}|{r['object'] for r in manifest['files']}
        if set(archive.namelist())!=expected:
            raise ValueError('Unexpected archive members')
        verified={}
        for row in manifest['files']:
            rel=Path(row['relative_path'])
            if rel.is_absolute() or '..' in rel.parts or ':' in str(rel):
                raise ValueError('Unsafe relative evidence path')
            if row['object']!='objects/'+row['sha256']:
                raise ValueError('Object key does not bind content')
            if row['object'] not in verified:
                h=hashlib.sha256();size=0
                with archive.open(row['object']) as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):
                        size+=len(block);h.update(block)
                verified[row['object']]=(h.hexdigest(),size)
            if verified[row['object']]!=(row['sha256'],row['bytes']):
                raise ValueError('Archived evidence differs')
        return manifest


def pack(result_path,output):
    import psutil,os
    p=psutil.Process();p.cpu_affinity([4])
    if os.name=='nt':p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    result=load(result_path);root=result_path.parent.resolve()
    if result.get('status')!='COMPLETE' or not all(result.get('checks',{}).values()):
        raise ValueError('Only completed checked execution evidence is admitted')
    checkpoint=load(root.parent/'CHECKPOINT.json')
    if checkpoint['result']!=bind(result_path) or checkpoint['status']!='COMPLETE':
        raise ValueError('Completed checkpoint changed')
    bindings=list(result['evidence'])+[bind(result_path)]
    files=[];objects={}
    for binding in bindings:
        path=Path(binding['path']).resolve(strict=True)
        if not path.is_relative_to(root) or path.is_symlink() or bind(path)!=binding:
            raise ValueError('Only unchanged in-cell evidence can be archived')
        rel=str(path.relative_to(root)).replace('\\','/')
        files.append(dict(relative_path=rel,sha256=binding['sha256'],bytes=binding['bytes'],
                          object='objects/'+binding['sha256']))
        objects[binding['sha256']]=path
    if len({r['relative_path'] for r in files})!=len(files):
        raise ValueError('Duplicate evidence path')
    manifest=dict(schema='n4-lossless-cell-evidence-v1',execution_result=bind(result_path),files=files,
                  semantics='exact byte preservation; no transcript, timestamp or probability changes')
    output.parent.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        archive.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True,allow_nan=False))
        for digest,path in objects.items():
            archive.write(path,'objects/'+digest)
    if verify_archive(output)!=manifest:
        raise ValueError('Archive verification differs from input manifest')
    total=sum(r['bytes'] for r in files)
    result=dict(status='LOSSLESS_ARCHIVE_VERIFIED',source=bind(result_path),archive=bind(output),
        files=len(files),unique_objects=len(objects),input_bytes=total,
        archive_bytes=output.stat().st_size,ratio=output.stat().st_size/total,
        elapsed_seconds=time.perf_counter()-started,source_files_modified=False,source_files_deleted=False,
        stage_completion_claimed=False,portable_cache_reader_integrated=False)
    freeze(output.with_suffix('.receipt.json'),result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--result',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(json.dumps(pack(args.result,args.output),indent=2))
