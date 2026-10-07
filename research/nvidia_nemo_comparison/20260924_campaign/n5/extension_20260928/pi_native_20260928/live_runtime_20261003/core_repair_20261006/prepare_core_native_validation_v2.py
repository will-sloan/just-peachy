"""Prepare one focused live/saved UI operation. README_CORE_NATIVE_VALIDATION_V2.md."""
import argparse
import ast
import base64
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time
import types
import uuid

HERE=Path(__file__).parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
DATA='/home/peachyprototype/JustPeachy/data/runtime-v29'
NATIVE_PARENT='/home/peachyprototype/JustPeachy/research/nemotron-20260928'
HELPERS = {'live':('native_core_live_check_v2.py','5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e'),
           'saved':('native_core_saved_check_v2.py','01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237')}
OPERATOR_IDS = ('pyannote_redimnet','pyannote_titanet','delayed_redimnet','delayed_titanet',
                'chunk52_2t_redimnet','chunk52_2t_titanet')
RESERVE=256*1024**2
MAX_OUTPUT=2*1024**2


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            if key in result:raise ValueError('Duplicate payload input field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path,maximum=2*1024**2):
    path=Path(path)
    before=path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
        or before.st_size>maximum or any(parent.is_symlink() for parent in path.parents)):
        raise ValueError('Bounded independent real input required')
    raw=path.read_bytes();after=path.stat()
    if len(raw)!=before.st_size or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Input changed during read')
    return raw


def bootstrap(label):
    if os.name!='nt':raise RuntimeError('Windows host-only preparation')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('live-check-payload-'+label+'-'+uuid.uuid4().hex)
    root.mkdir()
    raw=encoded(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
        cpu=14,affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000))
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short early owner write')
        stream.flush();os.fsync(stream.fileno())
    if (root/'REGISTERED_OWNER.json').read_bytes()!=raw:raise OSError('Early owner readback')
    return root


class Output:
    def __init__(self,root):
        self.root=root;self.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
        self.started=time.monotonic()
    def write(self,name,raw):
        if self.bytes+len(raw)>MAX_OUTPUT or time.monotonic()-self.started>600:
            raise RuntimeError('Finite600s/2MiB payload preparation scope exceeded')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Host free-space floor')
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short prepared payload write')
            stream.flush();os.fsync(stream.fileno())
        self.bytes+=len(raw)
        if read(path)!=raw:raise OSError('Independent prepared readback differs')


def inventory(package,pin):
    package=Path(package)
    if (not package.is_absolute() or package.resolve(strict=True)!=package or package.is_symlink()
        or not package.is_relative_to(PRIVATE)):
        raise ValueError('Exact private canonical package input required')
    raw=read(package/'PACKAGE_MANIFEST.json',262144)
    if sha(raw)!=pin:raise ValueError('Explicit actual package manifest hash differs')
    manifest=strict(raw);rows=manifest.get('files')
    if (manifest.get('schema')!='just-peachy.v29.package.v1' or type(rows) is not list
        or not 1<=len(rows)<=512 or re.fullmatch(re.escape(NATIVE_PARENT)+r'/field-runtime-v29-build-[0-9]{2}',manifest.get('target','')) is None):
        raise ValueError('Actual bounded versioned package required')
    files={};aliases=set();total=0
    for row in rows:
        name=row['path'];rel=PurePosixPath(name)
        if (type(name) is not str or rel.is_absolute() or '..' in rel.parts or '\\' in name
            or rel.as_posix()!=name or name.casefold() in aliases or type(row.get('bytes')) is not int):
            raise ValueError('Canonical unique typed package member')
        raw=read(package.joinpath(*rel.parts))
        total+=len(raw)
        if (len(raw),sha(raw))!=(row['bytes'],row['sha256']) or total>16*1024**2:
            raise ValueError('Package inventory bytes/hash/cap differs')
        files[name]=raw;aliases.add(name.casefold())
    actual=set()
    for count,path in enumerate(package.rglob('*'),1):
        if count>4096 or path.is_symlink():raise ValueError('Real bounded package tree')
        if path.is_file():actual.add(path.relative_to(package).as_posix())
    if actual!=set(files)|{'PACKAGE_MANIFEST.json'}:raise ValueError('Complete package membership differs')
    return manifest,files


