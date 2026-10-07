"""Review/build33 from sealed32; README_EVENT_PACKAGE33.md. Host only."""
import argparse
import ast
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
MODEL=HERE.parent/'model_address_space_20261006'
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE=PRIVATE/'audit-preparation/gallery-package32-d1140c29f0d843c881bd719309bb5d6d/package'
BASE_SHA='55f449d563b3011a0793cef174921a215cd9aeb0dbbaa597b228ae4ba889fbbf'
REFERENCE_SHA='4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
CORE=HERE.parent.parent/'ui_restore_20261004/build_classic_package.py'
CORE_SHA='bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5'
INVENTORY=HERE.parent/'capacity_gallery_20261006/build_gallery_package32.py'
INVENTORY_SHA='7f30a1a15631698630888fbf93fb0711197f1e3d820695b54a76528f358021d2'
OLD_TARGET='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-32'
NEW_TARGET=OLD_TARGET[:-2]+'33'
CODEC_NAMES=('event_compaction.py','runtime_support.py')
MODEL_NAMES=('worker.py','native_scope.py','launch_raw_qualification_action.py')
REPLACEMENTS=CODEC_NAMES+MODEL_NAMES+('README_EVENT_WRITER_STREAMING.md','README_MODEL_ADDRESS_SPACE.md')
CODEC_CHECKS=('test_event_writer_streaming.py','run_host_event_writer_checks.py')
MODEL_CHECKS=('test_model_address_space.py','run_host_model_address_space_checks.py')
ENTRIES=('native_scope.py','launcher.py','worker.py','gallery_worker.py','launch_raw_qualification_action.py')
CODEC_PARENT_PINS={'event_compaction.py':'4ad7255459b7aadbbee1c1bd498a6f1402e3ba60e83db0386a6a9bf10f28e206',
                   'runtime_support.py':'b31cc219a1dded71bc2393190c79a9e93a8bfcaff206c5c69d3c7ee056a24999'}
RAW_SOURCE_SHA='84f40eb404049164ec7efdaf27668e0a54044b5a874323f779237148e75768bf'
RAW_PROOFS=('RAW_QUALIFICATION_PROOF.json','RAW_QUALIFICATION_MIRROR_MANIFEST.json',
            'RAW_QUALIFICATION_MIRROR_COMPLETE.json','RAW_QUALIFICATION_JOB.json')
HOUR=PRIVATE/'full-app-hour-05-monitor-01'
HOUR_WORKER=HOUR/'closed-output/data/launches/b0ba37cf8100441e971cd60f190455ba/worker'
HOUR_EVENTS=HOUR/'closed-output/data/recordings/sessions/59a0f5135650417381600d778713c40a/work/sessions/edge_prototype_20261006T195556Z_1404e9aa'
HOUR_INPUTS={
    'HOUR05_WORKER_RESULT.json':(HOUR_WORKER/'RESULT.json','ec562df1d8a89d9368d7d3ac00829366cc19c1ac0510f9e26a874c13a33ee9ae'),
    'HOUR05_WORKER_ENVELOPE.json':(HOUR_WORKER/'ENVELOPE.json','94da15f03929a3444954e6bae5b06d3f5a233a44002b478b30eeca1e8d1f809a'),
    'HOUR05_COMPACTION.json':(HOUR_EVENTS/'events.jsonl.compaction.json','c4875b06b723c33209cf3e98c22679a2b8ca4ae34af895ed45fc07759a216a7e'),
    'HOUR05_MIRROR_COMPLETE.json':(HOUR/'MIRROR_COMPLETE.json','cc9215848c603abddce33dfff9863d9dffb22f69b3539849e2883a86bca42ab4'),
    'HOUR05_UNIT_OWNERSHIP.json':(HOUR/'closed-output/UNIT_OWNERSHIP.json','26d298fca53a1ed0e7221f215c2e0d64264e423a62a5191c77244fa3f8fe4504')}
MODEL_POLICY=dict(previous_worker_bytes=768*1024**2,candidate_worker_bytes=1024**3,
    frontend_soft_bytes=256*1024**2,candidate_inside_model_hard_bytes=1024**3,
    outside_metadata_bytes=128*1024**2,other_qualification_parent_bytes=768*1024**2,
    candidate_recording_parent_bytes=1024**3,
    recording_parent_scope='full_app_hour or modern classic_driver.py live/saved redimnet/titanet',
    physical_ram_floor_and_disk_reserves_unchanged=True,source_constants_are_authority=True,
    binding_and_acceptance_limits_schema_unchanged=True,native_qualification_pending=True)


