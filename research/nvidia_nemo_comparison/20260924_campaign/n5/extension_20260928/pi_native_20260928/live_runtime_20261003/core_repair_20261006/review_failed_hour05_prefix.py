"""Hash-bound read-only FAILED hour05 prefix. README_FAILED_HOUR05_PREFIX.md.

Separate derivative; never edits or reruns the original complete-hour reviewer.
"""
import argparse
import ast
import copy
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
OPS = PRIVATE/'audit-preparation/caption31-ops-27a8711bc02b45038f1a0a640bfddac0'
PACKAGE = PRIVATE/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/package'
PACKAGE_SHA = '4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
MIRROR = PRIVATE/'full-app-hour-05-monitor-01'
OPS_PINS = {
    'review_core_full_app_hour31.py': '8610912d0df9fa3a43de685cf116b556a7815f07c6e61b1132075c1aae692b23',
    'launch_core_full_app_hour31.py': '2feb4a27f1b329c460497c40b8d2e71328f4e1daa637c67268a56558dd887772',
    'prepare_core_native_validation_v31.py': 'db51515fec14cf08995a6a467caf677531f90c001c0fc52e617d0417aaeb2f78',
    'README_CORE_BUILD31_HELPERS.md': '3a4e5ae8a5f7ae819a5e6af46fe266d1eef0f2a2c780ad22c110d98e01b308bd',
}
MIRROR_PINS = {
    'RESULT.json': 'c819afad48edf3c69f451a7633a995d92ae878e7dc49cc038d75af81960219bc',
    'MIRROR_COMPLETE.json': 'cc9215848c603abddce33dfff9863d9dffb22f69b3539849e2883a86bca42ab4',
    'MIRROR_MANIFEST.json': 'd78d6ab3319f73c4c0d7e64619071a8407f2d8708f75ceeff9c99cd90c9b5dfb',
}
LANE_FIELDS = ('speaker_lag_seconds', 'asr_lag_seconds', 'speaker_cursor_seconds',
               'speaker_analyzed_through_seconds', 'asr_cursor_seconds')
PREFIX = {}
DEADLINE = None


def save(path, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode()
    if len(raw) > 2*1024**2:
        raise ValueError('Finite numeric review output')
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short review output')
        stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('Review independent readback differs')


def early(parent):
    if os.name != 'nt' or parent.resolve(strict=True) != PRIVATE/'audit-preparation':
        raise ValueError('Exact existing Windows private preparation parent required')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 16384):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    output = parent/('failed-hour05-prefix-'+uuid.uuid4().hex)
    output.mkdir(exist_ok=False)
    owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(),
                 cpu=14, affinity_mask=16384, creation_filetime=stamps[0].value,
                 create_time=(stamps[0].value-116444736000000000)/10000000)
    save(output/'REGISTERED_OWNER.json', owner)
    return output, owner


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def verified_prefix_events(path, *, maximum_bytes, maximum_records, iterator, allow_partial):
    """Individual native decoder proofs plus exact committed-prefix receipt digest."""
    if allow_partial is not True:
        raise ValueError('This exact failed-prefix derivative requires partial decoding')
    from event_compaction import encoded, strict
    index = strict(path.with_name(path.name+'.index.json').read_bytes())
    receipt = strict(path.with_name(path.name+'.compaction.json').read_bytes())
    if index.get('complete') is not False or receipt.get('complete') is not False or receipt.get('error') != 'MemoryError()':
        raise ValueError('Exact failed incomplete MemoryError stream required')
    digest = hashlib.sha256(); count = logical_bytes = 0
    for event in iterator(path, maximum_bytes=maximum_bytes, maximum_records=maximum_records,
                          allow_partial=True):
        if time.monotonic() > DEADLINE:
            raise TimeoutError('Failed-prefix reviewer exceeded its finite host deadline')
        raw = encoded(event)
        digest.update(raw); digest.update(b'\n')
        count += 1; logical_bytes += len(raw)+1
        yield event
    observed = dict(records=count, logical_bytes=logical_bytes, logical_sha256=digest.hexdigest())
    if any(observed[key] != receipt[key] for key in observed):
        raise ValueError('Available decoded prefix differs from committed writer receipt; no completeness inferred')
    PREFIX.update(observed, stored_prefix_matches_writer_receipt=True,
                  writer_complete=False, session_complete=False,
                  physical_completed_bytes=index['completed_bytes'], compaction_error=receipt['error'],
                  interpretation='Every available record sequence/base/event digest and committed prefix digest verified; failed session remains incomplete')


