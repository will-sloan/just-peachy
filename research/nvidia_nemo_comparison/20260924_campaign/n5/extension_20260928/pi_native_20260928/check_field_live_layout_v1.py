"""CPU14 host preparation checks; README_FIELD_LIVE_LAYOUT_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from field_live_layout_v1 import specification, reservation, start_gate, preflight, encoded, REQUIRED_BINDINGS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--installed-mirror', type=Path, required=True)
    args = parser.parse_args()
    root = args.preparation
    admission = json.loads((root/'ADMISSION_REVIEW_V1.json').read_bytes())
    assert datetime.now(timezone.utc) < datetime.fromisoformat(admission['expires_utc'])
    assert psutil.Process().cpu_affinity() == [14]
    output = root/'HOST_CHECKS_V1.json'
    if output.exists():
        raise FileExistsError('Closed check cannot be replayed')
    rows = []
    def rejected(name, call):
        try:
            call()
        except ValueError as exc:
            rows.append(dict(name=name, rejected=True, error=str(exc)))
        else:
            raise AssertionError(name)
    value = specification()
    assert reservation(value) == 2*value['target_maximum_bytes']+4*1024**2
    assert len(set(value['directories'])) == len(value['directories'])
    assert value['artifact_maximum_bytes'] == sum(r['maximum_bytes'] for r in value['artifacts'].values())
    rows.append(dict(name='all category maxima plus one directory reserve and exact host mirror', passed=True))
    # New integration gate checks; not old helper/float/geometry suites.
    rejected('empty binding registry', lambda: start_gate(value, {}, {}))
    bindings = {k: dict(source_sha256='1'*64, installed=True) for k in REQUIRED_BINDINGS}
    missing = deepcopy(bindings); del missing['native_text_trace']
    rejected('new native text producer omitted', lambda: start_gate(value, missing, {}))
    disabled = deepcopy(bindings); disabled['source_start_stop_restore']['installed'] = False
    rejected('real source binding not installed', lambda: start_gate(value, disabled, {}))
    maximum = dict(layout_sha256=hashlib.sha256(encoded(value)).hexdigest(),
                   target_maximum_bytes=value['target_maximum_bytes'],
                   host_maximum_bytes=value['host_maximum_bytes'],
                   combined_request_bytes=value['combined_request_bytes'])
    short = dict(maximum, host_maximum_bytes=4*1024**2)
    rejected('host metadata alone cannot replace full target backup', lambda: start_gate(value, bindings, short))
    assert start_gate(value, bindings, maximum) == maximum
    rows.append(dict(name='complete declared registry arithmetic', passed=True,
                     scope='declared fixture pins/flags, not actual runtime installation'))
    changed = deepcopy(value); changed['maximum_epochs'] = 2
    rejected('second epoch has no reservation', lambda: reservation(changed))
    changed = deepcopy(value); changed['artifacts']['native_clock_trace']['maximum_bytes'] = 0
    rejected('native S7 trace cannot disappear from allocation', lambda: reservation(changed))
    rejected('unmapped serial source diagnostic', lambda: preflight('failure', 'source-1.json', b'{}'))
    rejected('source bytes cannot use another slot', lambda: preflight('source', 'SOURCE_START.json', b' '*65537))
    rejected('configuration raw overflow', lambda: preflight('config', 'CONFIG.json', b'{"x":1e999}'))
    rejected('TRACE must end on JSON line boundary', lambda: preflight('trace', 'TRACE.jsonl', b'{}', append=True))
    assert preflight('source','SOURCE_START.json',b'{}')['producer']=='source'
    rows.append(dict(name='fixed source output projection', passed=True))
    # Read actual installed source, not runtime constructor fixtures.
    paths = ('app/pipeline.py', 'app/buffers.py', 'vendor/edge_speech_pipeline/runtime.py',
             'vendor/edge_speech_pipeline/research_s7.py', 'app/paths.py', 'native/field_entry_v5.py')
    sources = {}
    trees = {}
    for rel in paths:
        data = (args.installed_mirror/rel).read_bytes()
        trees[rel] = ast.parse(data)
        sources[rel] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    tree = trees['vendor/edge_speech_pipeline/runtime.py']
    native = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='PipelineEngine')
    methods = {n.name:n for n in native.body if isinstance(n, ast.FunctionDef)}
    writes = {'_begin_session':['events.jsonl','labelled_transcript.jsonl','transcript.md','s7_clocks.jsonl'],
              '_write_revised_transcript':['latest_labelled_transcript.jsonl'],
              'record_s6d_consumer_closure':['s6d_consumer_closure.json']}
    for method, names in writes.items():
        strings = {n.value for n in ast.walk(methods[method]) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        assert set(names) <= strings, method
    controls = {n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    assert {'session_summary.json','session_finalization_v3.json'} <= controls
    buffers = ast.unparse(trees['app/buffers.py'])
    assert 'old.unlink(missing_ok=True)' in buffers
    assert 'sink_factory or RotatingText' in buffers
    for path in ('field_live_layout_v1.py','field_native_text_v1.py'):
        ast.parse((Path(__file__).parent/path).read_bytes())
    rows.append(dict(name='actual installed writer sites and deletion route identified', passed=True))
    result = dict(status='PASS_HOST_LAYOUT_AND_INSTALLED_WRITER_AUDIT_ONLY',
                  affinity=psutil.Process().cpu_affinity(), cases=rows,
                  expected_rejections=sum(r.get('rejected',False) for r in rows),
                  sources=sources, allocation=value, native_text_binding_executed=False,
                  real_source_stop_exercised=False, native_dispatch=False, live_accepted=False,
                  completed_utc=datetime.now(timezone.utc).isoformat())
    raw = json.dumps(result,indent=2,allow_nan=False).encode('utf8')
    assert len(raw)<65536
    assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+len(raw)<admission['maximum_new_host_bytes']
    with output.open('xb') as handle:
        handle.write(raw)
    print(json.dumps(dict(status=result['status'],cases=len(rows),rejects=result['expected_rejections'],
                          target=value['target_maximum_bytes'],host=value['host_maximum_bytes'],combined=value['combined_request_bytes'])))


if __name__ == '__main__':
    main()