def bootstrap():
    if os.name!='nt':raise RuntimeError('Windows host package preparation only')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    handle=kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    parent=PRIVATE/'audit-preparation'
    if parent.resolve(strict=True)!=parent:raise ValueError('Exact existing private host parent required')
    root=parent/('event-package33-'+uuid.uuid4().hex);root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
        creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    raw=json.dumps(owner,sort_keys=True).encode()
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short early registered owner write')
        stream.flush();os.fsync(stream.fileno())
    if (root/'REGISTERED_OWNER.json').read_bytes()!=raw:raise OSError('Early owner readback differs')
    return root,owner


def load_pinned(name,path,sha):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Exact reviewed helper required: '+name)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,raw


def admit_host(core,raw_inputs,pins,prefix,root,origin,runtime,checks,schema,count,reference,before):
    result,owner,closed,sources,unchanged=(core.strict(raw_inputs[prefix+'_'+name+'.json'])
        for name in ('RESULT','REGISTERED_OWNER','HOST_CLOSED','SOURCE_CLOSED','SOURCE_UNCHANGED'))
    if (result.get('schema')!=schema or result.get('status')!='PASS' or result.get('tests_run')!=count
            or any(result.get(key)!=0 for key in ('failures','errors','skipped'))
            or any(result.get(key) is not True for key in ('fixture_closed','source_unchanged'))
            or any(result.get(key) is not False for key in ('native_action','models'))
            or result.get('failure') is not None or result.get('owner')!=owner or closed.get('owner')!=owner
            or owner.get('schema')!='just-peachy.host-registered-owner.v1' or owner.get('cpu')!=14
            or owner.get('affinity_mask')!=16384 or type(owner.get('pid')) is not int or owner['pid']<=0
            or type(owner.get('creation_filetime')) is not int or owner['creation_filetime']<=0
            or closed.get('natural_exit_code')!=0 or closed.get('os_process_absent') is not True
            or closed.get('independent_os_check') is not True
            or sources.get('package_manifest_sha256')!=reference):
        raise ValueError('Actual successful registered host proof and exact closure required: '+prefix)
    if prefix=='CODEC':
        if (sources.get('backup_and_independent_restore') is not True or sources.get('before_check') is not True
                or unchanged.get('pins')!=sources.get('pins')
                or any(unchanged.get(key) is not True for key in ('source_unchanged','fixture_closed','scope_closed'))
                or unchanged.get('native_action') is not False):
            raise ValueError('Actual codec source closure fields differ')
        proof_pins=sources['pins']
    elif prefix=='AS':
        proof_pins=sources.get('source_pins',[])
        expected_paths={str(BASE/name) for name in before}|{str(BASE/'PACKAGE_MANIFEST.json')}
        expected_paths|={str(MODEL/name) for name in MODEL_NAMES+MODEL_CHECKS+('README_MODEL_ADDRESS_SPACE.md',)}
        expected_paths|={str(MODEL/'preserved32'/(name+'.'+suffix)) for name in MODEL_NAMES for suffix in ('backup','restore')}
        if (sources.get('owner')!=owner or unchanged.get('owner')!=owner
                or closed.get('schema')!='just-peachy.model-address-space-host-closure.v1'
                or closed.get('source_count')!=445 or closed.get('source_backup_restore_readback_exact') is not True
                or closed.get('source_unchanged') is not True or closed.get('fixture_closed') is not True
                or closed.get('models') is not False or closed.get('native_action') is not False
                or sources.get('before_tests') is not True or sources.get('independent_backups_and_restores') is not True
                or sources.get('native_action') is not False or sources.get('models') is not False
                or unchanged.get('source_pins')!=proof_pins or unchanged.get('after_tests') is not True
                or unchanged.get('source_unchanged') is not True or unchanged.get('independent_backup_restore_readback_exact') is not True
                or len(proof_pins)!=445 or sources.get('source_count')!=445 or unchanged.get('source_count')!=445
                or {pin['path'] for pin in proof_pins}!=expected_paths
                or any(pin.get('independent_restore_equal') is not True for pin in proof_pins)):
            raise ValueError('Actual full-parent AS source/backup/reverse-proof closure differs')
        for pin in proof_pins:
            current=core.read(Path(pin['path']))
            if (Path(pin['path'])!=MODEL/'README_MODEL_ADDRESS_SPACE.md'
                    and (len(current)!=pin['bytes'] or core.sha(current)!=pin['sha256'])):
                raise ValueError('AS proof current source bytes differ')
            for key in ('backup','restore'):
                token=Path(pin[key])
                if token.drive or token.anchor or '..' in token.parts:raise ValueError('Canonical relative AS preservation token required')
                saved_path=root/token
                if saved_path.resolve(strict=True)!=saved_path or not saved_path.resolve(strict=True).is_relative_to(root):
                    raise ValueError('AS preservation path escapes its ordinary registered host root')
                saved=core.read(saved_path)
                if len(saved)!=pin['bytes'] or core.sha(saved)!=pin['sha256']:
                    raise ValueError('AS full-source backup/independent restore differs')
    else:raise ValueError('Explicit host proof family required')
    tested={}
    for pin in proof_pins:
        if Path(pin['path']).parent==origin:
            name=Path(pin['path']).name
            if name in tested:raise ValueError('Duplicate tested source pin')
            tested[name]=pin
    for name in runtime+checks:
        if (name not in tested or tested[name]['sha256']!=pins[name]['sha256']
                or tested[name]['bytes']!=pins[name]['bytes']):
            raise ValueError('Candidate code differs from actual tested bytes: '+name)
    return dict(root=str(root),schema=schema,owner=owner,tests=count,exact_owner_closed=True,
        runtime_and_check_bytes_match=True,
        receipts={name:pins[prefix+'_'+name+'.json']['sha256'] for name in
            ('RESULT','REGISTERED_OWNER','HOST_CLOSED','SOURCE_CLOSED','SOURCE_UNCHANGED')},
        measured_prepare=result.get('traced_prepare_allocation'))


