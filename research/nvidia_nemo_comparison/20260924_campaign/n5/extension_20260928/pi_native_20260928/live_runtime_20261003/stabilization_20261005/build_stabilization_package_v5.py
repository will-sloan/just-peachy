"""Build25 with closed speech storage/cleanup fixes and actual raw09 proof. README_STABILIZATION_PACKAGE_V5.md."""
import argparse
import ast
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE = PRIVATE/'audit-preparation/full-application-package-e366bb9496184252bc36bd4576fd8c04/package'
BASE_SHA = '9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e'
OLD_TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-21'
NEW_TARGET = OLD_TARGET[:-2]+'25'
REPLACEMENTS = ('launcher.py','classic_frontend.py','installed_engine.py','installed_source.py',
    'application_contract.py','application_controller.py','mature_frontend.py','saved_replay.py',
    'operator_profiles.py','seat_backend.py','saved_spatial.py','README_FULL_APPLICATION.md',
    'README_OPERATOR_PROFILES.md','README_SEAT_BACKENDS.md','README_SAVED_SPATIAL.md',
    'README_STARTUP_REPAIR.md','README_SAVED_REPLAY.md','storage.py','worker.py',
    'README_STORAGE.md','README_METADATA_CLEANUP.md','README_SOURCE_FAILURE_STATUS.md')
ALLOWED_CHANGED = {
    'launcher.py': {'Manager._nested_source'},
    'classic_frontend.py': {'show','choose','ClassicController.snapshot'},
    'installed_engine.py': {'InstalledSession.__init__','InstalledSession.run','InstalledSession._caption','InstalledSession.close','InstalledSession._close_saved_spatial'},
    'installed_source.py': {'_child'},
    'application_contract.py': {'compatibility'},
    'application_controller.py': {'controller_type'},
    'mature_frontend.py': {'frontend_type'},
    'saved_replay.py': {'SavedSessionSource.__init__','SavedSessionSource._run'},
    'storage.py': {'StoragePolicy.estimate_bytes','metadata_limits','_Lease.close',
        'SessionStore.__init__','SessionStore._charge_metadata','SessionStore.delete',
        'SessionSpool._release','SessionSpool.fail'},
    'worker.py': {'main','run_owned_session'},
}


def definitions(raw):
    result = {}
    def visit(nodes, prefix=''):
        for node in nodes:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                result[prefix+node.name] = ast.dump(node,include_attributes=False)
            elif isinstance(node,ast.ClassDef):
                visit(node.body,prefix+node.name+'.')
    visit(ast.parse(raw).body)
    return result


def bootstrap():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('stabilization-package-'+uuid.uuid4().hex)
    root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_text(json.dumps(owner,sort_keys=True))
    return root


RAW_REFERENCE_FILES = ('RAW_QUALIFICATION_PROOF.json','RAW_QUALIFICATION_MIRROR_MANIFEST.json',
    'RAW_QUALIFICATION_MIRROR_COMPLETE.json','RAW_QUALIFICATION_JOB.json')
RAW_SOURCE_SHA = '84f40eb404049164ec7efdaf27668e0a54044b5a874323f779237148e75768bf'
RAW_PACKAGE23_SHA = '16bfa6fcddfac639c83e0c785b4292d98eac478873d5a4c3a2efb3ceb7740492'
RAW_BOOT = '0561d730-3cad-48e0-940a-fe3930c89665'
RAW_VALIDATOR_SHA = '0a706522770d21d8b4846d3121cc430eef81ec73fcced965eca7d804fbf47832'


