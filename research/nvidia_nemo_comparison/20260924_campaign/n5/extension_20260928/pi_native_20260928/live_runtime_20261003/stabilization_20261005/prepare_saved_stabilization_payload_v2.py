"""Prepare one explicit saved backend replay payload; README_PREPARE_SAVED_STABILIZATION_V2.md.

Host only. This never dispatches SSH, starts a model, or invents a recording ID.
Generate each operation freshly after the preceding operation is closed.
"""
import argparse
import base64
import ctypes
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time
import uuid

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
NATIVE = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/'
DATA = '/home/peachyprototype/JustPeachy/data/runtime-v29'
MIB = 1024**2
LIMIT = 8*MIB
RESERVATION = 128*MIB
OPERATOR_IDS = ('pyannote_redimnet','pyannote_titanet','delayed_redimnet',
                'delayed_titanet','chunk52_2t_redimnet','chunk52_2t_titanet')
MODES = ('enrolled_names','spatial_assisted','strongly_spatial_assisted',
         'assigned_direction','assigned_hybrid')
HELPER_PIN = 'ca4570ca3411b743a20f4d510fb3065d149d2c9747bc10869c33d8ba8bfdc933'


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:
                raise ValueError('Duplicate payload input field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite input')))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def exact_text(value, pattern, description):
    if type(value) is not str or re.fullmatch(pattern,value) is None:
        raise ValueError(description)
    return value