def source_review(core,tools,parent,before,replacements,pins,admissions,hour):
    if set(replacements)!=set(REPLACEMENTS):raise ValueError('Complete explicit seven-file replacement set required')
    for name,sha in CODEC_PARENT_PINS.items():
        if core.sha(before[name])!=sha:raise ValueError('Exact tested codec origin differs in parent32')
    inventory={}
    for name in CODEC_NAMES+MODEL_NAMES:
        compile(ast.parse(replacements[name],filename=name),name,'exec')
        inventory[name]=tools.ast_diff(before[name],replacements[name])
    gallery=core.strict(before['REPAIR_PROVENANCE.json'])
    if (gallery.get('focused_host_tests')!=20 or gallery.get('focused_host_exact_owner_closed') is not True
            or gallery.get('focused_host_result_sha256')!='640d8da80ed93f85c2deaddd4da8dfe44a30241f415ad2cc16bc1c788162e182'):
        raise ValueError('Actual preserved parent32 gallery HOST20 provenance required')
    gallery_reference=dict(parent_manifest_sha256=BASE_SHA,repair_provenance_sha256=core.sha(before['REPAIR_PROVENANCE.json']),
        source_review_sha256=gallery['source_review_sha256'],host_tests=20,
        host_test_receipt=gallery['focused_host_test_receipt'],host_result_sha256=gallery['focused_host_result_sha256'],
        exact_owner_closed=True)
    return dict(schema='just-peachy.event-writer-model-as-package-source-review.v1',
        parent_target=OLD_TARGET,target=NEW_TARGET,parent_manifest_sha256=BASE_SHA,
        parent_candidate_content_sha256=parent['candidate_content_sha256'],
        packaging_core_sha256=CORE_SHA,inventory_helper_sha256=INVENTORY_SHA,
        source_pins=pins,replacement_names=list(REPLACEMENTS),
        replacement_pins={name:dict(bytes=len(raw),sha256=core.sha(raw)) for name,raw in replacements.items()},
        ast_inventory=inventory,import_closure=tools.import_closure(dict(before,**replacements)),
        focused_host_tests=admissions,parent32_gallery_host20_reference=gallery_reference,
        failed_hour05_evidence=hour,model_address_space_policy=MODEL_POLICY,
        packaging_core_adaptations=dict(exact_paired_frontend_condition_replaced=True,
            exact_single_archive_basename_changed_to_build33=True,immutable_core_edited=False,
            inventory_archive_and_whole_member_restore_validators_reused=True),
        constraints=dict(models_changed=False,gallery_data_changed=False,backend_descriptors_changed=False,
            raw_source_or_proof_bytes_changed=False,canonical_source_windows_or_identity_gates_changed=False,
            session_drain_backlog_thresholds_changed=False,physical_free_ram_or_disk_reserves_changed=False,
            finite_model_address_space_changed_768_mib_to_1_gib=True,
            logical_event_bytes_digests_patch_semantics_and_fifo_unchanged=True,
            audio_storage_and_fsync_durability_unchanged=True,binding_and_acceptance_limits_structure_unchanged=True,
            parent32_gallery_and_parent31_caption_repairs_retained=True,
            old_failed_hour05_relabelled=False,exclusive_allocation_or_stop_order_proven=False,
            new_native_live49_saved50_and_hour06_required=True,native_qualification_pending=True))