def selected(files,identifier,input_source):
    if 'profiles' in sys.modules:raise ValueError('Fresh pure profile namespace required')
    # Only the existing pure profile/catalogue modules are executed. Never call
    # chooser, launcher, source, model, GUI, gallery or runtime constructors.
    modules={}
    try:
        for name,filename in (('profiles','profiles.py'),('_payload_operator_profiles','operator_profiles.py')):
            tree=ast.parse(files[filename])
            imports={alias.name.split('.')[0] for node in tree.body if isinstance(node,ast.Import) for alias in node.names}
            imports.update(node.module.split('.')[0] for node in tree.body if isinstance(node,ast.ImportFrom) and node.module)
            if imports-{'__future__','dataclasses','math','json','profiles'}:
                raise ValueError('Unexpected pure module top-level dependency')
            module=types.ModuleType(name);module.__file__=filename
            sys.modules[name]=module;modules[name]=module
            exec(compile(tree,'<pinned-payload-pure:'+filename+'>','exec'),module.__dict__)
        profiles=modules['profiles'];catalogue=modules['_payload_operator_profiles']
        rows=catalogue._OPERATOR
        matches=[row for row in rows if row.id==identifier]
        if len(rows)!=6 or len(matches)!=1:raise ValueError('One of the six exact chooser names required')
        actual=catalogue.selection_for(matches[0].id,input_source).validate()
        if actual['provisional_correction'] or actual['optional_d1_refiner']:
            raise ValueError('Focused check excludes parallel/provisional refinement')
        return actual,matches[0].label
    finally:
        for name,module in modules.items():
            if sys.modules.get(name) is module:sys.modules.pop(name)


