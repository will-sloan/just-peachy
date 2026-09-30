"""New entry contract checks only; README_D1_MODE_ENTRY_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
assert psutil.Process().cpu_affinity() == [14]
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path

from d1_mode_entry_v1 import Registry, sha
from d1_method_controls_v1 import canonical
import d1_recovery_mode_entry_v1 as recovery


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mirror', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve the previous check receipt')
    here = Path(__file__).resolve().parent
    raw = (here/'D1_MODE_ENTRY_MANIFEST_V1.json').read_bytes()
    derivation = json.loads((here/'D1_MODE_ENTRY_DERIVATION_V1.json').read_bytes())
    assert sha(raw) == derivation['manifest_sha256']
    mirror = json.loads(args.mirror.read_bytes())
    reader = lambda path:Path(mirror[path]).read_bytes()
    registry = Registry(raw, sha(raw), reader)
    value = json.loads(raw)
    cases = []
    def reject(name, callback):
        try: callback()
        except ValueError: cases.append(dict(case=name, rejected=True))
        else: raise AssertionError('Unexpectedly accepted '+name)

    for mode in ('streaming', 'chunk52', 'delayed'):
        request = registry.request(mode, 'd1-entry-'+mode+'-fresh-v1')
        selected = registry.specification(request)
        assert selected['mode'] == mode and selected['session_id'] == request['session_id']
        pin = value['modes'][mode]['endpoint_module']
        path = Path(mirror[pin['path']])
        spec = importlib.util.spec_from_file_location('entry_host_endpoint_'+mode, path)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert module.CONTRACT_SHA256 == request['endpoint_sha256']
        # Class composition only. No Base constructor or native endpoint verification.
        cls = recovery.controller_class(object, here, selected, None, None, None, None, endpoint=module)
        closure = inspect.getclosurevars(cls._d1_run).nonlocals
        assert closure['expected_frames'] is module.expected_frames
        assert closure['verify_binding'] is module.verify_binding
        assert closure['spec']['mode'] == mode
        cases.append(dict(case='selected_endpoint_factory_closure_'+mode, passed=True))
        selected['mode'] = 'changed'
        request['geometry']['chunk_len'] = -1
        assert registry.specification(registry.request(mode, 'd1-entry-'+mode+'-fresh-v1'))['mode'] == mode
        reject('mutated_geometry_'+mode, lambda q=request:registry.validate(q))
    request = registry.request('streaming', 'd1-entry-streaming-fresh-v1')
    for name, key, val in [('live', 'live_start_available', True), ('endpoint', 'endpoint_sha256', '0'*64),
                           ('extra', 'apply_skip', True), ('mode', 'mode', 'chunk52')]:
        changed = deepcopy(request);changed[key] = val
        reject('mutated_request_'+name, lambda q=changed:registry.validate(q))
    reject('old_session', lambda:registry.request('streaming', registry._inputs['streaming']['session_id']))
    reject('no_session', lambda:registry.request('streaming', None))
    reject('unknown_mode', lambda:registry.request('unknown', 'd1-entry-unknown-v1'))
    reject('unbound_manifest_bytes', lambda:Registry(raw+b' ', sha(raw), reader))
    changed = deepcopy(value)
    changed['modes']['delayed']['endpoint_contract'] = deepcopy(changed['modes']['streaming']['endpoint_contract'])
    corrupt = canonical(changed).encode()
    reject('cross_mode_endpoint_receipt', lambda:Registry(corrupt, sha(corrupt), reader))
    changed = deepcopy(value)
    changed['modes']['streaming']['input']['path'] = '/tmp/unbound-input.json'
    corrupt = canonical(changed).encode()
    reject('outside_campaign_pin', lambda:Registry(corrupt, sha(corrupt), reader))
    first = value['modes']['streaming']['app_source']['path']
    reject('changed_bound_file', lambda:Registry(raw, sha(raw), lambda path:reader(path)+(b' ' if path == first else b'')))
    assert all(sha((here/name).read_bytes()) == digest for name,digest in derivation['parents'].items())
    result = dict(status='PASS_HOST_MODE_ENTRY_CONTRACT_AND_FACTORY_WIRING_ONLY', cases=cases,
        case_count=len(cases), rejected_cases=sum(bool(x.get('rejected')) for x in cases),
        manifest_sha256=sha(raw), bound_metadata_files=len(mirror), cpu_affinity=psutil.Process().cpu_affinity(),
        actual_constructor=False, native_endpoint_lineage_run=False, native_model_run=False,
        process_claim_executed=False, subprocess_launcher_executed=False, GUI=False, capture=False,
        old_sources_unchanged=True, method_and_recovery_body_scope='prepared derivative, no new native qualification')
    data = json.dumps(result, indent=2).encode()
    if len(data) > 32768:raise ValueError('Check receipt cap')
    with args.output.open('xb') as f:f.write(data)
    print(json.dumps({k:v for k,v in result.items() if k != 'cases'}))


if __name__ == '__main__':main()
