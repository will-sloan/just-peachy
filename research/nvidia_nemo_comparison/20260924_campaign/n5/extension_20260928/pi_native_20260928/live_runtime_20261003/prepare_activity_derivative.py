"""Exact10 to disabled11 optional empty-activity repair. See README_ACTIVITY_DERIVATIVE.md."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import uuid

SOURCE_MANIFEST='e2ac82b96c1b71db98a538bc30a534afdb0ea7af630eff9c14caef3236d393d1'
PRIOR_DERIVATION='024544780c8949d972ba63c39b7b7e6c47cc5eaf647749bb9ed1f2e3ab705634'


def early(output_root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p;handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
    values=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    output=Path(output_root)/('activity-derivative-'+uuid.uuid4().hex);output.mkdir(parents=True,exist_ok=False)
    with (output/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=1<<14,creation_filetime=values[0].value,
            create_time=(values[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    return output


def prepare(args,output):
    from prepare_package import build,encoded,strict,sha,write,read_regular,relative,operational_binding
    from install_candidate import verify_tree
    source=args.source.resolve(strict=True);verify_tree(source,SOURCE_MANIFEST)
    manifest=strict(read_regular(source/'PACKAGE_MANIFEST.json'))
    old_binding_raw=read_regular(source/'BINDING.json',65536);old_binding=strict(old_binding_raw)
    prior_raw=read_regular(args.prior_derivation,65536)
    if sha(prior_raw)!=PRIOR_DERIVATION:raise ValueError('Exact09 to10 predecessor review required')
    prior=strict(prior_raw)
    if (prior['destination']['candidate_content_sha256']!=manifest['candidate_content_sha256']
            or prior['destination']['target']!=manifest['target']):
        raise ValueError('Predecessor content/target differs')
    inputs={'optional_refiner.py':(args.replacement,args.replacement_sha256),
            'README_OPTIONAL_REFINER.md':(args.readme,args.readme_sha256)}
    repairs={}
    for name,(path,pin) in inputs.items():
        raw=read_regular(path,262144)
        if sha(raw)!=pin or raw==read_regular(source/name):raise ValueError('Exact new reviewed empty-activity repair required: '+name)
        if name.endswith('.py'):compile(raw,name,'exec')
        repairs[name]=raw
    copied=output/'source';copied.mkdir()
    for row in manifest['files']:
        raw=read_regular(source.joinpath(*relative(row['path']).parts))
        if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Source changed during copy')
        write(copied.joinpath(*relative(row['path']).parts),repairs.get(row['path'],raw))
    write(copied/'profiles/COMMON_BUNDLE.json',read_regular(copied/'reference-v28/COMMON_BUNDLE.json'))
    result=build(copied,copied/'profiles',output,release_id='field-runtime-v29-build-11')
    package=Path(result['package']);after=strict(read_regular(package/'PACKAGE_MANIFEST.json'))
    def content(rows):
        return {row['path']:row for row in rows if row['path'] not in
            ('BINDING.json','NATIVE_ADMISSION.json','PRODUCTION_ACCEPTANCE.json','RELOCATION_CERTIFICATE.json')
            and not row['path'].startswith('source-backups/')}
    old_rows=content(manifest['files']);new_rows=content(after['files'])
    if set(old_rows)!=set(new_rows):raise ValueError('Activity repair changed package membership')
    changes=[name for name in sorted(old_rows) if old_rows[name]!=new_rows[name]]
    if changes!=sorted(repairs):raise ValueError('Unexpected activity derivative content changes: '+repr(changes))
    new_binding=strict(read_regular(package/'BINDING.json',65536));expected=strict(encoded(old_binding))
    old_root=old_binding['target'];new_root=new_binding['target']
    if not old_root.endswith('/field-runtime-v29-build-10') or not new_root.endswith('/field-runtime-v29-build-11'):
        raise ValueError('Exact10 to11 target pair required')
    def moved(value):
        if not value.startswith(old_root+'/'):raise ValueError('Package path is outside source root')
        return new_root+value[len(old_root):]
    expected['target']=new_root;expected['candidate_content_sha256']=new_binding['candidate_content_sha256']
    for key in ('reference_code','raw_factory_path'):expected[key]=moved(expected[key])
    for row in expected['profiles'].values():row['path']=moved(row['path'])
    if encoded(operational_binding(expected))!=encoded(operational_binding(new_binding)):
        raise ValueError('Activity-only derivative changed another operational field')
    verify_tree(source,SOURCE_MANIFEST)
    for name,(path,pin) in inputs.items():
        if read_regular(path,262144)!=repairs[name]:raise ValueError('Activity repair changed during preparation')
        write(output/'reviewed-repairs'/(name+'.backup'),repairs[name])
        write(output/'reviewed-repairs'/(name+'.restore'),repairs[name])
    write(output/'PREDECESSOR_DERIVATION.json',prior_raw)
    receipt=dict(schema='just-peachy.optional-empty-activity-derivative.v1',source_package=str(source),
        source_manifest_sha256=SOURCE_MANIFEST,source_binding_sha256=sha(old_binding_raw),
        source_content_sha256=manifest['candidate_content_sha256'],predecessor_derivation_sha256=PRIOR_DERIVATION,
        predecessor_file='PREDECESSOR_DERIVATION.json',destination=result,
        changed_content_files=[dict(path=name,source_sha256=old_rows[name]['sha256'],destination_sha256=sha(repairs[name])) for name in changes],
        all_other_content_bytes_unchanged=True,reviewer=args.reviewer,native_executed=False,native_qualified=False,
        evidence_reuse='Actual08 primary/GUI and10 primary-only evidence retain their original identities; only empty optional activity acknowledgements change; no11 native execution claimed')
    write(output/'DERIVATION.json',encoded(receipt))
    return dict(result,derivation=str(output/'DERIVATION.json'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','replacement','readme','prior-derivation'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('replacement-sha256','readme-sha256','reviewer','output-root'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args();output=early(args.output_root);sys.dont_write_bytecode=True
    if not args.reviewer.strip() or len(args.reviewer)>128:raise ValueError('Explicit reviewer required')
    print(json.dumps(prepare(args,output),sort_keys=True))


if __name__=='__main__':main()
