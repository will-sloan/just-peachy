"""Bind the existing CUDA toolkit's local runtime DLLs; no download or installer."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent

def binding(path):
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'path':str(path),'sha256':digest,'bytes':path.stat().st_size}

def main():
    receipt_path=HERE/'CUDA_BUILD_RECEIPT.json'
    receipt=json.loads(receipt_path.read_text())
    if receipt['status']!='ACTUALLY_BUILT' or not receipt['gpu']:
        raise RuntimeError('A completed explicit CUDA build is required')
    binary_dir=Path(receipt['library_path']).parent
    toolkit_bin=Path(receipt['cuda_compiler']).parent
    names=('cudart64_12.dll','cublas64_12.dll','cublasLt64_12.dll')
    required=sum((toolkit_bin/name).stat().st_size for name in names)
    if shutil.disk_usage(binary_dir).free < 75*1024**3+required:
        raise RuntimeError('Insufficient private-disk reserve for CUDA runtime staging')
    staged=[]
    for name in names:
        original,target=toolkit_bin/name,binary_dir/name
        source_binding=binding(original)
        if target.exists() and binding(target)['sha256']!=source_binding['sha256']:
            raise RuntimeError('Refusing to overwrite a different existing CUDA runtime DLL')
        if not target.exists():
            shutil.copy2(original,target)
        if binding(target)['sha256']!=source_binding['sha256']:
            raise RuntimeError('CUDA runtime copy verification failed')
        staged.append({'original':source_binding,'staged':binding(target)})
    licenses=[]
    for path in toolkit_bin.parent.glob('*'):
        if path.is_file() and ('license' in path.name.lower() or 'eula' in path.name.lower()):
            licenses.append(binding(path))
    receipt['cuda_local_runtime_staging']={'source':'existing legitimately installed local toolkit; no installer executed',
                                            'files':staged,'toolkit_license_files':licenses,
                                            'redistribution':'private local execution only; DLLs not added to Git or handoff ZIP'}
    script_dir=binary_dir.parents[2]/'script-snapshots'
    script_dir.mkdir(exist_ok=True)
    for script in (HERE/'build_native.py',Path(__file__).resolve()):
        target=script_dir/script.name
        if target.exists() and binding(target)['sha256']!=binding(script)['sha256']:
            raise RuntimeError('Build/staging script changed; preserve the earlier snapshot and use a new build')
        if not target.exists():
            shutil.copyfile(script,target)
    receipt['build_script']=binding(script_dir/'build_native.py')
    receipt['staging_script']=binding(script_dir/'stage_cuda_runtime.py')
    receipt['cuda_compiler_binding']=binding(Path(receipt['cuda_compiler']))
    receipt['runtime_files']=[binding(path) for path in sorted(binary_dir.glob('*.dll'))]
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'LOCAL_CUDA_RUNTIME_STAGED','bytes':required,'files':names}))

if __name__=='__main__':
    main()
