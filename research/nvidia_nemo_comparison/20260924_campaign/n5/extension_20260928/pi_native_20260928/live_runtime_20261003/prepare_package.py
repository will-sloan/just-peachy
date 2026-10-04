"""Build a fresh offline v29 candidate, never install it. See README_PACKAGE.md."""
import argparse
import ast
import base64
import ctypes
import gzip
import hashlib
import json
import math
import os
import re
from pathlib import Path, PurePosixPath
import tarfile
import time
import uuid

BASE_MANIFEST = '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
TARGET_PARENT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928'
RUNTIME_FILES = ('launcher.py', 'worker.py', 'installed_engine.py', 'installed_source.py',
    'audio_journal.py', 'storage.py', 'profiles.py', 'nemotron_binding.py', 'runtime_support.py',
    'telemetry.py', 'refinement.py', 'correction.py', 'native_scope.py', 'install_candidate.py',
    'native_benchmark.py')
OPTIONAL_RUNTIME_FILES = ('raw_capture.py','raw_qualification.py','release_authorization.py',
    'owned_export.py',
    'sparse_embedding.py','late_labels.py','admitted_identity.py','saved_replay.py','saved_source_metrics.py',
    'launch_raw_qualification_action.py','launch_pipeline_qualification_action.py',
    'native_variant.py','native_gui_driver.py','source_batch.py','model_load_trace.py',
    'runtime_ui.py','runtime_ui_channel.py','native_storage_check.py','launch_storage_check_action.py',
    'launch_gui_check_action.py','desktop_rollback_action.py','event_compaction.py',
    'developer_replay.py','final_snapshot.py','launch_full_app_soak_action.py',
    'backup_reconciliation.py','native_backup_guard.py','native_backup_probe.py',
    'reconcile_production_backup.py','launch_backup_action.py','launch_recording_export_action.py',
    'native_job_probe.py','monitor_native_job.py',
    'optional_refiner.py','optional_refiner_admission.py','optional_refiner_worker.py',
    'optional_refiner_protocol.py','optional_refiner_labels.py','optional_refiner_dispatch.py',
    'optional_refiner_qualification.py','optional_refiner_resources.py','optional_refiner_qualification_cli.py')


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


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('Fresh artifact readback failed')


def bootstrap(output_root):
    # Affinity and numeric process creation time precede every project read.
    if os.name != 'nt':
        raise RuntimeError('Package preparation is the Windows CPU14 host action')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 1 << 14):
        raise ctypes.WinError(ctypes.get_last_error())
    values = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(x) for x in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    directory = Path(output_root) / ('package-preparation-' + uuid.uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    write(directory/'REGISTERED_OWNER.json', encoded(dict(
        schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=1 << 14, creation_filetime=values[0].value,
        create_time=(values[0].value-116444736000000000)/10000000)))
    return directory


def relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or path.as_posix() != name:
        raise ValueError('Unsafe package member: ' + name)
    return path


def read_regular(path, maximum=2*1024**2):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('Bounded regular package input required: ' + str(path))
    return path.read_bytes()


def verify_local_imports(files,available_modules):
    included={Path(name).stem for name in files if name.endswith('.py') and '/' not in name}
    for name,raw in files.items():
        if not name.endswith('.py'):continue
        tree=ast.parse(raw,filename=name)
        imports=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:imports.add(node.module.split('.')[0])
            elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                  and node.func.attr=='import_module' and node.args
                  and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str)):
                imports.add(node.args[0].value.split('.')[0])
        missing=(imports & available_modules)-included
        if missing:raise ValueError('Runtime local imports missing from package: '+name+' -> '+','.join(sorted(missing)))


