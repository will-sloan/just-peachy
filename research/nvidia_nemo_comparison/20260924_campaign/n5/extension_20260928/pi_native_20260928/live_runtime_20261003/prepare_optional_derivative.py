"""Prepare exact allocation/export repairs; see README_OPTIONAL_DERIVATIVE.md."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

MODULE='optional_refiner_qualification.py'
SOURCE_MANIFEST='2ec99c80d5d070c30a1b4a7959be1a9e552d5fc7688fe703ab9ad650891ee841'


def early(output_root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
    values=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    output=Path(output_root)/('optional-derivative-'+uuid.uuid4().hex)
    output.mkdir(parents=True,exist_ok=False)
    with (output/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=1<<14,creation_filetime=values[0].value,
            create_time=(values[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    return output


def expected_binding(old,new,encoded,operational):
    expected=json.loads(json.dumps(old));source=old['target'];target=new['target']
    if source.rsplit('/',1)[-1]!='field-runtime-v29-build-08' or target.rsplit('/',1)[-1]!='field-runtime-v29-build-09':
        raise ValueError('This derivative is exactly build08 to build09')
    def relocated(value):
        if not value.startswith(source+'/'):raise ValueError('Package-local path lost its exact source root')
        return target+value[len(source):]
    expected['target']=target
    expected['reference_code']=relocated(old['reference_code'])
    expected['raw_factory_path']=relocated(old['raw_factory_path'])
    for key,row in expected['profiles'].items():row['path']=relocated(row['path'])
    expected['candidate_content_sha256']=new['candidate_content_sha256']
    if encoded(operational(expected))!=encoded(operational(new)):
        raise ValueError('Allocation derivative changed another operational binding field')


def prepare(args,output):
    from prepare_package import (build,encoded,strict,sha,write,read_regular,operational_binding,relative)
    from install_candidate import verify_tree
    source=args.source.resolve(strict=True)
    verify_tree(source,SOURCE_MANIFEST)
    before=read_regular(source/'PACKAGE_MANIFEST.json')
    manifest=strict(before);old_binding=strict(read_regular(source/'BINDING.json',65536))
    inputs={MODULE:(args.replacement,args.replacement_sha256),
        'launcher.py':(args.export_launcher,args.export_launcher_sha256),
        'owned_export.py':(args.export_module,args.export_module_sha256),
        'README_OWNED_EXPORT.md':(args.export_readme,args.export_readme_sha256),
        'launch_raw_qualification_action.py':(args.shared_helper,args.shared_helper_sha256),
        'README_QUALIFICATION_DISPATCH.md':(args.shared_readme,args.shared_readme_sha256),
        'README_OPTIONAL_QUALIFICATION.md':(args.optional_readme,args.optional_readme_sha256)}
    replacements={}
    for name,(path,pin) in inputs.items():
        raw=read_regular(path,262144)
        if sha(raw)!=pin:raise ValueError('Exact reviewed replacement digest differs: '+name)
        if (source/name).exists() and raw==read_regular(source/name):
            raise ValueError('Derivative must contain the actual reviewed repair: '+name)
        if name.endswith('.py'):compile(raw,name,'exec')
        replacements[name]=raw
    # Every source byte comes from this verified immutable package; no mutable
    # runtime directory contributes files. Every repair has its own exact pin.
    copied=output/'source';copied.mkdir()
    for row in manifest['files']:
        raw=read_regular(source.joinpath(*relative(row['path']).parts))
        if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Frozen source changed while copying')
        write(copied.joinpath(*relative(row['path']).parts),replacements.get(row['path'],raw))
    for name in ('owned_export.py','README_OWNED_EXPORT.md'):
        if (copied/name).exists():raise ValueError('Reviewed added file already existed in source')
        write(copied/name,replacements[name])
    # The initial-builder descriptor interface expects the retained capsule here.
    # This duplicate is not a descriptor and is excluded from candidate content.
    write(copied/'profiles/COMMON_BUNDLE.json',read_regular(copied/'reference-v28/COMMON_BUNDLE.json'))
    result=build(copied,copied/'profiles',output,release_id='field-runtime-v29-build-09')
    package=Path(result['package']);after=strict(read_regular(package/'PACKAGE_MANIFEST.json'))
    old_rows={row['path']:row for row in manifest['files']}
    new_rows={row['path']:row for row in after['files']}
    excluded={'BINDING.json','NATIVE_ADMISSION.json','PRODUCTION_ACCEPTANCE.json','RELOCATION_CERTIFICATE.json'}
    old_content={name:row for name,row in old_rows.items() if name not in excluded and not name.startswith('source-backups/')}
    new_content={name:row for name,row in new_rows.items() if name not in excluded and not name.startswith('source-backups/')}
    added=set(new_content)-set(old_content)
    if added!={'owned_export.py','README_OWNED_EXPORT.md'} or set(old_content)-set(new_content):
        raise ValueError('Unexpected derivative content membership change')
    changed=[name for name in sorted(old_content) if old_content[name]!=new_content[name]]
    if changed!=sorted((MODULE,'launcher.py','launch_raw_qualification_action.py',
                         'README_QUALIFICATION_DISPATCH.md','README_OPTIONAL_QUALIFICATION.md')):
        raise ValueError('Only explicit reviewed optional/export/publication repairs and instructions may change: '+repr(changed))
    new_binding=strict(read_regular(package/'BINDING.json',65536))
    expected_binding(old_binding,new_binding,encoded,operational_binding)
    verify_tree(source,SOURCE_MANIFEST)
    for name,(path,pin) in inputs.items():
        if read_regular(path,262144)!=replacements[name]:raise ValueError('Reviewed repair changed during build: '+name)
    receipt=dict(schema='just-peachy.optional-allocation-derivative.v1',source_package=str(source),
        source_manifest_sha256=SOURCE_MANIFEST,source_binding_sha256=sha(read_regular(source/'BINDING.json',65536)),
        source_content_sha256=manifest['candidate_content_sha256'],destination=result,
        changed_content_files=[dict(path=name,source_sha256=old_content[name]['sha256'],
            destination_sha256=sha(replacements[name])) for name in changed],
        added_content_files=[dict(path=name,destination_sha256=sha(replacements[name])) for name in sorted(added)],
        all_other_content_bytes_unchanged=True,
        native_executed=False,native_qualified=False,reviewer=args.reviewer,
        evidence_reuse='Actual build08 primary/GUI provenance retained; build09 execution is not claimed')
    write(output/'DERIVATION.json',encoded(receipt))
    for name,raw in replacements.items():
        write(output/'reviewed-repairs'/(name+'.backup'),raw)
        write(output/'reviewed-repairs'/(name+'.restore'),raw)
    return dict(result,derivation=str(output/'DERIVATION.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--replacement',type=Path,required=True)
    parser.add_argument('--replacement-sha256',required=True)
    for label in ('export-launcher','export-module','export-readme','shared-helper','shared-readme','optional-readme'):
        parser.add_argument('--'+label,type=Path,required=True)
        parser.add_argument('--'+label+'-sha256',required=True)
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--output-root',required=True)
    args=parser.parse_args();output=early(args.output_root);sys.dont_write_bytecode=True
    if not args.reviewer.strip() or len(args.reviewer)>128:raise ValueError('Explicit reviewer required')
    print(json.dumps(prepare(args,output),sort_keys=True))


if __name__=='__main__':main()