def configure(core,tools,output,review):
    core.ALLOWED_REPLACEMENTS=set(REPLACEMENTS)
    def validate(before,replacements):
        actual=source_review(core,tools,review['parent'],before,replacements,review['pins'],
            review['document']['focused_host_tests'],review['document']['failed_hour05_evidence'])
        if actual!=review['document']:raise ValueError('Reviewed source/AST/import inventory changed')
        return actual['ast_inventory']
    core.validate_repair_scope=validate
    tree=ast.parse(CORE.read_bytes())
    derive_node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='derive')
    changed=0
    for node in ast.walk(derive_node):
        if (isinstance(node,ast.If) and any(isinstance(value,ast.Constant) and
                value.value=='Explicit paired launcher and new classic frontend replacements required'
                for value in ast.walk(node))):
            expected=ast.parse("not {'launcher.py','classic_frontend.py'}<=set(replacements)",mode='eval').body
            if ast.dump(node.test,include_attributes=False)!=ast.dump(expected,include_attributes=False):
                raise ValueError('Historical paired replacement condition changed')
            node.test=ast.parse('set(replacements)!=set('+repr(REPLACEMENTS)+')',mode='eval').body
            for value in ast.walk(node):
                if isinstance(value,ast.Constant) and value.value=='Explicit paired launcher and new classic frontend replacements required':
                    value.value='Exact codec/model-address-space sources and paired READMEs required'
            changed+=1
    if changed!=1:raise ValueError('Exactly one historical paired-condition substitution required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[derive_node],type_ignores=[])),
        '<historical-derive-with-exact-build33-set>','exec'),core.__dict__)
    original=core.derive
    def derive(parent,files,replacements,reviewer):
        prior=dict(files);manifest,files,provenance=original(parent,files,replacements,reviewer)
        binding=core.strict(files['BINDING.json']);acceptance=core.strict(files['PRODUCTION_ACCEPTANCE.json'])
        raw=dict(binding['raw_qualification_evidence'])
        if raw.get('evidence')!=OLD_TARGET+'/RAW_QUALIFICATION_PROOF.json':raise ValueError('Exact raw binding location required')
        raw['evidence']=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json';binding['raw_qualification_evidence']=raw
        if core.sha(files['installed_source.py'])!=RAW_SOURCE_SHA:raise ValueError('Qualified physical source changed')
        if any(files[name]!=prior[name] for name in RAW_PROOFS):raise ValueError('Immutable raw proof bytes changed')
        acceptance['limitations']=[
            'Build33 replaces only the codec/support pair, three source-bound model-address-space paths and their two maintained READMEs over sealed build32. Native qualification remains pending; build32 was never native-staged.',
            'The compact writer uses the C canonical JSON encoder, patch-first selection and immutable byte submission. Actual HOST14 matched exact compact bytes/digests and reduced traced preparation peak without measured CPU regression; it does not establish sustained native throughput.',
            'The finite model virtual-address ceiling changes from 768 MiB to 1 GiB for the worker and its admitted recording parents. The frontend keeps 256 MiB soft AS, independent metadata keeps 128 MiB, other qualification parents keep 768 MiB. Physical free-RAM floors, CPU/stack/core/task/disk guards, source ownership and backlog thresholds remain.',
            'Closed hour05 remains FAILED at 922.9 source seconds with compact MemoryError and contemporaneous D1 backlog pressure. Exact allocation/stop ordering is unproven. No failed receipt becomes a PASS by raising this finite candidate ceiling.',
            'All other build32 gallery capacity code, build31 caption identity code, models, assets, descriptors, calibration, recordings and raw source/proof bytes remain identical. Raw binding location is translated only to the new package.',
            'Fresh Live49, Saved50 and sustained hour06 plus complete independent closure/mirror are required before final activation from the actual build30 desktop CAS. Historical parent limitations below retain their original scopes.'
        ]+core.strict(prior['PRODUCTION_ACCEPTANCE.json'])['limitations']
        provenance.update(schema='just-peachy.event-writer-model-as-runtime-repair.v1',
            resource_storage_policy_changed=False,model_address_space_policy_changed=True,
            capacity_and_logical_quota_policy_changed=False,gallery_capacity_and_logical_quota_policy_changed=False,
            recording_capacity_and_logical_quota_policy_changed=False,
            parent32_gallery_capacity_and_logical_quota_policy_retained=True,
            model_address_space_policy=MODEL_POLICY,event_writer_allocation_strategy_changed=True,
            source_review_sha256=review['sha256'],static_import_closure=review['document']['import_closure'],
            focused_host_tests=review['document']['focused_host_tests'],
            parent32_gallery_host20_reference=review['document']['parent32_gallery_host20_reference'],
            failed_hour05_evidence=review['document']['failed_hour05_evidence'],
            logical_event_stream_and_compact_record_bytes_unchanged=True,queue_fifo_and_fsync_durability_retained=True,
            physical_free_ram_and_disk_reserves_retained=True,finite_model_as_768_mib_to_1_gib=True,
            all_physical_virtual_limits_unchanged=False,source_constants_are_model_as_authority=True,
            binding_and_acceptance_limits_structure_unchanged=True,
            parent32_gallery_capacity_and_parent31_caption_repairs_retained=True,
            models_assets_backend_descriptors_raw_source_and_raw_proof_bytes_unchanged=True,
            raw_qualification_repeated=False,raw_evidence_path_translation_only=True,
            original_hour05_failure_retained=True,exclusive_failure_allocation_or_stop_order_proven=False,
            native_measurements_relabelled=False,native_qualification_pending=True)
        files['REPAIR_PROVENANCE.json']=files['REPAIR_PROVENANCE.restore.json']=core.encoded(provenance)
        content=core.sha(core.encoded(core.rows({name:raw for name,raw in files.items()
            if name not in core.CONTENT_EXCLUDED and not name.startswith('source-backups/')})))
        acceptance['candidate_content_sha256']=binding['candidate_content_sha256']=content
        files['PRODUCTION_ACCEPTANCE.json']=core.encoded(acceptance)
        binding['production_acceptance_sha256']=core.sha(files['PRODUCTION_ACCEPTANCE.json'])
        files['BINDING.json']=core.encoded(binding);manifest.update(candidate_content_sha256=content,files=core.rows(files))
        allowed=set(REPLACEMENTS)|{'BINDING.json','PRODUCTION_ACCEPTANCE.json','REPAIR_PROVENANCE.json','REPAIR_PROVENANCE.restore.json'}
        for name in CODEC_NAMES+MODEL_NAMES:allowed.update({'source-backups/'+name+'.backup','source-backups/'+name+'.restore'})
        additions=set(files)-set(prior);removals=set(prior)-set(files)
        differences={name for name in set(files)&set(prior) if files[name]!=prior[name]}
        if removals or additions!=allowed-set(prior) or differences-allowed:raise ValueError('Unapproved build33 member change')
        old_binding=core.strict(prior['BINDING.json'])
        protected=set(old_binding)-{'target','reference_code','raw_factory_path','profiles','candidate_content_sha256',
            'production_acceptance_sha256','native_qualified','admission_sha256','optional_refiner_admissions',
            'optional_refiner_admission','raw_qualification_evidence'}
        if set(binding)-set(old_binding) or any(binding[key]!=old_binding[key] for key in protected):
            raise ValueError('Operational binding structure or protected policy changed')
        if binding['raw_qualification_evidence']!=dict(old_binding['raw_qualification_evidence'],evidence=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json'):
            raise ValueError('Raw proof changed beyond path translation')
        if acceptance['limits']!=core.strict(prior['PRODUCTION_ACCEPTANCE.json'])['limits']:
            raise ValueError('Session/drain/backlog/physical acceptance limits changed')
        output.write(output.root/'BUILD32_MEMBER_PRESERVATION.json',core.encoded(dict(parent_manifest_sha256=BASE_SHA,
            allowed_changed_members=sorted(allowed),actual_changed_members=sorted(differences),
            added_members=sorted(additions),removed_members=[],unchanged_parent_members=len(prior)-len(differences),
            all_other_runtime_assets_models_profiles_raw_proof_bytes_identical=True,
            binding_and_acceptance_limits_structure_preserved=True,model_address_space_policy=MODEL_POLICY,
            package_manifest_is_separate_derived_control=True)))
        if len(files)+1>512 or sum(map(len,files.values()))>core.MAX_PACKAGE:raise ValueError('Finite preserved package extent exceeded')
        return manifest,files,provenance
    core.derive=derive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-only',action='store_true')
    parser.add_argument('--review-manifest',type=Path);parser.add_argument('--review-sha256');parser.add_argument('--reviewer')
    parser.add_argument('--host-test-root',type=Path,required=True,help='Actual HOST14 writer proof')
    parser.add_argument('--address-space-test-root',type=Path,required=True,help='Actual HOST10 source-bound AS proof')
    args=parser.parse_args();root,owner=bootstrap();sys.dont_write_bytecode=True
    core,core_raw=load_pinned('build33_core',CORE,CORE_SHA)
    tools,_=load_pinned('build33_inventory',INVENTORY,INVENTORY_SHA)
    tools.REPLACEMENTS=REPLACEMENTS;tools.ENTRIES=ENTRIES
    core.BASE=BASE;core.BASE_SHA=BASE_SHA;core.OLD_TARGET=OLD_TARGET;core.NEW_TARGET=NEW_TARGET
    output=core.Output(root);output.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,maximum_seconds=600,
        issued_unix=time.time(),target=NEW_TARGET,native_action=False,review_only=args.review_only,archive_maximum_bytes=core.MAX_ARCHIVE)))
    roots={'CODEC':args.host_test_root.absolute(),'AS':args.address_space_test_root.absolute()}
    for path in roots.values():
        if path.resolve(strict=True)!=path or path.parent!=PRIVATE/'audit-preparation' or not path.is_dir():
            raise ValueError('Exact ordinary private successful test roots required')
    origins={name:(MODEL if name in MODEL_NAMES+('README_MODEL_ADDRESS_SPACE.md',) else HERE)/name for name in REPLACEMENTS}
    inputs=dict(origins)
    inputs.update({name:HERE/name for name in CODEC_CHECKS});inputs.update({name:MODEL/name for name in MODEL_CHECKS})
    inputs.update({'build_event_package33.py':Path(__file__),'README_EVENT_PACKAGE33.md':HERE/'README_EVENT_PACKAGE33.md',
        'PACKAGING_CORE.py':CORE,'INVENTORY_HELPER32.py':INVENTORY})
    inputs.update({name:path for name,(path,sha) in HOUR_INPUTS.items()})
    for prefix,path in roots.items():
        inputs.update({prefix+'_'+name+'.json':path/(name+'.json') for name in
            ('RESULT','REGISTERED_OWNER','HOST_CLOSED','SOURCE_CLOSED','SOURCE_UNCHANGED')})
    pins={};raw_inputs={};replacements={}
    for name,path in sorted(inputs.items()):
        raw=core.read(path)
        for suffix in ('backup','restore'):output.write(root/'prepared-source'/suffix/name,raw)
        if core.read(path)!=raw:raise ValueError('Source changed during independent source closure')
        pins[name]=dict(path=str(path),bytes=len(raw),sha256=core.sha(raw));raw_inputs[name]=raw
        if name in REPLACEMENTS:replacements[name]=raw
        if name in HOUR_INPUTS and pins[name]['sha256']!=HOUR_INPUTS[name][1]:raise ValueError('Accepted hour05 evidence changed')
    parent,before=core.inventory(BASE)
    admissions={
        'codec':admit_host(core,raw_inputs,pins,'CODEC',roots['CODEC'],HERE,CODEC_NAMES,CODEC_CHECKS,
            'just-peachy.event-writer-streaming-host.v1',14,REFERENCE_SHA,before),
        'address_space':admit_host(core,raw_inputs,pins,'AS',roots['AS'],MODEL,MODEL_NAMES,MODEL_CHECKS,
            'just-peachy.model-address-space-host.v1',10,BASE_SHA,before)}
    accepted={'CODEC_RESULT.json':'11d11396ac5bf239bdac983646e3d01369b624a54b6c57b277a2b0c9bbf4c337',
        'CODEC_REGISTERED_OWNER.json':'e3d67cc9d34b4045f9aa5cd4f7f9bddd22f765c64ad351eb5b66c7e9b547c2c4',
        'CODEC_HOST_CLOSED.json':'4dbf7abc86608cb0284d673f5fc80bf71468e9d70810e375015461a06b2d50a0',
        'CODEC_SOURCE_CLOSED.json':'3319bcbc9f7af913c16b999d515371c775782052e84415a4743eeb7264128fa9',
        'CODEC_SOURCE_UNCHANGED.json':'de42254ad5aab816ef3f95457ac42476661747a63a5a748c5e935e74990d3aad',
        'AS_RESULT.json':'ae873cdb69385ee3c8fa7918ddc20221a8871f356c06162fdf9b62eead857bcf',
        'AS_REGISTERED_OWNER.json':'8061dd5f0237ee34f5c300898c0c4c488ad6e0c8edae43260bd6aef7ab3790dc',
        'AS_HOST_CLOSED.json':'0c5d430b60d69d1bf9b11d60140f258867c3e225706f79a3181b92506731c9e7',
        'AS_SOURCE_CLOSED.json':'6ab12038539ebf79b3b5b3a54dde3b01e3ec58a75d5af38b38f994655ba36380',
        'AS_SOURCE_UNCHANGED.json':'21dee30313c0957e39100a6032a2aabaadc96fb36bb2c9fbc3fdafed64ea1020'}
    if any(pins[name]['sha256']!=sha for name,sha in accepted.items()):
        raise ValueError('Exact accepted HOST14/HOST10 proof bytes required')
    compact=core.strict(raw_inputs['HOUR05_COMPACTION.json'])
    if compact.get('complete') is not False or compact.get('error')!='MemoryError()':raise ValueError('Historical hour05 failure scope changed')
    hour=dict(receipt_sha256={name:pins[name]['sha256'] for name in HOUR_INPUTS},
        logical_records=compact['records'],logical_bytes=compact['logical_bytes'],physical=compact['physical'],
        complete=False,error=compact['error'],source_seconds=922.9,
        external_closed_mirror_distinct_from_internal_failed_writer=True,exclusive_allocation_or_stop_order_proven=False)
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),inputs=pins,independent_restores=True,owner=owner)))
    document=source_review(core,tools,parent,before,replacements,pins,admissions,hour)
    raw=core.encoded(document);output.write(root/'SOURCE_DIFF_REVIEW.json',raw)
    if args.review_only:
        output.write(root/'SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),owner=owner,
            source_review_sha256=core.sha(raw),actual_package_built=False,native_action=False)))
        print(json.dumps(dict(output=str(root),source_review=str(root/'SOURCE_DIFF_REVIEW.json'),source_review_sha256=core.sha(raw),actual_package_built=False,native_action=False)))
        return
    if args.review_manifest is None or args.review_sha256 is None or not args.reviewer:
        raise ValueError('Exact root-reviewed source manifest/SHA/reviewer required before build')
    approved=core.read(args.review_manifest)
    if core.sha(approved)!=args.review_sha256 or core.strict(approved)!=document:raise ValueError('Root-reviewed exact source inventory differs')
    configure(core,tools,output,dict(parent=parent,pins=pins,document=document,sha256=args.review_sha256))
    tree=ast.parse(core_raw);main_node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    changed=0
    for node in ast.walk(main_node):
        if isinstance(node,ast.Constant) and node.value=='field-runtime-v29-build-17-prepared.tar.gz':
            node.value='field-runtime-v29-build-33-prepared.tar.gz';changed+=1
    if changed!=1:raise ValueError('Exactly one historical archive basename substitution required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[main_node],type_ignores=[])),
        '<historical-package-main-with-build33-basename>','exec'),core.__dict__)
    core.bootstrap=lambda parent:output
    sys.argv=[str(Path(__file__)),'--base',str(BASE),'--base-manifest-sha256',BASE_SHA,'--reviewer',args.reviewer]
    for name in REPLACEMENTS:sys.argv.extend(['--replacement',name+'='+str(origins[name])])
    core.main()


if __name__=='__main__':main()