def select_options(current,source_batch_ms=None,native_variant=None,native_variant_sha256=None):
    if (native_variant is None)!=(native_variant_sha256 is None):raise ValueError('Native variant path and SHA256 are a pair')
    requested=dict(current) if current is not None else dict(schema='just-peachy.v29.build-options.v1',source_batch_ms=0)
    if source_batch_ms is not None:requested['source_batch_ms']=source_batch_ms
    if native_variant is not None:
        requested['native_variants']={'chunk52_threads2':dict(path=native_variant,sha256=native_variant_sha256)}
    if (not {'schema','source_batch_ms'}<=set(requested) or set(requested)-{'schema','source_batch_ms','native_variants','raw_qualification_reference'}
        or requested['schema']!='just-peachy.v29.build-options.v1'
        or type(requested['source_batch_ms']) is not int or requested['source_batch_ms'] not in (0,100)):
        raise ValueError('Exact bounded build options required')
    if 'native_variants' in requested:
        variants=requested['native_variants']
        if type(variants) is not dict or set(variants)!={'chunk52_threads2'}:raise ValueError('Exact opt-in native variant required')
        pin=variants['chunk52_threads2']
        if type(pin) is not dict or set(pin)!={'path','sha256'} or type(pin['path']) is not str or type(pin['sha256']) is not str:
            raise ValueError('Exact native variant path/SHA256 required')
        path=PurePosixPath(pin['path'])
        if (path.as_posix()!=pin['path'] or '\\' in pin['path'] or '..' in path.parts
            or path.name!='RUNTIME_VARIANT.json' or path.parent.parent!=PurePosixPath(TARGET_PARENT)/'live-runtime-tests-20261003'
            or re.fullmatch('[a-z0-9-]{4,48}',path.parent.name) is None or re.fullmatch('[0-9a-f]{64}',pin['sha256']) is None):
            raise ValueError('Pinned isolated native variant descriptor required')
    if current is not None and current!=requested:raise ValueError('Frozen build options cannot change')
    return requested if current is not None or source_batch_ms is not None or native_variant is not None else None


RAW_REFERENCE_FILES=('RAW_QUALIFICATION_PROOF.json','RAW_QUALIFICATION_MIRROR_MANIFEST.json',
                     'RAW_QUALIFICATION_MIRROR_COMPLETE.json','RAW_QUALIFICATION_JOB.json')

AUTHORIZATION_KEYS={'native_launch_enabled','authorization_kind','production_acceptance_sha256','admission_sha256'}


def operational_binding(value):
    return {key:item for key,item in value.items() if key not in AUTHORIZATION_KEYS}


def validate_relocation(certificate,source_binding,destination_binding,source_manifest_sha256,source_binding_raw):
    """Explicit reviewed path-only move; this never relabels a native measurement."""
    keys={'schema','reviewed','reviewer','reviewed_unix','source_target','destination_target',
          'source_manifest_sha256','source_binding_sha256','candidate_content_sha256','installed_manifest_sha256',
          'source_operational_binding_sha256','destination_operational_binding_sha256','relocations',
          'runtime_behavior_changed','measurement_reuse_requires_separate_review'}
    if (type(certificate) is not dict or set(certificate)!=keys
            or certificate.get('schema')!='just-peachy.reviewed-runtime-relocation.v1'
            or certificate.get('reviewed') is not True or type(certificate.get('reviewer')) is not str
            or not 1<=len(certificate['reviewer'].strip())<=128
            or type(certificate.get('reviewed_unix')) not in (int,float)
            or not math.isfinite(certificate['reviewed_unix']) or not 0<certificate['reviewed_unix']<=time.time()+60
            or certificate.get('runtime_behavior_changed') is not False
            or certificate.get('measurement_reuse_requires_separate_review') is not True):
        raise ValueError('Exact explicitly reviewed path-only relocation certificate required')
    for key in ('source_manifest_sha256','source_binding_sha256','candidate_content_sha256','installed_manifest_sha256',
                'source_operational_binding_sha256','destination_operational_binding_sha256'):
        if type(certificate[key]) is not str or re.fullmatch('[0-9a-f]{64}',certificate[key]) is None:
            raise ValueError('Exact relocation SHA256 pins required')
    before=source_binding['target'];after=destination_binding['target']
    if (before==after or certificate['source_target']!=before or certificate['destination_target']!=after
            or any(re.fullmatch(re.escape(TARGET_PARENT)+r'/field-runtime-v29-build-[0-9]+',value) is None for value in (before,after))
            or certificate['source_manifest_sha256']!=source_manifest_sha256
            or certificate['source_binding_sha256']!=sha(source_binding_raw)
            or strict(source_binding_raw)!=source_binding
            or any(binding.get(key)!=certificate[key] for binding in (source_binding,destination_binding)
                   for key in ('candidate_content_sha256','installed_manifest_sha256'))):
        raise ValueError('Actual source/destination relocation provenance differs')
    expected=strict(encoded(source_binding));relocations=[]
    def move(field,value):
        if value==before:updated=after
        elif type(value) is str and value.startswith(before+'/'):updated=after+value[len(before):]
        else:raise ValueError('Relocation field is not under its exact source root: '+field)
        relocations.append(dict(field=field,source=value,destination=updated));return updated
    expected['target']=move('target',expected['target'])
    expected['reference_code']=move('reference_code',expected['reference_code'])
    expected['raw_factory_path']=move('raw_factory_path',expected['raw_factory_path'])
    for key,row in expected['profiles'].items():row['path']=move('profiles.'+key+'.path',row['path'])
    relocations.sort(key=lambda row:row['field'])
    if certificate['relocations']!=relocations:
        raise ValueError('Exact complete sorted relocation field mapping required')
    old=encoded(operational_binding(source_binding));new=encoded(operational_binding(destination_binding))
    if (encoded(operational_binding(expected))!=new
            or sha(old)!=certificate['source_operational_binding_sha256']
            or sha(new)!=certificate['destination_operational_binding_sha256']):
        raise ValueError('Relocation changed runtime behavior or an unapproved operational field')
    return certificate


