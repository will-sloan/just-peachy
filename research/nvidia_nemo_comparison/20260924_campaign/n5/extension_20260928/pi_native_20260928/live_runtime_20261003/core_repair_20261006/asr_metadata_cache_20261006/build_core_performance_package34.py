"""Immutable build34 preparation; README_CORE_PERFORMANCE_PACKAGE34.md.

Exact cache/copy/capacity source union and actual focused host proofs only.
Review/build execution needs coordinator authorization; no native dispatch.
"""
import argparse
import ast
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE=PRIVATE/'audit-preparation/event-package33-efdac72ba11f4e8e93b519e80dc3898a/package'
BASE_SHA='2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e'
BASE_CONTENT_SHA='8b0eefd6ffa5a0749a1eeaf607e9454efd5fa16cbf76d373fcbb1fe22d759631'
CORE=HERE.parent.parent/'ui_restore_20261004/build_classic_package.py'
CORE_SHA='bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5'
INVENTORY=HERE.parent/'capacity_gallery_20261006/build_gallery_package32.py'
INVENTORY_SHA='7f30a1a15631698630888fbf93fb0711197f1e3d820695b54a76528f358021d2'
OLD_TARGET='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-33'
NEW_TARGET=OLD_TARGET[:-2]+'34'
CACHE_NAMES=('asr_segment_runtime.py','asr_metadata_cache.py')
CACHE_CHECKS=('test_asr_metadata_cache.py','run_host_asr_metadata_cache.py')
PROJECTION_ROOT=HERE.parent/'s7_projection_copy_20261006'
PROJECTION_NAMES=('s7_projection_copy.py','classic_frontend.py')
PROJECTION_CHECKS=('test_s7_projection_copy.py','run_host_s7_projection_copy.py')
CAPACITY_ROOT=HERE.parent/'disk_capacity_policy_20261006'
CAPACITY_NAMES=('nemotron_binding.py','profiles.py','telemetry.py','installed_engine.py',
    'application_controller.py','release_authorization.py','launcher.py','capacity_drain_profile.py')
CAPACITY_CHECKS=('test_disk_capacity_policy.py','run_host_disk_capacity_checks.py')
DOCUMENT_ORIGINS={'README_ASR_METADATA_CACHE.md':HERE,
    'README_S7_PROJECTION_COPY.md':PROJECTION_ROOT,
    'README_DISK_CAPACITY_POLICY.md':CAPACITY_ROOT}
ORIGINS={name:HERE/name for name in CACHE_NAMES}
ORIGINS.update({name:PROJECTION_ROOT/name for name in PROJECTION_NAMES})
ORIGINS.update({name:CAPACITY_ROOT/name for name in CAPACITY_NAMES})
ORIGINS.update({name:folder/name for name,folder in DOCUMENT_ORIGINS.items()})
REPLACEMENTS=tuple(ORIGINS)
ENTRIES=('native_scope.py','launcher.py','worker.py','gallery_worker.py','launch_raw_qualification_action.py')
RAW_SOURCE_SHA='84f40eb404049164ec7efdaf27668e0a54044b5a874323f779237148e75768bf'
RAW_PROOFS=('RAW_QUALIFICATION_PROOF.json','RAW_QUALIFICATION_MIRROR_MANIFEST.json',
            'RAW_QUALIFICATION_MIRROR_COMPLETE.json','RAW_QUALIFICATION_JOB.json')