def derive_review(original, raw):
    """Five exact AST regions; reverse proof preserves every other original node."""
    tree = ast.parse(raw)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'review']
    if len(nodes) != 1:
        raise ValueError('One exact admitted review method required')
    node = nodes[0]; baseline = copy.deepcopy(node); restores = []
    imports = [item for item in ast.walk(node) if isinstance(item, ast.ImportFrom) and item.module == 'event_compaction']
    if len(imports) != 1 or ast.dump(imports[0], include_attributes=False) != ast.dump(ast.parse('from event_compaction import iter_events').body[0], include_attributes=False):
        raise ValueError('Original compact reader import drift')
    restores.append((imports[0], 'names', copy.deepcopy(imports[0].names)))
    imports[0].names = [ast.alias(name='iter_events', asname='_admitted_iter_events')]
    calls = [item for item in ast.walk(node) if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == 'iter_events']
    expected = ast.parse("iter_events(root/indices[0].removesuffix('.index.json'), maximum_bytes=index['completed_bytes'] or 1, maximum_records=index['completed_bytes'] or 1)", mode='eval').body
    if len(calls) != 1 or ast.dump(calls[0], include_attributes=False) != ast.dump(expected, include_attributes=False):
        raise ValueError('Original complete-reader call drift')
    restores.extend(((calls[0], 'func', copy.deepcopy(calls[0].func)),
                     (calls[0], 'keywords', copy.deepcopy(calls[0].keywords))))
    calls[0].func = ast.Name(id='verified_prefix_events', ctx=ast.Load())
    calls[0].keywords.extend((ast.keyword(arg='iterator', value=ast.Name(id='_admitted_iter_events', ctx=ast.Load())),
                              ast.keyword(arg='allow_partial', value=ast.Constant(value=True))))
    tuples = [item for item in ast.walk(node) if isinstance(item, ast.Tuple) and item.elts and
              isinstance(item.elts[0], ast.Constant) and item.elts[0].value == 'rss']
    expected_fields = ('rss','pss_bytes','virtual_bytes','vm_peak_bytes','available_ram','backlog_seconds',
                       'temperature_millicelsius','cpu_seconds','threads','first_caption_latency','first_speaker_latency','dropped_audio')
    if len(tuples) != 1 or tuple(item.value for item in tuples[0].elts) != expected_fields:
        raise ValueError('Original health numeric field region drift')
    restores.append((tuples[0], 'elts', copy.deepcopy(tuples[0].elts)))
    tuples[0].elts.extend(ast.Constant(value=key) for key in LANE_FIELDS)
    returns = [item for item in ast.walk(node) if isinstance(item, ast.Return)]
    target = [item.value for item in returns if isinstance(item.value, ast.Call) and any(k.arg == 'completion_gates' for k in item.value.keywords)]
    if len(target) != 1:
        raise ValueError('One original numeric result region required')
    result = target[0]; status = [item for item in result.keywords if item.arg == 'status']
    expected_status = ast.parse("'COMPLETE_3600_SOURCE_AND_CLOSURE' if all(gates.values()) else 'FAILED_OR_INCOMPLETE_PREFIX'", mode='eval').body
    if len(status) != 1 or ast.dump(status[0].value, include_attributes=False) != ast.dump(expected_status, include_attributes=False):
        raise ValueError('Original result qualification expression drift')
    restores.append((result, 'keywords', copy.deepcopy(result.keywords)))
    restores.append((status[0], 'value', copy.deepcopy(status[0].value)))
    status[0].value = ast.Constant(value='FAILED_COMPACT_PREFIX_NUMERIC_REVIEW')
    result.keywords.extend((ast.keyword(arg='last_health_numeric', value=ast.parse("{key:value for key,value in last_health.items() if type(value) in (int,float,bool)}", mode='eval').body),
                           ast.keyword(arg='last_health_component_costs', value=ast.parse("last_health.get('costs')", mode='eval').body)))
    derived = copy.deepcopy(node)
    for owner, field, value in reversed(restores):
        setattr(owner, field, value)
    if ast.dump(node, include_attributes=False) != ast.dump(baseline, include_attributes=False):
        raise ValueError('Narrow failed-prefix AST reverse proof differs')
    namespace = dict(original.__dict__, verified_prefix_events=verified_prefix_events)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[derived], type_ignores=[])),
                 '<exact-admitted-hour31-review-failed-prefix-derivative>', 'exec'), namespace)
    return namespace['review'], dict(source_sha256=OPS_PINS['review_core_full_app_hour31.py'],
        original_review_ast_sha256=hashlib.sha256(ast.dump(baseline, include_attributes=False).encode()).hexdigest(),
        derived_review_ast_sha256=hashlib.sha256(ast.dump(derived, include_attributes=False).encode()).hexdigest(),
        reverse_ast_equal=True, regions=['reader alias','verified partial-reader call','five numeric lane fields',
                                        'always failed-prefix status','last numeric health and component cost result'])


