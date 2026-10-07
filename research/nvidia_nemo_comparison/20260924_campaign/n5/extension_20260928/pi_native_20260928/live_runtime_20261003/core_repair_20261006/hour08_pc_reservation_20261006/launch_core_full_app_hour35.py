"""Narrow frozen-build35 one-hour dispatch adapter. README_CORE_BUILD35_HELPERS.md.

Injected PAYLOAD/BASELINE only. Reuse the installed continuous replay and shared
unit envelope; no runtime edits, new model loop, SSH or implicit admission.
"""
import ast
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import wave

PACKAGE = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-35')
PIN = '5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f'
SOURCE = Path('/home/peachyprototype/JustPeachy/data/runtime-v29/recordings/sessions/c24b685b2bd34d6bb04172965d712c0f')


def bind_verified_package(package, manifest):
    """Resolve project dependencies only in the fully inventoried package."""
    from importlib.machinery import PathFinder, SourceFileLoader
    package = Path(package)
    if package.resolve(strict=True) != package or package.is_symlink():
        raise ValueError('Canonical inventoried import root required')
    project = {Path(row['path']).stem: row for row in manifest['files']
        if '/' not in row['path'] and row['path'].endswith('.py')}
    def ordinary(name, origin):
        row = project.get(name)
        if row is None or not isinstance(origin, str):
            raise ValueError('Inventoried ordinary project origin required')
        path = Path(origin)
        expected = package / row['path']
        info = path.lstat()
        if (path != expected or path.resolve(strict=True) != expected or path.is_symlink()
                or not path.is_file() or info.st_nlink != 1
                or info.st_size != row['bytes'] or hash_file(path) != row['sha256']):
            raise ValueError('Project import origin differs from inventory: '+name)
    def verify_loaded():
        for name, module in tuple(sys.modules.items()):
            primary = name.split('.', 1)[0]
            origin = getattr(module, '__file__', None)
            from_package = isinstance(origin, str) and Path(origin).parent == package
            if primary not in project and not from_package:
                continue
            source_name = Path(origin).stem if from_package else primary
            ordinary(source_name, origin)
            spec = getattr(module, '__spec__', None)
            if spec is None or getattr(spec, 'origin', None) != origin:
                raise ValueError('Project module spec/file origins differ: '+name)
    verify_loaded()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(package))
    for name in project:
        spec = PathFinder.find_spec(name, [str(package)])
        if spec is None or not isinstance(spec.loader, SourceFileLoader):
            raise ValueError('Ordinary inventoried source loader required: '+name)
        ordinary(name, spec.origin)
    return verify_loaded


