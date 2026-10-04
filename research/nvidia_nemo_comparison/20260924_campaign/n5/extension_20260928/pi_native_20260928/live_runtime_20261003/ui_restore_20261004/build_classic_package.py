"""Build the reviewed classic-UI repair as a fresh host package. See README_PACKAGE_REPAIR.md."""
import argparse
import ast
import copy
import ctypes
import gzip
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
import time
import uuid

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE = PRIVATE/'storage-preparation/production-finalization-451ce78e1e614f80ae7b650fe10caf58/package'
BASE_SHA = 'a88217b7dcdf0360309b4bea28baa376e6a55d64090fe64e2ba3cfeaa2cb2a73'
OLD_TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-16'
NEW_TARGET = OLD_TARGET[:-2]+'17'
USER_DATA = '/home/peachyprototype/JustPeachy/data/runtime-v29'
MAX_PACKAGE = MAX_PREPARATION = 16*1024**2
MAX_ARCHIVE = MAX_MEMBER = 2*1024**2
ALLOWED_REPLACEMENTS = {'launcher.py','worker.py','classic_frontend.py','installed_engine.py',
                        'xvf_readiness.py','xvf_readiness_helper.py',
                        'README_XVF_READINESS.md','README_RUNTIME_REPAIR.md',
                        'README_CLASSIC_FRONTEND.md','README_PACKAGE_REPAIR.md'}
CONTENT_EXCLUDED = {'BINDING.json','PRODUCTION_ACCEPTANCE.json','NATIVE_ADMISSION.json',
                    'PRODUCTION_BACKUP_MANIFEST.json','PRODUCTION_BACKUP_COMPLETE.json'}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, maximum=MAX_MEMBER):
    path = Path(path).resolve(strict=True)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
        raise ValueError('Bounded independent regular input required: '+str(path))
    with path.open('rb') as stream:
        raw = stream.read(maximum+1)
    after = path.stat()
    if len(raw) > maximum or (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Input changed during read: '+str(path))
    return raw


def relative(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or path.as_posix()!=name
        or '\\' in name or any(ord(char)<32 for char in name)):
        raise ValueError('Canonical relative package member required')
    return path.parts


class Output:
    def __init__(self, root):
        self.root = root
        self.bytes = 0
        self.expires = time.monotonic()+600
    def check(self, extra=0):
        if time.monotonic() > self.expires or self.bytes+extra > MAX_PREPARATION:
            raise RuntimeError('Finite 600-second / 16 MiB preparation scope exceeded')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free < floor+extra:
                raise OSError('Independent host free-space floor would be crossed')
    def write(self, path, raw):
        self.check(len(raw))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):
                raise OSError('Short preparation write')
            stream.flush();os.fsync(stream.fileno())
        self.bytes += len(raw)
        if read(path)!=raw:
            raise OSError('Independent output readback differs')


def bootstrap(output_parent):
    if os.name!='nt':
        raise RuntimeError('Windows CPU14 host preparation only; this builder never contacts the Pi')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    parent=Path(output_parent)
    if parent not in (PRIVATE/'audit-preparation',PRIVATE/'storage-preparation') or parent.resolve(strict=True)!=parent:
        raise ValueError('Exact existing private preparation parent required')
    root=parent/('classic-package-repair-'+uuid.uuid4().hex)
    root.mkdir(exist_ok=False)
    output=Output(root)
    output.write(root/'REGISTERED_OWNER.json',encoded(dict(pid=os.getpid(),cpu=14,
        affinity_mask=1<<14,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)))
    output.write(root/'HOST_SCOPE.json',encoded(dict(maximum_bytes=MAX_PREPARATION,
        maximum_seconds=600,issued_unix=time.time(),archive_maximum_bytes=MAX_ARCHIVE,
        target=NEW_TARGET,native_action=False)))
    return output