def raw_reference_input(native_path,expected_sha,mirror):
    """Verify every byte of the exact closed local raw qualification mirror."""
    native=PurePosixPath(native_path)
    expected_parent=PurePosixPath(TARGET_PARENT)/'live-runtime-tests-20261003'
    if (native.as_posix()!=native_path or '\\' in native_path or '..' in native.parts
            or native.name!='RAW_QUALIFICATION.json' or native.parent.name!='qualification'
            or native.parent.parent.parent!=expected_parent
            or not re.fullmatch('raw-qualification-[0-9]{2}',native.parent.parent.name)
            or not re.fullmatch('[0-9a-f]{64}',expected_sha)):
        raise ValueError('Exact native raw qualification receipt path/SHA required')
    mirror=Path(mirror).resolve(strict=True)
    manifest=read_regular(mirror/'MIRROR_MANIFEST.json',262144)
    completion=read_regular(mirror/'MIRROR_COMPLETE.json',65536)
    rows,closed=strict(manifest),strict(completion)
    if (not isinstance(rows,list) or not 1<=len(rows)<=256 or closed.get('kind')!='COMPLETE'
            or closed.get('mirror_scope')!='all_regular_output_files' or closed.get('files')!=len(rows)
            or sha(encoded(rows))!=closed.get('manifest_sha256')
            or type(closed.get('bytes')) is not int or not 0<closed['bytes']<=16*1024**2):
        raise ValueError('Bounded complete raw mirror required')
    source=mirror/'closed-output';expected=set();total=0
    for row in rows:
        name=relative(row['path']).as_posix()
        if name.casefold() in expected:raise ValueError('Duplicate raw mirror member')
        expected.add(name.casefold());path=source/name
        if path.resolve(strict=True)!=path or path.is_symlink() or not path.is_file():raise ValueError('Real raw mirror member')
        size=row['identity']['bytes']
        if type(size) is not int or size<0:raise ValueError('Raw mirror extent type')
        total+=size
        if total>16*1024**2 or path.stat().st_size!=size:raise ValueError('Raw mirror extent bound')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:raise ValueError('Raw mirror independent PC readback differs')
    actual=set();stack=[source];directories=0
    while stack:
        directory=stack.pop();directories+=1
        if directories>256:raise ValueError('Raw mirror directory bound')
        with os.scandir(directory) as entries:
            for entry in entries:
                path=Path(entry.path)
                if entry.is_symlink():raise ValueError('Raw mirror link refused')
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                    if len(stack)+directories>256:raise ValueError('Raw mirror directory membership bound')
                elif entry.is_file(follow_symlinks=False):
                    actual.add(path.relative_to(source).as_posix().casefold())
                    if len(actual)>256:raise ValueError('Raw mirror file bound')
                else:raise ValueError('Raw mirror special member')
    if actual!=expected or total!=closed['bytes']:raise ValueError('Full raw mirror membership/size differs')
    proof=read_regular(source/'qualification/RAW_QUALIFICATION.json',1024**2)
    job=read_regular(source/'JOB.json',65536)
    if sha(proof)!=expected_sha:raise ValueError('Explicit raw qualification SHA differs')
    reference=dict(path=native_path,sha256=expected_sha,mirror_manifest_sha256=sha(manifest),
        mirror_completion_sha256=sha(completion),job_sha256=sha(job))
    return reference,dict(zip(RAW_REFERENCE_FILES,(proof,manifest,completion,job)))