HOUR_LAUNCHER_ENTRYPOINT = 'def run_exact_hour_launcher(argv, package):\n if SETTINGS[\'kind\']!=\'full_app_hour\' or argv[0]!=str(package/\'launcher.py\'):\n  raise ValueError(\'Private nullable CLI adapter admits only the exact hour launcher\')\n expected={\'--binding\':str(package/\'BINDING.json\'),\'--data-root\':str(out/\'data\'),\n  \'--unit\':SETTINGS[\'unit\'],\'--unit-ownership\':str(out/\'UNIT_OWNERSHIP.json\'),\n  \'--input-source\':\'saved\',\'--maximum-session-seconds\':\'3600\',\n  \'--max-drain-seconds\':\'600\',\'--max-backlog-seconds\':\'None\',\'--repeat-input-seconds\':\'3600\'}\n for flag,value in expected.items():\n  if argv.count(flag)!=1 or argv.index(flag)+1>=len(argv) or argv[argv.index(flag)+1]!=value:\n   raise ValueError(\'Exact experimental hour CLI values required\')\n if any(argv.count(flag)!=1 for flag in (\'--headless\',\'--keep-processed\',\'--developer-soak\')):\n  raise ValueError(\'Exact headless saved developer hour flags required\')\n if any(flag in argv for flag in (\'--list-profiles\',\'--request-stop\',\'--optional-d1-refiner\')):\n  raise ValueError(\'This private launcher adapter does not admit alternate CLI paths\')\n path=package/\'launcher.py\';source=path.read_bytes()\n source_sha=\'8bc7db8dc4f6dae65691a85ff9cd9e97ad739f050ba796d5d83efee3b1ef5ff8\'\n if hashlib.sha256(source).hexdigest()!=source_sha:\n  raise ValueError(\'Exact HOST19 tested and sealed build35 launcher source required\')\n tree=ast.parse(source)\n functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==\'main\']\n if len(functions)!=1:raise ValueError(\'One exact source-bound launcher main required\')\n main=functions[0];original=ast.dump(main,include_attributes=False)\n original_call=ast.parse(\'SessionPolicy(args.maximum_session_seconds,args.developer_soak,max_drain_seconds=args.max_drain_seconds,max_backlog_seconds=args.max_backlog_seconds)\',mode=\'eval\').body\n nullable=ast.parse("lambda value: None if value==\'None\' else int(value)",mode=\'eval\').body\n def targets(function):\n  arguments=[node for node in ast.walk(function) if isinstance(node,ast.Call)\n   and isinstance(node.func,ast.Attribute) and node.func.attr==\'add_argument\'\n   and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value==\'--max-backlog-seconds\']\n  policies=[node for node in ast.walk(function) if isinstance(node,ast.Call)\n   and isinstance(node.func,ast.Name) and node.func.id==\'SessionPolicy\']\n  if len(arguments)!=1 or len(policies)!=1:raise ValueError(\'Exact nullable argument and policy construction required\')\n  types=[keyword for keyword in arguments[0].keywords if keyword.arg==\'type\']\n  if len(types)!=1:raise ValueError(\'One exact backlog parser type required\')\n  return types[0],policies[0]\n keyword,policy=targets(main)\n if ast.dump(keyword.value,include_attributes=False)!=ast.dump(ast.Name(id=\'int\',ctx=ast.Load()),include_attributes=False) or ast.dump(policy,include_attributes=False)!=ast.dump(original_call,include_attributes=False):\n  raise ValueError(\'Original tested launcher parser/policy AST differs\')\n keyword.value=nullable;policy.keywords.append(ast.keyword(arg=\'manual_stop\',value=ast.Constant(value=True)))\n reverse=copy.deepcopy(main);reverse_type,reverse_policy=targets(reverse)\n reverse_type.value=ast.Name(id=\'int\',ctx=ast.Load());reverse_policy.keywords.pop()\n if ast.dump(reverse,include_attributes=False)!=original:\n  raise ValueError(\'Private nullable/manual launcher reverse AST differs\')\n name=\'verified_hour_launcher_cli\'\n if name in sys.modules:raise ValueError(\'Fresh private hour launcher namespace required\')\n spec=importlib.util.spec_from_file_location(name,path)\n if spec is None or spec.origin!=str(path):raise ValueError(\'Exact ordinary launcher source origin required\')\n module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)\n if module.__file__!=str(path) or module.__spec__.origin!=str(path) or hashlib.sha256(path.read_bytes()).hexdigest()!=source_sha:\n  raise ValueError(\'Private launcher origin/source changed during load\')\n exec(compile(ast.fix_missing_locations(ast.Module(body=[main],type_ignores=[])),str(path),\'exec\'),module.__dict__)\n put(\'HOUR_LAUNCHER_POLICY_ADAPTER.json\',dict(source_sha256=source_sha,owner=owner,\n  nullable_backlog_argument_only=True,manual_stop_keyword_only=True,reverse_main_ast_exact=True,\n  policy=dict(maximum_session_seconds=3600,developer_soak=True,max_drain_seconds=600,\n   max_backlog_seconds=None,manual_stop=True),sealed_runtime_changed=False,\n  normal_gui_and_other_cli_paths_admitted=False,real_time_qualification_claimed=False))\n raise SystemExit(module.main())\n'

def bind_exact_hour_policy(namespace, helper_path):
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
        imported = 'from pathlib import Path\n'
        invocation = " try:runpy.run_path(argv[0],run_name='__main__');code=0"
        if source.count(imported) != 1 or source.count(invocation) != 1:
            raise ValueError('Exact original shared wrapper insertion/run boundary required')
        source = source.replace(imported, imported+'import ast,copy\n'+HOUR_LAUNCHER_ENTRYPOINT+'\n')
        source = source.replace(invocation, ' try:run_exact_hour_launcher(argv,package);code=0')
        compile(source, '<private-hour35-wrapper>', 'exec')
        return source
    namespace['wrapper_source'] = hour_wrapper


def hash_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def file_identity(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or
        any(p.is_symlink() for p in (path,*path.parents))):
        raise ValueError('Real single-link retained endurance input required')
    return dict(bytes=info.st_size,device=info.st_dev,inode=info.st_ino,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns)


