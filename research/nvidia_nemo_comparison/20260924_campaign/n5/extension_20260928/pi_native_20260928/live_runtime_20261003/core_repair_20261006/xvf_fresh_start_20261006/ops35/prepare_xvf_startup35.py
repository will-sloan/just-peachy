"""Materialize exact reviewed build35 operator derivatives; README_XVF_STARTUP35_OPS.md.

Narrow derivative of frozen ops34, retaining its exact older helper parents.
Host-only source preparation. This module never dispatches native actions, opens
SQLite, imports a runtime package, changes a desktop entry, or starts a model.
"""
import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import time
import uuid

HERE = Path(__file__).resolve().parent
D = HERE.parent.parent
S = D.parent/'stabilization_20261005'
TEMPLATE31 = D/'caption_snapshot_20261006/ops31/prepare_caption31.py'
TEMPLATE31_SHA = 'f0ffe35c4360447b0039e063e79e72bd8ac274ff5ce2e2e7afb219230e240cef'
PARENT_OPS32 = D/'capacity_gallery_20261006/ops32/prepare_gallery32.py'
PARENT_OPS32_SHA = '308f3f5333f7c12018c6e3134a6a47002318f803ad43effc9cb4aac59ce22408'
PARENT_OPS33 = D/'event_writer_streaming_20261006/ops33/prepare_event33_v2.py'
PARENT_OPS33_SHA = 'b9bdd602924fbc87b682e62243a026018594822d4a7ff4c92b24d087e1b4412f'
PARENT_OPS34 = D/'asr_metadata_cache_20261006/ops34/prepare_core_performance34.py'
PARENT_OPS34_SHA = 'b97c2acee883832235a77b1ff03b054ce36e7f20b9ca18db82f3c334bfbf74a4'
Q = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
CAMPAIGN = '/home/peachyprototype/JustPeachy/research/nemotron-20260928'
DATA = '/home/peachyprototype/JustPeachy/data/runtime-v29'
PIN30 = 'b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569'
PIN34 = 'fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802'
MODEL_POLICY = dict(previous_worker_bytes=768*1024**2, candidate_worker_bytes=1024**3,
    frontend_soft_bytes=256*1024**2, candidate_inside_model_hard_bytes=1024**3,
    outside_metadata_bytes=128*1024**2, other_qualification_parent_bytes=768*1024**2,
    candidate_recording_parent_bytes=1024**3,
    recording_parent_scope='full_app_hour or modern classic_driver.py live/saved redimnet/titanet',
    physical_ram_floor_and_disk_reserves_unchanged=True, source_constants_are_authority=True,
    binding_and_acceptance_limits_schema_unchanged=True, native_qualification_pending=True)
CURRENT_BOOT = 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
BACKUP14_PINS = dict(
    complete='9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e',
    result='1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879',
    census='509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263')
