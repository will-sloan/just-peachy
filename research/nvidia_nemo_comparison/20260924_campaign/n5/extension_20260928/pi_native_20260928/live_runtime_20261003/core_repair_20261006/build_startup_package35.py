"""Prepare the immutable35 startup overlay; README_STARTUP_PACKAGE35.md.

Source-only until the exact changed startup source and host-proof table settles.
The immutable34 packaging helper supplies the original inventory/archive guards.
"""
import argparse
import ast
import copy
import ctypes
import hashlib
import os
from pathlib import Path
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE=PRIVATE/'audit-preparation/core-performance-package34-fd1c79ff6e7f4a28b461c329a0b36e14/package'
BASE_SHA='fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802'
BASE_CONTENT_SHA='aec9d81d0208b608ebe1a0c43ec4d67ebeb04811f4b5e54187ee8616b3dce9d1'
BASE_PINS={
    'SOURCE_DIFF_REVIEW.json':'53275087e72069b6d3012f505616079ab8debaa90a290848f1830e159e9c6096',
    'BUILD_RESULT.json':'9331461c4a5664b040a7f98e243ea851f398a89fbae5dba7036e06e6b6ac7873',
    'INDEPENDENT_CLOSURE.json':'923c2d77c1c9cba03a88dad3075aaf15de994665c7b15c37c2dedfb0c8ed7aa4'}
BASE_ARCHIVE=BASE.parent/'field-runtime-v29-build-34-prepared.tar.gz'
BASE_ARCHIVE_SHA='5a4e83bf7b9bbe3874b363e7af842b706ddecc8150f7676874c7c7d003a36ce1'
PARENT_HELPER=HERE/'asr_metadata_cache_20261006/build_core_performance_package34.py'
PARENT_HELPER_SHA='959e7780a1f56ff99101fbe375beff9f3e15d4a8466cf1547fd4a6a10554790c'
OLD_TARGET='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-34'
NEW_TARGET=OLD_TARGET[:-2]+'35'
CANDIDATE=HERE/'xvf_fresh_start_20261006'
REPLACEMENTS=('launcher.py','xvf_readiness_helper.py','README_XVF_FRESH_START.md',
    'classic_frontend.py','README_CLASSIC_STORAGE_COPY35.md')
TESTED_NAMES=('launcher.py','xvf_readiness_helper.py','README_XVF_FRESH_START.md')
FRONTEND_SHA='fb89df638bafb00f16ea9c1ae0073fc0393e3fde0f9baa8c6fbebf8284db8a56'
OLD_STORAGE_COPY='Normal live tests last at most five minutes; audio is disk-spooled and kept only after your post-Stop choice.'
NEW_STORAGE_COPY='Normal live sessions continue until Stop within available storage; audio is disk-spooled and kept only after your post-Stop choice.'
CHECKS=('test_xvf_fresh_start.py','run_host_xvf_fresh_start.py')
ORIGINS={name:CANDIDATE/name for name in REPLACEMENTS}
PROOF_NAMES=('RESULT','REGISTERED_OWNER','HOST_CLOSED','SOURCE_CLOSED','SOURCE_UNCHANGED')
# Actual changed HOST19 closed naturally and was independently absent.
SOURCE_SET_SETTLED=True
ACCEPTED_STARTUP={
    'RESULT':'659e284ad8d6a70917ddc49647ae6ad6aea4b62ddcfdfbc9aab4072abcce2576',
    'REGISTERED_OWNER':'546f6557de16482197d42f817200d573d866bb22e337c94975bf2d86eb965b7e',
    'HOST_CLOSED':'1b5a09e565f48c5fd71f3b901fdc757cbd761c25234e4f807fece990f6da799d',
    'SOURCE_CLOSED':'d7b37f1534ceea8fcc540f4a381620b66d70f183aaa1030997bcce40811b2f70',
    'SOURCE_UNCHANGED':'1d233e24fcbf3ddd0e5323077a7aa245dc6e41cc9fc213dc617a59ab2ba88b11'}