SOURCE_SET_SETTLED=True
PROOF_NAMES=('RESULT','REGISTERED_OWNER','HOST_CLOSED','SOURCE_CLOSED','SOURCE_UNCHANGED')
ACCEPTED={'CACHE':{
    'RESULT':'76a8e4f0bfcd99b729e7f055d0ecd3d9de68ffc7d153a5f252e6a86937e45c47',
    'REGISTERED_OWNER':'80838f73dc56b4f9755089e1df4dad6049e8eff110b963acad8cb9293d40bcad',
    'HOST_CLOSED':'5d307de968239b9c828cc1b7a954bb9a38d5da46fdd41abee0519e3985f2f7ff',
    'SOURCE_CLOSED':'2c8266f12ee0cf26a89f68299c7ddc94a62eef4ac1049638c6869a741f18d36d',
    'SOURCE_UNCHANGED':'662b84a38ac2a7b667752ad2e4335f4dfbde5e6f559ef0fc8a6921f6db043174'},
    'PROJECTION':{
    'RESULT':'d6492c0804ccb005c1ed6ed2e062e598179b25f790d24805c475ac63d339e664',
    'REGISTERED_OWNER':'8f0bd040691d272374f29fa277ea7ee319945c461421855d8c72cfcc13ffc916',
    'HOST_CLOSED':'8e3afb8970c9de95c09689b37473ae9459fc86ea3409e120a4911ccb92f9e36d',
    'SOURCE_CLOSED':'ef034da2340012a152151eb4e056af6efccd483b1bf9905758ccce71c1bba27b',
    'SOURCE_UNCHANGED':'3a0ff6496a4065a0e9887c117b145ff7ba93d10449af205638a1095dfb0f1f58'},
    'CAPACITY':{
    'RESULT':'5558c307b3878c34bdbb5e4249e7c0f75b8847a945cb7e31674d4948cbdf845c',
    'REGISTERED_OWNER':'bd1c402e88008640667494c4113e9cd4bb6ecc754bebeb80e51b04544630fde3',
    'HOST_CLOSED':'a50b23d0f4203233e73621303603ce607973496ab0686d919048202e6884e3d9',
    'SOURCE_CLOSED':'1dd1c56727446a821d294a5f44bb0a92eed83279363ce8c17d2ce02aafae17f8',
    'SOURCE_UNCHANGED':'945e7c5be9d5e9ac9e2940cd82f730b4bfa608f572ed3a2f20890fa41e953c5f'}}
PROOF_TABLE={
    'CACHE':dict(schema='just-peachy.asr-metadata-cache-host.v1',count=17,origin=HERE,
        runtime=CACHE_NAMES,checks=CACHE_CHECKS,reference_field='package_manifest_sha256',
        reference_sha=BASE_SHA,source_count=14,backup_pattern='SOURCE_%03d.backup',
        restore_pattern='SOURCE_%03d.restore'),
    'PROJECTION':dict(schema='just-peachy.s7-projection-copy-host.v1',count=19,origin=PROJECTION_ROOT,
        runtime=PROJECTION_NAMES+('installed_engine.py',),checks=PROJECTION_CHECKS,
        reference_field='package_manifest_sha256',reference_sha=BASE_SHA,source_count=19,
        backup_pattern='SOURCE_%03d.backup',restore_pattern='SOURCE_%03d.restore'),
    'CAPACITY':dict(schema='just-peachy.disk-capacity-policy-host.v1',count=19,origin=CAPACITY_ROOT,
        runtime=CAPACITY_NAMES,checks=CAPACITY_CHECKS,reference_field='package_manifest_sha256',
        reference_sha=BASE_SHA,source_count=461)}
