"""Freeze reviewed source without audio, weights or local evidence. See README.md."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prototype',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--include',action='append',default=[],help='Explicit small source/test support file relative to repository root')
    a=p.parse_args();source=a.prototype.resolve();target=a.destination.resolve()
    if target.exists():raise SystemExit('Destination must be new; never overwrite a frozen release')
    allowed={'.py','.md','.json','.yaml','.yml','.toml','.ini','.cfg','.txt','.cmd','.bat','.ps1','.sh','.c','.cpp','.h','.hpp','.cmake','.in','.lock'}
    excluded={'__pycache__','evidence','.pytest_cache','models','data','3D Print Files',
              'node_modules','.git','.venv','venv'}
    files={}
    for path in sorted(source.rglob('*')):
        rel=path.relative_to(source)
        if not path.is_file() or any(v in excluded for v in rel.parts):continue
        if path.suffix.lower() not in allowed and path.name not in {'LICENSE','NOTICE','CMakeLists.txt'}:continue
        dest=target/'prototype'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);files[rel.as_posix()]={'sha256':sha(dest),'bytes':dest.stat().st_size}
    runtime={k:v['sha256'] for k,v in files.items() if k.startswith(('app/','vendor/','config/','release_tools/')) or k=='main.py' or '/' not in k and Path(k).suffix in {'.cmd','.bat','.ps1','.sh'}}
    digest=hashlib.sha256(json.dumps(runtime,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    ui_paths=['app/ui.py','app/caption_display.py','app/backends.py','app/mode_policy.py',
        'vendor/edge_speech_pipeline/research_n1_spans.py','vendor/edge_speech_pipeline/research_s7_presentation.py']
    ui={k:files[k]['sha256'] for k in ui_paths}
    auxiliary={}
    for relative in a.include:
        rel=Path(relative)
        path=(source.parent/rel).resolve(strict=True)
        if rel.is_absolute() or '..' in rel.parts or not path.is_relative_to(source.parent) or not path.is_file():
            raise ValueError('Support file must be explicitly inside the source repository')
        if path.suffix.lower() not in allowed or any(v in excluded for v in rel.parts) or path.stat().st_size>2*1024**2:
            raise ValueError('Support file is not small admitted source')
        dest=target/rel
        if dest.exists():raise ValueError('Support file collides with frozen source')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        auxiliary[rel.as_posix()]={'sha256':sha(dest),'bytes':dest.stat().st_size}
    bundle=target.with_suffix('.zip')
    with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for rel in files:archive.write(target/'prototype'/rel,'prototype/'+rel)
        for rel in auxiliary:archive.write(target/rel,rel)
    receipt={'schema':'just-peachy.n1.frozen-source.v1','prototype':str(target/'prototype'),
        'frontend_runtime_sha256':digest,'frontend_hash_scope':'all app/vendor/config/release_tools content plus main.py and root launchers',
        'common_ui_source_sha256':hashlib.sha256(json.dumps(ui,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'common_ui_files':ui,
        'files':files,'file_count':len(files),'auxiliary_files':auxiliary,
        'archive':{'path':str(bundle),'sha256':sha(bundle),'bytes':bundle.stat().st_size}}
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))


if __name__=='__main__':main()
