"""Exact closed failed normal01 ownership admission; README_CORE_OPERATIONS_V13.md.

Host-only source adapter. It never changes runtime policy or admits a future run.
"""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

PIN35 = '5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f'
BOOT = 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
RELATIVE = 'live-runtime-tests-20261003/production-normal-01'
NATIVE = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/'+RELATIVE
MIRROR = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/production-normal-01-monitor-02')
LEGACY_SHA = 'ea6549b4f6b1e4a53ca41c6de11e32aa42d7ad526e3d5063e910cb9c50b18c32'
ROOT_PINS = {
    'RESULT.json': 'd82ee7ae49f726884ea4a20a93848fc0c43169db25f3cbfb433610dc1c4de97c',
    'MIRROR_MANIFEST.json': '08750632bbfe89a4ed19938b01af8a22a73aab7146455b81e337e7029a627096',
    'MIRROR_COMPLETE.json': '90b3bfe06172f39624c7cd5007bec759981d8f48e2db526adb4cf36c3fda6b12',
}
BASE = {'control_group', 'deadline_monotonic', 'idle_timeout_seconds', 'invocation_id',
        'main_pid', 'owner', 'runtime_max_seconds', 'unit'}
EXTRA = {'address_space', 'stack', 'qualification_kind', 'recording_model_scope'}
WATCHDOG = BASE-{'deadline_monotonic', 'idle_timeout_seconds'}
MANUAL = BASE | {'lifetime_policy'}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('Duplicate normal01 metadata field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def read(path, maximum=262144):
    before = path.lstat()
    if (path.resolve(strict=True) != path or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1 or before.st_size > maximum
            or any(parent.is_symlink() for parent in path.parents)):
        raise ValueError('Canonical bounded single-link normal01 receipt required')
    with path.open('rb') as stream: raw = stream.read(maximum+1)
    after = path.lstat()
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if len(raw) != before.st_size or fields(before) != fields(after):
        raise ValueError('Normal01 receipt changed while reading')
    return raw


def owner(value, pid, ticks):
    if (type(value) is not dict or set(value) != {'pid', 'start_ticks', 'boot_id'}
            or type(value.get('pid')) is not int or type(value.get('start_ticks')) is not int
            or value != dict(pid=pid, start_ticks=ticks, boot_id=BOOT)):
        raise ValueError('Exact observed normal01 owner required')


def unit(value, keys, name, pid, ticks, invocation):
    if type(value) is not dict or set(value) != keys:
        raise ValueError('Exact normal01 unit role fields required')
    owner(value['owner'], pid, ticks)
    if (type(value['main_pid']) is not int or value['main_pid'] != pid
            or value['unit'] != name or value['invocation_id'] != invocation
            or value['control_group'] != '/user.slice/user-1000.slice/user@1000.service/app.slice/'+name):
        raise ValueError('Exact normal01 unit, invocation and cgroup required')


def validate_roles(job, outer, watcher, cleanup, watcher_exit):
    """Validate observed failed-run roles; never promote cleanup to normal Exit."""
    if (type(job) is not dict or job.get('schema') != 'just-peachy.native-component-job.v1'
            or job.get('package_manifest_sha256') != PIN35 or job.get('boot_id') != BOOT
            or job.get('output_root') != NATIVE or job.get('maximum_output_bytes') != 32*1024**2):
        raise ValueError('Exact observed normal01 job/PIN35 required')
    unit(outer, BASE | EXTRA, 'jp-v29-production-normal-01.service', 143535, 3393325,
         '18019d9b8be14da89306adfac02d66e3')
    if (any(outer[k] != job[k] for k in ('unit', 'owner', 'invocation_id', 'control_group'))
            or outer['qualification_kind'] != 'production_idle'
            or outer['recording_model_scope'] is not False
            or outer['address_space'] != [256*1024**2]*2 or outer['stack'] != [1024**2]*2
            or any(type(n) is not int for n in outer['address_space']+outer['stack'])
            or type(outer['runtime_max_seconds']) is not int or outer['runtime_max_seconds'] != 300
            or type(outer['idle_timeout_seconds']) is not int or outer['idle_timeout_seconds'] != 300
            or type(outer['deadline_monotonic']) not in (int, float)
            or not math.isfinite(outer['deadline_monotonic']) or outer['deadline_monotonic'] <= 0):
        raise ValueError('Exact external metadata controller policy required')
    unit(watcher, WATCHDOG, 'jp-v29-production-normal-01-watchdog.service', 143541, 3393344,
         'a2c5b1a2ce0d4c8ca50bd53d16ea50ae')
    if type(watcher['runtime_max_seconds']) is not int or watcher['runtime_max_seconds'] != 270:
        raise ValueError('Actual normal01 watchdog lifetime required')
    manual = cleanup['ownership']
    unit(manual, MANUAL, 'jp-v29-a4213a742b304e0885c5996228b901a7.service', 143555, 3393382,
         '1fa968283e544b99bf92874087260229')
    if (manual['runtime_max_seconds'] is not None or manual['deadline_monotonic'] is not None
            or manual['lifetime_policy'] != 'manual_stop_storage_guarded'
            or type(manual['idle_timeout_seconds']) is not int or manual['idle_timeout_seconds'] != 300
            or cleanup.get('forced') is not True
            or any(cleanup.get(k) is not True for k in ('closed', 'cgroup_empty', 'main_exact_owner_gone'))
            or watcher_exit.get('owner') != watcher['owner'] or watcher_exit.get('failure') is not None
            or watcher_exit.get('closure', {}).get('ownership') != manual
            or any(watcher_exit['closure'].get(k) is not True for k in ('closed', 'cgroup_empty', 'main_exact_owner_gone'))):
        raise ValueError('Matching failed normal01 cleanup and watchdog closure required')


def verified_normal01():
    roots = {}
    for name, pin in ROOT_PINS.items():
        raw = read(MIRROR/name)
        if hashlib.sha256(raw).hexdigest() != pin: raise ValueError('Sealed normal01 mirror root changed')
        roots[name] = strict(raw)
    transport, rows, complete = (roots[n] for n in ('RESULT.json', 'MIRROR_MANIFEST.json', 'MIRROR_COMPLETE.json'))
    job = transport['job']; closure = complete['closure']
    if (transport.get('status') != 'FULL_CLOSED_OUTPUT_MIRRORED' or complete.get('kind') != 'COMPLETE'
            or complete.get('files') != 34 or complete.get('bytes') != 280284
            or complete.get('manifest_sha256') != hashlib.sha256(encoded(rows)).hexdigest()
            or complete.get('mirror_scope') != 'all_regular_output_files'
            or any(closure.get(k) != job[k] for k in ('owner', 'unit', 'invocation_id', 'control_group'))
            or any(closure.get(k) is not True for k in ('closed', 'exact_owner_gone', 'cgroup_empty'))):
        raise ValueError('Exact complete independently closed normal01 mirror required')
    members = {}; total = 0
    for row in rows:
        name = row['path']
        if (type(name) is not str or name in members or '\\' in name or ':' in name
                or any(part in ('', '.', '..') for part in name.split('/'))):
            raise ValueError('Canonical unique normal01 mirrored member required')
        raw = read(MIRROR/'closed-output'/name)
        if len(raw) != row['identity']['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Full normal01 mirror member readback differs')
        members[name] = (raw, row); total += len(raw)
    actual = set()
    for directory, children, files in os.walk(MIRROR/'closed-output', followlinks=False):
        if any((Path(directory)/name).is_symlink() for name in children):
            raise ValueError('Normal01 mirror directory link refused')
        actual.update((Path(directory)/name).relative_to(MIRROR/'closed-output').as_posix() for name in files)
    if actual != set(members) or total != complete['bytes']: raise ValueError('Exact normal01 full membership required')
    doc = lambda name: strict(members[name][0])
    outer, watcher = doc('UNIT_OWNERSHIP.json'), doc('watchdog/UNIT_OWNERSHIP.json')
    control, exit_row = doc('CONTROL_COMPLETE.json'), doc('watchdog/WATCHDOG_EXIT.json')
    validate_roles(job, outer, watcher, control['cleanup'], exit_row)
    if (doc('JOB.json') != {k: v for k, v in job.items() if k != 'output_identity'}
            or doc('OWNER.json') != outer['owner'] or doc('watchdog/OWNER.json') != watcher['owner']
            or doc('JOB_EXIT.json') != closure.get('job_exit')
            or closure['job_exit'].get('natural_returncode') != 1
            or closure['job_exit'].get('leases_released') is not True
            or control.get('normal_exit') is not False
            or doc('NORMAL_GUI_RESULT.json').get('functional_success') is not False
            or doc('STATE_BEFORE.json') != doc('STATE_AFTER.json')):
        raise ValueError('Failed observed normal01 is closed evidence, not successful Exit')
    pins = {RELATIVE+'/'+name: dict(bytes=len(members[name][0]), sha256=members[name][1]['sha256'],
            document=value, owner=value['owner'], kind=kind)
        for name, value, kind in (('UNIT_OWNERSHIP.json', outer, 'normal01_outer'),
                                 ('watchdog/UNIT_OWNERSHIP.json', watcher, 'normal01_watchdog'))}
    return dict(job=job, pins=pins, outer=outer, watcher=watcher, cleanup=control['cleanup'],
                watcher_exit=exit_row, members=34, bytes=total)


def _fingerprint(code):
    return (code.co_code, code.co_names, code.co_varnames, code.co_argcount,
            tuple(_fingerprint(v) if isinstance(v, types.CodeType) else v for v in code.co_consts))


def focused_checks(proof):
    """One observed positive and eight changed-role negatives, without I/O."""
    values = [proof[n] for n in ('job', 'outer', 'watcher', 'cleanup', 'watcher_exit')]
    validate_roles(*values)
    cases = []
    def changed(index, key, value):
        fixture = copy.deepcopy(values); fixture[index][key] = value; cases.append(fixture)
    changed(0, 'package_manifest_sha256', '0'*64)
    changed(1, 'qualification_kind', 'gui')
    changed(0, 'output_root', NATIVE[:-2]+'02')
    changed(2, 'runtime_max_seconds', True)
    fixture = copy.deepcopy(values); fixture[3]['ownership']['idle_timeout_seconds'] = True; cases.append(fixture)
    fixture = copy.deepcopy(values); fixture[3]['ownership'].pop('owner'); cases.append(fixture)
    changed(1, 'unreviewed_field', 1)
    changed(1, 'recording_model_scope', True)
    for fixture in cases:
        try: validate_roles(*fixture)
        except ValueError: continue
        raise AssertionError('Changed normal01 role or field was admitted')
    return dict(schema='just-peachy.normal01-owner-focused-check.v1', checks=9,
                observed_positive=1, rejected=8, native_action=False, synthetic_receipts_written=False)


def filtered_legacy_map(v10, space, legacy_path, proof):
    """Skip only the exact verified new mirror; all seven historical gates remain."""
    raw = read(legacy_path)
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA: raise ValueError('Frozen legacy nested collector changed')
    nodes = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'actual_nested_unit_map']
    if len(nodes) != 1: raise ValueError('One exact legacy collector function required')
    original = nodes[0]; namespace = dict(space)
    exec(compile(ast.Module(body=[original], type_ignores=[]), str(legacy_path), 'exec'), namespace)
    if _fingerprint(namespace['actual_nested_unit_map'].__code__) != _fingerprint(v10['old_map'].__code__):
        raise ValueError('Actual loaded historical collector does not match its frozen source')
    changed = copy.deepcopy(original)
    loops = [n for n in ast.walk(changed) if isinstance(n, ast.For)
             and isinstance(n.target, ast.Name) and n.target.id == 'result_path']
    expected = ast.parse("if result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED':continue").body[0]
    if len(loops) != 1 or ast.dump(loops[0].body[1], include_attributes=False) != ast.dump(expected, include_attributes=False):
        raise ValueError('Exact legacy complete-mirror seam changed')
    addition = ast.parse('if normal01_filter(result_path,result):continue').body[0]
    loops[0].body.insert(2, addition)
    reverse = copy.deepcopy(changed)
    reverse_loop = next(n for n in ast.walk(reverse) if isinstance(n, ast.For)
                        and isinstance(n.target, ast.Name) and n.target.id == 'result_path')
    reverse_loop.body.pop(2)
    if ast.dump(reverse, include_attributes=False) != ast.dump(original, include_attributes=False):
        raise ValueError('Historical collector reverse AST differs')
    def skip(path, result):
        if result.get('job', {}).get('output_root') != NATIVE: return False
        if path != MIRROR/'RESULT.json' or result != strict(read(path)):
            raise ValueError('Unreviewed normal01 mirror path or changed receipt refused')
        if hashlib.sha256(read(path)).hexdigest() != ROOT_PINS['RESULT.json']:
            raise ValueError('Exact already verified normal01 result required')
        return True
    namespace['normal01_filter'] = skip
    exec(compile(ast.fix_missing_locations(ast.Module(body=[changed], type_ignores=[])), str(legacy_path), 'exec'), namespace)
    v10['old_map'] = namespace['actual_nested_unit_map']