def verify_raw_reference(reference,documents,runtime_files,source_batch_ms,factory_sha256):
    if type(reference) is not dict or set(reference)!={'path','sha256','mirror_manifest_sha256','mirror_completion_sha256','job_sha256'}:
        raise ValueError('Exact immutable raw reference fields required')
    for key in ('sha256','mirror_manifest_sha256','mirror_completion_sha256','job_sha256'):
        if type(reference[key]) is not str or not re.fullmatch('[0-9a-f]{64}',reference[key]):raise ValueError('Raw reference SHA required')
    proof_raw,manifest_raw,complete_raw,job_raw=(documents[name] for name in RAW_REFERENCE_FILES)
    if tuple(map(sha,(proof_raw,manifest_raw,complete_raw,job_raw)))!=tuple(reference[key] for key in ('sha256','mirror_manifest_sha256','mirror_completion_sha256','job_sha256')):
        raise ValueError('Frozen raw proof documents changed')
    proof,rows,complete,job=map(strict,(proof_raw,manifest_raw,complete_raw,job_raw))
    if (any(type(value) is not dict for value in (proof,complete,job))
            or not isinstance(rows,list) or not 1<=len(rows)<=256
            or type(reference['path']) is not str):raise ValueError('Bounded raw proof document shapes required')
    closure=complete.get('closure',{})
    owner=proof.get('owner');exit_row=closure.get('job_exit',{})
    if (type(owner) is not dict or set(owner)!={'pid','start_ticks','boot_id'}
            or any(type(owner.get(key)) is not int or owner[key]<=0 for key in ('pid','start_ticks'))
            or type(owner.get('boot_id')) is not str or not owner['boot_id']
            or type(exit_row) is not dict):raise ValueError('Actual numeric raw owner required')
    native=PurePosixPath(reference['path'])
    if (native.as_posix()!=reference['path'] or '\\' in reference['path'] or '..' in native.parts
            or str(native)!=job.get('output_root','')+'/qualification/RAW_QUALIFICATION.json'
            or native.parent.parent.parent!=PurePosixPath(TARGET_PARENT)/'live-runtime-tests-20261003'
            or not re.fullmatch('raw-qualification-[0-9]{2}',native.parent.parent.name)
            or job.get('schema')!='just-peachy.native-component-job.v1'
            or job.get('unit')!='jp-v29-'+native.parent.parent.name+'.service'
            or proof.get('unit')!=job['unit'] or proof.get('unit_invocation')!=job.get('invocation_id')
            or owner!=closure.get('owner') or owner['boot_id']!=job.get('boot_id')
            or (job.get('owner') is not None and owner!=job['owner'])
            or (job.get('owner') is None and closure.get('owner_recaptured') is not True)
            or closure.get('unit')!=job['unit']
            or closure.get('invocation_id')!=job['invocation_id']
            or closure.get('control_group')!=job.get('control_group') or not job.get('control_group')
            or not all(closure.get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty'))
            or exit_row.get('owner')!=owner or exit_row.get('unit')!=job['unit']
            or exit_row.get('invocation_id')!=job['invocation_id']
            or exit_row.get('natural_returncode')!=0 or exit_row.get('error') is not None
            or exit_row.get('leases_released') is not True or exit_row.get('output_budget_failure') is not None
            or complete.get('kind')!='COMPLETE' or complete.get('files')!=len(rows)
            or complete.get('mirror_scope')!='all_regular_output_files'
            or type(complete.get('bytes')) is not int or not 0<complete['bytes']<=16*1024**2
            or sha(encoded(rows))!=complete.get('manifest_sha256')):
        raise ValueError('Actual successful exact-job raw closure required')
    for name,raw in (('qualification/RAW_QUALIFICATION.json',proof_raw),('JOB.json',job_raw)):
        matching=[row for row in rows if row.get('path')==name]
        if len(matching)!=1 or matching[0].get('sha256')!=sha(raw) or matching[0].get('identity',{}).get('bytes')!=len(raw):
            raise ValueError('Raw proof/job is not an exact fully mirrored member')
    checks=('source_clock_checked','raw_readback_checked','processed_readback_checked','route_restored',
            'stream_closed','lease_released','source_owner_closed')
    if (proof.get('status')!='RAW_NATIVE_QUALIFICATION_PASSED' or proof.get('native_executed') is not True
            or proof.get('duration_seconds')!=5 or any(proof.get(key) is not True for key in checks)
            or proof.get('raw_channels')!=4 or proof.get('raw_samples')!=80000
            or proof.get('processed_samples')!=80000 or proof.get('raw_bytes')!=1280000
            or proof.get('processed_bytes')!=320000 or proof.get('failure') or proof.get('cleanup_failure')):
        raise ValueError('Complete five-second actual raw/processed qualification required')
    physical=proof.get('physical',{});raw=physical.get('raw_capture',{})
    if (physical.get('kind')!='CLOSED' or physical.get('error') is not None or physical.get('stream_closed') is not True
            or physical.get('lease_released') is not True or physical.get('source_batch_ms')!=source_batch_ms
            or physical.get('integrity',{}).get('ok') is not True
            or physical.get('integrity',{}).get('restoration_ok') is not True
            or physical.get('status',{}).get('dropped_frames')!=0
            or raw.get('derivation',{}).get('factory_sha256')!=factory_sha256
            or raw.get('channel_order')!=['MIC0','MIC1','MIC2','MIC3']):
        raise ValueError('Qualified source batch/factory/physical layout differs')
    for filename,key in (('installed_source.py','installed_source_sha256'),('raw_capture.py','raw_capture_sha256'),('source_batch.py','source_batch_sha256')):
        if sha(runtime_files[filename])!=proof.get(key):raise ValueError('Raw proof module differs from new immutable source: '+filename)
    return dict(qualified=True,adapter_native_qualified=True,evidence=reference['path'],
                evidence_sha256=reference['sha256'],mirror_manifest_sha256=reference['mirror_manifest_sha256'],
                mirror_completion_sha256=reference['mirror_completion_sha256'])


def live_configuration(template,options):
    live=dict(template,evidence_dir=None)
    if options is not None and options['source_batch_ms']==100:
        # The pinned app.live_audio.LiveConfig default is480. Make the source
        # geometry explicit so batching never depends on an implicit default.
        if 'block_frames' in live and (type(live['block_frames']) is not int or live['block_frames']!=480):
            raise ValueError('Reviewed batch mode requires retained480-frame source blocks')
        live['block_frames']=480
    return live


def verify_full_backup(acceptance):
    backup=acceptance['full_backup']
    root=Path(backup['root']).resolve(strict=True)
    paths=[Path(backup['manifest_path']),Path(backup['completion_path'])]
    raw=[read_regular(path,2*1024**2) for path in paths]
    if sha(raw[0])!=backup['manifest_sha256'] or sha(raw[1])!=backup['completion_sha256']:
        raise ValueError('Reviewed full backup receipts changed')
    rows,completion=map(strict,raw)
    if (not isinstance(rows,list) or not 1<=len(rows)<=4096 or completion.get('kind')!='COMPLETE'
        or completion.get('mirror_scope')!='all_regular_output_files'
        or not completion.get('closure',{}).get('closed')
        or not completion.get('closure',{}).get('exact_owner_gone')
        or not completion.get('closure',{}).get('cgroup_empty')
        or completion.get('files')!=len(rows) or sha(encoded(rows))!=completion.get('manifest_sha256')):
        raise ValueError('Full closed-source/PC backup completion proof required')
    expected=set();total=0
    for row in rows:
        name=relative(row['path']).as_posix()
        if name in expected:raise ValueError('Duplicate backup member')
        expected.add(name);path=root/name
        if path.is_symlink() or path.resolve(strict=True)!=path or not path.is_file():
            raise ValueError('Real complete backup member required')
        size=row['identity']['bytes'];total+=size
        if path.stat().st_size!=size:raise ValueError('Full backup extent changed')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:
                raise ValueError('Full backup PC readback changed')
    actual=set()
    for path in root.rglob('*'):
        if path.is_symlink():raise ValueError('Symlink in full backup')
        if path.is_file():
            name=path.relative_to(root).as_posix()
            if name not in expected:raise ValueError('Unlisted full backup file')
            actual.add(name)
    if actual!=expected or total!=completion['bytes']:raise ValueError('Full backup membership/byte count differs')
    return raw


def build(source, profiles, output, admission_path=None, release_id='field-runtime-v29', production_path=None,
          snapshot_manifest_sha256=None, source_batch_ms=None, native_variant=None, native_variant_sha256=None,
          raw_qualification_reference=None,raw_qualification_sha256=None,raw_qualification_mirror=None,
          relocation_certificate_path=None,relocation_certificate_sha256=None):
    if admission_path and production_path:raise ValueError('Qualification and production authorization are distinct')
    if not re.fullmatch(r'field-runtime-v29(?:-build-[0-9]+)?', release_id):
        raise ValueError('Explicit independent v29 release identifier required')
    target = TARGET_PARENT + '/' + release_id
    source, profiles = Path(source).resolve(strict=True), Path(profiles).resolve(strict=True)
    source_binding=None;source_binding_raw=None;relocation_raw=None
    if (relocation_certificate_path is None)!=(relocation_certificate_sha256 is None):
        raise ValueError('Relocation certificate path and SHA256 are a pair')
    if relocation_certificate_path is not None:
        if snapshot_manifest_sha256 is None:raise ValueError('Relocation requires an exact immutable source snapshot')
        relocation_raw=read_regular(Path(relocation_certificate_path),65536)
        if sha(relocation_raw)!=relocation_certificate_sha256:raise ValueError('Reviewed relocation certificate SHA256 differs')
    if snapshot_manifest_sha256 is not None:
        from install_candidate import verify_tree
        verify_tree(source,snapshot_manifest_sha256)
        if profiles!=source/'profiles':raise ValueError('Frozen profile directory must belong to the exact source snapshot')
        source_binding_raw=read_regular(source/'BINDING.json',65536);source_binding=strict(source_binding_raw)
    bundle_path=profiles/'COMMON_BUNDLE.json'
    if snapshot_manifest_sha256 is not None:bundle_path=source/'reference-v28/COMMON_BUNDLE.json'
    bundle_raw = read_regular(bundle_path)
    capsule = strict(bundle_raw)
    rows = capsule['manifest']['files']
    if len(rows) != 66 or len(capsule['files']) != 66:
        raise ValueError('Exact retained 66-file v28 capsule required')
    content = {}
    for row in rows:
        name = relative(row['path']).as_posix()
        if name in content:
            raise ValueError('Duplicate capsule member')
        raw = base64.b64decode(capsule['files'][name], validate=True)
        if len(raw) != row['bytes'] or sha(raw) != row['sha256']:
            raise ValueError('Retained capsule digest mismatch: ' + name)
        content[name] = raw
    if set(content) != set(capsule['files']):
        raise ValueError('Capsule inventory mismatch')
    old_config = strict(content['broker/CONFIG.json'])
    template = strict(content['broker/TEMPLATE.json'])
    if old_config['installed_manifest_sha256'] != BASE_MANIFEST:
        raise ValueError('Unexpected installed release source')
    runtime_files = RUNTIME_FILES + tuple(name for name in OPTIONAL_RUNTIME_FILES if (source/name).exists())
    files = {name: read_regular(source/name) for name in runtime_files}
    verify_local_imports(files,{path.stem for path in source.glob('*.py')})
    if b'raw_capture' in files['installed_source.py'] and 'raw_capture.py' not in files:
        # Older processed-only adapters mention raw_capture as a policy key;
        # require the module only when the source contains its actual import.
        tree = ast.parse(files['installed_source.py'])
        if any(isinstance(node, ast.ImportFrom) and node.module == 'raw_capture' or
               isinstance(node, ast.Import) and any(alias.name == 'raw_capture' for alias in node.names)
               for node in ast.walk(tree)):
            raise ValueError('Raw-integrated source requires its bounded raw_capture.py module')
    for name, raw in list(files.items()):
        if name.endswith('.py'):
            compile(raw, name, 'exec')
    # Runtime options affect admission content as well as BINDING.json. A later
    # admitted copy inherits these exact frozen options without mutable input.
    options_path=source/'BUILD_OPTIONS.json'
    options_raw=read_regular(options_path,4096) if options_path.exists() else None
    options=select_options(strict(options_raw) if options_raw is not None else None,
                           source_batch_ms,native_variant,native_variant_sha256)
    raw_arguments=(raw_qualification_reference,raw_qualification_sha256,raw_qualification_mirror)
    if any(value is not None for value in raw_arguments) and not all(value is not None for value in raw_arguments):
        raise ValueError('Raw native path, SHA and complete local mirror must be supplied together')
    raw_documents={};raw_evidence=None
    if raw_qualification_reference is not None:
        if snapshot_manifest_sha256 is not None:raise ValueError('Frozen raw operational reference cannot change during admission')
        reference,raw_documents=raw_reference_input(*raw_arguments)
        if options is None:options=dict(schema='just-peachy.v29.build-options.v1',source_batch_ms=0)
        if options.get('raw_qualification_reference') not in (None,reference):raise ValueError('Existing raw build reference cannot change')
        options=dict(options,raw_qualification_reference=reference);options_raw=None
    if options is not None and 'raw_qualification_reference' in options:
        if not raw_documents:raw_documents={name:read_regular(source/name,1024**2) for name in RAW_REFERENCE_FILES}
        raw_evidence=verify_raw_reference(options['raw_qualification_reference'],raw_documents,files,
            options['source_batch_ms'],sha(content['code/field_live_source_factory_v6.py']))
        files.update(raw_documents)
    if options is not None:
        if options['source_batch_ms'] and 'source_batch.py' not in files:raise ValueError('Batch option requires pinned source module')
        files['BUILD_OPTIONS.json']=options_raw if options_raw is not None else encoded(options)
    # Include all run instructions, and preserve two independently read-back
    # source copies. Neither copy is imported or included on runtime sys.path.
    for path in source.glob('README*.md'):
        files[path.name] = read_regular(path)
    for path in (source/'pipelines').glob('*.md'):
        files['pipelines/'+path.name] = read_regular(path)
    for path in (source/'component_evidence').glob('*.json'):
        files['component_evidence/'+path.name]=read_regular(path,262144)
    if options and options.get('native_variants') and 'component_evidence/chunk52_threads2_review.json' not in files:
        raise ValueError('Thread2 opt-in needs its pinned component review receipt')
    files['native_audit.md'] = read_regular(source/'native_audit.md')
    files.update({'reference-v28/'+name: raw for name, raw in content.items()})
    files['reference-v28/COMMON_BUNDLE.json'] = bundle_raw
    descriptors = {}
    for path in sorted(profiles.glob('*.json')):
        if path.name == 'COMMON_BUNDLE.json':
            continue
        raw = read_regular(path, 65536)
        document = strict(raw)
        if document.get('schema') != 'just-peachy.runtime-profile-descriptor.v1':
            raise ValueError('Unexpected profile descriptor')
        files['profiles/'+path.name] = raw
        descriptors[path.stem] = dict(path=target+'/profiles/'+path.name, sha256=sha(raw))
    required = {'baseline','baseline-titanet','d1-delayed','d1-delayed-titanet',
                'd1-streaming-saved','d1-streaming-titanet-saved'}
    if not required <= descriptors.keys():
        raise ValueError('Missing installed engine descriptor')
    inventory = [dict(path=name, bytes=len(raw), sha256=sha(raw)) for name, raw in sorted(files.items())]
    content_sha = sha(encoded(inventory))
    admission = None
    if admission_path is not None:
        raw = read_regular(Path(admission_path), 65536)
        admission = strict(raw)
        if (admission.get('schema') != 'just-peachy.v29-reviewed-native-admission.v1'
            or admission.get('reviewed') is not True or admission.get('native_launch_enabled') is not True
            or admission.get('candidate_content_sha256') != content_sha
            or admission.get('target') != target or not admission.get('reviewer')
            or not admission.get('boot_id') or not admission.get('baseline_sha256')
            or type(admission.get('expires_unix')) not in (int, float)
            or admission['expires_unix'] <= time.time()):
            raise ValueError('Explicit reviewed current exact-content native admission required')
        files['NATIVE_ADMISSION.json'] = raw
    production=None
    if production_path is not None:
        if 'release_authorization.py' not in files:raise ValueError('Production requires the per-session authorization module')
        raw=read_regular(Path(production_path),262144)
        from release_authorization import validate_acceptance
        production=validate_acceptance(strict(raw),dict(target=target,candidate_content_sha256=content_sha,
            installed_manifest_sha256=BASE_MANIFEST,python=old_config['python']))
        backup_manifest,backup_complete=verify_full_backup(production)
        files['PRODUCTION_ACCEPTANCE.json']=raw
        files['PRODUCTION_BACKUP_MANIFEST.json']=backup_manifest
        files['PRODUCTION_BACKUP_COMPLETE.json']=backup_complete
    live = (dict(source_binding['live_config']) if source_binding is not None else
            live_configuration(template['data_files']['live_config.json'],options))
    code_rows = [dict(row, path=row['path'][5:]) for row in rows if row['path'].startswith('code/')]
    binding = dict(schema='just-peachy.v29.binding.v1', target=target,
        native_launch_enabled=admission is not None or production is not None, native_qualified=False,
        authorization_kind='production' if production is not None else 'qualification',
        production_acceptance_sha256=sha(files['PRODUCTION_ACCEPTANCE.json']) if production else None,
        candidate_content_sha256=content_sha, admission_sha256=sha(files['NATIVE_ADMISSION.json']) if admission else None,
        installed_release=old_config['installed_release'], installed_manifest_sha256=BASE_MANIFEST,
        reference_code=target+'/reference-v28/code', reference_files=code_rows,
        profiles=descriptors, python=old_config['python'], live_config=live,
        alsa_config=old_config['alsa_config'], storage_policy={}, raw_capture_available=False,
        raw_adapter_enabled=False, raw_factory_path=target+'/reference-v28/code/field_live_source_factory_v6.py',
        raw_factory_sha256=next(row['sha256'] for row in rows if row['path']=='code/field_live_source_factory_v6.py'),
        raw_qualification_evidence=None)
    if raw_evidence is not None:
        binding.update(raw_capture_available=True,raw_adapter_enabled=True,raw_qualification_evidence=raw_evidence)
    if options is not None:binding['source_batch_ms']=options['source_batch_ms']
    if options is not None and 'native_variants' in options:binding['native_variants']=options['native_variants']
    if source_binding is not None:
        if relocation_raw is not None:
            validate_relocation(strict(relocation_raw),source_binding,binding,snapshot_manifest_sha256,source_binding_raw)
            files['RELOCATION_CERTIFICATE.json']=relocation_raw
        elif encoded(operational_binding(binding))!=encoded(operational_binding(source_binding)):
            raise ValueError('Frozen operational binding cannot change during admission')
    files['BINDING.json'] = encoded(binding)
    for name in runtime_files:
        files['source-backups/'+name+'.backup'] = files[name]
        files['source-backups/'+name+'.restore'] = files[name]
    package = output/'package'
    package.mkdir(exist_ok=False)
    for name, raw in sorted(files.items()):
        write(package.joinpath(*relative(name).parts), raw)
    manifest = dict(schema='just-peachy.v29.package.v1', target=target,
        candidate_content_sha256=content_sha, native_launch_enabled=admission is not None or production is not None,
        source_capsule_sha256=sha(bundle_raw), model_or_gallery_files_copied=False,
        files=[dict(path=name, bytes=len(raw), sha256=sha(raw)) for name, raw in sorted(files.items())])
    manifest_raw = encoded(manifest)
    write(package/'PACKAGE_MANIFEST.json', manifest_raw)
    # Reject concurrent edits rather than labeling a mixed snapshot current.
    for name in runtime_files:
        if read_regular(source/name) != files[name]:
            raise RuntimeError('Source changed during package preparation: ' + name)
    for name, raw in files.items():
        if name.startswith('component_evidence/') and read_regular(source/name,262144)!=raw:
            raise RuntimeError('Pinned component evidence changed during preparation: '+name)
        if name.endswith('.md') and not name.startswith('reference-v28/'):
            if read_regular(source/name) != raw:
                raise RuntimeError('Instructions changed during package preparation: ' + name)
    if read_regular(bundle_path) != bundle_raw:
        raise RuntimeError('Retained capsule changed during preparation')
    if options_raw is not None and read_regular(options_path,4096)!=options_raw:
        raise RuntimeError('Frozen build options changed during preparation')
    for key in descriptors:
        if read_regular(profiles/(key+'.json'), 65536) != files['profiles/'+key+'.json']:
            raise RuntimeError('Descriptor changed during preparation')
    archive = output/(release_id+'-prepared.tar.gz')
    with archive.open('xb') as output_stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output_stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as handle:
                for name, raw in sorted(dict(files, **{'PACKAGE_MANIFEST.json':manifest_raw}).items()):
                    import io
                    row = tarfile.TarInfo(name); row.size=len(raw); row.mode=0o600; row.mtime=0
                    handle.addfile(row, io.BytesIO(raw))
        output_stream.flush(); os.fsync(output_stream.fileno())
    if archive.stat().st_size > 2*1024**2:
        raise ValueError('Compressed candidate exceeds the existing 2 MiB payload gate')
    result = dict(package=str(package), archive=str(archive), manifest_sha256=sha(manifest_raw),
        archive_sha256=sha(archive.read_bytes()), candidate_content_sha256=content_sha,
        files=len(files), capsule_files=len(rows), native_launch_enabled=admission is not None or production is not None,
        target=target, installed=False, desktop_changed=False)
    if snapshot_manifest_sha256 is not None:result['source_snapshot_manifest_sha256']=snapshot_manifest_sha256
    write(output/'BUILD_RESULT.json', encoded(result))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--profiles', required=True)
    ap.add_argument('--output-root', required=True)
    ap.add_argument('--reviewed-native-admission')
    ap.add_argument('--production-acceptance')
    ap.add_argument('--release-id', default='field-runtime-v29')
    ap.add_argument('--source-snapshot-manifest-sha256')
    ap.add_argument('--source-batch-ms',type=int,choices=(0,100))
    ap.add_argument('--native-variant')
    ap.add_argument('--native-variant-sha256')
    ap.add_argument('--raw-qualification-reference',help='Exact native RAW_QUALIFICATION.json path')
    ap.add_argument('--raw-qualification-sha256')
    ap.add_argument('--raw-qualification-mirror',help='Complete closed local mirror for initial candidate build only')
    ap.add_argument('--reviewed-relocation-certificate',help='Explicit source-pinned path-only relocation review; never a native measurement')
    ap.add_argument('--relocation-certificate-sha256')
    args = ap.parse_args()
    output = bootstrap(args.output_root)
    result = build(args.source, args.profiles, output, args.reviewed_native_admission, args.release_id,
        args.production_acceptance,args.source_snapshot_manifest_sha256,args.source_batch_ms,
        args.native_variant,args.native_variant_sha256,args.raw_qualification_reference,
        args.raw_qualification_sha256,args.raw_qualification_mirror,
        args.reviewed_relocation_certificate,args.relocation_certificate_sha256)
    print(encoded(result).decode())


if __name__ == '__main__':
    main()