CAPACITY_README_UPDATE_SHA='fb7e13840fe6991dd5cedfdd8f179dd949af8ed95c161b99c10fc2ddf18f74ff'
PERFORMANCE_POLICY=dict(
    asr_metadata_cache=dict(maximum_charged_bytes=8*1024**2,maximum_entries=4096,
        immutable_cached_sql_json=True,fresh_returns=True,postcommit_parent_and_group_invalidation=True,
        fault_fenced_sql_fallback=True,separate_session_ledger_from_history=True,
        native_throughput_measured=False),
    s7_projection_copy=dict(exact_origin_and_reverse_ast_bound=True,per_instance_install=True,
        supported_modes_initial_overwritten_copies_removed=True,final_public_deepcopies_retained=True,
        visible_analysis_delay=True,real_time_qualification_claimed=False),
    ordinary_capacity_policy=dict(manual_stop=True,max_backlog_seconds=None,
        source_and_drain_capacity_derived=True,default_nonmanual_backlog_seconds=120,
        optional_refinement_finite_latency_admission_retained=True,
        finite_stop_and_cleanup_deadlines_retained=True),
    native_workspace=dict(full_abi_retained_rows=True,lazy_observed_count=True,
        actual_effective_as_and_physical_ram_admission=True,model_math_and_source_sequence_changed=False),
    failed_hour06_preserved=True,native_qualification_pending=True)


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
    if parent.resolve(strict=True)!=parent:raise ValueError('Exact ordinary private host parent required')
    root=parent/('core-performance-package34-'+uuid.uuid4().hex);root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
        creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    raw=json.dumps(owner,sort_keys=True).encode()
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short early registered owner write')
        stream.flush();os.fsync(stream.fileno())
    with (root/'REGISTERED_OWNER.json').open('rb') as stream:
        if stream.read(len(raw)+1)!=raw:raise OSError('Early owner readback differs')
    return root,owner


def load_pinned(name,path,sha):
    info=path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or path.is_symlink()
            or getattr(info,'st_file_attributes',0)&0x400
            or any(parent.is_symlink() or getattr(parent.lstat(),'st_file_attributes',0)&0x400 for parent in path.parents)
            or info.st_size>2*1024**2):
        raise ValueError('Bounded ordinary single-link pinned helper required')
    with path.open('rb') as stream:raw=stream.read(2*1024**2+1)
    if len(raw)>2*1024**2 or hashlib.sha256(raw).hexdigest()!=sha:
        raise ValueError('Exact reviewed helper bytes required: '+name)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,raw