def install(v12):
    """Add two exact campaign receipts before the unchanged V12 native preread."""
    space, v10 = v12['space'], v12['v10']; proof = verified_normal01()
    checks = focused_checks(proof)
    source = Path(v12['source_root']).parent/'stabilization_20261005/host_stabilization_operations_v5.py'
    raw = read(source); v12['independent_copy'](v12['initial'], source, raw)
    filtered_legacy_map(v10, space, source, proof)
    old_closed = space['driver'].closed_unit_owner
    def closed(job, raw, entry, closure):
        if job.get('output_root') != NATIVE: return old_closed(job, raw, entry, closure)
        expected = proof['pins'][RELATIVE+'/UNIT_OWNERSHIP.json']
        if (job != proof['job'] and job != {k: v for k, v in proof['job'].items() if k != 'output_identity'}
                or entry.get('path') != 'UNIT_OWNERSHIP.json' or type(raw) is not bytes
                or len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']
                or entry.get('sha256') != expected['sha256'] or entry.get('identity', {}).get('bytes') != len(raw)
                or strict(raw) != expected['document']
                or any(closure.get(k) != job[k] for k in ('owner', 'unit', 'invocation_id', 'control_group'))
                or any(closure.get(k) is not True for k in ('closed', 'exact_owner_gone', 'cgroup_empty'))):
            raise ValueError('Exact closed normal01 external controller receipt required')
        return dict(sha256=expected['sha256'], owner=expected['owner'])
    space['driver'].closed_unit_owner = closed
    prior = space['driver'].bind_native_owner_references
    def bind(native, new_owners, unit_owners):
        text = prior(native, new_owners, unit_owners)
        declaration = 'owner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()'
        seam = " elif 'owner' in v:\n  assert rel in NESTED"
        if text.count(declaration) != 1 or text.count(seam) != 1:
            raise ValueError('Exact retained native ownership seam changed')
        addition = """ elif rel in EXACT_CLOSED_NORMAL01:
  expected=EXACT_CLOSED_NORMAL01[rel]
  assert rel in {'live-runtime-tests-20261003/production-normal-01/UNIT_OWNERSHIP.json','live-runtime-tests-20261003/production-normal-01/watchdog/UNIT_OWNERSHIP.json'}
  assert len(raw)==expected['bytes'] and sha(raw)==expected['sha256'] and v==expected['document']
  identity(v['owner'])
  assert type(v['main_pid']) is int and v['main_pid']==v['owner']['pid']
  assert v['control_group']=='/user.slice/user-1000.slice/user@1000.service/app.slice/'+v['unit']
  assert not(v['owner']['boot_id']==boot and ticks(v['owner']['pid'])==v['owner']['start_ticks']), ('Actual normal01 owner remains live',rel)
  v=v['owner']
"""
        amended = text.replace(declaration, 'EXACT_CLOSED_NORMAL01='+repr(proof['pins'])+'\n'+declaration)
        amended = amended.replace(seam, addition+seam)
        restored = amended.replace('EXACT_CLOSED_NORMAL01='+repr(proof['pins'])+'\n', '').replace(addition, '')
        if restored != text: raise ValueError('Native exact normal01 insertion reverse differs')
        compile(amended, '<exact-failed-normal01-ownership>', 'exec')
        return amended
    space['driver'].bind_native_owner_references = bind
    space['put']('EXACT_CLOSED_NORMAL01_BINDING.json', dict(schema='just-peachy.exact-closed-normal01-binding.v1',
        source_roots=ROOT_PINS, package_manifest_sha256=PIN35, admitted_paths=sorted(proof['pins']),
        members=proof['members'], bytes=proof['bytes'], legacy_collector_reverse_ast_exact=True,
        historical_pin21_decoder_unchanged=True, failed_functional_result_preserved=True,
        forced_cleanup_not_normal_exit=True, native_action_claimed=False))
    space['put']('NORMAL01_OWNER_FOCUSED_CHECK.json', checks)