PIN29 = '331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b'
PIN28 = 'e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b'
PRIOR_RESULT_SHA = '0e2d1d0fa81e41fac84d8548ccf14904ff945905c4ede51613d2fccdb685973b'
PRIOR_DESKTOP_SHA = 'ef76ff090876de65491fa3aa845e2d4843228203c0e94c8ca921357d926d16d2'
AUTOSTART_SHA = '8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206'
PARENTS = {
    'sqlite_sidecar_race_20261006/prepare_sidecar_stage30_v2.py': '8ff6684b1de014d3b1c0be08a63c1393ed422b8e5b12e41eb21d7c4c43c53aa6',
    'prepare_core_native_validation_v3.py': '6beb178c78005e385ce0b64e1129843e97921709e9cedf7645d4833a935642bd',
    'prepare_core_endurance30.py': '22e0fb7c0e068dae8e424663cd5270649acb694f8bc6364a7a82c060cc964a57',
    'launch_core_full_app_hour30.py': 'b31b3a0bbdbf8746c14fedb6d7934dd25941cce7b32862498f74329f92d0cec2',
    'review_core_full_app_hour30.py': '6a8f883b3a79114afa1db3f3119b89faa166e4ac11226908794a1edc369849da',
    'prepare_core_activation30.py': 'd44f1ce4f6a68412ee8299046eaa8b2eac672bac2558d15713a39ffc714f3a7f',
    'activate_core_desktop_action30.py': 'c431d7b54441ed08a2a4fe1f3db630fcd2c39c6e1aaf5f0beec0e04f935cc968',
    'stage_c24_endurance_input30.py': '5ebb8550edfc83298eb21fa747e8b1aefaa50bffe6706731c085905e95bcf332',
    'core_database_recovery.py': '1b1f8127737ea47c77978e007c0c82f87e3ab4851e2ae15b013ba4a28a04adbc',
    'native_core_live_check_v2.py': '5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e',
    'native_core_saved_check_v2.py': '01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237',
    'extract_core_job31.py': 'e95de25c90eec8b74b8e847960f26014df4bb0962613a93043dbe7dfec1c88ec',
}
NAMES = {
    'sqlite_sidecar_race_20261006/prepare_sidecar_stage30_v2.py': 'prepare_core_stage35.py',
    'prepare_core_native_validation_v3.py': 'prepare_core_native_validation_v35.py',
    'prepare_core_endurance30.py': 'prepare_core_endurance35.py',
    'launch_core_full_app_hour30.py': 'launch_core_full_app_hour35.py',
    'review_core_full_app_hour30.py': 'review_core_full_app_hour35.py',
    'prepare_core_activation30.py': 'prepare_core_activation35.py',
    'activate_core_desktop_action30.py': 'activate_core_desktop_action35.py',
    'stage_c24_endurance_input30.py': 'stage_c24_endurance_input35.py',
    'extract_core_job31.py': 'extract_core_job35.py',
}
HOUR_LAUNCHER_ENTRYPOINT = '''def run_exact_hour_launcher(argv, package):
 if SETTINGS['kind']!='full_app_hour' or argv[0]!=str(package/'launcher.py'):
  raise ValueError('Private nullable CLI adapter admits only the exact hour launcher')
 expected={'--binding':str(package/'BINDING.json'),'--data-root':str(out/'data'),
  '--unit':SETTINGS['unit'],'--unit-ownership':str(out/'UNIT_OWNERSHIP.json'),
  '--input-source':'saved','--maximum-session-seconds':'3600',
  '--max-drain-seconds':'600','--max-backlog-seconds':'None','--repeat-input-seconds':'3600'}
 for flag,value in expected.items():
  if argv.count(flag)!=1 or argv.index(flag)+1>=len(argv) or argv[argv.index(flag)+1]!=value:
   raise ValueError('Exact experimental hour CLI values required')
 if any(argv.count(flag)!=1 for flag in ('--headless','--keep-processed','--developer-soak')):
  raise ValueError('Exact headless saved developer hour flags required')
 if any(flag in argv for flag in ('--list-profiles','--request-stop','--optional-d1-refiner')):
  raise ValueError('This private launcher adapter does not admit alternate CLI paths')
 path=package/'launcher.py';source=path.read_bytes()
 source_sha='PENDING_ACTUAL35_LAUNCHER_PIN'
 if hashlib.sha256(source).hexdigest()!=source_sha:
  raise ValueError('Exact HOST19 tested and sealed build35 launcher source required')
 tree=ast.parse(source)
 functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main']
 if len(functions)!=1:raise ValueError('One exact source-bound launcher main required')
 main=functions[0];original=ast.dump(main,include_attributes=False)
 original_call=ast.parse('SessionPolicy(args.maximum_session_seconds,args.developer_soak,max_drain_seconds=args.max_drain_seconds,max_backlog_seconds=args.max_backlog_seconds)',mode='eval').body
 nullable=ast.parse("lambda value: None if value=='None' else int(value)",mode='eval').body
 def targets(function):
  arguments=[node for node in ast.walk(function) if isinstance(node,ast.Call)
   and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument'
   and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=='--max-backlog-seconds']
  policies=[node for node in ast.walk(function) if isinstance(node,ast.Call)
   and isinstance(node.func,ast.Name) and node.func.id=='SessionPolicy']
  if len(arguments)!=1 or len(policies)!=1:raise ValueError('Exact nullable argument and policy construction required')
  types=[keyword for keyword in arguments[0].keywords if keyword.arg=='type']
  if len(types)!=1:raise ValueError('One exact backlog parser type required')
  return types[0],policies[0]
 keyword,policy=targets(main)
 if ast.dump(keyword.value,include_attributes=False)!=ast.dump(ast.Name(id='int',ctx=ast.Load()),include_attributes=False) or ast.dump(policy,include_attributes=False)!=ast.dump(original_call,include_attributes=False):
  raise ValueError('Original tested launcher parser/policy AST differs')
 keyword.value=nullable;policy.keywords.append(ast.keyword(arg='manual_stop',value=ast.Constant(value=True)))
 reverse=copy.deepcopy(main);reverse_type,reverse_policy=targets(reverse)
 reverse_type.value=ast.Name(id='int',ctx=ast.Load());reverse_policy.keywords.pop()
 if ast.dump(reverse,include_attributes=False)!=original:
  raise ValueError('Private nullable/manual launcher reverse AST differs')
 name='verified_hour_launcher_cli'
 if name in sys.modules:raise ValueError('Fresh private hour launcher namespace required')
 spec=importlib.util.spec_from_file_location(name,path)
 if spec is None or spec.origin!=str(path):raise ValueError('Exact ordinary launcher source origin required')
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
 if module.__file__!=str(path) or module.__spec__.origin!=str(path) or hashlib.sha256(path.read_bytes()).hexdigest()!=source_sha:
  raise ValueError('Private launcher origin/source changed during load')
 exec(compile(ast.fix_missing_locations(ast.Module(body=[main],type_ignores=[])),str(path),'exec'),module.__dict__)
 put('HOUR_LAUNCHER_POLICY_ADAPTER.json',dict(source_sha256=source_sha,owner=owner,
  nullable_backlog_argument_only=True,manual_stop_keyword_only=True,reverse_main_ast_exact=True,
  policy=dict(maximum_session_seconds=3600,developer_soak=True,max_drain_seconds=600,
   max_backlog_seconds=None,manual_stop=True),sealed_runtime_changed=False,
  normal_gui_and_other_cli_paths_admitted=False,real_time_qualification_claimed=False))
 raise SystemExit(module.main())
'''
HOUR_POLICY_ADAPTER = '''def bind_exact_hour_policy(namespace, helper_path):
    """Bind one private hour expectation; the sealed shared source stays exact."""
    raw = helper_path.read_bytes()
    source_sha = '307912b6d5fecace57d26dc40da8fe8d0a1d606dbd1c2fcfccc637136023a25d'
    if hashlib.sha256(raw).hexdigest() != source_sha:
        raise ValueError('Exact retained build33/34/35 shared envelope source required')
    tree = ast.parse(raw)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'budget_plan']
    if len(functions) != 1:
        raise ValueError('One exact shared budget function required')
    plan = functions[0]
    original = ast.dump(plan, include_attributes=False)
    branch_test = ast.parse("kind=='full_app_hour'", mode='eval').body
    old_call = ast.parse('profiles.SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=120)', mode='eval').body
    new_call = ast.parse('profiles.SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=None,manual_stop=True)', mode='eval').body
    def assignment(function, expected):
        branches = [node for node in function.body if isinstance(node, ast.If)
                    and ast.dump(node.test, include_attributes=False) == ast.dump(branch_test, include_attributes=False)]
        if len(branches) != 1:
            raise ValueError('One exact full_app_hour admission branch required')
        nodes = [node for node in branches[0].body if isinstance(node, ast.Assign)
                 and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id == 'expected']
        if len(nodes) != 1 or ast.dump(nodes[0].value, include_attributes=False) != ast.dump(expected, include_attributes=False):
            raise ValueError('Exact old/new full_app_hour expected policy required')
        return nodes[0]
    assignment(plan, old_call).value = new_call
    reverse = copy.deepcopy(plan)
    assignment(reverse, new_call).value = old_call
    if ast.dump(reverse, include_attributes=False) != original:
        raise ValueError('Private hour policy reverse AST differs')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[plan], type_ignores=[])),
                 str(helper_path), 'exec'), namespace)
    namespace['_hour_policy_adapter_proof'] = dict(shared_source_sha256=source_sha,
        full_app_hour_expected_policy_only=True,reverse_ast_exact=True,
        max_backlog_seconds=None,manual_stop=True,developer_soak=True,
        maximum_session_seconds=3600,max_drain_seconds=600,
        policy_deadline_seconds=4380,unit_runtime_seconds=4680,
        other_branches_guards_reservations_unchanged=True)
    original_wrapper = namespace['wrapper_source']
    def hour_wrapper(settings):
        if settings['kind'] != 'full_app_hour':
            raise ValueError('Private hour wrapper source is restricted to full_app_hour')
        source = original_wrapper(settings)
        imported = 'from pathlib import Path\\n'
        invocation = " try:runpy.run_path(argv[0],run_name='__main__');code=0"
        if source.count(imported) != 1 or source.count(invocation) != 1:
            raise ValueError('Exact original shared wrapper insertion/run boundary required')
        source = source.replace(imported, imported+'import ast,copy\\n'+HOUR_LAUNCHER_ENTRYPOINT+'\\n')
        source = source.replace(invocation, ' try:run_exact_hour_launcher(argv,package);code=0')
        compile(source, '<private-hour35-wrapper>', 'exec')
        return source
    namespace['wrapper_source'] = hour_wrapper
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def regular(path, maximum):
    path = Path(path)
    before = path.stat()
    if (path.is_symlink() or path.resolve(strict=True) != path
            or any(parent.is_symlink() for parent in path.parents)
            or not path.is_file() or before.st_nlink != 1 or before.st_size > maximum):
        raise ValueError('Canonical bounded single-link ordinary input required')
    return path, before


def read(path, maximum=262144):
    path, before = regular(path, maximum)
    raw = path.read_bytes()
    after = path.stat()
    if identity(before) != identity(after) or len(raw) != before.st_size:
        raise ValueError('Input changed during read')
    return raw


def identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def file_sha(path, maximum):
    path, before = regular(path, maximum)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    if identity(before) != identity(path.stat()):
        raise ValueError('Input changed during streamed hash')
    return digest.hexdigest()


def bootstrap():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    handle = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(handle, 16384):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = Q/'audit-preparation'/('xvf-startup35-ops-'+uuid.uuid4().hex)
    root.mkdir(exist_ok=False)
    owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
                 affinity_mask=16384, creation_filetime=stamps[0].value,
                 create_time=(stamps[0].value-116444736000000000)/1e7)
    raw = encoded(owner)
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short early-owner write')
        stream.flush()
        os.fsync(stream.fileno())
    if read(root/'REGISTERED_OWNER.json') != raw:
        raise OSError('Early owner independent readback differs')
    return root, owner


class Writer:
    def __init__(self, root):
        self.root = root
        self.started = time.monotonic()
        self.bytes = (root/'REGISTERED_OWNER.json').stat().st_size

    def put(self, name, raw):
        if re.fullmatch(r'[A-Za-z0-9_.-]+', name) is None:
            raise ValueError('Fixed ordinary output basename required')
        if self.bytes+len(raw) > 8*1024**2 or time.monotonic()-self.started > 600:
            raise OSError('Existing8MiB/600s host preparation scope exceeded')
        for drive, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
            if shutil.disk_usage(drive).free < floor+8*1024**2:
                raise OSError('Existing host physical free-space floor')
        with (self.root/name).open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short preparation write')
            stream.flush()
            os.fsync(stream.fileno())
        self.bytes += len(raw)
        if read(self.root/name, 8*1024**2) != raw:
            raise OSError('Independent preparation readback differs')

    def triple(self, name, raw):
        for suffix in ('', '.backup', '.restore'):
            self.put(name+suffix, raw)


def package_inventory(package, pin):
    raw = read(package/'PACKAGE_MANIFEST.json')
    if sha(raw) != pin:
        raise ValueError('Actual package manifest SHA differs')
    manifest = strict(raw)
    rows = manifest.get('files')
    if (manifest.get('schema') != 'just-peachy.v29.package.v1'
            or manifest.get('target') != CAMPAIGN+'/field-runtime-v29-build-35'
            or type(rows) is not list or not 1 <= len(rows) <= 512):
        raise ValueError('Existing bounded build35 manifest required')
    expected = {'PACKAGE_MANIFEST.json'}
    total = 0
    for row in rows:
        name = row.get('path', '')
        rel = PurePosixPath(name)
        size = row.get('bytes')
        pin = row.get('sha256', '')
        if (not name or rel.is_absolute() or '..' in rel.parts or '\\' in name
                or rel.as_posix() != name or name in expected or type(size) is not int or size < 0
                or re.fullmatch('[0-9a-f]{64}', pin) is None):
            raise ValueError('Unique canonical typed package membership required')
        path = package.joinpath(*rel.parts)
        if path.stat().st_size != size or file_sha(path, 16*1024**2) != pin:
            raise ValueError('Complete package member rehash differs')
        expected.add(name)
        total += size
    actual = set()
    for count, path in enumerate(package.rglob('*'), 1):
        if count > 4096 or path.is_symlink():
            raise ValueError('Existing bounded ordinary package tree required')
        if path.is_file():
            actual.add(path.relative_to(package).as_posix())
        elif not path.is_dir():
            raise ValueError('Unsupported package member')
    if actual != expected or total > 16*1024**2:
        raise ValueError('Complete package membership/extent differs')
    return manifest, len(expected)


def binding_inputs(args, writer):
    build = args.build_output
    if (build.parent != Q/'audit-preparation' or build.resolve(strict=True) != build
            or re.fullmatch('startup-package35-[0-9a-f]{32}', build.name) is None):
        raise ValueError('Actual fresh canonical build35 receipt directory required')
    names = ('BUILD_RESULT.json', 'SOURCE_CLOSED.json', 'INDEPENDENT_CLOSURE.json',
             'REGISTERED_OWNER.json', 'BUILD34_MEMBER_PRESERVATION.json', 'SOURCE_DIFF_REVIEW.json')
    raw = {name: read(build/name, 2*1024**2) for name in names}
    result, closed, independent, owner, preservation, review = (strict(raw[name]) for name in names)
    if (sha(raw['SOURCE_DIFF_REVIEW.json']) != args.source_review_sha256
            or sha(raw['INDEPENDENT_CLOSURE.json']) != args.build_closure_sha256
            or result.get('parent_manifest_sha256') != PIN34
            or result.get('manifest_sha256') != args.manifest_sha256
            or result.get('archive_sha256') != args.archive_sha256
            or result.get('candidate_content_sha256') != args.content_sha256
            or result.get('target') != CAMPAIGN+'/field-runtime-v29-build-35'
            or result.get('data_root') != DATA or result.get('installed') is not False
            or result.get('desktop_changed') is not False
            or result.get('source_backups_and_restores_exact') is not True
            or closed.get('scope_closed') is not True or closed.get('native_action') is not False
            or independent.get('schema') != 'just-peachy.core-package35-independent-closure.v1'
            or independent.get('owner') != owner or independent.get('builder_os_process_absent') is not True
            or independent.get('builder_natural_exit_code') != 0
            or independent.get('source_backups_and_independent_restores_exact') is not True
            or independent.get('current_sources_unchanged') is not True
            or independent.get('native_action') is not False
            or independent.get('source_review_sha256') != args.source_review_sha256
            or independent.get('manifest_sha256') != args.manifest_sha256
            or independent.get('archive_sha256') != args.archive_sha256
            or preservation.get('parent_manifest_sha256') != PIN34
            or preservation.get('removed_members') != []
            or preservation.get('all_other_parent_members_byte_identical') is not True
            or preservation.get('binding_and_acceptance_limits_structure_preserved') is not True
            or review.get('schema') != 'just-peachy.xvf-startup-package-source-review.v1'
            or review.get('retained_model_address_space_policy') != MODEL_POLICY
            or review.get('parent_manifest_sha256') != PIN34
            or set(review.get('replacement_names', [])) != {'launcher.py','xvf_readiness_helper.py',
                'README_XVF_FRESH_START.md','classic_frontend.py','README_CLASSIC_STORAGE_COPY35.md'}
            or set(review.get('replacement_pins', {})) != set(review.get('replacement_names', []))
            or review.get('target') != CAMPAIGN+'/field-runtime-v29-build-35'):
        raise ValueError('Exact reviewed, closed build35 and unchanged physical-policy evidence required')
    package = build/'package'
    archive = build/'field-runtime-v29-build-35-prepared.tar.gz'
    if Path(result.get('package', '')) != package or Path(result.get('archive', '')) != archive:
        raise ValueError('Actual authoritative package/archive locations differ')
    manifest, count = package_inventory(package, args.manifest_sha256)
    provenance = strict(read(package/'REPAIR_PROVENANCE.json', 2*1024**2))
    if (provenance.get('schema') != 'just-peachy.xvf-startup-runtime-repair.v1'
            or provenance.get('source_review_sha256') != args.source_review_sha256
            or provenance.get('retained_model_address_space_policy') != MODEL_POLICY
            or provenance.get('model_address_space_policy_changed') is not False
            or provenance.get('physical_ram_disk_and_model_address_space_ceiling_changed') is not False
            or provenance.get('retained_performance_policy') != review.get('retained_performance_policy')
            or type(provenance.get('retained_performance_policy')) is not dict
            or provenance.get('focused_host_tests') != review.get('focused_host_tests')
            or provenance.get('reused_build34_focused_host_tests') != review.get('reused_build34_focused_host_tests')
            or set(provenance.get('reused_build34_focused_host_tests', {})) != {'CACHE','PROJECTION','CAPACITY'}
            or provenance.get('startup_recovery_policy_changed') is not True
            or provenance.get('normal_capture_backlog_and_drain_policy_changed') is not False
            or provenance.get('resource_storage_policy_changed') is not False
            or review.get('focused_host_tests', {}).get('schema') != 'just-peachy.xvf-fresh-start-host.v1'
            or review.get('focused_host_tests', {}).get('tests') != 19
            or review.get('focused_host_tests', {}).get('source_count') != 452
            or review.get('focused_host_tests', {}).get('exact_owner_closed') is not True
            or review.get('frontend_wording_review', {}).get('whole_reverse_text_equal') is not True
            or review.get('frontend_wording_review', {}).get('host19_coverage_claimed') is not False):
        raise ValueError('Exact current35 source/host scope and retained finite model envelope required')
    package_rows={row['path']:row for row in manifest['files']}
    for name,pin in review['replacement_pins'].items():
        row=package_rows.get(name,{})
        if (row.get('bytes'),row.get('sha256'))!=(pin.get('bytes'),pin.get('sha256')):
            raise ValueError('Actual current35 replacement package/source-review binding differs')
    if (manifest.get('candidate_content_sha256') != args.content_sha256
            or file_sha(archive, 2*1024**2) != args.archive_sha256
            or result.get('archive_members_independently_restored') != count
            or independent.get('archive_members_readback') != count
            or independent.get('independent_expanded_restore_exact') is not True
            or independent.get('archive_expanded_bytes') !=
                sum(row['bytes'] for row in manifest['files'])+len(read(package/'PACKAGE_MANIFEST.json'))):
        raise ValueError('Closed complete archive and independent member counts differ')
    for index, name in enumerate(names):
        writer.triple('BUILD_INPUT_%02d.json'%index, raw[name])
    return raw, manifest


def accepted_backup(args, writer):
    backup = args.backup_root
    if (backup.parent != Q or backup.resolve(strict=True) != backup
            or re.fullmatch('production-backup-14-reconcile-[0-9]{2}', backup.name) is None):
        raise ValueError('Explicit accepted backup14 canonical reconciliation required')
    names = ('COMPLETE.json', 'RESULT.json', 'FULL_BACKUP.json', 'JOB.json', 'CENSUS.json', 'MANIFEST.json')
    raw = {name: read(backup/name, 2*1024**2) for name in names}
    complete, result, full, job, census, members = (strict(raw[name]) for name in names)
    number = backup.name.split('-')[2]
    if (sha(raw['COMPLETE.json']) != args.backup_complete_sha256
            or sha(raw['RESULT.json']) != args.backup_result_sha256
            or sha(raw['CENSUS.json']) != args.backup_census_sha256
            or complete.get('kind') != 'COMPLETE'
            or complete.get('backup_scope') != 'selected-release-and-user-data'
            or result.get('status') != 'VERIFIED_CURRENT_RELEASE_BACKUP'
            or complete.get('source_before_after_verified') is not True
            or complete.get('external_asset_pins_verified') is not True
            or complete.get('source_deleted') is not False
            or complete.get('census_sha256') != args.backup_census_sha256
            or complete.get('restoration_directories') != census.get('directories')
            or members != census.get('files')
            or job.get('unit') != 'jp-v29-production-backup-'+number+'.service'
            or job.get('boot_id') != args.boot_id
            or job.get('package_manifest_sha256') != {'13': PIN28, '14': PIN30}[number]):
        raise ValueError('Actual root-accepted complete backup metadata differs')
    for index, name in enumerate(names):
        # COMPLETE remains at the accepted restoration location; its bound pin
        # is retained here. The derived stage preparer repeats the full guard.
        if name not in ('COMPLETE.json', 'CENSUS.json', 'MANIFEST.json'):
            writer.triple('BACKUP_INPUT_%02d.json'%index, raw[name])
    return raw, job, number


class Editor:
    def __init__(self, raw):
        self.text = raw.decode('utf-8')
        self.changes = []

    def change(self, old, new, required=True):
        count = self.text.count(old)
        if required and count == 0:
            raise ValueError('Exact pinned parent substitution missing: '+old)
        if count:
            self.text = self.text.replace(old, new)
            self.changes.append(dict(old=old, new=new, occurrences=count))

    def assignment(self, name, expression):
        tree = ast.parse(self.text)
        nodes = [node for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
        if len(nodes) != 1 or nodes[0].lineno != nodes[0].end_lineno:
            raise ValueError('Exact single-line constant assignment required: '+name)
        lines = self.text.splitlines(keepends=True)
        old = lines[nodes[0].lineno-1].rstrip('\r\n')
        self.change(old, name+' = '+expression)


def derivatives(args, parents, backup_job, backup_number):
    generated = {}
    edits = {}
    ordered = dict(NAMES)
    ordered.pop('prepare_core_activation30.py')
    ordered['prepare_core_activation30.py'] = NAMES['prepare_core_activation30.py']
    for name, output in ordered.items():
        editor = Editor(parents[name])
        editor.change('README_CORE_BUILD30_HELPERS.md', 'README_CORE_BUILD35_HELPERS.md', False)
        for old, new in NAMES.items():
            editor.change(Path(old).name, new, False)
        editor.change('from prepare_core_native_validation import ',
                      'from prepare_core_native_validation_v35 import ', False)
        if output == 'prepare_core_stage35.py':
            for constant, expression in {
                'STABILIZATION': 'Path('+repr(S.as_posix())+')',
                'BACKUP': 'Path('+repr(args.backup_root.as_posix())+')',
                'TARGET': repr(CAMPAIGN+'/field-runtime-v29-build-35'),
                'BASE_SHA': repr(PIN34),
                'BACKUP_SELECTED_PACKAGE_SHA': repr(backup_job['package_manifest_sha256']),
                'MANIFEST_SHA': repr(args.manifest_sha256),
                'ARCHIVE_SHA': repr(args.archive_sha256),
                'SOURCE_REVIEW_SHA': repr(args.source_review_sha256),
            }.items():
                editor.assignment(constant, expression)
            editor.change("read(HERE.parent/'prepare_core_stage29_v2.py',65536)",
                          'read(Path('+repr((D/'prepare_core_stage29_v2.py').as_posix())+'),65536)')
            editor.change("'README_SIDECAR_STAGE30_V2.md'", "'README_CORE_BUILD35_HELPERS.md'")
            editor.change('README_SIDECAR_STAGE30_V2.md', 'README_CORE_BUILD35_HELPERS.md', False)
            editor.change('sidecar-package30-', 'startup-package35-')
            editor.change('field-runtime-v29-build-30-prepared.tar.gz', 'field-runtime-v29-build-35-prepared.tar.gz')
            editor.change('BUILD29_MEMBER_PRESERVATION.json', 'BUILD34_MEMBER_PRESERVATION.json')
            editor.change("preservation.get('all_other_runtime_assets_models_profiles_raw_proof_bytes_identical')",
                          "preservation.get('all_other_parent_members_byte_identical')")
            editor.change("independent.get('pid_absent')", "independent.get('builder_os_process_absent')")
            editor.change("independent.get('natural_returncode')", "independent.get('builder_natural_exit_code')")
            editor.change("or independent.get('owner') != builder_owner",
                          "or independent.get('schema') != 'just-peachy.core-package35-independent-closure.v1'\n"
                          "                or independent.get('owner') != builder_owner")
            editor.change("independent.get('source_backups_restores_unchanged') is not True",
                          "independent.get('source_backups_and_independent_restores_exact') is not True\n"
                          "                or independent.get('current_sources_unchanged') is not True\n"
                          "                or independent.get('native_action') is not False")
            editor.change('jp-v29-production-backup-13.service', 'jp-v29-production-backup-'+backup_number+'.service')
            editor.change('core-stage30-02', 'core-stage35-01')
            editor.change('sidecar-stage30-v2-preparation-', 'startup-stage35-preparation-')
            editor.change('def backup_admission(strict,boot,complete_pin,result_pin,reviewer):',
                          'BACKUP_CENSUS_SHA = '+repr(args.backup_census_sha256)+
                          '\n\ndef backup_admission(strict,boot,complete_pin,result_pin,reviewer):')
            editor.change("    if sha(raw['COMPLETE.json']) != complete_pin or sha(raw['RESULT.json']) != result_pin:",
                          "    if sha(raw['CENSUS.json']) != BACKUP_CENSUS_SHA:\n"
                          "        raise ValueError('Explicit accepted backup census SHA differs')\n"
                          "    if sha(raw['COMPLETE.json']) != complete_pin or sha(raw['RESULT.json']) != result_pin:")
            editor.change("    parser.add_argument('--backup-result-sha256',required=True)",
                          "    parser.add_argument('--backup-result-sha256',required=True)\n"
                          "    parser.add_argument('--backup-census-sha256',required=True)")
            editor.change('    args = parser.parse_args()',
                          "    args = parser.parse_args()\n"
                          "    if args.backup_census_sha256 != BACKUP_CENSUS_SHA:\n"
                          "        raise ValueError('Explicit sealed accepted census pin required')")
        else:
            editor.change(PIN30, args.manifest_sha256, False)
            editor.change('field-runtime-v29-build-30', 'field-runtime-v29-build-35', False)
        if output == 'prepare_core_activation35.py':
            editor.assignment('REFERENCE', 'Path('+repr(S.as_posix())+')')
            editor.assignment('CURRENT_BOOT', repr(args.boot_id))
            editor.assignment('PRIOR_RECEIPT_SHA', repr(PRIOR_RESULT_SHA))
            editor.change('operation-stabilization-desktop28-01/dispatch/RESULT.json',
                          'operation-core-desktop30-01/dispatch/RESULT.json')
            editor.change(PIN28, PIN30)
            editor.change('8c917153c58c57d73d8ce0d0e5662b42b3f7d698de0cee4189b844f8cfc70ac0', PRIOR_DESKTOP_SHA)
            editor.change('c431d7b54441ed08a2a4fe1f3db630fcd2c39c6e1aaf5f0beec0e04f935cc968',
                          sha(generated['activate_core_desktop_action35.py']))
            editor.change('actual_check_number=41', 'actual_check_number='+str(args.live_check_number))
            editor.change('check_number=41', 'check_number='+str(args.live_check_number))
            editor.change('activation30-payload-', 'activation35-payload-')
        if output in ('prepare_core_activation35.py', 'activate_core_desktop_action35.py'):
            editor.change('classic-ui-check-41', 'classic-ui-check-'+str(args.live_check_number))
            editor.change('check41', 'check'+str(args.live_check_number), False)
        if output == 'stage_c24_endurance_input35.py':
            editor.change('core-c24-endurance-input-02', 'core-c24-endurance-input-03')
        if output == 'prepare_core_endurance35.py':
            # Exact root-selected experimental nullable backlog policy. Keep
            # source3600, drain600, load120, cleanup60, unit4380+300=4680 and
            # complete output reservation. It is never a realtime PASS claim.
            editor.change('module.SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=120)',
                          'module.SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=None,manual_stop=True)')
            editor.change('model_limits_unchanged=True',
                          'model_limits_unchanged=False,model_address_space_bytes=1024**3,parent33_model_limits_unchanged=True')
        if output == 'launch_core_full_app_hour35.py':
            editor.change('import fcntl\n','import ast\nimport copy\nimport fcntl\n')
            editor.change('def hash_file(path):','HOUR_LAUNCHER_ENTRYPOINT = '+repr(HOUR_LAUNCHER_ENTRYPOINT)+'\n\n'+HOUR_POLICY_ADAPTER+'\n\ndef hash_file(path):')
            editor.change("    original_plan = namespace['budget_plan']",
                          "    bind_exact_hour_policy(namespace, helper_path)\n    original_plan = namespace['budget_plan']")
            editor.change('return dict(result,original_source_verified=source_proof,',
                          "return dict(result,original_source_verified=source_proof,\n        hour_policy_adapter=namespace['_hour_policy_adapter_proof'],")
        if output == 'extract_core_job35.py':
            editor.assignment('S', 'Path('+repr(S.as_posix())+')')
            editor.assignment('PIN', repr(args.manifest_sha256))
            editor.change('README_EXTRACT_CORE_JOB31.md', 'README_CORE_BUILD35_HELPERS.md')
            editor.change('build31', 'build35')
            editor.change('actual31', 'actual35')
            editor.change('core-job31-', 'core-job35-')
            editor.change('ACTUAL_BUILD31_JOB_EXTRACTED', 'ACTUAL_BUILD35_JOB_EXTRACTED')
        # Only explanatory build labels change here; runtime timers, uncertainty
        # gates, namespaces, source hash/math and physical reservations stay exact.
        editor.change('build30', 'build35', False)
        body = editor.text.encode()
        compile(body, output, 'exec')
        generated[output] = body
        edits[output] = dict(parent=name, parent_sha256=PARENTS[name], substitutions=editor.changes)
    return generated, edits


def main():
    global HOUR_LAUNCHER_ENTRYPOINT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-output', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--content-sha256', required=True)
    parser.add_argument('--source-review-sha256', required=True)
    parser.add_argument('--build-closure-sha256', required=True)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--backup-root', type=Path, required=True)
    parser.add_argument('--backup-complete-sha256', required=True)
    parser.add_argument('--backup-result-sha256', required=True)
    parser.add_argument('--backup-census-sha256', required=True)
    parser.add_argument('--reviewer', required=True)
    parser.add_argument('--live-check-number', type=int, required=True,
                        help='Explicit fresh53 finite live check; normal production Start is separate')
    parser.add_argument('--saved-check-number', type=int, required=True,
                        help='Explicit fresh54 finite saved check; no native result is claimed here')
    args = parser.parse_args()
    if (any(re.fullmatch('[0-9a-f]{64}', getattr(args, name)) is None for name in
            ('manifest_sha256', 'archive_sha256', 'content_sha256', 'source_review_sha256', 'build_closure_sha256',
             'backup_complete_sha256', 'backup_result_sha256', 'backup_census_sha256'))
            or str(uuid.UUID(args.boot_id)) != args.boot_id
            or args.boot_id != CURRENT_BOOT or args.live_check_number != 53 or args.saved_check_number != 54
            or args.backup_complete_sha256 != BACKUP14_PINS['complete']
            or args.backup_result_sha256 != BACKUP14_PINS['result']
            or args.backup_census_sha256 != BACKUP14_PINS['census']
            or not 1 <= len(args.reviewer.strip()) <= 128):
        raise ValueError('Explicit actual pins/current boot/root-selected label/reviewer required')
    root, owner = bootstrap()  # Before all project/package/source reads.
    writer = Writer(root)
    writer.triple('PREPARER.py', read(Path(__file__)))
    parent_ops32 = read(PARENT_OPS32)
    if sha(parent_ops32) != PARENT_OPS32_SHA:
        raise ValueError('Exact reviewed ops32 source parent differs')
    writer.triple('PARENT_OPS32.py', parent_ops32)
    parent_ops33 = read(PARENT_OPS33)
    if sha(parent_ops33) != PARENT_OPS33_SHA:
        raise ValueError('Exact frozen ops33V2 generator parent differs')
    writer.triple('PARENT_OPS33_V2.py', parent_ops33)
    parent_ops34 = read(PARENT_OPS34)
    if sha(parent_ops34) != PARENT_OPS34_SHA:
        raise ValueError('Exact frozen ops34 generator parent differs')
    writer.triple('PARENT_OPS34.py', parent_ops34)
    template = read(TEMPLATE31)
    if sha(template) != TEMPLATE31_SHA:
        raise ValueError('Immutable reviewed31 generator template differs')
    writer.triple('TEMPLATE31_SOURCE.py', template)
    readme = read(HERE/'README_XVF_STARTUP35_OPS.md')
    writer.triple('README_CORE_BUILD35_HELPERS.md', readme)
    build_raw, manifest = binding_inputs(args, writer)
    launcher_source_sha256=next(row['sha256'] for row in manifest['files'] if row['path']=='launcher.py')
    if HOUR_LAUNCHER_ENTRYPOINT.count('PENDING_ACTUAL35_LAUNCHER_PIN')!=1:
        raise ValueError('One exact actual sealed35 launcher source binding required')
    HOUR_LAUNCHER_ENTRYPOINT=HOUR_LAUNCHER_ENTRYPOINT.replace('PENDING_ACTUAL35_LAUNCHER_PIN',launcher_source_sha256)
    backup_raw, backup_job, backup_number = accepted_backup(args, writer)
    prior_raw = read(Q/'operation-core-desktop30-01/dispatch/RESULT.json')
    if sha(prior_raw) != PRIOR_RESULT_SHA:
        raise ValueError('Exact actual prior30 activation receipt differs')
    prior = strict(prior_raw).get('action_result', {})
    if (prior.get('package_manifest_sha256') != PIN30 or prior.get('desktop_sha256') != PRIOR_DESKTOP_SHA
            or prior.get('autostart_sha256') != AUTOSTART_SHA or prior.get('login_autostart_disabled') is not True):
        raise ValueError('Exact prior30 desktop and unchanged disabled autostart required')
    writer.triple('PRIOR_DESKTOP30_RESULT.json', prior_raw)
    parents = {}
    for index, (name, pin) in enumerate(PARENTS.items()):
        body = read(D/name)
        if sha(body) != pin:
            raise ValueError('Frozen exact parent/dependency SHA differs: '+name)
        parents[name] = body
        writer.triple('PARENT_%02d.py'%index, body)
    generated, edits = derivatives(args, parents, backup_job, backup_number)
    for name in ('core_database_recovery.py', 'native_core_live_check_v2.py', 'native_core_saved_check_v2.py'):
        generated[name] = parents[name]
    generated['launch_full_app_soak_action.py'] = generated['launch_core_full_app_hour35.py']
    for name, body in generated.items():
        writer.triple(name, body)
    receipt = dict(schema='just-peachy.xvf-startup35-operator-bundle.v1', status='PREPARED', owner=owner,
        output=str(root), package=str(args.build_output/'package'), target=manifest['target'],
        package_manifest_sha256=args.manifest_sha256, archive_sha256=args.archive_sha256,
        candidate_content_sha256=args.content_sha256,
        source_review_sha256=args.source_review_sha256, build_closure_sha256=args.build_closure_sha256,
        boot_id=args.boot_id, reviewer=args.reviewer, live_check_number=args.live_check_number,
        saved_check_number=args.saved_check_number, source_template31_sha256=TEMPLATE31_SHA,
        generator_parent32_sha256=PARENT_OPS32_SHA,generator_parent33_v2_sha256=PARENT_OPS33_SHA,
        generator_parent34_sha256=PARENT_OPS34_SHA,
        retained_model_address_space_policy=MODEL_POLICY,
        fresh_hour_label='full-app-hour-08',
        live_proof_present_claimed=False, native_action=False, models_started=False,
        frozen_parents_unchanged=True, original_data_written=False, desktop_changed=False,
        prior30_result_sha256=PRIOR_RESULT_SHA, prior30_desktop_sha256=PRIOR_DESKTOP_SHA,
        disabled_autostart_sha256=AUTOSTART_SHA, backup_root=str(args.backup_root),
        backup_complete_sha256=args.backup_complete_sha256, backup_result_sha256=args.backup_result_sha256,
        backup_census_sha256=args.backup_census_sha256,
        backup_payload_rehash_repeated=False, source_backup_independent_restores=True,
        admission_window_seconds=600, continuous_source_seconds=3600, unit_runtime_seconds=4680,
        backlog_gate_seconds=None,manual_stop=True,developer_soak=True,hour_max_drain_seconds=600,
        hour_policy_deadline_seconds=4380,live_saved_helper_policy_unchanged=True,
        private_hour_expected_policy_adapter=dict(shared_source_sha256='307912b6d5fecace57d26dc40da8fe8d0a1d606dbd1c2fcfccc637136023a25d',
            full_app_hour_branch_only=True,reverse_ast_required=True,sealed_source_changed=False),
        private_hour_launcher_adapter=dict(source_sha256=launcher_source_sha256,
            nullable_backlog_parser_and_manual_stop_keyword_only=True,reverse_ast_required=True,
            actual_developer_wrapper_scope_only=True,normal_gui_changed=False,sealed_source_changed=False),
        normal_production_start_qualified=False,real_time_qualification_claimed=False,
        hour_native_and_pc_reservation='Original complete plan <=3GiB,2048files each',
        stage_fresh_input_if_needed='core-c24-endurance-input-03; verified02 may be reused for hour payload',
        syntax_compile_only=True, tests_executed=False, substitutions=edits,
        files={name:dict(bytes=len(body), sha256=sha(body)) for name, body in generated.items()})
    writer.triple('OPERATOR_BUNDLE.json', encoded(receipt))
    for name, body in parents.items():
        if read(D/name) != body:
            raise ValueError('Frozen source changed during preparation')
    if read(TEMPLATE31) != template:
        raise ValueError('Frozen31 generator source changed during preparation')
    if read(PARENT_OPS32) != parent_ops32:
        raise ValueError('Frozen32 generator source changed during preparation')
    if read(PARENT_OPS33) != parent_ops33:
        raise ValueError('Frozen33V2 generator source changed during preparation')
    if read(PARENT_OPS34) != parent_ops34:
        raise ValueError('Frozen34 generator source changed during preparation')
    for name, body in build_raw.items():
        if read(args.build_output/name, 2*1024**2) != body:
            raise ValueError('Authoritative builder receipt changed')
    for name, body in backup_raw.items():
        if read(args.backup_root/name, 2*1024**2) != body:
            raise ValueError('Accepted backup metadata changed')
    writer.put('SOURCE_CLOSED.json', encoded(dict(scope_closed=True, native_action=False,
        closed_unix=time.time(), prepared_bytes=writer.bytes, owner=owner,
        source_backups_restores_unchanged=True, bundle_sha256=sha(encoded(receipt)))))
    print(encoded(dict(output=str(root), status='PREPARED', native_action=False,
                       package_manifest_sha256=args.manifest_sha256,
                       bundle_sha256=sha(encoded(receipt)))).decode())


if __name__ == '__main__':
    main()