def admit_host(core,raw_inputs,pins,family,root):
    spec=PROOF_TABLE[family]
    if spec is None or set(ACCEPTED[family])!=set(PROOF_NAMES):
        raise ValueError('Actual reviewed candidate proof table not settled')
    for name,sha in ACCEPTED[family].items():
        if pins[family+'_'+name+'.json']['sha256']!=sha:
            raise ValueError('Exact accepted host receipt bytes required: '+family)
    result,owner,closed,sources,unchanged=(core.strict(raw_inputs[family+'_'+name+'.json']) for name in PROOF_NAMES)
    proof_pins=sources.get('source_pins' if family=='CAPACITY' else 'pins',[])
    if (result.get('schema')!=spec['schema'] or result.get('status')!='PASS'
            or result.get('tests_run')!=spec['count'] or any(result.get(key)!=0 for key in ('failures','errors','skipped'))
            or any(result.get(key) is not True for key in ('fixture_closed','source_unchanged'))
            or any(result.get(key) is not False for key in ('models','native_action'))
            or result.get('failure') is not None or result.get('owner')!=owner or closed.get('owner')!=owner
            or owner.get('schema')!='just-peachy.host-registered-owner.v1' or owner.get('cpu')!=14
            or owner.get('affinity_mask')!=16384 or type(owner.get('pid')) is not int or owner['pid']<=0
            or type(owner.get('creation_filetime')) is not int or owner['creation_filetime']<=0
            or closed.get('os_process_absent') is not True
            or sources.get(spec['reference_field'])!=spec['reference_sha']
            or type(proof_pins) is not list or len(proof_pins)!=spec['source_count']):
        raise ValueError('Actual successful registered host/source proof and independent closure required: '+family)
    if family=='CAPACITY':
        # This exact root-accepted receipt honestly lacks an observed process
        # return code. PASS/code inspection does not manufacture a natural zero.
        if (closed.get('schema')!='just-peachy.host-independent-source-closure.v1'
                or closed.get('independent_os_check') is not True or closed.get('exit_code_observed') is not False
                or 'natural_exit_code' in closed or closed.get('source_pairs')!=461
                or closed.get('independent_source_backup_restore_exact') is not True
                or any(closed.get(key) is not False for key in ('models','native_action'))
                or sources.get('owner')!=owner or unchanged.get('owner')!=owner
                or sources.get('source_count')!=461 or sources.get('before_tests') is not True
                or sources.get('independent_backups_and_restores') is not True
                or unchanged.get('source_pins')!=proof_pins or unchanged.get('source_count')!=461
                or any(unchanged.get(key) is not True for key in ('after_tests','source_unchanged','independent_backup_restore_readback_exact'))
                or result.get('source_ast_and_pure_fixtures') is not True):
            raise ValueError('Exact root-accepted capacity closure with explicitly unknown natural exit required')
    else:
        if (closed.get('natural_exit_code')!=0
                or sources.get('backup_and_independent_restore') is not True or sources.get('before_check') is not True
                or unchanged.get('pins')!=proof_pins
                or any(unchanged.get(key) is not True for key in ('source_unchanged','fixture_closed','scope_closed'))
                or unchanged.get('native_action') is not False):
            raise ValueError('Exact natural exit and source preservation required: '+family)
        if family=='CACHE' and closed.get('independent_os_check') is not True:
            raise ValueError('Exact independent cache owner closure required')
        if family=='PROJECTION':
            observed=closed.get('independent_observed_unix')
            if type(observed) not in (int,float) or not math.isfinite(observed) or observed<owner['create_time']:
                raise ValueError('Exact projection independent observed closure timestamp required')
    tested={}
    expected_paths={name:ORIGINS[name] for name in spec['runtime']}
    expected_paths.update({name:spec['origin']/name for name in spec['checks']})
    maintained_paths={ORIGINS[name] for name in DOCUMENT_ORIGINS}
    for index,pin in enumerate(proof_pins):
        path=Path(pin['path'])
        if path.resolve(strict=True)!=path:raise ValueError('Canonical current host source path required')
        current=core.read(path)
        # Maintained README evidence can be updated after actual test closure.
        # Its exact current bytes are separately pinned in the source review.
        if path not in maintained_paths and (len(current)!=pin['bytes'] or core.sha(current)!=pin['sha256']):
            raise ValueError('Actual tested source changed: '+str(path))
        for key in ('backup_pattern','restore_pattern'):
            token=Path(pin['backup' if key=='backup_pattern' else 'restore'] if family=='CAPACITY' else spec[key]%index)
            if token.drive or token.anchor or '..' in token.parts:raise ValueError('Canonical relative source preservation token required')
            saved=root/token
            if saved.resolve(strict=True)!=saved or not saved.is_relative_to(root):raise ValueError('Host source preservation escapes its root')
            raw=core.read(saved)
            if len(raw)!=pin['bytes'] or core.sha(raw)!=pin['sha256']:
                raise ValueError('Host source backup/independent restore differs')
        if path.name in expected_paths and path==expected_paths[path.name]:
            if path.name in tested:raise ValueError('Duplicate tested source pin')
            tested[path.name]=pin
    for name in spec['runtime']+spec['checks']:
        if name not in tested or (tested[name]['bytes'],tested[name]['sha256'])!=(pins[name]['bytes'],pins[name]['sha256']):
            raise ValueError('Current runtime/check bytes differ from actual tested source: '+name)
    if family=='CACHE' and result.get('cache_query_elimination')!=dict(repeated_reads=200,candidate_sql_reads=1,
            reference_sql_reads=200,unrelated_metadata_commits=20,exact_normalized_rows=True,throughput_measured=False):
        raise ValueError('Measured cache query-count scope changed')
    if family=='CAPACITY':
        update=core.strict(raw_inputs['CAPACITY_MAINTAINED_README_UPDATE.json'])
        old=next(pin for pin in proof_pins if Path(pin['path'])==ORIGINS['README_DISK_CAPACITY_POLICY.md'])
        current=pins['README_DISK_CAPACITY_POLICY.md']
        if (pins['CAPACITY_MAINTAINED_README_UPDATE.json']['sha256']!=CAPACITY_README_UPDATE_SHA
                or update.get('schema')!='just-peachy.maintained-readme-update.v1'
                or Path(update.get('source',''))!=ORIGINS['README_DISK_CAPACITY_POLICY.md']
                or update.get('old_sha256')!=old['sha256'] or update.get('new_sha256')!=current['sha256']
                or update.get('bytes')!=current['bytes']
                or any(update.get(key) is not True for key in ('independent_restore_exact','only_readme_changed','runtime_fixture_runner_unchanged'))):
            raise ValueError('Exact maintained capacity README evidence update required')
        for key in ('backup','restore'):
            token=Path(update[key]);saved=root/token
            if token.drive or token.anchor or '..' in token.parts or saved.resolve(strict=True)!=saved or not saved.is_relative_to(root):
                raise ValueError('Canonical README update preservation token required')
            current_raw=core.read(saved)
            if len(current_raw)!=current['bytes'] or core.sha(current_raw)!=current['sha256']:
                raise ValueError('Current capacity README independent preservation differs')
    return dict(root=str(root),schema=spec['schema'],owner=owner,tests=spec['count'],exact_owner_closed=True,
        natural_exit_observed=family!='CAPACITY',natural_exit_code=0 if family!='CAPACITY' else None,
        root_accepted_unknown_capacity_natural_exit=family=='CAPACITY',
        runtime_and_check_bytes_match=True,receipts={name:pins[family+'_'+name+'.json']['sha256'] for name in PROOF_NAMES},
        measured_query_elimination=result.get('cache_query_elimination'),native_throughput_claimed=False)