def verify_source(payload):
    rows = payload['original_source_pins']
    if (type(rows) is not list or len(rows)!=8 or rows[0].get('source')!=str(SOURCE/'session.json') or
        [r.get('source') for r in rows[1:]]!=[str(SOURCE/('processed-%08d.wav'%i)) for i in range(7)]):
        raise ValueError('Exact c24 metadata and seven retained PCM16 segments required')
    pcm = hashlib.sha256();frames = 0
    for index,row in enumerate(rows):
        path = Path(row['source'])
        if file_identity(path)!=row['identity'] or hash_file(path)!=row['sha256']:
            raise ValueError('Original current c24 identity/hash differs from accepted host source')
        if index==0:
            meta = json.loads(path.read_bytes())
            if (meta.get('status')!='kept' or meta.get('session_id')!=SOURCE.name or
                meta.get('processed_samples')!=966400 or meta.get('spec',{}).get('sample_rate')!=16000):
                raise ValueError('Exact complete kept c24 source required')
        else:
            with wave.open(str(path),'rb') as source:
                if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())!=(1,2,16000,'NONE'):
                    raise ValueError('Original mono PCM16 16kHz replay representation required')
                frames += source.getnframes()
                while block:=source.readframes(8192):
                    pcm.update(block)
        if file_identity(path)!=row['identity']:
            raise ValueError('Original retained source changed during native verification')
    path = Path(payload['input'])
    before = file_identity(path)
    if hash_file(path)!=payload['input_sha256']:
        raise ValueError('Staged joined input SHA differs')
    joined = hashlib.sha256()
    with wave.open(str(path),'rb') as source:
        if ((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())!=(1,2,16000,'NONE') or
            source.getnframes()!=frames or frames!=966400):
            raise ValueError('Joined input must retain all exact original source frames')
        while block:=source.readframes(8192):
            joined.update(block)
    if (joined.hexdigest()!=pcm.hexdigest() or pcm.hexdigest()!=payload['input_pcm_sha256'] or
        file_identity(path)!=before):
        raise ValueError('Native joined PCM payload is not the lossless ordered original replay')
    return dict(source_session_id=SOURCE.name,frames=frames,seconds=frames/16000,
        retained_pcm16_representation=True,reencoded=False,lossless_pcm_join=True,
        source_pcm_sha256=pcm.hexdigest(),input_sha256=payload['input_sha256'])


def dispatch(payload,baseline):
    if (payload.get('schema')!='just-peachy.full-app-hour-admission.v1' or
        payload.get('reviewed') is not True or not isinstance(payload.get('reviewer'),str) or
        not 1<=len(payload['reviewer'])<=128 or payload.get('package')!=str(PACKAGE) or
        payload.get('package_manifest_sha256')!=PIN):
        raise ValueError('Exact reviewed frozen build35 continuous application admission required')
    manifest_path = PACKAGE/'PACKAGE_MANIFEST.json'
    if hash_file(manifest_path)!=PIN:
        raise ValueError('Frozen build35 manifest differs')
    manifest = json.loads(manifest_path.read_bytes())
    rows = [r for r in manifest['files'] if r['path']=='launch_raw_qualification_action.py']
    if len(rows)!=1:
        raise ValueError('Exact shared qualified envelope required')
    helper_path = PACKAGE/rows[0]['path']
    if file_identity(helper_path)['bytes']!=rows[0]['bytes'] or hash_file(helper_path)!=rows[0]['sha256']:
        raise ValueError('Pinned shared envelope differs')
    namespace = dict(__name__='verified_core_hour_envelope',__file__=str(helper_path))
    exec(compile(helper_path.read_bytes(),str(helper_path),'exec'),namespace)
    manifest = namespace['inventory'](PACKAGE,PIN)
    verified_imports = bind_verified_package(PACKAGE,manifest)
    lock_path = SOURCE.parent.parent/'locks'/(SOURCE.name+'.lock')
    if lock_path.is_symlink():
        raise ValueError('Real retained source lease required')
    with lock_path.open('rb') as lease:
        fcntl.flock(lease,fcntl.LOCK_SH|fcntl.LOCK_NB)
        source_proof = verify_source(payload)
    bind_exact_hour_policy(namespace, helper_path)
    original_plan = namespace['budget_plan']
    def capacity_plan(package,binding,request,kind):
        plan = original_plan(package,binding,request,kind)
        verified_imports()
        if kind!='full_app_hour':
            raise ValueError('This adapter admits only the retained integrated hour workflow')
        disk = namespace['shutil'].disk_usage(PACKAGE.parent)
        storage = namespace['load_pure'](package,'storage')
        verified_imports()
        reserve = storage.StoragePolicy(**binding.get('storage_policy',{})).reserve(disk.total)
        ceiling = disk.total-reserve
        if disk.free<reserve+plan['maximum_output_bytes'] or ceiling<plan['maximum_output_bytes']:
            raise OSError('Actual capacity cannot preserve complete hour output and physical reserve')
        plan.update(file_limit_bytes=ceiling,physical_file_reserve_bytes=reserve,
            physical_filesystem_total_bytes=disk.total,physical_free_at_admission_bytes=disk.free,
            file_limit_scope='Per-file capacity guard; complete job output reservation remains unchanged')
        return plan
    namespace['budget_plan'] = capacity_plan
    result = namespace['launch'](payload,baseline,kind='full_app_hour')
    verified_imports()
    return dict(result,original_source_verified=source_proof,
        hour_policy_adapter=namespace['_hour_policy_adapter_proof'],
        endurance_scope='One continuous wall-paced headless application session using repeated retained speech',
        natural_conversation=False,gui_endurance=False,quality_evaluated=False)


if 'PAYLOAD' in globals():
    RESULT = dispatch(PAYLOAD,BASELINE)
