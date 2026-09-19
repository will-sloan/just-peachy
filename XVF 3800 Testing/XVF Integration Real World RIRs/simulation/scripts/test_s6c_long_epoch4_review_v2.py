"""Independent, model-free review of the epoch4 long wrapper. See README_S6C_LONG_EPOCH4_REVIEW_V2.md."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
SOURCE=SIM/'scripts/s6c_long_native_epoch4.py'
SOURCE_SHA='9c15795253b17722af6b56e8bc3eb524ce68665bfa2d5de2d95ef940f690ea9b'
RECEIPT_SHA='86482db41724a86684fc495579ac5a7f36294caf260833aef446bba4c5e41a69'

def read_bound(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return json.loads(raw.decode('utf-8-sig')),dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def bind(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def main(output):
    if output.exists():raise ValueError('Independent receipt already exists')
    checks=0
    source=bind(SOURCE)
    assert source['sha256']==SOURCE_SHA;checks+=1
    receipt,receipt_binding=read_bound(REPORT/'long_native_epoch4/SOURCE_CHECKS_V2.json')
    assert receipt_binding['sha256']==RECEIPT_SHA;checks+=1
    for b in receipt['dependencies']+[receipt['previous_source_checks'],receipt['composition'],receipt['execution_manifest']]:
        assert bind(b['path'])==b;checks+=1
    for row in receipt['preserved_previous_sources']:
        assert bind(row['snapshot']['path'])==row['snapshot'];checks+=1
        assert all(row['original'][key]==row['snapshot'][key] for key in ('bytes','sha256'));checks+=1
    spec=importlib.util.spec_from_file_location('independent_long_v2',SOURCE)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    pure=module.checks()
    assert pure['checks']==47 and pure['model_calls']==0 and pure['native_calls']==0;checks+=1
    assert receipt['pure_checks']==pure;checks+=1
    assert set(receipt['rejected_dependency_mutations'])=={'assets','versions','python','input_index','scene_manifest','state_policy','s6c_execution.py','s6c_common.py','runtime.py'};checks+=1
    assert receipt['duration_samples']==29238826 and receipt['duration_sec']==1827.426625;checks+=1
    # Independent exact-read-buffer check: simulate a same-length, old-mtime
    # replacement after the bytes were read. Returned binding must remain for
    # the exact parsed buffer, and a later admission verify must reject it.
    with tempfile.TemporaryDirectory(prefix='s6c_long_independent_') as temp:
        root=Path(temp);authority=root/'authority.json';authority.write_bytes(b'{"value":1}')
        real_read=Path.read_bytes
        def swapped(p):
            raw=real_read(p)
            if p==authority:
                st=p.stat();p.write_bytes(b'{"value":2}');os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
            return raw
        with patch.object(Path,'read_bytes',swapped):value,b=module.read_bound(authority)
        assert value=={'value':1} and b['sha256']==hashlib.sha256(b'{"value":1}').hexdigest();checks+=1
        try:module.verify(b)
        except ValueError:checks+=1
        else:raise AssertionError('Recheck accepted replaced bytes')
        lease=root/'lease.json';lease.write_text('{"pid":1}',encoding='utf-8');lb=module.bind(lease);archive=root/'archive.json'
        with patch.object(module,'read_bound',side_effect=ValueError('injected post-rename read failure')):
            release=module.release_lease(lease,archive,lb)
        assert release['status']=='RELEASED_BINDING_UNVERIFIED' and release['released'] is True and not lease.exists() and archive.exists();checks+=1
        lease.write_text('{"pid":1}',encoding='utf-8');lb=module.bind(lease);before=archive.read_bytes()
        release=module.release_lease(lease,archive,lb)
        assert release['status']=='RELEASE_FAILED' and not release['released'] and lease.exists() and archive.read_bytes()==before;checks+=1
        with patch.object(Path,'rename',side_effect=PermissionError('injected rename failure')):
            release=module.release_lease(lease,root/'new.json',lb)
        assert release['status']=='RELEASE_FAILED' and release['released'] is False and lease.exists();checks+=1
    source_text=SOURCE.read_text(encoding='utf-8-sig')
    tree=ast.parse(source_text);run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    calls=[n for n in ast.walk(run) if isinstance(n,ast.Call)]
    native_calls=[n for n in calls if ast.unparse(n.func)=='driver.native']
    assert len(native_calls)==1;checks+=1
    verify_calls=[n for n in calls if ast.unparse(n.func)=='verify' and ast.unparse(n.args[0]) in ('manifest_binding','admission_binding')]
    assert len(verify_calls)==2 and all(n.lineno<native_calls[0].lineno for n in verify_calls);checks+=1
    save_lines={}
    for n in calls:
        if ast.unparse(n.func)=='common.save' and n.args:
            for label in ('NATIVE_OUTCOME.json','CLOSURE.json'):
                if label in ast.unparse(n.args[0]):save_lines[label]=n.lineno
    release_line=next(n.lineno for n in calls if ast.unparse(n.func)=='release_lease')
    assert save_lines['NATIVE_OUTCOME.json']<release_line<save_lines['CLOSURE.json'];checks+=1
    assert tuple(module.ALLOWED_OVERRIDES)==('load_composition','admit_work','process_sample');checks+=1
    result={'schema':'s6c_long_epoch4_independent_review.v2','status':'PASS_SOURCE_AND_MODEL_FREE_GUARDS',
        'checks':checks,'wrapper_pure_checks':pure,'source':source,'source_admission':receipt_binding,
        'helper':bind(__file__),'readme':bind(Path(__file__).with_name('README_S6C_LONG_EPOCH4_REVIEW_V2.md')),
        'scope':'Read-only source/schema admission and independent temporary-file authority/lease fault checks. No load_sources/source_checks/prepare/run call, model construction, native session, quiet admission or current process/storage census.',
        'resolved_findings':['Exact parsed authority bytes are bound and admitted manifest/quiet bytes are rechecked before native invocation.','Native outcome precedes lease release; CLOSURE distinguishes actual released, failed and released-but-unverified outcomes.'],
        'retained_boundaries':['Actual execution epoch4 versus original source-composition epoch2 must be resolved through the outer receipt.','Unchanged original native body with three declared temporary adapter overrides.','Fixed A/B roster and tier equal the registered candidate; continuous source roster never silently changes.','Periodic sampled resource guards exclude synchronous model load and bounded final join; sampled maxima are not continuous maxima.','External PID/creation closure still required after wrapper returns. Concurrent external file changes after invocation-boundary verification are not prevented by immutable hash declarations.']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(bind(output),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