def source_review(core,tools,parent,before,replacements,pins,admissions):
    if set(replacements)!=set(REPLACEMENTS):raise ValueError('Exact complete build34 candidate union required')
    if core.sha(before['asr_segment_runtime.py'])!='c5d474e86b6a38754dac4f86bcec6e244950822a2781e202a7362e05ac57219c':
        raise ValueError('Exact sealed33 tested ASR origin required')
    inventory={}
    for name in REPLACEMENTS:
        if name.endswith('.py'):
            compile(ast.parse(replacements[name],filename=name),name,'exec')
            inventory[name]=tools.ast_diff(before.get(name),replacements[name])
    prior=core.strict(before['REPAIR_PROVENANCE.json'])
    if prior.get('model_address_space_policy',{}).get('candidate_worker_bytes')!=1024**3:
        raise ValueError('Exact parent33 finite model address-space policy required')
    return dict(schema='just-peachy.core-performance-package-source-review.v1',
        parent_target=OLD_TARGET,target=NEW_TARGET,parent_manifest_sha256=BASE_SHA,
        parent_candidate_content_sha256=parent['candidate_content_sha256'],
        parent_repair_provenance_sha256=core.sha(before['REPAIR_PROVENANCE.json']),
        packaging_core_sha256=CORE_SHA,inventory_helper_sha256=INVENTORY_SHA,
        source_pins=pins,replacement_names=list(REPLACEMENTS),
        replacement_pins={name:dict(bytes=len(raw),sha256=core.sha(raw)) for name,raw in replacements.items()},
        ast_inventory=inventory,import_closure=tools.import_closure(dict(before,**replacements)),
        focused_host_tests=admissions,performance_policy=PERFORMANCE_POLICY,
        retained_model_address_space_policy=prior['model_address_space_policy'],
        packaging_core_adaptations=dict(exact_paired_frontend_condition_replaced=True,
            exact_single_archive_basename_changed_to_build34=True,immutable_core_edited=False,
            inventory_archive_and_whole_member_restore_validators_reused=True),
        constraints=dict(models_assets_and_backend_descriptor_bytes_changed=False,
            galleries_recordings_and_external_data_root_changed=False,raw_source_or_proof_bytes_changed=False,
            binding_and_acceptance_limits_structure_changed=False,model_address_space_ceiling_changed=False,
            durable_sql_and_event_content_or_fsync_relaxed=False,native_measurements_relabelled=False,
            failed_hour06_relabelled=False,native_throughput_claimed=False,native_qualification_pending=True))