def allocation(files,input_source):
    """Same exact storage arithmetic as V5, without a Store/source constructor."""
    tree=ast.parse(files['storage.py'])
    names={'StoragePolicy','metadata_limits','_validate_spec'}
    nodes=[node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name in names]
    if len(nodes)!=3:raise ValueError('Exact three pure storage definitions required')
    space=dict(__name__=__name__,dataclass=dataclass,json=json,math=__import__('math'))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-pinned-storage-arithmetic>','exec'),space)
    binding=strict(files['BINDING.json']);seconds=70
    spec=dict(sample_rate=16000,mode='processed',duration_seconds=seconds,
        metadata_reserve_bytes=2*(16*1024**2+seconds*256*1024),
        metadata_split='text1_sqlite1_v2',terminal_metadata_reserve_bytes=256*1024)
    if input_source=='live' and binding.get('raw_adapter_enabled') is True:
        spec.update(mode='raw_processed',raw=dict(sample_rate=16000,channels=4,sample_width_bytes=4,
            encoding='PCM_S32LE',qualification=dict(qualified=True,
                evidence='allocation only; actual worker verifies independently qualified physical raw route')))
    policy=space['StoragePolicy'](**binding.get('storage_policy',{}))
    plan=policy.estimate_bytes(spec)+32*1024**2
    if plan>RESERVE:raise ValueError('Complete exact storage plan exceeds full independent reserve')
    return dict(spec=spec,complete_plan_bytes=plan,limits=space['metadata_limits'](spec,policy.metadata_allowance_bytes),
        native_history_db_fit_still_requires_fresh_worker_check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True,help='Actual private immutable package folder')
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--boot-id',required=True,help='Actual current native boot; never generated here')
    parser.add_argument('--kind',choices=tuple(HELPERS),required=True)
    parser.add_argument('--operator-id',choices=OPERATOR_IDS,required=True)
    parser.add_argument('--operation',choices=('launch','finalize'),default='launch')
    parser.add_argument('--label',required=True,help='One explicit unused classic-ui-check-34 through99')
    parser.add_argument('--discard-session',action='store_true',help='Explicitly discard only the new validation output after closure')
    parser.add_argument('--saved-metadata-file',type=Path)
    parser.add_argument('--saved-metadata-sha256')
    args=parser.parse_args()
    if (re.fullmatch(r'classic-ui-check-(?:3[4-9]|[4-9][0-9])',args.label) is None
        or re.fullmatch('[0-9a-f]{64}',args.manifest_sha256) is None or
        re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',args.boot_id) is None):
        raise ValueError('Exact unused focused label, package pin and actual current boot required')
    if args.kind=='live' and not args.discard_session:
        raise ValueError('Focused live check requires explicit new-session Discard')
    if (args.kind=='saved')!=(args.saved_metadata_file is not None and args.saved_metadata_sha256 is not None):
        raise ValueError('Saved validation requires its exact pinned captured session.json')
    output=Output(bootstrap(args.label)) # BEFORE project/package input reads.
    sys.dont_write_bytecode=True
    output.write('HOST_SCOPE.json',encoded(dict(maximum_bytes=MAX_OUTPUT,maximum_seconds=600,
        cpu=14,native_action=False,label=args.label)))
    helper_name,helper_pin = HELPERS[args.kind]
    helper=read(HERE/helper_name,65536)
    if sha(helper)!=helper_pin:raise ValueError('Exact backed focused helper required')
    early_inputs={'PREPARER.py':read(Path(__file__)),'README.md':read(HERE/'README_CORE_NATIVE_VALIDATION_V2.md'),
        'ACTION.py':helper}
    for name,raw in early_inputs.items():
        for suffix in ('','.backup','.restore'):output.write(name+suffix,raw)
    output.write('SOURCE_PRECHECK_CLOSED.json',encoded(dict(closed_unix=time.time(),independent_restores=True,
        source_hashes={name:sha(raw) for name,raw in early_inputs.items()},native_action=False)))
    compile(helper,'<focused-core-native-validation>','exec')
    if args.operation=='launch' and any(PRIVATE.glob(args.label+'-monitor-*')):
        raise ValueError('Label already has preserved native monitor evidence')
    manifest,files=inventory(args.package,args.manifest_sha256)
    if manifest['target']!=NATIVE_PARENT+'/field-runtime-v29-build-29':
        raise ValueError('Exact repaired build29 target required')
    actual,chooser_label=selected(files,args.operator_id,args.kind)
    raw_input=encoded(actual)
    plan=allocation(files,args.kind)
    saved = None
    if args.kind=='saved':
        raw_saved=read(args.saved_metadata_file,65536)
        if sha(raw_saved)!=args.saved_metadata_sha256:
            raise ValueError('Exact captured saved session.json differs')
        saved=strict(raw_saved)
        if (saved.get('status')!='kept' or re.fullmatch(r'[0-9a-f]{32}',saved.get('session_id','')) is None or
            saved.get('spec',{}).get('sample_rate')!=16000 or type(saved.get('processed_samples')) is not int or
            not 0<saved['processed_samples']<=70*16000):
            raise ValueError('Same complete kept saved source must fit the existing finite <=70s qualification')
        output.write('SAVED_SOURCE_METADATA.json',raw_saved)
    payload=dict(operation=args.operation,package=manifest['target'],
        package_manifest_sha256=args.manifest_sha256,boot_id=args.boot_id,
        label=args.label,expires_unix=time.time()+590,data_root=DATA,
        chooser_label=chooser_label,selection=actual,stop_after_seconds=12,
        prepare_gallery=False,discard_session=args.discard_session,
        maximum_output_bytes=RESERVE,independent_pc_copy_bytes=RESERVE,
        helper_source_sha256=helper_pin,helper_source_b64=base64.b64encode(helper).decode())
    if saved is not None:
        payload.update(saved_session_id=saved['session_id'],saved_metadata_sha256=args.saved_metadata_sha256,
            application_mode='enrolled_names',seating=None)
    if args.operation=='finalize':
        payload['output_root']=NATIVE_PARENT+'/live-runtime-tests-20261003/'+args.label
    raw_payload=encoded(payload)
    if len(raw_payload)>131072:raise ValueError('Payload must remain bounded')
    inputs={'PAYLOAD.json':raw_payload,'SELECTION_INPUT.json':raw_input,'ALLOCATION.json':encoded(plan)}
    for name,raw in inputs.items():
        for suffix in ('','.backup','.restore'):output.write(name+suffix,raw)
    if read(HERE/helper_name,65536)!=helper:
        raise ValueError('Original helper changed during preparation')
    if read(args.package/'PACKAGE_MANIFEST.json',262144)!=encoded(manifest):
        # Manifest bytes may be formatted; compare their explicit supplied hash.
        if sha(read(args.package/'PACKAGE_MANIFEST.json',262144))!=args.manifest_sha256:
            raise ValueError('Actual package manifest changed')
    closed=dict(closed_unix=time.time(),prepared_bytes=output.bytes,independent_restores=True,
        helper_sha256=helper_pin,payload_sha256=sha(raw_payload),native_action=False,
        actual_boot_supplied=args.boot_id,operator_id=args.operator_id,kind=args.kind,operation=args.operation,
        source_seconds=70 if saved is None else saved['processed_samples']/16000,stop_after_seconds=12,
        target_reservation_bytes=RESERVE,independent_pc_reservation_bytes=RESERVE,
        kept_unless_explicit_discard=not args.discard_session,complete_pure_plan=plan)
    output.write('SOURCE_CLOSED.json',encoded(closed))
    print(encoded(dict(output=str(output.root),payload=str(output.root/'PAYLOAD.json'),
        action=str(output.root/'ACTION.py'),label=args.label,selection=actual,
        chooser_label=chooser_label,expires_unix=payload['expires_unix'],
        target_reservation_bytes=RESERVE,independent_pc_reservation_bytes=RESERVE,
        native_action=False)).decode())


if __name__=='__main__':main()