def inventory(base):
    if Path(base)!=BASE or BASE.resolve(strict=True)!=BASE:
        raise ValueError('Only the exact immutable reviewed build16 parent is supported')
    manifest_raw=read(BASE/'PACKAGE_MANIFEST.json',262144)
    if sha(manifest_raw)!=BASE_SHA:
        raise ValueError('Immutable build16 package manifest differs')
    manifest=strict(manifest_raw)
    if manifest.get('schema')!='just-peachy.v29.package.v1' or manifest.get('target')!=OLD_TARGET:
        raise ValueError('Exact production16 schema and target required')
    rows=manifest['files']
    if not 1<=len(rows)<=512:
        raise ValueError('Original 512-member cap retained')
    files={};aliases=set();total=0
    for row in rows:
        name=row['path'];parts=relative(name)
        if name in files or name.casefold() in aliases or type(row['bytes']) is not int:
            raise ValueError('Unique canonical typed inventory required')
        path=BASE.joinpath(*parts)
        if path.resolve(strict=True)!=path or path.is_symlink():
            raise ValueError('No linked package member')
        raw=read(path);total+=len(raw)
        if (len(raw),sha(raw))!=(row['bytes'],row['sha256']) or total>MAX_PACKAGE:
            raise ValueError('Parent full inventory bytes differ or exceed original cap')
        files[name]=raw;aliases.add(name.casefold())
    actual=set()
    for count,path in enumerate(BASE.rglob('*'),1):
        if count>4096 or path.is_symlink():
            raise ValueError('Bounded real parent tree required')
        if path.is_file():actual.add(path.relative_to(BASE).as_posix())
    if actual!=set(files)|{'PACKAGE_MANIFEST.json'}:
        raise ValueError('Parent complete file membership differs')
    return manifest,files


def move(value):
    if value==OLD_TARGET:return NEW_TARGET
    if isinstance(value,str) and value.startswith(OLD_TARGET+'/'):
        return NEW_TARGET+value[len(OLD_TARGET):]
    return value


def rows(files):
    return [dict(path=name,bytes=len(raw),sha256=sha(raw)) for name,raw in sorted(files.items())]


def ast_shape(node):
    return ast.dump(node,include_attributes=False)


def validate_repair_scope(before,replacements):
    """Constrain the root-reviewed hook and ASR-final presentation derivative."""
    original=ast.parse(before['launcher.py'],filename='parent/launcher.py')
    updated=ast.parse(replacements['launcher.py'],filename='repair/launcher.py')
    old_show=[node for node in original.body if isinstance(node,ast.FunctionDef) and node.name=='show']
    new_show=[node for node in updated.body if isinstance(node,ast.FunctionDef) and node.name=='show']
    laboratory=[node for node in updated.body if isinstance(node,ast.FunctionDef) and node.name=='laboratory_show']
    expected=ast.parse('def show(manager):\n from classic_frontend import show as portrait_show\n return portrait_show(manager)\n').body[0]
    if len(old_show)!=1 or len(new_show)!=1 or len(laboratory)!=1 or ast_shape(new_show[0])!=ast_shape(expected):
        raise ValueError('Exact classic frontend wrapper and retained laboratory view required')
    updated.body.remove(new_show[0]);laboratory[0].name='show'
    if ast_shape(laboratory[0])!=ast_shape(old_show[0]):
        raise ValueError('Retained laboratory interface body changed')
    hook=ast.parse("if selection.input_source == 'live':\n from xvf_readiness import recover_previous_source\n recover_previous_source(self)\n").body[0]
    manager=next(node for node in updated.body if isinstance(node,ast.ClassDef) and node.name=='Manager')
    start=next(node for node in manager.body if isinstance(node,ast.FunctionDef) and node.name=='start')
    hooks=[(index,node) for index,node in enumerate(start.body) if ast_shape(node)==ast_shape(hook)]
    if len(hooks)!=1:
        raise ValueError('Exactly one reviewed live-only readiness hook required')
    index,_=hooks[0]
    if (index==0 or not isinstance(start.body[index-1],ast.Assign)
        or ast_shape(start.body[index-1])!=ast_shape(ast.parse('optional_admission=request_receipt(self.binding,selection,policy)').body[0])):
        raise ValueError('Recovery hook must follow authorization/service-room/optional admission')
    start.body.pop(index)
    if ast_shape(updated)!=ast_shape(original):
        raise ValueError('Launcher changed outside the exact frontend wrapper/readiness hook')
    if not {'xvf_readiness.py','xvf_readiness_helper.py'}<=set(replacements):
        raise ValueError('The reviewed recovery hook requires both exact helper modules')
    receipt=dict(launcher_full_module_ast_identical_after_exact_wrapper_and_hook_removal=True,
                 recovery_hook_after_admission=True,worker_changed='worker.py' in replacements)
    if 'installed_engine.py' in replacements:
        old_engine=ast.parse(before['installed_engine.py'])
        new_engine=ast.parse(replacements['installed_engine.py'])
        removed=[]
        for node in ast.walk(new_engine):
            if isinstance(node,ast.Call):
                for keyword in list(node.keywords):
                    if keyword.arg=='asr_final':
                        removed.append(keyword);node.keywords.remove(keyword)
        keyword=ast.parse("dict(asr_final=row.get('final') is True)").body[0].value.keywords[0]
        if len(removed)!=1 or ast_shape(removed[0])!=ast_shape(keyword) or ast_shape(old_engine)!=ast_shape(new_engine):
            raise ValueError('Installed engine may only preserve the existing ASR final flag in caption provenance')
        receipt['installed_engine_full_module_ast_identical_after_one_asr_final_keyword_removal']=True
    return receipt