def raw_proof_documents(core, output, monitor, runtime_files, binding):
    """Re-use exact bounded full-mirror and native-closure validators."""
    monitor = Path(monitor)
    if (monitor.parent != PRIVATE or monitor.resolve(strict=True) != monitor
        or monitor.is_symlink() or re.fullmatch(r'raw-qualification-09-monitor-[0-9]{2}',monitor.name) is None
        or any(parent.is_symlink() for parent in monitor.parents)):
        raise ValueError('Exact canonical private raw09 monitor required')
    result = core.strict(core.read(monitor/'RESULT.json',262144))
    job_raw = core.read(monitor/'closed-output/JOB.json',65536)
    job = core.strict(job_raw)
    # The real monitor adds only an independently observed root identity.
    observed_job = result.get('job')
    complete = core.strict(core.read(monitor/'MIRROR_COMPLETE.json',65536))
    effective_raw = core.read(monitor/'EFFECTIVE_JOB.json',65536)
    original_backup = core.read(monitor/'JOB.json.backup',65536)
    original_restore = core.read(monitor/'JOB.json.restore',65536)
    output_identity = observed_job.get('output_identity') if type(observed_job) is dict else None
    if (type(observed_job) is not dict or set(observed_job) != set(job)|{'output_identity'}
        or {key:value for key,value in observed_job.items() if key!='output_identity'} != job
        or type(output_identity) is not dict or set(output_identity)!={'device','inode'}
        or any(type(output_identity[key]) is not int or output_identity[key]<=0 for key in ('device','inode'))
        or output_identity != complete.get('closure',{}).get('output_identity')
        or complete.get('closure',{}).get('kind') != 'STATUS'
        or complete.get('closure',{}).get('utility_read_only') is not True
        or core.strict(effective_raw) != observed_job
        or original_backup != original_restore or core.strict(original_backup) != job):
        raise ValueError('Exact monitor-only root identity augmentation required')
    expected_output = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/raw-qualification-09'
    if (result.get('status') != 'FULL_CLOSED_OUTPUT_MIRRORED'
        or job.get('output_root') != expected_output or job.get('boot_id') != RAW_BOOT
        or job.get('package_manifest_sha256') != RAW_PACKAGE23_SHA
        or core.sha(runtime_files['installed_source.py']) != RAW_SOURCE_SHA):
        raise ValueError('Actual closed raw09/current-boot/build23/source pins required')
    source = HERE.parent/'prepare_package.py'
    raw = core.read(source)
    if core.sha(raw) != RAW_VALIDATOR_SHA:
        raise ValueError('Exact original raw mirror/reference validation required')
    tree = ast.parse(raw)
    names = {'encoded','strict','sha','relative','read_regular',
             'raw_reference_input','verify_raw_reference'}
    nodes = [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if len(nodes) != len(names):
        raise ValueError('Exact seven original pure raw validators required')
    space = dict(hashlib=hashlib,json=json,os=os,re=re,Path=Path,PurePosixPath=PurePosixPath,
        TARGET_PARENT='/home/peachyprototype/JustPeachy/research/nemotron-20260928',
        RAW_REFERENCE_FILES=RAW_REFERENCE_FILES)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<unchanged-raw-proof-validators>','exec'),space)
    proof_raw = core.read(monitor/'closed-output/qualification/RAW_QUALIFICATION.json',1024**2)
    reference,documents = space['raw_reference_input'](
        expected_output+'/qualification/RAW_QUALIFICATION.json',core.sha(proof_raw),monitor)
    evidence = space['verify_raw_reference'](reference,documents,runtime_files,
        binding['source_batch_ms'],binding['raw_factory_sha256'])
    proof = core.strict(proof_raw)
    # Execute only the original admission function, with real private bytes.
    # No runtime imports, source constructor, models, microphone or native action.
    admission_tree = ast.parse(runtime_files['raw_capture.py'])
    nodes = [node for node in admission_tree.body if isinstance(node,ast.FunctionDef) and node.name=='admission']
    if len(nodes) != 1:
        raise ValueError('Exactly one preserved raw admission function required')
    context = output.root/'raw-admission-readback'
    for name in ('installed_source.py','raw_capture.py','source_batch.py'):
        output.write(context/name,runtime_files[name])
    output.write(context/'RAW_QUALIFICATION_PROOF.json',proof_raw)
    admission_space = dict(Path=Path,hashlib=hashlib,json=json,__file__=str(context/'raw_capture.py'))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<unchanged-raw-admission>','exec'),admission_space)
    host_evidence = dict(evidence,evidence=str(context/'RAW_QUALIFICATION_PROOF.json'))
    if admission_space['admission'](dict(raw_adapter_enabled=True,
            raw_qualification_evidence=host_evidence)) != host_evidence:
        raise ValueError('Actual raw admission output differs')
    output.write(output.root/'RAW_PROOF_BINDING_REVIEW.json',core.encoded(dict(
        status='PASSED_ACTUAL_RAW_SOURCE_PROOF_BINDING',monitor=str(monitor),
        job_sha256=core.sha(job_raw),proof_sha256=core.sha(proof_raw),
        installed_source_sha256=RAW_SOURCE_SHA,source_package_sha256=RAW_PACKAGE23_SHA,
        boot_id=RAW_BOOT,raw_samples=proof['raw_samples'],processed_samples=proof['processed_samples'],
        collector_root_identity=output_identity,monitor_effective_job_sha256=core.sha(effective_raw),
        original_job_independent_restore_sha256=core.sha(original_backup),
        raw_channels=proof['raw_channels'],raw_bytes=proof['raw_bytes'],processed_bytes=proof['processed_bytes'],
        original_raw_validators_source_sha256=RAW_VALIDATOR_SHA,
        admission_function_ast_exact=True,admission_host_path_translation_only=True,
        full_closed_mirror_verified=True,native_action=False)))
    return documents,dict(evidence,evidence=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json'),reference,proof


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw-monitor',type=Path,required=True,
        help='Complete passed raw-qualification-09 monitor; raw08 is never accepted')
    args=ap.parse_args()
    root=bootstrap()  # BEFORE any project/package reads.
    sys.dont_write_bytecode=True
    legacy_path=HERE.parent/'ui_restore_20261004/build_classic_package.py'
    if hashlib.sha256(legacy_path.read_bytes()).hexdigest()!='bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5':
        raise ValueError('Exact reviewed bounded packaging implementation required')
    spec=importlib.util.spec_from_file_location('full_packaging_core',legacy_path)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    # Derive only the archive basename; all packaging/check/restore logic stays exact.
    legacy_tree=ast.parse(legacy_path.read_bytes())
    legacy_main=next(node for node in legacy_tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    changed=0
    for node in ast.walk(legacy_main):
        if isinstance(node,ast.Constant) and node.value=='field-runtime-v29-build-17-prepared.tar.gz':
            node.value='field-runtime-v29-build-25-prepared.tar.gz';changed+=1
    if changed!=1:raise ValueError('Exact original archive basename boundary')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[legacy_main],type_ignores=[])),
        '<unchanged-package-main-with-build25-basename>','exec'),core.__dict__)
    core.BASE,core.BASE_SHA=BASE,BASE_SHA
    core.OLD_TARGET,core.NEW_TARGET=OLD_TARGET,NEW_TARGET
    core.ALLOWED_REPLACEMENTS=set(REPLACEMENTS)
    output=core.Output(root)
    output.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,
        maximum_seconds=600,issued_unix=time.time(),target=NEW_TARGET,native_action=False)))
    inputs={name: HERE/('README.md' if name=='README_FULL_APPLICATION.md' else name) for name in REPLACEMENTS}
    for name,path in dict(inputs,**{'build_stabilization_package_v5.py':Path(__file__),
            'README_STABILIZATION_PACKAGE_V5.md':HERE/'README_STABILIZATION_PACKAGE_V5.md'}).items():
        raw=core.read(path)
        for suffix in ('backup','restore'):
            output.write(root/'prepared-source'/suffix/name,raw)
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),
        inputs={name:core.sha(core.read(path)) for name,path in inputs.items()},independent_restores=True)))
    core.bootstrap=lambda parent:output
    def review(before,replacements):
        result={}
        for name, allowed in ALLOWED_CHANGED.items():
            old=definitions(before[name]);new=definitions(replacements[name])
            if not set(old)<=set(new):
                raise ValueError('Original function deletion refused: '+name)
            if name in ('storage.py','worker.py'):
                expected_new={'SessionStore.write_terminal_event'} if name=='storage.py' else set()
                if set(new)-set(old)!=expected_new:
                    raise ValueError('Exact approved new storage/worker definitions required')
            changed={key for key in old if old[key]!=new.get(key)}
            if changed-allowed:
                raise ValueError('Unapproved original function body change: '+name+' '+str(changed-allowed))
            result[name]=dict(changed=sorted(changed),new=sorted(set(new)-set(old)),
                preserved=len(set(old)-changed))
        # profiles/authorization/native ownership and raw converter are
        # inherited byte-for-byte from build21, including all resource guards.
        return result
    core.validate_repair_scope=review
    original_derive=core.derive
    def derive(parent,files,replacements,reviewer):
        manifest,files,provenance=original_derive(parent,files,replacements,reviewer)
        acceptance=core.strict(files['PRODUCTION_ACCEPTANCE.json'])
        binding=core.strict(files['BINDING.json'])
        acceptance['limits'].update(manual_stop_storage_policy=True,personal_enrollment=True)
        acceptance['limitations']=[
            'Build25 includes the focused speech-storage accounting and unconditional cleanup fixes over the six-choice portrait runtime; changed whole-application native qualification remains pending.',
            'Normal live duration is storage-capacity-driven with manual Stop; load, drain, backlog, ownership and disk/RAM guards remain enforced.',
            'Pyannote/ReDimNet retains C088. Other assigned-seat hybrid routes require their own exact N2 voice calibration and remain Unknown when that gate is unavailable.',
            'Rich saved-session spatial replay uses only recorded beam/BMI clocks; plain WAV spatial replay is unavailable.',
            'Startup diagnostics reserve 64KiB plus one 64KiB directory, independently of recording metadata.',
            'Representative native checks do not establish all Cartesian combinations or an hour-long whole-application pass.',
            'Old optional-refiner measurements are not reused to admit changed runtime content.']
        old_proof_sha=core.sha(files['RAW_QUALIFICATION_PROOF.json'])
        documents,raw_evidence,reference,proof=raw_proof_documents(core,output,args.raw_monitor,files,binding)
        for name,raw in documents.items():
            if name not in files:raise ValueError('Original raw evidence member missing: '+name)
            files[name]=raw
        binding['raw_qualification_evidence']=raw_evidence
        provenance['raw_source_proof_binding']=dict(parent_proof_sha256=old_proof_sha,
            proof_sha256=reference['sha256'],raw_job_sha256=reference['job_sha256'],
            raw_qualified=True,whole_application_native_qualified=False,
            raw_samples=proof['raw_samples'],processed_samples=proof['processed_samples'],
            raw_channels=proof['raw_channels'],source_sha256=RAW_SOURCE_SHA,
            source_native_package_sha256=RAW_PACKAGE23_SHA,target_evidence=raw_evidence['evidence'])
        provenance.update(schema='just-peachy.runtime-stabilization.v1',
            ordinary_application_modes=11,visible_backend_combinations=6,mode_backend_independent=True,
            personal_gallery_overlay=True,immutable_old_galleries_changed=False,
            manual_stop_storage_policy=True,personal_enrollment=True)
        files['REPAIR_PROVENANCE.json']=files['REPAIR_PROVENANCE.restore.json']=core.encoded(provenance)
        content=core.sha(core.encoded(core.rows({name:raw for name,raw in files.items()
            if name not in core.CONTENT_EXCLUDED and not name.startswith('source-backups/')})))
        acceptance['candidate_content_sha256']=binding['candidate_content_sha256']=content
        acceptance_raw=core.encoded(acceptance)
        binding['production_acceptance_sha256']=core.sha(acceptance_raw)
        files['PRODUCTION_ACCEPTANCE.json']=acceptance_raw
        files['BINDING.json']=core.encoded(binding)
        manifest.update(candidate_content_sha256=content,files=core.rows(files))
        if len(files)+1>512 or sum(map(len,files.values()))>core.MAX_PACKAGE:
            raise ValueError('Original package count/extent bounds exceeded')
        return manifest,files,provenance
    core.derive=derive
    sys.argv=[str(Path(__file__)), '--base',str(BASE),'--base-manifest-sha256',BASE_SHA,
        '--reviewer','Codex reviewed focused launch/source/chooser/seat/saved-clock stabilization over immutable build21']
    for name,path in inputs.items():
        sys.argv.extend(['--replacement',name+'='+str(path)])
    core.main()


if __name__=='__main__':
    main()

