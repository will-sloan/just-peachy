"""External UI-only evidence comparison/composition; README_GUI_POLICY_REUSE.md."""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import time
import uuid

AUTH={'native_launch_enabled','authorization_kind','production_acceptance_sha256','admission_sha256'}
CHANGES={'launcher.py','source-backups/launcher.py.backup','source-backups/launcher.py.restore',
         'README_GUI_OPTIONAL_POLICY.md','BINDING.json','NATIVE_ADMISSION.json'}
HELPERS={'gui_session_policy','gui_policy_summary'}
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()


def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))


def read(path,maximum=2*1024**2):
    path=Path(path);before=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>maximum:
        raise ValueError('Bounded canonical regular input required')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    after=path.stat()
    if len(raw)>maximum or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('Input changed')
    return raw


def write(path,raw):
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short write')
        stream.flush();os.fsync(stream.fileno())
    if path.read_bytes()!=raw:raise OSError('Readback mismatch')


def inventory(root,manifest_sha):
    root=Path(root);raw=read(root/'PACKAGE_MANIFEST.json');manifest=strict(raw)
    if sha(raw)!=manifest_sha or manifest['schema']!='just-peachy.v29.package.v1':raise ValueError('Exact package manifest required')
    if not 1<=len(manifest['files'])<=512:raise ValueError('Finite package inventory')
    members={};total=0
    for row in manifest['files']:
        name=row['path'];rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or str(rel)!=name or name in members:
            raise ValueError('Canonical unique package member')
        data=read(root.joinpath(*rel.parts));total+=len(data)
        if (len(data),sha(data))!=(row['bytes'],row['sha256']) or total>32*1024**2:raise ValueError('Package bytes differ or exceed bound')
        members[name]=data
    actual=set()
    for count,path in enumerate(root.rglob('*'),1):
        if count>2048:raise ValueError('Package tree membership bound')
        if path.is_symlink():raise ValueError('Package link refused')
        if path.is_file():actual.add(path.relative_to(root).as_posix())
    if actual!=set(members)|{'PACKAGE_MANIFEST.json'}:raise ValueError('Full package membership differs')
    binding=strict(members['BINDING.json'])
    if binding['candidate_content_sha256']!=manifest['candidate_content_sha256'] or binding['target']!=manifest['target']:
        raise ValueError('Manifest/binding identity differs')
    return manifest,binding,members


def normalized_binding(binding):
    value={k:copy.deepcopy(v) for k,v in binding.items() if k not in AUTH}
    root=value['target']
    def move(path):
        if path==root:return 'ROOT'
        if not path.startswith(root+'/'):raise ValueError('Unexpected operational source-root path')
        return 'ROOT'+path[len(root):]
    for key in ('target','reference_code','raw_factory_path'):value[key]=move(value[key])
    for row in value['profiles'].values():row['path']=move(row['path'])
    value['candidate_content_sha256']='CONTENT'
    return value


