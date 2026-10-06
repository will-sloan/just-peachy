"""Build27 shared XVF Start continuation and manual listening control. README_STABILIZATION_PACKAGE_V7.md."""
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
BASE = PRIVATE/'audit-preparation/stabilization-package-b3df11de85bf41d7a6e8afd5092e3268/package'
BASE_SHA = 'f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
OLD_TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-26'
NEW_TARGET = OLD_TARGET[:-2]+'27'
REPLACEMENTS = ('launcher.py','classic_frontend.py','mature_frontend.py','application_controller.py','xvf_readiness_helper.py','README_MANUAL_START.md','README_XVF_START_CONTINUATION.md')
ALLOWED_CHANGED = {'launcher.py': {'Manager._nested_source'}}


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
    ap.add_argument('--verify-source-only',action='store_true',
        help='Back up and compile this builder only; no package is assembled')
    args=ap.parse_args()
    root=bootstrap()  # CPU14 and exact FILETIME owner BEFORE project/package reads.
    sys.dont_write_bytecode=True
    if args.verify_source_only:
        import shutil
        started=time.monotonic();written=(root/'REGISTERED_OWNER.json').stat().st_size
        if shutil.disk_usage('C:/').free<50*1024**3 or shutil.disk_usage('G:/').free<75*1024**3+16*1024**2:
            raise OSError('Original source-freeze disk floors')
        with (root/'HOST_SCOPE.json').open('x',encoding='utf-8') as stream:
            json.dump(dict(maximum_bytes=16*1024**2,maximum_seconds=600,
                issued_unix=time.time(),native_action=False,actual_package_built=False),stream,sort_keys=True)
            stream.flush();os.fsync(stream.fileno())
        inputs={'BUILDER.py':Path(__file__),
            'README.md':HERE/'README_STABILIZATION_PACKAGE_V7.md',
            'PARENT_BUILDER.py':HERE/'build_stabilization_package_v6.py'}
        hashes={}
        for name,path in inputs.items():
            raw=path.read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
            for suffix in ('','.backup','.restore'):
                if written+len(raw)>16*1024**2 or time.monotonic()-started>600:
                    raise OSError('Original finite source-freeze scope')
                target=root/(name+suffix)
                with target.open('xb') as stream:
                    if stream.write(raw)!=len(raw):raise OSError('Short source freeze write')
                    stream.flush();os.fsync(stream.fileno())
                if target.read_bytes()!=raw:raise OSError('Independent source freeze differs')
                written+=len(raw)
        before=definitions((root/'PARENT_BUILDER.py').read_bytes())
        after=definitions((root/'BUILDER.py').read_bytes())
        if set(before)!=set(after) or any(before[name]!=after[name] for name in before if name!='main'):
            raise ValueError('All original non-main builder function AST must remain exact')
        compile((root/'BUILDER.py').read_bytes(),'build_stabilization_package_v7.py','exec')
        if any(path.read_bytes()!=(root/name).read_bytes() for name,path in inputs.items()):
            raise ValueError('Source changed during builder freeze')
        receipt=dict(output=str(root),source_hashes=hashes,independent_restores=True,
            original_non_main_function_asts_exact=True,actual_package_built=False,
            native_action=False,closed_unix=time.time())
        for name in ('SOURCE_REVIEW.json','SOURCE_CLOSED.json'):
            with (root/name).open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(receipt,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        print(json.dumps(receipt));return
    legacy_path=HERE.parent/'ui_restore_20261004/build_classic_package.py'
    if hashlib.sha256(legacy_path.read_bytes()).hexdigest()!='bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5':
        raise ValueError('Exact reviewed bounded packaging implementation required')
    spec=importlib.util.spec_from_file_location('full_packaging_core',legacy_path)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    legacy_tree=ast.parse(legacy_path.read_bytes())
    legacy_main=next(node for node in legacy_tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    changed=0
    for node in ast.walk(legacy_main):
        if isinstance(node,ast.Constant) and node.value=='field-runtime-v29-build-17-prepared.tar.gz':
            node.value='field-runtime-v29-build-27-prepared.tar.gz';changed+=1
    if changed!=1:raise ValueError('Exact original archive basename boundary')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[legacy_main],type_ignores=[])),
        '<unchanged-package-main-with-build27-basename>','exec'),core.__dict__)
    core.BASE,core.BASE_SHA=BASE,BASE_SHA
    core.OLD_TARGET,core.NEW_TARGET=OLD_TARGET,NEW_TARGET
    core.ALLOWED_REPLACEMENTS=set(REPLACEMENTS)
    output=core.Output(root)
    output.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,
        maximum_seconds=600,issued_unix=time.time(),target=NEW_TARGET,native_action=False)))
    inputs={name:HERE/name for name in REPLACEMENTS}
    inputs['xvf_readiness_helper.py']=HERE.parent/'ui_restore_20261004/xvf_readiness_helper.py'
    for name,path in dict(inputs,**{'build_stabilization_package_v7.py':Path(__file__),
            'README_STABILIZATION_PACKAGE_V7.md':HERE/'README_STABILIZATION_PACKAGE_V7.md'}).items():
        raw=core.read(path)
        for suffix in ('backup','restore'):
            output.write(root/'prepared-source'/suffix/name,raw)
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),
        inputs={name:core.sha(core.read(path)) for name,path in inputs.items()},independent_restores=True)))
    core.bootstrap=lambda parent:output
    changed_functions={
        'launcher.py':{'Manager.__init__','Manager.start','Manager.stop','Manager.poll',
            'Manager.export_recordings','Manager.close'},
        'classic_frontend.py':{'ClassicController.settings_update','ClassicController.session_action',
            'ClassicController.snapshot','frontend_type.PortraitUI.toggle_listening'},
        'mature_frontend.py':{'frontend_type.MatureUI.show_settings','frontend_type.MatureUI._page',
            'frontend_type.MatureUI.poll'},
        'application_controller.py':{'controller_type.ApplicationController._ensure_idle',
            'controller_type.ApplicationController.switch','controller_type.ApplicationController.display_roster',
            'controller_type.ApplicationController.settings_update',
            'controller_type.ApplicationController.text_assistance_action',
            'controller_type.ApplicationController._gallery'},
        'xvf_readiness_helper.py':{'unit_checks'},
    }
    added_functions={
        'launcher.py':{'Manager.readiness_pending','Manager._readiness_fault',
            'Manager._previous_readiness_fault','Manager._begin_readiness','Manager._poll_readiness'},
        'classic_frontend.py':{'ClassicController._require_readiness_idle'},
    }
    def review(before,replacements):
        if set(replacements)!=set(REPLACEMENTS):
            raise ValueError('Only complete reviewed Start/readiness sources and READMEs required')
        result={}
        for name,allowed in changed_functions.items():
            old=ast.parse(before[name]);new=ast.parse(replacements[name])
            old_nodes={}
            def inventory(nodes,prefix=''):
                for node in nodes:
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                        key=prefix+node.name;old_nodes[key]=node
                        inventory(node.body,key+'.')
            inventory(old.body)
            found_changed=set();found_added=set()
            def restore(nodes,prefix=''):
                for node in list(nodes):
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                        key=prefix+node.name
                        if key in added_functions.get(name,set()):
                            if key in old_nodes:raise ValueError('Expected new definition already exists: '+key)
                            nodes.remove(node);found_added.add(key)
                        elif key in allowed:
                            if key not in old_nodes:raise ValueError('Original reviewed definition missing: '+key)
                            if ast.dump(node,include_attributes=False)!=ast.dump(old_nodes[key],include_attributes=False):
                                found_changed.add(key)
                            nodes[nodes.index(node)]=old_nodes[key]
                        else:
                            restore(node.body,key+'.')
            restore(new.body)
            # README links may change only the module docstring. The native
            # helper additionally imports math for explicit finite/infinite unit checks.
            for tree in (old,new):
                if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) and isinstance(tree.body[0].value.value,str):
                    tree.body.pop(0)
            if name=='xvf_readiness_helper.py':
                imports=[node for node in new.body if isinstance(node,ast.Import) and
                    len(node.names)==1 and node.names[0].name=='math' and node.names[0].asname is None]
                if len(imports)!=1:raise ValueError('Exactly one reviewed math import required')
                new.body.remove(imports[0])
            if found_changed!=allowed or found_added!=added_functions.get(name,set()):
                raise ValueError('Exact reviewed changed/added function set differs: '+name)
            if ast.dump(old,include_attributes=False)!=ast.dump(new,include_attributes=False):
                raise ValueError('Runtime changed outside exact reviewed functions/docstrings/import: '+name)
            result[name]=dict(changed=sorted(found_changed),added=sorted(found_added),
                full_module_ast_exact_after_reviewed_functions_restored=True)
        return result
    core.validate_repair_scope=review
    original_derive=core.derive
    def derive(parent,files,replacements,reviewer):
        prior=dict(files)
        manifest,files,provenance=original_derive(parent,files,replacements,reviewer)
        acceptance=core.strict(files['PRODUCTION_ACCEPTANCE.json'])
        binding=core.strict(files['BINDING.json'])
        acceptance['limitations']=[
            'Build27 changes shared manual Start/readiness continuation over immutable build26; changed native qualification remains pending.',
            'Start is the explicit listening action. Capture never starts from launching or changing a mode. Enrollment and data transfer consent remain separate.',
            'A qualifying prior AEC failure may invoke one fenced readiness helper. This is not a periodic reset or a silent source retry; helper closure precedes a fresh source.',
            'Normal live duration is storage-capacity-driven with manual Stop; load, drain, backlog, ownership and disk/RAM guards remain enforced.',
            'Pyannote/ReDimNet retains C088. Other assigned-seat hybrid routes require their own exact N2 voice calibration and remain Unknown when that gate is unavailable.',
            'Rich saved-session spatial replay uses only recorded beam/BMI clocks; plain WAV spatial replay is unavailable.',
            'Representative native checks do not establish all Cartesian combinations or an hour-long whole-application pass.',
            'Old optional-refiner measurements are not reused to admit changed runtime content.']
        if core.sha(files['installed_source.py'])!=RAW_SOURCE_SHA:
            raise ValueError('Exact previously qualified physical raw source must remain unchanged')
        for name in RAW_REFERENCE_FILES:
            if files[name]!=prior[name]:raise ValueError('Immutable raw qualification document changed: '+name)
        # Relocate the actual retained proof path only. No raw requalification,
        # monitor rerun, byte rewrite or promotion of old native measurements.
        raw_evidence=dict(binding['raw_qualification_evidence'])
        if raw_evidence.get('evidence')!=OLD_TARGET+'/RAW_QUALIFICATION_PROOF.json':
            raise ValueError('Exact parent raw-proof evidence location required')
        raw_evidence['evidence']=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json'
        binding['raw_qualification_evidence']=raw_evidence
        provenance.update(schema='just-peachy.runtime-stabilization.v1',
            ordinary_application_modes=11,visible_backend_combinations=6,mode_backend_independent=True,
            personal_gallery_overlay=True,immutable_old_galleries_changed=False,
            manual_stop_storage_policy=True,personal_enrollment=True,
            raw_source_and_qualification_bytes_unchanged=True,
            raw_qualification_repeated=False,raw_evidence_path_translation_only=True,
            shared_start_readiness_continuation=True,listening_toggle_removed=True)
        files['REPAIR_PROVENANCE.json']=files['REPAIR_PROVENANCE.restore.json']=core.encoded(provenance)
        content=core.sha(core.encoded(core.rows({name:raw for name,raw in files.items()
            if name not in core.CONTENT_EXCLUDED and not name.startswith('source-backups/')})))
        acceptance['candidate_content_sha256']=binding['candidate_content_sha256']=content
        acceptance_raw=core.encoded(acceptance)
        binding['production_acceptance_sha256']=core.sha(acceptance_raw)
        files['PRODUCTION_ACCEPTANCE.json']=acceptance_raw
        files['BINDING.json']=core.encoded(binding)
        manifest.update(candidate_content_sha256=content,files=core.rows(files))
        allowed=set(REPLACEMENTS)|{'BINDING.json','PRODUCTION_ACCEPTANCE.json',
            'REPAIR_PROVENANCE.json','REPAIR_PROVENANCE.restore.json'}
        for name in REPLACEMENTS:
            if name.endswith('.py'):
                allowed.update({'source-backups/'+name+'.backup','source-backups/'+name+'.restore'})
        additions=set(files)-set(prior);removals=set(prior)-set(files)
        expected_additions={'README_MANUAL_START.md','README_XVF_START_CONTINUATION.md'}
        if removals or additions!=expected_additions:
            raise ValueError('Only two explicit new runtime guide members permitted')
        differences={name for name in set(files)&set(prior) if files[name]!=prior[name]}
        if differences-allowed or not {'launcher.py','BINDING.json','PRODUCTION_ACCEPTANCE.json'}<=differences:
            raise ValueError('Unexpected build27 member change: '+str(differences-allowed))
        output.write(output.root/'BUILD26_MEMBER_PRESERVATION.json',core.encoded(dict(
            parent_manifest_sha256=BASE_SHA,allowed_changed_members=sorted(allowed),
            actual_changed_members=sorted(differences),added_members=sorted(additions),removed_members=[],
            unchanged_parent_members=len(prior)-len(differences),
            all_other_runtime_models_profiles_raw_proof_bytes_identical=True,
            package_manifest_is_separate_derived_control=True)))
        if len(files)+1>512 or sum(map(len,files.values()))>core.MAX_PACKAGE:
            raise ValueError('Original package count/extent bounds exceeded')
        return manifest,files,provenance
    core.derive=derive
    sys.argv=[str(Path(__file__)), '--base',str(BASE),'--base-manifest-sha256',BASE_SHA,
        '--reviewer','Codex reviewed shared Start continuation and manual listening action over immutable build26']
    for name,path in inputs.items():
        sys.argv.extend(['--replacement',name+'='+str(path)])
    core.main()


if __name__=='__main__':
    main()