def derive(parent, files, replacements, reviewer):
    if not isinstance(reviewer,str) or not 1<=len(reviewer.strip())<=128:
        raise ValueError('Explicit reviewer for this concrete repair required')
    before_binding=strict(files['BINDING.json'])
    before_acceptance=strict(files['PRODUCTION_ACCEPTANCE.json'])
    if (before_binding['target']!=OLD_TARGET or before_binding['authorization_kind']!='production'
        or before_binding['native_launch_enabled'] is not True
        or sha(files['PRODUCTION_ACCEPTANCE.json'])!=before_binding['production_acceptance_sha256']):
        raise ValueError('Exact enabled production parent acceptance required')
    if not {'launcher.py','classic_frontend.py'}<=set(replacements):
        raise ValueError('Explicit paired launcher and new classic frontend replacements required')
    if set(replacements)-ALLOWED_REPLACEMENTS:
        raise ValueError('Only named frontend/startup repair modules and paired READMEs may change')
    source_scope=validate_repair_scope(files,replacements)
    changed=[]
    for name,raw in sorted(replacements.items()):
        if len(raw)>MAX_MEMBER or not raw:
            raise ValueError('Bounded nonempty replacement required')
        if name.endswith('.py'):
            compile(ast.parse(raw,filename=name),name,'exec')
        changed.append(dict(path=name,parent_sha256=sha(files[name]) if name in files else None,
                            replacement_sha256=sha(raw),bytes=len(raw)))
        files[name]=raw
        if name.endswith('.py'):
            for suffix in ('.backup','.restore'):
                files['source-backups/'+name+suffix]=raw
    binding=copy.deepcopy(before_binding)
    for key in ('target','reference_code','raw_factory_path'):
        binding[key]=move(binding[key])
    for row in binding['profiles'].values():row['path']=move(row['path'])
    acceptance=copy.deepcopy(before_acceptance)
    ordinary=[row for row in acceptance['allowed_selections'] if row['optional_d1_refiner'] is False]
    if len(ordinary)!=246 or any(row['provisional_correction'] is not False for row in ordinary):
        raise ValueError('Exact 246 ordinary single-diarizer selections required')
    removed=[row for row in acceptance['allowed_selections'] if row['optional_d1_refiner'] is True]
    acceptance['allowed_selections']=ordinary
    acceptance['optional_refiner_admissions']=[]
    acceptance['target']=NEW_TARGET
    acceptance['reviewer']=reviewer.strip()
    acceptance['accepted_unix']=time.time()
    for row in acceptance['assets']:
        old_path=row['path'];row['path']=move(row['path']);row['resolved']=move(row['resolved'])
        if row['path']!=old_path:
            relative_name=row['path'][len(NEW_TARGET)+1:]
            if relative_name not in files or (len(files[relative_name]),sha(files[relative_name]))!=(row['bytes'],row['sha256']):
                raise ValueError('Relocated package-local accepted asset bytes differ')
    # An old combined measurement cannot authorize newly changed runtime code.
    # Keep its evidence bytes and parent production acceptance immutable at BASE.
    for key in ('optional_refiner_admissions','optional_refiner_admission'):
        binding.pop(key,None)
    provenance=dict(schema='just-peachy.classic-runtime-repair.v1',reviewer=reviewer.strip(),
        reviewed_unix=acceptance['accepted_unix'],parent_target=OLD_TARGET,target=NEW_TARGET,
        parent_manifest_sha256=BASE_SHA,parent_binding_sha256=sha(files['BINDING.json']),
        parent_production_acceptance_sha256=sha(files['PRODUCTION_ACCEPTANCE.json']),
        parent_candidate_content_sha256=parent['candidate_content_sha256'],replacements=changed,
        exact_ast_scope=source_scope,
        ordinary_selections_sha256=sha(encoded(ordinary)),ordinary_selections=246,
        optional_selections_removed=removed,optional_refiner_admissions_reused=False,
        native_measurement_relabelled=False,native_qualification_pending=True,
        installed_models_and_galleries_changed=False,resource_storage_policy_changed=False,
        backend_profile_descriptors_changed=False,user_data_location_changed=False,
        preserved_external_data_root=USER_DATA,
        historical_acceptance_limitations=before_acceptance.get('limitations',[]))
    provenance_raw=encoded(provenance)
    files['REPAIR_PROVENANCE.json']=provenance_raw
    files['REPAIR_PROVENANCE.restore.json']=provenance_raw
    content_rows=rows({name:raw for name,raw in files.items()
        if name not in CONTENT_EXCLUDED and not name.startswith('source-backups/')})
    content_sha=sha(encoded(content_rows))
    acceptance['candidate_content_sha256']=binding['candidate_content_sha256']=content_sha
    acceptance['limitations']=[
        'Build17 restores the classic operator frontend and contains the explicitly reviewed startup repair. Native checks are pending; historical build16 and earlier measurements remain their original scopes.',
        'The 246 ordinary live/saved selections are permitted only for guarded field validation. This does not assert 246 independent native, sustainable real-time or quality passes.',
        'Optional parallel D1 refinement is disabled because its old measured admission binds different runtime content. No old combined admission is reauthorized.',
        'Models, separate galleries, BMI270 calibration, XVF routing, resource/storage guards, recordings and rollback releases remain unchanged. Prior limitations are retained in REPAIR_PROVENANCE.json.']
    # Preserve the validator-supported acceptance fields; provenance has its own files.
    if set(acceptance)!=set(before_acceptance):
        raise ValueError('Production acceptance schema fields changed')
    acceptance_raw=encoded(acceptance)
    binding['production_acceptance_sha256']=sha(acceptance_raw)
    binding['native_qualified']=False
    binding['admission_sha256']=None
    files['PRODUCTION_ACCEPTANCE.json']=acceptance_raw
    files['BINDING.json']=encoded(binding)
    manifest=copy.deepcopy(parent)
    manifest.update(target=NEW_TARGET,candidate_content_sha256=content_sha,files=rows(files))
    if len(files)+1>512 or sum(map(len,files.values()))>MAX_PACKAGE:
        raise ValueError('Original package file-count/expanded-byte caps exceeded')
    protected=set(before_binding)-{'target','reference_code','raw_factory_path','profiles',
        'candidate_content_sha256','production_acceptance_sha256','native_qualified','admission_sha256',
        'optional_refiner_admissions','optional_refiner_admission'}
    if any(binding[key]!=before_binding[key] for key in protected):
        raise ValueError('An unapproved operational pin changed')
    if acceptance['limits']!=before_acceptance['limits'] or binding['reference_files']!=before_binding['reference_files']:
        raise ValueError('Original resource/reference pins changed')
    return manifest,files,provenance


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=BASE)
    ap.add_argument('--base-manifest-sha256',default=BASE_SHA)
    ap.add_argument('--replacement',action='append',required=True,metavar='MODULE=PATH')
    ap.add_argument('--reviewer',required=True)
    ap.add_argument('--data-root',default=USER_DATA,
                    help='Preserved external recording store; emitted for separate Desktop activation')
    ap.add_argument('--output-root',type=Path,default=PRIVATE/'audit-preparation')
    args=ap.parse_args()
    output=bootstrap(args.output_root)
    if args.data_root!=USER_DATA:
        raise ValueError('Preserve the existing external recording store; no history migration is part of this repair')
    if args.base_manifest_sha256!=BASE_SHA:
        raise ValueError('Exact supplied parent manifest SHA required')
    parent,files=inventory(args.base)
    paths={};replacements={}
    for value in args.replacement:
        name,separator,path=value.partition('=')
        if not separator or name not in ALLOWED_REPLACEMENTS or name in paths:
            raise ValueError('Unique explicit MODULE=PATH replacement required')
        paths[name]=Path(path).resolve(strict=True);replacements[name]=read(paths[name])
    manifest,files,provenance=derive(parent,files,replacements,args.reviewer)
    package=output.root/'package';package.mkdir(exist_ok=False)
    for name,raw in sorted(files.items()):
        output.write(package.joinpath(*relative(name)),raw)
    manifest_raw=encoded(manifest)
    output.write(package/'PACKAGE_MANIFEST.json',manifest_raw)
    # Validate with only the exact copied pure validator/profile graph. Never
    # execute launcher, worker, installed engine, source or any model graph.
    forbidden={'release_authorization','profiles','optional_refiner_dispatch','optional_refiner_admission'}
    if forbidden&set(sys.modules):
        raise ValueError('Fresh pure validator module namespace required')
    sys.path.insert(0,str(package))
    try:
        module=importlib.import_module('release_authorization')
        if Path(module.__file__).resolve()!=package/'release_authorization.py':
            raise ValueError('Pure validator origin differs')
        module.validate_acceptance(strict(files['PRODUCTION_ACCEPTANCE.json']),strict(files['BINDING.json']))
    finally:
        sys.path.remove(str(package))
        for name in forbidden:sys.modules.pop(name,None)
    if any(read(paths[name])!=raw for name,raw in replacements.items()):
        raise ValueError('Replacement source changed during preparation')
    _,rechecked=inventory(args.base)
    for name,raw in rechecked.items():
        expected=next(row['sha256'] for row in parent['files'] if row['path']==name)
        if sha(raw)!=expected:raise ValueError('Immutable base changed')
    archive=output.root/'field-runtime-v29-build-17-prepared.tar.gz'
    payload=io.BytesIO()
    all_files=dict(files,**{'PACKAGE_MANIFEST.json':manifest_raw})
    with gzip.GzipFile(filename='',mode='wb',fileobj=payload,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w|',format=tarfile.PAX_FORMAT) as handle:
            for name,raw in sorted(all_files.items()):
                row=tarfile.TarInfo(name);row.size=len(raw);row.mode=0o600;row.mtime=0
                handle.addfile(row,io.BytesIO(raw))
    compressed_raw=payload.getvalue()
    if len(compressed_raw)>MAX_ARCHIVE:
        raise ValueError('Original 2 MiB archive cap exceeded')
    output.write(archive,compressed_raw)
    restored=set()
    with tarfile.open(fileobj=io.BytesIO(read(archive)),mode='r:gz') as handle:
        for member in handle:
            if not member.isfile() or member.name in restored or member.name not in all_files:
                raise ValueError('Archive restore membership differs')
            if handle.extractfile(member).read()!=all_files[member.name]:
                raise ValueError('Independent archive member readback differs')
            restored.add(member.name)
    if restored!=set(all_files):raise ValueError('Archive restore incomplete')
    result=dict(package=str(package),archive=str(archive),target=NEW_TARGET,
        data_root=USER_DATA,
        manifest_sha256=sha(manifest_raw),archive_sha256=sha(compressed_raw),
        candidate_content_sha256=manifest['candidate_content_sha256'],
        parent_manifest_sha256=BASE_SHA,files=len(files),ordinary_selections=246,
        optional_refiner_enabled=False,native_launch_enabled=True,native_qualified=False,
        installed=False,desktop_changed=False,source_backups_and_restores_exact=True,
        archive_members_independently_restored=len(restored),prepared_bytes=output.bytes)
    output.write(output.root/'BUILD_RESULT.json',encoded(result))
    output.write(output.root/'SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),
        prepared_bytes=output.bytes,scope_closed=True,native_action=False)))
    print(json.dumps(result))


if __name__=='__main__':
    sys.dont_write_bytecode=True
    main()