def launcher_scope(before,after):
    old=ast.parse(before);new=ast.parse(after)
    old_names={n.name for n in old.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    new_names={n.name for n in new.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    if HELPERS&old_names or new_names-old_names!=HELPERS or old_names-new_names:
        raise ValueError('Only two reviewed GUI policy helper definitions may be added')
    def rest(tree):
        return ast.dump(ast.Module(body=[n for n in tree.body if not isinstance(n,ast.FunctionDef)
            or n.name not in HELPERS|{'show'}],type_ignores=[]),include_attributes=False)
    if rest(old)!=rest(new):raise ValueError('Non-GUI module/Manager/worker-facing AST changed')
    return dict(all_preexisting_non_show_ast_identical=True,manager_ast_identical=True,
                added_helpers=sorted(HELPERS),changed_existing_function='show')


def compare(source,source_sha,destination,destination_sha):
    sm,sb,sfiles=inventory(source,source_sha);dm,db,dfiles=inventory(destination,destination_sha)
    if sm['target']==dm['target'] or sm['candidate_content_sha256']==dm['candidate_content_sha256']:
        raise ValueError('Explicit distinct UI-only candidate required')
    if normalized_binding(sb)!=normalized_binding(db):raise ValueError('Non-UI operational binding changed')
    changed=sorted(name for name in set(sfiles)|set(dfiles) if sfiles.get(name)!=dfiles.get(name))
    if not set(changed)<=CHANGES or not {'launcher.py','README_GUI_OPTIONAL_POLICY.md','BINDING.json'}<=set(changed):
        raise ValueError('Full inventory contains an unapproved non-GUI delta')
    if 'README_GUI_OPTIONAL_POLICY.md' in sfiles:raise ValueError('Expected new paired UI policy README')
    for files in (sfiles,dfiles):
        for suffix in ('.backup','.restore'):
            if files['launcher.py']!=files['source-backups/launcher.py'+suffix]:raise ValueError('Independent launcher copies differ')
    scope=launcher_scope(sfiles['launcher.py'],dfiles['launcher.py'])
    rows=[]
    for name in changed:
        rows.append(dict(path=name,source=None if name not in sfiles else dict(bytes=len(sfiles[name]),sha256=sha(sfiles[name])),
                         destination=None if name not in dfiles else dict(bytes=len(dfiles[name]),sha256=sha(dfiles[name]))))
    return dict(schema='just-peachy.reviewed-gui-policy-reuse.v1',reviewed=False,reviewer='PENDING independent root review',reviewed_unix=0,
        source_target=sb['target'],destination_target=db['target'],source_manifest_sha256=source_sha,destination_manifest_sha256=destination_sha,
        source_binding_sha256=sha(sfiles['BINDING.json']),destination_binding_sha256=sha(dfiles['BINDING.json']),
        source_content_sha256=sb['candidate_content_sha256'],destination_content_sha256=db['candidate_content_sha256'],
        installed_manifest_sha256=sb['installed_manifest_sha256'],changed_members=rows,
        unchanged_members=len(set(sfiles)&set(dfiles)-set(changed)),launcher_ast=scope,
        scope='UI policy selection/display only; actual measurement remains source14, destination UI requires targeted controls/idle check',
        actual_destination_native_measurement_claimed=False,worker_source_model_storage_optional_code_unchanged=True,
        input_audio_or_measured_policy_changed=False)


def validate_certificate(raw,digest,source,source_sha,ui,ui_sha):
    if sha(raw)!=digest:raise ValueError('UI review certificate SHA differs')
    value=strict(raw);expected=compare(source,source_sha,ui,ui_sha)
    review_keys={'reviewed','reviewer','reviewed_unix'}
    if ({k:v for k,v in value.items() if k not in review_keys}!={k:v for k,v in expected.items() if k not in review_keys}
        or value.get('reviewed') is not True or not isinstance(value.get('reviewer'),str) or not value['reviewer'].strip()
        or type(value.get('reviewed_unix')) not in (int,float) or not 0<value['reviewed_unix']<=time.time()+60):
        raise ValueError('Exact independently reviewed UI-only certificate required')
    return value


def compose_measured_admission(source_raw,source_receipt_sha,ui_certificate_raw,ui_certificate_sha,
        source_package,source_manifest_sha,ui_package,ui_manifest_sha,final_binding,
        path_certificate_raw,path_certificate_sha,selected_assets,builder,admission,profiles,reviewer,reviewed_unix):
    """One derivation from original actual measurement; never chain derived facts."""
    if not isinstance(reviewer,str) or not reviewer.strip() or type(reviewed_unix) not in (int,float) or not 0<reviewed_unix<=time.time()+60:
        raise ValueError('Explicit final receipt reuse review required')
    cert=validate_certificate(ui_certificate_raw,ui_certificate_sha,source_package,source_manifest_sha,ui_package,ui_manifest_sha)
    _,source_binding,source_files=inventory(source_package,source_manifest_sha)
    _,ui_binding,ui_files=inventory(ui_package,ui_manifest_sha)
    if sha(source_raw)!=source_receipt_sha or sha(path_certificate_raw)!=path_certificate_sha:raise ValueError('Exact measured/path certificate pins required')
    builder.validate_relocation(strict(path_certificate_raw),ui_binding,final_binding,ui_manifest_sha,ui_files['BINDING.json'])
    original=strict(source_raw)
    if (original.get('reuse_basis') is not None or original.get('qualified_binding_sha256')!=sha(source_files['BINDING.json'])
        or original.get('qualified_package_manifest_sha256')!=source_manifest_sha):raise ValueError('Original actual source measurement required')
    if not isinstance(selected_assets,list) or not 1<=len(selected_assets)<=512:raise ValueError('Exact selected native asset rows required')
    paths=set()
    for row in selected_assets:
        if set(row)!={'path','resolved','bytes','sha256'} or row['path'] in paths:raise ValueError('Exact unique selected asset row')
        for name in ('path','resolved'):
            path=PurePosixPath(row[name])
            if not path.is_absolute() or '..' in path.parts or str(path)!=row[name]:raise ValueError('Canonical selected asset path')
            if any(row[name]==root or row[name].startswith(root+'/') for root in (source_binding['target'],ui_binding['target'],final_binding['target'])):
                raise ValueError('Selected native asset cannot be a changed package-local member')
        if type(row['bytes']) is not int or row['bytes']<=0 or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None:raise ValueError('Selected asset pin')
        paths.add(row['path'])
    inventory_sha=sha(encoded(sorted(selected_assets,key=lambda row:row['path'])))
    expected=dict(candidate_content_sha256=source_binding['candidate_content_sha256'],installed_manifest_sha256=source_binding['installed_manifest_sha256'],
        operational_binding_sha256=admission.operational_binding_sha256(source_binding),selected_asset_inventory_sha256=inventory_sha)
    selection=profiles.RuntimeSelection(**original['selection']);policy=profiles.SessionPolicy(**original['policy'])
    total=original['measured']['total_ram_bytes']
    admission.validate_admission(source_raw,source_receipt_sha,selection,policy,expected,0,physical_ram_bytes=total,phase='historical_evidence')
    if final_binding['candidate_content_sha256']!=cert['destination_content_sha256']:raise ValueError('Final runtime content differs from reviewed UI candidate')
    derived=copy.deepcopy(original)
    derived['pins']['candidate_content_sha256']=final_binding['candidate_content_sha256']
    derived['pins']['operational_binding_sha256']=admission.operational_binding_sha256(final_binding)
    derived['reuse_basis']=dict(schema='just-peachy.reviewed-gui-policy-and-path-reuse.v1',reviewed=True,reviewer=reviewer,reviewed_unix=reviewed_unix,
        original_measured_receipt_sha256=source_receipt_sha,original_measured_target=source_binding['target'],ui_target=ui_binding['target'],final_target=final_binding['target'],
        gui_certificate_sha256=ui_certificate_sha,path_certificate_sha256=path_certificate_sha,
        source_qualified_binding_sha256=original['qualified_binding_sha256'],source_qualified_package_manifest_sha256=source_manifest_sha,
        selected_asset_inventory_sha256=inventory_sha,measured_facts_changed=False,measured_policy_changed=False,
        destination_native_measurement_claimed=False,scope='Actual14 measured facts retained; reviewed UI-only15 plus path-only16, no new combined measurement claimed')
    unchanged=copy.deepcopy(derived);unchanged.pop('reuse_basis');unchanged['pins']=copy.deepcopy(original['pins'])
    if encoded(unchanged)!=encoded(original):raise AssertionError('Measured facts changed')
    result=encoded(derived)
    admission.validate_admission(result,sha(result),selection,policy,derived['pins'],0,physical_ram_bytes=total,phase='historical_evidence')
    return derived


def main():
    import psutil
    me=psutil.Process();me.cpu_affinity([14]);ap=argparse.ArgumentParser(description=__doc__)
    for name in ('source','source-manifest-sha256','ui','ui-manifest-sha256','output-root'):ap.add_argument('--'+name,required=True)
    args=ap.parse_args();parent=Path(args.output_root)
    if parent not in (PRIVATE/'storage-preparation',PRIVATE/'audit-preparation') or parent.resolve(strict=True)!=parent:
        raise ValueError('Exact existing private preparation parent required')
    out=parent/('gui-policy-reuse-'+uuid.uuid4().hex);out.mkdir()
    write(out/'REGISTERED_OWNER.json',encoded(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    for drive,gib in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<gib*1024**3+16*1024**2:raise OSError('Independent preparation reserve unavailable')
    result=compare(Path(args.source),args.source_manifest_sha256,Path(args.ui),args.ui_manifest_sha256)
    write(out/'UI_ONLY_REUSE_REQUIRES_REVIEW.json',encoded(result));write(out/'UI_ONLY_REUSE_REQUIRES_REVIEW.restore.json',encoded(result))
    print(json.dumps(dict(output=str(out),reviewed=False,changed_members=len(result['changed_members']))))


if __name__=='__main__':main()
