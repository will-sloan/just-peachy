"""Freeze disabled GUI15 from actual14; see README_GUI_POLICY_DERIVATIVE.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import uuid

SOURCE_MANIFEST='8ec7f83c148d4cf5b043f0a8f044033b6881164b83f0c7bdb3d5af7757e0dcb8'
SOURCE_BINDING='6b768ec1482cef7c72efd7542eb239104eb0acdb335fefc6690834676f1ab633'
BUILDER='0a706522770d21d8b4846d3121cc430eef81ec73fcced965eca7d804fbf47832'
REPAIRS={'launcher.py':'a520e51e6bf033fc06d2fe60c708f047f8e357bfe3de1dbc691410abf0268fb5',
         'README_GUI_OPTIONAL_POLICY.md':'ed51f9a74597a98081a6af77c24cfd42d51daf55c8206359ac2add6e46178ab5'}
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def publish(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short write')
        stream.flush();os.fsync(stream.fileno())
    if path.read_bytes()!=raw:raise OSError('Independent readback mismatch')


def prepare(source,repairs,output):
    builder_path=Path(__file__).with_name('prepare_package.py')
    builder_raw=builder_path.read_bytes()
    if hashlib.sha256(builder_raw).hexdigest()!=BUILDER:raise ValueError('Reviewed builder pin differs')
    import gui_policy_reuse as reuse
    from prepare_package import build,encoded,read_regular,relative,sha
    from install_candidate import verify_tree
    manifest,binding,members=reuse.inventory(source,SOURCE_MANIFEST)
    if sha(members['BINDING.json'])!=SOURCE_BINDING or not binding['native_launch_enabled']:
        raise ValueError('Actual admitted14 required')
    checked={}
    for name,pin in REPAIRS.items():
        raw=reuse.read(repairs/name)
        if sha(raw)!=pin:raise ValueError('Exact audited GUI derivative required: '+name)
        checked[name]=raw
    reuse.launcher_scope(members['launcher.py'],checked['launcher.py'])
    compile(checked['launcher.py'],'launcher.py','exec')
    copied=output/'source';copied.mkdir()
    for name,raw in members.items():publish(copied.joinpath(*relative(name).parts),checked.get(name,raw))
    publish(copied/'README_GUI_OPTIONAL_POLICY.md',checked['README_GUI_OPTIONAL_POLICY.md'])
    publish(copied/'profiles/COMMON_BUNDLE.json',members['reference-v28/COMMON_BUNDLE.json'])
    result=build(copied,copied/'profiles',output,release_id='field-runtime-v29-build-15')
    package=Path(result['package'])
    comparison=reuse.compare(source,SOURCE_MANIFEST,package,result['manifest_sha256'])
    if result['native_launch_enabled'] or (package/'NATIVE_ADMISSION.json').exists():
        raise ValueError('Disabled15 may not inherit native authorization')
    verify_tree(package,result['manifest_sha256'])
    new_manifest,_,new_files=reuse.inventory(package,result['manifest_sha256'])
    expected=dict(new_files,**{'PACKAGE_MANIFEST.json':reuse.read(package/'PACKAGE_MANIFEST.json')})
    archive=Path(result['archive']);archive_raw=read_regular(archive)
    restored_archive=output/'independent-restore'/archive.name
    publish(restored_archive,archive_raw)
    seen=set();total=0;restored=output/'independent-restore/package'
    with tarfile.open(restored_archive,'r:gz') as stream:
        for row in stream:
            name=relative(row.name).as_posix()
            if not row.isfile() or name in seen or name not in expected:raise ValueError('Unexpected archive membership')
            if row.size!=len(expected[name]) or row.size>2*1024**2:raise ValueError('Archive member extent')
            total+=row.size
            if total>16*1024**2:raise ValueError('Archive aggregate bound')
            with stream.extractfile(row) as member:raw=member.read(row.size+1)
            if raw!=expected[name]:raise ValueError('Independent archive readback differs')
            publish(restored.joinpath(*relative(name).parts),raw);seen.add(name)
    if seen!=set(expected):raise ValueError('Archive omitted member')
    verify_tree(restored,result['manifest_sha256'])
    reuse.inventory(source,SOURCE_MANIFEST)
    for name,raw in checked.items():
        if reuse.read(repairs/name)!=raw:raise ValueError('Repair changed during preparation')
        for suffix in ('.backup','.restore'):publish(output/'reviewed-repairs'/(name+suffix),raw)
    for name in ('prepare_gui_policy_derivative.py','gui_policy_reuse.py','prepare_package.py'):
        raw=reuse.read(Path(__file__).with_name(name))
        for suffix in ('.backup','.restore'):publish(output/'tool-backups'/(name+suffix),raw)
    publish(output/'SOURCE_PACKAGE_MANIFEST.json',reuse.read(source/'PACKAGE_MANIFEST.json'))
    publish(output/'SOURCE_BINDING.json',members['BINDING.json'])
    publish(output/'UI_ONLY_REUSE_REQUIRES_REVIEW.json',encoded(comparison))
    publish(output/'UI_ONLY_REUSE_REQUIRES_REVIEW.restore.json',encoded(comparison))
    receipt=dict(schema='just-peachy.gui-policy-derivative.v1',source_package=str(source),
        source_manifest_sha256=SOURCE_MANIFEST,source_binding_sha256=SOURCE_BINDING,
        destination=result,changed_members=comparison['changed_members'],launcher_ast=comparison['launcher_ast'],
        independent_archive_and_member_restore=True,restored_files=len(seen),restored_bytes=total,
        builder_sha256=BUILDER,native_executed=False,native_qualified=False,production_accepted=False,
        evidence_reuse_certificate_sha256=sha(encoded(comparison)),evidence_reuse_reviewed=False)
    publish(output/'DERIVATION.json',encoded(receipt))
    return dict(result,derivation=str(output/'DERIVATION.json'),derivation_sha256=sha(encoded(receipt)),
                certificate=str(output/'UI_ONLY_REUSE_REQUIRES_REVIEW.json'),certificate_sha256=sha(encoded(comparison)))


def main():
    import psutil
    me=psutil.Process();me.cpu_affinity([14])
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('source','repairs','output-root'):ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args()
    if args.output_root not in (PRIVATE/'audit-preparation',PRIVATE/'storage-preparation') or args.output_root.resolve(strict=True)!=args.output_root:
        raise ValueError('Exact private preparation parent required')
    out=args.output_root/('gui-policy-derivative-'+uuid.uuid4().hex);out.mkdir()
    publish(out/'REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    sys.dont_write_bytecode=True
    for drive,floor in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<floor*1024**3+16*1024**2:raise OSError('Independent preparation reserve unavailable')
    try:print(json.dumps(prepare(args.source,args.repairs,out),sort_keys=True))
    except BaseException as error:
        publish(out/'FAILURE.json',json.dumps(dict(type=type(error).__name__,message=str(error)[:2048])).encode());raise


if __name__=='__main__':main()
