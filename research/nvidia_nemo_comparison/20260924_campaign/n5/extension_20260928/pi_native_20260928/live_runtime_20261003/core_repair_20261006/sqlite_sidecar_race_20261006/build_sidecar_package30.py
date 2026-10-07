"""Review/build immutable build30 from exact build29. README_SIDECAR_PACKAGE30.md.

Host CPU14 only. No SSH, installed runtime import, models, data or activation.
"""
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

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE = PRIVATE/'audit-preparation/core-package-v1-389154acb3e04317b614c4311bb6de02/package'
BASE_SHA = '331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b'
CORE = HERE.parent.parent/'ui_restore_20261004/build_classic_package.py'
CORE_SHA = 'bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5'
OLD_TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-29'
NEW_TARGET = OLD_TARGET[:-2]+'30'
REPLACEMENTS = ('storage_support.py','README_SQLITE_SIDECAR_RACE.md')
HOST_TEST = PRIVATE/'audit-preparation/core-sidecar-host-20261006-5e647c63cb7440a7a575db2e3e0ee92a'
HOST_PID = 26244
HOST_FILETIME = 134357830840231905
RAW_REFERENCE_FILES = ('RAW_QUALIFICATION_PROOF.json','RAW_QUALIFICATION_MIRROR_MANIFEST.json',
                       'RAW_QUALIFICATION_MIRROR_COMPLETE.json','RAW_QUALIFICATION_JOB.json')
RAW_SOURCE_SHA = '84f40eb404049164ec7efdaf27668e0a54044b5a874323f779237148e75768bf'
ENTRIES = ('native_scope.py','launcher.py','worker.py')


def bootstrap():
    if os.name != 'nt':
        raise RuntimeError('Windows host package preparation only')
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    handle = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(handle,1<<14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    parent = PRIVATE/'audit-preparation'
    if parent.resolve(strict=True) != parent:
        raise ValueError('Exact existing private preparation parent required')
    root = parent/('sidecar-package30-'+uuid.uuid4().hex)
    root.mkdir(exist_ok=False)
    owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
                 affinity_mask=16384,creation_filetime=stamps[0].value,
                 create_time=(stamps[0].value-116444736000000000)/10000000)
    raw = json.dumps(owner,sort_keys=True).encode()
    path = root/'REGISTERED_OWNER.json'
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short early registered owner write')
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('Early registered owner readback differs')
    return root,owner


def function_inventory(raw):
    """Name every nested function/method, including closures under conditionals."""
    result = {}
    def walk(node,prefix=''):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            key = prefix+node.name
            if key in result:
                raise ValueError('Ambiguous definition inventory: '+key)
            if not isinstance(node,ast.ClassDef):
                result[key] = dict(line=node.lineno,
                    ast_sha256=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest())
            prefix = key+'.'
        for child in ast.iter_child_nodes(node):
            walk(child,prefix)
    walk(ast.parse(raw))
    return result