def configure(core,tools,output,review):
    core.ALLOWED_REPLACEMENTS=set(REPLACEMENTS)
    def validate(before,replacements):
        actual=source_review(core,tools,review['parent'],before,replacements,review['pins'],review['document']['focused_host_tests'])
        if actual!=review['document']:raise ValueError('Root-reviewed source/AST/import inventory changed')
        return actual['ast_inventory']
    core.validate_repair_scope=validate
    tree=ast.parse(CORE.read_bytes())
    derive_node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='derive')
    changed=0
    for node in ast.walk(derive_node):
        if (isinstance(node,ast.If) and any(isinstance(value,ast.Constant) and
                value.value=='Explicit paired launcher and new classic frontend replacements required' for value in ast.walk(node))):
            expected=ast.parse("not {'launcher.py','classic_frontend.py'}<=set(replacements)",mode='eval').body
            if ast.dump(node.test,include_attributes=False)!=ast.dump(expected,include_attributes=False):raise ValueError('Historical paired condition changed')
            node.test=ast.parse('set(replacements)!=set('+repr(REPLACEMENTS)+')',mode='eval').body
            for value in ast.walk(node):
                if isinstance(value,ast.Constant) and value.value=='Explicit paired launcher and new classic frontend replacements required':
                    value.value='Exact complete reviewed build34 runtime and README union required'
            changed+=1
    if changed!=1:raise ValueError('Exactly one historical paired-condition substitution required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[derive_node],type_ignores=[])),
        '<historical-derive-with-exact-build34-set>','exec'),core.__dict__)
    original=core.derive
    def derive(parent,files,replacements,reviewer):
        prior=dict(files);manifest,files,provenance=original(parent,files,replacements,reviewer)
        binding=core.strict(files['BINDING.json']);acceptance=core.strict(files['PRODUCTION_ACCEPTANCE.json'])
        raw=dict(binding['raw_qualification_evidence'])
        if raw.get('evidence')!=OLD_TARGET+'/RAW_QUALIFICATION_PROOF.json':raise ValueError('Exact parent raw binding required')
        raw['evidence']=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json';binding['raw_qualification_evidence']=raw
        if core.sha(files['installed_source.py'])!=RAW_SOURCE_SHA or any(files[name]!=prior[name] for name in RAW_PROOFS):
            raise ValueError('Immutable qualified raw source/proof bytes changed')
        acceptance['limitations']=[
            'Build34 is the complete explicitly reviewed performance/capacity candidate union over immutable build33. Host contract checks do not establish native real-time performance or quality.',
            'The private ASR cache preserves normalized SQL returns, copied ownership, durable writes and failure fallback. Actual HOST17 reduced200 repeated read connections to1 across20 unrelated commits; native throughput is unmeasured.',
            'The S7 projection and normal capacity/workspace/drain changes are separately source-bound and host-tested. Their exact scope is recorded in REPAIR_PROVENANCE; no event, model input, evidence or history is dropped to reduce work.',
            'Build33 closed hour06 remains FAILED after649.3 source seconds at the configured120-second speaker backlog. No MemoryError occurred. Cache or policy changes do not relabel that failed measurement.',
            'The finite1GiB model address-space policy from build33, physical resources, immutable assets, gallery data, raw source/proof bytes and historical recordings remain their reviewed scopes. The raw binding path is relocated only.',
            'Fresh finite Live51/Saved52, experimental sustained hour07 and independent complete closure/mirror are needed before activation from the actual build30 desktop CAS. Finite checks retain their short qualification policy; production normal Start with capacity policy requires separate controlled evidence. Historical limitations below retain their original scopes.'
        ]+core.strict(prior['PRODUCTION_ACCEPTANCE.json'])['limitations']
        provenance.update(schema='just-peachy.core-performance-runtime-repair.v1',
            source_review_sha256=review['sha256'],static_import_closure=review['document']['import_closure'],
            focused_host_tests=review['document']['focused_host_tests'],performance_policy=PERFORMANCE_POLICY,
            parent33_repair_provenance_sha256=review['document']['parent_repair_provenance_sha256'],
            retained_model_address_space_policy=review['document']['retained_model_address_space_policy'],
            model_address_space_policy_changed=False,models_assets_and_backend_descriptors_changed=False,
            resource_storage_policy_changed=True,normal_capture_backlog_and_drain_policy_changed=True,
            physical_ram_disk_and_model_address_space_ceiling_changed=False,
            durable_sql_fsync_event_content_or_model_inputs_relaxed=False,
            raw_qualification_repeated=False,raw_evidence_path_translation_only=True,
            failed_hour06_relabelled=False,native_throughput_claimed=False,native_qualification_pending=True)
        files['REPAIR_PROVENANCE.json']=files['REPAIR_PROVENANCE.restore.json']=core.encoded(provenance)
        content=core.sha(core.encoded(core.rows({name:raw for name,raw in files.items()
            if name not in core.CONTENT_EXCLUDED and not name.startswith('source-backups/')})))
        acceptance['candidate_content_sha256']=binding['candidate_content_sha256']=content
        files['PRODUCTION_ACCEPTANCE.json']=core.encoded(acceptance)
        binding['production_acceptance_sha256']=core.sha(files['PRODUCTION_ACCEPTANCE.json'])
        files['BINDING.json']=core.encoded(binding);manifest.update(candidate_content_sha256=content,files=core.rows(files))
        allowed=set(REPLACEMENTS)|{'BINDING.json','PRODUCTION_ACCEPTANCE.json','REPAIR_PROVENANCE.json','REPAIR_PROVENANCE.restore.json'}
        for name in REPLACEMENTS:
            if name.endswith('.py'):allowed.update({'source-backups/'+name+'.backup','source-backups/'+name+'.restore'})
        additions=set(files)-set(prior);removals=set(prior)-set(files)
        differences={name for name in set(files)&set(prior) if files[name]!=prior[name]}
        if removals or additions!=allowed-set(prior) or differences-allowed:raise ValueError('Unapproved build34 member change')
        old_binding=core.strict(prior['BINDING.json'])
        protected=set(old_binding)-{'target','reference_code','raw_factory_path','profiles','candidate_content_sha256',
            'production_acceptance_sha256','native_qualified','admission_sha256','optional_refiner_admissions',
            'optional_refiner_admission','raw_qualification_evidence'}
        if set(binding)-set(old_binding) or any(binding[key]!=old_binding[key] for key in protected):
            raise ValueError('Operational binding structure or protected policy changed')
        if binding['raw_qualification_evidence']!=dict(old_binding['raw_qualification_evidence'],evidence=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json'):
            raise ValueError('Raw proof changed beyond path translation')
        if acceptance['limits']!=core.strict(prior['PRODUCTION_ACCEPTANCE.json'])['limits']:
            raise ValueError('Acceptance control limits changed')
        output.write(output.root/'BUILD33_MEMBER_PRESERVATION.json',core.encoded(dict(parent_manifest_sha256=BASE_SHA,
            allowed_changed_members=sorted(allowed),actual_changed_members=sorted(differences),added_members=sorted(additions),
            removed_members=[],unchanged_parent_members=len(prior)-len(differences),all_other_parent_members_byte_identical=True,
            binding_and_acceptance_limits_structure_preserved=True,package_manifest_is_separate_derived_control=True)))
        if len(files)+1>512 or sum(map(len,files.values()))>core.MAX_PACKAGE:raise ValueError('Finite preserved package extent exceeded')
        return manifest,files,provenance
    core.derive=derive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-only',action='store_true')
    parser.add_argument('--review-manifest',type=Path);parser.add_argument('--review-sha256');parser.add_argument('--reviewer')
    parser.add_argument('--host-test-root',type=Path,required=True)
    parser.add_argument('--projection-test-root',type=Path,required=True)
    parser.add_argument('--capacity-test-root',type=Path,required=True)
    args=parser.parse_args();root,owner=bootstrap();sys.dont_write_bytecode=True
    if not SOURCE_SET_SETTLED:raise ValueError('Build34 source/proof union is not frozen; source-only draft')
    core,core_raw=load_pinned('build34_core',CORE,CORE_SHA)
    tools,_=load_pinned('build34_inventory',INVENTORY,INVENTORY_SHA)
    tools.REPLACEMENTS=REPLACEMENTS;tools.ENTRIES=ENTRIES
    core.BASE=BASE;core.BASE_SHA=BASE_SHA;core.OLD_TARGET=OLD_TARGET;core.NEW_TARGET=NEW_TARGET
    output=core.Output(root);output.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,maximum_seconds=600,
        issued_unix=time.time(),target=NEW_TARGET,native_action=False,review_only=args.review_only,archive_maximum_bytes=core.MAX_ARCHIVE)))
    roots={name:path.absolute() for name,path in (('CACHE',args.host_test_root),('PROJECTION',args.projection_test_root),('CAPACITY',args.capacity_test_root))}
    for path in roots.values():
        if path.resolve(strict=True)!=path or path.parent!=PRIVATE/'audit-preparation' or not path.is_dir():
            raise ValueError('Exact ordinary private successful test roots required')
    inputs=dict(ORIGINS)
    for spec in PROOF_TABLE.values():
        inputs.update({name:spec['origin']/name for name in spec['checks']})
    inputs.update({'build_core_performance_package34.py':Path(__file__),
        'README_CORE_PERFORMANCE_PACKAGE34.md':HERE/'README_CORE_PERFORMANCE_PACKAGE34.md',
        'PACKAGING_CORE.py':CORE,'INVENTORY_HELPER32.py':INVENTORY})
    for family,path in roots.items():inputs.update({family+'_'+name+'.json':path/(name+'.json') for name in PROOF_NAMES})
    inputs['CAPACITY_MAINTAINED_README_UPDATE.json']=roots['CAPACITY']/'MAINTAINED_README_UPDATE.json'
    pins={};raw_inputs={};replacements={}
    for name,path in sorted(inputs.items()):
        raw=core.read(path)
        for suffix in ('backup','restore'):output.write(root/'prepared-source'/suffix/name,raw)
        if core.read(path)!=raw:raise ValueError('Source changed during independent source closure')
        pins[name]=dict(path=str(path),bytes=len(raw),sha256=core.sha(raw));raw_inputs[name]=raw
        if name in REPLACEMENTS:replacements[name]=raw
    parent,before=core.inventory(BASE)
    if parent['candidate_content_sha256']!=BASE_CONTENT_SHA:raise ValueError('Exact immutable33 content required')
    admissions={family:admit_host(core,raw_inputs,pins,family,path) for family,path in roots.items()}
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),inputs=pins,independent_restores=True,owner=owner)))
    document=source_review(core,tools,parent,before,replacements,pins,admissions)
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
            node.value='field-runtime-v29-build-34-prepared.tar.gz';changed+=1
    if changed!=1:raise ValueError('Exactly one historical archive basename substitution required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[main_node],type_ignores=[])),
        '<historical-package-main-with-build34-basename>','exec'),core.__dict__)
    core.bootstrap=lambda parent:output
    sys.argv=[str(Path(__file__)),'--base',str(BASE),'--base-manifest-sha256',BASE_SHA,'--reviewer',args.reviewer]
    for name in REPLACEMENTS:sys.argv.extend(['--replacement',name+'='+str(ORIGINS[name])])
    core.main()


if __name__=='__main__':main()