STARTUP_TEST_COUNT=19
STARTUP_SOURCE_COUNT=452
STARTUP_PIN_FIELD='source_pins'
STARTUP_UNCHANGED_PIN_FIELD='source_pins'
STARTUP_CLOSURE_EXPECTATIONS=dict(natural_exit_code=0,os_process_absent=True,independent_os_check=True)
STARTUP_README_TESTED_SHA='f7ee966e552c24099504198ffca4db411fb26315239af1fd7484915d07b8c167'
STARTUP_README_CURRENT_SHA='3a2c7f8fa4fc8b51f27ea7bacf1564373f6bca31cecf7816ea16f14ad3719203'


def bootstrap():
    """Register the exact CPU14 process before its first project-source read."""
    if os.name!='nt':raise RuntimeError('Windows host-only startup package preparation')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    process=kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(process,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(process,*(ctypes.byref(item) for item in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    parent=PRIVATE/'audit-preparation'
    if parent.resolve(strict=True)!=parent:raise ValueError('Canonical private output parent required')
    root=parent/('startup-package35-'+uuid.uuid4().hex);root.mkdir(exist_ok=False)
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    import json
    raw=(json.dumps(owner,sort_keys=True)+'\n').encode()
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short early owner write')
        stream.flush();os.fsync(stream.fileno())
    with (root/'REGISTERED_OWNER.json').open('rb') as stream:
        if stream.read(len(raw)+1)!=raw:raise OSError('Early owner readback differs')
    return root,owner


def load_parent():
    """Use the exact immutable34 loader after this process is registered."""
    import importlib.util
    import stat
    before=PARENT_HELPER.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
            or PARENT_HELPER.resolve(strict=True)!=PARENT_HELPER
            or getattr(before,'st_file_attributes',0)&0x400 or before.st_size>2*1024**2
            or any(path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400
                for path in PARENT_HELPER.parents)):
        raise ValueError('Canonical bounded immutable34 helper required')
    with PARENT_HELPER.open('rb') as stream:raw=stream.read(2*1024**2+1)
    after=PARENT_HELPER.lstat()
    if (hashlib.sha256(raw).hexdigest()!=PARENT_HELPER_SHA or len(raw)!=before.st_size
            or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=
               (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
        raise ValueError('Immutable34 helper bytes changed')
    spec=importlib.util.spec_from_file_location('startup35_exact_packaging34',PARENT_HELPER)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper,raw


def admit_parent(core,raw_inputs,parent,files):
    """Reuse accepted34 source/test proofs; do not rerun healthy host tests."""
    for name,pin in BASE_PINS.items():
        if core.sha(raw_inputs['PARENT_'+name])!=pin:raise ValueError('Exact parent34 receipt differs: '+name)
    document=core.strict(raw_inputs['PARENT_SOURCE_DIFF_REVIEW.json'])
    result=core.strict(raw_inputs['PARENT_BUILD_RESULT.json'])
    closure=core.strict(raw_inputs['PARENT_INDEPENDENT_CLOSURE.json'])
    owner=core.strict(raw_inputs['PARENT_REGISTERED_OWNER.json'])
    closed=core.strict(raw_inputs['PARENT_SOURCE_CLOSED.json'])
    if (parent['target']!=OLD_TARGET or parent['candidate_content_sha256']!=BASE_CONTENT_SHA
            or len(files)!=446 or len(document.get('source_pins',{}))!=41
            or len(document.get('replacement_pins',{}))!=15
            or document.get('schema')!='just-peachy.core-performance-package-source-review.v1'
            or result.get('manifest_sha256')!=BASE_SHA or result.get('candidate_content_sha256')!=BASE_CONTENT_SHA
            or result.get('archive_sha256')!=BASE_ARCHIVE_SHA or result.get('installed') is not False
            or closure.get('schema')!='just-peachy.core-package34-independent-closure.v1'
            or closure.get('owner')!=owner or closure.get('builder_os_process_absent') is not True
            or type(closure.get('builder_natural_exit_code')) is not int or closure['builder_natural_exit_code']!=0
            or closure.get('manifest_sha256')!=BASE_SHA or closure.get('source_review_sha256')!=BASE_PINS['SOURCE_DIFF_REVIEW.json']
            or closure.get('archive_sha256')!=BASE_ARCHIVE_SHA or closure.get('archive_members_readback')!=447
            or closure.get('archive_expanded_bytes')!=7492370 or closure.get('source_inputs')!=41
            or any(closure.get(key) is not True for key in ('independent_expanded_restore_exact',
                'source_backups_and_independent_restores_exact','current_sources_unchanged'))
            or closed.get('scope_closed') is not True or closed.get('native_action') is not False):
        raise ValueError('Actual independently closed parent34 package/source identity required')
    for name,pin in document['source_pins'].items():
        raw=core.read(Path(pin['path']))
        if (len(raw),core.sha(raw))!=(pin['bytes'],pin['sha256']):raise ValueError('Frozen34 source changed: '+name)
        for suffix in ('backup','restore'):
            if core.read(BASE.parent/'prepared-source'/suffix/name)!=raw:
                raise ValueError('Independent34 source backup/restore differs: '+name)
    for name,pin in document['replacement_pins'].items():
        if (len(files[name]),core.sha(files[name]))!=(pin['bytes'],pin['sha256']):
            raise ValueError('Parent34 replacement differs: '+name)
    if core.sha(core.read(BASE_ARCHIVE))!=BASE_ARCHIVE_SHA:
        raise ValueError('Immutable34 archive differs')
    return document


def admit_startup(core,raw_inputs,test_root,parent_files):
    """Exact actual receipt shapes are sealed before this function can admit."""
    if (not SOURCE_SET_SETTLED or set(ACCEPTED_STARTUP)!=set(PROOF_NAMES)
            or type(STARTUP_TEST_COUNT) is not int or STARTUP_TEST_COUNT<=0
            or type(STARTUP_SOURCE_COUNT) is not int or STARTUP_SOURCE_COUNT<=0
            or not STARTUP_PIN_FIELD or not STARTUP_UNCHANGED_PIN_FIELD or not STARTUP_CLOSURE_EXPECTATIONS):
        raise ValueError('Startup source/actual host proof table remains unsettled')
    for name,pin in ACCEPTED_STARTUP.items():
        if core.sha(raw_inputs['STARTUP_'+name+'.json'])!=pin:
            raise ValueError('Actual accepted startup proof bytes differ: '+name)
    result,owner,closed,sources,unchanged=(core.strict(raw_inputs['STARTUP_'+name+'.json']) for name in PROOF_NAMES)
    proof_pins=sources.get(STARTUP_PIN_FIELD)
    if (result.get('schema')!='just-peachy.xvf-fresh-start-host.v1' or result.get('status')!='PASS'
            or result.get('tests_run')!=STARTUP_TEST_COUNT
            or any(result.get(key)!=0 for key in ('failures','errors','skipped'))
            or result.get('owner')!=owner or closed.get('owner')!=owner
            or sources.get('owner')!=owner or unchanged.get('owner')!=owner
            or owner.get('schema')!='just-peachy.host-registered-owner.v1'
            or owner.get('cpu')!=14 or owner.get('affinity_mask')!=16384
            or any(type(owner.get(key)) is not int or owner[key]<=0 for key in ('pid','creation_filetime'))
            or any(result.get(key) is not True for key in ('fixture_closed','source_unchanged'))
            or any(result.get(key) is not False for key in ('models','native_action'))
            or result.get('failure') is not None or result.get('source_ast_and_pure_fixtures') is not True
            or result.get('package_manifest_sha256')!=BASE_SHA or result.get('source_count')!=STARTUP_SOURCE_COUNT
            or any(closed.get(key)!=value for key,value in STARTUP_CLOSURE_EXPECTATIONS.items())
            or type(closed.get('natural_exit_code')) is not int
            or sources.get('package_manifest_sha256')!=BASE_SHA
            or sources.get('source_count')!=STARTUP_SOURCE_COUNT or sources.get('before_tests') is not True
            or sources.get('independent_backups_and_restores') is not True
            or any(sources.get(key) is not False for key in ('models','native_action'))
            or unchanged.get('source_count')!=STARTUP_SOURCE_COUNT or unchanged.get('after_tests') is not True
            or unchanged.get('source_unchanged') is not True
            or unchanged.get('independent_backup_restore_readback_exact') is not True
            or type(proof_pins) is not list or len(proof_pins)!=STARTUP_SOURCE_COUNT
            or unchanged.get(STARTUP_UNCHANGED_PIN_FIELD)!=proof_pins):
        raise ValueError('Exact changed HOST PASS, owner, source and independent closure required')
    expected={BASE/name:('package/'+name,raw) for name,raw in parent_files.items()}
    expected[BASE/'PACKAGE_MANIFEST.json']=('package/PACKAGE_MANIFEST.json',core.read(BASE/'PACKAGE_MANIFEST.json'))
    expected.update({CANDIDATE/name:('draft/'+name,raw_inputs[name]) for name in (*TESTED_NAMES,*CHECKS)})
    if len(expected)!=STARTUP_SOURCE_COUNT:raise ValueError('Exact full parent package plus five changed proof inputs required')
    seen=set()
    tested_readme=None
    for pin in proof_pins:
        path=Path(pin['path'])
        if path not in expected or path in seen or pin.get('independent_restore_equal') is not True:
            raise ValueError('Unique exact admitted source paths and restored proof required')
        seen.add(path);token,current=expected[path]
        for side in ('backup','restore'):
            relative=Path(pin[side])
            if (not isinstance(pin[side],str) or relative.drive or relative.anchor
                    or '..' in relative.parts or pin[side]!=('source-'+side+'/'+token)):
                raise ValueError('Exact relative independent source token required')
            owned=(test_root/relative).resolve(strict=True)
            if not owned.is_relative_to(test_root):raise ValueError('Source restore token escaped actual host root')
            stored=core.read(owned)
            if (len(stored),core.sha(stored))!=(pin['bytes'],pin['sha256']):
                raise ValueError('Full actual source backup/restore readback differs')
            if side=='backup':backed=stored
            elif stored!=backed:raise ValueError('Source backup and independent restore differ')
        if path==CANDIDATE/'README_XVF_FRESH_START.md':
            if pin['sha256']!=STARTUP_README_TESTED_SHA or core.sha(current)!=STARTUP_README_CURRENT_SHA:
                raise ValueError('Exact tested/current maintained startup documentation required')
            for key in ('POST_HOST_README_BACKUP.md','POST_HOST_README_RESTORE.md'):
                if raw_inputs[key]!=backed:raise ValueError('Tested documentation independent preservation differs')
            tested_readme=dict(tested_sha256=pin['sha256'],tested_bytes=pin['bytes'],
                current_sha256=core.sha(current),current_bytes=len(current),
                tested_copy_backed_and_independently_restored=True,
                evidence_only_update_separately_pinned=True)
        elif current!=backed or core.read(path)!=current:
            raise ValueError('Actual tested production/check or parent source differs')
    if seen!=set(expected) or tested_readme is None:raise ValueError('Complete actual tested source inventory required')
    return dict(root=str(test_root),schema=result['schema'],tests=STARTUP_TEST_COUNT,
        source_count=STARTUP_SOURCE_COUNT,owner=owner,exact_owner_closed=True,natural_exit_code=0,
        independent_os_absence=True,all_source_backups_and_independent_restores_exact=True,
        runtime_and_fixture_sources_unchanged=True,models=False,native_action=False,
        receipt_sha256=ACCEPTED_STARTUP,maintained_readme=tested_readme)


def source_review(core,tools,parent,before,replacements,pins,admissions):
    if set(replacements)!=set(REPLACEMENTS):raise ValueError('Exact startup35 overlay required')
    frontend=replacements['classic_frontend.py']
    old=OLD_STORAGE_COPY.encode();new=NEW_STORAGE_COPY.encode()
    if (core.sha(frontend)!=FRONTEND_SHA or before['classic_frontend.py'].count(old)!=1
            or frontend.count(new)!=1 or frontend.replace(new,old)!=before['classic_frontend.py']):
        raise ValueError('Exact independently reviewed frontend storage sentence and whole reverse proof required')
    helper_references=[node for node in ast.walk(ast.parse(before['xvf_readiness.py']))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
        and node.func.attr=='with_name' and len(node.args)==1
        and isinstance(node.args[0],ast.Constant) and node.args[0].value=='xvf_readiness_helper.py']
    if len(helper_references)!=1:raise ValueError('Exact unchanged readiness subprocess entry required')
    prior=core.strict(before['REPAIR_PROVENANCE.json'])
    return dict(schema='just-peachy.xvf-startup-package-source-review.v1',
        parent_target=OLD_TARGET,target=NEW_TARGET,parent_manifest_sha256=BASE_SHA,
        parent_candidate_content_sha256=BASE_CONTENT_SHA,parent_archive_sha256=BASE_ARCHIVE_SHA,
        parent_source_review_sha256=BASE_PINS['SOURCE_DIFF_REVIEW.json'],
        parent_independent_closure_sha256=BASE_PINS['INDEPENDENT_CLOSURE.json'],
        packaging_helper34_sha256=PARENT_HELPER_SHA,packaging_core_sha256=admissions['core_sha256'],
        inventory_helper_sha256=admissions['inventory_sha256'],source_pins=pins,
        replacement_names=list(REPLACEMENTS),
        replacement_pins={name:dict(bytes=len(raw),sha256=core.sha(raw)) for name,raw in replacements.items()},
        ast_inventory={name:tools.ast_diff(before.get(name),raw)
            for name,raw in replacements.items() if name.endswith('.py')},
        import_closure=tools.import_closure(dict(before,**replacements)),
        explicit_subprocess_entry='xvf_readiness_helper.py',
        unchanged_readiness_dispatch_literal_verified=True,
        focused_host_tests=admissions['startup'],
        frontend_wording_review=dict(source_sha256=FRONTEND_SHA,whole_reverse_text_equal=True,
            single_sentence_only=True,host19_coverage_claimed=False),
        reused_build34_focused_host_tests=admissions['parent']['focused_host_tests'],
        retained_performance_policy=prior['performance_policy'],
        retained_model_address_space_policy=prior['retained_model_address_space_policy'],
        constraints=dict(xvf_readiness_module_byte_identical=True,
            unrelated_parent_runtime_models_assets_profiles_and_user_data_changed=False,
            disk_ram_model_address_space_or_backlog_policy_changed=False,
            raw_source_or_proof_bytes_changed=False,raw_binding_path_translation_only=True,
            durable_sql_event_content_or_fsync_relaxed=False,healthy_host_tests_repeated=False,
            live51_failure_relabelled=False,native_qualification_pending=True))


def configure35(helper,helper_raw,core,tools,output,review):
    """Reuse34 derivation, changing only its current provenance/limitations labels."""
    helper.BASE=BASE;helper.BASE_SHA=BASE_SHA;helper.OLD_TARGET=OLD_TARGET;helper.NEW_TARGET=NEW_TARGET
    helper.REPLACEMENTS=REPLACEMENTS
    helper.source_review=lambda c,t,p,b,r,s,ignored:source_review(c,t,p,b,r,s,review['admissions'])
    tree=ast.parse(helper_raw)
    function=copy.deepcopy(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='configure'))
    original=copy.deepcopy(function)
    limitations=[node for node in ast.walk(function) if isinstance(node,ast.Assign)
        and len(node.targets)==1 and isinstance(node.targets[0],ast.Subscript)
        and isinstance(node.targets[0].value,ast.Name) and node.targets[0].value.id=='acceptance'
        and isinstance(node.targets[0].slice,ast.Constant) and node.targets[0].slice.value=='limitations']
    updates=[node for node in ast.walk(function) if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
        and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name)
        and node.value.func.value.id=='provenance' and node.value.func.attr=='update']
    names=[node for node in ast.walk(function) if isinstance(node,ast.Constant) and node.value=='BUILD33_MEMBER_PRESERVATION.json']
    if len(limitations)!=1 or len(updates)!=1 or len(names)!=1:
        raise ValueError('Three exact immutable34 metadata derivation boundaries required')
    old_limitations=limitations[0].value;old_update=updates[0].value;old_name=names[0].value
    limitations[0].value=ast.parse("['Build35 is a narrow startup recovery overlay over immutable34. Native first-Start, normal production and sustained checks remain pending.', 'Only the two startup modules, their README, the exact Settings storage sentence and its README change; the34 cache/copy/capacity source and actual HOST17/19/19 proofs retain their original scopes.', 'Live51 on34 remains FAILED at zero processed samples with the AEC255 source fault. No wrapper exit or source proof relabels that failure.', 'Finite1GiB model AS, physical RAM/disk floors, normal manual capacity policy, models, assets, profiles, galleries, recording data, source clock and durable event semantics remain inherited. The raw proof binding path alone is relocated.'] + core.strict(prior['PRODUCTION_ACCEPTANCE.json'])['limitations']",mode='eval').body
    updates[0].value=ast.parse("provenance.update(schema='just-peachy.xvf-startup-runtime-repair.v1',source_review_sha256=review['sha256'],static_import_closure=review['document']['import_closure'],focused_host_tests=review['document']['focused_host_tests'],reused_build34_focused_host_tests=review['document']['reused_build34_focused_host_tests'],parent34_repair_provenance_sha256=core.sha(prior['REPAIR_PROVENANCE.json']),retained_performance_policy=review['document']['retained_performance_policy'],retained_model_address_space_policy=review['document']['retained_model_address_space_policy'],startup_recovery_policy_changed=True,model_address_space_policy_changed=False,resource_storage_policy_changed=False,normal_capture_backlog_and_drain_policy_changed=False,physical_ram_disk_and_model_address_space_ceiling_changed=False,durable_sql_fsync_event_content_or_model_inputs_relaxed=False,raw_qualification_repeated=False,raw_evidence_path_translation_only=True,live51_failure_relabelled=False,healthy_host_tests_repeated=False,native_qualification_pending=True)",mode='eval').body
    names[0].value='BUILD34_MEMBER_PRESERVATION.json'
    changed=copy.deepcopy(function)
    limitations[0].value=old_limitations;updates[0].value=old_update;names[0].value=old_name
    if ast.dump(function,include_attributes=False)!=ast.dump(original,include_attributes=False):
        raise ValueError('Metadata adapter reverse AST differs')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[changed],type_ignores=[])),
        '<exact34-derivation-with-startup35-metadata>','exec'),helper.__dict__)
    helper.configure(core,tools,output,review)
    output.write(output.root/'PACKAGING_ADAPTER_AST.json',core.encoded(dict(
        parent_helper_sha256=PARENT_HELPER_SHA,metadata_boundaries_changed=3,
        full_reverse_ast_equal=True,inventory_archive_and_member_restore_logic_reused=True)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-only',action='store_true')
    parser.add_argument('--startup-test-root',type=Path,required=True)
    parser.add_argument('--review-manifest',type=Path);parser.add_argument('--review-sha256');parser.add_argument('--reviewer')
    args=parser.parse_args();root,owner=bootstrap();sys.dont_write_bytecode=True
    if not SOURCE_SET_SETTLED:raise ValueError('Startup35 source/proofs remain source-only and unsettled')
    helper,helper_raw=load_parent()
    core,core_raw=helper.load_pinned('startup35_exact_core',helper.CORE,helper.CORE_SHA)
    tools,_=helper.load_pinned('startup35_exact_inventory',helper.INVENTORY,helper.INVENTORY_SHA)
    core.BASE=BASE;core.BASE_SHA=BASE_SHA;core.OLD_TARGET=OLD_TARGET;core.NEW_TARGET=NEW_TARGET
    tools.REPLACEMENTS=REPLACEMENTS;tools.ENTRIES=helper.ENTRIES+('xvf_readiness_helper.py',)
    output=core.Output(root);output.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,
        maximum_seconds=600,target=NEW_TARGET,archive_maximum_bytes=core.MAX_ARCHIVE,native_action=False)))
    test_root=args.startup_test_root.absolute()
    if test_root.resolve(strict=True)!=test_root or test_root.parent!=PRIVATE/'audit-preparation' or not test_root.is_dir():
        raise ValueError('Canonical actual private startup host root required')
    inputs=dict(ORIGINS)
    inputs.update({name:CANDIDATE/name for name in CHECKS})
    inputs.update({'build_startup_package35.py':Path(__file__),'README_STARTUP_PACKAGE35.md':HERE/'README_STARTUP_PACKAGE35.md',
        'PACKAGING_HELPER34.py':PARENT_HELPER,'PACKAGING_CORE.py':helper.CORE,'INVENTORY_HELPER32.py':helper.INVENTORY})
    inputs.update({'PARENT_'+name:BASE.parent/name for name in (*BASE_PINS,'REGISTERED_OWNER.json','SOURCE_CLOSED.json')})
    inputs.update({'STARTUP_'+name+'.json':test_root/(name+'.json') for name in PROOF_NAMES})
    inputs.update({'POST_HOST_README_'+side.upper()+'.md':CANDIDATE/'post_host_doc'/('README_XVF_FRESH_START.md.'+side)
        for side in ('backup','restore')})
    pins={};raw_inputs={};replacements={}
    for name,path in sorted(inputs.items()):
        raw=core.read(path)
        for suffix in ('backup','restore'):output.write(root/'prepared-source'/suffix/name,raw)
        if core.read(path)!=raw:raise ValueError('Source changed during independent source closure')
        pins[name]=dict(path=str(path),bytes=len(raw),sha256=core.sha(raw));raw_inputs[name]=raw
        if name in REPLACEMENTS:replacements[name]=raw
    parent,files=core.inventory(BASE)
    admissions=dict(parent=admit_parent(core,raw_inputs,parent,files),startup=admit_startup(core,raw_inputs,test_root,files),
        core_sha256=helper.CORE_SHA,inventory_sha256=helper.INVENTORY_SHA)
    document=source_review(core,tools,parent,files,replacements,pins,admissions)
    raw=core.encoded(document);output.write(root/'SOURCE_DIFF_REVIEW.json',raw)
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(inputs=pins,owner=owner,independent_restores=True)))
    if args.review_only:
        output.write(root/'SOURCE_CLOSED.json',core.encoded(dict(owner=owner,source_review_sha256=core.sha(raw),
            actual_package_built=False,native_action=False,closed_unix=time.time())))
        print(core.encoded(dict(output=str(root),source_review_sha256=core.sha(raw),actual_package_built=False)).decode());return
    if args.review_manifest is None or args.review_sha256 is None or not args.reviewer:
        raise ValueError('Exact root-reviewed source manifest/SHA/reviewer required before build')
    approved=core.read(args.review_manifest)
    if core.sha(approved)!=args.review_sha256 or core.strict(approved)!=document:
        raise ValueError('Approved exact startup source inventory differs')
    configure35(helper,helper_raw,core,tools,output,dict(parent=parent,pins=pins,document=document,
        sha256=args.review_sha256,admissions=admissions))
    main_node=next(node for node in ast.parse(core_raw).body if isinstance(node,ast.FunctionDef) and node.name=='main')
    names=[node for node in ast.walk(main_node) if isinstance(node,ast.Constant) and node.value=='field-runtime-v29-build-17-prepared.tar.gz']
    if len(names)!=1:raise ValueError('One immutable core archive basename boundary required')
    names[0].value='field-runtime-v29-build-35-prepared.tar.gz'
    exec(compile(ast.fix_missing_locations(ast.Module(body=[main_node],type_ignores=[])),
        '<immutable-core-main-with-build35-basename>','exec'),core.__dict__)
    core.bootstrap=lambda parent:output
    sys.argv=[str(Path(__file__)),'--base',str(BASE),'--base-manifest-sha256',BASE_SHA,'--reviewer',args.reviewer]
    for name in REPLACEMENTS:sys.argv.extend(['--replacement',name+'='+str(ORIGINS[name])])
    core.main()


if __name__=='__main__':main()