def ast_diff(before,after):
    old = function_inventory(before) if before is not None else {}
    new = function_inventory(after)
    changed = [name for name in sorted(set(old)&set(new)) if old[name]['ast_sha256'] != new[name]['ast_sha256']]
    def module_scope(raw):
        if raw is None:
            return None
        tree = ast.parse(raw)
        class WithoutFunctions(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                return None
            def visit_AsyncFunctionDef(self,node):
                return None
            def visit_ClassDef(self,node):
                self.generic_visit(node)
                if not node.body:
                    node.body = [ast.Pass()]
                return node
        tree = WithoutFunctions().visit(tree)
        return hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()
    return dict(changed=changed,added=sorted(set(new)-set(old)),removed=sorted(set(old)-set(new)),
                before=old,after=new,before_module_scope_ast_sha256=module_scope(before),
                after_module_scope_ast_sha256=module_scope(after),
                module_scope_changed=module_scope(before)!=module_scope(after))


def imports(raw):
    names = set()
    for node in ast.walk(ast.parse(raw)):
        if isinstance(node,ast.Import):
            names.update(value.name for value in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
        elif (isinstance(node,ast.Call) and node.args and isinstance(node.args[0],ast.Constant)
              and isinstance(node.args[0].value,str)
              and (isinstance(node.func,ast.Attribute) and node.func.attr == 'import_module'
                   or isinstance(node.func,ast.Name) and node.func.id == '__import__')):
            names.add(node.args[0].value)
    return names


def import_closure(files):
    modules = {name[:-3].replace('/','.') : name for name in files if name.endswith('.py')}
    reached = set()
    pending = list(ENTRIES)
    edges = {}
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        local = sorted({modules[module] for module in imports(files[name]) if module in modules})
        edges[name] = local
        pending.extend(local)
    required = {name for name in REPLACEMENTS if name.endswith('.py')}
    if required-set(reached):
        raise ValueError('Replacement helper not reachable from native entrypoints: '+repr(sorted(required-set(reached))))
    return dict(entries=list(ENTRIES),required_replacements=sorted(required),
                reachable_replacements=sorted(required&reached),local_edges=edges,
                static_only=True,external_dependencies_and_dynamic_model_graph_not_imported=True)


def source_review(core,parent,before,replacements,pins):
    if set(replacements) != set(REPLACEMENTS):
        raise ValueError('Complete explicit candidate replacement set required')
    runtime = {name:raw for name,raw in replacements.items() if name.endswith('.py')}
    inventory = {}
    for name,raw in runtime.items():
        compile(ast.parse(raw,filename=name),name,'exec')
        inventory[name] = ast_diff(before.get(name),raw)
    effective = dict(before,**replacements)
    return dict(schema='just-peachy.sqlite-sidecar-package-source-review.v1',
                parent_target=OLD_TARGET,target=NEW_TARGET,parent_manifest_sha256=BASE_SHA,
                packaging_core_sha256=CORE_SHA,parent_candidate_content_sha256=parent['candidate_content_sha256'],
                source_pins=pins,replacement_names=list(REPLACEMENTS),
                replacement_pins={name:dict(bytes=len(raw),sha256=core.sha(raw)) for name,raw in replacements.items()},
                ast_inventory=inventory,import_closure=import_closure(effective),
                packaging_core_adaptations=dict(
                    derive_exact_paired_frontend_condition_replaced_with_complete_two_file_set=True,
                    main_exact_archive_basename_changed_to_build30=True,
                    immutable_pinned_core_source_edited=False,
                    inventory_output_archive_and_restore_validators_reused=True),
                constraints=dict(models_changed=False,galleries_changed=False,raw_source_changed=False,
                    raw_proof_bytes_changed=False,user_data_location_changed=False,
                    backend_descriptors_changed=False,physical_storage_guards_retained=True,
                    capacity_and_logical_quota_policy_changed=False,
                    sqlite_sidecar_inspection_only=True,one_readonly_recheck=True,
                    main_anomalies_and_hardlinks_still_rejected=True,
                    original_native37_stat_facts_unavailable=True,native_race_proven=False,
                    native_qualification_pending=True,native_measurements_relabelled=False,
                    ordinary_selection_count=246,optional_refiner_admissions_reused=False))


def configure_derive(core,output,review):
    core.ALLOWED_REPLACEMENTS = set(REPLACEMENTS)
    def validate(before,replacements):
        actual = source_review(core,review['parent'],before,replacements,review['source_pins'])
        if actual != review['document']:
            raise ValueError('Reviewed source/AST/import inventory changed')
        return actual['ast_inventory']
    core.validate_repair_scope = validate
    # The pinned historical core required paired frontend replacements. Replace
    # exactly that one AST condition with this narrower complete two-file set.
    tree = ast.parse(CORE.read_bytes())
    derive_node = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name == 'derive')
    changed = 0
    for node in ast.walk(derive_node):
        if (isinstance(node,ast.If) and any(isinstance(value,ast.Constant) and
                value.value == 'Explicit paired launcher and new classic frontend replacements required'
                for value in ast.walk(node))):
            expected = ast.parse("not {'launcher.py','classic_frontend.py'}<=set(replacements)",mode='eval').body
            if ast.dump(node.test,include_attributes=False) != ast.dump(expected,include_attributes=False):
                raise ValueError('Historical paired-frontend admission condition changed')
            node.test = ast.parse("set(replacements) != {'storage_support.py','README_SQLITE_SIDECAR_RACE.md'}",mode='eval').body
            for value in ast.walk(node):
                if isinstance(value,ast.Constant) and value.value == 'Explicit paired launcher and new classic frontend replacements required':
                    value.value = 'Exact SQLite sidecar helper and maintained README replacements required'
            changed += 1
    if changed != 1:
        raise ValueError('Exact single paired-frontend condition substitution required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[derive_node],type_ignores=[])),
                 '<historical-package-derive-with-exact-sidecar-replacement-set>','exec'),core.__dict__)
    original = core.derive
    def derive(parent,files,replacements,reviewer):
        prior = dict(files)
        manifest,files,provenance = original(parent,files,replacements,reviewer)
        binding = core.strict(files['BINDING.json'])
        acceptance = core.strict(files['PRODUCTION_ACCEPTANCE.json'])
        raw_evidence = dict(binding['raw_qualification_evidence'])
        if raw_evidence.get('evidence') != OLD_TARGET+'/RAW_QUALIFICATION_PROOF.json':
            raise ValueError('Exact parent raw proof binding location required')
        raw_evidence['evidence'] = NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json'
        binding['raw_qualification_evidence'] = raw_evidence
        if core.sha(files['installed_source.py']) != RAW_SOURCE_SHA:
            raise ValueError('Previously qualified physical source changed')
        for name in RAW_REFERENCE_FILES:
            if files[name] != prior[name]:
                raise ValueError('Immutable raw reference bytes changed: '+name)
        acceptance['limitations'] = [
            'Build30 changes only the SQLite sidecar inspection helper and its maintained README over immutable build29. Fresh native qualification of changed content remains pending.',
            'The 246 ordinary selections are admitted for guarded validation; this does not establish all combinations, sustainable hour-long realtime operation or identity/transcription accuracy.',
            'Native recognition-segment final and utterance/group final are distinct. Only a supported spoken boundary may finish a punctuation group. Partial-word display revisions preserve historical recognition evidence.',
            'Identity validity, backend/gallery provenance, roster/mode eligibility and current presentation revision are checked independently. Unavailable or unsupported evidence remains Unknown.',
            'Build29 capacity and logical-quota policy is retained: physical free-space floors, memory/queue bounds, ownership and bounded transactions remain; historical corpus ceilings remain removed.',
            'Only a regular zero-link named SQLite sidecar receives one read-only lstat recheck. Missing names or validated different ordinary single-link inodes can pass; main anomalies, hardlinks, symlinks, reparse points, nonregular files and ambiguous rechecks fail.',
            'Native29 check37 lacked the offending suffix and stat snapshot. Journal turnover is a plausible explanation, not a proven original nlink0 observation; passing frozen29 checks cannot qualify changed build30.',
            'Explicit Discard/Delete uses a durable scoped intent and startup recovery. Retained data requires a separately verified consistent backup before native writable recovery or activation.',
            'Launching/changing a Mode cannot start capture. Physical layout, model variants, backend descriptors, galleries, calibration, raw source/proof and external data-root location are preserved.',
            'Raw qualification proof bytes are unchanged; only its package-local binding path moves. No historical native measurement or optional parallel-refiner admission is reauthorized.']
        provenance.update(schema='just-peachy.sqlite-sidecar-runtime-repair.v1',
            resource_storage_policy_changed=True,sqlite_path_inspection_changed=True,
            capacity_and_logical_quota_policy_changed=False,parent_build29_capacity_policy_retained=True,
            finite_capacity_driven_sqlite_file_ceiling_retained=True,
            physical_resource_guards_retained=True,physical_storage_reserve_retained=True,
            raw_source_and_qualification_bytes_unchanged=True,raw_qualification_repeated=False,
            raw_evidence_path_translation_only=True,source_review_sha256=review['sha256'],
            static_import_closure=review['document']['import_closure'],
            focused_host_test_receipt=str(HOST_TEST),focused_host_tests=17,
            focused_host_result_sha256=review['source_pins']['FOCUSED_HOST_RESULT.json']['sha256'],
            focused_host_exact_owner_closed=True,original_native37_failure_retained=True,
            original_native37_race_proven=False,maximum_sidecar_rechecks=1,
            native_measurement_relabelled=False,native_qualification_pending=True,
            ordinary_application_modes=11,visible_backend_combinations=6,
            immutable_old_galleries_changed=False,mode_backend_independent=True)
        files['REPAIR_PROVENANCE.json'] = files['REPAIR_PROVENANCE.restore.json'] = core.encoded(provenance)
        content = core.sha(core.encoded(core.rows({name:raw for name,raw in files.items()
            if name not in core.CONTENT_EXCLUDED and not name.startswith('source-backups/')})))
        acceptance['candidate_content_sha256'] = binding['candidate_content_sha256'] = content
        acceptance_raw = core.encoded(acceptance)
        binding['production_acceptance_sha256'] = core.sha(acceptance_raw)
        files['PRODUCTION_ACCEPTANCE.json'] = acceptance_raw
        files['BINDING.json'] = core.encoded(binding)
        manifest.update(candidate_content_sha256=content,files=core.rows(files))
        allowed = set(REPLACEMENTS)|{'BINDING.json','PRODUCTION_ACCEPTANCE.json',
                    'REPAIR_PROVENANCE.json','REPAIR_PROVENANCE.restore.json'}
        for name in REPLACEMENTS:
            if name.endswith('.py'):
                allowed.update({'source-backups/'+name+'.backup','source-backups/'+name+'.restore'})
        additions = set(files)-set(prior)
        removals = set(prior)-set(files)
        differences = {name for name in set(files)&set(prior) if files[name] != prior[name]}
        expected_additions = allowed-set(prior)
        if removals or additions != expected_additions or differences-allowed:
            raise ValueError('Unapproved package member changes: '+repr((removals,additions^expected_additions,differences-allowed)))
        old_binding = core.strict(prior['BINDING.json'])
        protected = set(old_binding)-{'target','reference_code','raw_factory_path','profiles',
            'candidate_content_sha256','production_acceptance_sha256','native_qualified','admission_sha256',
            'optional_refiner_admissions','optional_refiner_admission','raw_qualification_evidence'}
        if any(binding[key] != old_binding[key] for key in protected):
            raise ValueError('Untouched operational binding pin changed')
        expected_raw = dict(old_binding['raw_qualification_evidence'],evidence=NEW_TARGET+'/RAW_QUALIFICATION_PROOF.json')
        if binding['raw_qualification_evidence'] != expected_raw or binding['storage_policy'] != old_binding['storage_policy']:
            raise ValueError('Raw proof changed outside exact path or physical policy fields changed')
        if acceptance['limits'] != core.strict(prior['PRODUCTION_ACCEPTANCE.json'])['limits']:
            raise ValueError('Physical acceptance resource limits changed')
        output.write(output.root/'BUILD29_MEMBER_PRESERVATION.json',core.encoded(dict(
            parent_manifest_sha256=BASE_SHA,allowed_changed_members=sorted(allowed),
            actual_changed_members=sorted(differences),added_members=sorted(additions),removed_members=[],
            unchanged_parent_members=len(prior)-len(differences),
            all_other_runtime_assets_models_profiles_raw_proof_bytes_identical=True,
            physical_binding_and_acceptance_policies_preserved=True,
            package_manifest_is_separate_derived_control=True)))
        if len(files)+1 > 512 or sum(map(len,files.values())) > core.MAX_PACKAGE:
            raise ValueError('Preserved package count/extent bounds exceeded')
        return manifest,files,provenance
    core.derive = derive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-only',action='store_true',help='Emit source/AST/import inventory; do not build a package')
    parser.add_argument('--review-manifest',type=Path)
    parser.add_argument('--review-sha256')
    parser.add_argument('--reviewer')
    args = parser.parse_args()
    root,owner = bootstrap()  # Exact owner registered before package/project reads.
    sys.dont_write_bytecode = True
    core_raw = CORE.read_bytes()
    if hashlib.sha256(core_raw).hexdigest() != CORE_SHA:
        raise ValueError('Exact reviewed packaging core required')
    spec = importlib.util.spec_from_file_location('core_build30_packaging',CORE)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    core.BASE,core.BASE_SHA = BASE,BASE_SHA
    core.OLD_TARGET,core.NEW_TARGET = OLD_TARGET,NEW_TARGET
    output = core.Output(root)
    output.bytes = (root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,
        maximum_seconds=600,issued_unix=time.time(),target=NEW_TARGET,native_action=False,
        review_only=args.review_only,archive_maximum_bytes=core.MAX_ARCHIVE)))
    inputs = {name:HERE/name for name in REPLACEMENTS}
    inputs.update({'build_sidecar_package30.py':Path(__file__),
                   'README_SIDECAR_PACKAGE30.md':HERE/'README_SIDECAR_PACKAGE30.md',
                   'PACKAGING_CORE.py':CORE,
                   'FOCUSED_TEST_FIXTURE.py':HERE/'test_sqlite_sidecar_race.py',
                   'FOCUSED_TEST_RUNNER.py':HERE/'run_host_sidecar_checks.py',
                   'FOCUSED_HOST_RESULT.json':HOST_TEST/'RESULT.json',
                   'FOCUSED_HOST_CLOSED.json':HOST_TEST/'HOST_CLOSED.json',
                   'FOCUSED_HOST_SOURCE_CLOSED.json':HOST_TEST/'SOURCE_CLOSED.json'})
    pins = {}
    replacements = {}
    for name,path in sorted(inputs.items()):
        raw = core.read(path)
        for suffix in ('backup','restore'):
            output.write(root/'prepared-source'/suffix/name,raw)
        if core.read(path) != raw:
            raise ValueError('Source changed during independent source closure')
        pins[name] = dict(path=str(path),bytes=len(raw),sha256=core.sha(raw))
        if name in REPLACEMENTS:
            replacements[name] = raw
    host_result = core.strict(core.read(inputs['FOCUSED_HOST_RESULT.json']))
    host_closed = core.strict(core.read(inputs['FOCUSED_HOST_CLOSED.json']))
    host_sources = core.strict(core.read(inputs['FOCUSED_HOST_SOURCE_CLOSED.json']))
    if (host_result.get('status') != 'PASS' or host_result.get('tests_run') != 17 or
            any(host_result.get(key) != 0 for key in ('failures','errors','skipped')) or
            host_result.get('fixture_closed') is not True or host_result.get('source_unchanged') is not True or
            host_result.get('owner',{}).get('pid') != HOST_PID or
            host_result.get('owner',{}).get('creation_filetime') != HOST_FILETIME or
            host_closed.get('pid') != HOST_PID or host_closed.get('creation_filetime') != HOST_FILETIME or
            host_closed.get('natural_exit') != 0 or host_closed.get('exact_owner_absent') is not True):
        raise ValueError('Exact successful focused host test and independent closure required')
    source_pins = {Path(pin['path']).name:pin for pin in host_sources['pins']
                   if Path(pin['path']).parent == HERE}
    for current,tested in (('storage_support.py','storage_support.py'),
                           ('FOCUSED_TEST_FIXTURE.py','test_sqlite_sidecar_race.py'),
                           ('FOCUSED_TEST_RUNNER.py','run_host_sidecar_checks.py')):
        if pins[current]['sha256'] != source_pins[tested]['sha256']:
            raise ValueError('Runtime or focused fixture source differs from tested bytes')
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),
        inputs=pins,independent_restores=True,owner=owner)))
    parent,before = core.inventory(BASE)
    document = source_review(core,parent,before,replacements,pins)
    review_raw = core.encoded(document)
    output.write(root/'SOURCE_DIFF_REVIEW.json',review_raw)
    if args.review_only:
        output.write(root/'SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),owner=owner,
            source_review_sha256=core.sha(review_raw),actual_package_built=False,native_action=False)))
        print(json.dumps(dict(output=str(root),source_review=str(root/'SOURCE_DIFF_REVIEW.json'),
            source_review_sha256=core.sha(review_raw),actual_package_built=False,native_action=False)))
        return
    if args.review_manifest is None or args.review_sha256 is None or not args.reviewer:
        raise ValueError('Build requires the exact root-reviewed source manifest, its SHA256 and reviewer')
    approved_raw = core.read(args.review_manifest)
    if core.sha(approved_raw) != args.review_sha256 or core.strict(approved_raw) != document:
        raise ValueError('Reviewed source manifest differs from current exact source/AST/import inventory')
    configure_derive(core,output,dict(parent=parent,source_pins=pins,document=document,sha256=args.review_sha256))
    tree = ast.parse(core_raw)
    main_node = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name == 'main')
    changed = 0
    for node in ast.walk(main_node):
        if isinstance(node,ast.Constant) and node.value == 'field-runtime-v29-build-17-prepared.tar.gz':
            node.value = 'field-runtime-v29-build-30-prepared.tar.gz'
            changed += 1
    if changed != 1:
        raise ValueError('Exact single original archive basename substitution required')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[main_node],type_ignores=[])),
                 '<unchanged-package-main-with-build30-basename>','exec'),core.__dict__)
    core.bootstrap = lambda parent:output
    sys.argv = [str(Path(__file__)),'--base',str(BASE),'--base-manifest-sha256',BASE_SHA,
                '--reviewer',args.reviewer]
    for name in REPLACEMENTS:
        sys.argv.extend(['--replacement',name+'='+str(HERE/name)])
    core.main()


if __name__ == '__main__':
    main()