def main():
    global DEADLINE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mirror', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    output, owner = early(args.output_root)
    sys.dont_write_bytecode = True; DEADLINE = time.monotonic()+600; PREFIX.clear()
    if args.mirror.resolve(strict=True) != MIRROR or args.package.resolve(strict=True) != PACKAGE or args.manifest_sha256 != PACKAGE_SHA:
        raise ValueError('Only the exact FAILED hour05 mirror and sealed31 dependencies admitted')
    sources = {}
    for name, expected in OPS_PINS.items():
        path = OPS/name
        if sha(path) != expected:
            raise ValueError('Original OPS31 source pin drift: '+name)
        sources[str(path)] = expected
    for name, expected in MIRROR_PINS.items():
        if sha(MIRROR/name) != expected:
            raise ValueError('Exact closed failed mirror metadata drift: '+name)
    for path in [*(OPS/name for name in OPS_PINS), Path(__file__), HERE/'README_FAILED_HOUR05_PREFIX.md']:
        raw = path.read_bytes(); token = path.name
        sources[str(path)] = hashlib.sha256(raw).hexdigest()
        for suffix in ('backup','restore'):
            copied = output/(token+'.'+suffix)
            with copied.open('xb') as stream:
                if stream.write(raw) != len(raw): raise OSError('Short independent source copy')
                stream.flush(); os.fsync(stream.fileno())
            if copied.read_bytes() != raw: raise OSError('Source independent restore differs')
    save(output/'SOURCE_CLOSED.json', dict(owner=owner, before_review=True, source_pins=sources,
         original_sources_unchanged=True, independent_backups_and_restores=True,
         failed_mirror_metadata_pins=MIRROR_PINS, package_manifest_sha256=PACKAGE_SHA, native_action=False))
    original = module('_admitted_hour31_failed_prefix_base', OPS/'review_core_full_app_hour31.py')
    transport = original.strict(MIRROR/'RESULT.json'); complete = original.strict(MIRROR/'MIRROR_COMPLETE.json')
    if (transport.get('functional_success') is not False or transport['job']['package_manifest_sha256'] != PACKAGE_SHA
            or complete['closure']['job_exit']['natural_returncode'] != 1
            or complete['closure']['owner']['pid'] != 77571 or complete['closure']['owner']['start_ticks'] != 1712599):
        raise ValueError('Exact closed FAILED hour05 scope required')
    preparer = module('_admitted_hour31_prefix_inventory', OPS/'prepare_core_native_validation_v31.py')
    manifest, _ = preparer.inventory(PACKAGE, PACKAGE_SHA)
    tree = ast.parse((OPS/'launch_core_full_app_hour31.py').read_bytes())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'bind_verified_package','hash_file'}]
    if len(nodes) != 2: raise ValueError('Original pure package binder drift')
    scope = dict(Path=Path, sys=sys, hashlib=hashlib)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<admitted-hour31-pure-import-binder>', 'exec'), scope)
    check = scope['bind_verified_package'](PACKAGE, manifest)
    reviewer, derivation = derive_review(original, (OPS/'review_core_full_app_hour31.py').read_bytes())
    save(output/'AST_DERIVATION.json', derivation)
    result = reviewer(MIRROR)
    check()
    if not PREFIX or result['status'] != 'FAILED_COMPACT_PREFIX_NUMERIC_REVIEW':
        raise ValueError('Validated stored-prefix evidence required; no success status permitted')
    result.update(schema='just-peachy.failed-hour05-prefix-review.v1', event_prefix=PREFIX,
                  stored_prefix_only=True, source_session_failed=True, full_output_complete=False,
                  sustained_realtime_qualified=False, exact_3600_qualification_claimed=False,
                  original_complete_reviewer_failure_preserved=True, native_executed=False)
    for path, expected in sources.items():
        if sha(Path(path)) != expected: raise ValueError('Review source changed: '+path)
    for name, expected in MIRROR_PINS.items():
        if sha(MIRROR/name) != expected: raise ValueError('Mirror metadata changed during review')
    save(output/'REVIEW.json', result)
    save(output/'RESULT.json', dict(status='FAILED_PREFIX_REVIEWED', owner=owner, source_unchanged=True,
         prefix_validated=True, source_session_status='FAILED', qualified=False, native_action=False,
         package_manifest_sha256=PACKAGE_SHA, review_sha256=sha(output/'REVIEW.json')))
    print(json.dumps(dict(output=str(output), status='FAILED_PREFIX_REVIEWED', qualified=False,
                         health_samples=result['health_samples'], prefix_records=PREFIX['records'])))


if __name__ == '__main__':
    main()