def validated(args):
    if args.source!='saved' or args.operator_id not in OPERATOR_IDS:
        raise ValueError('One explicit intended operator backend and Saved source required')
    if args.operation not in ('launch','finalize') or args.application_mode not in MODES:
        raise ValueError('Known explicit phase and application Mode required')
    exact_text(args.native_label,r'classic-ui-check-\d{2}','Fresh finite native test label required')
    exact_text(args.dispatch_label,r'[a-z0-9][a-z0-9-]{3,63}','Fresh simple host operation label required')
    exact_text(args.boot_id,r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}','Explicit observed boot UUID required')
    exact_text(args.session_id,r'[0-9a-f]{32}','Explicit actual kept recording UUID required')
    exact_text(args.session_metadata_sha256,r'[0-9a-f]{64}','Explicit observed session.json raw-byte SHA required')
    exact_text(args.package_manifest_sha256,r'[0-9a-f]{64}','Exact selected package manifest SHA required')
    if args.native_package!=NATIVE+'field-runtime-v29-build-24' or args.data_root!=DATA:
        raise ValueError('This generator binds only the explicit staged build24 and canonical owned data root')
    if type(args.ttl_seconds) is not int or not 60<=args.ttl_seconds<=600:
        raise ValueError('Explicit60-to600-second fresh payload lifetime required')
    if args.package_dir is None:
        raise ValueError('Existing verified host package directory required')
    if (args.application_mode in ('assigned_direction','assigned_hybrid')) != (args.seating is not None):
        raise ValueError('Assigned Modes require an explicit actual-person recorded-reference seat draft')
    return args


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check',action='store_true',help='Only new source syntax/lexical contracts; no native payload')
    parser.add_argument('--operation',choices=('launch','finalize'),default='launch')
    parser.add_argument('--operator-id',choices=OPERATOR_IDS)
    parser.add_argument('--source',choices=('saved',))
    parser.add_argument('--package-dir',type=Path)
    parser.add_argument('--native-package')
    parser.add_argument('--package-manifest-sha256')
    parser.add_argument('--boot-id')
    parser.add_argument('--session-id')
    parser.add_argument('--session-metadata-sha256')
    parser.add_argument('--session-json',type=Path,help='Optional actual PC mirror of original session.json')
    parser.add_argument('--native-label')
    parser.add_argument('--dispatch-label')
    parser.add_argument('--data-root')
    parser.add_argument('--application-mode',choices=MODES,default='enrolled_names')
    parser.add_argument('--seating',type=Path)
    parser.add_argument('--discard-output',action='store_true')
    parser.add_argument('--ttl-seconds',type=int,default=590)
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    output=PRIVATE/'audit-preparation'/('saved-stabilization-payload-v2-'+uuid.uuid4().hex)
    output.mkdir()
    started=time.time()
    written=0
    def put(name,raw):
        nonlocal written
        if type(raw) is not bytes or len(raw)>2*MIB or written+len(raw)>LIMIT or time.time()-started>600:
            raise ValueError('Bounded cumulative host preparation bytes/time required')
        with (output/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):
                raise OSError('Short host payload publication')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if (output/name).read_bytes()!=raw:
            raise OSError('Host payload readback differs')
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
        creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000,
        cpu=14,affinity_mask=16384)
    put('REGISTERED_OWNER.json',encoded(owner))
    put('HOST_SCOPE.json',encoded(dict(issued_unix=started,maximum_seconds=600,
        maximum_bytes=LIMIT,purpose='one fresh explicit Saved backend payload; no campaign',native_action=False)))
    status='FAILED'
    def read(path,maximum=128*1024):
        path=Path(path);before=path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or
                before.st_size>maximum or time.time()-started>600):
            raise ValueError('Finite real unaliased host input required')
        raw=path.read_bytes();after=path.stat()
        if len(raw)!=before.st_size or (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size):
            raise ValueError('Host input changed during read')
        return raw
    pins=[]
    def backup(path,maximum=128*1024):
        raw=read(path,maximum)
        number=len(pins)
        put('SOURCE_%02d.backup'%number,raw)
        restored=(output/('SOURCE_%02d.backup'%number)).read_bytes()
        put('SOURCE_%02d.restore'%number,restored)
        if restored!=raw or read(path,maximum)!=raw:
            raise OSError('Independent source restore or original differs')
        pins.append(dict(path=str(path),bytes=len(raw),sha256=digest(raw)))
        return raw
    try:
        floors=[]
        for drive,gib in (('C:/',50),('G:/',75)):
            free=shutil.disk_usage(drive).free
            if free<gib*1024**3+LIMIT+RESERVATION:
                raise OSError('Independent host copy reserve and drive floor required')
            floors.append(dict(drive=drive,free_bytes=free,floor_bytes=gib*1024**3,
                preparation_bytes=LIMIT,independent_pc_copy_bytes=RESERVATION))
        generator=backup(Path(__file__))
        backup(here/'README_PREPARE_SAVED_STABILIZATION_V2.md')
        helper=backup(here/'native_saved_stabilization_check_v2.py')
        dispatcher=backup(here/'host_stabilization_operations_v2.py')
        if len(helper)>65536 or digest(helper)!=HELPER_PIN:
            raise ValueError('Exact reviewed kept-session replay helper required')
        if args.self_check:
            put('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),pins=pins,
                exact_backup=True,independent_restore=True,before_execution=True)))
            compile(generator,str(__file__),'exec')
            compile(helper,'<backed-native-saved-helper>','exec')
            rejects=0
            for value,pattern in (('bad-session',r'[0-9a-f]{32}'),('classic-ui-check-100',r'classic-ui-check-\d{2}'),
                                  ('not-a-hash',r'[0-9a-f]{64}')):
                try:exact_text(value,pattern,'Rejected synthetic lexical input')
                except ValueError:rejects+=1
                else:raise AssertionError('Invalid source pin/label accepted')
            status='PASS_HOST_PAYLOAD_GENERATOR_SOURCE_ONLY'
            put('RESULT.json',encoded(dict(status=status,lexical_rejects=rejects,operator_ids=list(OPERATOR_IDS),
                payload_issued=False,uuid_or_native_proof_invented=False,native_action=False,
                source_sha256=digest(generator),host_bytes=written,elapsed_seconds=time.time()-started)))
        else:
            validated(args)
            package=args.package_dir.resolve(strict=True)
            if args.package_dir.is_symlink() or not package.is_dir():
                raise ValueError('Actual immutable host package directory required')
            manifest_raw=backup(package/'PACKAGE_MANIFEST.json',262144)
            if digest(manifest_raw)!=args.package_manifest_sha256:
                raise ValueError('Exact current host package manifest bytes required')
            manifest=strict(manifest_raw)
            if manifest.get('target')!=args.native_package:
                raise ValueError('Actual host manifest target differs from requested build24')
            rows=manifest.get('files')
            if type(rows) is not list or not 1<=len(rows)<=1024:
                raise ValueError('Bounded complete prepared package required')
            members={};total=0
            for row in rows:
                if type(row) is not dict or set(row)!={'path','bytes','sha256'}:
                    raise ValueError('Exact package member shape required')
                name=row['path'];relative=PurePosixPath(name)
                if (type(name) is not str or relative.is_absolute() or str(relative)!=name or
                        '\\' in name or any(v in ('','..','.') for v in relative.parts) or
                        name.casefold() in members or type(row['bytes']) is not int or row['bytes']<0):
                    raise ValueError('Unique canonical package member required')
                raw=read(package.joinpath(*relative.parts),8*MIB)
                if len(raw)!=row['bytes'] or digest(raw)!=row['sha256']:
                    raise ValueError('Complete current package member readback differs')
                members[name.casefold()]=row;total+=len(raw)
                if total>32*MIB:
                    raise ValueError('Finite code package verification bound')
            for name in ('profiles.py','operator_profiles.py','application_contract.py'):
                if name.casefold() not in members:
                    raise ValueError('Pinned pure operator dependency required: '+name)
                backup(package/name)
            seating=None
            if args.seating is not None:
                seating=strict(backup(args.seating,65536))
                if type(seating) is not dict or set(seating)!={'rows','strength','acknowledged'}:
                    raise ValueError('Explicit recorded-reference actual-person seat draft required')
            if args.session_json is not None:
                source_raw=backup(args.session_json,65536)
                source=strict(source_raw)
                if (digest(source_raw)!=args.session_metadata_sha256 or source.get('session_id')!=args.session_id or
                        source.get('status')!='kept' or source.get('spec',{}).get('sample_rate')!=16000 or
                        type(source.get('processed_samples')) is not int or not 0<source['processed_samples']<=90*16000):
                    raise ValueError('Actual mirrored short kept source metadata differs')
            put('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),pins=pins,
                exact_backup=True,independent_restore=True,before_execution=True,package_members=len(rows),
                complete_package_bytes_verified=total,package_manifest_sha256=args.package_manifest_sha256)))
            sys.dont_write_bytecode=True
            if {'profiles','operator_profiles','application_contract'} & set(sys.modules):
                raise ValueError('Project profile import collision')
            sys.path.insert(0,str(package))
            profiles=importlib.import_module('operator_profiles')
            matrix=profiles.catalog()
            if tuple(row['id'] for row in matrix)!=OPERATOR_IDS:
                raise ValueError('Actual prepared six-profile catalogue differs')
            selection=profiles.selection_for(args.operator_id,'saved').validate()
            for name in ('profiles','operator_profiles','application_contract'):
                if Path(sys.modules[name].__file__).resolve()!=package/(name+'.py'):
                    raise ValueError('Actual pure operator module origin differs')
            descriptor=next(row for row in matrix if row['id']==args.operator_id)
            compile(helper,'<backed-native-saved-helper>','exec')
            issued=time.time();expires=issued+args.ttl_seconds
            payload=dict(operation=args.operation,boot_id=args.boot_id,package=args.native_package,
                package_manifest_sha256=args.package_manifest_sha256,data_root=args.data_root,
                expires_unix=expires,label=args.native_label,maximum_output_bytes=RESERVATION,
                independent_pc_copy_bytes=RESERVATION,chooser_label=descriptor['label'],selection=selection,
                saved_session_id=args.session_id,saved_metadata_sha256=args.session_metadata_sha256,
                application_mode=args.application_mode,seating=seating,prepare_gallery=False,
                discard_session=args.discard_output,manual_stop_test=False,
                helper_source_b64=base64.b64encode(helper).decode(),helper_source_sha256=HELPER_PIN)
            if args.operation=='finalize':
                payload['output_root']=NATIVE+'live-runtime-tests-20261003/'+args.native_label
            payload_raw=encoded(payload)
            for name,raw in (('PAYLOAD.json',payload_raw),('ACTION.py',helper)):
                for suffix in ('','.backup','.restore'):
                    put(name+suffix,raw)
            command=[sys.executable,'-B',str(here/'host_stabilization_operations_v2.py'),
                '--label',args.dispatch_label,'--action',str(output/'ACTION.py'),
                '--payload',str(output/'PAYLOAD.json'),'--writes']
            status='PREPARED_HOST_SAVED_PAYLOAD_NOT_DISPATCHED'
            result=dict(status=status,output=str(output),payload=str(output/'PAYLOAD.json'),action=str(output/'ACTION.py'),
                operation=args.operation,native_label=args.native_label,operator_id=args.operator_id,selection=selection,
                source_session_id=args.session_id,source_metadata_sha256=args.session_metadata_sha256,
                source_metadata_verified_host=args.session_json is not None,application_mode=args.application_mode,
                native_package=args.native_package,package_manifest_sha256=args.package_manifest_sha256,
                boot_id=args.boot_id,issued_unix=issued,expires_unix=expires,maximum_output_bytes=RESERVATION,
                independent_pc_copy_bytes=RESERVATION,helper_sha256=HELPER_PIN,dispatcher_sha256=digest(dispatcher),
                command_argv=command,host_drive_reservations=floors,native_admission_issued=False,
                native_dispatched=False,host_bytes=written,source_pins_sha256=digest(encoded(pins)))
            put('RESULT.json',encoded(result))
        print(encoded(dict(output=str(output),status=status,
            result=str(output/'RESULT.json'),native_dispatched=False)).decode())
    finally:
        put('EXIT_INTENT.json',encoded(dict(owner=owner,status=status,physical_closure_claimed=False)))


if __name__=='__main__':
    main()
